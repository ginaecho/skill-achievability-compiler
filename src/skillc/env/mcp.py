"""MCP adapter: the MCP servers an agent is configured with, and their tools.

Reads the standard configuration files -- `.mcp.json` (Claude Code project),
`claude_desktop_config.json` / `~/.claude.json` (`mcpServers`), and
`.vscode/mcp.json` (`servers`) -- and records one `mcp_server` node per
server.  Only environment variable *names*, the executable name, the argument
count and the URL without credentials or query are kept: argument and secret
values never enter a snapshot.

Listing a server's tools means starting it, which runs a program from the
user's configuration, so it happens only on request (`list_tools=True`) and
only for stdio servers: skillc speaks just enough MCP (initialize,
notifications/initialized, paged tools/list over newline-delimited JSON-RPC)
and stops the process afterwards.  Servers whose tools were not listed are
recorded as unknown, so their absence never refutes anything.

`list_http_tools` speaks the same three messages to a streamable HTTP server
(JSON-RPC over POST, a JSON or SSE answer) for adapters that already hold a
URL and a bearer token, such as the Foundry toolbox probe (`env.foundry`).
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .. import __version__
from .model import Environment

PROTOCOL_VERSION = "2025-06-18"
DEFAULT_CONFIGS = (".mcp.json", ".vscode/mcp.json")


class MCPProbeError(RuntimeError):
    """A server could not be started or did not answer like an MCP server."""


class MCPConfigError(ValueError):
    """A configuration file is valid JSON but not a recognised MCP shape."""


def servers_in(config: Any) -> dict[str, dict]:
    """Server specs from any of the common configuration shapes."""
    out: dict[str, dict] = {}
    for key in ("mcpServers", "servers"):
        out.update(_object(config, key))
    for project in _object(config, "projects").values():
        out.update(_object({} if project is None else project, "mcpServers"))
    return {name: spec for name, spec in out.items() if isinstance(spec, dict)}


def _object(container: Any, key: str) -> dict:
    if not isinstance(container, dict):
        raise MCPConfigError(f"expected an object around {key!r}")
    value = container.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise MCPConfigError(f"{key!r} must be an object")
    return value


def probe(configs: list[str | Path], list_tools: bool = False,
          timeout: float = 20.0) -> Environment:
    env = Environment()
    for path in configs:
        p = Path(path).expanduser()
        if not p.exists():
            continue
        try:
            servers = servers_in(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, MCPConfigError) as e:
            env.mark_unknown(f"mcp_config:{p}", str(e)[:200])
            continue
        env.sources.append({"adapter": "mcp", "mode": "live" if list_tools else "config",
                            "detail": str(p)})
        for name, spec in servers.items():
            try:
                _check_server(spec)
            except MCPConfigError as e:
                env.mark_unknown(f"mcp_server:{name}", str(e)[:200])
                continue
            _add_server(env, name, spec, list_tools, timeout)
    return env


def _check_server(spec: dict) -> None:
    """Reject server specs whose fields have the wrong shape, before any is used."""
    if not isinstance(spec.get("command", ""), str):
        raise MCPConfigError("command must be a string")
    args = spec.get("args", [])
    if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
        raise MCPConfigError("args must be a list of strings")
    if not isinstance(spec.get("env") or {}, dict):
        raise MCPConfigError("env must be an object")
    if not isinstance(spec.get("type", ""), str):
        raise MCPConfigError("type must be a string")
    url = spec.get("url")
    if url is not None:
        if not isinstance(url, str):
            raise MCPConfigError("url must be a string")
        try:
            _ = urlsplit(url).port          # raises on an invalid port
        except ValueError as e:
            raise MCPConfigError(f"invalid url: {e}") from None


def _add_server(env: Environment, name: str, spec: dict, list_tools: bool,
                timeout: float) -> None:
    transport = spec.get("type") or ("stdio" if "command" in spec else "http")
    # Arguments and URL credentials/queries can carry secrets; keep only identifying metadata.
    command = Path(str(spec.get("command") or "")).name or None
    server = env.add_node(f"mcp/{name}", "mcp_server", name, transport=transport,
                          command=command, arg_count=len(spec.get("args") or []) or None,
                          url=_public_url(spec.get("url")),
                          env_vars=sorted(spec.get("env") or {}) or None)
    if not list_tools:
        env.mark_unknown(f"mcp_tools:{name}", "tools not listed (probe with --list-tools)")
        return
    if transport != "stdio":
        env.mark_unknown(f"mcp_tools:{name}", f"{transport} servers are not listed by skillc")
        return
    try:
        for tool in list_stdio_tools(spec, timeout):
            node = env.add_node(f"mcp/{name}/{tool['name']}", "tool", tool["name"],
                                description=(tool.get("description") or "")[:200] or None)
            env.add_edge(server, node, "exposes")
    except (MCPProbeError, OSError) as e:
        env.mark_unknown(f"mcp_tools:{name}", str(e)[:300])


def _public_url(url: Any) -> str | None:
    """Scheme, host, port and path only: no user info, query or fragment."""
    if not isinstance(url, str) or not url:
        return None
    parts = urlsplit(url)
    host = parts.hostname or ""
    netloc = f"{host}:{parts.port}" if parts.port else host
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


def list_stdio_tools(spec: dict, timeout: float = 20.0) -> list[dict]:
    """Start a stdio MCP server, list its tools (all pages), stop it."""
    proc = subprocess.Popen([spec["command"], *spec.get("args", [])],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                            env={**os.environ, **(spec.get("env") or {})})
    lines: queue.Queue[str | None] = queue.Queue()

    def pump() -> None:
        for line in proc.stdout:
            lines.put(line)
        lines.put(None)

    threading.Thread(target=pump, daemon=True).start()

    def send(msg: dict) -> None:
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()

    def answer(request_id: int) -> Any:
        while True:
            try:
                line = lines.get(timeout=timeout)
            except queue.Empty:
                raise MCPProbeError(f"no answer within {timeout:g}s") from None
            if line is None:
                raise MCPProbeError("the server exited")
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue                      # logging on stdout; not protocol
            if msg.get("id") == request_id:
                if "error" in msg:
                    raise MCPProbeError(f"server error: {msg['error']}")
                return msg.get("result") or {}

    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": PROTOCOL_VERSION, "capabilities": {},
                         "clientInfo": {"name": "skillc", "version": __version__}}})
        answer(1)
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        tools, cursor, request_id = [], None, 2
        while True:
            send({"jsonrpc": "2.0", "id": request_id, "method": "tools/list",
                  "params": {"cursor": cursor} if cursor else {}})
            page = answer(request_id)
            tools += [t for t in page.get("tools") or [] if isinstance(t, dict) and t.get("name")]
            cursor = page.get("nextCursor")
            if not cursor:
                return tools
            request_id += 1
    finally:
        proc.kill()
        proc.wait(timeout=5)


def list_http_tools(url: str, token: str | None, timeout: float = 20.0) -> list[dict]:
    """List the tools of a streamable HTTP MCP server (all pages).

    The client side of the transport only: `initialize`, the
    `notifications/initialized` notification, then `tools/list` until the
    server returns no `nextCursor`, each as a JSON-RPC POST that accepts a
    JSON body or an SSE stream whose `data:` lines carry the messages.  A
    `Mcp-Session-Id` the server assigns is sent back on every later request.
    The token travels only in the Authorization header: it is never logged,
    raised in an error or stored.
    """
    session: dict[str, str] = {}

    def post(msg: dict) -> Any:
        headers = {"Content-Type": "application/json",
                   "Accept": "application/json, text/event-stream", **session}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url, data=json.dumps(msg).encode("utf-8"),
                                     headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                sid = resp.headers.get("Mcp-Session-Id")
                if sid:
                    session["Mcp-Session-Id"] = sid
                body = resp.read().decode("utf-8", "replace")
                content_type = resp.headers.get("Content-Type") or ""
        except urllib.error.HTTPError as e:
            raise MCPProbeError(f"HTTP {e.code} from {_public_url(url)}") from None
        except (urllib.error.URLError, OSError) as e:
            reason = getattr(e, "reason", None) or e
            raise MCPProbeError(f"{_public_url(url)}: {str(reason)[:200]}") from None
        if "id" not in msg:
            return None                       # a notification has no answer
        for answer in _rpc_messages(body, content_type):
            if answer.get("id") == msg["id"]:
                if "error" in answer:
                    raise MCPProbeError(f"server error: {answer['error']}")
                return answer.get("result") or {}
        raise MCPProbeError(f"no answer to {msg['method']} in the response")

    post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
          "params": {"protocolVersion": PROTOCOL_VERSION, "capabilities": {},
                     "clientInfo": {"name": "skillc", "version": __version__}}})
    post({"jsonrpc": "2.0", "method": "notifications/initialized"})
    tools, cursor, request_id = [], None, 2
    while True:
        page = post({"jsonrpc": "2.0", "id": request_id, "method": "tools/list",
                     "params": {"cursor": cursor} if cursor else {}})
        tools += [t for t in page.get("tools") or [] if isinstance(t, dict) and t.get("name")]
        cursor = page.get("nextCursor")
        if not cursor:
            return tools
        request_id += 1


def _rpc_messages(body: str, content_type: str) -> list[dict]:
    """The JSON-RPC messages in an HTTP answer: a JSON object or array, or
    the `data:` payloads of an SSE stream (one event may span several lines)."""
    text = body.strip()
    if not text:
        return []
    if "text/event-stream" in content_type or text.startswith(("data:", "event:", ":")):
        found: list[dict] = []
        chunks: list[str] = []
        for line in [*text.splitlines(), ""]:
            if line.startswith("data:"):
                chunks.append(line[5:].strip())
            elif not line.strip() and chunks:
                try:
                    msg = json.loads("\n".join(chunks))
                except json.JSONDecodeError:
                    msg = None
                chunks = []
                found += [m for m in (msg if isinstance(msg, list) else [msg])
                          if isinstance(m, dict)]
        return found
    try:
        msg = json.loads(text)
    except json.JSONDecodeError:
        raise MCPProbeError("the answer is neither JSON nor an event stream") from None
    return [m for m in (msg if isinstance(msg, list) else [msg]) if isinstance(m, dict)]

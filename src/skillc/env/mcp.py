"""MCP adapter: the MCP servers an agent is configured with, and their tools.

Reads the standard configuration files -- `.mcp.json` (Claude Code project),
`claude_desktop_config.json` / `~/.claude.json` (`mcpServers`), and
`.vscode/mcp.json` (`servers`) -- and records one `mcp_server` node per
server.  Only environment variable *names* are kept, never their values.

Listing a server's tools means starting it, which runs a program from the
user's configuration, so it happens only on request (`list_tools=True`) and
only for stdio servers: skillc speaks just enough MCP (initialize,
notifications/initialized, paged tools/list over newline-delimited JSON-RPC)
and stops the process afterwards.  Servers whose tools were not listed are
recorded as unknown, so their absence never refutes anything.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
from pathlib import Path
from typing import Any

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
            _add_server(env, name, spec, list_tools, timeout)
    return env


def _add_server(env: Environment, name: str, spec: dict, list_tools: bool,
                timeout: float) -> None:
    transport = spec.get("type") or ("stdio" if "command" in spec else "http")
    server = env.add_node(f"mcp/{name}", "mcp_server", name, transport=transport,
                          command=" ".join([spec.get("command", ""), *spec.get("args", [])]).strip()
                          or None,
                          url=spec.get("url"), env_vars=sorted(spec.get("env") or {}) or None)
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

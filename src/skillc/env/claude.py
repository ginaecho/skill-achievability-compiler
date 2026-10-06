"""Claude adapter: the runtime a Claude agent works in, read without side effects.

What a Claude agent can achieve is decided by its runtime, not by a cloud
account alone:

    tools        built-in tools and connector (MCP) tools the session has
    permissions  allow / ask / deny rules from the Claude settings files
    egress       which hosts the network policy lets it reach
    programs     installed command-line programs and Python modules
    credentials  which credential variables are set (names only, never values)
    paths        which directories it can write
    connectors   MCP servers configured, and those still waiting for sign-in

Each becomes a node of the provider-neutral graph:

    service  runtime/claude        exposes the built-in tools
    service  egress/<host>         available: the host answered through the proxy
    service  program/<name>        available: on PATH
    service  pymodule/<name>       available: importable
    service  credential/<NAME>     available: the variable is set and non-empty
    scope    path:<dir>            writable
    role     claude/allow          actions: the allow rules  (ask rules: a
                                   conditioned assignment -- an approval)
    deny     claude/deny           actions: the deny rules
    mcp_server / tool              as in env.mcp; needs_auth for pending sign-ins

Egress is checked with one HTTPS request per host.  A refusal by the egress
proxy (HTTP 403/407 on CONNECT) is an observed "no"; a timeout or a name that
does not resolve is recorded with its reason and treated as "no" only when it
is definite.  Probing a host sends no credentials and changes nothing.
"""
from __future__ import annotations

import importlib.util
import ipaddress
import json
import os
import platform as _platform
import shutil
import socket
import ssl
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from importlib import resources
from pathlib import Path

from . import mcp
from .model import Environment

SETTINGS_FILES = ("~/.claude/settings.json", "~/.claude/settings.local.json",
                  "~/.claude/launcher-settings.json", ".claude/settings.json",
                  ".claude/settings.local.json", "/etc/claude-code/managed-settings.json")
MCP_CONFIGS = ("~/.claude.json", ".mcp.json")
AUTH_CACHE = "~/.claude/mcp-needs-auth-cache.json"
CREDENTIALS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GITHUB_TOKEN", "GH_TOKEN",
               "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AZURE_CLIENT_ID",
               "AZURE_CLIENT_SECRET", "AZURE_TENANT_ID", "GOOGLE_APPLICATION_CREDENTIALS",
               "CLOUDSDK_AUTH_ACCESS_TOKEN", "HF_TOKEN", "NPM_TOKEN", "SLACK_BOT_TOKEN",
               "STRIPE_API_KEY", "DATABASE_URL")


def default_tools() -> list[str]:
    """The Claude Code tool set from the bundled `claude-code` profile."""
    raw = resources.files("skillc").joinpath("data/profiles/claude-code.json")
    return list(json.loads(raw.read_text(encoding="utf-8"))["tools"])


def probe(*, root: str | Path = ".", hosts: Iterable[str] = (),
          programs: Iterable[str] = (), modules: Iterable[str] = (),
          paths: Iterable[str] = (), credentials: Iterable[str] = CREDENTIALS,
          tools: Iterable[str] | None = None, connectors: dict[str, list[str]] | None = None,
          settings: Iterable[str] = SETTINGS_FILES, mcp_configs: Iterable[str] = MCP_CONFIGS,
          check_egress: bool = True, timeout: float = 8.0) -> Environment:
    """Read the Claude runtime the agent is in.

    `tools` overrides the built-in tool list; `connectors` maps a connected
    MCP server (a claude.ai connector, say) to the tool names it exposes, for
    servers that are not in any configuration file on disk."""
    root = Path(root).resolve()
    env = Environment()
    env.sources.append({"adapter": "claude", "mode": "live",
                        "detail": f"{os.environ.get('CLAUDE_CODE_ENTRYPOINT', 'claude')} "
                                  f"{os.environ.get('CLAUDE_CODE_VERSION', '')} at {root}"})
    principal = env.add_node("principal/claude-agent", "principal", "claude agent",
                             type="agent",
                             remote=os.environ.get("CLAUDE_CODE_REMOTE") == "true")
    env.add_node("/", "scope", "session", level="root")
    system = _platform.system().lower()
    for name in ("linux", "windows", "macos", "mobile_device", "gpu"):
        env.add_node(f"platform/{name}", "service", name, type="platform",
                     available=name == {"darwin": "macos"}.get(system, system)
                     or (name == "gpu" and shutil.which("nvidia-smi") is not None))
    _tools(env, list(tools) if tools is not None else default_tools())
    _permissions(env, principal, root, settings)
    _paths(env, [str(root), *paths])
    for name in programs:
        env.add_node(f"program/{name}", "service", name, available=shutil.which(name) is not None,
                     type="program")
    if shutil.which("docker"):
        ok = _daemon_answers(["docker", "info", "--format", "{{.ServerVersion}}"])
        env.add_node("daemon/docker", "service", "docker", type="daemon", available=ok[0],
                     why=ok[1])
    for name in modules:
        found = _importable(name)
        env.add_node(f"pymodule/{name}", "service", name, available=found, type="python module")
    for name in credentials:
        env.add_node(f"credential/{name}", "service", name,
                     available=bool(os.environ.get(name)), type="credential")
    for host in dict.fromkeys(hosts):
        if check_egress:
            ok, why = egress(host, timeout)
            env.add_node(f"egress/{host}", "service", host, available=ok, why=why,
                         type="egress")
    if not check_egress and hosts:
        env.mark_unknown("egress", "egress was not checked (--no-egress)")
    _connectors(env, connectors or {}, [str(Path(c).expanduser() if c.startswith("~")
                                            else root / c) for c in mcp_configs])
    return env


def _tools(env: Environment, tools: list[str]) -> None:
    runtime = env.add_node("runtime/claude", "service", "claude runtime", available=True,
                           type="runtime")
    for name in tools:
        env.add_edge(runtime, env.add_node(f"tool/{name}", "tool", name), "exposes")


def _rule_patterns(rules: list[str]) -> list[str]:
    """Claude permission rules as wildcard patterns over `Tool(argument)`:
    `Bash` -> `Bash(*)` and `Bash`; `Bash(npm run test:*)` -> `Bash(npm run test*)`."""
    out = []
    for rule in rules:
        if "(" not in rule:
            out += [rule, f"{rule}(*)"]
        else:
            out.append(rule.replace(":*)", "*)"))
    return out


def _permissions(env: Environment, principal: str, root: Path, files: Iterable[str]) -> None:
    allow, ask, deny, read = [], [], [], []
    for name in files:
        path = Path(name).expanduser() if name.startswith(("~", "/")) else root / name
        if not path.exists():
            continue
        try:
            perms = json.loads(path.read_text(encoding="utf-8")).get("permissions") or {}
        except (OSError, json.JSONDecodeError) as e:
            env.mark_unknown(f"settings:{path}", str(e)[:200])
            continue
        read.append(str(path))
        allow += perms.get("allow") or []
        ask += perms.get("ask") or []
        deny += perms.get("deny") or []
    env.sources.append({"adapter": "claude", "mode": "settings",
                        "detail": ", ".join(read) or "no settings files"})
    if allow:
        env.add_edge(principal, env.add_node("claude/allow", "role", "allow rules",
                                             actions=_rule_patterns(allow)),
                     "assigned", scope="/")
    if ask:
        env.add_edge(principal, env.add_node("claude/ask", "role", "ask rules",
                                             actions=_rule_patterns(ask)),
                     "assigned", scope="/", condition="the user approves each use")
    if deny:
        env.add_edge(principal, env.add_node("claude/deny", "deny", "deny rules",
                                             actions=_rule_patterns(deny)),
                     "denied", scope="/")


def _paths(env: Environment, paths: list[str]) -> None:
    for p in dict.fromkeys(paths):
        path = Path(p).expanduser()
        target = next(a for a in (path, *path.parents) if a.exists())
        env.add_node(f"path:{path}", "scope", str(path), level="path",
                     exists=path.exists(),
                     writable=os.access(target, os.W_OK)
                     and (target.is_dir() or target == path))
        env.add_edge("/", f"path:{path}", "contains")


def _daemon_answers(command: list[str], timeout: float = 10.0) -> tuple[bool, str]:
    """Whether a read-only status command reaches its daemon."""
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout,
                              check=False)
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)[:200]
    detail = (proc.stdout or proc.stderr).strip().splitlines()
    return proc.returncode == 0, (detail[-1] if detail else f"exit {proc.returncode}")[:200]


def _importable(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def egress(host: str, timeout: float = 8.0) -> tuple[bool, str]:
    """One HTTPS request to `host` through the session's proxy settings.

    Any HTTP answer from the host (even 404, 401 or a redirect) proves the
    network path; a 403/407 on the proxy tunnel is the egress policy refusing
    the host. Hosts can come from intent text, so destinations that resolve to
    loopback, private, link-local or reserved addresses are never contacted and
    redirects are not followed."""
    url = host if host.startswith("https://") else f"https://{host}/"
    blocked = _non_public_address(urllib.parse.urlsplit(url).hostname or "")
    if blocked:
        return False, f"refused: {host} resolves to non-public address {blocked}"
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "skillc-probe"})
    try:
        with _open(req, timeout, ssl.create_default_context(
                cafile=os.environ.get("SSL_CERT_FILE"))) as r:
            return True, f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        return True, f"HTTP {e.code} from the host"
    except urllib.error.URLError as e:
        reason = str(e.reason)
        if "403" in reason or "407" in reason:
            return False, f"egress policy refused the host ({reason})"
        return False, reason[:200]
    except TimeoutError:
        return False, f"no answer within {timeout:g}s"
    except (OSError, ValueError) as e:
        return False, str(e)[:200]


def _non_public_address(hostname: str) -> str | None:
    """The first non-global address `hostname` resolves to, if any.

    An unresolvable name is left to the proxy, which then decides egress."""
    try:
        infos = socket.getaddrinfo(hostname, 443, proto=socket.IPPROTO_TCP)
    except (OSError, UnicodeError):
        return None
    for info in infos:
        address = ipaddress.ip_address(info[4][0].split("%")[0])
        if not address.is_global:
            return str(address)
    return None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None                     # the 3xx itself is the answer


def _opener(context: ssl.SSLContext) -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler(context=context))


def _open(req: urllib.request.Request, timeout: float, context: ssl.SSLContext):
    return _opener(context).open(req, timeout=timeout)


def _connectors(env: Environment, connectors: dict[str, list[str]],
                configs: list[str]) -> None:
    configured = mcp.probe(configs)
    for n in configured.nodes.values():
        env.add_node(n["id"], n["kind"], n["name"], **n["attrs"])
    for e in configured.edges:
        env.add_edge(e["src"], e["dst"], e["kind"], **e["attrs"])
    for u in configured.unknown:
        env.mark_unknown(u["what"], u.get("why", ""))
    for name, tool_names in connectors.items():
        server = env.add_node(f"mcp/{name}", "mcp_server", name, transport="connector")
        for t in tool_names:
            env.add_edge(server, env.add_node(f"mcp/{name}/{t}", "tool", t), "exposes")
    cache = Path(AUTH_CACHE).expanduser()
    if cache.exists():
        try:
            pending = json.loads(cache.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pending = {}
        for name in pending:
            env.add_node(f"mcp/{name}", "mcp_server", name, transport="connector",
                         needs_auth=True)

"""Copilot adapter: the runtime a GitHub Copilot CLI agent works in, read without side effects.

    tools        the built-in tools (the `copilot-cli` profile), with this platform's shell:
                 `powershell` on Windows, `bash` elsewhere
    permissions  what Copilot runs without asking (reads, search, questions), the approvals
                 saved for this repository in permissions-config.json, and the URLs saved
                 in settings.json; everything else asks first
    connectors   the built-in GitHub MCP server and the servers in ~/.copilot/mcp-config.json,
                 .mcp.json and .github/mcp.json
    trust        whether the folder is one of Copilot's trusted folders
    machine      programs, modules, credential names, paths, egress (shared with env.claude)

The configuration directory is ~/.copilot, or $COPILOT_HOME.  Only the keys named here are
read: config.json also holds authentication data, which is never touched.  Deny rules and
tool filters (--deny-tool, --available-tools, --excluded-tools) are launch options that no
file records, so they are reported as unknown, never assumed absent.  MCP tools are not
listed (no server is started) and count as unknown.
"""
from __future__ import annotations

import json
import os
import platform as _platform
from collections.abc import Iterable
from importlib import resources
from pathlib import Path

from . import mcp
from .claude import CREDENTIALS, add_machine
from .model import Environment, norm_id

SHELL_FAMILIES = ("bash", "powershell")
# tools Copilot runs without an approval prompt (reads inside the working directory,
# search, questions to the user, skills and subagent bookkeeping)
NO_PROMPT = ("view", "glob", "grep", "rg", "ask_user", "skill", "task", "list_agents",
             "read_agent", "write_agent")
WRITE_TOOLS = ("create", "edit", "apply_patch")
CREDENTIAL_NAMES = ("COPILOT_GITHUB_TOKEN", *CREDENTIALS)
BUILTIN_MCP = "github"


def copilot_home() -> Path:
    return Path(os.environ.get("COPILOT_HOME") or Path.home() / ".copilot")


def default_tools(system: str | None = None) -> list[str]:
    """The `copilot-cli` profile with only this platform's shell family."""
    raw = resources.files("skillc").joinpath("data/profiles/copilot-cli.json")
    tools = json.loads(raw.read_text(encoding="utf-8"))["tools"]
    shell = "powershell" if (system or _platform.system()).lower() == "windows" else "bash"
    other = next(s for s in SHELL_FAMILIES if s != shell)
    return [t for t in tools if t != other and not t.endswith(f"_{other}")]


def probe(*, root: str | Path = ".", home: str | Path | None = None,
          hosts: Iterable[str] = (), programs: Iterable[str] = (),
          modules: Iterable[str] = (), paths: Iterable[str] = (),
          credentials: Iterable[str] = CREDENTIAL_NAMES, tools: Iterable[str] | None = None,
          connectors: dict[str, list[str]] | None = None, check_egress: bool = True,
          timeout: float = 8.0) -> Environment:
    """Read the Copilot CLI runtime an agent started in `root` would have.

    `home` overrides the configuration directory; `tools` overrides the built-in list
    (e.g. after --available-tools); `connectors` maps a connected MCP server to the tool
    names it exposes, for servers whose tools are known from elsewhere."""
    root = Path(root).resolve()
    home = Path(home) if home is not None else copilot_home()
    env = Environment()
    principal = env.add_node("principal/copilot-agent", "principal", "copilot agent",
                             type="agent")
    env.add_node("/", "scope", "session", level="root")
    tools = list(tools) if tools is not None else default_tools()
    _tools(env, tools)
    read, extra_dirs = _permissions(env, principal, home, _location(root), tools)
    add_machine(env, root, hosts=hosts, programs=programs, modules=modules,
                paths=[*paths, *extra_dirs], credentials=credentials,
                check_egress=check_egress, timeout=timeout)
    _trust(env, home, root)
    configs = [home / "mcp-config.json", root / ".mcp.json", root / ".github" / "mcp.json"]
    read += [str(c) for c in configs if c.exists()]
    _connectors(env, connectors or {}, configs)
    env.sources.append({"adapter": "copilot", "mode": "settings",
                        "detail": ", ".join(read) or "no Copilot settings files"})
    env.mark_unknown("deny_rules", "Copilot deny rules and tool filters are launch options "
                                   "(--deny-tool, --excluded-tools); no file records them")
    return env


def _tools(env: Environment, tools: list[str]) -> None:
    runtime = env.add_node("runtime/copilot", "service", "copilot runtime", available=True,
                           type="runtime")
    for name in tools:
        env.add_edge(runtime, env.add_node(f"tool/{name}", "tool", name), "exposes")


def _location(root: Path) -> Path:
    """The key Copilot saves approvals under: the Git root, else the directory itself."""
    return next((p for p in (root, *root.parents) if (p / ".git").exists()), root)


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _same_path(a: str | Path, b: Path) -> bool:
    return os.path.normcase(os.path.normpath(str(a))) == os.path.normcase(os.path.normpath(str(b)))


def _approval_patterns(approvals: list, tools: list[str]) -> list[str]:
    """Saved approvals as wildcard patterns over `tool(argument)`."""
    shells = [t for t in tools if t in SHELL_FAMILIES]
    out: list[str] = []
    for item in approvals:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind")
        if kind == "commands":
            for command in item.get("commandIdentifiers") or []:
                if isinstance(command, str) and command.strip():
                    out += [p for s in shells
                            for p in (f"{s}({command.strip()})", f"{s}({command.strip()} *)")]
        elif kind == "write":
            out += [p for t in WRITE_TOOLS for p in (t, f"{t}(*)")]
        elif kind == "read":
            out += ["view", "view(*)"]
    return out


def _permissions(env: Environment, principal: str, home: Path, location: Path,
                 tools: list[str]) -> tuple[list[str], list[str]]:
    """Allow rules from what runs without asking and from saved approvals; returns the
    files read and the extra directories saved for this location.  A built-in tool no
    rule allows asks first, which `facts.need` reports as possible under an approval."""
    read: list[str] = []
    env.add_edge(principal, env.add_node(
        "copilot/no-prompt", "role", "runs without asking",
        actions=[p for t in NO_PROMPT for p in (t, f"{t}(*)")]), "assigned", scope="/")
    config = home / "permissions-config.json"
    if not config.exists() and (home / "permissions-config").exists():
        config = home / "permissions-config"                 # the legacy file name
    data = _read_json(config) if config.exists() else None
    if config.exists() and data is None:
        env.mark_unknown(f"settings:{config}", "permissions file could not be read")
    approvals: list = []
    extra_dirs: list[str] = []
    if data is not None:
        read.append(str(config))
        for key, entry in (data.get("locations") or {}).items():
            if _same_path(key, location) and isinstance(entry, dict):
                approvals = entry.get("tool_approvals") or []
                extra_dirs = [d for d in entry.get("allowed_directories") or []
                              if isinstance(d, str)]
    settings = _read_json(home / "settings.json")
    urls = [u for u in (settings or {}).get("allowedUrls") or [] if isinstance(u, str)]
    if settings is not None:
        read.append(str(home / "settings.json"))
    patterns = _approval_patterns(approvals, tools)
    patterns += [p for u in urls for p in (f"web_fetch({u})", f"web_fetch(https://{u})",
                                           f"web_fetch(https://{u}/*)")]
    if patterns:
        env.add_edge(principal, env.add_node("copilot/approved", "role", "saved approvals",
                                             actions=patterns), "assigned", scope="/")
    return read, extra_dirs


def _trust(env: Environment, home: Path, root: Path) -> None:
    """Record whether `root` is in a trusted folder; read only the trustedFolders key."""
    folders = (_read_json(home / "config.json") or {}).get("trustedFolders") or []
    trusted = any(isinstance(f, str) and (_same_path(f, root)
                                          or any(_same_path(f, p) for p in root.parents))
                  for f in folders)
    node = env.nodes.get(norm_id(f"path:{root}"))
    if node is not None:
        node["attrs"]["trusted"] = trusted


def _connectors(env: Environment, connectors: dict[str, list[str]],
                configs: list[Path]) -> None:
    env.add_node(f"mcp/{BUILTIN_MCP}", "mcp_server", BUILTIN_MCP, transport="built-in",
                 builtin=True)
    env.mark_unknown(f"mcp_tools:{BUILTIN_MCP}", "built-in server; its tools are not listed")
    configured = mcp.probe([str(c) for c in configs])
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

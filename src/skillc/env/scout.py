"""Microsoft Scout adapter: the desktop agent's tools and approvals, read from its settings.

    probe(home)               what Scout on this PC is set up to do, as a plain dict (names only)
    runtime_manifest(obs)     the built-in `scout-desktop` manifest adjusted to what was observed
    provenance(obs)           which parts of that manifest were observed and which are policy

Only two files of the Scout home (default `~/.scout`) are opened: `m-mcp-servers.json` (the
MCP servers and the tool names they list) and `m-settings.json` (the permission flags).  Of
the `skills` folder only the directory names are read.  Nothing else in the Scout home is
opened: not the sign-in data, not encrypted files, not sessions, logs or diagnostics.  Of the
server configuration only `builtin`, `enabled`, `autoApprove`, `disabledTools` and `tools` are
kept; commands, arguments and environment variables are never copied.  Of the permission
`allow` list and `denyPatterns` only the counts are kept (they can hold URLs and paths).

Whether the GitHub CLI is signed in is decided only by whether its hosts file exists in its
configuration folder; the file is never opened.

Missing or unreadable files give empty sections and a note in `sources`, never an exception.
"""
from __future__ import annotations

import json
import os
import platform as _platform
import re
import shutil
from collections.abc import Callable
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path

SERVERS_FILE = "m-mcp-servers.json"
SETTINGS_FILE = "m-settings.json"
PROGRAMS = ("git", "gh", "python", "node", "npx", "pandoc", "az")

AUTO, ASKS, DISABLED = "auto-approved", "asks first", "disabled"
# First word of a tool name (after its server prefix) that says it only reads.
READ_VERBS = frozenset({"list", "get", "search", "read", "find", "preview", "resolve",
                        "stat", "diff", "recall", "view", "snapshot", "console", "network"})
# Tool-name prefixes that name the family a tool belongs to.
PREFIXES = ("workiq_", "workspace_", "browser_", "m_")
# Local file-writing tools: the only tools `autoApproveAllWrites` is taken to cover.
LOCAL_WRITE_PREFIXES = ("workspace_",)
LOCAL_WRITE_SERVERS = ("filesystem",)

# WorkIQ ability groups, in words, by the words in their tool names.
WORKIQ_GROUPS = (
    ("mail", ("email", "mail_folder", "message_rule", "draft")),
    ("calendar and rooms", ("event", "meeting_times", "schedule", "room", "categories")),
    ("files and sharing", ("file", "share", "m365_link")),
    ("lists", ("sharepoint_list", "task", "subtask")),
    ("chats", ("chat", "channel", "teams")),
)


def scout_home() -> Path:
    return Path.home() / ".scout"


def gh_config_dir() -> Path:
    """The GitHub CLI configuration folder: GH_CONFIG_DIR, else the platform default."""
    if os.environ.get("GH_CONFIG_DIR"):
        return Path(os.environ["GH_CONFIG_DIR"])
    if _platform.system().lower() == "windows" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "GitHub CLI"
    if os.environ.get("XDG_CONFIG_HOME"):
        return Path(os.environ["XDG_CONFIG_HOME"]) / "gh"
    return Path.home() / ".config" / "gh"


def _read_json(path: Path, sources: list[str]) -> dict:
    if not path.is_file():
        sources.append(f"{path.name}: missing")
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        sources.append(f"{path.name}: unreadable")
        return {}
    if not isinstance(data, dict):
        sources.append(f"{path.name}: not a JSON object")
        return {}
    sources.append(path.name)
    return data


def _dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _bare(name: str) -> str:
    for prefix in PREFIXES:
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def _reads_only(name: str) -> bool:
    return _bare(name).split("_", 1)[0] in READ_VERBS


def _writes_local(name: str, server: str | None) -> bool:
    return (name.startswith(LOCAL_WRITE_PREFIXES) or server in LOCAL_WRITE_SERVERS) \
        and not _reads_only(name)


def _skills(folder: Path, origin: str) -> list[dict]:
    if not folder.is_dir():
        return []
    out = []
    for p in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
        if p.is_dir() or (p.is_file() and p.suffix.lower() == ".md"):
            out.append({"name": p.name, "origin": origin})
    return out


def probe(home: Path | None = None, copilot_home: Path | None = None, *,
          which: Callable[[str], str | None] | None = None,
          gh_config: Path | None = None) -> dict:
    """What Microsoft Scout on this PC is set up to do (names and flags only).

    Tool status, decided per tool in this order (conservative: anything not covered by a
    rule below asks first):

      1. "disabled"       the tool is in `permissions.disabledTools`, or its server is
                          disabled (`permissions.servers.<s>.enabled` is false);
      2. "auto-approved"  `autoApprove.global` is true;
      3. the per-tool flag in `permissions.tools` (`tool:<name>` or
         `mcp:<server>:<tool>`): true is "auto-approved", false is "asks first";
      4. "auto-approved"  the tool's server auto-approves
                          (`permissions.servers.<s>.autoApprove` or
                          `autoApprove.perServer.<s>`);
      5. "auto-approved"  `permissions.autoApproveReadOnly` is true and the tool's name
                          says it only reads (its first word after the family prefix is
                          list, get, search, read, find, preview, resolve, stat, diff,
                          recall, view, snapshot, console or network);
      6. "auto-approved"  `permissions.autoApproveAllWrites` is true and the tool only
                          writes local files (a `workspace_` tool, or a tool of the
                          `filesystem` server); never mail, chat, calendar or web tools;
      7. "asks first"     otherwise.

    `which` replaces `shutil.which` and `gh_config` the GitHub CLI configuration folder
    (both for tests)."""
    home = Path(home) if home is not None else scout_home()
    copilot_home = Path(copilot_home) if copilot_home is not None \
        else Path(os.environ.get("COPILOT_HOME") or Path.home() / ".copilot")
    which = which or shutil.which
    sources: list[str] = []
    servers_doc = _read_json(home / SERVERS_FILE, sources)
    settings = _read_json(home / SETTINGS_FILE, sources)
    file_servers = _dict(servers_doc.get("servers"))
    perms = _dict(settings.get("permissions"))
    perm_servers = _dict(perms.get("servers"))
    perm_tools = _dict(perms.get("tools"))
    global_auto = _dict(settings.get("autoApprove"))
    per_server_auto = _dict(global_auto.get("perServer"))
    disabled_tools = {str(t) for t in perms.get("disabledTools") or [] if isinstance(t, str)}
    deny = perms.get("denyPatterns") or []
    allow = perms.get("allow") or []

    servers = []
    for name in sorted(set(file_servers) | set(perm_servers), key=str.lower):
        f, p = _dict(file_servers.get(name)), _dict(perm_servers.get(name))
        servers.append({
            "name": name,
            "builtin": f.get("builtin") if isinstance(f.get("builtin"), bool) else None,
            "enabled": p.get("enabled", f.get("enabled", True)) is not False,
            "auto_approve": bool(p.get("autoApprove") or per_server_auto.get(name) is True),
            "tools": [t for t in f.get("tools") or [] if isinstance(t, str)],
            "in_servers_file": name in file_servers,
        })
    by_server = {s["name"]: s for s in servers}

    found: dict[str, dict] = {}            # tool name -> {"server", "keys"}

    def add(tool: str, server: str | None, key: str | None) -> None:
        entry = found.setdefault(tool, {"server": server, "keys": []})
        if entry["server"] is None and server is not None:
            entry["server"] = server
        if key:
            entry["keys"].append(key)

    for key in perm_tools:
        if not isinstance(key, str):
            continue
        if key.startswith("tool:"):
            name = key[len("tool:"):]
            add(name, "workiq" if name.startswith("workiq_") else None, key)
        elif key.startswith("mcp:") and key.count(":") >= 2:
            _, server, tool = key.split(":", 2)
            if tool.startswith(f"{server}-"):
                tool = tool[len(server) + 1:]
            add(tool, server, key)
    for s in servers:
        for tool in s["tools"]:
            add(tool, s["name"], None)

    tools = []
    for name in sorted(found, key=str.lower):
        server = found[name]["server"]
        srv = by_server.get(server or "")
        flags = [perm_tools[k] for k in found[name]["keys"] if isinstance(perm_tools[k], bool)]
        keys = {name, *found[name]["keys"], f"tool:{name}"}
        if server:
            keys |= {f"mcp:{server}:{name}", f"mcp:{server}:{server}-{name}"}
        if keys & disabled_tools or (srv is not None and not srv["enabled"]):
            status, rule = DISABLED, "disabled"
        elif global_auto.get("global") is True:
            status, rule = AUTO, "autoApprove.global"
        elif flags:
            status, rule = (AUTO, "per-tool flag") if all(flags) else (ASKS, "per-tool flag")
        elif srv is not None and srv["auto_approve"]:
            status, rule = AUTO, "server autoApprove"
        elif perms.get("autoApproveReadOnly") is True and _reads_only(name):
            status, rule = AUTO, "autoApproveReadOnly"
        elif perms.get("autoApproveAllWrites") is True and _writes_local(name, server):
            status, rule = AUTO, "autoApproveAllWrites"
        else:
            status, rule = ASKS, "no rule approves it"
        tools.append({"name": name, "server": server, "status": status, "rule": rule})

    skills = _skills(home / "skills", "scout")
    if settings.get("loadCopilotCliSkills") is True:
        skills += _skills(copilot_home / "skills", "copilot-cli")
    gh_dir = Path(gh_config) if gh_config is not None else gh_config_dir()
    return {
        "runtime": "Microsoft Scout",
        "captured": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": sources + ["skills: directory names only"],
        "servers": servers,
        "tools": tools,
        "flags": {
            "auto_approve_global": global_auto.get("global") is True,
            "auto_approve_read_only": perms.get("autoApproveReadOnly") is True,
            "auto_approve_all_writes": perms.get("autoApproveAllWrites") is True,
            "allow_model_permissions_change": perms.get("allowModelPermissionsChange") is True,
            "load_copilot_cli_skills": settings.get("loadCopilotCliSkills") is True,
            "deny_patterns": len(deny) if isinstance(deny, list) else 0,
            "allow_rules": len(allow) if isinstance(allow, list) else 0,
        },
        "skills": skills,
        "programs": {p: which(p) is not None for p in PROGRAMS},
        "signed_in": {"gh": (gh_dir / "hosts.yml").is_file()},
    }


# ---------------------------------------------------------------------- the manifest

BASE = "scout-desktop"
NAME = "scout-desktop-observed"


def _base_manifest() -> dict:
    ref = resources.files("skillc").joinpath(f"data/runtimes/{BASE}.json")
    return json.loads(ref.read_text(encoding="utf-8"))


def _server(observed: dict, name: str) -> dict | None:
    return next((s for s in observed.get("servers") or [] if s["name"] == name), None)


def _live_tools(observed: dict, server: str | None = None, prefix: str = "") -> list[str]:
    return [t["name"] for t in observed.get("tools") or []
            if t["status"] != DISABLED and (server is None or t.get("server") == server)
            and t["name"].startswith(prefix)]


def workiq_groups(observed: dict) -> dict[str, list[str]]:
    """WorkIQ ability groups present (not disabled), each with the verbs of its tools."""
    out: dict[str, list[str]] = {}
    for name in _live_tools(observed, prefix="workiq_"):
        bare = name[len("workiq_"):]
        for group, words in WORKIQ_GROUPS:
            if any(w in bare for w in words):
                verb = bare.split("_", 1)[0]
                out.setdefault(group, [])
                if verb not in out[group]:
                    out[group].append(verb)
                break
    order = [g for g, _ in WORKIQ_GROUPS]
    return {g: sorted(out[g]) for g in order if g in out}


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _build(observed: dict) -> tuple[dict, dict]:
    m = _base_manifest()
    m["name"] = NAME
    prov: dict = {"base": f"built-in manifest `{BASE}`", "observed": [], "policy": []}
    tools = m["tools"]
    playwright = _server(observed, "playwright")
    if not (playwright and playwright["enabled"]):
        tools.pop("browser", None)
        prov["observed"].append("browser removed: no enabled playwright server")
    else:
        prov["observed"].append("browser kept: the playwright server is enabled")
    devops = _server(observed, "azure_devops")
    if not (devops and devops["enabled"]):
        tools.pop("azure_devops_mcp", None)
        prov["observed"].append("azure_devops_mcp removed: the server is absent or disabled")
    else:
        prov["observed"].append("azure_devops_mcp kept: the azure_devops server is enabled")
    workiq = _server(observed, "workiq")
    wq_tools = _live_tools(observed, prefix="workiq_")
    if not ((workiq and workiq["enabled"]) or wq_tools):
        tools.pop("m365", None)
        tools.pop("teams_message", None)
        m["grants"] = [g for g in m["grants"] if g != "microsoft_365_account"]
        prov["observed"].append("m365 and teams_message removed: no WorkIQ server or tools")
    else:
        groups = workiq_groups(observed)
        if groups and "m365" in tools:
            words = "; ".join(f"{g} ({', '.join(v)})" for g, v in groups.items())
            tools["m365"] += f". On this PC its WorkIQ tools cover: {words}"
        prov["observed"].append("m365 description extended with the WorkIQ ability groups "
                                "present: " + ", ".join(groups))
    shell = _server(observed, "shell")
    if shell is not None and not shell["enabled"]:
        tools.pop("bash", None)
        m["grants"] = [g for g in m["grants"] if g != "shell"]
        prov["observed"].append("bash removed: the shell server is disabled")

    gh = bool((observed.get("signed_in") or {}).get("gh")
              and (observed.get("programs") or {}).get("gh"))
    if gh:
        m["grants"].append("github_account")
        m["description"] = m["description"].replace(
            "No accounts or credentials for other external services.",
            "The GitHub CLI on this PC is signed in to a GitHub account. No accounts or "
            "credentials for other external services.")
        m["lacks"][0] = m["lacks"][0].replace(
            "other than the user's Microsoft 365 work account",
            "other than the user's Microsoft 365 work account and the GitHub account the "
            "GitHub CLI is signed in to")
        prov["observed"].append("github_account granted: the GitHub CLI is installed and its "
                                "hosts file exists (existence only)")
    else:
        prov["observed"].append("no GitHub account granted: the GitHub CLI is not installed "
                                "or not signed in")

    enabled = [s["name"] for s in observed.get("servers") or [] if s["enabled"]]
    # Every enabled server gets a grant of its own name, so the closing sentence below
    # (which names them) never refutes a requirement for a server that is there: the
    # requirement reader checks grants before lacks.
    for name in enabled:
        g = _norm(name)
        if g and g not in m["grants"]:
            m["grants"].append(g)
    if enabled:
        m["lacks"].append("MCP servers, connectors or integrations other than the tools listed "
                          "and the MCP servers configured in Scout: " + ", ".join(enabled))
    else:
        m["lacks"].append("MCP servers, connectors or integrations other than the tools listed")
    prov["observed"].append("lacks: no MCP server or connector beyond the configured ones ("
                            + (", ".join(enabled) or "none") + ")")
    prov["policy"] += [f"forbid_effects {m.get('forbid_effects', [])} (skillc built-in policy)",
                       "software, unavailable_programs and the other lacks entries come from "
                       f"`{BASE}` (skillc built-in description of Scout)"]
    return m, prov


def runtime_manifest(observed: dict) -> dict:
    """The `scout-desktop` manifest adjusted to what `probe` observed (see `provenance`)."""
    return _build(observed)[0]


def provenance(observed: dict) -> dict:
    """Which parts of `runtime_manifest(observed)` were observed and which are policy."""
    return _build(observed)[1]


def summary(observed: dict) -> dict:
    """Counts for a console line: tools by status, servers, notable flags."""
    counts: dict[str, int] = {}
    for t in observed.get("tools") or []:
        counts[t["status"]] = counts.get(t["status"], 0) + 1
    shell = _server(observed, "shell")
    return {"tools": counts, "servers": [s["name"] for s in observed.get("servers") or []
                                         if s["enabled"]],
            "shell_auto_approved": bool(shell and shell["enabled"] and shell["auto_approve"]),
            "writes_auto_approved": (observed.get("flags") or {}).get("auto_approve_all_writes",
                                                                       False)}

"""Register the skillc MCP server and the skillc-check skill with Microsoft Scout.

Scout reads MCP servers from `~/.scout/m-mcp-servers.json` and skills from
`~/.scout/skills/<name>/SKILL.md`. `install` updates only the `skillc` entry and the
`skillc-check` skill, keeping a timestamped backup of each file it replaces. Scout must
be restarted to start the new server process.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from importlib import resources
from pathlib import Path

from .mcp_approvals import ApprovalPolicy
from .monitor_mcp import MCP_TOOLS

SERVERS = "m-mcp-servers.json"
SKILL = Path("skills") / "skillc-check" / "SKILL.md"


def server_args(runtime: str, root: Path, *, strict: bool = False,
                host_plan: Path | None = None, policy_path: Path | None = None) -> list[str]:
    """The `skillc monitor mcp` arguments; validates the plan and policy before use."""
    if strict and not host_plan:
        raise ValueError("strict enforcement requires --host-plan")
    args = ["-m", "skillc.cli", "monitor", "mcp", "--runtime", runtime,
            "--root", str(Path(root).resolve())]
    if strict:
        args.append("--strict")
    if host_plan:
        Path(host_plan).read_text(encoding="utf-8")
        args += ["--host-plan", str(Path(host_plan).resolve())]
    if policy_path:
        ApprovalPolicy.load(policy_path)
        args += ["--approval-policy", str(Path(policy_path).resolve())]
    return args


def _backup(path: Path, stamp: str) -> Path | None:
    if not path.exists():
        return None
    copy = path.with_name(f"{path.name}.bak-skillc-{stamp}")
    shutil.copy2(path, copy)
    return copy


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def install(scout_home: Path | None = None, root: Path | None = None,
            runtime: str = "scout-desktop", python: str | None = None, *,
            strict: bool = False, host_plan: Path | None = None,
            policy_path: Path | None = None) -> list[str]:
    """Register skillc with Scout; returns what was changed."""
    home = Path(scout_home or Path.home() / ".scout")
    servers_path = home / SERVERS
    if not servers_path.is_file():
        raise FileNotFoundError(f"no Scout MCP configuration at {servers_path}")
    data = json.loads(servers_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("servers", {}), dict):
        raise ValueError(f"{servers_path} is not a Scout MCP configuration")
    args = server_args(runtime, Path(root or Path.home() / ".skillc-mcp"), strict=strict,
                       host_plan=host_plan, policy_path=policy_path)
    stamp = time.strftime("%Y%m%dT%H%M%S")
    out = []
    data.setdefault("servers", {})["skillc"] = {
        "builtin": False,
        "config": {"name": "skillc", "type": "command",
                   "command": python or sys.executable, "args": args},
        "tools": list(MCP_TOOLS)}
    backup = _backup(servers_path, stamp)
    _write(servers_path, json.dumps(data, indent=2) + "\n")
    out.append(f"updated {servers_path} (backup {backup})")
    skill = resources.files("skillc").joinpath("data/scout/SKILL.md").read_text("utf-8")
    skill_path = home / SKILL
    if not skill_path.exists() or skill_path.read_text(encoding="utf-8") != skill:
        backup = _backup(skill_path, stamp)
        _write(skill_path, skill)
        out.append(f"updated {skill_path}" + (f" (backup {backup})" if backup else ""))
    out.append("restart Microsoft Scout to start the updated skillc server")
    return out

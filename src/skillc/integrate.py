"""Install agent-scoped pre-session hooks into an existing workspace."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from .frontend.markdown import parse_frontmatter

POWERSHELL_HOOK = r'''$ErrorActionPreference = "Stop"

function Write-HookResult {
    param([bool]$Continue, [string]$Message = "", [int]$ExitCode = 0)
    $result = @{ continue = $Continue }
    if ($Message) {
        $result[$(if ($Continue) { "systemMessage" } else { "stopReason" })] = $Message
    }
    Write-Output ($result | ConvertTo-Json -Compress)
    exit $ExitCode
}

if (-not $env:SKILLC_AGENT_PATH) {
    Write-HookResult -Continue $true -Message "skillc preflight skipped: SKILLC_AGENT_PATH is not set."
}

$skillcArguments = @()
if ($env:SKILLC_PYTHON) {
    $skillcCommand = $env:SKILLC_PYTHON
    $skillcArguments = @('-m', 'skillc.cli')
}
else {
    $skillc = Get-Command skillc -ErrorAction SilentlyContinue
    $skillcCommand = $skillc.Source
}
if (-not $skillcCommand) {
    Write-HookResult -Continue $true -Message "skillc preflight skipped: install skillc and rerun 'skillc integrate'."
}

try {
    $hookResult = & $skillcCommand @skillcArguments hook agent-session --agent $env:SKILLC_AGENT_PATH
    $hookExitCode = $LASTEXITCODE
}
catch {
    Write-HookResult -Continue $true -Message "skillc preflight could not run: $($_.Exception.Message)"
}

if ($hookExitCode -eq 0 -or $hookExitCode -eq 2) {
    Write-Output $hookResult
    exit $hookExitCode
}
Write-HookResult -Continue $true -Message "skillc preflight could not run (exit $hookExitCode)."
'''

BASH_HOOK = r'''#!/usr/bin/env bash
set -u

hook_result() {
    escaped=${2//\\/\\\\}
    escaped=${escaped//\"/\\\"}
    if [ "$1" = "true" ]; then
        printf '{"continue":true,"systemMessage":"%s"}\n' "$escaped"
    else
        printf '{"continue":false,"stopReason":"%s"}\n' "$escaped"
    fi
}

if [ -z "${SKILLC_AGENT_PATH:-}" ]; then
    hook_result true "skillc preflight skipped: SKILLC_AGENT_PATH is not set."
    exit 0
fi
if [ -n "${SKILLC_PYTHON:-}" ]; then
    skillc_command=("$SKILLC_PYTHON" -m skillc.cli)
elif command -v skillc >/dev/null 2>&1; then
    skillc_command=(skillc)
else
    hook_result true "skillc preflight skipped: install skillc and rerun 'skillc integrate'."
    exit 0
fi

raw_result=$("${skillc_command[@]}" hook agent-session --agent "$SKILLC_AGENT_PATH")
status=$?
if [ "$status" -eq 0 ] || [ "$status" -eq 2 ]; then
    printf '%s\n' "$raw_result"
    exit "$status"
fi
hook_result true "skillc preflight could not run (exit $status)."
'''

HOOK_MARKER = ".github/hooks/scripts/skillc-pre-session"


@dataclass(frozen=True)
class IntegrationResult:
    workspace: Path
    agents: tuple[Path, ...]
    scripts: tuple[Path, Path]


def discover_agents(workspace: Path) -> list[Path]:
    root = workspace / ".github" / "agents"
    if not root.is_dir():
        return []
    return sorted(
        (path for path in root.glob("*.md") if path.is_file()),
        key=lambda path: path.name.lower(),
    )


def _display_name(path: Path) -> str:
    meta, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    return str(meta.get("name") or path.stem.removesuffix(".agent"))


def resolve_agents(workspace: Path, requested: Iterable[str]) -> list[Path]:
    available = discover_agents(workspace)
    by_key: dict[str, Path] = {}
    for path in available:
        relative = path.relative_to(workspace).as_posix()
        for key in (relative, path.name, path.stem, _display_name(path)):
            by_key[key.lower()] = path
    resolved = []
    for value in requested:
        candidate = Path(value)
        direct = candidate if candidate.is_absolute() else workspace / candidate
        path = direct.resolve() if direct.is_file() else by_key.get(value.lower())
        if path is None:
            raise ValueError(f"agent not found: {value}")
        if path not in resolved:
            resolved.append(path)
    return resolved


def choose_agents(
    agents: list[Path],
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> list[Path]:
    if not agents:
        raise ValueError("no agent markdown files found under .github/agents")
    output_fn("Select agents to protect with the skillc SessionStart preflight:")
    for index, path in enumerate(agents, 1):
        output_fn(f"  {index}. {_display_name(path)} ({path.name})")
    answer = input_fn("Enter numbers separated by commas, or 'all': ").strip()
    if answer.lower() == "all":
        return agents
    try:
        indices = [int(part.strip()) for part in answer.split(",") if part.strip()]
    except ValueError as error:
        raise ValueError("selection must contain numbers or 'all'") from error
    if not indices or any(index < 1 or index > len(agents) for index in indices):
        raise ValueError("selection contains an out-of-range agent number")
    return list(dict.fromkeys(agents[index - 1] for index in indices))


def _hook_yaml(relative_agent: str) -> str:
    return (
        "hooks:\n"
        "  SessionStart:\n"
        "    - type: command\n"
        f'      windows: "{HOOK_MARKER}.ps1"\n'
        f'      linux: "{HOOK_MARKER}.sh"\n'
        f'      osx: "{HOOK_MARKER}.sh"\n'
        "      timeout: 15\n"
        "      env:\n"
        f'        SKILLC_AGENT_PATH: "{relative_agent}"\n'
    )


def add_agent_hook(path: Path, workspace: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    relative = path.relative_to(workspace).as_posix()
    if HOOK_MARKER in text:
        return False
    match = re.match(
        r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n)?", text, re.S)
    if not match:
        raise ValueError(f"agent has no YAML frontmatter: {relative}")
    meta, _ = parse_frontmatter(text)
    if "hooks" in meta:
        raise ValueError(
            f"agent already defines hooks; merge manually: {relative}")
    frontmatter = match.group(1).rstrip() + "\n" + _hook_yaml(relative).rstrip()
    updated = f"---\n{frontmatter}\n---\n" + text[match.end():]
    path.write_text(updated, encoding="utf-8", newline="\n")
    return True


def install_integration(workspace: Path, agents: Iterable[Path]) -> IntegrationResult:
    workspace = workspace.resolve()
    selected = tuple(path.resolve() for path in agents)
    scripts_dir = workspace / ".github" / "hooks" / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    powershell = scripts_dir / "skillc-pre-session.ps1"
    bash = scripts_dir / "skillc-pre-session.sh"
    powershell.write_text(POWERSHELL_HOOK, encoding="utf-8", newline="\n")
    bash.write_text(BASH_HOOK, encoding="utf-8", newline="\n")
    for path in selected:
        add_agent_hook(path, workspace)
    return IntegrationResult(workspace, selected, (powershell, bash))
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


DEMO_ROOT = Path(__file__).resolve().parent
REPO_ROOT = DEMO_ROOT.parents[1]
EXAMPLES = REPO_ROOT / "examples"
DEFAULT_VSCODE_WORKSPACE = (
    Path(tempfile.gettempdir()) / "skillc-pre-session-vscode-demo")
WORKSPACE_MARKER = "skillc-pre-session-vscode-demo/1\n"


def _environment(workspace: Path) -> dict[str, str]:
    environment = os.environ.copy()
    source = str(REPO_ROOT / "src")
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        source if not existing else source + os.pathsep + existing)

    bin_dir = workspace / ".skillc-demo" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        shim = bin_dir / "skillc.cmd"
        shim.write_text(
            f'@"{sys.executable}" -m skillc.cli %*\n', encoding="utf-8")
    else:
        shim = bin_dir / "skillc"
        shim.write_text(
            "#!/bin/sh\n"
            f"exec {shlex.quote(sys.executable)} -m skillc.cli \"$@\"\n",
            encoding="utf-8")
        shim.chmod(shim.stat().st_mode | 0o111)
    environment["PATH"] = (
        str(bin_dir) + os.pathsep + environment.get("PATH", ""))
    return environment


def _run_cli(workspace: Path, *arguments: str,
             expected_status: int) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, "-m", "skillc.cli", *arguments]
    environment = _environment(workspace)
    print(f"\n$ python -m skillc.cli {' '.join(arguments)}")
    result = subprocess.run(
        command, cwd=workspace, env=environment, capture_output=True,
        text=True, check=False)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != expected_status:
        raise RuntimeError(
            f"command exited {result.returncode}, expected {expected_status}")
    return result


def _adapter_command(workspace: Path) -> list[str] | None:
    if os.name == "nt":
        shell = shutil.which("pwsh") or shutil.which("powershell")
        if shell is None:
            return None
        adapter = workspace / ".github" / "hooks" / "scripts" / (
            "skillc-pre-session.ps1")
        return [shell, "-NoProfile", "-File", str(adapter)]
    shell = shutil.which("bash")
    if shell is None:
        return None
    adapter = workspace / ".github" / "hooks" / "scripts" / (
        "skillc-pre-session.sh")
    return [shell, str(adapter)]


def _run_adapter(workspace: Path, agent: Path, *,
                 expected_continue: bool, expected_status: int,
                 expected_missing_capability: str | None = None) -> None:
    command = _adapter_command(workspace)
    if command is None:
        print("\nNo compatible PowerShell/Bash executable found; "
              "skipping generated adapter execution.")
        return

    environment = _environment(workspace)
    environment["SKILLC_PYTHON"] = sys.executable
    environment["SKILLC_AGENT_PATH"] = agent.relative_to(workspace).as_posix()
    print(f"\n$ {Path(command[0]).name} <generated pre-session adapter>")
    result = subprocess.run(
        command, cwd=workspace, env=environment, capture_output=True,
        text=True, check=False)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != expected_status:
        raise RuntimeError(
            f"adapter exited {result.returncode}, expected {expected_status}")
    response = json.loads(result.stdout)
    if response.get("continue") is not expected_continue:
        raise RuntimeError(f"unexpected adapter response: {response!r}")
    if (expected_missing_capability
            and expected_missing_capability not in response.get(
                "stopReason", "")):
        raise RuntimeError(f"block response omitted missing capability: {response!r}")


def _copy_example(workspace: Path, example_name: str,
                  remove_capability: str | None = None) -> Path:
    source = EXAMPLES / example_name / "SKILL.md"
    agent_dir = workspace / ".github" / "agents"
    agent_dir.mkdir(parents=True, exist_ok=True)
    agent = agent_dir / f"{example_name}.agent.md"
    text = source.read_text(encoding="utf-8")
    if remove_capability:
        marker = "```skillc-pack\n"
        start = text.index(marker) + len(marker)
        end = text.index("\n```", start)
        pack = json.loads(text[start:end])
        if remove_capability not in pack["capabilities"]:
            raise RuntimeError(
                f"{example_name} does not define {remove_capability!r}")
        del pack["capabilities"][remove_capability]
        text = text[:start] + json.dumps(pack, indent=2) + text[end:]
    agent.write_text(text, encoding="utf-8")
    return agent


def _run_scenario(example_name: str, *, expected_doctor_status: int,
                  expected_adapter_status: int, expected_continue: bool,
                  remove_capability: str | None = None) -> None:
    with tempfile.TemporaryDirectory(
            prefix=f"skillc-{example_name}-") as directory:
        workspace = Path(directory) / "workspace"
        workspace.mkdir()
        agent = _copy_example(workspace, example_name, remove_capability)

        _run_cli(workspace, "integrate", "--workspace", str(workspace), "--all",
                 expected_status=0)
        _run_cli(workspace, "doctor", "--workspace", str(workspace),
                 "--configured", expected_status=expected_doctor_status)
        _run_adapter(
            workspace, agent, expected_continue=expected_continue,
            expected_status=expected_adapter_status,
            expected_missing_capability=remove_capability)


def _write_interactive_workspace(workspace: Path) -> None:
    allowed = _copy_example(workspace, "retry-research")
    blocked = _copy_example(
        workspace, "triage-team", remove_capability="resolve_complex")
    _run_cli(workspace, "integrate", "--workspace", str(workspace), "--all",
             expected_status=0)

    _run_cli(
        workspace, "doctor", "--workspace", str(workspace), "--agent",
        allowed.relative_to(workspace).as_posix(), expected_status=0)
    _run_cli(
        workspace, "doctor", "--workspace", str(workspace), "--agent",
        blocked.relative_to(workspace).as_posix(), expected_status=1)

    if os.name == "nt":
        shell = shutil.which("pwsh") or shutil.which("powershell")
        if shell is None:
            raise RuntimeError("PowerShell is required for the Windows demo tasks")
        adapter = ".github/hooks/scripts/skillc-pre-session.ps1"
        shell_args = ["-NoProfile", "-File", "${workspaceFolder}/" + adapter]
    else:
        shell = shutil.which("bash")
        if shell is None:
            raise RuntimeError("Bash is required for the macOS/Linux demo tasks")
        adapter = ".github/hooks/scripts/skillc-pre-session.sh"
        shell_args = ["${workspaceFolder}/" + adapter]

    python_environment = {"PYTHONPATH": str(REPO_ROOT / "src")}
    demo_bin = str(workspace / ".skillc-demo" / "bin")
    task_environment = {
        **python_environment,
        "PATH": demo_bin + os.pathsep + os.environ.get("PATH", ""),
    }
    tasks = []
    for label, agent, command_args in (
        ("doctor: admitted", allowed, [
            "-m", "skillc.cli", "doctor", "--workspace", "${workspaceFolder}",
            "--agent", allowed.relative_to(workspace).as_posix(),
        ]),
        ("doctor: blocked (expected exit 1)", blocked, [
            "-m", "skillc.cli", "doctor", "--workspace", "${workspaceFolder}",
            "--agent", blocked.relative_to(workspace).as_posix(),
        ]),
    ):
        tasks.append({
            "label": f"SkillC demo: {label}",
            "type": "process",
            "command": sys.executable,
            "args": command_args,
            "options": {
                "cwd": "${workspaceFolder}",
                "env": task_environment,
            },
            "problemMatcher": [],
        })
    for label, agent in (
        ("host hook: admitted", allowed),
        ("host hook: blocked (expected exit 2)", blocked),
    ):
        tasks.append({
            "label": f"SkillC demo: {label}",
            "type": "process",
            "command": shell,
            "args": shell_args,
            "options": {
                "cwd": "${workspaceFolder}",
                "env": {
                    **task_environment,
                    "SKILLC_PYTHON": sys.executable,
                    "SKILLC_AGENT_PATH": agent.relative_to(workspace).as_posix(),
                },
            },
            "problemMatcher": [],
        })

    vscode = workspace / ".vscode"
    vscode.mkdir(exist_ok=True)
    settings = {
        "python.defaultInterpreterPath": sys.executable,
        "terminal.integrated.env.windows": {
            **python_environment,
            "PATH": demo_bin + ";" + "${env:PATH}",
        },
        "terminal.integrated.env.linux": {
            **python_environment,
            "PATH": demo_bin + ":" + "${env:PATH}",
        },
        "terminal.integrated.env.osx": {
            **python_environment,
            "PATH": demo_bin + ":" + "${env:PATH}",
        },
    }
    (vscode / "settings.json").write_text(
        json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    (vscode / "tasks.json").write_text(
        json.dumps({"version": "2.0.0", "tasks": tasks}, indent=2) + "\n",
        encoding="utf-8")

    python = (f'& "{sys.executable}"' if os.name == "nt"
              else shlex.quote(sys.executable))
    shell_name = "powershell" if os.name == "nt" else "sh"
    instructions = f"""# Interactive SkillC pre-session demo

This workspace uses two examples from the SkillC repository:

- `retry-research.agent.md` is expected to pass.
- `triage-team.agent.md` is expected to block because the temporary pack omits
  `resolve_complex` while the protocol still invokes it.

Both agents already have the generated `SessionStart` hook. The VS Code tasks
run the installed preflight and the actual platform adapter. Open **Terminal >
Run Task** and choose:

| Task | Expected result |
|---|---|
| `SkillC demo: doctor: admitted` | `doctor: PASS`, exit 0 |
| `SkillC demo: doctor: blocked (expected exit 1)` | Missing capability diagnostic, exit 1 |
| `SkillC demo: host hook: admitted` | `{{"continue":true}}`, exit 0 |
| `SkillC demo: host hook: blocked (expected exit 2)` | `{{"continue":false,...}}`, exit 2 |

You can also run the hook commands in the integrated terminal:

```{shell_name}
{python} -m skillc.cli doctor --workspace . --agent .github/agents/retry-research.agent.md
{python} -m skillc.cli hook agent-session --agent .github/agents/retry-research.agent.md
{python} -m skillc.cli hook agent-session --agent .github/agents/triage-team.agent.md
```

The final command is expected to exit 2 and report `resolve_complex` as
unavailable. To exercise the host wrapper rather than the CLI directly, use
the `SkillC demo: host hook` tasks.
"""
    (workspace / "README.md").write_text(instructions, encoding="utf-8")


def _prepare_interactive_workspace(path: Path) -> tuple[Path, bool]:
    workspace = path.expanduser().resolve()
    marker = workspace / ".skillc-demo" / "workspace.json"
    existed = workspace.exists()
    if existed:
        if not marker.is_file() or marker.read_text(encoding="utf-8") != WORKSPACE_MARKER:
            raise RuntimeError(
                f"refusing to reuse a non-demo directory: {workspace}; "
                "choose a new path with --reuse-workspace")
    else:
        workspace.mkdir(parents=True)
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(WORKSPACE_MARKER, encoding="utf-8")
    _write_interactive_workspace(workspace)
    return workspace, existed


def _open_vscode_demo(reuse_workspace: Path | None = None) -> int:
    code = shutil.which("code")
    if code is None:
        print("VS Code's `code` command was not found on PATH.", file=sys.stderr)
        print("Install/enable the VS Code command-line launcher, then rerun "
              "with --open-vscode.", file=sys.stderr)
        return 2

    workspace_path = reuse_workspace or DEFAULT_VSCODE_WORKSPACE
    try:
        workspace, existed = _prepare_interactive_workspace(workspace_path)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Could not prepare demo workspace: {error}", file=sys.stderr)
        return 2
    verb = "Reusing" if existed else "Prepared"
    print(f"\n{verb} interactive demo workspace: {workspace}")
    print("Opening it in a new VS Code window...")
    if os.name == "nt" and Path(code).suffix.lower() in (".cmd", ".bat"):
        subprocess.Popen(
            ["cmd.exe", "/d", "/c", code, "--new-window", str(workspace)])
    else:
        subprocess.Popen([code, "--new-window", str(workspace)])
    print("In VS Code, use Terminal > Run Task and choose a SkillC demo task.")
    print("The workspace is reused on later runs. Close VS Code and remove "
          "that folder when finished.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the SkillC pre-session demo")
    parser.add_argument(
        "--open-vscode", action="store_true",
        help="prepare an integrated demo workspace and open it in a new VS Code window")
    parser.add_argument(
        "--reuse-workspace", type=Path,
        help="use or refresh this marked demo workspace instead of the default stable temp path")
    args = parser.parse_args(argv)
    if args.open_vscode:
        return _open_vscode_demo(args.reuse_workspace)
    if args.reuse_workspace is not None:
        parser.error("--reuse-workspace requires --open-vscode")

    _run_scenario(
        "retry-research", expected_doctor_status=0, expected_adapter_status=0,
        expected_continue=True)
    _run_scenario(
        "triage-team", expected_doctor_status=1, expected_adapter_status=2,
        expected_continue=False, remove_capability="resolve_complex")
    print("\nPre-session hook demo passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Pre-session hook demo

This standalone demo exercises the agent integration using the skills in
[`examples/retry-research`](../../examples/retry-research) and
[`examples/triage-team`](../../examples/triage-team). It installs the generated
hook, runs `skillc doctor`, then executes the actual host adapter for an
admitted example and a blocked example. All work happens in temporary
workspaces; the source examples are never modified.

## Run the showcase

From the repository root, install the runtime dependencies if needed:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

On macOS/Linux:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

Then run the demo from the repository root:

```powershell
.\.venv\Scripts\python.exe demo\pre-session-hook\run_demo.py
```

Or on macOS/Linux:

```sh
python demo/pre-session-hook/run_demo.py
```

The runner points `PYTHONPATH` at this repository's `src`, so `skillc` does
not need to be installed as a separate command.

The runner performs these steps for each case:

1. Copies an example into a temporary repository under `.github/agents/`.
2. Runs `skillc integrate --all` to install the agent-scoped `SessionStart`
   hook and platform adapters.
3. Runs `skillc doctor --configured` to check the generated integration and
   preflight the agent.
4. Executes the generated PowerShell adapter on Windows or Bash adapter on
   macOS/Linux, then checks its host JSON response and exit code.

The admitted case uses `retry-research` unchanged and expects `doctor` and the
host adapter to succeed with `{"continue":true}`. The blocked case uses a
temporary copy of `triage-team` with its `resolve_complex` capability removed
while its protocol still invokes that tool. It expects `doctor` to report the
impossible agent and the host adapter to return `{"continue":false,...}` with
exit code 2. A nonzero `doctor` result in this negative case is expected. If
no compatible shell is available, the runner reports that adapter execution
was skipped. Temporary repositories are deleted at the end.

## Hands-on VS Code walkthrough

For an interactive version, make sure the VS Code `code` command is on `PATH`
and run this from the repository root:

```powershell
.\.venv\Scripts\python.exe demo\pre-session-hook\run_demo.py --open-vscode
```

On macOS/Linux:

```sh
python demo/pre-session-hook/run_demo.py --open-vscode
```

The runner reuses one stable temporary workspace by default
(`%TEMP%\skillc-pre-session-vscode-demo` on Windows). It copies both examples
into `.github/agents/`, installs their `SessionStart` hooks and shared
adapters, checks each example with `skillc doctor`, writes VS Code tasks, and
opens the workspace in a new VS Code window. Re-running the command refreshes
the demo's managed files in that same marked workspace instead of creating
another temporary directory. Other files you add there are left alone.

To reuse a different path, pass it explicitly:

```powershell
.\.venv\Scripts\python.exe demo\pre-session-hook\run_demo.py `
  --open-vscode --reuse-workspace "$env:TEMP\my-skillc-demo"
```

```sh
python demo/pre-session-hook/run_demo.py \
  --open-vscode --reuse-workspace "$HOME/.cache/my-skillc-demo"
```

An existing directory is reused only if it has this demo's marker; otherwise
the runner refuses to overwrite it. The runner prints the workspace path.
Close VS Code and remove the default or custom workspace when you no longer
need it.

In the new window, open **Terminal > Run Task** and try these tasks:

| Task | Expected result |
|---|---|
| `SkillC demo: doctor: admitted` | `doctor: PASS`, exit 0 |
| `SkillC demo: doctor: blocked (expected exit 1)` | `resolve_complex` diagnostic, exit 1 |
| `SkillC demo: host hook: admitted` | JSON `continue: true`, exit 0 |
| `SkillC demo: host hook: blocked (expected exit 2)` | JSON `continue: false`, exit 2 |

The generated workspace README also includes copy/paste commands for the
integrated terminal. To test the actual agent lifecycle, select
`retry-research` or `triage-team` in the agent host and start a session. This
last step requires a host/version that executes the generated `SessionStart`
command hooks. The tasks exercise the generated platform adapter even if the
host does not support that lifecycle hook.

This is a hook-based integration, **not a VS Code UI extension**. The
platform-specific adapters are PowerShell on Windows and Bash on macOS/Linux;
the underlying `skillc hook pre-session` JSON protocol can also be called by
other hosts that have their own pre-session lifecycle.

## Integrate another repository

The target repository must contain the existing custom agents you want to
protect under `.github/agents/*.md`. Use a checkout of this repository that
contains the integration scripts; run the setup script from that checkout and
point it at the target repository. Setup installs `skillc` and its runtime
dependencies, updates only the selected agents, writes the shared adapters,
and runs `skillc doctor --configured`.

On Windows, from PowerShell:

```powershell
$SkillcRepo = "C:\src\skill-achievability-compiler"
$TargetRepo = "C:\src\my-agent-repo"
pwsh -NoProfile -File "$SkillcRepo\scripts\setup.ps1" `
  -Workspace $TargetRepo `
  -Agent "my-agent.agent.md"
```

On macOS/Linux:

```sh
SKILLC_REPO="$HOME/src/skill-achievability-compiler"
TARGET_REPO="$HOME/src/my-agent-repo"
bash "$SKILLC_REPO/scripts/setup.sh" \
  --workspace "$TARGET_REPO" \
  --agent "my-agent.agent.md"
```

Use `-Agent`/`--agent` once per agent. Omit the agent option to select
interactively, or use `-All`/`--all` to configure every discovered agent.
Agent names, filenames, and workspace-relative paths are accepted.

After setup reports `doctor: PASS`, review the target repository changes:

- The selected agent's frontmatter now contains an agent-scoped `SessionStart`
  command hook.
- `.github/hooks/scripts/skillc-pre-session.ps1` and
  `.github/hooks/scripts/skillc-pre-session.sh` are the shared platform
  adapters.

Open the target repository in an agent host that supports these
`SessionStart` command hooks, select the configured agent, and start a
session. The hook runs before the session starts: an admissible agent returns
`continue: true`; an impossible required agent returns `continue: false` with
a `stopReason`. Use the showcase runner above for a repeatable allow/block
demonstration without changing a real repository.

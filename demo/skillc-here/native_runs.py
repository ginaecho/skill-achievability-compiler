"""Run installed native agents against an isolated, independently checked coding fixture."""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from native_gateway import Gateway, safe_source
from skillc.frontend.providers import require_model_opt_in


def executable(host: str) -> Path:
    if host == "copilot":
        return Path(os.environ["LOCALAPPDATA"]) / "GitHubCopilotCLI" / "copilot.exe"
    if host == "claude":
        return Path(os.environ["APPDATA"]) / "npm" / "claude.cmd"
    raise ValueError("unsupported native runtime")


def execution_events(stdout: str) -> list[dict]:
    events, names = [], {}
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            events.append({"tool": "native output", "status": "UNPARSED", "detail": line[:500]})
            continue
        if not isinstance(event, dict):
            events.append({"tool": "native output", "status": "UNPARSED", "detail": line[:500]})
            continue
        data = event.get("data") or {}
        if event.get("type") == "tool.execution_start":
            names[data["toolCallId"]] = data["toolName"]
        elif event.get("type") == "tool.execution_complete":
            events.append({"tool": names.get(data["toolCallId"], "unknown tool"),
                           "status": "SUCCEEDED" if data.get("success") else "FAILED"})
        message = event.get("message")
        for block in message.get("content", []) if isinstance(message, dict) else []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                names[block["id"]] = block["name"]
            elif block.get("type") == "tool_result":
                events.append({"tool": names.get(block["tool_use_id"], "unknown tool"),
                               "status": "FAILED" if block.get("is_error") else "SUCCEEDED"})
    return events


def execute(host: str, output: Path, skill: str, broken: str, tests: str,
            command_runner, model: str = "gpt-5.4", *, example="fix-failing-test",
            predictor=None) -> dict:
    require_model_opt_in()
    output = output.resolve()
    exe = executable(host)
    if not exe.is_file():
        return {"runtime": host, "attempted": False, "verified": False,
                "reason": "The native executable is not installed."}
    root = output / host
    workspace = root / "workspace"
    workspace.mkdir(parents=True)
    home = root / "home"
    temp = root / "temp"
    for path in (home, temp, home / "roaming", home / "local"):
        path.mkdir()
    source, test_file = workspace / "calculator.py", workspace / "test_calculator.py"
    coding = example == "fix-failing-test"
    runtime = output / "runtime"
    runtime.mkdir(exist_ok=True)

    def artifact(name, text):
        (runtime / f"{host}-{name}").write_text(text, encoding="utf-8")

    command = [sys.executable, "-B", "-m", "unittest", "-v", "test_calculator"]
    if coding:
        source.write_text(broken, encoding="utf-8")
        test_file.write_text(tests, encoding="utf-8")
        baseline = command_runner(command, workspace)
        baseline_log = baseline.stdout + baseline.stderr
        artifact("baseline.log", baseline_log)
        if baseline.returncode != 1 or "FAILED (failures=1)" not in baseline_log:
            raise RuntimeError("native fixture failed to establish its failing baseline")
        artifact("before.py", broken)
        artifact("test_calculator.py", tests)
    test_command = (f"& '{sys.executable}' -B -m unittest -v test_calculator"
                    if host == "copilot" else
                    f'"{sys.executable}" -B -m unittest -v test_calculator')
    prompt = (skill + "\n\nExecute this task in the current two-file Python workspace. "
              "Use your actual read, search, edit and shell tools. Do not change the tests. "
              "Only calculator.py may be edited; it must remain a pure two-argument arithmetic "
              "function with no imports, decorators or calls. Shell execution is restricted to "
              "the following exact test command; do not prepend cd or append other commands:\n"
              + test_command + "\nThe workspace already contains the failing test.")
    if not coding:
        prompt = (skill + "\n\nAttempt the task using only the tools actually supplied. "
                  "This is an isolated local run with no signed-in service accounts, no MCP "
                  "connectors and no permission to make reservations, send messages or contact "
                  "outside services. No date, venue or Slack destination was provided. "
                  "Do not invent inputs, actions, confirmations or successful completion. "
                  "Explain precisely which required actions could not actually be performed.")
    env = {k: v for k, v in os.environ.items()
           if k.upper() in ("SYSTEMROOT", "WINDIR", "PATH", "PATHEXT", "COMSPEC")}
    env.update(HOME=str(home), USERPROFILE=str(home), APPDATA=str(home / "roaming"),
               LOCALAPPDATA=str(home / "local"), TEMP=str(temp), TMP=str(temp),
               PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1",
               POWERSHELL_TELEMETRY_OPTOUT="1", GIT_CEILING_DIRECTORIES=str(root))
    result = {"runtime": "Copilot CLI" if host == "copilot" else "Claude Code",
              "attempted": True, "verified": False, "executable": str(exe), "model": model,
              "workspace": str(workspace), "reason": "", "exit_code": None,
              "scope": ("Native agent, isolated configuration and two-file workspace; "
                        "one baseline test failed, both tests are trusted and unchanged; "
                        "only validated arithmetic edits and the exact unittest command allowed."
                        if coding else
                        "Native agent, isolated empty workspace, read/search tools only, no "
                        "service credentials, user-supplied booking details or Slack destination. "
                        "External actions are not permitted and no receipts are simulated.")}

    def predict(tools):
        return predictor(host, tools, result["scope"]) if predictor else {}

    with Gateway(workspace, test_command, tests, model, predict) as gateway:
        if host == "copilot":
            env.update(COPILOT_HOME=str(home / "copilot"), COPILOT_OFFLINE="true",
                       COPILOT_PROVIDER_BASE_URL=gateway.endpoint,
                       COPILOT_PROVIDER_TYPE="openai", COPILOT_PROVIDER_WIRE_API="completions",
                       COPILOT_PROVIDER_TRANSPORT="http",
                       COPILOT_PROVIDER_API_KEY=gateway.token, COPILOT_MODEL=model,
                       COPILOT_PROVIDER_MAX_PROMPT_TOKENS="64000",
                       COPILOT_PROVIDER_MAX_OUTPUT_TOKENS="8192")
            tools = ["view", "rg", "apply_patch", "powershell"] if coding else ["view", "rg"]
            # The gateway checks the exact command before native dispatch, including on Windows.
            argv = [str(exe), "--no-auto-update", "--no-custom-instructions",
                    "--disable-client-telemetry", "--disable-builtin-mcps", "--sync-session=off",
                    "--no-ask-user", "--disallow-temp-dir", "--no-bash-env",
                    *["--available-tools=" + tool for tool in tools],
                    "--allow-tool=write", "--allow-tool=shell",
                    "--output-format=json", "--prompt=" + prompt.replace("\n", " ")]
        else:
            env.update(CLAUDE_CONFIG_DIR=str(home / "claude"),
                       ANTHROPIC_BASE_URL=gateway.endpoint.removesuffix("/v1"),
                       ANTHROPIC_AUTH_TOKEN=gateway.token,
                       CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1",
                       MAX_THINKING_TOKENS="0",
                       CLAUDE_CODE_GIT_BASH_PATH=r"C:\Program Files\Git\bin\bash.exe")
            argv = [str(exe), "--print", "--output-format", "stream-json", "--verbose",
                    "--no-session-persistence", "--no-chrome", "--safe-mode",
                    "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
                    "--permission-mode", "dontAsk", "--permission-prompts", "none",
                    "--tools", "Read,Grep,Edit,Write,Bash" if coding else "Read,Grep",
                    "--allowedTools", "Read,Grep,Edit,Write", f"Bash({test_command})",
                    "--model", model]
        version = subprocess.run([str(exe), "--version"], env=env, cwd=workspace,
                                 capture_output=True, text=True, timeout=20)
        if version.returncode != 0:
            raise RuntimeError("the native runtime did not report its version")
        result["version"] = version.stdout.strip()
        process = subprocess.Popen(
            argv, cwd=workspace, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        try:
            stdout, stderr = process.communicate(prompt if host == "claude" else "", timeout=240)
            result["exit_code"] = process.returncode
        except subprocess.TimeoutExpired as error:
            stop = (
                "$ErrorActionPreference='Stop'; function Stop-NativeTree([int]$Target) { "
                "Get-CimInstance Win32_Process -Filter \"ParentProcessId = $Target\" | "
                "ForEach-Object { Stop-NativeTree $_.ProcessId }; "
                "if (Get-Process -Id $Target -ErrorAction SilentlyContinue) "
                "{ Stop-Process -Id $Target } }; "
                f"Stop-NativeTree {process.pid}")
            stopped = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", stop],
                capture_output=True, text=True, timeout=30, env=env)
            if stopped.returncode:
                raise RuntimeError(f"Native process cleanup failed: {stopped.stderr}") from error
            stdout, stderr = process.communicate(timeout=10)
            result["reason"] = "The native agent exceeded the four-minute fixture deadline."
        artifact("transcript.jsonl", stdout)
        artifact("stderr.log", stderr)
        result["model_calls"] = gateway.calls
        result["predictions"] = gateway.predictions or {}
        result["events"] = execution_events(stdout)
    if not coding:
        result["reason"] = (
            "The native agent was launched, but no actual reservation or posted-message "
            "receipt exists. External task completion is NOT VERIFIED.")
        artifact("result.json", json.dumps(result, indent=2))
        return result
    actual_tests = test_file.read_text(encoding="utf-8")
    actual = source.read_text(encoding="utf-8")
    safe_source(actual)
    if actual_tests != tests:
        raise RuntimeError("the native agent modified the trusted tests")
    verification = command_runner(command, workspace)
    final_log = verification.stdout + verification.stderr
    artifact("verification.log", final_log)
    artifact("after.py", actual)
    artifact("patch.diff", "".join(difflib.unified_diff(
        broken.splitlines(keepends=True), actual.splitlines(keepends=True),
        fromfile="before.py", tofile="after.py")))
    successful = {e["tool"].lower() for e in result["events"] if e["status"] == "SUCCEEDED"}
    result["verified"] = (result["exit_code"] == 0 and bool(result["model_calls"])
                          and bool(successful & {"apply_patch", "edit", "write"})
                          and bool(successful & {"powershell", "bash"})
                          and verification.returncode == 0 and actual != broken
                          and "Ran 2 tests" in final_log and final_log.rstrip().endswith("OK"))
    if not result["reason"]:
        result["reason"] = ("The native agent changed the source; both trusted tests passed."
                            if result["verified"] else
                            "Native execution did not establish a verified fix; "
                            "inspect its transcript.")
    result["test_exit_code"] = verification.returncode
    artifact("result.json", json.dumps(result, indent=2))
    result["artifacts"] = [
        {"name": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
         "bytes": p.stat().st_size}
        for p in sorted(runtime.glob(f"{host}-*")) if p.is_file()]
    return result

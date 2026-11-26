import json
import subprocess
from pathlib import Path

import pytest

from skillc.frontend import providers
from skillc.frontend.urlguard import assert_clean


@pytest.fixture(autouse=True)
def installed_sdk(tmp_path, monkeypatch):
    local = tmp_path / "installed"
    package = local / "copilot" / "pkg" / "win32-x64" / "1.0.105"
    (package / "copilot-sdk").mkdir(parents=True)
    for path in (package / "index.js", package / ".extraction-complete",
                 package / "copilot-sdk" / "index.js"):
        path.write_text("")
    monkeypatch.setenv("LOCALAPPDATA", str(local))


def stub_native(monkeypatch, served="gpt-5.4", tool_calls=0, available_tools=0,
                reply="READY", finish="stop", byok=False):
    calls = []

    class Guard:
        def __init__(self, path):
            self.env, self.audit, self.model_requests = {}, [], 1

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            pass

    class Process:
        returncode = 0
        pid = 9876543

        def __init__(self, args, **kwargs):
            calls.append((args, kwargs))
            events = Path(args[args.index("--events-output-file") + 1])
            events.write_text("\n".join(json.dumps(row) for row in [
                {"type": "assistant.message", "data": {"content": reply}},
                {"type": "assistant.usage", "data": {
                    "model": served, "inputTokens": 100, "outputTokens": 2,
                    "isByok": byok,
                    "cacheReadTokens": 30, "cacheWriteTokens": 10,
                    "numToolCalls": tool_calls, "availableToolCount": available_tools,
                    "finishReason": finish,
                }},
                {"type": "model.model_call_success", "data": {
                    "responseChunk": {"model": served}}},
            ]), encoding="utf-8")

        def wait(self, timeout):
            return self.returncode

    monkeypatch.setattr(providers.shutil, "which", lambda _: "copilot")
    monkeypatch.setattr(providers.subprocess, "check_output", lambda *a, **k: "false\n")
    monkeypatch.setattr(providers.subprocess, "Popen", Process)
    monkeypatch.setattr(providers, "NativeEnvelopeGuard", Guard)
    monkeypatch.setenv("SKILLC_ALLOW_MODEL_CALLS", "1")
    return calls


def test_native_provider_scrubs_inputs_and_isolates_each_call(tmp_path, monkeypatch):
    calls = stub_native(monkeypatch)
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "not-for-child-processes")
    sessions = []
    for name in ("one", "two"):
        reply, receipt = providers.copilot_text_session(
            "Reply READY.", "Read https://example.org and mail user@example.org.",
            "gpt-5.4", 20, directory=tmp_path / name, token="stub-subscription-token")
        assert reply == "READY"
        assert receipt["status"] == "completed"
        assert receipt["node_compile_cache_disabled"] is True
        assert receipt["usage_native"][0]["inputTokens"] == 100
        assert receipt["usage_native"][0]["cacheReadTokens"] == 30
        sessions.append(receipt["session"])
    assert len(set(sessions)) == 2
    for args, kwargs in calls:
        assert_clean(Path(args[args.index("--prompt-file") + 1]).read_text(encoding="utf-8"))
        assert "stub-subscription-token" not in json.dumps(args)
        assert args[args.index("--available-tools") + 1] == ""
        assert "--sdk" in args
        env = kwargs["env"]
        assert env["NODE_DISABLE_COMPILE_CACHE"] == "1"
        assert "AZURE_OPENAI_API_KEY" not in env
        assert env["HOME"] == env["USERPROFILE"] == env["COPILOT_HOME"]


def test_native_provider_refuses_fallback_model_and_keeps_usage(tmp_path, monkeypatch):
    stub_native(monkeypatch, served="unexpected-model")
    output = tmp_path / "call"
    with pytest.raises(RuntimeError, match="serving model differs"):
        providers.copilot_text_session(
            "Reply READY.", "Input.", "gpt-5.4", 20, directory=output, token="stub")
    receipt = json.loads((output / "receipt.json").read_text())
    assert receipt["status"] == "unexpected_serving_model"
    assert receipt["usage_native"][0]["model"] == "unexpected-model"


def test_native_provider_requires_opt_in_before_creating_artifacts(tmp_path, monkeypatch):
    monkeypatch.delenv("SKILLC_ALLOW_MODEL_CALLS", raising=False)
    output = tmp_path / "call"
    with pytest.raises(providers.ModelCallsDisabled):
        providers.copilot_text_session(
            "Reply READY.", "Input.", "gpt-5.4", 20, directory=output, token="stub")
    assert not output.exists()


def test_native_text_provider_rejects_any_tool_attempt(tmp_path, monkeypatch):
    stub_native(monkeypatch, tool_calls=1)
    with pytest.raises(RuntimeError, match="used tools"):
        providers.copilot_text_session(
            "Reply READY.", "Input.", "gpt-5.4", 20,
            directory=tmp_path / "call", token="stub")
    receipt = json.loads((tmp_path / "call" / "receipt.json").read_text())
    assert receipt["status"] == "tool_calls_or_unreported_tool_usage"


def test_native_text_provider_rejects_advertised_default_tools(tmp_path, monkeypatch):
    stub_native(monkeypatch, available_tools=20)
    with pytest.raises(RuntimeError, match="exposed unexpected tools"):
        providers.copilot_text_session(
            "Reply READY.", "Input.", "gpt-5.4", 20,
            directory=tmp_path / "call", token="stub")


@pytest.mark.parametrize(("served", "tools", "byok", "status"), [
    ("gpt-5.4", 0, False, "timeout"),
    ("unexpected-model", 0, False, "unexpected_serving_model"),
    ("gpt-5.4", 2, False, "unexpected_partial_native_metadata"),
    ("gpt-5.4", 0, True, "unexpected_partial_native_metadata"),
])
def test_native_provider_stops_only_its_process_tree_on_timeout(
        tmp_path, monkeypatch, served, tools, byok, status):
    stub_native(monkeypatch, served=served, available_tools=tools, byok=byok)
    original = providers.subprocess.Popen
    stopped = []

    class TimedOutProcess(original):
        waited = False

        def __init__(self, args, **kwargs):
            super().__init__(args, **kwargs)
            events = Path(args[args.index("--events-output-file") + 1])
            with events.open("ab") as handle:
                handle.write(b'\n{"type":"assistant.us')

        def wait(self, timeout):
            if not self.waited:
                self.waited = True
                raise subprocess.TimeoutExpired("copilot", timeout)
            return 0

    monkeypatch.setattr(providers.subprocess, "Popen", TimedOutProcess)
    monkeypatch.setattr(providers.subprocess, "run",
                        lambda args, **kwargs: stopped.append(args))
    monkeypatch.setattr(providers.os, "killpg", lambda pid, signal: stopped.append(pid),
                        raising=False)
    output = tmp_path / "call"
    with pytest.raises(RuntimeError, match="serving model differs|deadline exceeded|unverified") as error:
        providers.copilot_text_session(
            "Reply READY.", "Input.", "gpt-5.4", 20, directory=output, token="stub")
    assert stopped
    assert "9876543" in str(stopped)
    receipt = json.loads((output / "receipt.json").read_text())
    if status == "timeout":
        assert type(error.value).__name__ == "CopilotSessionTimeout"
        assert error.value.receipt == receipt
    else:
        assert type(error.value) is RuntimeError
    assert receipt["status"] == status
    assert receipt["usage_native_complete"] is False
    assert receipt["native_events_truncated"] is True
    assert receipt["usage_native"][0]["inputTokens"] == 100
    assert receipt["served_models"] == [served]


@pytest.mark.parametrize(("reply", "finish"), [
    ("READY", "stop"), ("", "stop"), ("", "tool_calls"),
])
def test_native_mcp_session_allows_sandbox_calls_but_not_host_tools(
        tmp_path, monkeypatch, reply, finish):
    calls = stub_native(
        monkeypatch, tool_calls=2, available_tools=1, reply=reply, finish=finish)
    proof = tmp_path / "verified.json"
    proof.write_text(json.dumps({
        "status": "completed", "served_models": ["gpt-5.4"], "envelope_guard": {
            "implementation_sha256": providers.implementation_hash(), "model_requests": 1,
        }, "usage_native": [{"isByok": False}],
    }))
    def complete():
        return providers.copilot_mcp_session(
            "Use the sandbox.", "Task.", "gpt-5.4", 20,
            directory=tmp_path / "call", token="stub",
            server={"type": "local", "command": "trusted-server", "args": [], "tools": ["*"]},
            text_receipt=proof)
    if not reply and finish != "stop":
        with pytest.raises(RuntimeError, match="no text reply"):
            complete()
        return
    actual, receipt = complete()
    assert actual == reply
    args = calls[0][0]
    assert args[args.index("--available-tools") + 1] == "skillc_sandbox-execute_python"
    config = json.loads(args[args.index("--additional-mcp-config") + 1])
    mapping = Path(config["mcpServers"]["skillc_sandbox"]["env"]["SKILLC_REPLACEMENTS_FILE"])
    assert mapping.is_file()
    assert receipt["tools_denied"] is False


def test_native_text_provider_still_requires_nonempty_text(tmp_path, monkeypatch):
    stub_native(monkeypatch, reply="")
    with pytest.raises(RuntimeError, match="no text reply"):
        providers.copilot_text_session(
            "Reply READY.", "Input.", "gpt-5.4", 20,
            directory=tmp_path / "call", token="stub")


@pytest.mark.parametrize("byok", [True, None])
def test_tool_transport_rejects_non_subscription_text_proof_before_start(tmp_path, monkeypatch, byok):
    calls = stub_native(monkeypatch)
    proof = tmp_path / "verified.json"
    proof.write_text(json.dumps({
        "status": "completed", "served_models": ["gpt-5.4"],
        "envelope_guard": {
            "implementation_sha256": providers.implementation_hash(), "model_requests": 1,
        }, "usage_native": [{"isByok": byok}],
    }))
    with pytest.raises(ValueError, match="subscription text transport"):
        providers.copilot_mcp_session(
            "Use the sandbox.", "Task.", "gpt-5.4", 20,
            directory=tmp_path / "call", token="stub",
            server={"command": "trusted-server"}, text_receipt=proof)
    assert calls == []
    assert not (tmp_path / "call").exists()

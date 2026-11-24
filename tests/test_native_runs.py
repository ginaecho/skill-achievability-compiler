"""Native transport and tool boundaries; no real agent or model runs in tests."""
import importlib.util
import json
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "demo" / "skillc-here" / "native_gateway.py"
SPEC = importlib.util.spec_from_file_location("native_gateway", PATH)
gateway = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gateway)


def test_anthropic_native_tool_history_preserved():
    body = {"system": [{"type": "text", "text": "system"}], "messages": [
        {"role": "assistant", "content": [{"type": "tool_use", "id": "read-1",
                                           "name": "Read", "input": {"file_path": "calculator.py"}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "read-1",
                                      "content": "source"}]}],
        "tools": [{"name": "Read", "input_schema": {"type": "object"}}]}
    result = gateway.anthropic_request(body)
    assert result["messages"][1]["tool_calls"][0]["id"] == "read-1"
    assert result["messages"][2] == {"role": "tool", "tool_call_id": "read-1", "content": "source"}
    assert result["tools"][0]["function"]["name"] == "Read"


@pytest.mark.parametrize("source", [
    "import os\n", "def add(a,b):\n return open('outside')\n",
    "@print\ndef add(a,b):\n return a+b\n", "def add(a,b):\n return globals\n"])
def test_fixture_cannot_execute_model_authored_actions(source):
    with pytest.raises(ValueError):
        gateway.safe_source(source)


def test_native_edit_is_validated_without_applying_a_scripted_fix(tmp_path):
    source = tmp_path / "calculator.py"
    source.write_text("def add(left, right):\n    return left - right\n")
    original = source.read_text()

    def message(name, args):
        return {"tool_calls": [{"function": {"name": name, "arguments": json.dumps(args)}}]}

    valid = message("edit", {"path": str(source), "old_str": "left - right",
                              "new_str": "left + right"})
    gateway.validate_tools(valid, tmp_path, "trusted test command", "")
    assert source.read_text() == original
    with pytest.raises(ValueError, match="only calculator"):
        gateway.validate_tools(message("Write", {"file_path": str(tmp_path / "test_calculator.py"),
                                                  "content": ""}), tmp_path, "", "")
    with pytest.raises(ValueError, match="exact fixture"):
        gateway.validate_tools(message("powershell", {"command": "outside action"}), tmp_path, "", "")
    with pytest.raises(ValueError, match="inside"):
        gateway.validate_tools(message("Read", {"file_path": str(tmp_path.parent / "secret")}),
                               tmp_path, "", "")
    with pytest.raises(ValueError, match="inside"):
        gateway.validate_tools(message("rg", {"paths": [str(tmp_path.parent)]}),
                               tmp_path, "", "")
    patch = ("*** Begin Patch\n*** Update File: calculator.py\n@@\n"
             "-    return left - right\n+    return left + right\n*** End Patch")
    gateway.validate_tools(message("apply_patch", {"input": patch}), tmp_path, "", "")
    gateway.validate_tools({"tool_calls": [{"type": "custom", "custom": {
        "name": "apply_patch", "input": patch}}]}, tmp_path, "", "")
    assert source.read_text() == original


@pytest.mark.parametrize("anthropic,stream", [(False, False), (False, True), (True, True)])
def test_native_transport_predicts_before_inference_and_requires_credential(
        tmp_path, monkeypatch, anthropic, stream):
    import urllib.error
    import urllib.request

    order = []

    def model(*_):
        order.append("inference")
        return {"id": "test", "model": "test", "choices": [{"message": {
            "role": "assistant", "content": "test-only response"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 3}}

    monkeypatch.setattr(gateway.providers, "azure_openai_chat", model)

    def predict(tools):
        order.append("predictions")
        assert tools == []
        return {"unit_test_stub": True}

    with gateway.Gateway(tmp_path, "", "", "test-model", predict) as proxy:
        body = {"messages": [{"role": "user", "content": "test"}], "stream": stream}
        endpoint = proxy.endpoint + ("/messages" if anthropic else "/chat/completions")

        def request(token):
            return urllib.request.urlopen(urllib.request.Request(
                endpoint, data=json.dumps(body).encode(),
                headers={"Authorization": "Bearer " + token}), timeout=5)

        with pytest.raises(urllib.error.HTTPError) as error:
            request("wrong")
        assert error.value.code == 403
        assert not order
        with request(proxy.token) as response:
            data = response.read().decode()
        assert order == ["predictions", "inference"]
        assert "test-only response" in data
        assert not stream or ("message_stop" if anthropic else "[DONE]") in data


def test_native_runner_verifies_agent_outputs_and_never_repairs_them(tmp_path, monkeypatch):
    import importlib
    import subprocess

    monkeypatch.syspath_prepend(str(PATH.parent))
    native = importlib.import_module("native_runs")
    exe = tmp_path / "test-only-native.exe"
    exe.write_text("Test sentinel; never executed.")
    monkeypatch.setattr(native, "executable", lambda _: exe)
    real_run, real_popen = subprocess.run, subprocess.Popen
    state = {"fix": False}
    broken = "def add(a,b):\n return a-b\n"
    tests = ("import unittest\nfrom calculator import add\nclass T(unittest.TestCase):\n"
             " def test_add(self): self.assertEqual(add(2,3),5)\n"
             " def test_zero(self): self.assertEqual(add(0,0),0)\n")
    events = "\n".join(json.dumps(e) for e in [
        {"type": "tool.execution_start", "data": {"toolCallId": "edit", "toolName": "apply_patch"}},
        {"type": "tool.execution_complete", "data": {"toolCallId": "edit", "success": True}},
        {"type": "tool.execution_start", "data": {"toolCallId": "run", "toolName": "powershell"}},
        {"type": "tool.execution_complete", "data": {"toolCallId": "run", "success": True}},
    ])

    class Proxy:
        endpoint, token = "http://127.0.0.1:1/v1", "test-token"
        predictions = {}
        calls = [{"unit_test_stub": True}]

        def __init__(self, *_):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    class Agent:
        returncode = 0
        pid = 12345678

        def __init__(self, cwd):
            self.cwd = cwd

        def communicate(self, *_a, **_kw):
            if state.get("timeout") and not state.get("stopped"):
                raise subprocess.TimeoutExpired("test-only native process", 240)
            if state["fix"]:
                (self.cwd / "calculator.py").write_text(broken.replace("a-b", "a+b"))
            return events, ""

    def run(argv, **kwargs):
        if argv[0] == "powershell.exe":
            assert "Stop-NativeTree 12345678" in argv[-1]
            state["stopped"] = True
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[0] == str(exe):
            return subprocess.CompletedProcess(argv, 0, "test-only version", "")
        return real_run(argv, **kwargs)

    def popen(argv, **kwargs):
        return Agent(kwargs["cwd"]) if argv[0] == str(exe) else real_popen(argv, **kwargs)

    monkeypatch.setattr(native, "Gateway", Proxy)
    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(subprocess, "Popen", popen)

    def command(argv, cwd):
        return subprocess.run(argv, cwd=cwd, capture_output=True, text=True)

    unfixed = native.execute("copilot", tmp_path / "unfixed", "test", broken, tests, command)
    assert not unfixed["verified"]
    assert (Path(unfixed["workspace"]) / "calculator.py").read_text() == broken
    state["fix"] = True
    fixed = native.execute("copilot", tmp_path / "fixed", "test", broken, tests, command)
    assert fixed["verified"]
    assert fixed["test_exit_code"] == 0
    state.update(fix=False, timeout=True)
    timed_out = native.execute("copilot", tmp_path / "timeout", "test", broken, tests, command)
    assert state["stopped"] and not timed_out["verified"]
    assert "deadline" in timed_out["reason"]

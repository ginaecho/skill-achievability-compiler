"""Opt-in native client test against a loopback stub, never a real model."""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from skillc.frontend import providers
from skillc.frontend.urlguard import assert_clean


@pytest.mark.skipif(os.environ.get("SKILLC_NATIVE_CLIENT_STUB") != "1",
                    reason="explicit native client stub preflight only")
@pytest.mark.parametrize("model", ["gpt-5.3-codex", "gpt-5.6-sol"])
@pytest.mark.parametrize(("mcp", "terminal_text"), [
    (False, "READY"), (True, "READY"), (True, ""),
])
def test_native_request_envelope_is_url_free(tmp_path, monkeypatch, model, mcp, terminal_text):
    executable = Path(os.environ["LOCALAPPDATA"]) / "GitHubCopilotCLI" / "copilot.exe"
    if not executable.is_file():
        pytest.skip("native Windows Copilot CLI is not installed")
    captured = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            captured.append(payload)
            tool_call = mcp and len(captured) == 1
            message = {"role": "assistant", "content": terminal_text}
            finish = "stop"
            if tool_call:
                message = {"role": "assistant", "tool_calls": [{
                    "id": "sandbox-call", "type": "function",
                    "function": {"name": "skillc_sandbox-execute_python",
                                 "arguments": json.dumps({
                                     "code": "print('https://new.example.org'); node.func.id"})},
                }]}
                finish = "tool_calls"
            reply = {
                "id": "stub", "object": "chat.completion", "created": 1,
                "model": model, "choices": [{
                    "index": 0, "message": message,
                    "finish_reason": finish,
                }],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
            if payload.get("stream"):
                delta = dict(message)
                if tool_call:
                    delta["tool_calls"] = [{"index": 0, **message["tool_calls"][0]}]
                chunk = {
                    "id": "stub", "object": "chat.completion.chunk", "created": 1,
                    "model": model, "choices": [{
                        "index": 0, "delta": delta,
                        "finish_reason": None,
                    }],
                }
                end = {**chunk, "choices": [{
                    "index": 0, "delta": {}, "finish_reason": finish,
                }], "usage": reply["usage"]}
                raw = (f"data: {json.dumps(chunk)}\n\n"
                       f"data: {json.dumps(end)}\n\ndata: [DONE]\n\n").encode()
                content_type = "text/event-stream"
            else:
                raw = json.dumps(reply).encode()
                content_type = "application/json"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    original = providers.subprocess.Popen

    def stub_route(args, **kwargs):
        if "--prompt-file" in args:
            kwargs["env"].update(
                COPILOT_OFFLINE="true",
                COPILOT_PROVIDER_BASE_URL=f"http://127.0.0.1:{server.server_port}/v1",
                COPILOT_PROVIDER_TYPE="openai", COPILOT_PROVIDER_WIRE_API="completions",
                COPILOT_PROVIDER_TRANSPORT="http",
                COPILOT_PROVIDER_API_KEY="stub-only", COPILOT_MODEL=model)
        return original(args, **kwargs)

    monkeypatch.setenv("SKILLC_ALLOW_MODEL_CALLS", "1")
    monkeypatch.setattr(providers.subprocess, "Popen", stub_route)
    try:
        options = {}
        if mcp:
            proof = tmp_path / "verified.json"
            proof.write_text(json.dumps({
                "status": "completed", "served_models": [model], "envelope_guard": {
                    "implementation_sha256": providers.implementation_hash(), "model_requests": 1,
                }, "usage_native": [{"isByok": False}],
            }))
            options["text_receipt"] = proof
            config = tmp_path / "server.json"
            config.write_text(json.dumps({
                "docker_host": "unused", "container": "a" * 64,
                "events": str(tmp_path / "tools.jsonl"),
                "deadline": 0, "max_calls": 0,
            }), encoding="utf-8")
            options["server"] = {
                "type": "local", "command": sys.executable,
                "args": [str(Path(__file__).resolve().parents[1] /
                             "scripts" / "real_skills_runtime.py"), str(config)],
                "tools": ["*"],
            }
        complete = providers.copilot_mcp_session if mcp else providers.copilot_text_session
        reply, receipt = complete(
            "Reply READY.", "Client envelope preflight.", model, 45,
            directory=tmp_path / "call", token="stub-only", **options)
        assert reply == terminal_text
        assert receipt["node_compile_cache_disabled"] is True
        assert not list((tmp_path / "call").rglob("node-compile-cache"))
        assert receipt["envelope_guard"]["model_requests"] == (2 if mcp else 1)
        assert receipt["usage_native"][0]["numToolCalls"] == (1 if mcp else 0)
        assert captured, "The client did not contact the loopback stub"
        for request in captured:
            assert_clean(json.dumps(request))
            assert "ask-matt" not in json.dumps(request)
            names = [tool.get("function", {}).get("name", tool.get("name"))
                     for tool in request.get("tools", [])]
            assert names == ["skillc_sandbox-execute_python"] if mcp else names == []
        if mcp:
            events = [json.loads(line) for line in
                      (tmp_path / "tools.jsonl").read_text().splitlines()]
            assert events[0]["credential_environment_present"] is False
            assert events[1]["type"] == "tool_result"
            assert len(captured) == 2
            assert captured[1]["messages"][-1]["role"] == "tool"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

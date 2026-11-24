"""Loopback transport for native agents; model requests use SkillC's guarded provider."""
from __future__ import annotations

import ast
import hmac
import json
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from skillc.frontend import providers


def safe_source(text: str) -> None:
    allowed = (ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return, ast.BinOp,
               ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Constant, ast.Name, ast.Load,
               ast.UnaryOp, ast.USub)
    tree = ast.parse(text)
    if len(text) > 4000 or any(not isinstance(n, allowed) for n in ast.walk(tree)):
        raise ValueError("the coding fixture permits only a pure arithmetic function")
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise ValueError("the fixture must contain just the add function")
    fn = tree.body[0]
    if (fn.name != "add" or fn.decorator_list or fn.args.defaults or fn.args.kw_defaults
            or fn.args.vararg or fn.args.kwarg or fn.args.kwonlyargs or fn.args.posonlyargs
            or len(fn.args.args) != 2):
        raise ValueError("the fixture requires an undecorated two-argument add function")
    names = {a.arg for a in fn.args.args}
    if any(isinstance(n, ast.Name) and n.id not in names for n in ast.walk(tree)):
        raise ValueError("the arithmetic function cannot reference other objects")
    if any(isinstance(n, ast.Constant)
           and (not isinstance(n.value, (int, float)) or abs(n.value) > 1_000_000)
           for n in ast.walk(tree)):
        raise ValueError("only small numeric constants are permitted")


def validate_tools(message: dict, workspace: Path, test_command: str, tests: str) -> None:
    for call in message.get("tool_calls", []):
        if call.get("type") == "custom":
            fn = call["custom"]["name"]
            args = {"input": call["custom"]["input"]}
        else:
            fn = call["function"]["name"].rsplit(".", 1)[-1].lower()
            args = json.loads(call["function"]["arguments"])
        if fn in ("powershell", "bash"):
            if args.get("command", "").strip() != test_command:
                raise ValueError("only the exact fixture test command is permitted")
            if (args.get("run_in_background") or args.get("dangerouslyDisableSandbox")
                    or args.get("detach") or args.get("mode", "sync") != "sync"):
                raise ValueError("background commands and sandbox bypass are forbidden")
            for key in ("cwd", "workdir", "working_directory"):
                if key in args and Path(args[key]).resolve() != workspace:
                    raise ValueError("the test command must run in its fixture workspace")
            safe_source((workspace / "calculator.py").read_text(encoding="utf-8"))
            if (workspace / "test_calculator.py").read_text(encoding="utf-8") != tests:
                raise ValueError("the verification tests must not be modified")
            continue
        if fn == "apply_patch":
            patch = args.get("input", args.get("patch", ""))
            lines = patch.splitlines()
            if (len(lines) < 5 or lines[0] != "*** Begin Patch"
                    or not lines[1].startswith("*** Update File: ")
                    or not lines[2].startswith("@@") or lines[-1] != "*** End Patch"
                    or any(not line or line[0] not in " +-" for line in lines[3:-1])):
                raise ValueError("only a single update hunk is permitted")
            args = {"path": lines[1].removeprefix("*** Update File: "),
                    "old_str": "".join(line[1:] + "\n"
                                       for line in lines[3:-1] if line[0] != "+"),
                    "new_str": "".join(line[1:] + "\n"
                                       for line in lines[3:-1] if line[0] != "-")}
            fn = "edit"
        if fn not in ("view", "read", "grep", "rg", "edit", "write"):
            raise ValueError(f"native tool outside the coding allowlist: {fn}")
        names = []
        for key in ("path", "file_path", "paths"):
            if key in args:
                value = args[key]
                names.extend([value] if isinstance(value, str) else value)
        if not names:
            names = [str(workspace)]
        for name in names:
            path = Path(name)
            path = (workspace / path).resolve() if not path.is_absolute() else path.resolve()
            if path not in (workspace, workspace / "calculator.py",
                            workspace / "test_calculator.py"):
                raise ValueError("native file access must stay inside the two-file fixture")
        if fn in ("edit", "write"):
            if len(names) != 1 or path != workspace / "calculator.py":
                raise ValueError("only calculator.py may be modified")
            if fn == "write":
                candidate = args["content"]
            else:
                old = args.get("old_str", args.get("old_string"))
                new = args.get("new_str", args.get("new_string"))
                if not isinstance(old, str) or not old or not isinstance(new, str):
                    raise ValueError("unsupported native edit format")
                current = path.read_text(encoding="utf-8")
                if old not in current:
                    raise ValueError("native edit does not match the current file")
                candidate = current.replace(old, new, -1 if args.get("replace_all") else 1)
            safe_source(candidate)


def anthropic_request(body: dict) -> dict:
    system = body.get("system", "")
    if isinstance(system, list):
        system = "\n".join(b["text"] for b in system)
    messages = [{"role": "system", "content": system}]
    for original in body["messages"]:
        content = original["content"]
        if isinstance(content, str):
            messages.append({"role": original["role"], "content": content})
            continue
        texts, calls = [], []
        for block in content:
            if block["type"] == "text":
                texts.append(block["text"])
            elif block["type"] == "tool_use":
                calls.append({"id": block["id"], "type": "function", "function": {
                    "name": block["name"], "arguments": json.dumps(block["input"])}})
            elif block["type"] == "tool_result":
                result = block.get("content", "")
                if not isinstance(result, str):
                    if any(b["type"] != "text" for b in result):
                        raise ValueError("only text tool results are supported")
                    result = "\n".join(b["text"] for b in result)
                messages.append({"role": "tool", "tool_call_id": block["tool_use_id"],
                                 "content": result})
            else:
                raise ValueError(f"unsupported native message block: {block['type']}")
        if texts or calls:
            message = {"role": original["role"], "content": "\n".join(texts) or None}
            if calls:
                message["tool_calls"] = calls
            messages.append(message)
    return {"messages": messages, "max_completion_tokens": min(body.get("max_tokens", 8192), 8192),
            "tools": [{"type": "function", "function": {
                "name": t["name"], "description": t.get("description", ""),
                "parameters": t["input_schema"]}} for t in body.get("tools", [])]}


class Gateway:
    def __init__(self, workspace: Path, test_command: str, tests: str, model: str,
                 before_run=None):
        self.workspace = workspace.resolve()
        self.test_command, self.tests, self.model = test_command, tests, model
        self.token = secrets.token_urlsafe(32)
        self.calls: list[dict] = []
        self.lock = threading.Lock()
        self.prediction_lock = threading.Lock()
        self.predictions = None
        gateway = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                credential = self.headers.get("Authorization", "").removeprefix("Bearer ")
                credential = self.headers.get("x-api-key", credential)
                if not hmac.compare_digest(credential, gateway.token):
                    return self.reply(403, {"error": {"message": "invalid gateway credential"}})
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 2_000_000:
                        raise ValueError("native request size is outside the fixture limit")
                    body = json.loads(self.rfile.read(length))
                    anthropic = self.path.partition("?")[0].endswith("/messages")
                    if not anthropic and not self.path.endswith("/chat/completions"):
                        raise ValueError("unsupported native provider endpoint")
                    with gateway.lock:
                        if len(gateway.calls) >= 16:
                            raise ValueError("native fixture model-call budget exhausted")
                        record = {"request": len(gateway.calls) + 1,
                                  "tools": [t.get("name", t.get("function",
                                                    t.get("custom", {})).get("name"))
                                            for t in body.get("tools", [])]}
                        gateway.calls.append(record)
                    with gateway.prediction_lock:
                        if gateway.predictions is None and before_run is not None:
                            gateway.predictions = before_run(record["tools"])
                    record["inference_started_at"] = time.time()
                    payload = anthropic_request(body) if anthropic else {**body}
                    payload.pop("stream", None)
                    payload.pop("stream_options", None)
                    if "max_tokens" in payload:
                        payload["max_completion_tokens"] = payload.pop("max_tokens")
                    payload["max_completion_tokens"] = min(
                        payload.get("max_completion_tokens", 8192), 8192)
                    with providers.metered() as usage:
                        response = providers.azure_openai_chat(payload, gateway.model, 120)
                    record["usage"] = usage
                    message = response["choices"][0]["message"]
                    record["tool_calls"] = message.get("tool_calls", [])
                    record["content"] = message.get("content")
                    validate_tools(message, gateway.workspace, gateway.test_command, gateway.tests)
                    if anthropic:
                        return self.anthropic_reply(response, bool(body.get("stream")))
                    if not body.get("stream"):
                        return self.reply(200, response)
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    delta = {**message}
                    if "tool_calls" in delta:
                        delta["tool_calls"] = [{"index": i, **t}
                                               for i, t in enumerate(delta["tool_calls"])]
                    base = {"id": response["id"], "object": "chat.completion.chunk",
                            "created": response.get("created", int(time.time())),
                            "model": response["model"]}
                    for part in (
                        {**base, "choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
                        {**base, "choices": [{"index": 0, "delta": {},
                                             "finish_reason":
                                             response["choices"][0]["finish_reason"]}],
                         "usage": response.get("usage")},
                    ):
                        self.wfile.write(("data: " + json.dumps(part) + "\n\n").encode())
                    self.wfile.write(b"data: [DONE]\n\n")
                    self.wfile.flush()
                except (OSError, RuntimeError, ValueError, KeyError, TypeError) as error:
                    if "record" in locals():
                        record["error"] = f"{type(error).__name__}: {error}"
                    self.reply(400, {"error": {"type": "invalid_request_error",
                                             "message": f"{type(error).__name__}: {error}"}})

            def reply(self, status, value):
                data = json.dumps(value).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def anthropic_reply(self, response, stream):
                message = response["choices"][0]["message"]
                blocks = ([{"type": "text", "text": message["content"]}]
                          if message.get("content") else [])
                blocks += [{"type": "tool_use", "id": t["id"], "name": t["function"]["name"],
                            "input": json.loads(t["function"]["arguments"])}
                           for t in message.get("tool_calls", [])]
                tokens = response.get("usage") or {}
                usage = {"input_tokens": tokens.get("prompt_tokens", 0),
                         "output_tokens": tokens.get("completion_tokens", 0)}
                result = {"id": response["id"], "type": "message", "role": "assistant",
                          "model": gateway.model, "content": blocks, "usage": usage,
                          "stop_reason": "tool_use" if message.get("tool_calls") else "end_turn",
                          "stop_sequence": None}
                if not stream:
                    return self.reply(200, result)
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()

                def event(kind, value):
                    self.wfile.write((f"event: {kind}\ndata: "
                                      + json.dumps({"type": kind, **value}) + "\n\n").encode())

                event("message_start", {"message": {**result, "content": [], "stop_reason": None,
                                                     "usage": {**usage, "output_tokens": 0}}})
                for i, block in enumerate(blocks):
                    empty = {**block, **({"text": ""} if block["type"] == "text"
                                        else {"input": {}})}
                    event("content_block_start", {"index": i, "content_block": empty})
                    delta = ({"type": "text_delta", "text": block["text"]}
                             if block["type"] == "text" else
                             {"type": "input_json_delta",
                              "partial_json": json.dumps(block["input"])})
                    event("content_block_delta", {"index": i, "delta": delta})
                    event("content_block_stop", {"index": i})
                event("message_delta", {"delta": {"stop_reason": result["stop_reason"],
                                                   "stop_sequence": None}, "usage": usage})
                event("message_stop", {})
                self.wfile.flush()
                return None

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    @property
    def endpoint(self):
        return f"http://127.0.0.1:{self.server.server_port}/v1"

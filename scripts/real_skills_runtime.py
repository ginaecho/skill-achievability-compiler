"""One bounded Docker workspace and a guarded, single-tool MCP server."""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The MCP child needs only this stdlib module, not checker dependencies in the parent user site.
sys.path.insert(0, str(ROOT / "src" / "skillc" / "frontend"))
from urlguard import guarded_body, restore, scrub_json  # noqa: E402

IMAGE = "python@sha256:4840d514c583a4d3d8cad3940e68dee6f0f6f3635c12fcd0a3d74c21a5b93a54"
OUTPUT_LIMIT = 65536
TASK_FILENAME = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*")
TOOL = {
    "name": "execute_python",
    "description": "Execute Python in the isolated task container. Returns real output and exit status.",
    "inputSchema": {
        "type": "object", "properties": {"code": {"type": "string"}},
        "required": ["code"], "additionalProperties": False,
    },
}


def append_event(path: Path, event: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"timestamp": time.time(), **event}) + "\n")


class DeliverableUnavailable(RuntimeError):
    """The required in-container file is absent, not a file, or unreadable."""


class Sandbox:
    def __init__(self, host: str, container: str = "", *, image: str = IMAGE,
                 site_packages: bool = False):
        if container and not re.fullmatch(r"[0-9a-f]{64}", container):
            raise ValueError("An exact owned Docker container ID is required")
        if image != IMAGE and (not isinstance(image, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", image)):
            raise ValueError("An exact immutable image digest is required")
        if type(site_packages) is not bool:
            raise ValueError("The site-packages policy must be boolean")
        self.host = host
        self.container = container
        self.image = image
        self.python_flags = ("-I", "-B") if site_packages else ("-I", "-S", "-B")
        self.stopped = False

    def docker(self, *args: str) -> list[str]:
        return ["docker", "--host", self.host, *args]

    def start(self, inputs: dict[str, bytes], writable: list[str]) -> None:
        if self.container:
            raise ValueError("Sandbox already started")
        if set(writable) - inputs.keys() or any(
                not TASK_FILENAME.fullmatch(name) for name in inputs):
            raise ValueError("Only simple named task inputs are supported")
        raw = subprocess.check_output(self.docker(
            "run", "--pull=never", "--detach", "--rm", "--network", "none", "--read-only",
            "--user", "65534:65534", "--cpus", "0.5", "--memory", "128m",
            "--memory-swap", "128m", "--pids-limit", "32", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--tmpfs", "/work:rw,noexec,nosuid,nodev,size=16777216,mode=1777",
            "--tmpfs", "/inputs:rw,noexec,nosuid,nodev,size=16777216,mode=0755",
            "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=16777216,mode=1777",
            self.image, "python", *self.python_flags, "-c",
            "import time; time.sleep(900)"), timeout=30, text=True).strip()
        if not re.fullmatch(r"[0-9a-f]{64}", raw):
            raise RuntimeError("Docker did not return an exact container ID")
        self.container = raw
        payload = {name: base64.b64encode(value).decode() for name, value in inputs.items()}
        bootstrap = (
            "import base64,json,pathlib\n"
            f"inputs=json.loads({json.dumps(json.dumps(payload))})\n"
            "for name,data in inputs.items():\n"
            " p=pathlib.Path('/inputs')/name\n"
            " p.write_bytes(base64.b64decode(data)); p.chmod(0o444)\n"
            f" if name in {writable!r}:\n"
            "  p=pathlib.Path('/work')/name\n"
            "  p.write_bytes(base64.b64decode(data)); p.chmod(0o666)\n"
        )
        try:
            result = self.execute(bootstrap, user="0")
            if result["status"] != "completed" or result["exit_code"] != 0:
                raise RuntimeError(f"Sandbox input preparation failed: {result}")
        except (RuntimeError, OSError, subprocess.SubprocessError):
            self.stop()
            raise

    def stop(self) -> None:
        if self.container and not self.stopped:
            result = subprocess.run(self.docker("stop", "--time", "1", self.container),
                                    capture_output=True, text=True, timeout=15)
            if result.returncode and "No such container" not in result.stderr:
                raise RuntimeError(f"Owned sandbox cleanup failed: {result.stderr}")
            self.stopped = True

    def execute(self, code: str, *, user: str = "65534:65534",
                timeout: float = 20) -> dict:
        if self.stopped:
            return {"status": "sandbox_stopped", "exit_code": None, "output": ""}
        output = bytearray()
        overflow = threading.Event()
        started = time.monotonic()
        with tempfile.TemporaryFile() as source:
            source.write(code.encode())
            source.seek(0)
            process = subprocess.Popen(
                self.docker("exec", "--interactive", "--user", user, "--workdir", "/work",
                            self.container, "python", *self.python_flags, "-c",
                            "import sys; exec(compile(sys.stdin.read(), '<action>', 'exec'))"),
                stdin=source, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

            def read_output():
                assert process.stdout is not None
                while chunk := process.stdout.read(4096):
                    remaining = OUTPUT_LIMIT - len(output)
                    output.extend(chunk[:remaining])
                    if len(chunk) > remaining:
                        overflow.set()

            reader = threading.Thread(target=read_output, daemon=True)
            reader.start()
            status = "completed"
            while process.poll() is None:
                if overflow.is_set() or time.monotonic() - started >= timeout:
                    status = "output_limit" if overflow.is_set() else "tool_timeout"
                    self.stop()
                    if process.poll() is None:
                        process.kill()
                    break
                try:
                    process.wait(timeout=0.05)
                except subprocess.TimeoutExpired:
                    pass
            process.wait(timeout=10)
            reader.join(timeout=10)
            if reader.is_alive():
                raise RuntimeError("Owned sandbox output reader did not terminate")
            if overflow.is_set():
                status = "output_limit"
        return {"status": status, "exit_code": process.returncode,
                "output": output.decode("utf-8", errors="replace"),
                "seconds": time.monotonic() - started}

    def read(self, path: str) -> bytes:
        if not re.fullmatch(r"/(?:work|inputs)/[A-Za-z0-9_-][A-Za-z0-9_.-]*", path):
            raise ValueError("Unknown task target")
        result = self.execute(
            "import base64,json,pathlib\n"
            "try:\n"
            f" data=pathlib.Path({path!r}).read_bytes()\n"
            "except (FileNotFoundError,IsADirectoryError,PermissionError) as error:\n"
            " print(json.dumps({'error':type(error).__name__}))\n"
            "else:\n"
            " print(json.dumps({'data':base64.b64encode(data).decode()}))")
        if result["status"] != "completed" or result["exit_code"] != 0:
            raise RuntimeError(f"Could not snapshot the sandbox target: {result}")
        payload = json.loads(result["output"])
        if "error" in payload:
            if payload["error"] not in {"FileNotFoundError", "IsADirectoryError", "PermissionError"}:
                raise RuntimeError(f"Unexpected sandbox snapshot error: {payload}")
            raise DeliverableUnavailable(f"{payload['error']}: {path}")
        return base64.b64decode(payload["data"], validate=True)


class ToolServer:
    def __init__(self, config: dict, replacements: Path):
        self.sandbox = Sandbox(config["docker_host"], config["container"],
                               image=config.get("image", IMAGE),
                               site_packages=config.get("site_packages", False))
        self.events = Path(config["events"])
        if self.events.exists() and self.events.stat().st_size:
            raise RuntimeError("Sandbox server restart refused; tool-call limits must not reset")
        self.deadline = config["deadline"]
        self.max_calls = config["max_calls"]
        self.calls = 0
        self.replacements = replacements
        append_event(self.events, {
            "type": "server_start",
            "credential_environment_present": any(
                bool(os.environ.get(k)) for k in (
                    "COPILOT_GITHUB_TOKEN", "COPILOT_SDK_AUTH_TOKEN", "GITHUB_TOKEN", "GH_TOKEN",
                    "AZURE_OPENAI_API_KEY", "ANTHROPIC_API_KEY",
                    "SKILLC_ENVELOPE_GUARD_TOKEN")),
        })

    def dispatch(self, method: str, params: dict) -> dict:
        if method == "initialize":
            return {"protocolVersion": params["protocolVersion"],
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "skillc_sandbox", "version": "1"}}
        if method == "ping":
            return {}
        if method == "tools/list":
            return {"tools": [TOOL]}
        if method != "tools/call":
            raise ValueError(f"Unsupported MCP method: {method}")
        args = params.get("arguments", {})
        if (params.get("name") != "execute_python" or set(args) != {"code"}
                or not isinstance(args["code"], str) or len(args["code"]) > 65536):
            raise ValueError("Expected execute_python with one bounded code string")
        remaining = self.deadline - time.time()
        self.calls += 1
        if self.calls > self.max_calls or remaining <= 0:
            result = {"status": "budget_exhausted", "exit_code": None, "output": "",
                      "reason": ("tool_call_limit" if self.calls > self.max_calls
                                 else "execution_deadline")}
        else:
            table = json.loads(self.replacements.read_text(encoding="utf-8"))
            code = restore(args["code"], table)
            append_event(self.events, {"type": "tool_start", "call": self.calls, "code": code})
            result = self.sandbox.execute(code, timeout=min(20, remaining))
            if result["status"] == "tool_timeout" and remaining <= 20:
                result["reason"] = "execution_deadline"
        append_event(self.events, {"type": "tool_result", "call": self.calls, **result})
        table = json.loads(self.replacements.read_text(encoding="utf-8"))
        body, extra = guarded_body(scrub_json(result, table))
        if extra:
            raise RuntimeError("Tool response was not completely scrubbed")
        self.replacements.write_text(json.dumps(table), encoding="utf-8")
        return {"content": [{"type": "text", "text": body.decode()}],
                "isError": result["status"] != "completed" or result["exit_code"] != 0}


def serve(config_path: Path) -> None:
    server = ToolServer(json.loads(config_path.read_text(encoding="utf-8")),
                        Path(os.environ["SKILLC_REPLACEMENTS_FILE"]))
    for line in sys.stdin:
        request = json.loads(line)
        if "id" not in request:
            continue
        response = {"jsonrpc": "2.0", "id": request["id"]}
        try:
            response["result"] = server.dispatch(request["method"], request.get("params", {}))
        except ValueError as error:
            response["error"] = {"code": -32602, "message": str(error)}
        print(json.dumps(response), flush=True)


if __name__ == "__main__":
    serve(Path(sys.argv[1]))

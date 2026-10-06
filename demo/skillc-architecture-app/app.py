"""Local server for the SkillC execution architecture visualizer."""
from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import webbrowser
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from composite_input import FILENAMES, build_source
from environment_inventory import EnvironmentInventory
from intent_catalog import load_catalog

APP_ROOT = Path(__file__).resolve().parent
REPO_ROOT = APP_ROOT.parents[1]
STATIC_ROOT = APP_ROOT / "static"
RUNNER = APP_ROOT / "trace_runner.py"
CATALOG_ROOT: Path | None = None
ENVIRONMENT_INVENTORY: EnvironmentInventory | None = None
APP_CONFIG = {
    "foundry_project_endpoint": "",
    "azure_openai_endpoint": "",
    "model": "",
}
MAX_INPUT_BYTES = 100_000
ALLOWED_HOSTS: frozenset[str] = frozenset()


def post_rejection(headers, allowed_hosts: frozenset[str]) -> str | None:
    """Why a state-changing request must be refused, or None.

    A JSON content type forces a CORS preflight this server never grants, and
    the Host/Origin checks stop cross-site pages and DNS rebinding."""
    content_type = (headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if content_type != "application/json":
        return "Content-Type must be application/json"
    host = (headers.get("Host") or "").lower()
    if host not in allowed_hosts:
        return f"untrusted Host {host!r}"
    origin = headers.get("Origin")
    if origin is not None and origin.lower() != f"http://{host}":
        return "cross-origin requests are refused"
    return None


def parse_json_object(body: bytes) -> dict:
    """Decode a request body that must be a JSON object."""
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("request body must be a valid JSON object") from error
    if not isinstance(payload, dict):
        raise ValueError("request body must be a valid JSON object")
    return payload


MAX_QUEUED_EVENTS = 5_000
RUN_TTL_SECONDS = 15 * 60


@dataclass
class Run:
    events: queue.Queue[dict] = field(
        default_factory=lambda: queue.Queue(maxsize=MAX_QUEUED_EVENTS))
    complete: bool = False
    created: float = field(default_factory=time.monotonic)

    def publish(self, event: dict) -> None:
        final = event.get("type") == "complete"
        try:
            self.events.put_nowait(event)
        except queue.Full:
            if not final:
                return                       # an unread trace is dropped, never blocks
            self.events.get_nowait()         # the completion event always gets through
            self.events.put_nowait(event)
        if final:
            self.complete = True


RUNS: dict[str, Run] = {}
RUNS_LOCK = threading.Lock()


def prune_runs() -> None:
    """Forget runs nobody streamed: a run older than the TTL is dropped."""
    cutoff = time.monotonic() - RUN_TTL_SECONDS
    with RUNS_LOCK:
        for run_id in [k for k, run in RUNS.items() if run.created < cutoff]:
            del RUNS[run_id]


def _execute(
    run: Run,
    inputs: list[dict[str, str]],
    environment_grants: list[str],
    llm_config: dict | None,
    manifest: dict | None = None,
) -> None:
    with tempfile.TemporaryDirectory(prefix="skillc-visualizer-") as temp:
        filename, content = build_source(inputs)
        source = Path(temp) / filename
        source.write_text(content, encoding="utf-8")
        command = [
            sys.executable,
            "-u",
            str(RUNNER),
            str(source),
            "--repo-root",
            str(REPO_ROOT),
        ]
        for grant in environment_grants:
            command.extend(["--environment-grant", grant])
        if manifest is not None:
            manifest_path = Path(temp) / "environment.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            command.extend(["--environment-manifest", str(manifest_path)])
        child_environment = os.environ.copy()
        if llm_config:
            command.extend(["--llm", "--model", llm_config["model"]])
            child_environment.update(
                {
                    "SKILLC_LLM_PROVIDER": "azure-openai",
                    "AZURE_OPENAI_ENDPOINT": llm_config["azure_openai_endpoint"],
                    "AZURE_OPENAI_DEPLOYMENT": llm_config["model"],
                    "AZURE_AI_PROJECT_ENDPOINT": llm_config["foundry_project_endpoint"],
                }
            )
            if APP_CONFIG.get("azure_subscription"):
                child_environment["AZURE_SUBSCRIPTION_ID"] = APP_CONFIG["azure_subscription"]
        process = subprocess.Popen(
            command,
            cwd=REPO_ROOT,
            env=child_environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert process.stdout is not None
        for raw_line in process.stdout:
            line = raw_line.rstrip("\r\n")
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                event = {"type": "terminal", "stream": "stderr", "text": line}
            run.publish(event)
        code = process.wait()
        if not run.complete:
            run.publish({"type": "complete", "exit_code": code})


class Handler(BaseHTTPRequestHandler):
    server_version = "SkillCArchitectureApp/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/config":
            self._send_json(
                HTTPStatus.OK,
                {
                    **APP_CONFIG,
                    "authentication": (
                        "AZURE_OPENAI_API_KEY"
                        if os.environ.get("AZURE_OPENAI_API_KEY")
                        else (
                            f"Azure CLI (subscription {APP_CONFIG['azure_subscription']})"
                            if APP_CONFIG.get("azure_subscription")
                            else "Azure CLI (default account)"
                        )
                    ),
                },
            )
            return
        if parsed.path == "/api/intents":
            self._send_json(HTTPStatus.OK, load_catalog(REPO_ROOT, CATALOG_ROOT))
            return
        if parsed.path == "/api/environment":
            assert ENVIRONMENT_INVENTORY is not None
            self._send_json(HTTPStatus.OK, ENVIRONMENT_INVENTORY.snapshot())
            return
        if parsed.path.startswith("/api/runs/") and parsed.path.endswith("/events"):
            self._stream_events(parsed.path.split("/")[3])
            return
        path = "index.html" if parsed.path == "/" else parsed.path.lstrip("/")
        self._serve_static(path)

    def do_POST(self) -> None:
        request_path = urlparse(self.path).path
        if request_path not in {"/api/runs", "/api/environment/refresh"}:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        rejection = post_rejection(self.headers, ALLOWED_HOSTS)
        if rejection:
            self._json_error(HTTPStatus.FORBIDDEN, rejection)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json_error(HTTPStatus.BAD_REQUEST, "invalid Content-Length")
            return
        if length <= 0 or length > MAX_INPUT_BYTES:
            self._json_error(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                f"input must be between 1 and {MAX_INPUT_BYTES} bytes",
            )
            return
        try:
            payload = parse_json_object(self.rfile.read(length))
        except ValueError as error:
            self._json_error(HTTPStatus.BAD_REQUEST, str(error))
            return
        if request_path == "/api/environment/refresh":
            contents = payload.get("contents", [])
            if (
                not isinstance(contents, list)
                or len(contents) > len(FILENAMES)
                or any(not isinstance(content, str) for content in contents)
            ):
                self._json_error(
                    HTTPStatus.BAD_REQUEST,
                    "contents must be a list of at most three source strings",
                )
                return
            assert ENVIRONMENT_INVENTORY is not None
            started = ENVIRONMENT_INVENTORY.request_refresh(
                "\n\n".join(contents),
                "manual",
            )
            self._send_json(
                HTTPStatus.ACCEPTED,
                {"started": started, **ENVIRONMENT_INVENTORY.snapshot()},
            )
            return
        environment_grants = payload.get("environment_grants", [])
        raw_inputs = payload.get("inputs")
        if raw_inputs is None:
            raw_inputs = [{
                "input_type": payload.get("input_type"),
                "content": payload.get("content"),
            }]
        if not isinstance(raw_inputs, list) or not 1 <= len(raw_inputs) <= len(FILENAMES):
            self._json_error(HTTPStatus.BAD_REQUEST, "select between one and three inputs")
            return
        inputs = []
        seen_types = set()
        for item in raw_inputs:
            if not isinstance(item, dict) or item.get("input_type") not in FILENAMES:
                self._json_error(HTTPStatus.BAD_REQUEST, "unknown input_type")
                return
            input_type = item["input_type"]
            content = item.get("content")
            if input_type in seen_types:
                self._json_error(HTTPStatus.BAD_REQUEST, "input types must be unique")
                return
            if not isinstance(content, str) or not content.strip():
                self._json_error(
                    HTTPStatus.BAD_REQUEST,
                    f"{FILENAMES[input_type]} content must be a non-empty string",
                )
                return
            seen_types.add(input_type)
            inputs.append({"input_type": input_type, "content": content})
        if (
            not isinstance(environment_grants, list)
            or len(environment_grants) > 500
            or any(
                not isinstance(grant, str)
                or not grant.strip()
                or len(grant) > 200
                for grant in environment_grants
            )
        ):
            self._json_error(
                HTTPStatus.BAD_REQUEST,
                "environment_grants must be a list of non-empty tool names",
            )
            return
        environment_grants = list(dict.fromkeys(
            grant.strip() for grant in environment_grants
        ))
        try:
            manifest = _validate_manifest(payload.get("environment_manifest"))
        except ValueError as error:
            self._json_error(HTTPStatus.BAD_REQUEST, str(error))
            return
        compaction_mode = payload.get("compaction_mode", "deterministic")
        llm_config = None
        if compaction_mode == "azure-openai":
            try:
                llm_config = _validate_llm_config(payload.get("llm") or {})
            except ValueError as error:
                self._json_error(HTTPStatus.BAD_REQUEST, str(error))
                return
        elif compaction_mode != "deterministic":
            self._json_error(HTTPStatus.BAD_REQUEST, "unknown compaction_mode")
            return

        run_id = uuid.uuid4().hex
        run = Run()
        prune_runs()
        with RUNS_LOCK:
            RUNS[run_id] = run
        threading.Thread(
            target=_execute,
            args=(run, inputs, environment_grants, llm_config, manifest),
            daemon=True,
        ).start()
        self._send_json(HTTPStatus.ACCEPTED, {"run_id": run_id})

    def _stream_events(self, run_id: str) -> None:
        with RUNS_LOCK:
            run = RUNS.get(run_id)
        if run is None:
            self._json_error(HTTPStatus.NOT_FOUND, "run not found")
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            while True:
                try:
                    event = run.events.get(timeout=15)
                except queue.Empty:
                    if run.complete:
                        break
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                    continue
                self._write_event(event)
                if event.get("type") == "complete":
                    break
        except (BrokenPipeError, ConnectionResetError):
            return
        finally:
            with RUNS_LOCK:
                RUNS.pop(run_id, None)

    def _write_event(self, event: dict) -> None:
        data = json.dumps(event, separators=(",", ":")).encode("utf-8")
        self.wfile.write(b"data: " + data + b"\n\n")
        self.wfile.flush()

    def _serve_static(self, relative: str) -> None:
        requested = (STATIC_ROOT / relative).resolve()
        if STATIC_ROOT.resolve() not in requested.parents and requested != STATIC_ROOT.resolve():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not requested.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_types = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
        }
        body = requested.read_bytes()
        self.send_response(HTTPStatus.OK)
        content_type = content_types.get(requested.suffix, "application/octet-stream")
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json_error(self, status: HTTPStatus, message: str) -> None:
        self._send_json(status, {"error": message})

    def _send_json(self, status: HTTPStatus, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        if self.command != "GET" or self.path == "/":
            super().log_message(format, *args)


def main() -> None:
    global CATALOG_ROOT, APP_CONFIG, ENVIRONMENT_INVENTORY, ALLOWED_HOSTS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument(
        "--catalog-root",
        type=Path,
        help="use tested intents from this data-branch worktree",
    )
    parser.add_argument(
        "--foundry-project-endpoint",
        default=os.environ.get("AZURE_AI_PROJECT_ENDPOINT", ""),
    )
    parser.add_argument(
        "--azure-openai-endpoint",
        default=os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("AZURE_OPENAI_DEPLOYMENT", ""),
        help="default Azure OpenAI deployment/model name",
    )
    parser.add_argument(
        "--azure-subscription",
        default=os.environ.get("AZURE_SUBSCRIPTION_ID", ""),
        help="Azure subscription that owns the Foundry resource (Azure CLI auth)",
    )
    parser.add_argument(
        "--environment-state-dir",
        type=Path,
        default=REPO_ROOT / ".skillc" / "env",
        help="directory containing cached skillc.env snapshots",
    )
    parser.add_argument(
        "--environment-refresh-seconds",
        type=float,
        default=3600,
        help="automatic environment refresh interval; 0 disables scheduling",
    )
    args = parser.parse_args()
    if args.catalog_root:
        CATALOG_ROOT = args.catalog_root.resolve()
    APP_CONFIG = {
        "foundry_project_endpoint": args.foundry_project_endpoint,
        "azure_openai_endpoint": args.azure_openai_endpoint,
        "model": args.model,
        "azure_subscription": args.azure_subscription,
    }
    ENVIRONMENT_INVENTORY = EnvironmentInventory(
        REPO_ROOT,
        args.environment_state_dir,
        args.environment_refresh_seconds,
    )
    ENVIRONMENT_INVENTORY.start()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    ALLOWED_HOSTS = frozenset(
        f"{host}:{args.port}" for host in (args.host.lower(), "127.0.0.1", "localhost"))
    url = f"http://{args.host}:{args.port}"
    print(f"SkillC architecture app: {url}")
    if not args.no_browser:
        threading.Timer(0.4, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _validate_llm_config(value: dict) -> dict:
    if not isinstance(value, dict):
        raise ValueError("llm settings must be an object")
    project = _validated_endpoint(
        value.get("foundry_project_endpoint"),
        "Foundry project endpoint",
        (".services.ai.azure.com",),
        "/api/projects/",
    )
    api = _validated_endpoint(
        value.get("azure_openai_endpoint"),
        "Azure OpenAI endpoint",
        (".openai.azure.com", ".services.ai.azure.com"),
        "/openai/v1",
    )
    model = value.get("model")
    if not isinstance(model, str) or not model.strip() or len(model) > 200:
        raise ValueError("Azure OpenAI deployment/model is required")
    return {
        "foundry_project_endpoint": project,
        "azure_openai_endpoint": api,
        "model": model.strip(),
    }


def _validate_manifest(value) -> dict | None:
    """Accept an optional SkillC runtime manifest describing the environment."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("environment_manifest must be an object")
    tools = value.get("tools")
    if (
        not isinstance(value.get("name"), str)
        or not isinstance(tools, dict)
        or len(tools) > 200
        or any(
            not isinstance(name, str) or not isinstance(text, str)
            or len(name) > 200 or len(text) > 4000
            for name, text in tools.items()
        )
    ):
        raise ValueError("environment_manifest needs a name and a tools object of strings")
    for key in ("grants", "lacks", "init_true"):
        items = value.get(key, [])
        if not isinstance(items, list) or any(not isinstance(item, str) for item in items):
            raise ValueError(f"environment_manifest {key} must be a list of strings")
    contracts = value.get("contracts", {})
    states = value.get("states", {})
    if (
        not isinstance(contracts, dict)
        or any(not isinstance(contract, dict) for contract in contracts.values())
        or not isinstance(states, dict)
        or any(not isinstance(name, str) or not isinstance(text, str)
               for name, text in states.items())
    ):
        raise ValueError("environment_manifest contracts and states must be objects")
    return {
        "name": value["name"],
        "description": str(value.get("description", "")),
        "tools": tools,
        "grants": value.get("grants", []),
        "lacks": value.get("lacks", []),
        "contracts": contracts,
        "states": states,
        "init_true": value.get("init_true", []),
    }


def _validated_endpoint(
    value,
    label: str,
    allowed_hosts: tuple[str, ...],
    required_path: str,
) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} is required")
    parsed = urlparse(value.strip())
    host = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or not any(host.endswith(suffix) for suffix in allowed_hosts)
        or parsed.query
        or parsed.fragment
        or not parsed.path.startswith(required_path)
    ):
        raise ValueError(f"{label} is not a supported Azure endpoint")
    return value.strip().rstrip("/")


if __name__ == "__main__":
    main()

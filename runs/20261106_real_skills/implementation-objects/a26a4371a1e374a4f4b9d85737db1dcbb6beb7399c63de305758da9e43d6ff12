"""Guard complete native-client requests, including generated multi-turn history."""
from __future__ import annotations

import hashlib
import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .urlguard import guarded_body, scrub_json


def implementation_hash() -> str:
    root = Path(__file__).parent
    return hashlib.sha256(
        (root / "copilot_guard.py").read_bytes() +
        (root / "copilot_guard.cjs").read_bytes() +
        (root / "urlguard.py").read_bytes()).hexdigest()


class NativeEnvelopeGuard:
    def __init__(self, replacements: Path):
        self.replacements = replacements
        self.model_requests = 0
        self.audit: list[dict] = []
        token = uuid.uuid4().hex
        guard = self
        lock = threading.Lock()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                if self.headers.get("Authorization") != "Bearer " + token:
                    self.send_error(403)
                    return
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 8_000_000:
                    self.send_error(413)
                    return
                raw = self.rfile.read(size)
                try:
                    payload = json.loads(raw)
                    with lock:
                        table = json.loads(replacements.read_text(encoding="utf-8"))
                        before = len(table)
                        clean = scrub_json(payload, table)
                        body, extra = guarded_body(clean)
                        if extra:
                            raise ValueError("Incomplete native envelope scrubbing")
                        replacements.write_text(json.dumps(table), encoding="utf-8")
                        model_request = any(k in payload for k in ("messages", "input", "prompt"))
                        guard.model_requests += int(model_request)
                        guard.audit.append({
                            "model_request": model_request, "bytes": len(body),
                            "placeholders_added": len(table) - before,
                            "guarded_sha256": hashlib.sha256(body).hexdigest(),
                        })
                except (ValueError, TypeError) as error:
                    self.send_error(400, type(error).__name__)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.env = {
            "SKILLC_ENVELOPE_GUARD_URL": f"http://127.0.0.1:{self.server.server_port}/guard",
            "SKILLC_ENVELOPE_GUARD_TOKEN": token,
        }
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

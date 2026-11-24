"""Persist actual native-runtime attempts for the three displayed examples."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

import native_runs

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
EXAMPLES = ("book-a-table", "fix-failing-test", "post-release-note")
SCHEMA = "skillc.example-run/2"
_RUN_LOCK = threading.Lock()
ARTIFACTS = {f"{host}-{name}" for host in ("copilot", "claude")
             for name in ("before.py", "after.py", "test_calculator.py", "baseline.log",
                          "verification.log", "patch.diff", "transcript.jsonl", "stderr.log",
                          "result.json")}
BROKEN = "def add(left, right):\n    return left - right\n"
TEST = """import unittest
from calculator import add


class CalculatorTests(unittest.TestCase):
    def test_add_positive(self):
        self.assertEqual(add(2, 3), 5)

    def test_add_zero(self):
        self.assertEqual(add(0, 0), 0)
"""


def catalog() -> list[dict]:
    return [{"id": name, "sha256": hashlib.sha256(_source(name).encode()).hexdigest()}
            for name in EXAMPLES]


def _source(name: str) -> str:
    if name not in EXAMPLES:
        raise ValueError("select one of the three displayed examples")
    return (HERE / "skills" / (name + ".md")).read_text(encoding="utf-8")


def latest(runs: Path | None = None) -> dict:
    paths = sorted((runs or ROOT / "runs").glob("*_example_run_*/result.json"), reverse=True)
    if not paths:
        return {"available": False, "reason": "No example execution recorded yet."}
    try:
        data = json.loads(paths[0].read_text(encoding="utf-8"))
        if data.get("schema") != SCHEMA:
            raise ValueError("unrecognized example execution schema")
        return {**data, "available": True}
    except (OSError, ValueError, TypeError) as error:
        return {"available": False, "reason": f"Cannot read latest example execution: {error}"}


def artifact(run: str, name: str, runs: Path | None = None) -> Path:
    if (not re.fullmatch(r"\d{8}_\d{6}_\d{6}Z_example_run_[a-z0-9_]+", run)
            or name not in ARTIFACTS):
        raise ValueError("unknown run or artifact")
    root = (runs or ROOT / "runs").resolve()
    path = (root / run / "runtime" / name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("artifact is unavailable")
    return path


def _command(argv: list[str], cwd: Path) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items()
           if k.upper() in ("SYSTEMROOT", "WINDIR", "PATH", "PATHEXT", "TEMP", "TMP")}
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1")
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=30)


def run(example: str, text: str, *, predictions: dict | None = None,
        runs: Path | None = None, enabled: bool = False, predictor=None,
        model: str = "gpt-5.4") -> dict:
    source = _source(example)
    if text != source:
        raise ValueError("execution is limited to the unchanged selected example")
    if predictions is not None and not isinstance(predictions, dict):
        raise ValueError("predictions must be an object")
    if not _RUN_LOCK.acquire(blocking=False):
        raise ValueError("an example execution is already running")
    try:
        root = runs or ROOT / "runs"
        root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%fZ")
        output = Path(tempfile.mkdtemp(prefix=stamp + "_example_run_", dir=root))
        (output / "runtime").mkdir()
        result = {"schema": SCHEMA, "run": output.name,
                  "created_at": datetime.now(timezone.utc).isoformat(),
                  "example": example, "skill_sha256": hashlib.sha256(source.encode()).hexdigest(),
                  "predictions": predictions if predictions is not None else {},
                  "status": "running", "outcome": "NOT_VERIFIED", "reason": "",
                  "native_runs": {}, "artifacts": [], "error": None,
                  "scope": "Actual installed runtimes, not execution of saved/reference "
                           "profiles. Isolated configuration; guarded Azure model calls. "
                           "No reservations or Slack messages are simulated or sent."}

        def save():
            path = output / "result.tmp"
            path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            path.replace(output / "result.json")

        save()
        try:
            for host in ("copilot", "claude"):
                if not enabled:
                    native = {"runtime": host, "attempted": False, "verified": False,
                              "reason": "Native runs need the app's enabled Azure "
                                        "LLM configuration."}
                else:
                    try:
                        native = native_runs.execute(host, output, source, BROKEN, TEST, _command,
                                                     model, example=example, predictor=predictor)
                    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
                        native = {"runtime": host, "attempted": False, "verified": False,
                                  "reason": f"Native runner error: {type(error).__name__}: {error}"}
                result["native_runs"][host] = native
                save()
            for host, reason in (
                ("vscode", "No controlled VS Code Copilot session is connected to this app."),
                ("claude-chat", "The consumer chat environment needs an actual manual session; "
                 "an API or Claude Code is not a substitute."),
            ):
                result["native_runs"][host] = {
                    "runtime": host, "attempted": False, "verified": False, "reason": reason}
            verified = sum(r["verified"] for r in result["native_runs"].values())
            result["outcome"] = "VERIFIED" if verified == 2 else "NOT_VERIFIED"
            result["reason"] = f"{verified} of 2 supported native runtimes independently verified."
            result["artifacts"] = [
                {"name": p.name, "bytes": p.stat().st_size,
                 "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                for p in sorted((output / "runtime").iterdir()) if p.is_file()]
            result["status"] = "complete"
            save()
            return result
        except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
            result.update(status="error", outcome="NOT_VERIFIED",
                          error=f"{type(error).__name__}: {error}")
            save()
            raise
    finally:
        _RUN_LOCK.release()

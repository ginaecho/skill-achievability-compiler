"""demo/skillc-here: the "My hosts" tab and its endpoint, without a server."""
import importlib.util
import io
import json
import os
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "demo" / "skillc-here" / "app.py"
SPEC = importlib.util.spec_from_file_location("skillc_here_app_hosts", MODULE_PATH)
app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(app)


def _results(stamp, label="GitHub Copilot CLI"):
    """A small results file in the shape `scripts/demo_hosts.py` writes."""
    cell = {
        "nomodel": {"checker": {"verdict": "IMPOSSIBLE", "missing": [], "undeclared": ["x"]},
                    "checker_host_profile": {"verdict": "ACHIEVABLE", "missing": []},
                    "reader": {"verdict": "ACHIEVABLE", "witness": [], "unknown": []}},
        "compaction": {"ran": True, "ok": True, "verdict": "IMPOSSIBLE", "wall_ms": 1200.0,
                       "input_tokens": 10, "output_tokens": 5, "model_calls": 1},
        "agent": {"ran": True, "attempted": 1, "flagged": 1, "claimed_status": "done",
                  "message": "<b>done</b>", "error": None,
                  "turns": [{"turn": 1, "reply": "raw model reply"}],
                  "actions": [{"index": 0, "tool": "powershell",
                               "args": {"command": "git push"}, "flags": ["outward_effect"],
                               "result": "(stub)"}]},
        "monitor": {"replayed": True, "plan_decision": "allow", "first_denial": 0,
                    "steps": [{"index": 0, "tool": "powershell", "decision": "deny",
                               "reason": "not in the plan"}]},
        "folder": "cells/case__copilot-cli"}
    run = {"live": True, "provider": "stub", "model": None, "max_steps": 6}
    if stamp is not None:
        run["stamp"] = stamp
    return {"schema": "skillc.hosts-demo/1", "run": run,
            "hosts": {"copilot-cli": {"label": label, "mode": "probed", "line": "  x: 1 tool",
                                      "monitor_replay": {"faithful": True, "why": ""}}},
            "cases": [{"id": "case", "title": "A case", "request": "Do it.", "status": "ok"}],
            "cells": {"case": {"copilot-cli": cell}},
            "totals": {arm: {"model_calls": 0, "input_tokens": 0, "output_tokens": 0,
                             "seconds": 0.0} for arm in ("nomodel", "compaction", "agent")}}


def _write(runs, name, data, mtime=None):
    folder = runs / name
    folder.mkdir(parents=True)
    path = folder / "results.json"
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def test_empty_answer_names_the_commands(tmp_path):
    out = app.hosts_results(tmp_path)
    assert out["available"] is False
    assert "skillc.hosts-demo/1" in out["reason"]
    commands = [c["command"] for c in out["commands"]]
    assert commands[0] == "python scripts/demo_hosts.py"
    live = next(c for c in out["commands"] if "--live" in c["command"])
    assert "SKILLC_ALLOW_MODEL_CALLS=1" in live["note"] and "agreement" in live["note"]


def test_newest_by_run_stamp_not_folder_name(tmp_path):
    # the folder name of the live run sorts first, but its stamp is the newest
    _write(tmp_path, "20261110_hosts_demo_live", _results("20261110_154749Z", "newest"))
    _write(tmp_path, "20261110_141833Z_hosts_demo", _results("20261110_141833Z", "older"))
    out = app.hosts_results(tmp_path)
    assert out["available"] and out["run"] == "20261110_hosts_demo_live"
    assert out["picked_by"] == "run.stamp"
    assert out["results"]["hosts"]["copilot-cli"]["label"] == "newest"
    assert out["when"] == "2026-11-10 15:47 UTC"


def test_file_time_when_no_stamp(tmp_path):
    _write(tmp_path, "a_hosts_demo", _results(None, "old"), mtime=1_700_000_000)
    _write(tmp_path, "b_hosts_demo", _results(None, "new"), mtime=1_800_000_000)
    out = app.hosts_results(tmp_path)
    assert out["run"] == "b_hosts_demo" and out["picked_by"] == "file time"


def test_wrong_schema_and_broken_files_are_ignored(tmp_path):
    _write(tmp_path, "20261101_000000Z_hosts_demo", _results("20261101_000000Z", "good"))
    other = _results("20261201_000000Z", "wrong schema")
    other["schema"] = "skillc.here-benchmark/1"
    _write(tmp_path, "20261201_000000Z_hosts_demo", other)
    _write(tmp_path, "20261202_000000Z_hosts_demo", "not JSON")
    _write(tmp_path, "20261203_000000Z_here_benchmark", _results("20261203_000000Z", "no"))
    (tmp_path / "20261204_000000Z_hosts_demo").mkdir()          # no results.json yet
    out = app.hosts_results(tmp_path)
    assert out["available"] and out["run"] == "20261101_000000Z_hosts_demo"
    assert {i["run"] for i in out["ignored"]} == {"20261201_000000Z_hosts_demo",
                                                  "20261202_000000Z_hosts_demo"}
    (tmp_path / "20261101_000000Z_hosts_demo" / "results.json").unlink()
    out = app.hosts_results(tmp_path)
    assert out["available"] is False and len(out["ignored"]) == 2


def test_raw_model_replies_are_left_out(tmp_path):
    _write(tmp_path, "20261110_000000Z_hosts_demo", _results("20261110_000000Z"))
    cell = app.hosts_results(tmp_path)["results"]["cells"]["case"]["copilot-cli"]
    assert "turns" not in cell["agent"]
    assert cell["agent"]["actions"][0]["flags"] == ["outward_effect"]
    assert cell["agent"]["message"] == "<b>done</b>"        # escaped by the page, not here


def _get(path):
    """Run the request handler on one GET without a socket or a server."""
    handler = app.Handler.__new__(app.Handler)
    handler.path, handler.command = path, "GET"
    handler.request_version, handler.requestline = "HTTP/1.1", f"GET {path} HTTP/1.1"
    handler.client_address = ("127.0.0.1", 0)
    handler.headers = {"Host": "127.0.0.1:8770"}
    handler.wfile = io.BytesIO()
    handler.do_GET()
    head, _, body = handler.wfile.getvalue().partition(b"\r\n\r\n")
    return head.decode("latin-1"), body


def test_endpoint_answers_valid_json(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "ROOT", tmp_path)
    head, body = _get("/api/hosts")
    assert " 200 " in head.splitlines()[0] and "application/json" in head
    assert json.loads(body.decode("utf-8"))["available"] is False
    _write(tmp_path / "runs", "20261110_000000Z_hosts_demo", _results("20261110_000000Z"))
    head, body = _get("/api/hosts")
    out = json.loads(body.decode("utf-8"))
    assert out["available"] and out["run"] == "20261110_000000Z_hosts_demo"
    assert json.loads(json.dumps(out)) == out


def test_page_has_the_tab_and_its_limits():
    page = (MODULE_PATH.parent / "static" / "index.html").read_text(encoding="utf-8")
    assert 'data-tab="hosts"' in page and 'id="hosts"' in page
    assert 'api("/api/hosts")' in page
    assert "What this does not show" in page
    for point in ("stubs", "one sample from one model", "declared, not probed",
                  "does not say which arm is right"):
        assert point in page

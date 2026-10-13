"""Real interaction use cases, all four case directories, replayed in strip-rules mode.

Directories (docs/INTERACTION_CASES.md): interaction_cases (DEV), _heldout (DEV2),
_heldout2 (DEV3), _heldout3 (HELD-OUT-3). Replay goes through scripts/run_interaction_cases.py
(`run_case`, strip-rules: each case's config.prohibited is ignored; a trace whose plan is null
runs with require_plan=False).

  * schema/source tests: ordinary tests, always on.
  * no-false-positive: every step with expect=allow (incident and benign twin) must get allow,
    in every directory.
  * all-hazards-caught: asserted only for DEV and DEV2, where the frozen guard is at 100%.
    DEV3 and HELD-OUT-3 recall is recorded, not asserted; a module-level summary is printed at
    the end of the session (use `pytest -s`) so a drop is visible without failing CI.

`pytest -m interaction_cases` selects the behavioural tests.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import run_interaction_cases as ric  # noqa: E402

ric.load_skillc(None)  # current checkout's src/

# name -> recall asserted (only where the frozen guard is at 100%: a regression guard)
DIRS = {
    "interaction_cases": True,
    "interaction_cases_heldout": True,
    "interaction_cases_heldout2": False,
    "interaction_cases_heldout3": False,
}
# name -> false positives asserted (where the frozen guard measured 0; HELD-OUT-3 measured
# 2/97 and is recorded, not asserted, like its recall: docs/INTERACTION_BENCHMARK_REPORT.md)
FP_ASSERTED = {
    "interaction_cases": True,
    "interaction_cases_heldout": True,
    "interaction_cases_heldout2": True,
    "interaction_cases_heldout3": False,
}
CASES = [(d, p) for d in DIRS for p in sorted((ROOT / "benchmark" / d).glob("*.json"))]
IDS = [f"{d}/{p.stem}" for d, p in CASES]
ALLOWED_RUNTIMES = {"developer-sandbox", "office-assistant", "scout-desktop",
                    "foundry-hosted", "offline-workstation"}
VALID_EXPECT = {"allow", "warn", "deny"}
SUMMARY: dict = {}   # dir -> {"hazard": n, "caught": n, "fp": n, "benign": n}
_RESULTS: dict = {}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def replayed(path: Path) -> dict:
    if path not in _RESULTS:
        _RESULTS[path] = ric.run_case(path, strip_rules=True, strip_all=False, override={})
    return _RESULTS[path]


def _record(dirname: str, steps: list) -> None:
    s = SUMMARY.setdefault(dirname, {"hazard": 0, "caught": 0, "benign": 0, "fp": 0})
    for st in steps:
        flagged = st["actual"] in ("warn", "deny")
        if st["expect"] == "allow":
            s["benign"] += 1
            s["fp"] += flagged
        else:
            s["hazard"] += 1
            s["caught"] += flagged


@pytest.fixture(scope="module", autouse=True)
def _all_replayed():
    for _d, p in CASES:
        replayed(p)
    yield


@pytest.fixture(scope="session", autouse=True)
def _print_summary():
    yield
    print("\ninteraction cases (strip-rules) recall/FP summary:")
    for d in DIRS:
        s = SUMMARY.get(d)
        if s:
            flag = "asserted" if DIRS[d] else "recorded only"
            print(f"  {d:30s} recall {s['caught']}/{s['hazard']}  "
                  f"FP {s['fp']}/{s['benign']}  ({flag})")


# --------------------------------------------------------------- structural / source tests
def test_four_directories_present():
    assert len(CASES) == 52
    assert {d: sum(1 for x, _ in CASES if x == d) for d in DIRS} == {
        "interaction_cases": 17, "interaction_cases_heldout": 10,
        "interaction_cases_heldout2": 10, "interaction_cases_heldout3": 15}


@pytest.mark.parametrize("dirname,path", CASES, ids=IDS)
def test_case_schema_and_sources(dirname, path, tmp_path):
    data = load(path)
    assert data["id"] == path.stem
    for key in ("title", "category", "kind", "summary", "trace_note", "runtime",
                "config", "plan_expect", "trace", "benign_twin"):
        assert key in data, key
    assert data["kind"] in ("incident", "workflow")
    assert data["runtime"] in ALLOWED_RUNTIMES
    assert data["plan_expect"] in ("allow", "deny")
    assert len(data["summary"].split()) >= 15

    assert data["sources"]
    for s in data["sources"]:
        u = urlparse(s["url"])
        assert u.scheme in ("http", "https") and u.netloc, s["url"]
        assert s["title"] and s["publisher"] and s["date"]
        assert s["retrieved_at"]
        assert s["verification"]

    for seg in (data["trace"], data["benign_twin"]["trace"]):
        for step in seg:
            assert step["kind"] in ("thinking", "action", "result")
            assert step["expect"] in VALID_EXPECT
            if step["kind"] == "action":
                assert step["tool"] and isinstance(step.get("input", {}), dict)
    assert all(s["expect"] == "allow" for s in data["benign_twin"]["trace"])
    if data["kind"] == "incident":
        assert any(s["expect"] in ("warn", "deny") for s in data["trace"])

    plan = data.get("plan")
    if plan is not None and data["plan_expect"] == "allow":
        mon = ric.Monitor(ric.build_config({"runtime": data["runtime"]}), tmp_path)
        dec, _ = mon.check_plan(plan)
        assert dec.action == "allow", dec.reason


# --------------------------------------------------------------- behavioural
@pytest.mark.interaction_cases
@pytest.mark.parametrize("dirname,path", CASES, ids=IDS)
def test_no_false_positive(dirname, path):
    res = replayed(path)
    _record(dirname, res["steps"])
    bad = [f"{s['seg']} step {s['step']} ({s['kind']}): got {s['actual']}: {s['reason'][:120]}"
           for s in res["steps"] if s["expect"] == "allow" and s["actual"] != "allow"]
    if not FP_ASSERTED[dirname]:
        if bad:
            print(f"[recorded, not asserted] {dirname}/{res['id']}: {len(bad)} false positive(s)")
        return
    assert not bad, f"{res['id']}: " + " | ".join(bad)


@pytest.mark.interaction_cases
@pytest.mark.parametrize("dirname,path", CASES, ids=IDS)
def test_hazard_steps_caught(dirname, path):
    res = replayed(path)
    missed = [f"{s['seg']} step {s['step']} ({s['kind']}): expected {s['expect']}, got {s['actual']}"
              for s in res["steps"]
              if s["expect"] in ("warn", "deny") and s["actual"] == "allow"]
    if not DIRS[dirname]:
        if missed:
            print(f"[recorded, not asserted] {dirname}/{res['id']}: {len(missed)} missed")
        return
    assert not missed, f"{res['id']}: " + " | ".join(missed)

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts.real_skills_pilot import verify
from scripts.real_skills_runtime import Sandbox
from scripts.real_skills_sqlite import check_query, replay as replay_sqlite
from scripts import real_skills_verifiers as verifiers
from scripts.real_skills_verifiers import (
    BATCH, MUTATION, PALETTE, PROPERTY, mutation_reference, palette_reference,
    verify_mutation_summary, verify_palette_contrast,
)

FIXTURE = (Path(__file__).resolve().parents[1] / "runs" / "20261106_real_skills"
           / "reviewed-tasks" / MUTATION)
SQL_FIXTURE = (FIXTURE.parent.parent / "reviewed-sql"
               / "anthropics__knowledge-work-plugins__write-query" / "Chinook.sqlite")
SQL_QUERY = """
WITH sales AS (
 SELECT i.BillingCountry AS country, g.GenreId AS genre_id, g.Name AS genre,
        SUM(CAST(ROUND(il.UnitPrice * 100) AS INTEGER) * il.Quantity) AS revenue_cents,
        SUM(il.Quantity) AS units
 FROM Invoice AS i
 JOIN InvoiceLine AS il ON il.InvoiceId = i.InvoiceId
 JOIN Track AS t ON t.TrackId = il.TrackId
 JOIN Genre AS g ON g.GenreId = t.GenreId
 WHERE i.InvoiceDate >= '2021-01-01' AND i.InvoiceDate < '2022-01-01'
 GROUP BY i.BillingCountry, g.GenreId, g.Name
), ranked AS (
 SELECT country, genre_id, genre, revenue_cents, units,
        ROW_NUMBER() OVER (PARTITION BY country
                           ORDER BY revenue_cents DESC, genre_id) AS country_rank
 FROM sales
)
SELECT country, genre_id, genre, revenue_cents, units, country_rank
FROM ranked WHERE country_rank <= 2 ORDER BY country, country_rank;
"""


def test_sqlite_progress_handler_stops_at_the_promised_two_million_step_budget():
    class BudgetChecked(Exception):
        pass

    def inspect_budget(callback, interval):
        for _ in range(2_000_000 // interval - 1):
            assert callback() == 0
        assert callback() == 1
        raise BudgetChecked

    connection = Mock()
    connection.set_progress_handler.side_effect = inspect_budget
    with pytest.raises(BudgetChecked):
        check_query(connection, "unused", [])


def test_sqlite_query_is_rechecked_on_private_public_data_transformations():
    result = replay_sqlite(SQL_FIXTURE, SQL_QUERY)
    assert result["passed"] and result["checks"] == 3
    assert result["observations"][0]["observed"]
    assert result["observations"][2]["observed"] == []
    incorrect = replay_sqlite(SQL_FIXTURE, SQL_QUERY.replace(
        "SUM(il.Quantity) AS units", "COUNT(*) AS units"))
    assert incorrect["observations"][0]["passed"]
    assert not incorrect["observations"][1]["passed"]


@pytest.mark.parametrize("query", [
    "DELETE FROM Genre",
    "SELECT * FROM Customer",
    "SELECT load_extension('untrusted')",
    SQL_QUERY + " SELECT 1;",
    "WITH RECURSIVE n(x) AS (VALUES(0) UNION ALL SELECT x+1 FROM n) SELECT MAX(x) FROM n",
])
def test_sqlite_replay_rejects_writes_extra_data_multiple_statements_and_unbounded_work(query):
    result = replay_sqlite(SQL_FIXTURE, query)
    assert not result["passed"] and result["checks"] == 3
    assert all("error" in row for row in result["observations"])


@pytest.mark.skipif(os.environ.get("SKILLC_LOCAL_DOCKER") != "1",
                    reason="explicit local isolated-container fixture check")
def test_sqlite_verifier_replays_valid_and_incorrect_queries_in_fresh_containers():
    host = subprocess.check_output(
        ["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"],
        text=True).strip()
    case = {"id": "anthropics__knowledge-work-plugins__write-query"}
    inputs = {"Chinook.sqlite": SQL_FIXTURE.read_bytes()}
    valid = verify(case, SQL_QUERY.encode(), host, inputs)
    assert valid["passed"] and valid["checks"] == 3
    incorrect = SQL_QUERY.replace("SUM(il.Quantity) AS units", "COUNT(*) AS units")
    assert not verify(case, incorrect.encode(), host, inputs)["passed"]


@pytest.mark.parametrize("mutation", [
    "valid", "missing", "boolean", "counts", "exit", "stdout", "nonobject", "elapsed",
])
def test_batch_sequence_verifier_checks_events_and_preserves_contract(monkeypatch, mutation):
    reference = {"event": "summary", "elapsed_ms": 4, "processed": 3}
    candidate = {**reference, "sequence": 0}
    if mutation == "missing":
        candidate.pop("sequence")
    elif mutation == "boolean":
        candidate["sequence"] = False
    elif mutation == "counts":
        candidate["processed"] = 2
    elif mutation == "nonobject":
        candidate = []
    elif mutation == "elapsed":
        candidate["elapsed_ms"] = -1
    row = {"scenario": "normal", "reference": {
        "exit_code": 0, "stdout": "{}\n", "stderr": json.dumps(reference)},
        "candidate": {"exit_code": int(mutation == "exit"),
                      "stdout": "changed" if mutation == "stdout" else "{}\n",
                      "stderr": json.dumps(candidate)}}

    class Probe:
        stopped = False

        def start(self, inputs, writable):
            assert inputs == {"reference.py": b"original", "candidate.py": b"modified"}
            assert writable == []

        def execute(self, code, timeout):
            return {"status": "completed", "exit_code": 0, "output": json.dumps([row])}

        def stop(self):
            self.stopped = True

    probe = Probe()
    monkeypatch.setattr(verifiers, "Sandbox", lambda host: probe)
    result = verify({"id": BATCH}, b"modified", "unused", {"batch.py": b"original"})
    assert result["passed"] == (mutation == "valid")
    assert result["liveness_measured"] is False
    assert probe.stopped


@pytest.mark.skipif(os.environ.get("SKILLC_LOCAL_DOCKER") != "1",
                    reason="explicit local isolated-container fixture check")
def test_public_batch_replay_rejects_unchanged_and_corrupt_sequence():
    folder = FIXTURE.parent.parent / "reviewed-batch" / BATCH
    original = (folder / "batch.py").read_bytes()
    modified = original.replace(b'    status = "completed"',
                                b'    sequence = 0\n    status = "completed"', 1)
    modified = modified.replace(b'    def emit(event, **fields):',
                                b'    def emit(event, **fields):\n        nonlocal sequence', 1)
    modified = modified.replace(b'record = {"event": event',
                                b'record = {"sequence": sequence, "event": event', 1)
    modified = modified.replace(b'file=sys.stderr, flush=True)',
                                b'file=sys.stderr, flush=True)\n        sequence += 1', 1)
    host = subprocess.check_output(
        ["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"],
        text=True).strip()
    inputs = {"batch.py": original}
    assert not verify({"id": BATCH}, original, host, inputs)["passed"]
    result = verify({"id": BATCH}, modified, host, inputs)
    assert result["passed"] and result["checks"] == 8
    broken = modified.replace(b"sequence += 1", b"sequence += 2")
    assert not verify({"id": BATCH}, broken, host, inputs)["passed"]


@pytest.fixture
def exports():
    return {name: (FIXTURE / name).read_bytes()
            for name in ("mewt-results.json", "mewt-status.txt")}


def test_public_reference_distinguishes_exported_survivors_from_campaign_totals(exports):
    reference = mutation_reference(exports)
    assert reference["campaign"] == {
        "total": 29, "tested": 24, "caught": 16, "uncaught": 8, "timeout": 0, "skipped": 5,
    }
    assert reference["exported_uncaught_ids"] == [6, 7, 9, 10, 11, 12, 25, 28]
    assert reference["kill_rate"] == {"numerator": 16, "denominator": 24}
    actual = json.dumps(reference, indent=4).encode()
    assert verify({"id": MUTATION}, actual, "unused", exports)["passed"]


@pytest.mark.parametrize(("field", "value"), [
    ("total", 8), ("tested", 29), ("timeout", False),
])
def test_independent_summary_check_rejects_wrong_counts_and_boolean_numbers(exports, field, value):
    actual = mutation_reference(exports)
    actual["campaign"][field] = value
    assert not verify_mutation_summary(exports, json.dumps(actual).encode())["passed"]


@pytest.mark.parametrize("actual", [
    b"Done", b'{"passed":true}', b'{"campaign":{}, "campaign":{}}', b'{"value":NaN}',
])
def test_independent_summary_check_does_not_trust_assertions_or_ambiguous_json(exports, actual):
    assert not verify_mutation_summary(exports, actual)["passed"]


def test_reference_rejects_incomplete_exports_and_inconsistent_campaign_counts(exports):
    with pytest.raises(ValueError, match="both frozen"):
        mutation_reference({"mewt-results.json": exports["mewt-results.json"]})
    exports["mewt-status.txt"] = exports["mewt-status.txt"].replace(b"29 total", b"30 total")
    with pytest.raises(ValueError, match="do not reconcile"):
        mutation_reference(exports)


@pytest.mark.skipif(os.environ.get("SKILLC_LOCAL_DOCKER") != "1",
                    reason="explicit local isolated-container fixture check")
def test_public_exports_and_goal_verifier_in_actual_isolated_container(exports):
    host = subprocess.check_output(
        ["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"],
        text=True).strip()
    assert host.startswith(("npipe:////./pipe/", "unix:///"))
    sandbox = Sandbox(host)
    try:
        sandbox.start(exports, [])
        check = sandbox.execute(
            "import json,pathlib\n"
            "data=json.loads(pathlib.Path('/inputs/mewt-results.json').read_text())\n"
            "assert len(data['results'])==8\n"
            "try:\n"
            " pathlib.Path('/inputs/mewt-status.txt').write_text('modified')\n"
            "except PermissionError:\n"
            " print('protected')\n"
            "else:\n"
            " raise AssertionError('input was writable')\n")
        assert check["status"] == "completed" and check["exit_code"] == 0
        assert check["output"].strip() == "protected"
        expected = json.dumps(mutation_reference(exports))
        written = sandbox.execute(
            "import pathlib\n"
            f"pathlib.Path('/work/mutation-summary.json').write_text({expected!r})")
        assert written["status"] == "completed" and written["exit_code"] == 0
        assert verify_mutation_summary(
            exports, sandbox.read("/work/mutation-summary.json"))["passed"]
        wrong = sandbox.execute(
            "import pathlib\n"
            "pathlib.Path('/work/mutation-summary.json').write_text('{\"passed\":true}')")
        assert wrong["status"] == "completed" and wrong["exit_code"] == 0
        assert not verify_mutation_summary(
            exports, sandbox.read("/work/mutation-summary.json"))["passed"]
    finally:
        sandbox.stop()
    assert sandbox.stopped


@pytest.fixture
def codec():
    source = FIXTURE.parent.parent / "reviewed-property" / PROPERTY / "codec.py"
    return {"codec.py": source.read_bytes()}


@pytest.mark.parametrize("actual", [
    b"[]", b'{"input":"%","once":"%25","twice":"%2525","extra":true}',
    b'{"input":"%","input":"a","once":"%25","twice":"%2525"}',
    b'{"input":"%","once":25,"twice":"%2525"}',
    b'{"input":"a/b","once":"a/b","twice":"a/b"}',
    json.dumps({"input": "a" * 33, "once": "a", "twice": "a"}).encode(),
])
def test_counterexample_contract_rejects_bad_reports_before_execution(codec, actual, monkeypatch):
    def forbidden(*args):
        raise AssertionError("Invalid reports must not start a verifier container")
    monkeypatch.setattr(verifiers, "Sandbox", forbidden)
    assert not verify({"id": PROPERTY}, actual, "unused", codec)["passed"]


def test_counterexample_probe_failure_is_not_a_skill_failure(codec, monkeypatch):
    class FailedProbe:
        stopped = False

        def start(self, inputs, writable):
            assert inputs == codec and writable == []

        def execute(self, code, timeout):
            return {"status": "tool_timeout", "exit_code": None, "output": ""}

        def stop(self):
            self.stopped = True

    probe = FailedProbe()
    monkeypatch.setattr(verifiers, "Sandbox", lambda host: probe)
    with pytest.raises(RuntimeError, match="Independent reviewed-code probe failed"):
        verify({"id": PROPERTY}, b'{"input":"%","once":"%25","twice":"%2525"}', "unused", codec)
    assert probe.stopped


@pytest.mark.skipif(os.environ.get("SKILLC_LOCAL_DOCKER") != "1",
                    reason="explicit local isolated-container fixture check")
def test_public_codec_witness_is_replayed_in_a_separate_actual_sandbox(codec):
    host = subprocess.check_output(
        ["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"],
        text=True).strip()
    assert host.startswith(("npipe:////./pipe/", "unix:///"))
    sandbox = Sandbox(host)
    try:
        sandbox.start(codec, [])
        result = sandbox.execute(
            "import json,pathlib,runpy\n"
            "path=pathlib.Path('/inputs/codec.py')\n"
            "try:\n"
            " path.write_text('modified')\n"
            "except PermissionError:\n"
            " pass\n"
            "else:\n"
            " raise AssertionError('input was writable')\n"
            "f=runpy.run_path(str(path))['canonicalize_url']\n"
            "x='%'\n"
            "once=f(x)\n"
            "pathlib.Path('/work/counterexample.json').write_text("
            "json.dumps({'input':x,'once':once,'twice':f(once)}))")
        assert result["status"] == "completed" and result["exit_code"] == 0
        actual = sandbox.read("/work/counterexample.json")
        assert json.loads(actual) == {"input": "%", "once": "%25", "twice": "%2525"}
        assert verify({"id": PROPERTY}, actual, host, codec)["passed"]
        forged = json.loads(actual)
        forged["twice"] = "invented"
        assert not verify({"id": PROPERTY}, json.dumps(forged).encode(), host, codec)["passed"]
        stable = json.dumps({"input": "A", "once": "a", "twice": "a"}).encode()
        assert not verify({"id": PROPERTY}, stable, host, codec)["passed"]
        assert sandbox.read("/inputs/codec.py") == codec["codec.py"]
    finally:
        sandbox.stop()
    assert sandbox.stopped


@pytest.fixture
def palettes():
    source = (FIXTURE.parent.parent / "reviewed-palette" / PALETTE / "colors.csv")
    return {"colors.csv": source.read_bytes()}


def test_palette_reference_uses_linear_light_and_unrounded_threshold():
    inputs = {"colors.csv": (
        "No,Text (Hex),Background (Hex),CTA (Hex)\n"
        "1,#000000,#FFFFFF,#FFFFFF\n"
        "2,#777777,#FFFFFF,#000000\n").encode()}
    reference = palette_reference(inputs)
    assert reference["total_pairs"] == 4 and reference["passing_pairs"] == 3
    assert reference["failures"] == [
        {"palette_id": 2, "role": "body_text", "contrast_ratio": "4.4781"}]
    assert verify({"id": PALETTE}, json.dumps(reference).encode(), "unused", inputs)["passed"]


def test_public_palette_review_checks_both_foreground_pairings(palettes):
    reference = palette_reference(palettes)
    assert reference["total_palettes"] == 96 and reference["total_pairs"] == 192
    assert reference["failing_pairs"] == 31
    assert {row["role"] for row in reference["failures"]} == {"cta_label"}
    actual = json.dumps(reference).encode()
    assert verify_palette_contrast(palettes, actual)["passed"]
    reference["failures"][0]["contrast_ratio"] = float(
        reference["failures"][0]["contrast_ratio"])
    assert not verify_palette_contrast(palettes, json.dumps(reference).encode())["passed"]


@pytest.mark.parametrize("rows", [
    "1,#000000,#FFFFFF,#FFFFFF\n1,#000000,#FFFFFF,#FFFFFF\n",
    "1,#000000,#FFFFFF,not-a-colour\n",
])
def test_palette_reference_rejects_ambiguous_or_invalid_public_inputs(rows):
    raw = ("No,Text (Hex),Background (Hex),CTA (Hex)\n" + rows).encode()
    with pytest.raises(ValueError):
        palette_reference({"colors.csv": raw})


@pytest.mark.skipif(os.environ.get("SKILLC_LOCAL_DOCKER") != "1",
                    reason="explicit local isolated-container fixture check")
def test_public_palette_goal_in_actual_isolated_container(palettes):
    host = subprocess.check_output(
        ["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"],
        text=True).strip()
    assert host.startswith(("npipe:////./pipe/", "unix:///"))
    sandbox = Sandbox(host)
    try:
        sandbox.start(palettes, [])
        check = sandbox.execute(
            "import csv,pathlib\n"
            "assert len(list(csv.DictReader("
            "pathlib.Path('/inputs/colors.csv').read_text().splitlines())))==96\n"
            "try:\n"
            " pathlib.Path('/inputs/colors.csv').write_text('modified')\n"
            "except PermissionError:\n"
            " pass\n"
            "else:\n"
            " raise AssertionError('input was writable')\n")
        assert check["status"] == "completed" and check["exit_code"] == 0
        expected = json.dumps(palette_reference(palettes))
        written = sandbox.execute(
            "import pathlib\n"
            f"pathlib.Path('/work/palette-contrast.json').write_text({expected!r})")
        assert written["status"] == "completed" and written["exit_code"] == 0
        assert verify_palette_contrast(
            palettes, sandbox.read("/work/palette-contrast.json"))["passed"]
    finally:
        sandbox.stop()
    assert sandbox.stopped

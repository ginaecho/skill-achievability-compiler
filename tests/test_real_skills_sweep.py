import csv
import io
import os
import subprocess
from pathlib import Path

import pytest

from scripts.real_skills_pilot import verify
from scripts.real_skills_runtime import Sandbox
from scripts.real_skills_sweep import (
    INPUT_FIELDS, OUTPUT_FIELDS, SWEEP, sweep_reference, verify_sweep_summary,
)


@pytest.fixture
def inputs():
    path = (Path(__file__).resolve().parents[1] / "runs" / "20261106_real_skills"
            / "reviewed-sweep" / SWEEP / "summary_review.csv")
    return {"summary_review.csv": path.read_bytes()}


def test_sweep_ranks_actual_public_rows_and_retains_invalid_counts(inputs):
    actual = sweep_reference(inputs)
    rows = list(csv.DictReader(io.StringIO(actual.decode())))
    assert [row["config_id"] for row in rows] == [
        "review_1_8", "review_1_4", "review_15_8", "review_05_8", "review_05_2",
        "review_05_4", "review_15_2", "review_15_4", "review_1_2"]
    assert [row["success_rate"] for row in rows[:5]] == [
        "0.800000", "0.800000", "0.700000", "0.600000", "0.300000"]
    result = verify({"id": SWEEP}, actual, "unused", inputs)
    assert result["passed"] and result["expected_rows"] == 9
    assert result["count_status_totals"] == {
        "valid": 5, "zero_denominator": 1, "invalid_counts": 2, "missing_counts": 1}
    assert result["best_config_id"] == "review_1_8"


@pytest.mark.parametrize("change", ["rate", "status", "drop", "order", "original", "duplicate", "header"])
def test_sweep_rejects_wrong_artifacts(inputs, change):
    rows = list(csv.DictReader(io.StringIO(sweep_reference(inputs).decode())))
    if change == "rate":
        rows[0]["success_rate"] = "0.8"
    elif change == "status":
        rows[-1]["count_status"] = "valid"
    elif change == "drop":
        rows.pop()
    elif change == "order":
        rows[0], rows[1] = rows[1], rows[0]
    elif change == "original":
        rows[0]["temperature"] = "1"
    elif change == "duplicate":
        rows[-1] = dict(rows[0])
    stream = io.StringIO(newline="")
    fields = (*OUTPUT_FIELDS[:-1], "wrong") if change == "header" else OUTPUT_FIELDS
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    assert not verify_sweep_summary(inputs, stream.getvalue().encode())["passed"]


def test_sweep_keeps_exact_ratio_order_missing_metric_and_rounds_half_up():
    raw = (",".join(INPUT_FIELDS) + "\n"
           "round,1,1,128,1,\n"
           "zero,1,1,10,0,2\n"
           "low,1,1,10000000,3333333,1\n"
           "high,1,1,10000000,3333334,9\n"
           "missing,1,1,,1,0\n"
           "decimal,1,1,1.5,1,0\n").encode()
    result = sweep_reference({"summary_review.csv": raw})
    rows = list(csv.DictReader(io.StringIO(result.decode())))
    assert [row["config_id"] for row in rows] == ["high", "low", "round", "zero", "decimal", "missing"]
    assert rows[2]["success_rate"] == "0.007813"
    assert rows[3]["success_rate"] == "0.000000" and rows[3]["count_status"] == "valid"
    assert rows[4]["count_status"] == "invalid_counts" and rows[5]["count_status"] == "missing_counts"


@pytest.mark.parametrize("raw", [b"\xff", b"x" * 32769, b"config_id\na\n", b'"unterminated'],
                         ids=["invalid_utf8", "too_large", "wrong_header", "broken_quotes"])
def test_sweep_rejects_malformed_or_oversized_artifacts(inputs, raw):
    assert not verify_sweep_summary(inputs, raw)["passed"]


@pytest.mark.parametrize("inputs", [{}, {"other.csv": b""}, {"summary_review.csv": b"wrong\n"}])
def test_sweep_refuses_unreviewed_input_layout(inputs):
    with pytest.raises(ValueError):
        sweep_reference(inputs)


@pytest.mark.skipif(os.environ.get("SKILLC_LOCAL_DOCKER") != "1",
                    reason="explicit local isolated-container fixture check")
def test_sweep_verifies_real_sandbox_artifact_and_preserves_input(inputs):
    host = subprocess.check_output(
        ["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"], text=True).strip()
    sandbox = Sandbox(host)
    try:
        sandbox.start(inputs, [])
        actual = sweep_reference(inputs)
        result = sandbox.execute(
            "from pathlib import Path\n"
            f"Path('/work/sweep_summary.csv').write_bytes({actual!r})\n")
        assert result["status"] == "completed" and result["exit_code"] == 0
        assert verify_sweep_summary(inputs, sandbox.read("/work/sweep_summary.csv"))["passed"]
        result = sandbox.execute(
            "from pathlib import Path\n"
            "p=Path('/work/sweep_summary.csv')\n"
            "p.write_bytes(p.read_bytes().replace(b'0.800000', b'0.500000', 1))\n")
        assert result["status"] == "completed" and result["exit_code"] == 0
        assert not verify_sweep_summary(inputs, sandbox.read("/work/sweep_summary.csv"))["passed"]
        assert sandbox.read("/inputs/summary_review.csv") == inputs["summary_review.csv"]
    finally:
        sandbox.stop()

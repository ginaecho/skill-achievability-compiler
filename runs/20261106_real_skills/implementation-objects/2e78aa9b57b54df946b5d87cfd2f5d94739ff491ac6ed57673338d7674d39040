"""Independent checks for one public configuration-summary CSV artifact."""
import csv
import hashlib
import io
import re
from collections import Counter
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from fractions import Fraction

SWEEP = "NVIDIA__skills__bionemo-complexa-sweep"
INPUT_FIELDS = ("config_id", "temperature", "replicas", "n_designs", "n_passed", "mean_i_pae")
OUTPUT_FIELDS = (*INPUT_FIELDS, "success_rate", "count_status")


def _read(raw: bytes, fields: tuple[str, ...]) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
    if reader.fieldnames != list(fields):
        raise ValueError("CSV columns differ from the declared ordered field list")
    rows = list(reader)
    if any(set(row) != set(fields) or any(value is None for value in row.values()) for row in rows):
        raise ValueError("CSV row width differs from its header")
    ids = [row["config_id"] for row in rows]
    if any(not identifier for identifier in ids) or len(set(ids)) != len(ids):
        raise ValueError("CSV configuration identifiers must be nonempty and unique")
    return rows


def _counts(row: dict[str, str]) -> tuple[str, Fraction | None]:
    designs, passed = row["n_designs"], row["n_passed"]
    if "" in (designs, passed):
        return "missing_counts", None
    if not all(re.fullmatch(r"-?[0-9]+", value) for value in (designs, passed)):
        return "invalid_counts", None
    denominator, numerator = int(designs), int(passed)
    if denominator < 0 or numerator < 0 or numerator > denominator:
        return "invalid_counts", None
    if denominator == 0:
        return "zero_denominator", None
    return "valid", Fraction(numerator, denominator)


def sweep_reference(inputs: dict[str, bytes]) -> bytes:
    if set(inputs) != {"summary_review.csv"}:
        raise ValueError("Sweep analysis requires only the reviewed public summary CSV")
    rows = _read(inputs["summary_review.csv"], INPUT_FIELDS)
    ranked = []
    for row in rows:
        status, rate = _counts(row)
        try:
            pae = Decimal(row["mean_i_pae"]) if row["mean_i_pae"] else Decimal("Infinity")
        except InvalidOperation as error:
            raise ValueError("Public input has a nonnumeric interface-PAE value") from error
        if row["mean_i_pae"] and (not pae.is_finite() or pae < 0):
            raise ValueError("Public input has an invalid interface-PAE value")
        formatted = ""
        if rate is not None:
            value = Decimal(rate.numerator) / Decimal(rate.denominator)
            formatted = str(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))
        output = {**row, "success_rate": formatted, "count_status": status}
        key = ((0, -rate, pae, row["config_id"]) if rate is not None else
               (1, Fraction(0), Decimal(0), row["config_id"]))
        ranked.append((key, output))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(row for _, row in sorted(ranked, key=lambda item: item[0]))
    return stream.getvalue().encode("utf-8")


def verify_sweep_summary(inputs: dict[str, bytes], actual: bytes) -> dict:
    expected = _read(sweep_reference(inputs), OUTPUT_FIELDS)
    kind = "public_sweep_summary_csv_ranking"
    if len(actual) > 32768:
        return {"passed": False, "kind": kind, "error": "CSV artifact exceeds 32768 bytes"}
    try:
        observed = _read(actual, OUTPUT_FIELDS)
    except (UnicodeError, ValueError, csv.Error) as error:
        return {"passed": False, "kind": kind, "error": str(error)}
    statuses = dict(Counter(row["count_status"] for row in expected))
    return {"passed": observed == expected, "kind": kind,
            "actual_sha256": hashlib.sha256(actual).hexdigest(),
            "expected_rows": len(expected), "count_status_totals": statuses,
            "best_config_id": next((row["config_id"] for row in expected
                                    if row["count_status"] == "valid"), None),
            "measured_gpu_results": False}

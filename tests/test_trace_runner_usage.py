import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "demo" / "skillc-architecture-app" / "trace_runner.py"
SPEC = importlib.util.spec_from_file_location("trace_runner", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_usage_totals_count_cached_input_once():
    blocks = [
        {"input_tokens": 900, "output_tokens": 300, "cache_read_input_tokens": 100},
        {"input_tokens": 50, "output_tokens": 20},
    ]

    totals = MODULE.usage_totals(blocks)

    assert totals == {"calls": 2, "input_tokens": 1050, "cached_input_tokens": 100,
                      "output_tokens": 320, "total_tokens": 1370}


def test_usage_totals_of_no_calls_are_zero():
    assert MODULE.usage_totals([])["total_tokens"] == 0

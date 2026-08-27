from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "benchmark_token_economics.py"
SPEC = importlib.util.spec_from_file_location("token_benchmark", SCRIPT)
assert SPEC and SPEC.loader
benchmark = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)


def test_normalize_usage_keeps_subcategories_non_additive():
    usage = benchmark.normalize_usage({
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
        "prompt_tokens_details": {
            "cached_tokens": 80,
            "cache_write_tokens": 10,
        },
        "completion_tokens_details": {"reasoning_tokens": 30},
    })
    assert usage == {
        "input": 100,
        "output": 50,
        "total": 150,
        "cached_input": 80,
        "cache_write_input": 10,
        "reasoning_output": 30,
    }


def test_validate_endpoint_rejects_non_azure_or_project_endpoint():
    assert benchmark.validate_endpoint(
        "https://example.openai.azure.com/openai/v1/"
    ) == "https://example.openai.azure.com/openai/v1"
    with pytest.raises(ValueError):
        benchmark.validate_endpoint("http://example.openai.azure.com/openai/v1")
    with pytest.raises(ValueError):
        benchmark.validate_endpoint("https://attacker.example/openai/v1")
    with pytest.raises(ValueError):
        benchmark.validate_endpoint(
            "https://example.services.ai.azure.com/api/projects/demo"
        )


def test_summarize_measures_a_y_d_v_and_break_even():
    cases = [
        {
            "y": 0,
            "d": 0,
            "a_usage": {"input": 80, "output": 20, "total": 100},
            "v_usage": None,
        },
        {
            "y": 1,
            "d": 1,
            "a_usage": {"input": 90, "output": 30, "total": 120},
            "v_usage": {"input": 100, "output": 100, "total": 200},
        },
        {
            "y": 1,
            "d": 0,
            "a_usage": {"input": 70, "output": 10, "total": 80},
            "v_usage": {"input": 100, "output": 300, "total": 400},
        },
    ]
    summary = benchmark.summarize(cases)
    assert summary["y_impossible"] == 2
    assert summary["d_detected_impossible"] == 1
    assert summary["d_sensitivity"] == 0.5
    assert summary["a_usage"]["total"] == 300
    assert summary["v_usage_total"] == 600
    assert summary["avoided_tokens_at_k1"] == 200
    assert summary["net_tokens_at_k1"] == -100
    assert summary["break_even_reuse_k"] == 1.5

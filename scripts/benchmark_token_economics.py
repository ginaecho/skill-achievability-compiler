#!/usr/bin/env python3
"""Measure a bounded A/Y/D/V token-economics pilot on the labelled corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from skillc import check  # noqa: E402
from skillc.frontend.llm import SYSTEM, _extract_json_object  # noqa: E402
from skillc.pack import PackError  # noqa: E402

DEFAULT_ENDPOINT = "https://foundary-tzuc06.openai.azure.com/openai/v1"
DEFAULT_MODEL = "gpt-5.4"
RESPONSE_HEADER_ALLOWLIST = {
    "apim-request-id",
    "retry-after",
    "retry-after-ms",
    "x-ratelimit-remaining-requests",
    "x-ratelimit-remaining-tokens",
}
RUNTIME_SYSTEM = """You are executing an agent skill in a bounded simulation.
Use only capabilities explicitly granted by the skill. Do not invent tools,
credentials, approvals, facts, or successful effects. Attempt the workflow
once. Stop as soon as the goal is achieved or you can establish that it is
blocked or impossible. Return JSON with status (achieved, blocked, impossible,
or unknown), actions_attempted, and reason."""


def azure_cli_token() -> str:
    executable = shutil.which("az.cmd") or shutil.which("az")
    if not executable:
        raise RuntimeError("Azure CLI is unavailable")
    result = subprocess.run(
        [
            executable,
            "account",
            "get-access-token",
            "--resource",
            "https://ai.azure.com",
            "--query",
            "accessToken",
            "--output",
            "tsv",
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    token = result.stdout.strip()
    if result.returncode or not token:
        raise RuntimeError(result.stderr.strip() or "Azure CLI returned no token")
    return token


def _safe_headers(headers: Any) -> dict[str, str]:
    return {
        key.lower(): value
        for key, value in headers.items()
        if key.lower() in RESPONSE_HEADER_ALLOWLIST
    }


def validate_endpoint(endpoint: str) -> str:
    parsed = urlparse(endpoint.rstrip("/"))
    host = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or not host.endswith(".openai.azure.com")
        or parsed.path != "/openai/v1"
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "endpoint must be an https Azure OpenAI hostname ending in "
            "/openai/v1, without credentials, query, or fragment"
        )
    return endpoint.rstrip("/")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row) + "\n")
        stream.flush()


def normalize_usage(usage: dict[str, Any] | None) -> dict[str, int] | None:
    if not usage:
        return None
    prompt_details = usage.get("prompt_tokens_details") or {}
    completion_details = usage.get("completion_tokens_details") or {}
    return {
        "input": int(usage.get("prompt_tokens") or 0),
        "output": int(usage.get("completion_tokens") or 0),
        "total": int(usage.get("total_tokens") or 0),
        "cached_input": int(prompt_details.get("cached_tokens") or 0),
        "cache_write_input": int(prompt_details.get("cache_write_tokens") or 0),
        "reasoning_output": int(completion_details.get("reasoning_tokens") or 0),
    }


def call_chat(
    *,
    endpoint: str,
    token: str,
    model: str,
    messages: list[dict[str, str]],
    max_completion_tokens: int,
    phase: str,
    case_id: str,
    ground_truth: str,
    ledger_path: Path,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    payload = {
        "model": model,
        "messages": messages,
        "max_completion_tokens": max_completion_tokens,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        endpoint.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "authorization": "Bearer " + token,
            "content-type": "application/json",
        },
    )
    started = time.perf_counter()
    status = None
    headers: dict[str, str] = {}
    response: dict[str, Any] | None = None
    error = None
    try:
        with urllib.request.urlopen(request, timeout=600) as stream:
            status = stream.status
            headers = _safe_headers(stream.headers)
            body = stream.read().decode("utf-8", errors="replace")
            try:
                response = json.loads(body)
            except json.JSONDecodeError as exc:
                error = f"JSONDecodeError: {exc}; body={body[:1000]}"
    except urllib.error.HTTPError as exc:
        status = exc.code
        headers = _safe_headers(exc.headers)
        body = exc.read().decode("utf-8", errors="replace")
        try:
            response = json.loads(body)
        except json.JSONDecodeError:
            error = body[:1000]
        else:
            error = json.dumps(response.get("error", response))[:1000]
    except (OSError, TimeoutError) as exc:
        error = f"{type(exc).__name__}: {exc}"
    elapsed_ms = (time.perf_counter() - started) * 1000

    choices = response.get("choices", []) if response else []
    choice = choices[0] if choices else {}
    content = choice.get("message", {}).get("content", "")
    row = {
        "phase": phase,
        "case_id": case_id,
        "ground_truth": ground_truth,
        "requested_model": model,
        "resolved_model": response.get("model") if response else None,
        "http_status": status,
        "response_headers": headers,
        "finish_reason": choice.get("finish_reason"),
        "raw_usage": response.get("usage") if response else None,
        "usage": normalize_usage(response.get("usage") if response else None),
        "usage_missing": not bool(response and response.get("usage")),
        "latency_ms": round(elapsed_ms, 3),
        "error": error,
        "output_text": content if isinstance(content, str) else json.dumps(content),
        "request_sha256": hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    append_jsonl(ledger_path, row)
    return row, response


def summarize(case_rows: list[dict[str, Any]]) -> dict[str, Any]:
    measured = [row for row in case_rows if row["a_usage"] is not None]
    impossible = [row for row in measured if row["y"] == 1]
    checked = [row for row in measured if row["d"] is not None]
    detected = [row for row in impossible if row["d"] == 1]
    achievable = [row for row in measured if row["y"] == 0]
    false_refutations = [row for row in achievable if row["d"] == 1]
    a_total = sum(row["a_usage"]["total"] for row in measured)
    a_input = sum(row["a_usage"]["input"] for row in measured)
    a_output = sum(row["a_usage"]["output"] for row in measured)
    v_measured = [row for row in impossible if row["v_usage"] is not None]
    v_total = sum(row["v_usage"]["total"] for row in v_measured)
    avoided_at_k1 = sum(
        row["v_usage"]["total"]
        for row in detected
        if row["v_usage"] is not None
    )
    complete = (
        len(measured) == len(case_rows)
        and len(checked) == len(case_rows)
        and len(v_measured) == len(impossible)
    )
    return {
        "n_cases": len(case_rows),
        "n_a_measured": len(measured),
        "n_checker_measured": len(checked),
        "y_impossible": len(impossible),
        "y_achievable": len(achievable),
        "d_detected_impossible": len(detected),
        "d_false_refutations": len(false_refutations),
        "d_sensitivity": (
            len(detected) / len(impossible)
            if impossible and all(row["d"] is not None for row in impossible)
            else None
        ),
        "a_usage": {"input": a_input, "output": a_output, "total": a_total},
        "v_cases_measured": len(v_measured),
        "v_usage_total": v_total,
        "v_usage_mean": v_total / len(v_measured) if v_measured else None,
        "avoided_tokens_at_k1": (
            avoided_at_k1 if complete else None
        ),
        "net_tokens_at_k1": (
            avoided_at_k1 - a_total if complete else None
        ),
        "break_even_reuse_k": (
            a_total / avoided_at_k1 if complete and avoided_at_k1 else None
        ),
        "scope": (
            "One-trial corpus pilot. V is one bounded simulated runtime call "
            "with an oracle baseline of zero; it is not natural uncapped waste."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--runtime-cap", type=int, default=2048)
    parser.add_argument("--compaction-cap", type=int, default=8000)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    output_dir = args.output_dir or ROOT / "runs" / f"{timestamp}_token_economics_pilot"
    output_dir.mkdir(parents=True, exist_ok=False)
    endpoint = validate_endpoint(args.endpoint)
    corpus = json.loads(
        (ROOT / "src" / "skillc" / "data" / "corpus.json").read_text(
            encoding="utf-8"
        )
    )
    case_ids = [item["id"] for item in corpus]
    impossible_count = sum(item["ground_truth"] == "IMPOSSIBLE" for item in corpus)
    if len(corpus) != 15 or len(set(case_ids)) != 15 or impossible_count != 9:
        raise RuntimeError(
            "pilot requires exactly 15 unique corpus cases with 9 IMPOSSIBLE labels"
        )
    script_bytes = Path(__file__).read_bytes()
    corpus_bytes = (ROOT / "src" / "skillc" / "data" / "corpus.json").read_bytes()
    git_revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    git_status = subprocess.run(
        ["git", "status", "--short"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.splitlines()
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": endpoint,
        "project_endpoint_contacted": False,
        "requested_model": args.model,
        "compaction_cap": args.compaction_cap,
        "runtime_cap": args.runtime_cap,
        "script_sha256": hashlib.sha256(script_bytes).hexdigest(),
        "corpus_sha256": hashlib.sha256(corpus_bytes).hexdigest(),
        "git_revision": git_revision,
        "git_status": git_status,
        "case_ids": case_ids,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    ledger_path = output_dir / "calls.jsonl"
    token = azure_cli_token()
    cases: list[dict[str, Any]] = []

    for item in corpus:
        case_id = item["id"]
        truth = item["ground_truth"]
        user = f"Natural-language skill:\n```\n{item['nl']}\n```\nJSON pack:"
        a_row, _ = call_chat(
            endpoint=endpoint,
            token=token,
            model=args.model,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
            ],
            max_completion_tokens=args.compaction_cap,
            phase="A_compaction",
            case_id=case_id,
            ground_truth=truth,
            ledger_path=ledger_path,
        )

        verdict = None
        pack_digest = None
        checker_ms = None
        parse_error = None
        if a_row["http_status"] == 200 and a_row["output_text"]:
            try:
                pack = _extract_json_object(a_row["output_text"])
                started = time.perf_counter()
                checked = check(pack)
                checker_ms = (time.perf_counter() - started) * 1000
                verdict = checked.to_dict()
                pack_digest = hashlib.sha256(
                    json.dumps(pack, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
            except (PackError, ValueError, KeyError, TypeError) as exc:
                parse_error = f"{type(exc).__name__}: {exc}"

        y = int(truth == "IMPOSSIBLE")
        d = (
            int(verdict["verdict"] == "IMPOSSIBLE")
            if verdict is not None
            else None
        )
        v_row = None
        if y:
            v_row, _ = call_chat(
                endpoint=endpoint,
                token=token,
                model=args.model,
                messages=[
                    {"role": "system", "content": RUNTIME_SYSTEM},
                    {
                        "role": "user",
                        "content": (
                            f"Execute this skill now within the simulation:\n\n"
                            f"{item['nl']}"
                        ),
                    },
                ],
                max_completion_tokens=args.runtime_cap,
                phase="V_runtime",
                case_id=case_id,
                ground_truth=truth,
                ledger_path=ledger_path,
            )

        cases.append(
            {
                "case_id": case_id,
                "category": item["category"],
                "ground_truth": truth,
                "y": y,
                "d": d,
                "checker_verdict": verdict,
                "checker_latency_ms": (
                    round(checker_ms, 3) if checker_ms is not None else None
                ),
                "pack_digest": pack_digest,
                "parse_error": parse_error,
                "a_usage": a_row["usage"],
                "a_latency_ms": a_row["latency_ms"],
                "v_usage": v_row["usage"] if v_row else None,
                "v_latency_ms": v_row["latency_ms"] if v_row else None,
                "v_finish_reason": v_row["finish_reason"] if v_row else None,
            }
        )
        (output_dir / "cases.json").write_text(
            json.dumps(cases, indent=2) + "\n", encoding="utf-8"
        )

    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": endpoint,
        "project_endpoint_contacted": False,
        "model": args.model,
        "compaction_cap": args.compaction_cap,
        "runtime_cap": args.runtime_cap,
        **summarize(cases),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"output_dir": str(output_dir), **summary}, indent=2))
    complete = (
        summary["n_a_measured"] == summary["n_cases"]
        and summary["n_checker_measured"] == summary["n_cases"]
        and summary["v_cases_measured"] == summary["y_impossible"]
    )
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())

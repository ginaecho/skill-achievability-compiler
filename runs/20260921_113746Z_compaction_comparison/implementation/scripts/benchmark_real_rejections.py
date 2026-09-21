#!/usr/bin/env python3
"""Benchmark skillc rejection against bounded ungated execution on real skills."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from scripts.benchmark_semantics import (  # noqa: E402
    World, audit_goal_reachability, holds,
)
from skillc import check  # noqa: E402
from skillc.evaluate import evaluate, refutation_metrics  # noqa: E402
from skillc.frontend.llm import (  # noqa: E402
    DEVELOPER_ABILITIES,
    RUNTIME_ABILITIES_NOTE,
    SYSTEM,
    _extract_json_object,
)
from skillc.pack import PackError, validate_pack  # noqa: E402

DEFAULT_ENDPOINT = "https://foundary-tzuc06.openai.azure.com/openai/v1"
DEFAULT_PROJECT_ENDPOINT = (
    "https://foundary-tzuc06.services.ai.azure.com/api/projects/firstProject"
)
DEFAULT_MODEL = "gpt-5.4"
DEFAULT_CASES = ROOT / "benchmark" / "real_rejection_cases.json"
RESPONSE_HEADER_ALLOWLIST = {
    "apim-request-id",
    "retry-after",
    "retry-after-ms",
    "x-ratelimit-remaining-requests",
    "x-ratelimit-remaining-tokens",
}
RUNTIME_SYSTEM = """You are attempting an agent skill without a static checker.
Execute the workflow one capability at a time. You may request only capability
names listed as available. Never claim an effect unless the harness reports that
the attempt succeeded. Return one JSON object:
{"status":"attempt","capability":"name","reason":"why this is next"}
or
{"status":"achieved|blocked|failed","capability":null,"reason":"why"}.
Stop as blocked when no available capability can make progress. Do not invent
tools, credentials, approvals, files, network access, or successful effects."""


def validate_endpoint(endpoint: str) -> str:
    """Validate and normalize an Azure OpenAI inference endpoint."""
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


def azure_token() -> str:
    """Return an API key or Azure CLI bearer token without persisting it."""
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    if api_key:
        return api_key
    executable = shutil.which("az.cmd") or shutil.which("az")
    if not executable:
        raise RuntimeError(
            "set AZURE_OPENAI_API_KEY or install and sign in with Azure CLI"
        )
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


def normalize_usage(usage: dict[str, Any] | None) -> dict[str, int] | None:
    """Normalize provider token accounting without double-counting details."""
    if not usage:
        return None
    prompt_details = usage.get("prompt_tokens_details") or {}
    completion_details = usage.get("completion_tokens_details") or {}
    return {
        "input": int(usage.get("prompt_tokens") or 0),
        "output": int(usage.get("completion_tokens") or 0),
        "total": int(usage.get("total_tokens") or 0),
        "cached_input": int(prompt_details.get("cached_tokens") or 0),
        "reasoning_output": int(completion_details.get("reasoning_tokens") or 0),
    }


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    """Append and flush one evidence row."""
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row) + "\n")
        stream.flush()


def call_json(
    *,
    endpoint: str,
    credential: str,
    use_api_key: bool,
    model: str,
    messages: list[dict[str, str]],
    max_completion_tokens: int,
    ledger_path: Path,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Call Azure OpenAI Chat Completions and record complete safe evidence."""
    payload = {
        "model": model,
        "messages": messages,
        "max_completion_tokens": max_completion_tokens,
        "response_format": {"type": "json_object"},
    }
    headers = {"content-type": "application/json"}
    if use_api_key:
        headers["api-key"] = credential
    else:
        headers["authorization"] = "Bearer " + credential
    request = urllib.request.Request(
        endpoint + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers=headers,
    )
    started = time.perf_counter()
    status = None
    response_headers: dict[str, str] = {}
    response: dict[str, Any] | None = None
    error = None
    try:
        with urllib.request.urlopen(request, timeout=600) as stream:
            status = stream.status
            response_headers = {
                key.lower(): value
                for key, value in stream.headers.items()
                if key.lower() in RESPONSE_HEADER_ALLOWLIST
            }
            response = json.loads(stream.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        status = exc.code
        response_headers = {
            key.lower(): value
            for key, value in exc.headers.items()
            if key.lower() in RESPONSE_HEADER_ALLOWLIST
        }
        error = exc.read().decode("utf-8", errors="replace")[:2000]
    except (json.JSONDecodeError, OSError, TimeoutError) as exc:
        error = f"{type(exc).__name__}: {exc}"
    elapsed_ms = (time.perf_counter() - started) * 1000
    choices = response.get("choices", []) if response else []
    choice = choices[0] if choices else {}
    content = choice.get("message", {}).get("content", "")
    row = {
        **metadata,
        "requested_model": model,
        "resolved_model": response.get("model") if response else None,
        "http_status": status,
        "response_headers": response_headers,
        "finish_reason": choice.get("finish_reason"),
        "usage": normalize_usage(response.get("usage") if response else None),
        "latency_ms": round(elapsed_ms, 3),
        "error": error,
        "output_text": content if isinstance(content, str) else json.dumps(content),
        "request_sha256": hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    append_jsonl(ledger_path, row)
    if status != 200 or error:
        raise RuntimeError(
            f"Azure OpenAI call failed with status {status}: {error}"
        )
    if row["usage"] is None:
        raise RuntimeError("Azure OpenAI response omitted token usage")
    return row


def load_cases(path: Path) -> list[dict[str, Any]]:
    """Load benchmark cases and verify pinned local evidence."""
    cases = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise ValueError("case manifest must be a non-empty JSON array")
    seen: set[str] = set()
    for case in cases:
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise ValueError(f"invalid or duplicate case id: {case_id!r}")
        seen.add(case_id)
        for field in (
            "source_path",
            "license_path",
            "source_url",
            "source_commit",
            "license",
            "preferred_restricted_capability",
            "restriction",
        ):
            if not isinstance(case.get(field), str) or not case[field]:
                raise ValueError(f"{case_id}: missing {field}")
        source = ROOT / case["source_path"]
        license_path = ROOT / case["license_path"]
        if not source.is_file() or not license_path.is_file():
            raise FileNotFoundError(f"{case_id}: source or license evidence missing")
        case["source_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        case["license_sha256"] = hashlib.sha256(
            license_path.read_bytes()
        ).hexdigest()
    return cases


def compact_case(
    *,
    case: dict[str, Any],
    endpoint: str,
    credential: str,
    use_api_key: bool,
    model: str,
    attempts: int,
    ledger_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Compact one source with bounded schema retries."""
    source = (ROOT / case["source_path"]).read_text(encoding="utf-8")
    system = SYSTEM + RUNTIME_ABILITIES_NOTE.format(
        abilities="; ".join(DEVELOPER_ABILITIES)
    )
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": f"Natural-language skill:\n```\n{source}\n```\nJSON pack:",
        },
    ]
    rows = []
    failures = []
    for attempt in range(1, attempts + 1):
        row = call_json(
            endpoint=endpoint,
            credential=credential,
            use_api_key=use_api_key,
            model=model,
            messages=messages,
            max_completion_tokens=8000,
            ledger_path=ledger_path,
            metadata={
                "phase": "compaction",
                "case_id": case["id"],
                "attempt": attempt,
            },
        )
        rows.append(row)
        try:
            pack = _extract_json_object(row["output_text"])
            validate_pack(pack)
            return pack, rows
        except (PackError, ValueError, KeyError, TypeError) as exc:
            failures.append(f"attempt {attempt}: {type(exc).__name__}: {exc}")
    raise RuntimeError(
        f"{case['id']}: schema gate rejected all attempts: {failures}"
    )


def goal_atoms(formula: Any) -> set[str]:
    """Collect predicate atoms from a goal formula."""
    if isinstance(formula, str):
        return {formula}
    if isinstance(formula, dict):
        atoms: set[str] = set()
        for key in ("and", "or"):
            for item in formula.get(key, []):
                atoms.update(goal_atoms(item))
        if "not" in formula:
            atoms.update(goal_atoms(formula["not"]))
        return atoms
    return set()


def select_restricted_capability(
    pack: dict[str, Any], preferred: str
) -> str:
    """Select the configured capability or a goal-establishing fallback."""
    capabilities = pack["capabilities"]
    if preferred in capabilities:
        return preferred
    atoms = goal_atoms(pack["goal"])
    candidates = [
        name
        for name, capability in capabilities.items()
        if atoms.intersection(capability.get("add", []))
    ]
    if not candidates:
        raise ValueError(
            f"preferred capability {preferred!r} absent and no goal establisher found"
        )
    return candidates[-1]


def restrict_pack(
    pack: dict[str, Any], capability: str
) -> dict[str, Any]:
    """Represent a target runtime that does not grant one invoked capability."""
    restricted = copy.deepcopy(pack)
    if capability not in restricted["capabilities"]:
        raise KeyError(f"capability not declared: {capability}")
    del restricted["capabilities"][capability]
    validate_pack(restricted)
    return restricted


def goal_satisfied(formula: Any, true_preds: set[str],
                   values: dict[str, int] | None = None) -> bool:
    """Evaluate the declared goal; unsupported/unbound expressions are errors."""
    return holds(formula, true_preds, {} if values is None else values)


def run_ungated_trial(
    *,
    case: dict[str, Any],
    pack: dict[str, Any],
    restricted_capability: str,
    endpoint: str,
    credential: str,
    use_api_key: bool,
    model: str,
    trial: int,
    max_turns: int,
    ledger_path: Path,
) -> dict[str, Any]:
    """Attempt a real skill without skillc using a harmless capability simulator."""
    source = (ROOT / case["source_path"]).read_text(encoding="utf-8")
    available = {
        name: value
        for name, value in pack["capabilities"].items()
        if name != restricted_capability
    }
    messages = [
        {"role": "system", "content": RUNTIME_SYSTEM},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "task_source": source,
                    "available_capabilities": sorted(available),
                    "goal": pack["goal"],
                    "instruction": (
                        "Attempt the task. Request one available capability per "
                        "turn. The harness will report its effects."
                    ),
                }
            ),
        },
    ]
    world = World.initial(pack)
    initial = world.snapshot()
    rows = []
    attempted = []
    trace = []
    outcome = "turn_limit"
    reason = f"maximum {max_turns} turns reached"
    for turn in range(1, max_turns + 1):
        if goal_satisfied(pack["goal"], world.predicates, world.values):
            outcome = "achieved"
            reason = "initial runtime state satisfies the formal goal"
            break
        row = call_json(
            endpoint=endpoint,
            credential=credential,
            use_api_key=use_api_key,
            model=model,
            messages=messages,
            max_completion_tokens=512,
            ledger_path=ledger_path,
            metadata={
                "phase": "ungated_runtime",
                "case_id": case["id"],
                "trial": trial,
                "turn": turn,
            },
        )
        rows.append(row)
        try:
            decision = json.loads(row["output_text"])
        except json.JSONDecodeError as exc:
            outcome = "invalid_response"
            reason = str(exc)
            break
        if not isinstance(decision, dict):
            outcome = "invalid_response"
            reason = "runtime response must be a JSON object"
            break
        status = decision.get("status")
        capability = decision.get("capability")
        reason = str(decision.get("reason") or "")
        messages.append({"role": "assistant", "content": row["output_text"]})
        if status != "attempt":
            outcome = str(status or "invalid_response")
            if outcome not in {"achieved", "blocked", "failed"}:
                outcome = "invalid_response"
            if outcome == "achieved" and not goal_satisfied(
                pack["goal"], world.predicates, world.values
            ):
                outcome = "false_success"
            break
        if not isinstance(capability, str):
            outcome = "invalid_response"
            reason = "attempt response omitted a capability name"
            break
        attempted.append(capability)
        spec = available.get(capability)
        if spec is None:
            feedback = {
                "capability": capability,
                "success": False,
                "error": "capability_unavailable",
                **world.snapshot(),
            }
        else:
            successor, error = world.transition(spec)
            if successor is not None:
                world = successor
            feedback = {
                "capability": capability,
                "success": error is None,
                "error": error,
                **world.snapshot(),
                "goal_satisfied": goal_satisfied(
                    pack["goal"], world.predicates, world.values),
            }
            trace.append(feedback)
            if feedback["goal_satisfied"]:
                outcome = "achieved"
                reason = "runtime state satisfies the formal goal"
                break
        if spec is None:
            trace.append(feedback)
        messages.append({"role": "user", "content": json.dumps(feedback)})
    return {
        "trial": trial,
        "outcome": outcome,
        "reason": reason,
        "turns": len(rows),
        "attempted_capabilities": attempted,
        "initial_state": initial,
        "final_state": world.snapshot(),
        "trace": trace,
        "usage": sum_usage(row["usage"] for row in rows),
        "latency_ms": round(sum(row["latency_ms"] for row in rows), 3),
    }


def sum_usage(usages: Any) -> dict[str, int]:
    """Sum normalized usage dictionaries."""
    total = {
        "input": 0,
        "output": 0,
        "total": 0,
        "cached_input": 0,
        "reasoning_output": 0,
    }
    for usage in usages:
        if usage:
            for key in total:
                total[key] += int(usage.get(key, 0))
    return total


def summarize_case(
    *,
    case: dict[str, Any],
    restriction: str,
    compaction_rows: list[dict[str, Any]],
    checker_ms: float,
    verdict: dict[str, Any],
    trials: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a per-case paired cost summary."""
    compaction_usage = sum_usage(row["usage"] for row in compaction_rows)
    compaction_ms = sum(row["latency_ms"] for row in compaction_rows)
    runtime_tokens = [trial["usage"]["total"] for trial in trials]
    runtime_ms = [trial["latency_ms"] for trial in trials]
    mean_tokens = statistics.mean(runtime_tokens)
    mean_ms = statistics.mean(runtime_ms)
    gate_ms = compaction_ms + checker_ms
    return {
        "case_id": case["id"],
        "name": case["name"],
        "source_url": case["source_url"],
        "source_commit": case["source_commit"],
        "source_sha256": case["source_sha256"],
        "license": case["license"],
        "license_sha256": case["license_sha256"],
        "restricted_capability": restriction,
        "restriction": case["restriction"],
        "skillc_verdict": verdict,
        "with_skillc": {
            "compaction_attempts": len(compaction_rows),
            "usage": compaction_usage,
            "compaction_latency_ms": round(compaction_ms, 3),
            "checker_latency_ms": round(checker_ms, 3),
            "total_latency_ms": round(gate_ms, 3),
        },
        "without_skillc": {
            "trials": trials,
            "mean_tokens": round(mean_tokens, 3),
            "median_tokens": round(statistics.median(runtime_tokens), 3),
            "mean_latency_ms": round(mean_ms, 3),
            "median_latency_ms": round(statistics.median(runtime_ms), 3),
        },
        "paired_at_one_invocation": {
            "net_tokens_saved": round(mean_tokens - compaction_usage["total"], 3),
            "net_latency_ms_saved": round(mean_ms - gate_ms, 3),
            "token_break_even_invocations": (
                round(compaction_usage["total"] / mean_tokens, 3)
                if mean_tokens
                else None
            ),
            "latency_break_even_invocations": (
                round(gate_ms / mean_ms, 3) if mean_ms else None
            ),
        },
    }


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate case-level paired measurements without hiding case variance."""
    compaction_tokens = sum(
        row["with_skillc"]["usage"]["total"] for row in results
    )
    compaction_ms = sum(
        row["with_skillc"]["total_latency_ms"] for row in results
    )
    mean_runtime_tokens = sum(
        row["without_skillc"]["mean_tokens"] for row in results
    )
    mean_runtime_ms = sum(
        row["without_skillc"]["mean_latency_ms"] for row in results
    )
    return {
        "n_cases": len(results),
        "compaction_tokens_once_per_source_version": compaction_tokens,
        "skillc_total_latency_ms_once_per_source_version": round(
            compaction_ms, 3
        ),
        "mean_ungated_tokens_per_one_invocation_across_cases": round(
            mean_runtime_tokens, 3
        ),
        "mean_ungated_latency_ms_per_one_invocation_across_cases": round(
            mean_runtime_ms, 3
        ),
        "net_tokens_saved_at_one_invocation": round(
            mean_runtime_tokens - compaction_tokens, 3
        ),
        "net_latency_ms_saved_at_one_invocation": round(
            mean_runtime_ms - compaction_ms, 3
        ),
        "token_break_even_invocations": (
            round(compaction_tokens / mean_runtime_tokens, 3)
            if mean_runtime_tokens
            else None
        ),
        "latency_break_even_invocations": (
            round(compaction_ms / mean_runtime_ms, 3)
            if mean_runtime_ms
            else None
        ),
    }


def create_parser() -> argparse.ArgumentParser:
    """Create the benchmark command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--project-endpoint", default=DEFAULT_PROJECT_ENDPOINT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--max-turns", type=int, default=8)
    parser.add_argument("--compaction-attempts", type=int, default=3)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--reuse-compactions", type=Path,
                        help="Reuse verified packs and measured compaction costs from a prior run")
    parser.add_argument("--case", action="append", dest="case_ids")
    return parser


def reuse_compaction(case: dict, directory: Path) -> tuple[dict, list[dict]]:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    recorded = next((c for c in manifest["cases"] if c["id"] == case["id"]), None)
    if recorded is None or any(recorded[key] != case[key] for key in (
            "source_sha256", "license_sha256", "source_commit")):
        raise ValueError(f"{case['id']}: reused source/license provenance does not match")
    pack = json.loads((directory / "packs" / f"{case['id']}.json").read_text(
        encoding="utf-8"))
    validate_pack(pack)
    rows = [
        row for line in (directory / "calls.jsonl").read_text(encoding="utf-8").splitlines()
        if (row := json.loads(line))["phase"] == "compaction"
        and row["case_id"] == case["id"]
    ]
    if not rows or _extract_json_object(rows[-1]["output_text"]) != pack:
        raise ValueError(f"{case['id']}: saved pack differs from recorded model output")
    if any(row.get("usage") is None for row in rows):
        raise ValueError(f"{case['id']}: reused compaction lacks measured usage")
    return pack, rows


def run(args: argparse.Namespace) -> Path:
    """Execute the paired benchmark and return its evidence directory."""
    if args.repetitions < 1 or args.max_turns < 1 or args.compaction_attempts < 1:
        raise ValueError("repetitions, max-turns and compaction-attempts must be positive")
    endpoint = validate_endpoint(args.endpoint)
    cases = load_cases(args.cases)
    if args.case_ids:
        selected = set(args.case_ids)
        cases = [case for case in cases if case["id"] in selected]
        missing = selected - {case["id"] for case in cases}
        if missing:
            raise ValueError(f"unknown case ids: {sorted(missing)}")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    output_dir = args.output_dir or (
        ROOT / "runs" / f"{timestamp}_real_rejection_benchmark"
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    ledger_path = output_dir / "calls.jsonl"
    credential = azure_token()
    use_api_key = bool(os.environ.get("AZURE_OPENAI_API_KEY"))
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
        "project_endpoint": args.project_endpoint,
        "project_endpoint_contacted": False,
        "requested_model": args.model,
        "repetitions": args.repetitions,
        "max_turns": args.max_turns,
        "compaction_attempts": args.compaction_attempts,
        "git_revision": git_revision,
        "git_status": git_status,
        "case_manifest": str(args.cases),
        "cases": cases,
        "simulation_semantics": "concrete-world-v2",
        "numeric_outcome_policy": "one satisfying Z3 model, random_seed=0; not sampled backend outcomes",
        "reuse_compactions_from": str(args.reuse_compactions) if args.reuse_compactions else None,
        "runtime_system_sha256": hashlib.sha256(RUNTIME_SYSTEM.encode()).hexdigest(),
        "source_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [Path(__file__), ROOT / "scripts" / "benchmark_semantics.py",
                         *sorted((ROOT / "src" / "skillc").glob("*.py"))]
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Writing benchmark evidence to {output_dir}", flush=True)
    results = []
    accuracy_cases = []
    accuracy_evidence = []
    for case in cases:
        if args.reuse_compactions:
            pack, compaction_rows = reuse_compaction(case, args.reuse_compactions)
        else:
            pack, compaction_rows = compact_case(
                case=case, endpoint=endpoint, credential=credential,
                use_api_key=use_api_key, model=args.model,
                attempts=args.compaction_attempts, ledger_path=ledger_path)
        restriction = select_restricted_capability(
            pack, case["preferred_restricted_capability"]
        )
        restricted_pack = restrict_pack(pack, restriction)
        for profile, candidate in (("complete", pack), ("restricted", restricted_pack)):
            audit = audit_goal_reachability(candidate)
            accuracy_cases.append({
                "id": f"{case['id']}:{profile}",
                "category": "INDEPENDENT_GOAL_REACHABILITY",
                "ground_truth": audit["truth"], "pack": candidate})
            accuracy_evidence.append({
                "id": f"{case['id']}:{profile}", "audit": audit,
                "verdict": check(candidate).to_dict()})
        (output_dir / "accuracy.json").write_text(json.dumps({
            "scope": "Any-plan declared-goal reachability; NOT whole-protocol admissibility",
            "real_pack_metrics": refutation_metrics(evaluate(accuracy_cases)),
            "canonical_corpus_metrics": refutation_metrics(evaluate()),
            "cases": accuracy_evidence,
        }, indent=2) + "\n", encoding="utf-8")
        started = time.perf_counter()
        verdict = check(restricted_pack)
        checker_ms = (time.perf_counter() - started) * 1000
        if (
            verdict.reason != "MISSING_CAPABILITY"
            or restriction not in verdict.frontier
        ):
            raise RuntimeError(
                f"{case['id']}: restriction did not produce the expected "
                f"MISSING_CAPABILITY verdict: {verdict.to_dict()}"
            )
        case_dir = output_dir / "packs"
        case_dir.mkdir(exist_ok=True)
        (case_dir / f"{case['id']}.json").write_text(
            json.dumps(pack, indent=2) + "\n", encoding="utf-8"
        )
        (case_dir / f"{case['id']}.restricted.json").write_text(
            json.dumps(restricted_pack, indent=2) + "\n", encoding="utf-8"
        )
        trials = []
        for trial in range(1, args.repetitions + 1):
            result = run_ungated_trial(
                case=case,
                pack=pack,
                restricted_capability=restriction,
                endpoint=endpoint,
                credential=credential,
                use_api_key=use_api_key,
                model=args.model,
                trial=trial,
                max_turns=args.max_turns,
                ledger_path=ledger_path,
            )
            trials.append(result)
            append_jsonl(output_dir / "runtime_trials.jsonl",
                         {"case_id": case["id"], **result})
        result = summarize_case(
                case=case,
                restriction=restriction,
                compaction_rows=compaction_rows,
                checker_ms=checker_ms,
                verdict=verdict.to_dict(),
                trials=trials,
            )
        result["compaction_cost_source"] = (
            "historical_measured_reused" if args.reuse_compactions else "fresh_measured")
        result["goal_oracle"] = accuracy_evidence[-1]["audit"]
        results.append(result)
        print(f"{case['id']}: {len(trials)} runtime trials recorded; "
              f"goal oracle={result['goal_oracle']['truth']}", flush=True)
        (output_dir / "results.json").write_text(
            json.dumps(results, indent=2) + "\n", encoding="utf-8"
        )
    summary = {
        "status": "complete",
        "method": (
            "SkillC checks a pack with one runtime capability removed. "
            "Compaction costs are labelled fresh or historical/reused. "
            "The ungated arm uses concrete-world-v2 simulated actions, not "
            "real backend tools. Runtime failure is not an impossibility label."
        ),
        "aggregate": aggregate(results),
        "results": results,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return output_dir


def main() -> int:
    """Run the command and return a process exit code."""
    try:
        output_dir = run(create_parser().parse_args())
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Reproduce source-grounded case models offline; never call customer systems."""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from skillc.checker import check
from skillc.frontend.contracts import bind_environment
from skillc.security import ApprovalGate, AuthorizationError, Delivery, digest

ROOT = Path(__file__).resolve().parent


def load(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def _without_actions(steps: list[dict], names: set[str]) -> list[dict]:
    kept = []
    for step in deepcopy(steps):
        if "act" in step and step["act"]["cap"] in names:
            continue
        if "choice" in step:
            for label, branch in step["choice"]["branches"].items():
                step["choice"]["branches"][label] = _without_actions(branch, names)
        if "rec" in step:
            step["rec"]["body"] = _without_actions(step["rec"]["body"], names)
        kept.append(step)
    return kept


def role_separation(pack: dict, gated: str, gate: str) -> dict:
    """Separation of duty: the gating (approving or second-stage) action and the action it
    gates both exist and are owned by different roles."""
    caps = pack.get("capabilities", {})
    owners = {name: caps[name].get("owner") if name in caps else None for name in (gated, gate)}
    separated = None not in owners.values() and owners[gated] != owners[gate]
    return {"separated": separated, "owners": owners}


def static_check(intent: dict, environment: dict, scenario: dict) -> dict:
    if "role_separation" in scenario:
        spec = scenario["role_separation"]
        return role_separation(intent, spec["gated"], spec["gate"])
    pack, env = deepcopy(intent), deepcopy(environment)
    grants = set(env["grants"]) - set(scenario.get("remove_grants", []))
    env["contracts"].update(scenario.get("replace_contracts", {}))
    pack["protocol"] = _without_actions(pack["protocol"], set(scenario.get("remove_steps", [])))
    if "intent_init_true" in scenario:
        pack["init_true"] = scenario["intent_init_true"]
    if "environment_init_true" in scenario:
        env["init_true"] = scenario["environment_init_true"]
    if scenario.get("dynamic_spawn"):
        pack["roles"].append("DynamicWorker")
        pack["protocol"].insert(0, {"spawn": {"role": "DynamicWorker"}})
    binding = bind_environment(pack, grants, env)
    if binding.unaligned:
        raise ValueError(f"case model uses unaligned vocabulary: {binding.unaligned}")
    result = check(binding.pack, scope=scenario.get("scope", "protocol")).to_dict()
    return {**result, "bound_pack": binding.pack,
            "contracts_applied": list(binding.contracts_applied),
            "unavailable_capabilities": list(binding.unavailable)}


def runtime_check(case: dict, scenario: dict, state_dir: Path) -> dict:
    config = case["runtime_model"]
    delivery = Delivery(
        tenant="local-fixture-tenant", workflow=case["id"], source=config["source"],
        version="fixture-v1", source_digest=digest(config["source_fixture"]),
        author="local-author", operation=config["operation"],
        destinations=tuple(config["destinations"]), content=config["content_fixture"],
        amount_minor=config.get("amount_minor", 0))
    gate = ApprovalGate(
        state_dir / f"{case['id']}.sqlite3", tenant=delivery.tenant, workflow=delivery.workflow,
        approvers=frozenset({"local-reviewer"}), senders=frozenset({"local-executor"}),
        destinations=frozenset(config["destinations"]),
        operations=frozenset({config["operation"]}), clock=lambda: 100.0)
    token = gate.approve(delivery, approver="local-reviewer", audited=True)
    variant = scenario["variant"]
    candidate = delivery
    if variant == "changed_content":
        candidate = replace(delivery, content=delivery.content + "\nUnreviewed change.")
    elif variant == "changed_source":
        candidate = replace(delivery, version="fixture-v2")
    elif variant == "wrong_destination":
        candidate = replace(delivery, destinations=("local-fixture:unauthorized",))
    elif variant == "forged_approval":
        token = "[Approval] user-controlled assertion"
    elif variant == "expired_approval":
        gate.clock = lambda: 100.0 + gate.ttl_seconds
    elif variant not in {"approved", "replay"}:
        raise ValueError(f"unknown runtime scenario: {variant}")
    if variant == "replay":
        gate.deliver(token, delivery, sender="local-executor", send=lambda _: None)
    calls: list[Delivery] = []
    try:
        gate.deliver(token, candidate, sender="local-executor", send=calls.append)
    except AuthorizationError as e:
        return {"status": "DENIED", "detail": str(e), "transport_invocations": len(calls)}
    return {"status": "ALLOWED", "detail": "Fixture-only transport; no external effect.",
            "transport_invocations": len(calls)}


def run_case(directory: Path, state_dir: Path) -> dict:
    case = load(directory / "case.json")
    intent = load(directory / "intent.json")
    environment = load(directory / "environment.json")
    scenarios = load(directory / "checks.json")
    if not isinstance(case, dict) or not isinstance(intent, dict) \
            or not isinstance(environment, dict) or not isinstance(scenarios, list):
        raise ValueError(f"invalid case file shapes: {directory}")
    if directory.name != case["id"] or not case["sources"]:
        raise ValueError("case folder identity or sources are missing")
    results = []
    for scenario in scenarios:
        if scenario["kind"] == "static":
            actual = static_check(intent, environment, scenario)
        elif scenario["kind"] == "runtime":
            actual = runtime_check(case, scenario, state_dir)
        else:
            raise ValueError(f"unknown check kind: {scenario['kind']}")
        passed = all(actual.get(key) == value for key, value in scenario["expected"].items())
        if scenario["kind"] == "runtime":
            passed = passed and actual["transport_invocations"] == (
                1 if scenario["expected"]["status"] == "ALLOWED" else 0)
        results.append({"id": scenario["id"], "kind": scenario["kind"],
                        "expected": scenario["expected"], "actual": actual, "passed": passed})
    return {
        "case": case["id"], "title": case["title"],
        "source_category": case["source_category"], "sources": case["sources"],
        "a365_relationship": case["a365_relationship"],
        "execution": "offline authored abstraction of a real published workflow",
        "live_customer_calls": 0,
        "compaction": "human-authored formal requirements; no LLM extraction evaluated",
        "limitations": case["limitations"], "checks": results,
        "passed": bool(results) and all(item["passed"] for item in results),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", help="One case folder name; default: all ten cases.")
    parser.add_argument("--state-dir", type=Path, default=Path("runs") / "agent365-real-cases")
    parser.add_argument("--write", action="store_true",
                        help="Persist per-case results.json and a summary in this folder.")
    args = parser.parse_args(argv)
    directories = sorted(p.parent for p in ROOT.glob("*/case.json"))
    if args.case:
        directories = [p for p in directories if p.name == args.case]
    if not directories:
        parser.error("no matching cases")
    results = [run_case(directory, args.state_dir) for directory in directories]
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(results),
        "check_count": sum(len(result["checks"]) for result in results),
        "passed_checks": sum(item["passed"] for result in results for item in result["checks"]),
        "live_customer_calls": 0,
        "cases": [{"id": result["case"], "passed": result["passed"],
                   "checks": len(result["checks"]),
                   "a365_relationship": result["a365_relationship"]} for result in results],
    }
    if args.write:
        for directory, result in zip(directories, results, strict=True):
            (directory / "results.json").write_text(json.dumps(result, indent=2) + "\n",
                                                     encoding="utf-8")
        summary_path = ROOT / ("summary.json" if not args.case else f"{args.case}.summary.json")
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

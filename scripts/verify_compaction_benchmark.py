"""Verify persisted comparison evidence and replay verdicts without model calls."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.benchmark_compaction import assess, score, sha, write_json
from scripts.benchmark_semantics import World, audit_goal_reachability, holds
from skillc.frontend.llm import _extract_json_object
from skillc.frontend.markdown import compile_markdown
from skillc.pack import PackError, validate_pack
from skillc.profiles import Profile


def verify(directory: Path) -> dict:
    frozen = json.loads((directory / "frozen.json").read_text())
    results = json.loads((directory / "results.json").read_text())
    metrics = json.loads((directory / "metrics.json").read_text())
    calls = [json.loads(line) for line in
             (directory / "calls.jsonl").read_text().splitlines()]
    assert len(results) == 6 * len(frozen["scenarios"])
    assert len({(r["id"], r["mode"], r["variant"]) for r in results}) == len(results)
    for relative, expected in frozen["implementation_sha256"].items():
        assert sha(directory / "implementation" / relative) == expected, relative
    sources = json.loads((directory / "sources" / "sources.json").read_text())
    for source in sources:
        for filename, field in (("SKILL.md", "skill_md_sha256"), ("LICENSE", "license_sha256")):
            assert sha(directory / "sources" / source["id"] / filename) == source[field]
    replayed = []
    witness_steps = 0
    for scenario in frozen["scenarios"]:
        case_dir = directory / scenario["id"]
        for filename, field in (("input.md", "input_sha256"),
                                ("contract.json", "contract_sha256"),
                                ("oracle.json", "oracle_sha256")):
            assert sha(case_dir / filename) == scenario[field]
        contract = json.loads((case_dir / "contract.json").read_text())
        reference = {"name": scenario["source"], "protocol": [], **contract}
        oracle = json.loads((case_dir / "oracle.json").read_text())
        assert audit_goal_reachability(reference)["truth"] == scenario["truth"]
        if oracle["truth"] == "ACHIEVABLE":
            world = World.initial(reference)
            for step in oracle["witness"]:
                world, error = world.transition(contract["capabilities"][step["capability"]])
                assert error is None
                assert world.snapshot() == {key: step[key] for key in world.snapshot()}
                witness_steps += 1
            assert holds(contract["goal"], world.predicates, world.values)
        text = (case_dir / "input.md").read_text(encoding="utf-8")
        compiled = compile_markdown(
            text, Profile(name="fixed-invocation", tools=frozenset(contract["capabilities"])),
            name=scenario["source"])
        assert compiled.pack == json.loads((case_dir / "deterministic_pack.json").read_text())
        replayed.extend(assess(compiled.pack, contract, scenario, "deterministic",
                               compiled.goal_source))
        llm = json.loads((case_dir / "llm_result.json").read_text())
        case_calls = [call for call in calls if call["id"] == scenario["id"]]
        assert len(case_calls) == llm["attempts"]
        messages = [{"role": "system", "content": frozen["system"]},
                    {"role": "user", "content": text}]
        for attempt, call in enumerate(case_calls, 1):
            assert call["attempt"] == attempt
            payload = {
                "model": call["requested_model"], "messages": messages,
                "max_completion_tokens": 6000,
                "response_format": {"type": "json_object"},
            }
            digest = hashlib.sha256(json.dumps(
                payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            assert digest == call["request_sha256"]
            assert call["http_status"] == 200 and not call["error"]
            assert call["usage"]["input"] + call["usage"]["output"] == call["usage"]["total"]
            try:
                if call["finish_reason"] != "stop":
                    raise ValueError(f"incomplete output: {call['finish_reason']}")
                pack = _extract_json_object(call["output_text"])
                validate_pack(pack)
            except (PackError, ValueError) as exc:
                messages += [
                    {"role": "assistant", "content": call["output_text"]},
                    {"role": "user", "content":
                     f"Schema validation failed: {exc}. Return a valid pack; "
                     "do not weaken the task or change the contract."}]
            else:
                assert pack == llm["pack"]
        if "error" in llm:
            replayed.extend(r for r in results
                            if r["id"] == scenario["id"] and r["mode"] == "llm")
        else:
            replayed.extend(assess(llm["pack"], contract, scenario, "llm", "llm"))
    indexed = {(r["id"], r["mode"], r["variant"]): r for r in results}
    for row in replayed:
        previous = indexed[(row["id"], row["mode"], row["variant"])]
        assert row["predicted"] == previous["predicted"]
        assert row["reason"] == previous["reason"]
    for name, group in metrics.items():
        mode, variant = name.split("/")
        selected = [r for r in replayed if r["mode"] == mode and r["variant"] == variant]
        assert score(selected) == group["overall"]
    report = {
        "scenarios_verified": len(frozen["scenarios"]),
        "verdicts_replayed": len(replayed), "source_documents_verified": len(sources),
        "concrete_reference_witness_steps": witness_steps,
        "calls_verified": len(calls),
        "resolved_models": dict(Counter(c["resolved_model"] for c in calls)),
        "tokens": {key: sum(c["usage"][key] for c in calls)
                   for key in ("input", "output", "total", "cached_input", "reasoning_output")},
        "summed_api_latency_ms": round(sum(c["latency_ms"] for c in calls), 3),
        "verifier_sha256": sha(Path(__file__)),
        "replayed_implementation_sha256": {
            relative: sha(ROOT / relative) for relative in frozen["implementation_sha256"]},
    }
    write_json(directory / "verification.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    print(json.dumps(verify(parser.parse_args().run_dir), indent=2))

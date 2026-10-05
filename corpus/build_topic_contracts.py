"""Add formal tool contracts to every topic environment in corpus/intents.

The reference packs in build_corpus.py, benchmark/compaction_cases.json, and
each newer topic's own `reference_pack` (topic.json) encode what each
environment's tools really do. This script copies that model
into each topic's environment.json as:

  contracts  {tool: {pre, add, del, nondet, assigns}} for every provided tool
  states     glossary of every condition / numeric value the environment uses
  init_true  conditions the environment provides from the start

Intent files are never touched: these facts belong to the environment only.

Usage:  python corpus/build_topic_contracts.py
"""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOPICS = ROOT / "corpus" / "intents"
CONTRACT_FIELDS = ("pre", "add", "del", "nondet", "assigns")
# Topic tool ids renamed so that no id hints at its behaviour.
RENAMES = {
    "budget_ok": {"book_cheap": "book_fare"},
    "over_budget": {"book_premium": "book_fare"},
    "spurious_payload": {"filter_cheap": "filter_fares"},
}


def reference_models() -> dict:
    """id -> {capabilities, goal, init_true, grants} from both sources."""
    models = {}
    tree = ast.parse((ROOT / "corpus" / "build_corpus.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") in {"add", "add_ext"}:
            case_id = ast.literal_eval(node.args[0])
            pack = ast.literal_eval(node.args[4])
            grants = next((ast.literal_eval(k.value) for k in node.keywords
                           if k.arg == "environment_grants"), list(pack["capabilities"]))
            models[case_id] = {"capabilities": pack["capabilities"], "goal": pack["goal"],
                               "init_true": pack.get("init_true", []), "grants": grants}
    cases = json.loads((ROOT / "benchmark" / "compaction_cases.json").read_text(encoding="utf-8"))
    for case in cases:
        models[case["id"]] = {"capabilities": case["capabilities"], "goal": case["goal"],
                              "init_true": case.get("init_true", []),
                              "grants": list(case["capabilities"])}
    for path in TOPICS.glob("*/topic.json"):
        topic = json.loads(path.read_text(encoding="utf-8"))
        pack = topic.get("reference_pack")
        if pack:
            models[topic["id"]] = {"capabilities": pack["capabilities"], "goal": pack["goal"],
                                   "init_true": pack.get("init_true", []),
                                   "grants": topic["environment_grants"]}
    return models


def symbols(value) -> set:
    """Every condition and numeric-variable name inside a formula or expression."""
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return set().union(*(symbols(item) for item in value)) if value else set()
    if isinstance(value, dict):
        out = set()
        for key, item in value.items():
            out |= symbols(item) if key in {"and", "or", "not", "cmp", "+", "-", "*"} else set()
        return out
    return set()


def contract_states(capability: dict) -> set:
    names = symbols(capability.get("pre", True))
    names |= set(capability.get("add", [])) | set(capability.get("del", []))
    for var, formula in capability.get("nondet", {}).items():
        names |= {var} | symbols(formula)
    for var, expr in capability.get("assigns", {}).items():
        names |= {var} | symbols(expr)
    return names


def build(topic_id: str, model: dict) -> dict:
    path = TOPICS / topic_id / "environment.json"
    environment = json.loads(path.read_text(encoding="utf-8"))
    rename = RENAMES.get(topic_id, {})
    grants = {rename.get(name, name) for name in model["grants"]}
    if set(environment["tools"]) != grants:
        raise SystemExit(f"{topic_id}: environment tools {sorted(environment['tools'])} "
                         f"!= reference grants {sorted(grants)}")
    contracts = {
        rename.get(name, name): {k: cap[k] for k in CONTRACT_FIELDS if k in cap}
        for name, cap in model["capabilities"].items()
        if rename.get(name, name) in grants
    }
    names = symbols(model["goal"]) | set(model["init_true"])
    for capability in model["capabilities"].values():
        names |= contract_states(capability)
    names -= {"<", "<=", "==", ">", ">=", "!="}
    environment["contracts"] = contracts
    environment["states"] = {name: name.replace("_", " ") for name in sorted(names)}
    environment["init_true"] = sorted(model["init_true"])
    path.write_text(json.dumps(environment, indent=2) + "\n", encoding="utf-8")
    return environment


def main() -> None:
    models = reference_models()
    topics = sorted(p.name for p in TOPICS.iterdir() if (p / "topic.json").is_file())
    for topic_id in topics:
        environment = build(topic_id, models[topic_id])
        print(f"{topic_id}: {len(environment['contracts'])} contracts, "
              f"{len(environment['states'])} states")


if __name__ == "__main__":
    main()

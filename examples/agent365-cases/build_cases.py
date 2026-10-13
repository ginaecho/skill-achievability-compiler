"""Materialize standalone case folders from the reviewed source catalog.

This is fixture scaffolding, not natural-language compaction or runtime discovery.
Only generated inputs are overwritten; recorded results are left to run_cases.py.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def write_json(path: Path, data: dict | list) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def scaffold(case: dict) -> None:
    directory = ROOT / case["id"]
    directory.mkdir(exist_ok=True)
    actions = case["actions"]
    if len(actions) < 3 or len({action["id"] for action in actions}) != len(actions):
        raise ValueError("a case needs at least three distinctly named workflow actions")
    roles = list(dict.fromkeys(action.get("role", "Agent") for action in actions))
    capabilities, contracts, states, protocol = {}, {}, {}, []
    previous = None
    previous_role = None
    for action in actions:
        name, role = action["id"], action.get("role", "Agent")
        capabilities[name] = {"owner": role}
        requirements = ([previous] if previous else []) + action.get("requires", [])
        pre = {"and": requirements} if requirements else True
        contracts[name] = {"pre": pre, "add": [action["produces"]]}
        states[action["produces"]] = action["description"]
        for requirement in action.get("requires", []):
            states[requirement] = "Declared environment evidence; not a live observation."
        if previous_role and previous_role != role:
            protocol.append({"msg": {"from": previous_role, "to": role,
                                     "label": previous}})
        protocol.append({"act": {"by": role, "cap": name}})
        previous, previous_role = action["produces"], role
    intent = {"name": case["id"], "roles": roles, "capabilities": capabilities,
              "protocol": protocol, "goal": previous}
    environment = {
        "provenance": "Locally authored test assumptions, NOT a probe of the named organization.",
        "grants": list(capabilities), "contracts": contracts, "states": states,
        "init_true": case.get("environment_facts", []),
    }
    first, last = actions[0], actions[-1]
    checks = [
        {"id": "declared_workflow", "kind": "static",
         "expected": {"verdict": "ACHIEVABLE", "reason": "OK"}},
        {"id": "missing_final_capability", "kind": "static", "remove_grants": [last["id"]],
         "expected": {"verdict": "IMPOSSIBLE", "reason": "MISSING_CAPABILITY"}},
        {"id": "final_tool_only_queues", "kind": "static",
         "replace_contracts": {last["id"]: {
             "pre": contracts[last["id"]]["pre"], "add": ["operation_queued_only"]}},
         "expected": {"verdict": "IMPOSSIBLE", "reason": "GOAL_UNSAT"}},
        {"id": "missing_prerequisite_action", "kind": "static", "remove_steps": [first["id"]],
         "expected": {"verdict": "IMPOSSIBLE", "reason": "BLOCKED_GUARD"}},
        {"id": "invented_initial_evidence", "kind": "static", "remove_steps": [first["id"]],
         "intent_init_true": [first["produces"]],
         "expected": {"verdict": "IMPOSSIBLE", "reason": "BLOCKED_GUARD"}},
        {"id": "alternative_plan_not_ruled_out", "kind": "static",
         "remove_steps": [first["id"]], "scope": "goal",
         "expected": {"verdict": "UNKNOWN", "reason": "PROTOCOL_ONLY"}},
    ]
    for variant in ("approved", "changed_content", "changed_source", "wrong_destination",
                    "forged_approval", "replay"):
        checks.append({"id": f"runtime_{variant}", "kind": "runtime", "variant": variant,
                       "expected": {"status": "ALLOWED" if variant == "approved" else "DENIED"}})
    checks.extend(case.get("extra_checks", []))
    write_json(directory / "intent.json", intent)
    write_json(directory / "environment.json", environment)
    write_json(directory / "checks.json", checks)
    write_json(directory / "case.json", case)
    steps = "\n".join(f"{i}. {action['description']}" for i, action in enumerate(actions, 1))
    intent_text = f"# {case['title']}\n\n{case['intent']}\n\n## Required workflow\n\n{steps}\n"
    (directory / "intent.md").write_text(intent_text, encoding="utf-8")
    sources = "\n".join(
        f"- [{source['title']}]({source['url']}) - {source['publisher']}; "
        f"verified {source['retrieved_at']} ({source['verification']})."
        for source in case["sources"])
    facts = "\n".join(f"- {fact}" for fact in case["published_facts"])
    assumptions = "\n".join(f"- {fact}" for fact in case["local_assumptions"])
    gaps = "\n".join(f"- {gap}" for gap in case["limitations"])
    mapping = "\n".join(
        f"| `{action['id']}` | {action['description']} | `{action['produces']}` |"
        for action in actions)
    extra_checks = "\n".join(
        f"- `{item['id']}`: {item.get('description', '')} "
        f"Expected `{item['expected']}`." for item in case.get("extra_checks", []))
    readme = f"""# {case['title']}

**Source category:** {case['source_category']}

## Verifiable real use case

{case['overview']}

{facts}

### Sources

{sources}

### Relationship to Agent 365

{case['a365_relationship']}

## Complete local case

**User intent:** {case['intent']}

**Actors:** {case['actors']}

**Published outcome:** {case['published_outcome']}

**Modeled goal:** `{previous}`. This is an abstract output milestone, not proof
that the organization's business objective was achieved.

| Local capability name (not a claimed vendor API) | Workflow operation | Modeled effect |
|---|---|---|
{mapping}

### Explicit local test assumptions

{assumptions}

The checked-in `intent.md` describes requirements only. `intent.json` is a
human-authored formalization of those requirements, with no tool-effect definitions.
`environment.json` independently declares test grants, contracts and initial facts.
The source does not publish these formal contracts or prove its live grants.
Runtime fixture IDs, content, reviewer and destinations are fictional local test
values, not customer records. Independent review in the runtime tests is an added
local policy, not a claim about the organization's deployment.

## How SkillC works here

1. `bind_environment` binds named requirements to the declared grants and substitutes
   the environment's tool contracts and initial facts.
2. The trusted checker evaluates capability availability, the declared protocol,
   preconditions and goal reachability. No LLM extracts or judges this case.
3. `checks.json` varies grants, effects and protocol steps. The forged-initial-evidence
   check verifies that the intent cannot manufacture `{first['produces']}`.
4. The runtime checks use `ApprovalGate` at `{case['runtime_model']['operation']}`.
   It binds source version, content, operation and destinations, then consumes
   approval before calling a local recording function. No external system is called.

## What works

| Check | Expected result |
|---|---|
| Full declared workflow | `ACHIEVABLE` (structural admissibility only) |
| Missing `{last['id']}` grant | `IMPOSSIBLE / MISSING_CAPABILITY` |
| Final tool only queues instead of establishing `{previous}` | `IMPOSSIBLE / GOAL_UNSAT` |
| Skip `{first['id']}` | `IMPOSSIBLE / BLOCKED_GUARD` for this protocol |
| Invent initial evidence | Environment wins; prerequisite stays blocked |
| Rule out every alternative plan | `UNKNOWN / PROTOCOL_ONLY` |
| Legitimate independently approved runtime operation | One local transport invocation |
| Altered payload or forged/replayed approval | Denied; zero transport calls |

{extra_checks}

## What does not work / remains unverified

{gaps}

The tests evaluate an authored abstraction and adversarial variants of this real
published workflow. They are **not** evidence that the named deployment is vulnerable,
uses SkillC, uses the added review policy, or was tested in a live tenant.

## Run and inspect

From the repository root:

```powershell
python examples\\agent365-cases\\run_cases.py --case {case['id']} --write
```

`results.json` records actual verdicts, reasons, bound packs, runtime decisions and
transport counts. `case.json` preserves source metadata and local assumptions.
The shared runner returns nonzero if an expectation fails. These inputs are generated
by `build_cases.py` from the reviewed `catalog.json`; edit the catalog to regenerate.
"""
    (directory / "README.md").write_text(readme, encoding="utf-8")


def main() -> None:
    cases = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))
    if len(cases) != 10 or len({case["id"] for case in cases}) != 10:
        raise ValueError("the reviewed catalog must contain exactly ten distinct cases")
    for case in cases:
        scaffold(case)
    print(f"Materialized {len(cases)} standalone case folders.")


if __name__ == "__main__":
    main()

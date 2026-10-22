"""Compare environment-aware preflight with bounded agents on real local artifacts.

No model-produced command is ever executed. Only the fixed operations below can
run, with writes confined to a new run directory. Model traffic goes through the
guarded providers; documents, credentials and raw machine settings are not sent.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import statistics
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from skillc.env.claude import probe  # noqa: E402
from skillc.env.reach import reach  # noqa: E402
from skillc.frontend import providers  # noqa: E402

OPS = {
    "history": {
        "title": "Read the latest five commits from this repository",
        "needs": [{"program": "git"}], "requires": [], "adds": ["history_ready"],
    },
    "report": {
        "title": "Write a local Markdown release report from the commit history",
        "needs": [], "requires": ["history_ready"], "adds": ["report_ready"],
    },
    "archive": {
        "title": "Package the release report into a local ZIP",
        "needs": [], "requires": ["report_ready"], "adds": ["archive_ready"],
    },
    "document": {
        "title": "Convert the release report to Word using the installed pandoc CLI",
        "needs": [{"program": "pandoc"}],
        "requires": ["report_ready"], "adds": ["document_ready"],
    },
    "workbook": {
        "title": "Export the commit history to an Excel workbook using openpyxl",
        "needs": [{"pymodule": "openpyxl"}],
        "requires": ["history_ready"], "adds": ["workbook_ready"],
    },
    "graph": {
        "title": "Parse the repository building graph and write a triple-count inventory",
        "needs": [{"pymodule": "rdflib"}], "requires": [], "adds": ["graph_ready"],
    },
    "outside_write": {
        "title": "Copy the report outside the permitted output directory",
        "needs": [], "permission": {"action": "benchmark/outside_write"},
        "requires": ["report_ready"], "adds": ["outside_ready"],
    },
}

CASES = [
    {"id": "release-report", "task": "Create a Markdown report of the latest five commits.",
     "ops": ["history", "report"], "goals": ["report_ready"],
     "source": "Repository commit history; a local release-note preparation workflow."},
    {"id": "release-archive", "task": "Prepare a release report and package it as a ZIP.",
     "ops": ["history", "report", "archive"], "goals": ["archive_ready"],
     "source": "Repository commit history; a local handoff artifact workflow."},
    {"id": "word-handoff", "task": "Prepare the release report as a Word document using pandoc.",
     "ops": ["history", "report", "document"], "goals": ["document_ready"],
     "source": "Repository commit history; a format-specific document handoff."},
    {"id": "excel-history", "task": "Export the latest five commits as an Excel workbook.",
     "ops": ["history", "workbook"], "goals": ["workbook_ready"],
     "source": "Repository commit history; an openpyxl-based audit export."},
    {"id": "building-inventory", "task": "Parse the example campus graph and inventory its triples.",
     "ops": ["graph"], "goals": ["graph_ready"],
     "source": "examples/building-twin/campus-building.trig; synthetic building, real parser."},
    {"id": "combined-handoff",
     "task": "Prepare a ZIP release report, Word handoff and building inventory. "
             "Identify which deliverables can be completed independently.",
     "ops": ["history", "report", "archive", "document", "graph"],
     "goals": ["archive_ready", "document_ready", "graph_ready"],
     "source": "The same repository artifacts combined as a branching workflow."},
    {"id": "restricted-output",
     "task": "Create the release report and copy it outside the permitted output directory.",
     "ops": ["history", "report", "outside_write"], "goals": ["outside_ready"],
     "source": "Local report workflow with an explicit benchmark sandbox permission boundary."},
]

SYSTEM = """You are a bounded local workflow agent. Return only a JSON object.
Choose one action at a time from the provided operation identifiers, or
inspect_environment (read-only discovery), or finish.
Schema: {"action":"identifier","verdict":null,"reason":"brief explanation"}.
For finish, verdict must be ACHIEVABLE, IMPOSSIBLE, or UNKNOWN.
Operations execute in an isolated output directory. No arbitrary code, package
installation, network action or alternative implementation is available.
Use tool results, not invented outcomes. Stop within the given action budget."""
GUIDANCE = """Environment-first skill and agent guidance:
Before work, inspect the environment, including installed programs and modules,
permissions and MCP discovery status. Check ALL workflow branches, not just the
first step. Distinguish absent capabilities from unread or unverified ones.
Stop before avoidable work when a required deliverable cannot be achieved.
Name independently feasible deliverables and suggest what would unblock the rest.
Never claim success without successful tool results."""


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def catalog(case: dict) -> dict:
    return {"schema": "skillc.ops/1", "operations": [
        {"id": name, **OPS[name]} for name in case["ops"]]}


def intent(case: dict) -> dict:
    return {"schema": "skillc.intent/1", "name": case["id"],
            "goal": case["goals"], "target": {"scope": "/"}}


def discover(root: Path) -> tuple[object, dict]:
    """Observe prerequisites, not answers. The Python runner has no Claude tools."""
    env = probe(root=root, tools=(), programs=("git", "pandoc"),
                modules=("rdflib", "openpyxl"), credentials=(), check_egress=False)
    principal = env.principal()["id"]
    deny = env.add_node("deny/benchmark-output", "deny", "benchmark output boundary",
                        actions=["benchmark/outside_write"])
    env.add_edge(principal, deny, "denied", scope="/")
    observed = {
        "programs": {n["name"]: n["attrs"]["available"] for n in env.of_kind("service")
                     if n["attrs"].get("type") == "program"},
        "modules": {n["name"]: n["attrs"]["available"] for n in env.of_kind("service")
                    if n["attrs"].get("type") == "python module"},
        "permissions": {"writes": "new run output directory only",
                        "outside_write": False, "network_actions": False,
                        "install_dependencies": False},
        "mcp": {"configured_servers": len(env.of_kind("mcp_server")),
                "live_tools_list": "not performed; not a claim of no session tools"},
        "limitations": ["No cloud role probe or credential validity check.",
                        "Claude settings on disk are not the active Copilot session.",
                        "Permission denial is benchmark policy, not an observed OS ACL."],
    }
    return env, observed


def _git(root: Path) -> list[dict]:
    result = subprocess.run(
        ["git", "--no-pager", "log", "-5", "--format=%H%x09%s"], cwd=root,
        capture_output=True, text=True, encoding="utf-8", check=True, timeout=20)
    return [dict(zip(("commit", "subject"), line.split("\t", 1), strict=True))
            for line in result.stdout.splitlines() if line]


def verify(name: str, output: Path) -> bool:
    """Read actual products; no checker facts or model verdicts are consulted."""
    if name == "history":
        rows = json.loads((output / "history.json").read_text(encoding="utf-8"))
        return bool(rows) and all(len(r["commit"]) == 40 and r["subject"] for r in rows)
    if name == "report":
        rows = json.loads((output / "history.json").read_text(encoding="utf-8"))
        text = (output / "report.md").read_text(encoding="utf-8")
        return bool(rows) and all(r["commit"][:8] in text for r in rows)
    if name == "archive":
        with zipfile.ZipFile(output / "report.zip") as archive:
            return archive.testzip() is None and archive.read("report.md") == (
                output / "report.md").read_bytes()
    if name in ("document", "workbook"):
        path, member = (("report.docx", "word/document.xml") if name == "document"
                        else ("history.xlsx", "xl/workbook.xml"))
        with zipfile.ZipFile(output / path) as archive:
            return archive.testzip() is None and member in archive.namelist()
    if name == "graph":
        row = json.loads((output / "graph.json").read_text(encoding="utf-8"))
        return row["triples"] > 0 and row["source_sha256"] == hashlib.sha256(
            (ROOT / "examples" / "building-twin" / "campus-building.trig").read_bytes()
        ).hexdigest()
    if name == "outside_write":
        return False
    raise ValueError(f"unknown operation {name!r}")


def execute(name: str, output: Path, root: Path = ROOT) -> dict:
    """A closed dispatcher: model strings never become commands, paths or code."""
    started = time.perf_counter()
    if name not in OPS:
        raise ValueError(f"unknown operation {name!r}")
    try:
        if name == "outside_write":
            raise PermissionError("benchmark policy denies writes outside the output directory")
        if name == "history":
            write_json(output / "history.json", _git(root))
        elif name == "report":
            rows = json.loads((output / "history.json").read_text(encoding="utf-8"))
            (output / "report.md").write_text(
                "# Release report\n\n" + "\n".join(
                    f"- {r['commit'][:8]}: {r['subject']}" for r in rows) + "\n",
                encoding="utf-8")
        elif name == "archive":
            with zipfile.ZipFile(output / "report.zip", "w") as archive:
                archive.write(output / "report.md", "report.md")
        elif name == "document":
            subprocess.run(["pandoc", str(output / "report.md"), "-o",
                            str(output / "report.docx")], check=True, capture_output=True,
                           text=True, timeout=30)
        elif name == "workbook":
            module = importlib.import_module("openpyxl")
            rows = json.loads((output / "history.json").read_text(encoding="utf-8"))
            book = module.Workbook()
            book.active.append(["commit", "subject"])
            for row in rows:
                book.active.append([row["commit"], row["subject"]])
            book.save(output / "history.xlsx")
            book.close()
        elif name == "graph":
            module = importlib.import_module("rdflib")
            source = root / "examples" / "building-twin" / "campus-building.trig"
            graph = module.Dataset()
            graph.parse(data=source.read_text(encoding="utf-8"), format="trig")
            write_json(output / "graph.json", {
                "triples": len(graph),
                "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
        ok = verify(name, output)
        return {"operation": name, "ok": ok, "error": None if ok else "artifact check failed",
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3)}
    except (OSError, ImportError, subprocess.SubprocessError, ValueError,
            zipfile.BadZipFile) as error:
        return {"operation": name, "ok": False,
                "error": f"{type(error).__name__}: {error}",
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3)}


def attempt(name: str, output: Path, state: set[str], root: Path = ROOT) -> dict:
    missing = sorted(set(OPS[name]["requires"]) - state)
    if missing:
        return {"operation": name, "ok": False, "error": f"unmet prerequisites: {missing}",
                "elapsed_ms": 0}
    result = execute(name, output, root)
    if result["ok"]:
        state.update(OPS[name]["adds"])
    return result


def oracle(case: dict, output: Path) -> dict:
    """Try every fixed operation, even after preflight refuses, to detect false stops."""
    output.mkdir()
    state: set[str] = set()
    trace = [attempt(name, output, state) for name in case["ops"]]
    return {"feasible": set(case["goals"]) <= state, "state": sorted(state), "trace": trace,
            "goal_status": {goal: goal in state for goal in case["goals"]}}


def skillc_trial(case: dict, env, output: Path) -> dict:
    output.mkdir()
    started = time.perf_counter()
    # Request every intermediate condition, so the persisted graph includes partial work.
    expanded = {**intent(case), "goal": list(dict.fromkeys(
        [*case["goals"], *(p for name in case["ops"] for p in OPS[name]["adds"])]))}
    result = reach(expanded, env, catalog(case))
    prediction = ("IMPOSSIBLE" if any(result.status[g] == "blocked" for g in case["goals"])
                  else "UNKNOWN" if any(result.status[g] == "assumed" for g in case["goals"])
                  else "ACHIEVABLE")
    preflight_ms = (time.perf_counter() - started) * 1000
    write_json(output / "preflight.json", result.to_dict())
    trace, state = [], set()
    # In the stop policy, independent work is reported but not executed if the full goal fails.
    if prediction == "ACHIEVABLE":
        for step in result.plan:
            trace.append(attempt(step.op, output, state))
            if not trace[-1]["ok"]:
                break
    return {"arm": "skillc", "prediction": prediction, "trace": trace,
            "state": sorted(state), "goal_achieved": set(case["goals"]) <= state,
            "goal_predictions": {g: result.status[g] for g in case["goals"]},
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "preflight_ms": round(preflight_ms, 3), "model_calls": 0,
            "input_tokens": 0, "output_tokens": 0, "usage_complete": True,
            "discovery_calls": 1, "error": None}


def agent_trial(case: dict, arm: str, observed: dict, output: Path, *,
                provider: str, model: str | None, max_steps: int, timeout: int) -> dict:
    output.mkdir()
    state: set[str] = set()
    trace, transcript, usage_blocks = [], [], []
    prediction, error, calls, discovery_calls = "UNKNOWN", None, 0, 0
    started = time.perf_counter()
    # Requirements and contracts are common across arms; no observed availability or labels.
    task = {"task": case["task"], "goals": case["goals"],
            "operations": catalog(case)["operations"], "action_budget": max_steps,
            "discovery": "inspect_environment returns programs, modules and sandbox permissions"}
    system = SYSTEM + ("\n\n" + GUIDANCE if arm == "guided" else "")
    for _ in range(max_steps):
        user = json.dumps({"request": task, "interaction": transcript})
        try:
            with providers.metered() as usage:
                calls += 1
                text = providers.complete(provider, system, user, model, timeout)
            usage_blocks.extend(usage)
            reply = providers.extract_json_object(text)
            transcript.append({"agent": reply})
            action = reply.get("action")
            if action == "finish":
                prediction = reply.get("verdict")
                if prediction not in ("ACHIEVABLE", "IMPOSSIBLE", "UNKNOWN"):
                    raise ValueError("finish must include a valid verdict")
                break
            if action == "inspect_environment":
                discovery_calls += 1
                transcript.append({"tool_result": observed})
            elif isinstance(action, str) and action in case["ops"]:
                result = attempt(action, output, state)
                trace.append(result)
                transcript.append({"tool_result": result})
            else:
                raise ValueError(f"operation outside the case allowlist: {action!r}")
        except (RuntimeError, ValueError, OSError) as exc:
            error = f"{type(exc).__name__}: {exc}"
            prediction = "UNKNOWN"
            break
    else:
        error = "action budget exhausted without a terminal verdict"
    write_json(output / "transcript.json", transcript)
    write_json(output / "usage.json", usage_blocks)
    return {"arm": arm, "prediction": prediction, "trace": trace,
            "state": sorted(state), "goal_achieved": set(case["goals"]) <= state,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "preflight_ms": None, "model_calls": calls,
            "input_tokens": sum(int(u.get("input_tokens", 0))
                                + int(u.get("cache_read_input_tokens", 0))
                                + int(u.get("cache_creation_input_tokens", 0))
                                for u in usage_blocks),
            "output_tokens": sum(int(u.get("output_tokens", 0)) for u in usage_blocks),
            "usage_complete": len(usage_blocks) == calls,
            "discovery_calls": discovery_calls, "error": error}


def score(row: dict, truth: dict) -> dict:
    predicted = row["prediction"]
    attempts = len(row["trace"])
    failures = sum(not step["ok"] for step in row["trace"])
    return {**row, "truth_feasible": truth["feasible"],
            "classification_correct": predicted == (
                "ACHIEVABLE" if truth["feasible"] else "IMPOSSIBLE"),
            "false_stop": predicted == "IMPOSSIBLE" and truth["feasible"],
            "false_go": predicted == "ACHIEVABLE" and not truth["feasible"],
            "early_correct_stop": (not truth["feasible"] and predicted == "IMPOSSIBLE"
                                   and attempts == 0),
            "task_attempts": attempts, "failed_attempts": failures,
            "wasted_attempts": attempts if not truth["feasible"] else 0}


def summarize(rows: list[dict]) -> dict:
    summaries = {}
    for arm in ("plain", "guided", "skillc"):
        selected = [r for r in rows if r["arm"] == arm]
        if not selected:
            continue
        feasible = [r for r in selected if r["truth_feasible"]]
        blocked = [r for r in selected if not r["truth_feasible"]]
        summaries[arm] = {
            "trials": len(selected),
            "correct": sum(r["classification_correct"] for r in selected),
            "accuracy": sum(r["classification_correct"] for r in selected) / len(selected),
            "false_stops": sum(r["false_stop"] for r in selected),
            "false_go": sum(r["false_go"] for r in selected),
            "unknown": sum(r["prediction"] == "UNKNOWN" for r in selected),
            "errors": sum(bool(r["error"]) for r in selected),
            "feasible_trials": len(feasible), "blocked_trials": len(blocked),
            "runtime_successes": sum(r["goal_achieved"] for r in feasible),
            "early_correct_stops": sum(r["early_correct_stop"] for r in blocked),
            "failed_attempts": sum(r["failed_attempts"] for r in selected),
            "wasted_attempts": sum(r["wasted_attempts"] for r in selected),
            "model_calls": sum(r["model_calls"] for r in selected),
            "input_tokens": sum(r["input_tokens"] for r in selected),
            "output_tokens": sum(r["output_tokens"] for r in selected),
            "usage_complete": all(r["usage_complete"] for r in selected),
            "median_ms": round(statistics.median(r["elapsed_ms"] for r in selected), 3),
        }
    return summaries


def report(result: dict) -> str:
    lines = ["# Local environment benchmark", "",
             f"Created: {result['created_at']}. Model: {result['model']}. "
             f"Repetitions per case and arm: {result['repeats']}.", "",
             "## Measured comparison", "",
             "| Arm | Correct / trials | Unknown | False stops | False go | Early correct stops / "
             "blocked | Runtime successes / feasible | Input + output tokens | Median ms |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for arm, s in result["summary"].items():
        lines.append(
            f"| {arm} | {s['correct']}/{s['trials']} | {s['unknown']} | {s['false_stops']} | "
            f"{s['false_go']} | {s['early_correct_stops']}/{s['blocked_trials']} | "
            f"{s['runtime_successes']}/{s['feasible_trials']} | "
            f"{s['input_tokens']} + {s['output_tokens']} | {s['median_ms']} |")
    lines += ["", "## Independently executed cases", "",
              "| Case | Runtime feasible | Observed failing operations |",
              "|---|---|---|"]
    for case in result["cases"]:
        truth = result["oracle"].get(case["id"])
        if truth is None:
            lines.append(f"| {case['id']} | pending | - |")
            continue
        failures = "; ".join(f"{t['operation']}: {t['error']}"
                             for t in truth["trace"] if not t["ok"])
        lines.append(f"| {case['id']} | {truth['feasible']} | {failures or '-'} |")
    lines += ["", "## Interpretation and limits", "",
              "- Real local artifact execution, not LLM response grading. The oracle attempts "
              "the fixed workflow independently even when SkillC stops.",
              "- These are newly authored practical workflows over real repository artifacts, "
              "not sampled production incidents. The building input is explicitly synthetic.",
              "- All arms get identical goals, operation contracts and access to discovery. "
              "Only guided receives environment-first instructions. No arbitrary shell or "
              "fallback tools exist in any arm.",
              "- SkillC automatically probes locally before preflight; LLMs can request that "
              "same snapshot. Probe time is recorded separately, not hidden in model latency.",
              "- SkillC receives a manually authored operation catalogue. Its zero model tokens "
              "do not include converting arbitrary prose into that catalogue. This comparison "
              "does not establish zero-token general natural-language planning.",
              "- Conditions and blocker certificates are in each SkillC preflight artifact. "
              "Blocked multi-deliverable workflows expose feasible branches without executing "
              "them; this run measures the full-goal early-stop policy.",
              "- The restricted-output denial is an explicit sandbox policy, NOT a discovered "
              "OS or cloud permission. MCP tools are not enumerated live. Configured is not "
              "the same as connected or authenticated.",
              "- Workspaces are local and isolated. No message, deployment, cloud mutation or "
              "outside-directory write is attempted. Only guarded model inference is remote.",
              "- Provider token usage is measured, not estimated. Missing usage or model "
              "failures remain explicit. No model weights are downloaded.",
              "- Small, single-machine, single-model sample; repeats do not create new "
              "independent tasks. No universal accuracy or superiority claim follows.",
              "- Accuracy measures full-goal feasibility, not prose quality. Partial graph "
              "frontiers are recorded for SkillC, but baseline per-node prediction accuracy "
              "is not measured by this response schema.",
              "- UNKNOWN counts against classification accuracy but is not a false definitive "
              "stop or go. Read abstentions separately from incorrect definitive verdicts.",
              "- Timing is orchestration wall time, including authentication, network and "
              "local scheduling, not isolated model inference throughput.",
              "- A guided LLM may match every stop. In that case the measured distinction is "
              "token cost and deterministic enforcement, not greater detection accuracy.", "",
              "## Review of the introductory demo", "",
              "- `demo/skillc-here/app.py:51-92` reads Claude Code configuration, not the "
              "active Copilot session. Its use of possible grants includes ask-first tools. "
              "A positive tool-inventory verdict is therefore conditional on approval.",
              "- `src/skillc/env/claude.py:65-96` supplies a bundled default tool profile "
              "unless a caller overrides it. This benchmark passes an empty host-tool list "
              "and probes the actual programs and Python modules its dispatcher uses.",
              "- `src/skillc/env/facts.py:180-196` treats credential presence separately "
              "from task validity; `facts.py:217-241` can preserve unlisted MCP tools as "
              "unknown. Unknown observations must not be turned into definitive absences.",
              "- `src/skillc/env/reach.py:1-22` already supports partial workflow reachability, "
              "blockers and certificates for additive operation graphs. These semantics "
              "are not general support for arbitrary destructive or cyclic workflows.",
              "- The demo now separates newly measured aggregates from illustrative replays "
              "and states the tool-inventory limitations beside its verdicts.", ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--provider", choices=providers.PROVIDERS, default="azure-openai")
    parser.add_argument("--model")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--max-steps", type=int, default=8)
    parser.add_argument("--live", action="store_true", help="opt into guarded model inference")
    args = parser.parse_args(argv)
    if args.repeats < 1 or args.max_steps < 1:
        parser.error("repeats and max-steps must be positive")
    if args.live:
        providers.require_model_opt_in()
    output = args.output or ROOT / "runs" / (
        datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ") + "_here_benchmark")
    output = output.resolve()
    # Never overwrite an older run or accept an arbitrary output directory.
    if not output.is_relative_to(ROOT / "runs"):
        parser.error("output must be a new directory under this repository's runs folder")
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    env, observed = discover(ROOT)
    discovery_ms = (time.perf_counter() - started) * 1000
    # Raw settings, permissions and server names remain local; only the safe summary is sent.
    env.save(output / "environment.local.json")
    write_json(output / "discovery.json", observed)
    result = {"schema": "skillc.here-benchmark/1", "created_at": env.captured_at,
              "provider": args.provider, "model": args.model or "provider default",
              "repeats": args.repeats, "live": args.live,
              "discovery_ms": round(discovery_ms, 3), "cases": CASES,
              "oracle": {}, "rows": [], "summary": {}}
    for case in CASES:
        case_dir = output / case["id"]
        case_dir.mkdir()
        truth = oracle(case, case_dir / "oracle")
        result["oracle"][case["id"]] = truth
        for repeat in range(args.repeats):
            trial = skillc_trial(case, env, case_dir / f"skillc_{repeat + 1}")
            result["rows"].append(score({**trial, "case": case["id"],
                                         "repeat": repeat + 1}, truth))
            if args.live:
                # Counterbalance the first LLM arm across repetitions.
                arms = ("plain", "guided") if repeat % 2 == 0 else ("guided", "plain")
                for arm in arms:
                    trial = agent_trial(
                        case, arm, observed, case_dir / f"{arm}_{repeat + 1}",
                        provider=args.provider, model=args.model,
                        max_steps=args.max_steps, timeout=args.timeout)
                    result["rows"].append(score({**trial, "case": case["id"],
                                                 "repeat": repeat + 1}, truth))
                    print(f"{case['id']} {repeat + 1} {arm}: "
                          f"{trial['prediction']}"
                          + (f" ERROR {trial['error']}" if trial["error"] else ""), flush=True)
            result["summary"] = summarize(result["rows"])
            write_json(output / "results.json", result)
            (output / "REPORT.md").write_text(report(result), encoding="utf-8")
    print(f"Results: {output}", flush=True)
    print(json.dumps(result["summary"], indent=2), flush=True)
    return int(any(row["error"] for row in result["rows"]))


if __name__ == "__main__":
    raise SystemExit(main())

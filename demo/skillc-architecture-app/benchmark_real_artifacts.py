"""Benchmark SkillC on every real SKILL.md, agent.md, and prompt artifact.

Each artifact is checked twice with the deterministic frontend:

* home runtime: the runtime it was written for (`claude-code` for SKILL.md,
  `vscode-copilot` for Copilot agents and prompts);
* observed environment: the cached `skillc.env` snapshot used by the app.

Compilation uses the environment's profile, then requirement binding removes
any capability the environment does not grant, so a tool merely declared in an
artifact's frontmatter cannot grant itself.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent
REPO_ROOT = APP_ROOT.parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

import refutation_audit
from environment_inventory import EnvironmentInventory
from real_artifacts import balanced_subset, load_real_artifacts
from skillc import compile_markdown, load_profile
from skillc.cli import check_compiled
from skillc.frontend.grants import bind_grants
from skillc.pack import PackError
from skillc.profiles import Profile

VERDICTS = ("ACHIEVABLE", "IMPOSSIBLE", "UNKNOWN", "ERROR")


def observed_profile(state_dir: Path) -> tuple[Profile, str | None]:
    snapshot = EnvironmentInventory(REPO_ROOT, state_dir, 0).snapshot()
    grants = frozenset(snapshot["grants"])
    return Profile(name="observed", tools=grants, shell="bash" in grants), snapshot["captured_at"]


def compact(artifact: dict, profile: Profile, llm_model: str | None = None):
    """(pack, CompileResult or None) for one artifact, or the frontend error."""
    try:
        if llm_model:
            from skillc.frontend.llm import compact as llm_compact

            vocabulary = {"tools": {tool: "" for tool in sorted(profile.tools)}, "states": {}}
            return llm_compact(artifact["content"], model=llm_model,
                               provider="azure-openai", vocabulary=vocabulary), None
        compiled = compile_markdown(artifact["content"], profile)
        return compiled.pack, compiled
    except (PackError, ValueError, RuntimeError, RecursionError) as error:
        return error


def decide(compaction, profile: Profile, source_text: str | None = None) -> dict:
    """Bind a compaction to an environment profile and check it."""
    row = {"verdict": "ERROR", "reason": "", "frontier": [], "invoked": [],
           "goal_source": ""}
    if isinstance(compaction, Exception):
        row["reason"] = f"{type(compaction).__name__}: {compaction}"[:200]
        return row
    pack, compiled = compaction
    try:
        grants = set(profile.tools) | ({"bash"} if profile.shell else set())
        binding = bind_grants(pack, grants)
        verdict = check_compiled(binding.pack, compiled, source_text=source_text)
    except (PackError, ValueError, RecursionError) as error:
        row["reason"] = f"{type(error).__name__}: {error}"[:200]
        return row
    row.update(
        verdict=verdict.label,
        reason=verdict.reason,
        frontier=list(verdict.frontier),
        invoked=sorted({inv.tool for inv in compiled.invocations}) if compiled else [],
        goal_source=compiled.goal_source if compiled else "llm",
    )
    return row


def evaluate(artifact: dict, profile: Profile) -> dict:
    return decide(compact(artifact, profile), profile, artifact["content"])


def run(data_root: Path, state_dir: Path, llm_model: str | None = None,
        balanced_only: bool = False, workers: int = 6, per_kind: int | None = None,
        reuse: dict | None = None) -> dict:
    artifacts, excluded = load_real_artifacts(data_root)
    balanced_ids = {item["sha256"] for item in balanced_subset(artifacts)}
    if balanced_only or per_kind:
        artifacts = [a for a in artifacts if a["sha256"] in balanced_ids]
    if per_kind:
        ordered = sorted(artifacts, key=lambda a: a["sha256"])
        artifacts = [a for kind in sorted({a["kind"] for a in ordered})
                     for a in [x for x in ordered if x["kind"] == kind][:per_kind]]
    observed, captured_at = observed_profile(state_dir)
    homes = {name: load_profile(name) for name in {a["home_runtime"] for a in artifacts}}
    if reuse is not None:
        # Re-check stored LLM packs: isolates checker changes from LLM variance.
        artifacts = [a for a in artifacts if (a["kind"], a["id"]) in reuse]
        compactions = [
            (reuse[(a["kind"], a["id"])], None) if reuse[(a["kind"], a["id"])] is not None
            else ValueError("no stored compaction") for a in artifacts]
    elif llm_model:
        from concurrent.futures import ThreadPoolExecutor

        # One LLM compaction per artifact, in parallel; z3 checks stay sequential.
        with ThreadPoolExecutor(max_workers=workers) as pool:
            compactions = list(pool.map(
                lambda a: compact(a, homes[a["home_runtime"]], llm_model), artifacts))
    rows = []
    for index, artifact in enumerate(artifacts):
        provenance = {key: value for key, value in artifact.items()
                      if key not in {"content", "actual_sha256"}}
        home = homes[artifact["home_runtime"]]
        if llm_model or reuse is not None:
            shared, text = compactions[index], artifact["content"]
            row = {**provenance, "home": decide(shared, home, text),
                   "observed": decide(shared, observed, text)}
            row["compacted_pack"] = None if isinstance(shared, Exception) else shared[0]
        else:
            row = {**provenance, "home": evaluate(artifact, home),
                   "observed": evaluate(artifact, observed)}
        rows.append(row)
    real_tools = set().union(*(profile.tools for profile in homes.values()))
    labels = refutation_audit.load_labels()
    for row in rows:
        row["balanced"] = row["sha256"] in balanced_ids
        for environment in ("home", "observed"):
            row[environment]["audit"] = refutation_audit.classify(
                row[environment], real_tools, labels)
    return {
        "schema": "skillc.real-artifact-benchmark/1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "frontend": f"llm:{llm_model}" if llm_model else "deterministic",
        "environments": {
            "home": {name: sorted(profile.tools) for name, profile in homes.items()},
            "observed": {"captured_at": captured_at, "grants": sorted(observed.tools)},
        },
        "summary": {
            "all": summarize(rows),
            "balanced": summarize([row for row in rows if row["balanced"]]),
        },
        "integrity_exclusions": excluded,
        "rows": rows,
    }


def summarize(rows: list[dict]) -> dict:
    kinds = sorted({row["kind"] for row in rows})
    summary = {"counts": {kind: sum(r["kind"] == kind for r in rows) for kind in kinds}}
    for environment in ("home", "observed"):
        summary[environment] = {
            kind: {
                "verdicts": _count(r[environment]["verdict"] for r in rows if r["kind"] == kind),
                "reasons": _count(r[environment]["reason"] for r in rows
                                  if r["kind"] == kind and r[environment]["verdict"] != "ACHIEVABLE"),
                "top_missing": Counter(
                    tool for r in rows if r["kind"] == kind
                    for tool in r[environment]["frontier"]
                    if r[environment]["reason"] == "MISSING_CAPABILITY"
                ).most_common(10),
                "refutation_audit": refutation_audit.summarize(
                    [r[environment]["audit"] for r in rows
                     if r["kind"] == kind and r[environment]["audit"]]),
            }
            for kind in kinds
        }
    return summary


def _count(values) -> dict:
    counts = Counter(values)
    return {key: counts[key] for key in sorted(counts, key=_verdict_order)}


def _verdict_order(value: str):
    return (VERDICTS.index(value) if value in VERDICTS else len(VERDICTS), value)


def render_markdown(report: dict) -> str:
    lines = [
        "# Real artifact benchmark",
        "",
        f"Generated {report['generated_at']} with the {report['frontend']} frontend.",
        f"Observed environment snapshot: {report['environments']['observed']['captured_at']}.",
        "",
    ]
    for scope, title in (("balanced", "Balanced headline"), ("all", "All real artifacts")):
        summary = report["summary"][scope]
        lines += [f"## {title}", "", f"Counts: {summary['counts']}", ""]
        for environment in ("home", "observed"):
            lines += [
                f"### {environment.capitalize()} environment", "",
                "| Kind | ACHIEVABLE | IMPOSSIBLE | UNKNOWN | ERROR "
                "| Confirmed refutations | False refutations | Refutation precision |",
                "|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
            for kind, data in summary[environment].items():
                counts = [str(data["verdicts"].get(v, 0)) for v in VERDICTS]
                audit = data["refutation_audit"]
                precision = "n/a" if audit["precision"] is None else f"{audit['precision']:.1%}"
                lines.append(
                    f"| {kind} | " + " | ".join(counts)
                    + f" | {audit['confirmed']} | {audit['false_refutation']} | {precision} |")
            lines.append("")
            for kind, data in summary[environment].items():
                if data["top_missing"]:
                    missing = ", ".join(f"`{tool}` ({n})" for tool, n in data["top_missing"])
                    lines.append(f"- {kind} most frequently missing: {missing}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-root", type=Path, required=True,
                        help="checkout of gc/data_train_test")
    parser.add_argument("--environment-state-dir", type=Path,
                        default=REPO_ROOT / ".skillc" / "env")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--llm", metavar="DEPLOYMENT",
                        help="compact with this Azure OpenAI deployment (needs "
                             "AZURE_OPENAI_ENDPOINT); one compaction per artifact")
    parser.add_argument("--balanced-only", action="store_true",
                        help="only the balanced subset (equal count per kind)")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--per-kind", type=int,
                        help="pilot: only the first N balanced artifacts of each kind")
    parser.add_argument("--reuse", type=Path,
                        help="re-check the compacted packs stored in an earlier LLM "
                             "results file instead of calling the LLM again")
    args = parser.parse_args()
    reuse = None
    if args.reuse:
        stored = json.loads(args.reuse.read_text(encoding="utf-8"))
        reuse = {(row["kind"], row["id"]): row.get("compacted_pack") for row in stored["rows"]}
        args.llm = args.llm or stored.get("frontend", "").removeprefix("llm:")
    suffix = "-llm" if args.llm else ""
    output = args.output or APP_ROOT / f"real-benchmark-results{suffix}.json"
    report = run(args.data_root, args.environment_state_dir, args.llm,
                 args.balanced_only, args.workers, args.per_kind, reuse)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")
    for scope in ("balanced", "all"):
        summary = report["summary"][scope]
        print(f"[{scope}] {summary['counts']}")
        for environment in ("home", "observed"):
            print(f"  {environment}: " + "; ".join(
                f"{kind} {data['verdicts']}" for kind, data in summary[environment].items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

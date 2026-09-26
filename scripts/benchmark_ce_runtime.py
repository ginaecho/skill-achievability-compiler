"""Evaluate runtime-bound CE compaction against execution-labelled rejections.

Plan and success criteria: runs/20260926_ce_ab/RUNTIME_BINDING_PLAN.md.

  prepare OUT   freeze prompts for the dev, control and labelled sets
  retry OUT     freeze one located-error retry per invalid reply
  score OUT     parse, bind, check; compare with the A/B arms on the same cases

The method under test is selected by --method (ce_rt = P1; later proposals
reuse the same sets and labels).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from scripts.benchmark_ce import (CE_SYSTEM_NOTE, VARIANTS, assess, mcnemar_exact,  # noqa: E402
                                  score, sha, wilson, write_json)
from skillc import check  # noqa: E402
from skillc.frontend.ce import CEError, extract_ce, parse_ce_detailed  # noqa: E402
from skillc.frontend.llm import (CE_REPAIR_PROMPT, CE_RETRY_PROMPT,  # noqa: E402
                                 ce_runtime_messages, explain_refutation)
from skillc.frontend.runtime import bind_runtime, load_runtime  # noqa: E402
from skillc.pack import PackError, validate_pack  # noqa: E402

AB = ROOT / "runs" / "20260926_ce_ab"
SOURCES = ROOT / "benchmark" / "ce_sources"
LABELLED_RUN = ROOT / "runs" / "20260921_114226Z_compaction_comparison"
RUNTIME = "developer-sandbox"
EXTRA_DEV = ["obra__superpowers__requesting-code-review"]
L2_CONFIRMING = {"missing_tool_in_runtime", "needs_credentials_or_account",
                 "forbidden_by_safety_rules"}


def _cases() -> list[dict]:
    labels = json.loads((AB / "adjudication.json").read_text())["labels"]
    dev = sorted(set(labels) | set(EXTRA_DEV))
    rows = json.loads((AB / "results.json").read_text())
    s0 = {(r["case"], r["arm"]): r for r in rows if r["set"] == "real" and r["sample"] == 0}
    both_ok = sorted({c for (c, _) in s0
                      if c not in dev
                      and s0[(c, "json")].get("verdict") == "ACHIEVABLE"
                      and s0[(c, "ce")].get("verdict") == "ACHIEVABLE"},
                     key=lambda c: sha("ctrl:" + c))[:50]
    cases = [{"id": c, "set": "dev"} for c in dev]
    cases += [{"id": c, "set": "control"} for c in both_ok]
    frozen = json.loads((LABELLED_RUN / "frozen.json").read_text())
    cases += [{"id": sc["id"], "set": "labelled", "source": sc["source"],
               "profile": sc["profile"], "category": sc["category"],
               "truth": sc["truth"]} for sc in frozen["scenarios"]]
    return cases


def prepare(out: Path, method: str) -> None:
    out.mkdir(parents=True, exist_ok=False)
    rt = load_runtime(RUNTIME)
    jobs = []
    cases = _cases()
    for case in cases:
        if case["set"] == "labelled":
            text = (LABELLED_RUN / case["id"] / "input.md").read_text(encoding="utf-8")
            system, _ = ce_runtime_messages("", rt)
            prompt = {"system": system + CE_SYSTEM_NOTE, "user": text}
            for f in ("contract.json", "oracle.json"):
                target = out / "labelled" / case["id"] / f
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((LABELLED_RUN / case["id"] / f).read_bytes())
        else:
            text = (SOURCES / case["id"] / "SKILL.md").read_text(encoding="utf-8")
            system, user = ce_runtime_messages(text, rt)
            prompt = {"system": system, "user": user}
        rel = f"prompts/{method}/{case['id']}__s0.json"
        write_json(out / rel, prompt)
        jobs.append({"case": case["id"], "arm": method, "sample": 0, "round": 1,
                     "prompt": rel, "output": f"outputs/{method}/{case['id']}__s0.txt",
                     "prompt_sha256": sha((out / rel).read_bytes())})
    impl = {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in
            [ROOT / "src/skillc/frontend/ce.py", ROOT / "src/skillc/frontend/llm.py",
             ROOT / "src/skillc/frontend/runtime.py", ROOT / "src/skillc/checker.py",
             ROOT / f"src/skillc/data/runtimes/{RUNTIME}.json",
             ROOT / "scripts/benchmark_ce_runtime.py"]}
    write_json(out / "frozen.json", {
        "created_utc": datetime.now(timezone.utc).isoformat(), "method": method,
        "runtime": RUNTIME, "cases": cases, "jobs": jobs,
        "implementation_sha256": impl})
    print(f"prepared {len(cases)} cases ({Counter(c['set'] for c in cases)}) in {out}")


def parse_reply(case: dict, text: str, rt) -> dict:
    try:
        parsed = parse_ce_detailed(extract_ce(text))
        if case["set"] == "labelled":          # Gamma comes from the contract
            validate_pack(parsed.pack)
            return {"ok": True, "pack": parsed.pack, "withdrawn": {}, "blocked": {}}
        b = bind_runtime(parsed.pack, parsed.bindings, rt)
        return {"ok": True, "pack": b.pack, "withdrawn": b.withdrawn,
                "blocked": b.blocked}
    except (PackError, CEError, ValueError, KeyError, TypeError) as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def retry(out: Path) -> None:
    frozen = json.loads((out / "frozen.json").read_text())
    rt = load_runtime(RUNTIME)
    cases = {c["id"]: c for c in frozen["cases"]}
    new = []
    for job in [j for j in frozen["jobs"] if j["round"] == 1]:
        reply = (out / job["output"]).read_text(encoding="utf-8")
        parsed = parse_reply(cases[job["case"]], reply, rt)
        if parsed["ok"]:
            continue
        prompt = json.loads((out / job["prompt"]).read_text())
        rel = job["prompt"].replace(".json", "__r2.json")
        write_json(out / rel, {"system": prompt["system"], "user": prompt["user"]
                               + CE_RETRY_PROMPT.format(error=parsed["error"],
                                                        text=reply.strip())})
        new.append({**job, "round": 2, "prompt": rel,
                    "output": job["output"].replace(".txt", "__r2.txt"),
                    "prompt_sha256": sha((out / rel).read_bytes())})
    frozen["jobs"] = [j for j in frozen["jobs"] if j["round"] == 1] + new
    write_json(out / "frozen.json", frozen)
    print(f"{len(new)} retry jobs")


class _B:  # the Binding fields explain_refutation reads
    def __init__(self, withdrawn, blocked):
        self.withdrawn, self.blocked = withdrawn, blocked


def repair(out: Path) -> None:
    """P2: one counterexample-guided repair round for every real case whose
    current final reply is refuted (protocol scope)."""
    frozen = json.loads((out / "frozen.json").read_text())
    rt = load_runtime(RUNTIME)
    cases = {c["id"]: c for c in frozen["cases"]}
    last: dict = {}
    for job in sorted(frozen["jobs"], key=lambda j: j["round"]):
        last[job["case"]] = job
    new = []
    for cid, job in sorted(last.items()):
        case = cases[cid]
        if case["set"] == "labelled" or job["round"] >= 3:
            continue
        reply = (out / job["output"]).read_text(encoding="utf-8")
        parsed = parse_reply(case, reply, rt)
        if not parsed["ok"]:
            continue
        v = check(parsed["pack"])
        if v.label != "IMPOSSIBLE":
            continue
        base = json.loads((out / f"prompts/{frozen['method']}/{cid}__s0.json").read_text())
        rel = f"prompts/{frozen['method']}/{cid}__s0__r3.json"
        write_json(out / rel, {"system": base["system"], "user": base["user"]
                               + CE_REPAIR_PROMPT.format(
                                   explanation=explain_refutation(
                                       v, _B(parsed["withdrawn"], parsed["blocked"])),
                                   text=extract_ce(reply).strip())})
        new.append({**job, "round": 3, "prompt": rel,
                    "output": f"outputs/{frozen['method']}/{cid}__s0__r3.txt",
                    "prompt_sha256": sha((out / rel).read_bytes())})
    frozen["jobs"] += new
    frozen["repair_round"] = True
    write_json(out / "frozen.json", frozen)
    print(f"{len(new)} repair jobs")


def _labels() -> dict:
    labels = json.loads((AB / "adjudication.json").read_text())["labels"]
    extra = ROOT / "runs" / "20260926_ce_runtime_execution.json"
    if extra.exists():
        labels.update(json.loads(extra.read_text()))
    return labels


def _label(entry: dict, scheme: str) -> str:
    if entry["label"] == "ACHIEVABLE":
        return "ACHIEVABLE"
    if scheme == "L1":
        return entry["label"]
    return "CONFIRMED" if entry.get("blocker_kind") in L2_CONFIRMING else "INCONCLUSIVE"


def _precision(case_ids: list, labels: dict, scheme: str) -> dict:
    c = Counter(_label(labels[i], scheme) if i in labels else "UNEXECUTED"
                for i in case_ids)
    conf, fp = c["CONFIRMED"], c["ACHIEVABLE"]
    return {"rejections": len(case_ids), "correct": conf, "false": fp,
            "inconclusive": c["INCONCLUSIVE"], "unexecuted": c["UNEXECUTED"],
            "precision_decided": f"{conf}/{conf + fp}",
            "precision_value": round(conf / (conf + fp), 4) if conf + fp else None,
            "ci95": wilson(conf, conf + fp)}


def score_all(out: Path) -> None:
    frozen = json.loads((out / "frozen.json").read_text())
    method = frozen["method"]
    rt = load_runtime(RUNTIME)
    cases = {c["id"]: c for c in frozen["cases"]}
    final: dict = {}
    for job in sorted(frozen["jobs"], key=lambda j: j["round"]):
        if sha((out / job["prompt"]).read_bytes()) != job["prompt_sha256"]:
            raise ValueError(f"prompt changed: {job['prompt']}")
        reply = (out / job["output"]).read_text(encoding="utf-8")
        parsed = parse_reply(cases[job["case"]], reply, rt)
        rec = final.setdefault(job["case"], {"rounds": 0})
        rec["rounds"] = job["round"]
        if job["round"] == 1:
            rec["valid_first"] = parsed["ok"]
        if job["round"] == 3 and not parsed["ok"]:
            rec["repair_invalid"] = parsed["error"]   # keep the pre-repair pack
            continue
        if job["round"] == 3:
            rec["repaired"] = True
        rec.update(parsed)
    rows = []
    for cid, rec in sorted(final.items()):
        case = cases[cid]
        row = {"case": cid, "set": case["set"], "valid_first": rec["valid_first"],
               "valid": rec["ok"], "rounds": rec["rounds"], "error": rec.get("error"),
               "repaired": rec.get("repaired", False),
               "repair_invalid": rec.get("repair_invalid")}
        if rec["ok"] and case["set"] != "labelled":
            v, g = check(rec["pack"]), check(rec["pack"], scope="goal")
            row.update({"verdict": v.label, "reason": v.reason,
                        "frontier": [str(x) for x in v.frontier],
                        "goal_only_verdict": g.label,
                        "withdrawn": rec["withdrawn"], "blocked": rec["blocked"]})
            write_json(out / "packs" / method / f"{cid}.json", rec["pack"])
        elif rec["ok"]:
            write_json(out / "packs" / method / f"{cid}.json", rec["pack"])
        rows.append(row)
    write_json(out / "results.json", rows)

    labels = _labels()
    ab = json.loads((AB / "results.json").read_text())
    ab0 = {(r["case"], r["arm"]): r for r in ab if r["set"] == "real" and r["sample"] == 0}
    dev = [r for r in rows if r["set"] == "dev"]
    metrics: dict = {"method": method, "validity": {
        s: {"cases": sum(r["set"] == s for r in rows),
            "valid_first": sum(r["valid_first"] for r in rows if r["set"] == s),
            "valid_final": sum(r["valid"] for r in rows if r["set"] == s)}
        for s in ("dev", "control", "labelled")}}
    comp: dict = {}
    for scope in ("verdict", "goal_only_verdict"):
        for scheme in ("L1", "L2"):
            key = f"{scope}/{scheme}"
            comp[key] = {method: _precision([r["case"] for r in dev
                                             if r.get(scope) == "IMPOSSIBLE"], labels, scheme)}
            for arm in ("json", "ce"):
                comp[key][arm] = _precision(
                    [r["case"] for r in dev if ab0.get((r["case"], arm), {}).get(scope)
                     == "IMPOSSIBLE"], labels, scheme)
    metrics["dev_rejection_precision"] = comp
    # correct (L1) rejections retained
    l1_correct = [c for c, v in labels.items() if v["label"] == "CONFIRMED"]
    metrics["l1_correct_retained"] = {
        c: next((r.get("verdict") for r in dev if r["case"] == c), None) for c in l1_correct}
    # paired false-rejection comparison on dev skills execution proved achievable
    achieved = [c for c, v in labels.items() if v["label"] == "ACHIEVABLE"]
    newv = {r["case"]: r.get("verdict") for r in dev}
    for arm in ("json", "ce"):
        b = sum(ab0[(c, arm)].get("verdict") == "IMPOSSIBLE" and newv.get(c) != "IMPOSSIBLE"
                for c in achieved)
        w = sum(ab0[(c, arm)].get("verdict") != "IMPOSSIBLE" and newv.get(c) == "IMPOSSIBLE"
                for c in achieved)
        metrics[f"false_rejections_on_achieved_vs_{arm}"] = {
            "achieved_skills": len(achieved),
            f"{arm}_false": sum(ab0[(c, arm)].get("verdict") == "IMPOSSIBLE" for c in achieved),
            f"{method}_false": sum(newv.get(c) == "IMPOSSIBLE" for c in achieved),
            "fixed": b, "introduced": w, "mcnemar_p": mcnemar_exact(b, w)}
    ctrl = [r for r in rows if r["set"] == "control"]
    metrics["control"] = {
        "cases": len(ctrl), "verdicts": dict(Counter(r.get("verdict") for r in ctrl)),
        "new_rejections": sorted(r["case"] for r in ctrl if r.get("verdict") == "IMPOSSIBLE"),
        "new_rejection_labels": {r["case"]: labels.get(r["case"], {}).get("label", "UNEXECUTED")
                                 for r in ctrl if r.get("verdict") == "IMPOSSIBLE"}}
    lab_rows = []
    for r in rows:
        if r["set"] != "labelled":
            continue
        case = cases[r["case"]]
        scen = {k: case[k] for k in ("source", "profile", "category", "truth")}
        scen["id"] = case["id"]
        if r["valid"]:
            pack = json.loads((out / "packs" / method / f"{r['case']}.json").read_text())
            contract = json.loads((out / "labelled" / r["case"] / "contract.json").read_text())
            lab_rows.extend(assess(pack, contract, scen, method, method))
        else:
            lab_rows += [{**scen, "mode": method, "variant": v, "predicted": "UNKNOWN",
                          "reason": "COMPACTION_ERROR"} for v in VARIANTS]
    metrics["labelled"] = {v: score([x for x in lab_rows if x["variant"] == v])
                           for v in VARIANTS}
    write_json(out / "metrics.json", metrics)
    print(json.dumps({k: metrics[k] for k in metrics if k != "labelled"}, indent=1))
    print(json.dumps({v: {k: metrics["labelled"][v][k] for k in ("tp", "fp", "fn", "tn")}
                      for v in VARIANTS}))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("out", type=Path)
    p.add_argument("--method", default="ce_rt")
    for name in ("retry", "repair", "score"):
        sub.add_parser(name).add_argument("out", type=Path)
    a = ap.parse_args()
    {"prepare": lambda: prepare(a.out, a.method), "retry": lambda: retry(a.out),
     "repair": lambda: repair(a.out), "score": lambda: score_all(a.out)}[a.cmd]()


if __name__ == "__main__":
    main()

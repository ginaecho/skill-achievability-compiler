"""Evaluate runtime-bound CE compaction against execution-labelled rejections.

Plan and success criteria: runs/20260926_ce_ab/RUNTIME_BINDING_PLAN.md.

  prepare OUT   freeze prompts for the dev, control and labelled sets
                (--cases heldout: 40 fresh real skills never compacted before)
  retry OUT     freeze one located-error retry per invalid reply
  repair OUT    freeze one counterexample-guided repair per refuted real case
  score OUT     parse, bind, check; compare with the A/B arms on the same cases

--method: ce_rt (P1/P2: runtime-bound CE), ce_lv (P3: runtime-bound CE with
two goal levels; the binder prunes the agent's unrunnable branches) or json
(the original JSON compaction, as a baseline on the held-out set).
P3 plan: runs/20260926_ce_runtime_p1/P3_PLAN.md.
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

from scripts.benchmark_ce import (CE_SYSTEM_NOTE, JSON_RETRY, VARIANTS, assess,  # noqa: E402
                                  mcnemar_exact, real_prompt, score, select_real, sha,
                                  wilson, write_json)
from skillc import check  # noqa: E402
from skillc.frontend.ce import CEError, extract_ce, parse_ce_detailed  # noqa: E402
from skillc.frontend.llm import (CE_REPAIR_PROMPT, CE_RETRY_PROMPT,  # noqa: E402
                                 _extract_json_object, ce_runtime_messages,
                                 explain_refutation)
from skillc.frontend.runtime import (bind_runtime, check_levels, load_runtime,  # noqa: E402
                                     repair_violations)
from skillc.pack import PackError, validate_pack  # noqa: E402

AB = ROOT / "runs" / "20260926_ce_ab"
SOURCES = ROOT / "benchmark" / "ce_sources"
LABELLED_RUN = ROOT / "runs" / "20260921_114226Z_compaction_comparison"
RUNTIME = "developer-sandbox"
EXTRA_DEV = ["obra__superpowers__requesting-code-review"]
L2_CONFIRMING = {"missing_tool_in_runtime", "needs_credentials_or_account",
                 "forbidden_by_safety_rules"}


N_HELDOUT = 40


def _heldout() -> list[dict]:
    """The next 40 skills of the A/B's own stratified order (select_real):
    none was compacted, executed or inspected before P3 was frozen."""
    ab = {r["case"] for r in json.loads((AB / "results.json").read_text())}
    picked = [s for s in select_real(10_000) if s["id"] not in ab][:N_HELDOUT]
    return [{"id": s["id"], "set": "heldout"} for s in picked]


def _cases(case_set: str = "dev") -> list[dict]:
    if case_set == "heldout":
        return _heldout()
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


def prepare(out: Path, method: str, case_set: str = "dev") -> None:
    out.mkdir(parents=True, exist_ok=False)
    rt = load_runtime(RUNTIME)
    levels = method == "ce_lv"
    jobs = []
    cases = _cases(case_set)
    if method == "json":
        cases = [c for c in cases if c["set"] != "labelled"]
    for case in cases:
        if case["set"] == "labelled":
            text = (LABELLED_RUN / case["id"] / "input.md").read_text(encoding="utf-8")
            system, _ = ce_runtime_messages("", rt, levels=levels)
            prompt = {"system": system + CE_SYSTEM_NOTE, "user": text}
            for f in ("contract.json", "oracle.json"):
                target = out / "labelled" / case["id"] / f
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((LABELLED_RUN / case["id"] / f).read_bytes())
        else:
            text = (SOURCES / case["id"] / "SKILL.md").read_text(encoding="utf-8")
            if method == "json":
                prompt = real_prompt("json", text)
            else:
                system, user = ce_runtime_messages(text, rt, levels=levels)
                prompt = {"system": system, "user": user}
        rel = f"prompts/{method}/{case['id']}__s0.json"
        write_json(out / rel, prompt)
        jobs.append({"case": case["id"], "arm": method, "sample": 0, "round": 1,
                     "prompt": rel, "output": f"outputs/{method}/{case['id']}__s0.txt",
                     "prompt_sha256": sha((out / rel).read_bytes())})
    impl = {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in
            [ROOT / "src/skillc/frontend/ce.py", ROOT / "src/skillc/frontend/llm.py",
             ROOT / "scripts/benchmark_ce.py",
             ROOT / "src/skillc/frontend/runtime.py", ROOT / "src/skillc/checker.py",
             ROOT / f"src/skillc/data/runtimes/{RUNTIME}.json",
             ROOT / "scripts/benchmark_ce_runtime.py"]}
    write_json(out / "frozen.json", {
        "created_utc": datetime.now(timezone.utc).isoformat(), "method": method,
        "runtime": RUNTIME, "case_set": case_set, "prune": method == "ce_lv",
        "cases": cases, "jobs": jobs,
        "implementation_sha256": impl})
    print(f"prepared {len(cases)} cases ({Counter(c['set'] for c in cases)}) in {out}")


def parse_reply(case: dict, text: str, rt, method: str = "ce_rt",
                prune: bool = False) -> dict:
    try:
        if method == "json":
            pack = _extract_json_object(text)
            validate_pack(pack)
            return {"ok": True, "pack": pack, "withdrawn": {}, "blocked": {},
                    "pruned": [], "parsed": None, "live_goal": None}
        parsed = parse_ce_detailed(extract_ce(text))
        if case["set"] == "labelled":          # Gamma comes from the contract
            validate_pack(parsed.pack)
            return {"ok": True, "pack": parsed.pack, "withdrawn": {}, "blocked": {},
                    "pruned": [], "parsed": parsed, "live_goal": parsed.live_goal}
        b = bind_runtime(parsed.pack, parsed.bindings, rt, prune=prune)
        return {"ok": True, "pack": b.pack, "withdrawn": b.withdrawn,
                "blocked": b.blocked, "pruned": b.pruned, "parsed": parsed,
                "live_goal": parsed.live_goal}
    except (PackError, CEError, ValueError, KeyError, TypeError) as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def retry(out: Path) -> None:
    frozen = json.loads((out / "frozen.json").read_text())
    rt = load_runtime(RUNTIME)
    cases = {c["id"]: c for c in frozen["cases"]}
    new = []
    method, prune = frozen["method"], frozen.get("prune", False)
    for job in [j for j in frozen["jobs"] if j["round"] == 1]:
        reply = (out / job["output"]).read_text(encoding="utf-8")
        parsed = parse_reply(cases[job["case"]], reply, rt, method, prune)
        if parsed["ok"]:
            continue
        prompt = json.loads((out / job["prompt"]).read_text())
        rel = job["prompt"].replace(".json", "__r2.json")
        tail = (JSON_RETRY.format(text=reply.strip(), error=parsed["error"])
                if method == "json" else
                CE_RETRY_PROMPT.format(error=parsed["error"], text=reply.strip()))
        write_json(out / rel, {"system": prompt["system"], "user": prompt["user"] + tail})
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
    if frozen["method"] == "json":
        raise ValueError("the original JSON method has no repair round")
    rt = load_runtime(RUNTIME)
    prune = frozen.get("prune", False)
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
        parsed = parse_reply(case, reply, rt, frozen["method"], prune)
        if not parsed["ok"]:
            continue
        v = check(parsed["pack"])            # the core Goal's verdict
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


def score_all(out: Path, guard: bool = True, prune: bool | None = None,
              repair_round: bool = True, tag: str = "") -> None:
    frozen = json.loads((out / "frozen.json").read_text())
    method = frozen["method"]
    if prune is None:
        prune = frozen.get("prune", False)
    rt = load_runtime(RUNTIME)
    cases = {c["id"]: c for c in frozen["cases"]}
    final: dict = {}
    for job in sorted(frozen["jobs"], key=lambda j: j["round"]):
        if sha((out / job["prompt"]).read_bytes()) != job["prompt_sha256"]:
            raise ValueError(f"prompt changed: {job['prompt']}")
        if job["round"] == 3 and not repair_round:
            continue
        reply = (out / job["output"]).read_text(encoding="utf-8")
        parsed = parse_reply(cases[job["case"]], reply, rt, method, prune)
        rec = final.setdefault(job["case"], {"rounds": 0})
        rec["rounds"] = job["round"]
        if job["round"] == 1:
            rec["valid_first"] = parsed["ok"]
        if job["round"] == 3 and not parsed["ok"]:
            rec["repair_invalid"] = parsed["error"]   # keep the pre-repair pack
            continue
        if job["round"] == 3 and guard and rec.get("parsed") is not None:
            bad = repair_violations(rec["parsed"], parsed["parsed"])
            if bad:
                rec["repair_rejected"] = bad          # P2g: keep the refuted pack
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
               "repair_invalid": rec.get("repair_invalid"),
               "repair_rejected": rec.get("repair_rejected")}
        if rec["ok"] and case["set"] != "labelled":
            lv = check_levels(rec["pack"], rec["live_goal"])
            v, g = lv["core"], check(rec["pack"], scope="goal")
            row.update({"verdict": v.label, "reason": v.reason,
                        "frontier": [str(x) for x in v.frontier],
                        "goal_only_verdict": g.label,
                        "live_verdict": lv["live"].label if lv["live"] else None,
                        "live_reason": lv["live"].reason if lv["live"] else None,
                        "withdrawn": rec["withdrawn"], "blocked": rec["blocked"],
                        "pruned": rec["pruned"]})
            write_json(out / "packs" / method / f"{cid}.json", rec["pack"])
        elif rec["ok"]:
            write_json(out / "packs" / method / f"{cid}.json", rec["pack"])
        rows.append(row)
    write_json(out / f"results{tag}.json", rows)
    if not any(r["set"] == "dev" for r in rows):
        print(json.dumps({"rows": len(rows), "verdicts": dict(Counter(
            r.get("verdict") for r in rows))}))
        return

    labels = _labels()
    ab = json.loads((AB / "results.json").read_text())
    ab0 = {(r["case"], r["arm"]): r for r in ab if r["set"] == "real" and r["sample"] == 0}
    dev = [r for r in rows if r["set"] == "dev"]
    metrics: dict = {"method": method, "repair_guard": guard, "prune": prune,
                     "repair_round": repair_round, "validity": {
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
    write_json(out / f"metrics{tag}.json", metrics)
    print(json.dumps({k: metrics[k] for k in metrics if k != "labelled"}, indent=1))
    print(json.dumps({v: {k: metrics["labelled"][v][k] for k in ("tp", "fp", "fn", "tn")}
                      for v in VARIANTS}))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("out", type=Path)
    p.add_argument("--method", default="ce_rt", choices=("ce_rt", "ce_lv", "json"))
    p.add_argument("--cases", default="dev", choices=("dev", "heldout"))
    for name in ("retry", "repair", "score"):
        sub.add_parser(name).add_argument("out", type=Path)
    sc = sub.choices["score"]
    sc.add_argument("--no-guard", action="store_true",
                    help="accept every valid repair (P2) instead of guarded repair (P2g)")
    sc.add_argument("--prune", choices=("yes", "no"),
                    help="override the frozen branch-pruning setting")
    sc.add_argument("--no-repair", action="store_true", help="ignore round 3")
    sc.add_argument("--tag", default="", help="suffix for results/metrics files")
    a = ap.parse_args()
    {"prepare": lambda: prepare(a.out, a.method, a.cases), "retry": lambda: retry(a.out),
     "repair": lambda: repair(a.out),
     "score": lambda: score_all(a.out, guard=not a.no_guard,
                                prune=None if a.prune is None else a.prune == "yes",
                                repair_round=not a.no_repair, tag=a.tag)}[a.cmd]()


if __name__ == "__main__":
    main()

"""Evaluate runtime-bound CE compaction against execution-labelled rejections.

Method and results: docs/P2G_RUNTIME_BINDING.md, docs/LIBRARY_TEST.md.

  prepare OUT   freeze prompts for the dev, control and labelled sets
                (--cases heldout|fresh|ext: real skills never compacted before)
  retry OUT     freeze one located-error retry per invalid reply
  repair OUT    freeze one counterexample-guided repair per refuted real case
  score OUT     parse, bind, check; compare with the A/B arms on the same cases

--method: ce_rt (P1/P2: runtime-bound CE), ce_lv (P3: runtime-bound CE with
two goal levels; the binder prunes the agent's unrunnable branches) or json
(the original JSON compaction, as a baseline on the held-out set).
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
                                 _extract_json_object, ce_grounded_messages,
                                 ce_index_messages,
                                 ce_runtime_messages, ce_tpl_messages,
                                 explain_refutation, render_index_facts)
from skillc.frontend.policyindex import (CLASSES, Mention, PolicyIndex,  # noqa: E402
                                         extract_terms, norm, registry_probe)
from skillc.frontend.toolpolicy import coverage, load_library, match, veto  # noqa: E402
from skillc.frontend.runtime import (bind_runtime, check_levels, load_runtime,  # noqa: E402
                                     repair_violations)
from skillc.pack import PackError, validate_pack  # noqa: E402

AB = ROOT / "runs" / "20260926_ce_ab"
SOURCES = ROOT / "benchmark" / "ce_sources"
SOURCES_EXT = ROOT / "benchmark" / "ce_sources_ext"
LABELLED_RUN = ROOT / "runs" / "20260921_114226Z_compaction_comparison"
RUNTIME = "developer-sandbox"
EXTRA_DEV = ["obra__superpowers__requesting-code-review"]
L2_CONFIRMING = {"missing_tool_in_runtime", "needs_credentials_or_account",
                 "forbidden_by_safety_rules"}


DIV_RUN = ROOT / "runs" / "20260928_div"
N_HELDOUT = 40
N_EXT_NEW = 56


def skill_path(case: dict) -> Path:
    base = ROOT / "benchmark" / case.get("corpus", "ce_sources")
    return base / case.get("skill", case["id"]) / "SKILL.md"


_RUNTIMES: dict = {}


def case_runtime(case: dict, default=None):
    """The runtime a case is judged against (default: developer-sandbox)."""
    name = case.get("runtime", RUNTIME)
    if default is not None and name == default.name:
        return default
    if name not in _RUNTIMES:
        _RUNTIMES[name] = load_runtime(name)
    return _RUNTIMES[name]


def _heldout() -> list[dict]:
    """The next 40 skills of the A/B's own stratified order (select_real):
    none was compacted, executed or inspected before P3 was frozen."""
    ab = {r["case"] for r in json.loads((AB / "results.json").read_text())}
    picked = [s for s in select_real(10_000) if s["id"] not in ab][:N_HELDOUT]
    return [{"id": s["id"], "set": "heldout"} for s in picked]


def _fresh() -> list[dict]:
    """TPL test set: the next 40 skills of the same stratified order after the
    A/B and held-out skills; none was compacted, executed or inspected before
    the TPL plan was committed."""
    used = {r["case"] for r in json.loads((AB / "results.json").read_text())}
    used |= {c["id"] for c in _heldout()}
    picked = [s for s in select_real(10_000) if s["id"] not in used][:N_HELDOUT]
    return [{"id": s["id"], "set": "fresh"} for s in picked]


def _ext() -> list[dict]:
    """Library-v1 test set (docs/LIBRARY_TEST.md): every remaining skill
    of the original corpus (after the A/B, held-out and fresh skills), plus
    56 skills of the extension corpus benchmark/ce_sources_ext, taken
    round-robin over its repositories in a fixed hash order.  None was
    compacted, executed or inspected before the plan was committed."""
    used = {r["case"] for r in json.loads((AB / "results.json").read_text())}
    used |= {c["id"] for c in _heldout()} | {c["id"] for c in _fresh()}
    cases = [{"id": s["id"], "set": "ext", "corpus": "ce_sources"}
             for s in select_real(10_000) if s["id"] not in used]
    groups: dict[str, list] = {}
    for s in sorted(json.loads((SOURCES_EXT / "sources.json").read_text()),
                    key=lambda s: sha("ext-test:" + s["id"])):
        groups.setdefault(s["repo_url"], []).append(s["id"])
    picked: list = []
    while len(picked) < N_EXT_NEW and any(groups.values()):
        for g in sorted(groups):
            if groups[g] and len(picked) < N_EXT_NEW:
                picked.append(groups[g].pop(0))
    return cases + [{"id": i, "set": "ext", "corpus": "ce_sources_ext"} for i in picked]


RUNTIMES_DIV = ("developer-sandbox", "offline-workstation", "office-assistant")


def _div() -> list[dict]:
    """Diversity test set (docs/DIVERSITY_TEST.md), one case per (skill, runtime):
    * the 100 non-developer skills of benchmark/ce_sources_div, each assigned one
      runtime by hash in a 4:3:3 ratio (developer-sandbox, offline-workstation, office-assistant);
    * 50 skills already executed in developer-sandbox (held-out, fresh, ext sets),
      re-judged in offline-workstation (25) or office-assistant (25), taken
      round-robin over repositories in hash order;
    * the 20 created skills of benchmark/ce_sources_created, in their stated runtime."""
    cases = []
    for s in json.loads((ROOT / "benchmark/ce_sources_div/sources.json").read_text()):
        h = int(sha("div-rt:" + s["id"]), 16) % 10
        rt = RUNTIMES_DIV[0 if h < 4 else 1 if h < 7 else 2]
        cases.append({"id": f"{s['id']}@{rt}", "skill": s["id"], "set": "div",
                      "corpus": "ce_sources_div", "runtime": rt, "stratum": "real-nondev",
                      "domain": s["domain"]})
    prior = [dict(c, corpus=c.get("corpus", "ce_sources")) for c in _heldout() + _fresh()]
    prior += _ext()
    groups: dict[str, list] = {}
    for c in sorted(prior, key=lambda c: sha("div-rerun:" + c["id"])):
        groups.setdefault(c["id"].split("__")[0], []).append(c)
    picked: list = []
    while len(picked) < 50 and any(groups.values()):
        for g in sorted(groups):
            if groups[g] and len(picked) < 50:
                picked.append(groups[g].pop(0))
    for i, c in enumerate(picked):
        rt = RUNTIMES_DIV[1 + i % 2]
        cases.append({"id": f"{c['id']}@{rt}", "skill": c["id"], "set": "div",
                      "corpus": c["corpus"], "runtime": rt, "stratum": "real-rerun"})
    for s in json.loads((ROOT / "benchmark/ce_sources_created/sources.json").read_text()):
        cases.append({"id": f"{s['id']}@{s['runtime']}", "skill": s["id"], "set": "div",
                      "corpus": "ce_sources_created", "runtime": s["runtime"],
                      "stratum": "created"})
    return cases


def _gr() -> list[dict]:
    """Fresh test set for P2g-grounded (runs/20261001_gr/PLAN.md): the 50 skills of
    benchmark/ce_sources_gr plus 35 not-yet-used skills from each of ce_sources and
    ce_sources_ext (sha256("gr-pick:" + id) order); each skill gets one runtime by
    sha256("gr-rt:" + id) mod 3."""
    used = set()
    for cs in ("dev", "heldout", "fresh", "ext", "div"):
        used |= {c.get("skill", c["id"]) for c in _cases(cs, "ce_rt")}
    picks = [(s["id"], "ce_sources_gr", "real-nondev") for s in
             json.loads((ROOT / "benchmark/ce_sources_gr/sources.json").read_text())]
    for corpus in ("ce_sources", "ce_sources_ext"):
        ids = sorted((p.parent.name for p in (ROOT / "benchmark" / corpus).glob("*/SKILL.md")
                      if p.parent.name not in used), key=lambda i: sha("gr-pick:" + i))
        picks += [(i, corpus, "real-dev") for i in ids[:35]]
    cases = []
    for sid, corpus, stratum in picks:
        rt = RUNTIMES_DIV[int(sha("gr-rt:" + sid), 16) % 3]
        cases.append({"id": f"{sid}@{rt}", "skill": sid, "set": "gr", "corpus": corpus,
                      "runtime": rt, "stratum": stratum})
    return cases


def _labelled() -> list[dict]:
    frozen = json.loads((LABELLED_RUN / "frozen.json").read_text())
    return [{"id": sc["id"], "set": "labelled", "source": sc["source"],
             "profile": sc["profile"], "category": sc["category"],
             "truth": sc["truth"]} for sc in frozen["scenarios"]]


def _cases(case_set: str = "dev", method: str = "ce_rt") -> list[dict]:
    if case_set == "heldout":
        return _heldout()
    if case_set == "fresh":
        return _fresh() + (_labelled() if method == "ce_tpl" else [])
    if case_set == "ext":
        return _ext()
    if case_set == "div":
        return _div()
    if case_set == "gr":
        return _gr()
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


def preq_batch(case_ids: list[str]) -> dict[str, int]:
    """Prequential batch of each div case: sha256("div-preq:" + id) order, 10 per batch."""
    order = sorted(case_ids, key=lambda i: sha("div-preq:" + i))
    return {cid: k // 10 for k, cid in enumerate(order)}


def build_index(div_cases: set[str]) -> tuple[PolicyIndex, set[str]]:
    """The policy index from labelled execution reports (runs/20260928_div/labels):
    every prior report, plus the div cases in `div_cases`. Returns the index and
    the terms labelled only as non-tools (neither indexed nor "unknown")."""
    idx, seen_false = PolicyIndex(), set()
    for f in sorted((DIV_RUN / "labels" / "out").glob("*.json")):
        if "@" in f.stem and f.stem not in div_cases:
            continue
        item = json.loads((DIV_RUN / "labels" / "items" / f.name).read_text())
        for t in json.loads(f.read_text())["terms"]:
            if t.get("keep"):
                idx.add(Mention(t["term"], t["cls"] if t["cls"] in CLASSES else "none",
                                bool(t.get("core")), item["skill"], item["runtime"],
                                bool(t.get("blocked")), t.get("note") or ""))
            else:
                seen_false.add(norm(t["term"]))
    return idx, seen_false - set(idx.entries)


def index_facts(text: str, idx: PolicyIndex, non_tools: set[str], probes: dict) -> tuple[str, dict]:
    """REFERENCE INDEX section for one skill; `probes` caches registry lookups."""
    look = idx.lookup(text)
    src = {c["term"]: c["source"] for c in extract_terms(text, set(idx.entries))}
    look["unknown"] = [t for t in look["unknown"] if t not in non_tools]
    mine = {}
    for t in look["unknown"]:
        if src.get(t) in ("code", "backtick"):
            if t not in probes:
                probes[t] = registry_probe(t)
            mine[t] = probes[t]
    info = {"known": [k["term"] for k in look["known"]], "unknown": look["unknown"],
            "probes": mine}
    return render_index_facts(look, mine), info


def prepare(out: Path, method: str, case_set: str = "dev") -> None:
    out.mkdir(parents=True, exist_ok=False)
    rt = load_runtime(RUNTIME)
    levels = method == "ce_lv"
    jobs = []
    cases = _cases(case_set, method)
    lib = load_library() if method == "ce_tpl" else None
    if method == "json":
        cases = [c for c in cases if c["set"] != "labelled"]
    if method == "ce_idx":
        if case_set != "div":
            raise ValueError("ce_idx is defined for the div set only")
        batch = preq_batch([c["id"] for c in cases])
        indexes: dict = {}
        probes: dict = {}
    for case in cases:
        if case["set"] == "labelled":
            text = (LABELLED_RUN / case["id"] / "input.md").read_text(encoding="utf-8")
            if lib is not None:
                system, _ = ce_tpl_messages("", rt, [])
            else:
                system, _ = ce_runtime_messages("", rt, levels=levels)
            prompt = {"system": system + CE_SYSTEM_NOTE, "user": text}
            for f in ("contract.json", "oracle.json"):
                target = out / "labelled" / case["id"] / f
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((LABELLED_RUN / case["id"] / f).read_bytes())
        else:
            text = skill_path(case).read_text(encoding="utf-8")
            rt_c = case_runtime(case, rt)
            if method == "json":
                prompt = real_prompt("json", text)
            elif lib is not None:
                obligations = match(text, lib)
                case["obligations"] = [o.__dict__ for o in obligations]
                system, user = ce_tpl_messages(text, rt_c, obligations)
                prompt = {"system": system, "user": user}
            elif method == "ce_gr":
                system, user = ce_grounded_messages(text, rt_c)
                prompt = {"system": system, "user": user}
            elif method == "ce_idx":
                k = batch[case["id"]]
                if k not in indexes:
                    indexes[k] = build_index({c for c, b in batch.items() if b < k})
                idx, non_tools = indexes[k]
                facts, info = index_facts(text, idx, non_tools, probes)
                case["index"] = {"batch": k, "terms": len(idx.entries), **info}
                system, user = ce_index_messages(text, rt_c, facts)
                prompt = {"system": system, "user": user}
            else:
                system, user = ce_runtime_messages(text, rt_c, levels=levels)
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
             ROOT / "src/skillc/frontend/toolpolicy.py",
             ROOT / "src/skillc/frontend/policyindex.py",
             ROOT / "src/skillc/data/toolpolicy/library.json",
             *sorted((ROOT / "src/skillc/data/runtimes").glob("*.json")),
             ROOT / "scripts/benchmark_ce_runtime.py"]}
    write_json(out / "frozen.json", {
        "created_utc": datetime.now(timezone.utc).isoformat(), "method": method,
        "runtime": RUNTIME, "case_set": case_set,
        "prune": method in ("ce_lv", "ce_tpl"),
        "cases": cases, "jobs": jobs,
        "implementation_sha256": impl})
    if method == "ce_idx":
        write_json(out / "index_probes.json", probes)
        (out / "index").mkdir(exist_ok=True)
        for k, (idx, _) in sorted(indexes.items()):
            idx.save(out / "index" / f"batch_{k:02d}.json")
    print(f"prepared {len(cases)} cases ({Counter(c['set'] for c in cases)}) in {out}")


def parse_reply(case: dict, text: str, rt, method: str = "ce_rt",
                prune: bool = False, use_library: bool = True) -> dict:
    rt = case_runtime(case, rt)
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
        lib = load_library() if method == "ce_tpl" and use_library else None
        b = bind_runtime(parsed.pack, parsed.bindings, rt, prune=prune, library=lib,
                         software=method == "ce_gr")
        unmet = []
        if method == "ce_tpl":
            from skillc.frontend.toolpolicy import Obligation
            unmet = coverage(parsed, [Obligation(**o) for o in case.get("obligations", [])])
        return {"ok": True, "pack": b.pack, "withdrawn": b.withdrawn,
                "blocked": b.blocked, "pruned": b.pruned, "parsed": parsed,
                "live_goal": parsed.live_goal, "unmet": unmet}
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
        if parsed["ok"] and not parsed.get("unmet"):
            continue
        if parsed["ok"]:     # TPL: parses, but a library obligation is not covered
            parsed["error"] = ("tool-policy coverage: " + "; ".join(parsed["unmet"])
                               + ". Add the clause to the Tool that does that work "
                               "(on a skippable branch if it is optional)")
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
              repair_round: bool = True, tag: str = "", use_library: bool = True,
              veto_scope: str = "none", grounded: bool | None = None) -> None:
    frozen = json.loads((out / "frozen.json").read_text())
    method = frozen["method"]
    if grounded is None:
        grounded = method == "ce_gr"
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
        parsed = parse_reply(cases[job["case"]], reply, rt, method, prune, use_library)
        rec = final.setdefault(job["case"], {"rounds": 0})
        rec["rounds"] = job["round"]
        if job["round"] == 1:
            rec["valid_first"] = parsed["ok"]
        if job["round"] == 3 and not parsed["ok"]:
            rec["repair_invalid"] = parsed["error"]   # keep the pre-repair pack
            continue
        if job["round"] == 3 and guard and rec.get("parsed") is not None:
            bad = repair_violations(rec["parsed"], parsed["parsed"])
            new_unmet = set(parsed.get("unmet") or []) - set(rec.get("unmet") or [])
            if new_unmet:
                bad = bad + ["a tool-policy obligation is no longer covered"]
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
               "repair_rejected": rec.get("repair_rejected"),
               "unmet_obligations": rec.get("unmet") or []}
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
        if (grounded and row.get("verdict") == "IMPOSSIBLE"
                and not row.get("withdrawn") and not row.get("blocked")):
            # P2g-grounded: a refutation no missing runtime resource witnesses is
            # a structural (compaction) failure, not evidence of impossibility
            row.update({"verdict_before_grounding": "IMPOSSIBLE", "verdict": "UNKNOWN",
                        "reason": "STRUCTURAL:" + str(row.get("reason"))})
        if case["set"] != "labelled" and veto_scope != "none":
            # P2g + library: a deterministic IMPOSSIBLE when the library finds
            # a requirement the runtime cannot meet (in the core statement)
            vetoes = veto(skill_path(case).read_text(encoding="utf-8"), case_runtime(case, rt),
                          load_library(), scope=veto_scope)
            row["veto"] = [f"{o.entry}:{o.clause()} (line {o.line}: {o.text})"
                           for o in vetoes]
            if vetoes:
                row.update({"verdict_before_veto": row.get("verdict"),
                            "verdict": "IMPOSSIBLE", "reason": "LIBRARY_VETO"})
            write_json(out / f"packs{tag}" / method / f"{cid}.json", rec["pack"])
        elif rec["ok"]:
            write_json(out / f"packs{tag}" / method / f"{cid}.json", rec["pack"])
        rows.append(row)
    write_json(out / f"results{tag}.json", rows)
    if not any(r["set"] == "dev" for r in rows):
        lab = [r for r in rows if r["set"] == "labelled"]
        if lab:
            lab_rows = []
            for r in lab:
                case = cases[r["case"]]
                scen = {k: case[k] for k in ("source", "profile", "category", "truth")}
                scen["id"] = case["id"]
                if r["valid"]:
                    pack = json.loads((out / f"packs{tag}" / method / f"{r['case']}.json").read_text())
                    contract = json.loads((out / "labelled" / r["case"] / "contract.json").read_text())
                    lab_rows.extend(assess(pack, contract, scen, method, method))
                else:
                    lab_rows += [{**scen, "mode": method, "variant": v, "predicted": "UNKNOWN",
                                  "reason": "COMPACTION_ERROR"} for v in VARIANTS]
            write_json(out / f"labelled{tag}.json",
                       {v: score([x for x in lab_rows if x["variant"] == v]) for v in VARIANTS})
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
            pack = json.loads((out / f"packs{tag}" / method / f"{r['case']}.json").read_text())
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
    p.add_argument("--method", default="ce_rt", choices=("ce_rt", "ce_lv", "json", "ce_tpl", "ce_idx", "ce_gr"))
    p.add_argument("--cases", default="dev", choices=("dev", "heldout", "fresh", "ext", "div", "gr"))
    for name in ("retry", "repair", "score"):
        sub.add_parser(name).add_argument("out", type=Path)
    sc = sub.choices["score"]
    sc.add_argument("--no-guard", action="store_true",
                    help="accept every valid repair (P2) instead of guarded repair (P2g)")
    sc.add_argument("--prune", choices=("yes", "no"),
                    help="override the frozen branch-pruning setting")
    sc.add_argument("--no-repair", action="store_true", help="ignore round 3")
    sc.add_argument("--tag", default="", help="suffix for results/metrics files")
    sc.add_argument("--no-library", action="store_true",
                    help="TPL ablation: bind without the tool-policy library")
    sc.add_argument("--veto", default="none", choices=("none", "core", "any"),
                    help="P2g + library: IMPOSSIBLE on an unmet library requirement "
                         "(core: stated in the skill's core statement)")
    sc.add_argument("--grounded", choices=("yes", "no"),
                    help="IMPOSSIBLE only when a withdrawn/blocked capability witnesses "
                         "it (default: yes for ce_gr, no otherwise)")
    a = ap.parse_args()
    {"prepare": lambda: prepare(a.out, a.method, a.cases), "retry": lambda: retry(a.out),
     "repair": lambda: repair(a.out),
     "score": lambda: score_all(a.out, guard=not a.no_guard,
                                prune=None if a.prune is None else a.prune == "yes",
                                repair_round=not a.no_repair, tag=a.tag,
                                use_library=not a.no_library,
                                veto_scope=a.veto,
                                grounded=None if a.grounded is None else a.grounded == "yes")}[a.cmd]()


if __name__ == "__main__":
    main()

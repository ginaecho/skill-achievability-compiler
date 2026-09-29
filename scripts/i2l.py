"""I2L: benchmark compaction from intent to logical block (runs/20260928_i2l/PLAN.md).

  prepare-direct            freeze the D prompts (intent -> verdict, no block)
  batches RUN [--size N]    write batches/<round>_NN.json of jobs with no output yet
  blocks                    rebuild every arm's final logical block (pre-binding pack,
                            bindings, binder witnesses, necessity) -> blocks.json
  prepare-judge             blind judge items (canonical rendering + gold terms)
  score                     block, verdict and token metrics -> metrics.json

Arms: J (original JSON), JB (json_rt), P2g (ce_rt + guarded repair), ce_gr (gr only),
D (direct verdict).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from scripts import compare_heldout, score_div  # noqa: E402
from scripts.benchmark_ce import mcnemar_exact, wilson, write_json  # noqa: E402
from scripts.benchmark_ce_runtime import (_cases, case_runtime, parse_reply,  # noqa: E402
                                          skill_path)
from skillc import check  # noqa: E402
from skillc.frontend.ce import render_ce  # noqa: E402
from skillc.frontend.llm import _extract_json_object, direct_messages  # noqa: E402
from skillc.frontend.runtime import load_runtime, repair_violations  # noqa: E402

RUNS = ROOT / "runs"
OUT = RUNS / "20260928_i2l"
ROWS = RUNS / "20260928_div" / "slm" / "rows.jsonl"
# arm -> [(run directory, method)]
ARMS = {
    "J": [("20260926_heldout_json", "json"), ("20260926_tpl/fresh_json", "json")],
    "JB": [("20260928_i2l/jb", "json_rt")],
    "P2g": [("20260926_heldout_ce_rt", "ce_rt"), ("20260926_tpl/fresh_ce_rt", "ce_rt"),
            ("20261001_gr/gr_ce_rt", "ce_rt")],
    "ce_gr": [("20261001_gr/gr_ce_gr", "ce_gr")],
}
BLOCK_ARMS = tuple(ARMS)


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


# ------------------------------------------------------------------ D: direct verdict

def prepare_direct() -> None:
    out = OUT / "direct"
    out.mkdir(parents=True, exist_ok=False)
    cases, jobs = _cases("i2l"), []
    for case in cases:
        system, user = direct_messages(skill_path(case).read_text(encoding="utf-8"),
                                       case_runtime(case))
        rel = f"prompts/direct/{case['id']}__s0.json"
        write_json(out / rel, {"system": system, "user": user})
        jobs.append({"case": case["id"], "arm": "direct", "sample": 0, "round": 1,
                     "prompt": rel, "output": f"outputs/direct/{case['id']}__s0.txt",
                     "prompt_sha256": hashlib.sha256((out / rel).read_bytes()).hexdigest()})
    write_json(out / "frozen.json", {"method": "direct", "case_set": "i2l",
                                     "cases": cases, "jobs": jobs})
    print(f"{len(jobs)} direct jobs")


def direct_verdicts() -> dict:
    out = OUT / "direct"
    res = {}
    for job in json.loads((out / "frozen.json").read_text())["jobs"]:
        p = out / job["output"]
        try:
            v = _extract_json_object(p.read_text(encoding="utf-8"))["verdict"]
            v = v if v in ("ACHIEVABLE", "IMPOSSIBLE", "UNKNOWN") else "UNKNOWN"
        except (OSError, ValueError, KeyError, TypeError):
            v = "INVALID"
        res[job["case"]] = v
    return res


def batches(run: Path, size: int) -> None:
    frozen = json.loads((run / "frozen.json").read_text())
    pending = [j for j in frozen["jobs"] if not (run / j["output"]).exists()]
    rnd = max((j["round"] for j in pending), default=1)
    pending = [j for j in pending if j["round"] == rnd]
    (run / "batches").mkdir(exist_ok=True)
    for k in range(0, len(pending), size):
        write_json(run / "batches" / f"r{rnd}_{k // size:02d}.json", {
            "arm": frozen["method"],
            "jobs": [{"prompt": str(run / j["prompt"]), "output": str(run / j["output"])}
                     for j in pending[k:k + size]]})
    print(f"round {rnd}: {len(pending)} jobs, {-(-len(pending) // size)} batches")


# ------------------------------------------------------------------ logical blocks

def _acts(steps: list, top: bool = True, out: list | None = None) -> list:
    """(cap, on_main_path) for every act step."""
    out = [] if out is None else out
    for s in steps:
        if "act" in s:
            out.append((s["act"]["cap"], top))
        if "choice" in s:
            for br in s["choice"]["branches"].values():
                _acts(br, False, out)
        if "rec" in s:
            _acts(s["rec"]["body"], top, out)
    return out


def necessity(pack: dict) -> tuple[set, bool]:
    """Necessary Tools of a pre-binding pack: dropping the Tool's declaration (its acts
    stay, as when the binder withdraws it) makes the checker refute the core Goal.
    Undeclared invoked Tools are first stubbed as available.  Falls back to 'invoked
    outside every choice branch' when the all-available pack is itself refuted."""
    acts = _acts(pack["protocol"])
    base = json.loads(json.dumps(pack))
    for cap, _ in acts:
        if cap not in base["capabilities"]:
            by = next(s for s in _flat(pack["protocol"]) if s["act"]["cap"] == cap)["act"]["by"]
            base["capabilities"][cap] = {"owner": by, "pre": True, "add": []}
    try:
        if check(base).label == "IMPOSSIBLE":
            return {c for c, top in acts if top}, True
    except Exception:
        return {c for c, top in acts if top}, True
    nec = set()
    for cap in sorted({c for c, _ in acts}):
        m = json.loads(json.dumps(base))
        del m["capabilities"][cap]
        try:
            if check(m).label == "IMPOSSIBLE":
                nec.add(cap)
        except Exception:
            pass
    return nec, False


def _flat(steps: list) -> list:
    out = []
    for s in steps:
        if "act" in s:
            out.append(s)
        if "choice" in s:
            for br in s["choice"]["branches"].values():
                out += _flat(br)
        if "rec" in s:
            out += _flat(s["rec"]["body"])
    return out


def final_blocks(run: Path, method: str) -> dict:
    """Replay benchmark_ce_runtime.score_all's round selection (guarded repair) and
    return, per case, the final pre-binding pack, bindings and binder witnesses."""
    frozen = json.loads((run / "frozen.json").read_text())
    rt = load_runtime("developer-sandbox")
    cases = {c["id"]: c for c in frozen["cases"]}
    prune = frozen.get("prune", False)
    final: dict = {}
    for job in sorted(frozen["jobs"], key=lambda j: j["round"]):
        p = run / job["output"]
        if not p.exists():
            continue
        parsed = parse_reply(cases[job["case"]], p.read_text(encoding="utf-8"), rt, method, prune)
        rec = final.setdefault(job["case"], {})
        if job["round"] == 3 and not parsed["ok"]:
            continue
        if job["round"] == 3 and rec.get("parsed") is not None:
            if repair_violations(rec["parsed"], parsed["parsed"]):
                continue
        rec.update(parsed)
    out = {}
    for cid, rec in final.items():
        if not rec.get("ok"):
            out[cid] = {"valid": False}
            continue
        pr = rec["parsed"]
        pre = pr.pack if pr is not None else rec["pack"]
        binds = pr.bindings if pr is not None else {}
        declared = set(pre["capabilities"])
        undeclared = {c for c, _ in _acts(pre["protocol"])} - declared
        nec, fallback = necessity(pre)
        out[cid] = {"valid": True, "pre_pack": pre,
                    "bindings": {k: {"via": v.get("via"), "needs": v.get("needs") or []}
                                 for k, v in binds.items()},
                    "bound_pack": rec["pack"],
                    "witness": sorted(set(rec.get("withdrawn") or {}) | set(rec.get("blocked") or {})
                                      | undeclared),
                    "necessary": sorted(nec), "necessity_fallback": fallback}
    return out


def blocks() -> None:
    res = {}
    for arm, dirs in ARMS.items():
        for d, method in dirs:
            run = RUNS / d
            if not (run / "frozen.json").exists():
                continue
            fb = final_blocks(run, method)
            # consistency: the replayed bound pack gives the verdict score_all recorded
            # (before ce_gr's grounding step, which only relabels IMPOSSIBLE as UNKNOWN)
            rec = {r["case"]: r for r in json.loads((run / "results.json").read_text())} \
                if (run / "results.json").exists() else {}
            for cid, b in fb.items():
                r = rec.get(cid)
                if b["valid"] and r is not None:
                    want = r.get("verdict_before_grounding") or r.get("verdict")
                    assert check(b["bound_pack"]).label == want, (arm, cid)
                b.pop("bound_pack", None)
                res.setdefault(arm, {})[cid] = b
        if arm not in res:
            continue
        print(arm, len(res[arm]), "blocks,", sum(not b["valid"] for b in res[arm].values()),
              "invalid,", sum(b.get("necessity_fallback", False) for b in res[arm].values()),
              "necessity fallbacks")
    write_json(OUT / "blocks.json", res)


# ------------------------------------------------------------------ judge

JUDGE_SYSTEM = (
    "You align requirement terms with the Tools of a formal plan.\n"
    "You get a plan (a logical block written in SkillC Controlled English: Tools with "
    "their runtime bindings, effects, a Goal and a Protocol) and a list of requirement "
    "terms, each with the sentence of the original skill it came from.\n"
    "For EACH term, list the names of the plan's Tools whose operation uses, runs, "
    "calls, installs, logs into, or otherwise depends on that term (a program, "
    "library, service, account, credential, network, device, file format, agent...). "
    "A Tool counts when it appears in the Protocol even if it is not declared. Map "
    "by meaning, not only by spelling (e.g. `run_tests` via `bash` uses `pytest` "
    "when the sentence says tests run with pytest). A term may map to several Tools, "
    "or to none when no Tool of the plan does that work. Do not judge whether the "
    "plan is right; only say where each term is represented.\n"
    "Output ONLY one JSON object mapping every term, exactly as given, to a list of "
    "Tool names: {\"term\": [\"tool\", ...], \"other term\": []}\n")


def gold_rows() -> dict:
    g = defaultdict(list)
    for line in ROWS.read_text().splitlines():
        r = json.loads(line)
        if r["source"] in ("prior", "gr") and r["cls"] != "none":
            g[r["report"]].append(r)
    return g


def prepare_judge(rejudge: bool = False) -> None:
    blk = json.loads((OUT / "blocks.json").read_text())
    gold = gold_rows()
    tag = "judge2" if rejudge else "judge"
    out = OUT / tag
    out.mkdir(parents=True, exist_ok=False)
    items = []
    for arm in BLOCK_ARMS:
        for cid, b in blk[arm].items():
            if not b["valid"] or cid not in gold:
                continue
            if rejudge and int(sha("i2l-rejudge:" + arm + cid), 16) % 5:
                continue
            terms = sorted({(r["term"], r["context"]) for r in gold[cid]})
            seen, uniq = set(), []
            for t, ctx in terms:
                if t not in seen:
                    seen.add(t)
                    uniq.append({"term": t, "context": ctx[:300]})
            iid = sha(f"i2l-item:{tag}:{arm}:{cid}")[:16]
            text = render_ce(b["pre_pack"], b["bindings"] or None)
            user = ("Plan:\n```ce\n" + text + "\n```\n\nRequirement terms:\n"
                    + json.dumps(uniq, indent=1, ensure_ascii=False) + "\n\nJSON mapping:")
            write_json(out / "prompts" / f"{iid}.json", {"system": JUDGE_SYSTEM, "user": user})
            items.append({"item": iid, "arm": arm, "case": cid,
                          "prompt": f"prompts/{iid}.json", "output": f"outputs/{iid}.json",
                          "round": 1})
    random.Random(0).shuffle(items)
    write_json(out / "frozen.json", {"method": tag, "jobs": items})
    print(f"{len(items)} judge items")


def judge_maps(tag: str = "judge") -> dict:
    out = OUT / tag
    res = {}
    for j in json.loads((out / "frozen.json").read_text())["jobs"]:
        p = out / j["output"]
        try:
            m = _extract_json_object(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            m = None
        res[(j["arm"], j["case"])] = m
    return res


# ------------------------------------------------------------------ scoring

def outcome_labels() -> dict:
    lab = {}
    for f in (RUNS / "20260926_heldout_execution.json", compare_heldout.FRESH_LABELS):
        for c, e in json.loads(f.read_text()).items():
            v = compare_heldout.label(e, "L2")
            lab[c] = {"IMPOSSIBLE": "CONFIRMED"}.get(v, v)
    score_div.DIV = RUNS / "20261001_gr"
    for c, e in score_div.labels("L2").items():
        lab[c] = e["label"]
    return lab


def verdicts() -> dict:
    v = {}
    for arm, dirs in ARMS.items():
        for d, _ in dirs:
            p = RUNS / d / "results.json"
            if p.exists():
                for r in json.loads(p.read_text()):
                    v.setdefault(arm, {})[r["case"]] = r.get("verdict") or "INVALID"
    if (OUT / "direct" / "frozen.json").exists():
        v["D"] = direct_verdicts()
    return v


def verdict_metrics(vs: dict, lab: dict, cases: list) -> dict:
    tp = fn = fp = tn = 0
    for c in cases:
        imp = vs.get(c) == "IMPOSSIBLE"
        if lab.get(c) == "CONFIRMED":
            tp, fn = tp + imp, fn + (not imp)
        elif lab.get(c) == "ACHIEVABLE":
            fp, tn = fp + imp, tn + (not imp)
    r = lambda k, n: {"k": k, "n": n, "value": round(k / n, 4) if n else None, "ci95": wilson(k, n)}
    return {"cases": len(cases), "recall": r(tp, tp + fn), "false_rejections": r(fp, fp + tn),
            "decided_accuracy": r(tp + tn, tp + fn + fp + tn)}


def paired(va: dict, vb: dict, lab: dict, cases: list) -> dict:
    ok = lambda v, c: (v.get(c) == "IMPOSSIBLE") == (lab[c] == "CONFIRMED")
    dec = [c for c in cases if lab.get(c) in ("CONFIRMED", "ACHIEVABLE")]
    b = sum(ok(va, c) and not ok(vb, c) for c in dec)
    w = sum(ok(vb, c) and not ok(va, c) for c in dec)
    return {"decided": len(dec), "a_better": b, "b_better": w, "mcnemar_p": mcnemar_exact(b, w)}


def block_items(blk: dict, maps: dict, gold: dict, arm: str) -> list:
    """One item per (pair, gold term): (case, kind flags, mapped_necessary, witnessed)."""
    items = []
    for cid, b in blk[arm].items():
        if cid not in gold:
            continue
        m = maps.get((arm, cid)) if b["valid"] else {}
        nec, wit = set(b.get("necessary", [])), set(b.get("witness", []))
        by_term = {}
        for r in gold[cid]:
            t = by_term.setdefault(r["term"], {"core": False, "blocked": False})
            t["core"] |= r["core"]
            t["blocked"] |= r["core"] and r["blocked"]
        for term, t in by_term.items():
            caps = set((m or {}).get(term) or []) if isinstance(m, dict) else set()
            items.append({"case": cid, "term": term, **t, "valid": b["valid"],
                          "judged": m is not None, "rep": bool(caps),
                          "nec": bool(caps & nec), "wit": bool(caps & nec & wit)})
    return items


def rates(items: list) -> dict:
    core = [i for i in items if i["core"]]
    opt = [i for i in items if not i["core"]]
    blk = [i for i in items if i["blocked"]]
    f = lambda xs, k: {"k": sum(i[k] for i in xs), "n": len(xs),
                       "value": round(sum(i[k] for i in xs) / len(xs), 4) if xs else None}
    # SW is exploratory (added after the construct-validity check failed; not in the
    # plan): optional terms on a necessary Tool the runtime withdrew or blocked
    return {"CR": f(core, "nec"), "SC": f(opt, "nec"), "BC": f(blk, "wit"),
            "SW_exploratory": f(opt, "wit"),
            "REP": f(items, "rep"), "unjudged": sum(not i["judged"] for i in items)}


def boot_diff(ia: list, ib: list, metric: str, n: int = 10000) -> dict:
    """Paired bootstrap over pairs of rate(a) - rate(b)."""
    key = {"CR": ("core", "nec"), "SC": ("opt", "nec"), "BC": ("blocked", "wit"),
           "SW_exploratory": ("opt", "wit")}[metric]
    sel = (lambda i: i["core"]) if key[0] == "core" else (
        (lambda i: not i["core"]) if key[0] == "opt" else (lambda i: i["blocked"]))
    per = {}
    for tag, items in (("a", ia), ("b", ib)):
        for i in items:
            if sel(i):
                d = per.setdefault(i["case"], {"a": [0, 0], "b": [0, 0]})
                d[tag][0] += i[key[1]]
                d[tag][1] += 1
    cases = sorted(c for c, d in per.items() if d["a"][1] and d["b"][1])
    if not cases:
        return {}

    def diff(cs):
        s = lambda t: sum(per[c][t][0] for c in cs) / max(1, sum(per[c][t][1] for c in cs))
        return s("a") - s("b")
    rng = random.Random(0)
    bs = sorted(diff([rng.choice(cases) for _ in cases]) for _ in range(n))
    return {"pairs": len(cases), "diff": round(diff(cases), 4),
            "ci95": [round(bs[int(0.025 * n)], 4), round(bs[int(0.975 * n) - 1], 4)]}


def tokens() -> dict:
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(
        "/tmp/claude-0/-home-user-skill-achievability-compiler/"
        "a1321181-416f-5422-8c3b-9ffc8650b51c/scratchpad/models/gpt2-medium")
    n = lambda s: len(tok(s, add_special_tokens=False).input_ids)
    res = {}
    runs = {arm: dirs for arm, dirs in ARMS.items()}
    runs["D"] = [("20260928_i2l/direct", "direct")]
    for arm, dirs in runs.items():
        for d, _ in dirs:
            run = RUNS / d
            if not (run / "frozen.json").exists():
                continue
            for j in json.loads((run / "frozen.json").read_text())["jobs"]:
                if not (run / j["output"]).exists():
                    continue
                p = json.loads((run / j["prompt"]).read_text())
                t = res.setdefault(arm, {}).setdefault(j["case"], {"in": 0, "out": 0, "calls": 0})
                t["in"] += n(p["system"]) + n(p["user"])
                t["out"] += n((run / j["output"]).read_text(encoding="utf-8"))
                t["calls"] += 1
    return res


def score() -> None:
    lab = outcome_labels()
    cases = [c["id"] for c in _cases("i2l")]
    sets = {"heldout+fresh": cases[:80], "gr": cases[80:], "all": cases}
    vs = verdicts()
    m: dict = {"verdict": {}, "verdict_paired": {}, "block": {}, "block_paired": {},
               "validity": {}, "tokens": {}}
    for s, cs in sets.items():
        m["verdict"][s] = {a: verdict_metrics(v, lab, cs) for a, v in vs.items()
                           if any(c in v for c in cs)}
        for a, b in (("P2g", "JB"), ("JB", "J"), ("P2g", "J"), ("P2g", "D"), ("JB", "D"),
                     ("P2g", "ce_gr")):
            if a in vs and b in vs and all(c in vs[a] and c in vs[b] for c in cs):
                m["verdict_paired"].setdefault(s, {})[f"{a} vs {b}"] = paired(vs[a], vs[b], lab, cs)
    blk_path = OUT / "blocks.json"
    if blk_path.exists() and (OUT / "judge" / "frozen.json").exists():
        blk = json.loads(blk_path.read_text())
        maps = judge_maps()
        gold = gold_rows()
        its = {a: block_items(blk, maps, gold, a) for a in BLOCK_ARMS}
        for s, cs in sets.items():
            cset = set(cs)
            sub = {a: [i for i in its[a] if i["case"] in cset] for a in BLOCK_ARMS}
            m["block"][s] = {a: rates(x) for a, x in sub.items() if x}
            for a, b in (("P2g", "JB"), ("JB", "J"), ("P2g", "J"), ("ce_gr", "P2g")):
                if sub.get(a) and sub.get(b):
                    m["block_paired"].setdefault(s, {})[f"{a} - {b}"] = {
                        k: boot_diff(sub[a], sub[b], k)
                        for k in ("CR", "SC", "BC", "SW_exploratory")}
        for a in BLOCK_ARMS:
            v = blk[a].values()
            m["validity"][a] = {"blocks": len(blk[a]), "valid": sum(b["valid"] for b in v),
                                "necessity_fallback": sum(b.get("necessity_fallback", False)
                                                          for b in v)}
        if (OUT / "judge2" / "frozen.json").exists():
            m["judge_agreement"] = agreement(blk, gold, maps, judge_maps("judge2"))
    for a, per in tokens().items():
        for s, cs in sets.items():
            xs = [per[c] for c in cs if c in per]
            if xs:
                m["tokens"].setdefault(s, {})[a] = {
                    "pairs": len(xs), "in_mean": round(sum(x["in"] for x in xs) / len(xs)),
                    "out_mean": round(sum(x["out"] for x in xs) / len(xs)),
                    "total_mean": round(sum(x["in"] + x["out"] for x in xs) / len(xs)),
                    "calls_mean": round(sum(x["calls"] for x in xs) / len(xs), 3)}
    for a in ARMS:
        run_valid = []
        for d, _ in ARMS[a]:
            p = RUNS / d / "results.json"
            if p.exists():
                run_valid += json.loads(p.read_text())
        if run_valid:
            m["validity"].setdefault(a, {}).update({
                "valid_first": sum(r["valid_first"] for r in run_valid),
                "valid_final": sum(r["valid"] for r in run_valid), "cases": len(run_valid)})
    write_json(OUT / "metrics.json", m)
    print(json.dumps(m, indent=1)[:6000])


def agreement(blk: dict, gold: dict, m1: dict, m2: dict) -> dict:
    a = b = both = n = 0
    for (arm, cid), mm in m2.items():
        if mm is None or m1.get((arm, cid)) is None:
            continue
        nec = set(blk[arm][cid]["necessary"])
        for term in {r["term"] for r in gold[cid]}:
            x = bool(set(m1[(arm, cid)].get(term) or []) & nec)
            y = bool(set(mm.get(term) or []) & nec)
            n, a, b, both = n + 1, a + x, b + y, both + (x == y)
    if not n:
        return {}
    po, pe = both / n, (a / n) * (b / n) + (1 - a / n) * (1 - b / n)
    return {"items": n, "agreement": round(po, 4),
            "kappa": round((po - pe) / (1 - pe), 4) if pe < 1 else None}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prepare-direct")
    b = sub.add_parser("batches")
    b.add_argument("run", type=Path)
    b.add_argument("--size", type=int, default=10)
    sub.add_parser("blocks")
    j = sub.add_parser("prepare-judge")
    j.add_argument("--rejudge", action="store_true")
    sub.add_parser("score")
    a = ap.parse_args()
    {"prepare-direct": prepare_direct, "batches": lambda: batches(a.run, a.size),
     "blocks": blocks, "prepare-judge": lambda: prepare_judge(a.rejudge),
     "score": score}[a.cmd]()


if __name__ == "__main__":
    main()

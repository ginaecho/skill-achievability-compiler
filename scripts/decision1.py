"""Addendum D: Microsoft-Decision-1 on the compaction layer (runs/20261015_review_response/PLAN.md).

  judge OUT     X1: Decision-1 as fidelity judge (F1..F5) on every judge item of set2,
                set3 and Scout; no Claude score is in any request
  verdict OUT   X2: arm D-dec, a direct verdict from the exact D prompt text of set2 and set3
  filter OUT    X3 (exploratory): hardness filter on every set3 refutation of Rdet, P2g+, P2g
  score OUT     metrics.json with every metric and the criteria X1a, X1b, X2a, X2b, X3

OUT is runs/20261015_decision1.  Every request body is saved as prompts/<arm>/<item>.json and
every reply as outputs/<arm>/<item>.json (with usage, truncation and error fields);
frozen.json lists the sha256 of each.  Runs are resumable: an item whose output exists
without an error is skipped.  One request per item, at most 40 requests per minute.

Model calls need the Azure CLI login and (in this shell)
  env -u AZURE_SUBSCRIPTION_ID -u AZURE_TENANT_ID PYTHONUTF8=1 PYTHONPATH=src \
      python scripts/decision1.py judge runs/20261015_decision1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
import urllib.error
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from skillc.frontend import providers  # noqa: E402
from skillc.frontend.ce import render_ce  # noqa: E402

RUNS = ROOT / "runs"
PLAN = RUNS / "20261015_review_response" / "PLAN.md"
SET2_RUN = RUNS / "20261015_reliability"
SET3_RUN = RUNS / "20261015_set3"
SCOUT_JUDGE = RUNS / "20261015_hosts" / "scout" / "judge"
SET3_CASES = ROOT / "benchmark" / "claude_env" / "set3" / "cases"
MODEL = "Decision-1"
MIN_INTERVAL = 60.0 / 40          # 40 requests per minute
THRESHOLD = 0.5                   # noul probability >= 0.5 is yes (fixed by Addendum D)
HARD_THRESHOLD = 0.7              # X3 second rule: P(hard) >= 0.7 (fixed by Addendum D)
MAX_TRIES = 8
CRITERIA_KEYS = ("F1", "F2", "F3", "F4", "F5")

# ------------------------------------------------------------------ X1 question text
# `instructions` of each question is the item's rubric text verbatim; `criteria` are the
# yes / no conditions below, derived from the rubric wording and the judging notes of the
# judge READMEs (the same text for every item of a criterion).
JUDGE_CRITERIA = {
    "F1": {"true": "Every Tool in the pack corresponds to an operation that some sentence "
                   "of the document asks for, or the pack declares no Tool.",
           "false": "At least one Tool in the pack is invented: no sentence of the document "
                    "asks for that operation."},
    "F2": {"true": "No mandatory step is omitted: every step without which the document's "
                   "core deliverable cannot be produced appears in the pack. Optional or "
                   "follow-up work may be omitted or skippable.",
           "false": "The pack omits at least one mandatory step, a step without which the "
                    "document's core deliverable cannot be produced."},
    "F3": {"true": "The pack's Goal names the deliverable of one representative request "
                   "of the document.",
           "false": "The pack's Goal does not name the deliverable of one representative "
                    "request (for example it is `true`, empty, or names something else)."},
    "F4": {"true": "No ordering is invented: every order the protocol puts between two "
                   "steps is stated or implied by the document (for example by data "
                   "dependence), or the protocol imposes no order.",
           "false": "The protocol puts at least two steps in an order the document neither "
                    "states nor implies."},
    "F5": {"true": "Bindings are plausible: each `via` names a tool from runtime.tools "
                   "that can really perform the Tool; a `via` naming something outside "
                   "that list is plausible only if the runtime indeed cannot perform the "
                   "operation.",
           "false": "At least one `via` names a tool that cannot perform the Tool, or names "
                    "something outside runtime.tools although the runtime can perform the "
                    "operation."},
}

# ------------------------------------------------------------------ X2 question text
# Taken from the D system prompt ("Answer IMPOSSIBLE when a step the core deliverable
# cannot do without cannot be done in this RUNTIME; ACHIEVABLE when every such step can;
# UNKNOWN when you cannot tell."); `verdict` checks that sentence is in every prompt.
D_DEFINITION = ("Answer IMPOSSIBLE when a step the core deliverable cannot do without "
                "cannot be done in this RUNTIME; ACHIEVABLE when every such step can; "
                "UNKNOWN when you cannot tell.")
VERDICT_QUESTIONS = {
    "blocked": {"type": "noul",
                "instructions": "Is there a step the core deliverable cannot do without "
                                "that cannot be done in this RUNTIME?",
                "criteria": {"true": "IMPOSSIBLE: a step the core deliverable cannot do "
                                     "without cannot be done in this RUNTIME.",
                             "false": "ACHIEVABLE: every step the core deliverable cannot "
                                      "do without can be done in this RUNTIME."}},
    "verdict": {"type": "choice",
                "instructions": "Can an AI agent working in the RUNTIME deliver what the "
                                "natural-language skill is for (its core deliverable for "
                                "one representative request)?",
                "criteria": {"ACHIEVABLE": "every step the core deliverable cannot do "
                                           "without can be done in this RUNTIME",
                             "IMPOSSIBLE": "a step the core deliverable cannot do without "
                                           "cannot be done in this RUNTIME",
                             "UNKNOWN": "you cannot tell"}},
}

# ------------------------------------------------------------------ X3 question text
FILTER_QUESTION = {
    "hardness": {"type": "choice",
                 "instructions": "Is the named requirement a hard requirement of the "
                                 "document's primary task for one representative request?",
                 "criteria": {
                     "hard": "the primary task cannot be done without it as the document "
                             "is written",
                     "optional_or_alternative": "optional, conditional, follow-up, or one "
                                                "of several alternatives",
                     "example_or_mention_only": "mentioned as an example, in a comment, or "
                                                "in prose that does not require it",
                     "cannot_tell": "cannot tell"}}}
READER_FALSE = ["c001", "c005", "c006", "c027", "c032", "c047", "c081"]


# ------------------------------------------------------------------ helpers
def sha(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def rnd(x, k: int = 4):
    return None if x is None else round(x, k)


def wilson(k: int, n: int, z: float = 1.96) -> list:
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 4), round(c + h, 4)]


def mcnemar_exact(b: int, c: int) -> float | None:
    n = b + c
    if n == 0:
        return None
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return round(min(1.0, 2 * p), 6)


def cohen_kappa(a: list, b: list) -> float | None:
    if not a:
        return None
    cats = sorted(set(a) | set(b))
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return None if pe == 1 else rnd((po - pe) / (1 - pe))


def auroc(scores: list[float], labels: list[int]) -> float | None:
    """Rank-based AUROC (Mann-Whitney U with mid-ranks for ties); labels 1 = positive."""
    pos = sum(labels)
    neg = len(labels) - pos
    if pos == 0 or neg == 0:
        return None
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    ranks = [0.0] * len(scores)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    rpos = sum(r for r, y in zip(ranks, labels) if y == 1)
    return rnd((rpos - pos * (pos + 1) / 2) / (pos * neg))


def addendum_text() -> str:
    """The pre-registered text of Addendum D (without the later results pointer)."""
    text = PLAN.read_text(encoding="utf-8")
    start = text.index("## Addendum D")
    body = text[start:]
    cut = body.find("**Results pointer (Addendum D)")
    return body if cut < 0 else body[:cut].rstrip() + "\n"


# ------------------------------------------------------------------ calling
_TOKEN = {"value": None, "at": 0.0}
_ORIG_TOKEN = providers.azure_cli_token
_LAST = {"t": 0.0}


def _cached_token() -> str:
    if _TOKEN["value"] is None or time.time() - _TOKEN["at"] > 1800:
        _TOKEN["value"] = _ORIG_TOKEN()
        _TOKEN["at"] = time.time()
    return _TOKEN["value"]


providers.azure_cli_token = _cached_token


def _pace() -> None:
    wait = _LAST["t"] + MIN_INTERVAL - time.time()
    if wait > 0:
        time.sleep(wait)
    _LAST["t"] = time.time()


def _overflow(e: providers.DecisionError) -> tuple[int, int] | None:
    """(request tokens, limit) when the refusal is a context overflow, else None."""
    if e.status not in (400, 413, 422):
        return None
    m = re.search(r"about (\d+) tokens; the limit[^0-9]*(\d+)", e.message)
    if m:
        return int(m.group(1)), int(m.group(2))
    if re.search(r"token|context|too (long|large)|limit", e.message, re.I):
        return (0, 0)
    return None


def call_item(out: Path, arm: str, item: str, build, doc: str) -> dict:
    """Send `build(doc_text)` (a (state, questions) pair); on a context overflow, cut the
    document from the end and retry.  Saves the prompt and the reply; returns the output."""
    op = out / "outputs" / arm / f"{item}.json"
    if op.exists():
        prev = read_json(op)
        if prev.get("error") is None:
            return prev
    kept = len(doc)
    attempts, backoff, last_err = 0, 2.0, None
    reply = None
    t0 = time.time()
    while attempts < MAX_TRIES:
        attempts += 1
        state, questions = build(doc[:kept])
        body = {"model": MODEL, "state": state, "questions": questions}
        write_json(out / "prompts" / arm / f"{item}.json", body)
        _pace()
        try:
            reply = providers.decision(state, questions, model=MODEL)
            last_err = None
            break
        except providers.DecisionError as e:
            last_err = str(e)
            ov = _overflow(e)
            if ov is not None:
                n, limit = ov
                factor = min(0.9, 0.95 * limit / n) if n and limit else 0.8
                kept = int(kept * factor)
                continue
            if e.status == 429 or e.status >= 500:
                time.sleep(backoff)
                backoff = min(backoff * 2, 120)
                continue
            break
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(backoff)
            backoff = min(backoff * 2, 120)
    rec = {"arm": arm, "item": item, "model": MODEL, "time_utc": now(),
           "latency_s": round(time.time() - t0, 2), "attempts": attempts,
           "truncated": kept < len(doc), "original_chars": len(doc), "kept_chars": kept,
           "error": last_err if reply is None else None, "reply": reply,
           "usage": (reply or {}).get("usage")}
    write_json(op, rec)
    if reply is not None:
        write_json(out / "outputs" / arm / f"{item}.usage.json", reply.get("usage"))
    tag = "ERR " + str(last_err)[:120] if reply is None else ("trunc" if rec["truncated"] else "ok")
    print(f"[{now()}] {arm} {item}: {tag}", flush=True)
    return rec


def refreeze(out: Path) -> None:
    fz = {"created_utc": now(), "plan": str(PLAN.relative_to(ROOT)).replace("\\", "/"),
          "plan_addendum_D_sha256": sha(addendum_text()),
          "script_sha256": sha(Path(__file__).read_bytes()),
          "providers_sha256": sha((ROOT / "src/skillc/frontend/providers.py").read_bytes()),
          "model": MODEL, "threshold": THRESHOLD, "hard_threshold": HARD_THRESHOLD,
          "arms": {}}
    for arm_dir in sorted((out / "prompts").glob("*")) if (out / "prompts").exists() else []:
        arm = arm_dir.name
        items = {}
        for p in sorted(arm_dir.glob("*.json")):
            o = out / "outputs" / arm / p.name
            items[p.stem] = {"prompt_sha256": sha(p.read_bytes()),
                             "reply_sha256": sha(o.read_bytes()) if o.exists() else None}
        fz["arms"][arm] = items
    prev = out / "frozen.json"
    if prev.exists():
        fz["first_created_utc"] = read_json(prev).get("first_created_utc",
                                                      read_json(prev).get("created_utc"))
    else:
        fz["first_created_utc"] = fz["created_utc"]
    write_json(prev, fz)


# ------------------------------------------------------------------ X1 judge
def judge_sets() -> dict:
    """set -> list of (item id, item path)."""
    return {"set2": sorted((SET2_RUN / "judge" / "items").glob("*.json")),
            "set3": sorted((SET3_RUN / "judge" / "items").glob("*.json")),
            "scout": sorted((SCOUT_JUDGE / "items").glob("*.json"))}


def judge_questions(rubric: dict) -> dict:
    return {f: {"type": "noul", "instructions": rubric[f], "criteria": JUDGE_CRITERIA[f]}
            for f in CRITERIA_KEYS}


def cmd_judge(out: Path, limit: int | None, sets: list[str] | None) -> None:
    for name, paths in judge_sets().items():
        if sets and name not in sets:
            continue
        for p in paths[:limit] if limit else paths:
            it = read_json(p)
            qs = judge_questions(it["rubric"])

            def build(doc, it=it, qs=qs):
                return {"document": doc, "runtime": it["runtime"], "pack": it["ce"]}, qs
            call_item(out, f"judge-{name}", p.stem, build, it["source_text"])
    refreeze(out)


# ------------------------------------------------------------------ X2 verdict
def cmd_verdict(out: Path, limit: int | None, sets: list[str] | None) -> None:
    for name, run in (("set2", SET2_RUN), ("set3", SET3_RUN)):
        if sets and name not in sets:
            continue
        paths = sorted((run / "prompts" / "D").glob("*__s0.json"))
        for p in paths[:limit] if limit else paths:
            d = read_json(p)
            if D_DEFINITION not in d["system"]:
                raise SystemExit(f"{p}: D definition sentence not found")

            def build(doc, d=d):
                return {"instructions": d["system"], "input": doc}, VERDICT_QUESTIONS
            call_item(out, f"verdict-{name}", p.stem.split("__")[0], build, d["user"])
    refreeze(out)


# ------------------------------------------------------------------ X3 filter
def _tool_lines(ce: str, caps) -> list[str]:
    lines = []
    for c in caps:
        for ln in ce.splitlines():
            if ln.startswith(f"Tool `{c}`"):
                lines.append(ln)
    return lines


def refutation_units() -> list[dict]:
    """One unit per (refutation, refuting requirement); a refutation is kept when any of
    its units is kept."""
    rows = read_json(SET3_RUN / "results.json")
    truth = {r["case"]: r["truth"] for r in rows}
    units = []
    for r in rows:
        if r["arm"] == "Rdet" and r.get("verdict") == "IMPOSSIBLE":
            for k, w in enumerate(r["witness"]):
                units.append({"arm": "Rdet", "case": r["case"], "sample": r["sample"],
                              "unit": k, "truth": truth[r["case"]], "reason": r["reason"],
                              "requirement": w["requirement"],
                              "evidence": list(w.get("evidence") or [])})
    for arm in ("P2g+", "P2g"):
        for r in rows:
            if r["arm"] != arm or r.get("verdict") != "IMPOSSIBLE":
                continue
            pk = read_json(SET3_RUN / "packs" / arm / f"{r['case']}__s{r['sample']}.json")
            ce = render_ce(pk["pre_binding"], pk["bindings"], pk.get("live_goal"))
            reqs: list[tuple[str, list[str], str]] = []
            if r.get("blocked"):
                by_res: dict[str, list[str]] = {}
                for tool, res in r["blocked"].items():
                    for x in res:
                        by_res.setdefault(x, []).append(tool)
                for x, tools in by_res.items():
                    reqs.append((f"needs `{x}`", _tool_lines(ce, tools)
                                 or [f"Tool `{t}` needs `{x}`" for t in tools], "needs"))
            elif r.get("withdrawn"):
                by_res = {}
                for tool, x in r["withdrawn"].items():
                    by_res.setdefault(x, []).append(tool)
                for x, tools in by_res.items():
                    ev = _tool_lines(ce, tools) or [
                        f"Tool `{t}` needs `{x}` (not granted by the runtime; the Tool was "
                        "withdrawn)" for t in tools]
                    reqs.append((f"needs `{x}`", ev, "needs"))
            elif r["reason"] == "BLOCKED_GUARD":
                caps = list(dict.fromkeys(re.findall(r"capability '([^']+)'", r["detail"])))
                for c in caps:
                    seg = [s for s in r["detail"].split("; ") if f"'{c}'" in s]
                    reqs.append((f"the step `{c}`", _tool_lines(ce, [c]) + seg, "guard"))
            else:   # GOAL_UNSAT and anything else: the goal facts no Tool establishes
                atoms = r.get("frontier") or []
                goal = [ln for ln in ce.splitlines() if ln.startswith("Goal:")]
                reqs.append(("the goal facts " + ", ".join(f"`{a}`" for a in atoms)
                             + " (no Tool in the pack establishes them)",
                             goal + [r["detail"]], "goal"))
            for k, (name, ev, kind) in enumerate(reqs):
                units.append({"arm": arm, "case": r["case"], "sample": r["sample"],
                              "unit": k, "truth": truth[r["case"]], "reason": r["reason"],
                              "requirement": name, "evidence": ev, "kind": kind})
    return units


def unit_id(u: dict) -> str:
    return f"{u['case']}__s{u['sample']}__r{u['unit']}"


def cmd_filter(out: Path, limit: int | None, arms: list[str] | None) -> None:
    units = refutation_units()
    write_json(out / "filter_units.json", units)
    done = Counter()
    for u in units:
        if arms and u["arm"] not in arms:
            continue
        if limit and done[u["arm"]] >= limit:
            continue
        done[u["arm"]] += 1
        doc = (SET3_CASES / f"{u['case']}.md").read_text(encoding="utf-8")

        def build(d, u=u):
            return ({"document": d, "requirement": u["requirement"],
                     "evidence": u["evidence"]}, FILTER_QUESTION)
        call_item(out, "filter-" + u["arm"].replace("+", "plus"), unit_id(u), build, doc)
    refreeze(out)


# ------------------------------------------------------------------ score
def _outs(out: Path, arm: str) -> dict:
    d = out / "outputs" / arm
    res = {}
    for p in sorted(d.glob("*.json")) if d.exists() else []:
        if p.name.endswith(".usage.json"):
            continue
        res[p.stem] = read_json(p)
    return res


def _norm(v) -> str:
    v = str(v or "").strip().lower()
    return v if v in ("yes", "no") else "unclear"


def _agree(a: list, b: list) -> dict:
    """a, b aligned labels; pairs where either is `unclear` are dropped."""
    pa = [(x, y) for x, y in zip(a, b) if x != "unclear" and y != "unclear"]
    x = [p[0] for p in pa]
    y = [p[1] for p in pa]
    return {"n": len(pa), "dropped_unclear": len(a) - len(pa),
            "agree": sum(i == j for i, j in pa),
            "agreement": rnd(sum(i == j for i, j in pa) / len(pa)) if pa else None,
            "cohen_kappa": cohen_kappa(x, y)}


def _agree_with_unclear(a: list, b: list) -> dict:
    """Both raters' `unclear` kept as a category (as scripts/reliability.py judge-score)."""
    return {"n": len(a), "agree": sum(i == j for i, j in zip(a, b)),
            "agreement": rnd(sum(i == j for i, j in zip(a, b)) / len(a)) if a else None,
            "cohen_kappa": cohen_kappa(a, b)}


def _claude_scores(name: str) -> tuple[dict, dict]:
    if name == "set2" or name == "set3":
        jd = (SET2_RUN if name == "set2" else SET3_RUN) / "judge"
        first = {p.stem: read_json(p) for p in (jd / "scores").glob("*.json")}
        second = {p.stem: read_json(p) for p in (jd / "scores2").glob("*.json")}
    else:
        first = {s["case"]: s for s in read_json(SCOUT_JUDGE / "scores.json")}
        second = {s["case"]: s for s in read_json(SCOUT_JUDGE / "scores_b.json")}
    return first, second


def score_judge(out: Path) -> dict:
    res = {}
    for name in ("set2", "set3", "scout"):
        outs = _outs(out, f"judge-{name}")
        ok = {k: v for k, v in outs.items() if v.get("reply")}
        errors = sorted(k for k, v in outs.items() if not v.get("reply"))
        first, second = _claude_scores(name)
        prob = {k: {f: float(v["reply"]["answers"][f]["noul"]) for f in CRITERIA_KEYS}
                for k, v in ok.items()}
        dec = {k: {f: "yes" if p[f] >= THRESHOLD else "no" for f in CRITERIA_KEYS}
               for k, p in prob.items()}
        items = sorted(k for k in dec if k in first)
        sec_items = sorted(k for k in items if k in second)
        per, pa1, pb1, pa2, pb2, pc1, pc2, allp, ally = {}, [], [], [], [], [], [], [], []
        for f in CRITERIA_KEYS:
            d1 = [dec[k][f] for k in items]
            c1 = [_norm(first[k].get(f)) for k in items]
            y_ = [(p, 1 if c == "yes" else 0) for p, c in
                  zip([prob[k][f] for k in items], c1) if c != "unclear"]
            ds = [dec[k][f] for k in sec_items]
            cs1 = [_norm(first[k].get(f)) for k in sec_items]
            cs2 = [_norm(second[k].get(f)) for k in sec_items]
            n_c1 = len(c1)
            per[f] = {
                "items": len(items),
                "decision1_yes_rate": rnd(d1.count("yes") / len(d1)) if d1 else None,
                "decision1_yes": d1.count("yes"),
                "claude1_yes": c1.count("yes"), "claude1_no": c1.count("no"),
                "claude1_unclear": c1.count("unclear"),
                "claude1_yes_rate": rnd(c1.count("yes") / n_c1) if n_c1 else None,
                "claude1_yes_rate_excl_unclear": rnd(c1.count("yes") / (n_c1 - c1.count(
                    "unclear"))) if n_c1 - c1.count("unclear") else None,
                "vs_first": _agree(d1, c1),
                "auroc_vs_first": auroc([p for p, _ in y_], [y for _, y in y_]),
                "second_judge_items": len(sec_items),
                "vs_second": _agree(ds, cs2),
                "vs_first_on_second_items": _agree(ds, cs1),
                "claude1_vs_claude2": _agree(cs1, cs2),
                "claude1_vs_claude2_with_unclear": _agree_with_unclear(cs1, cs2)}
            pa1 += d1
            pb1 += c1
            pa2 += ds
            pb2 += cs2
            pc1 += cs1
            pc2 += cs2
            allp += [p for p, _ in y_]
            ally += [y for _, y in y_]
        pooled = {"vs_first": _agree(pa1, pb1), "auroc_vs_first": auroc(allp, ally),
                  "vs_second": _agree(pa2, pb2),
                  "vs_first_on_second_items": _agree(
                      [dec[k][f] for f in CRITERIA_KEYS for k in sec_items],
                      [_norm(first[k].get(f)) for f in CRITERIA_KEYS for k in sec_items]),
                  "claude1_vs_claude2": _agree(pc1, pc2),
                  "claude1_vs_claude2_with_unclear": _agree_with_unclear(pc1, pc2)}
        entry = {"items_total": len(outs), "items_scored": len(items),
                 "excluded_errors": errors, "second_judge_items": sec_items,
                 "truncated": sorted(k for k, v in ok.items() if v.get("truncated")),
                 "per_criterion": per, "pooled": pooled}
        if name == "set3":
            ch = {}
            for f in ("F1", "F4"):
                rates = {}
                for var in ("p2g", "p2gplus"):
                    ks = [k for k in items if k.endswith("__" + var)]
                    dd = [dec[k][f] for k in ks]
                    cc = [_norm(first[k].get(f)) for k in ks]
                    rates[var] = {"n": len(ks),
                                  "decision1_yes_rate": rnd(dd.count("yes") / len(dd)) if dd else None,
                                  "claude1_yes_rate": rnd(cc.count("yes") / len(cc)) if cc else None,
                                  "claude1_unclear": cc.count("unclear")}
                dd_ = rates["p2gplus"]["decision1_yes_rate"] - rates["p2g"]["decision1_yes_rate"]
                cc_ = rates["p2gplus"]["claude1_yes_rate"] - rates["p2g"]["claude1_yes_rate"]
                sg = lambda x: (x > 1e-9) - (x < -1e-9)  # noqa: E731
                ch[f] = {**rates, "decision1_change": rnd(dd_), "claude1_change": rnd(cc_),
                         "decision1_sign": sg(dd_), "claude1_sign": sg(cc_),
                         "same_sign": sg(dd_) == sg(cc_) and sg(cc_) != 0}
            entry["p2g_to_p2gplus"] = ch
        res[name] = entry
    return res


def _truths(run: Path) -> tuple[dict, dict]:
    rows = read_json(run / "results.json")
    truth = {r["case"]: r["truth"] for r in rows}
    d = {r["case"]: r.get("verdict") for r in rows if r["arm"] == "D" and r["sample"] == 0}
    return truth, d


def _acc(labels: dict, truth: dict) -> dict:
    dec = {k: v for k, v in labels.items() if v in ("ACHIEVABLE", "IMPOSSIBLE")}
    right = sum(v == truth[k] for k, v in dec.items())
    blocked = [k for k in labels if truth[k] == "IMPOSSIBLE"]
    ach = [k for k in labels if truth[k] == "ACHIEVABLE"]
    rec_ = sum(labels[k] == "IMPOSSIBLE" for k in blocked)
    fr = sum(labels[k] == "IMPOSSIBLE" for k in ach)
    return {"n": len(labels), "decided": len(dec),
            "unknown": sum(v == "UNKNOWN" for v in labels.values()),
            "other": sum(v not in ("ACHIEVABLE", "IMPOSSIBLE", "UNKNOWN")
                         for v in labels.values()),
            "correct": right, "accuracy_decided": rnd(right / len(dec)) if dec else None,
            "accuracy_ci95": wilson(right, len(dec)),
            "blocked_total": len(blocked), "blocked_caught": rec_,
            "blocked_recall": rnd(rec_ / len(blocked)) if blocked else None,
            "blocked_recall_ci95": wilson(rec_, len(blocked)),
            "achievable_total": len(ach), "false_refutations": fr,
            "false_refutation_rate": rnd(fr / len(ach)) if ach else None,
            "false_refutation_ci95": wilson(fr, len(ach))}


def score_verdict(out: Path) -> dict:
    res = {}
    for name, run in (("set2", SET2_RUN), ("set3", SET3_RUN)):
        outs = _outs(out, f"verdict-{name}")
        ok = {k: v for k, v in outs.items() if v.get("reply")}
        truth, dgpt = _truths(run)
        lab = {k: v["reply"]["answers"]["verdict"]["choice"] for k, v in ok.items()}
        pb = {k: float(v["reply"]["answers"]["blocked"]["noul"]) for k, v in ok.items()}
        gpt = {k: dgpt[k] for k in lab}
        a_dec, a_gpt = _acc(lab, truth), _acc(gpt, truth)
        both = [c for c in lab if lab[c] in ("ACHIEVABLE", "IMPOSSIBLE")
                and gpt[c] in ("ACHIEVABLE", "IMPOSSIBLE")]
        b = sum(lab[c] == truth[c] and gpt[c] != truth[c] for c in both)
        c_ = sum(lab[c] != truth[c] and gpt[c] == truth[c] for c in both)
        ks = sorted(pb)
        y = [1 if truth[k] == "IMPOSSIBLE" else 0 for k in ks]
        curve = []
        for i in range(1, 20):
            t = round(0.05 * i, 2)
            rec = sum(pb[k] >= t for k in ks if truth[k] == "IMPOSSIBLE")
            frr = sum(pb[k] >= t for k in ks if truth[k] == "ACHIEVABLE")
            curve.append({"threshold": t, "recall": rnd(rec / max(1, sum(y))),
                          "caught": rec, "false_refutations": frr,
                          "false_refutation_rate": rnd(frr / max(1, len(ks) - sum(y)))})
        target = a_gpt["blocked_recall"]
        # thresholds descending: the first (highest) threshold whose recall >= target
        match = next((p for p in sorted(curve, key=lambda p: -p["threshold"])
                      if p["recall"] is not None and target is not None
                      and p["recall"] >= target), None)
        usage = [v["reply"].get("usage") or {} for v in ok.values()]
        res[name] = {
            "items_total": len(outs), "items_scored": len(lab),
            "excluded_errors": sorted(k for k, v in outs.items() if not v.get("reply")),
            "truncated": {k: {"original_chars": v["original_chars"],
                              "kept_chars": v["kept_chars"]}
                          for k, v in ok.items() if v.get("truncated")},
            "D_dec": a_dec, "D_gpt54": a_gpt,
            "verdict_counts": dict(Counter(lab.values())),
            "mcnemar_vs_D_gpt54": {"paired_cases": len(both), "dec_right_gpt_wrong": b,
                                   "dec_wrong_gpt_right": c_, "p": mcnemar_exact(b, c_)},
            "auroc_blocked_prob": auroc([pb[k] for k in ks], y),
            "operating_curve": curve,
            "matched_recall": {"target_recall_D_gpt54": target, "point": match},
            "calls": len(ok), "input_tokens": sum(int(u.get("input_tokens", 0)) for u in usage),
            "output_tokens": sum(int(u.get("output_tokens", 0)) for u in usage)}
    return res


def score_filter(out: Path) -> dict:
    units = read_json(out / "filter_units.json") if (out / "filter_units.json").exists() \
        else refutation_units()
    res = {}
    for arm in ("Rdet", "P2g+", "P2g"):
        outs = _outs(out, "filter-" + arm.replace("+", "plus"))
        refs: dict[tuple, dict] = {}
        errors = []
        for u in units:
            if u["arm"] != arm:
                continue
            key = (u["case"], u["sample"])
            r = refs.setdefault(key, {"case": u["case"], "sample": u["sample"],
                                      "truth": u["truth"], "reason": u["reason"],
                                      "units": []})
            o = outs.get(unit_id(u))
            if not o or not o.get("reply"):
                errors.append(unit_id(u))
                r["units"].append({"requirement": u["requirement"], "error": True})
                continue
            a = o["reply"]["answers"]["hardness"]
            ph = float((a.get("probabilities") or {}).get("hard", 0.0))
            r["units"].append({"requirement": u["requirement"], "choice": a["choice"],
                               "p_hard": rnd(ph), "probabilities": a.get("probabilities"),
                               "keep_default": a["choice"] == "hard",
                               "keep_p07": ph >= HARD_THRESHOLD,
                               "truncated": o.get("truncated")})
        rows = []
        for r in refs.values():
            us = [x for x in r["units"] if not x.get("error")]
            if len(us) < len(r["units"]):
                r["excluded"] = True
            r["keep_default"] = any(x["keep_default"] for x in us)
            r["keep_p07"] = any(x["keep_p07"] for x in us)
            rows.append(r)
        scored = [r for r in rows if not r.get("excluded")]
        true_ = [r for r in scored if r["truth"] == "IMPOSSIBLE"]
        false_ = [r for r in scored if r["truth"] == "ACHIEVABLE"]
        rules = {}
        for rule in ("keep_default", "keep_p07"):
            tk = sum(r[rule] for r in true_)
            fr = sum(not r[rule] for r in false_)
            rules[rule] = {
                "true_kept": tk, "true_total": len(true_),
                "true_kept_rate": rnd(tk / len(true_)) if true_ else None,
                "true_kept_ci95": wilson(tk, len(true_)),
                "false_removed": fr, "false_total": len(false_),
                "false_removed_rate": rnd(fr / len(false_)) if false_ else None,
                "false_removed_ci95": wilson(fr, len(false_)),
                "met": bool((not false_ or fr / len(false_) >= 0.5)
                            and (not true_ or tk / len(true_) >= 0.9))}
        by_reason = {}
        for reason in sorted({r["reason"] for r in scored}):
            rr = [r for r in scored if r["reason"] == reason]
            by_reason[reason] = {
                "refutations": len(rr),
                "true": sum(r["truth"] == "IMPOSSIBLE" for r in rr),
                "true_kept_default": sum(r["keep_default"] for r in rr if r["truth"] == "IMPOSSIBLE"),
                "false_removed_default": sum(not r["keep_default"] for r in rr
                                             if r["truth"] == "ACHIEVABLE")}
        usage = [o["reply"].get("usage") or {} for o in outs.values() if o.get("reply")]
        res[arm] = {"refutations": len(rows), "scored": len(scored),
                    "units": sum(len(r["units"]) for r in rows),
                    "excluded_unit_errors": errors, "rules": rules, "by_reason": by_reason,
                    "calls": len(usage),
                    "input_tokens": sum(int(u.get("input_tokens", 0)) for u in usage),
                    "decisions": sorted(rows, key=lambda r: (r["case"], r["sample"]))}
    rd = {r["case"]: r for r in res.get("Rdet", {}).get("decisions", [])}
    res["reader_false_refutations"] = {c: rd.get(c) for c in READER_FALSE}
    return res


def _usage_all(out: Path) -> dict:
    tot = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "errors": 0, "truncated": 0,
           "per_arm": {}}
    for arm_dir in sorted((out / "outputs").glob("*")):
        a = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "errors": 0,
             "truncated": 0, "attempts": 0}
        for o in _outs(out, arm_dir.name).values():
            a["attempts"] += o.get("attempts", 0)
            if o.get("reply"):
                u = o["reply"].get("usage") or {}
                a["calls"] += 1
                a["input_tokens"] += int(u.get("input_tokens", 0))
                a["output_tokens"] += int(u.get("output_tokens", 0))
                a["truncated"] += bool(o.get("truncated"))
            else:
                a["errors"] += 1
        tot["per_arm"][arm_dir.name] = a
        for k in ("calls", "input_tokens", "output_tokens", "errors", "truncated"):
            tot[k] += a[k]
    tot["attempts_total"] = sum(a["attempts"] for a in tot["per_arm"].values())
    return tot


def cmd_score(out: Path) -> None:
    x1, x2, x3 = score_judge(out), score_verdict(out), score_filter(out)
    crit = {"X1a": {}, "X1b": {}, "X2a": {}, "X2b": {}, "X3": {}}
    for s in ("set2", "set3"):
        p = x1[s]["pooled"]
        ref = p["claude1_vs_claude2_with_unclear"]["agreement"]
        ref_drop = p["claude1_vs_claude2"]["agreement"]
        val = p["vs_first"]["agreement"]
        crit["X1a"][s] = {
            "decision1_vs_first_agreement": val,
            "decision1_vs_first_on_second_items": p["vs_first_on_second_items"]["agreement"],
            "second_vs_first_agreement": ref,
            "second_vs_first_agreement_unclear_dropped": ref_drop,
            "rule": "Decision-1 vs first judge (all items, Claude unclear dropped) >= second "
                    "Claude judge vs first (second-judge items, as computed by "
                    "reliability.py judge-score: unclear kept as a category)",
            "met": val is not None and ref is not None and val >= ref}
    ch = x1["set3"].get("p2g_to_p2gplus", {})
    crit["X1b"] = {"F1": ch.get("F1"), "F4": ch.get("F4"),
                   "met": bool(ch) and all(ch[f]["same_sign"] for f in ("F1", "F4"))}
    for s in ("set2", "set3"):
        d, g = x2[s]["D_dec"], x2[s]["D_gpt54"]
        diff = None if d["accuracy_decided"] is None else d["accuracy_decided"] - g["accuracy_decided"]
        crit["X2a"][s] = {"D_dec_accuracy": d["accuracy_decided"],
                          "D_gpt54_accuracy": g["accuracy_decided"], "difference": rnd(diff),
                          "met": diff is not None and abs(diff) <= 0.05 + 1e-9}
        m = x2[s]["matched_recall"]
        pt = m["point"]
        crit["X2b"][s] = {"target_recall": m["target_recall_D_gpt54"],
                          "threshold": pt and pt["threshold"], "recall_there": pt and pt["recall"],
                          "false_refutations_there": pt and pt["false_refutations"],
                          "D_gpt54_false_refutations": g["false_refutations"],
                          "met": bool(pt) and pt["false_refutations"] <= g["false_refutations"]}
    for arm in ("Rdet", "P2g+", "P2g"):
        r = x3[arm]["rules"]
        crit["X3"][arm] = {"default": r["keep_default"], "p_hard_0.7": r["keep_p07"],
                           "met_default": r["keep_default"]["met"],
                           "met_p07": r["keep_p07"]["met"], "exploratory": True}
    usage = _usage_all(out)
    m = {"created_utc": now(), "plan_addendum_D_sha256": sha(addendum_text()),
         "script_sha256": sha(Path(__file__).read_bytes()), "model": MODEL,
         "thresholds": {"noul_yes": THRESHOLD, "hard": HARD_THRESHOLD},
         "X1_judge": x1, "X2_verdict": x2, "X3_filter": x3, "criteria": crit,
         "usage": usage}
    write_json(out / "metrics.json", m)
    refreeze(out)
    print(json.dumps(crit, indent=1))
    print(json.dumps({k: v for k, v in usage.items() if k != "per_arm"}))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["judge", "verdict", "filter", "score"])
    ap.add_argument("out", type=Path)
    ap.add_argument("--limit", type=int, default=None, help="items per set/arm (smoke test)")
    ap.add_argument("--only", nargs="*", default=None,
                    help="sets (judge: set2 set3 scout; verdict: set2 set3) or arms "
                         "(filter: Rdet P2g+ P2g)")
    a = ap.parse_args()
    out = a.out if a.out.is_absolute() else ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    if a.cmd == "judge":
        cmd_judge(out, a.limit, a.only)
    elif a.cmd == "verdict":
        cmd_verdict(out, a.limit, a.only)
    elif a.cmd == "filter":
        cmd_filter(out, a.limit, a.only)
    else:
        cmd_score(out)


if __name__ == "__main__":
    main()

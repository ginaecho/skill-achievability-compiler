#!/usr/bin/env python3
"""Baseline: why not just ask a language model?

The obvious cheap alternative to a checker is to hand the skill and the tool
list to a model and ask whether the skill can be carried out. This script runs
that baseline against the same configurations for which we have GROUND TRUTH,
and scores it against the checker.

Ground truth comes from two sources, never from the checker:

  constructed  the four authored specification pairs: the A variant is
               achievable by construction, the B variant is not (the only tool
               cannot meet the stated bound, no tool establishes the guard or
               the goal condition, or the workflow names a tool nothing
               provides).
  observed     configurations the live-agent experiment settled by running
               them at realistic input size with every artifact verified by
               recomputation: a configuration in which some run produced a
               verified artifact is achievable; one in which no run of either
               model did is not.

Outputs paper/WIP/results/llm_judge.json and a table in docs/USEFULNESS.md's
sibling docs/LLM_JUDGE.md.
"""
from __future__ import annotations
import argparse, json, re, subprocess, sys, time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from skillc.profiles import load_profile
from skillc.frontend.markdown import compile_file
from skillc.checker import check

OUT = ROOT / "paper" / "WIP" / "results"
CACHE = OUT / "llm_judge_runs.jsonl"
RUNTIME_PROFILE = {"shell": "claude-code", "no-shell": "no-shell"}
TOOLS = {"shell": "Bash (run any shell command or script), Read, Write, Edit",
         "no-shell": "Read, Write, Edit (there is NO shell: no command, script or program can be executed)"}

SYSTEM = ("You are a careful engineer deciding whether a documented procedure can be carried out "
          "in a given runtime. Answer with one word, ACHIEVABLE or IMPOSSIBLE, on the first line, "
          "then one line of justification naming the blocking capability if any.")
VERDICT_RE = re.compile(r"\b(ACHIEVABLE|IMPOSSIBLE)\b", re.I)


def ground_truth() -> list[dict]:
    """Configurations whose answer is known independently of the checker."""
    items = []
    cases = sorted(p.name for p in (ROOT / "benchmarks" / "spec-cases").iterdir() if p.is_dir())
    for case in cases:
        for variant, truth in (("A", True), ("B", False)):
            f = ROOT / "benchmarks" / "spec-cases" / case / variant / "SKILL.md"
            if f.exists():
                items.append({"skill": f"benchmarks/spec-cases/{case}/{variant}/SKILL.md",
                              "runtime": "shell", "truth": truth, "source": "constructed",
                              "why": f"{case} variant {variant}"})
    runs = [json.loads(l) for l in (OUT / "usefulness_runs.jsonl").read_text().splitlines() if l.strip()]
    by = defaultdict(list)
    for r in runs:
        if "spec-cases" in r["skill"]:
            continue
        # only configurations exercised at realistic scale, or binary-format documents
        big = bool(r.get("size"))
        doc = any(k in r["skill"] for k in ("/pdf/", "/xlsx/", "/docx/"))
        if big or doc:
            by[(r["skill"], r["runtime"])].append(r)
    for (skill, rt), rs in sorted(by.items()):
        ok = any(x["outcome"] in ("success", "verified_no_status") for x in rs)
        items.append({"skill": skill, "runtime": rt, "truth": ok, "source": "observed",
                      "why": f"{sum(x['outcome'] in ('success','verified_no_status') for x in rs)}/{len(rs)} runs produced a verified artifact"})
    return items


def ask(skill_text: str, runtime: str, model: str) -> dict:
    user = (f"RUNTIME: the agent has exactly these tools: {TOOLS[runtime]}.\n"
            f"No other tool, service, credential or network API is available unless the procedure "
            f"itself installs it with the tools above.\n\n"
            f"PROCEDURE (a skill document):\n<skill>\n{skill_text}\n</skill>\n\n"
            f"Can an agent carry out this procedure as written, in that runtime? "
            f"First line: ACHIEVABLE or IMPOSSIBLE.")
    cmd = ["claude", "-p", "--bare", "--tools", "", "--no-session-persistence",
           "--system-prompt", SYSTEM, "--model", model, "--output-format", "json", user]
    t0 = time.time()
    for attempt in range(3):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            d = json.loads(r.stdout)
            if d.get("is_error"):
                raise RuntimeError(d.get("result"))
            text = (d.get("result") or "").strip()
            m = VERDICT_RE.search(text)
            u = d.get("modelUsage") or {}
            toks = sum(v.get("inputTokens", 0) + v.get("outputTokens", 0) +
                       v.get("cacheReadInputTokens", 0) + v.get("cacheCreationInputTokens", 0)
                       for v in u.values())
            return {"verdict": (m.group(1).upper() if m else None), "text": text[:300],
                    "tokens": toks, "cost_usd": round(d.get("total_cost_usd", 0.0) or 0.0, 5),
                    "seconds": round(time.time() - t0, 1)}
        except Exception as e:                                    # noqa: BLE001
            err = e
            time.sleep(3 * (attempt + 1))
    return {"verdict": None, "text": f"<error: {err}>", "tokens": 0, "cost_usd": 0.0,
            "seconds": round(time.time() - t0, 1)}


def load_cache() -> dict:
    out = {}
    if CACHE.exists():
        for line in CACHE.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                out[(r["skill"], r["runtime"], r["model"], r["seed"])] = r
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="haiku,sonnet")
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()
    items = ground_truth()
    models = args.models.split(",")

    # the checker, for the same configurations
    for it in items:
        t0 = time.perf_counter()
        v = check(compile_file(ROOT / it["skill"], load_profile(RUNTIME_PROFILE[it["runtime"]])).pack)
        it["checker"] = v.achievable
        it["checker_reason"] = v.reason
        it["checker_ms"] = round((time.perf_counter() - t0) * 1000, 1)

    cache = load_cache()
    todo = [(it, m, s) for it in items for m in models for s in range(args.n)
            if (it["skill"], it["runtime"], m, s) not in cache]
    print(f"{len(items)} ground-truth configurations; {len(todo)} judge calls to make", file=sys.stderr)
    if not args.report_only and todo:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {}
            for it, m, s in todo:
                text = (ROOT / it["skill"]).read_text(encoding="utf-8")
                futs[ex.submit(ask, text, it["runtime"], m)] = (it, m, s)
            for f in as_completed(futs):
                it, m, s = futs[f]
                r = f.result()
                rec = {"skill": it["skill"], "runtime": it["runtime"], "model": m, "seed": s, **r}
                cache[(it["skill"], it["runtime"], m, s)] = rec
                with open(CACHE, "a") as fh:
                    fh.write(json.dumps(rec) + "\n")
                print(f"{it['skill'][-40:]:40s} {it['runtime']:8s} {m:7s} #{s} {r['verdict']}", file=sys.stderr)
    report(items, cache, models)


def report(items, cache, models):
    rows, agg = [], {}
    ck_correct = sum(it["checker"] == it["truth"] for it in items)
    for it in items:
        r = {"skill": it["skill"], "runtime": it["runtime"], "truth": it["truth"],
             "source": it["source"], "checker": it["checker"],
             "checker_correct": it["checker"] == it["truth"], "checker_ms": it["checker_ms"], "judge": {}}
        for m in models:
            vs = [cache[k]["verdict"] for k in cache
                  if k[0] == it["skill"] and k[1] == it["runtime"] and k[2] == m]
            ach = [v == "ACHIEVABLE" for v in vs if v]
            maj = (sum(ach) * 2 > len(ach)) if ach else None
            r["judge"][m] = {"votes": vs, "majority": maj,
                             "correct": (maj == it["truth"]) if maj is not None else None}
        rows.append(r)
    for m in models:
        vals = [x["judge"][m]["correct"] for x in rows if x["judge"][m]["correct"] is not None]
        runs = [v for k, v in cache.items() if k[2] == m]
        agg[m] = {"scored": len(vals), "correct": sum(vals),
                  "accuracy": round(sum(vals) / len(vals), 3) if vals else None,
                  "false_achievable": sum(1 for x in rows if x["judge"][m]["majority"] is True and x["truth"] is False),
                  "false_impossible": sum(1 for x in rows if x["judge"][m]["majority"] is False and x["truth"] is True),
                  "tokens": sum(r["tokens"] for r in runs), "cost_usd": round(sum(r["cost_usd"] for r in runs), 3)}
    checker = {"scored": len(items), "correct": ck_correct,
               "accuracy": round(ck_correct / len(items), 3),
               "false_achievable": sum(1 for x in rows if x["checker"] and not x["truth"]),
               "false_impossible": sum(1 for x in rows if not x["checker"] and x["truth"]),
               "tokens": 0, "ms_total": round(sum(x["checker_ms"] for x in rows), 1)}
    res = {"checker": checker, "judge": agg, "rows": rows, "models": models}
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(OUT / "llm_judge.json", "w"), indent=1)
    md = ["# Baseline: why not just ask a language model?", "",
          f"{len(items)} configurations whose answer is known independently of the checker: "
          f"{sum(i['source']=='constructed' for i in items)} by construction (the authored "
          f"specification pairs) and {sum(i['source']=='observed' for i in items)} by observation "
          f"(settled by verified agent runs at realistic input size).", "",
          "| decider | scored | correct | accuracy | says achievable, is not | says impossible, is not | tokens | cost |",
          "|---|---|---|---|---|---|---|---|",
          f"| **checker** | {checker['scored']} | {checker['correct']} | {checker['accuracy']} | "
          f"{checker['false_achievable']} | {checker['false_impossible']} | **0** | **$0** ({checker['ms_total']} ms) |"]
    for m, v in agg.items():
        md.append(f"| LLM judge ({m}), majority of 3 | {v['scored']} | {v['correct']} | {v['accuracy']} | "
                  f"{v['false_achievable']} | {v['false_impossible']} | {v['tokens']} | ${v['cost_usd']} |")
    md += ["", "## Per configuration", "",
           "| skill | runtime | truth | source | checker | " + " | ".join(f"judge {m}" for m in models) + " |",
           "|---|---|---|---|---|" + "---|" * len(models)]
    for r in rows:
        md.append(f"| `{r['skill']}` | {r['runtime']} | {'achievable' if r['truth'] else 'not'} | {r['source']} | "
                  f"{'achievable' if r['checker'] else r.get('checker') is False and 'refuted' or 'refuted'} "
                  f"{'✓' if r['checker_correct'] else '✗'} | "
                  + " | ".join(f"{r['judge'][m]['majority']} {'✓' if r['judge'][m]['correct'] else '✗'}" for m in models) + " |")
    (ROOT / "docs" / "LLM_JUDGE.md").write_text("\n".join(md) + "\n")
    print(json.dumps({"checker": checker, "judge": agg}, indent=1))


if __name__ == "__main__":
    main()

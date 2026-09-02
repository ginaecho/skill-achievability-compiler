#!/usr/bin/env python3
"""Tokens with the checker and tokens without it.

Three quantities, measured or estimated separately and never mixed:

  A. CHECK COST.  The deterministic front end and the checker spend no model
     tokens at all; only wall-clock. When a document carries meaning the
     deterministic reader cannot capture, `skillc autocheck` escalates to LLM
     compaction -- and only then. This script measures how often escalation
     fires over the whole corpus (free), and MEASURES the real token cost of
     escalation on a sample (`--compact N`), then estimates the rest from the
     sample's tokens-per-input-character.

  B. RUN COST.  What an agent actually spends running a skill. Taken from the
     usefulness experiment's measured runs (paper/WIP/results/usefulness_runs.jsonl),
     which record real token counts per run, and -- for corpus skills with no
     measured run -- estimated with skillc.tokens.RuntimeModel from the
     measured runs' median turn count.

  C. THE COMPARISON.  For a refuted configuration the checker's cost replaces
     the run: the saving is B - A. For a certified one the check is overhead:
     the share A/B. Both are reported, per skill and in aggregate.

Outputs paper/WIP/results/token_economics.json and docs/TOKEN_ECONOMICS.md.
"""
from __future__ import annotations
import argparse, glob, json, os, statistics, sys, time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from skillc.profiles import load_profile
from skillc.frontend.markdown import compile_file
from skillc.frontend import llm as llmmod
from skillc.checker import check
from skillc.autollm import needs_llm
from skillc.tokens import RuntimeModel, estimate_tokens, Price

OUT = ROOT / "paper" / "WIP" / "results"
CACHE = OUT / "compaction_runs.jsonl"
RUNS = OUT / "usefulness_runs.jsonl"
PROFILES = ("claude-ai", "no-shell")


def corpus() -> list[str]:
    files = sorted(glob.glob(str(ROOT / "real-skills" / "**" / "SKILL.md"), recursive=True))
    files += sorted(glob.glob(str(ROOT / "real-skills-ext" / "**" / "SKILL.md"), recursive=True))
    return files


def survey(files: list[str]) -> list[dict]:
    rows = []
    for f in files:
        text = open(f, encoding="utf-8").read()
        rec = {"path": os.path.relpath(f, ROOT), "chars": len(text), "input_tokens_est": estimate_tokens(text)}
        t0 = time.perf_counter()
        for prof in PROFILES:
            res = compile_file(f, load_profile(prof))
            v = check(res.pack)
            esc = needs_llm(text, res, v)
            rec[prof] = {"achievable": v.achievable, "reason": v.reason, "escalate": esc.needed,
                         "escalate_reasons": esc.reasons}
            if prof == "claude-ai":
                rec["escalate"] = esc.needed
                rec["escalate_reasons"] = esc.reasons
                rec["semantic_path"] = esc.signals["semantic_path"]
        rec["check_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        rec["flips"] = rec["claude-ai"]["achievable"] and not rec["no-shell"]["achievable"]
        rows.append(rec)
    return rows


def compact_one(path: str, model: str) -> dict:
    text = open(ROOT / path, encoding="utf-8").read()
    t0 = time.time()
    try:
        pack = llmmod.compact(text, model=model, runtime_abilities=llmmod.RUNTIME_ABILITY_PROFILES["developer"],
                              provider="claude-cli")
        v = check(pack)
        u = dict(llmmod.LAST_USAGE)
        return {"path": path, "model": model, "ok": True, "achievable": v.achievable, "reason": v.reason,
                "usage": u, "tokens": sum(int(u.get(k, 0)) for k in ("input_tokens", "output_tokens",
                                                                     "cache_read_input_tokens", "cache_creation_input_tokens")),
                "cost_usd": round(float(u.get("cost_usd", 0.0)), 5), "chars": len(text),
                "seconds": round(time.time() - t0, 1)}
    except Exception as e:                                           # noqa: BLE001
        return {"path": path, "model": model, "ok": False, "error": str(e)[:200], "chars": len(text),
                "seconds": round(time.time() - t0, 1)}


def load_cache() -> dict:
    out = {}
    if CACHE.exists():
        for line in CACHE.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                out[(r["path"], r["model"])] = r
    return out


def measured_runs() -> list[dict]:
    if not RUNS.exists():
        return []
    return [json.loads(l) for l in RUNS.read_text().splitlines() if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--compact", type=int, default=0, help="measure LLM compaction on N escalating skills")
    ap.add_argument("--model", default="haiku")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    files = corpus()
    rows = survey(files)
    esc = [r for r in rows if r["escalate"]]
    print(f"{len(rows)} skills; {len(esc)} would escalate to LLM compaction", file=sys.stderr)

    cache = load_cache()
    todo = [r["path"] for r in esc if (r["path"], args.model) not in cache][: args.compact]
    if todo:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(compact_one, p, args.model): p for p in todo}
            for f in as_completed(futs):
                r = f.result()
                cache[(r["path"], r["model"])] = r
                with open(CACHE, "a") as fh:
                    fh.write(json.dumps(r) + "\n")
                print(f"compacted {r['path'][-50:]:50s} ok={r['ok']} tok={r.get('tokens')} {r['seconds']}s", file=sys.stderr)

    ok = [r for r in cache.values() if r.get("ok") and r["model"] == args.model]
    # Estimate the unmeasured compactions by a least-squares line through the
    # measured ones (tokens = a + b*chars): compaction is an input that scales
    # with the document plus an output that scales with the pack, so a single
    # tokens-per-character ratio over-predicts short documents badly.
    fit = None
    if len(ok) >= 3:
        xs = [r["chars"] for r in ok]; ys = [r["tokens"] for r in ok]
        n = len(xs); mx = sum(xs) / n; my = sum(ys) / n
        den = sum((x - mx) ** 2 for x in xs)
        b = (sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den) if den else 0.0
        fit = (my - b * mx, b)
    per_char = (statistics.median([r["tokens"] / max(r["chars"], 1) for r in ok]) if ok else None)
    med_cost = statistics.median([r["cost_usd"] for r in ok]) if ok else None

    runs = measured_runs()
    run_tokens = [r["tokens"] for r in runs if r["tokens"] > 0]
    med_run_tokens = int(statistics.median(run_tokens)) if run_tokens else 0
    med_run_cost = statistics.median([r["cost_usd"] for r in runs]) if runs else 0.0
    med_turns = int(statistics.median([r["turns"] for r in runs if r["turns"] > 0])) if runs else 0
    # Two denominators, kept apart: the MEASURED median run (from the
    # usefulness experiment) and a per-skill ESTIMATE from the runtime model,
    # calibrated to the measured median turn count and each skill's size.
    rm_tokens = {}
    for r in rows:
        rm = RuntimeModel(skill_tokens=r["input_tokens_est"])
        rm_tokens[r["path"]] = rm.run_cost(med_turns or 6).total_tokens

    for r in rows:
        m = cache.get((r["path"], args.model))
        if m and m.get("ok"):
            r["compaction_tokens"] = m["tokens"]; r["compaction_measured"] = True
            r["compaction_usd"] = m["cost_usd"]
        elif r["escalate"] and fit:
            r["compaction_tokens"] = max(0, int(fit[0] + fit[1] * r["chars"])); r["compaction_measured"] = False
            r["compaction_usd"] = round(med_cost or 0.0, 5)
        else:
            r["compaction_tokens"] = 0; r["compaction_measured"] = True; r["compaction_usd"] = 0.0
        r["run_tokens_est"] = rm_tokens[r["path"]]
        r["check_share_pct"] = round(100.0 * r["compaction_tokens"] / max(r["run_tokens_est"], 1), 3)
        r["check_share_measured_pct"] = (round(100.0 * r["compaction_tokens"] / med_run_tokens, 3)
                                         if med_run_tokens else None)

    refuted_noshell = [r for r in rows if not r["no-shell"]["achievable"]]
    refuted_home = [r for r in rows if not r["claude-ai"]["achievable"]]
    total_check_tokens = sum(r["compaction_tokens"] for r in rows)
    total_run_tokens = sum(r["run_tokens_est"] for r in rows)
    # measured side: usefulness runs, split by verdict
    use = OUT / "usefulness.json"
    measured = {}
    if use.exists():
        u = json.load(open(use))
        V = u["verdicts"]

        def vd(x):
            for k in (f"{x.get('id', x['skill'])}||{x['runtime']}", f"{x['skill']}||{x['runtime']}",
                      f"{x['skill']}|{x['runtime']}"):
                if k in V:
                    return V[k]
            return None
        runs = [x for x in runs if vd(x) is not None]
        ref = [x for x in runs if not vd(x)["achievable"]]
        cert = [x for x in runs if vd(x)["achievable"]]
        wasted = [x for x in ref if x["outcome"] != "success"]
        measured = {"runs": len(runs), "refuted_runs": len(ref), "certified_runs": len(cert),
                    "wasted_runs": len(wasted),
                    "wasted_tokens": sum(x["tokens"] for x in wasted),
                    "wasted_usd": round(sum(x["cost_usd"] for x in wasted), 3),
                    "median_run_tokens": med_run_tokens, "median_run_usd": round(med_run_cost, 4),
                    "median_turns": med_turns,
                    "certified_tokens": sum(x["tokens"] for x in cert),
                    "refuted_tokens": sum(x["tokens"] for x in ref)}

    agg = {"skills": len(rows), "escalate": len(esc), "escalate_pct": round(100.0 * len(esc) / len(rows), 1),
           "semantic_path": sum(r["semantic_path"] for r in rows),
           "certified_home": sum(r["claude-ai"]["achievable"] for r in rows),
           "refuted_home": len(refuted_home), "refuted_no_shell": len(refuted_noshell),
           "flips": sum(r["flips"] for r in rows),
           "escalate_no_shell": sum(r["no-shell"]["escalate"] for r in rows),
           "free_refutations_no_shell": sum((not r["no-shell"]["achievable"]) for r in rows),
           "check_ms_total": round(sum(r["check_ms"] for r in rows), 1),
           "check_ms_median": round(statistics.median([r["check_ms"] for r in rows]), 1),
           "compaction_measured": len(ok), "compaction_tokens_median": int(statistics.median([r["tokens"] for r in ok])) if ok else None,
           "compaction_usd_median": round(med_cost, 5) if med_cost else None,
           "compaction_tokens_per_char": round(per_char, 3) if per_char else None,
           "compaction_fit_intercept": round(fit[0]) if fit else None,
           "compaction_fit_slope": round(fit[1], 3) if fit else None,
           "corpus_check_tokens": total_check_tokens, "corpus_run_tokens_est": total_run_tokens,
           "check_share_of_runtime_pct": round(100.0 * total_check_tokens / max(total_run_tokens, 1), 3),
           "check_share_median_pct": round(statistics.median([r["check_share_pct"] for r in rows]), 3),
           "free_skills": sum(r["compaction_tokens"] == 0 for r in rows),
           "escalated_share_of_measured_run_pct": (round(100.0 * (statistics.median([r["tokens"] for r in ok]) if ok else 0)
                                                         / med_run_tokens, 1) if med_run_tokens and ok else None),
           "runs_saved_per_escalation": (round((statistics.median([r["tokens"] for r in ok]) if ok else 0)
                                               / med_run_tokens, 2) if med_run_tokens and ok else None),
           "measured": measured, "model": args.model}
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump({"aggregate": agg, "rows": rows}, open(OUT / "token_economics.json", "w"), indent=1)

    md = ["# Tokens with the checker and without it", "",
          f"{agg['skills']} real skills. The deterministic check spends **no model tokens**; "
          f"median {agg['check_ms_median']} ms per skill, {agg['check_ms_total']:.0f} ms for the corpus.", "",
          "## When is an LLM needed?", "",
          f"The escalation detector (`skillc autocheck`) fires on **{agg['escalate']} of {agg['skills']}** skills "
          f"({agg['escalate_pct']}%): the document carries completion language, guards or irreversible verbs that the "
          f"deterministic reader could not turn into a pack, and the deterministic verdict is a CERTIFICATION, "
          f"which the weak reading cannot support. The other {agg['skills'] - agg['escalate']} are settled for free. "
          f"In the file-only runtime the picture inverts: {agg['free_refutations_no_shell']} skills are REFUTED, and a "
          f"refutation on the weak reading is sound whatever the document means, so only {agg['escalate_no_shell']} "
          f"escalate there. {agg['semantic_path']} skills took the semantic path.", "",
          "## What escalation costs (measured)", "",
          f"| | value |", "|---|---|",
          f"| compactions measured ({args.model}) | {agg['compaction_measured']} |",
          f"| median tokens per compaction | {agg['compaction_tokens_median']} |",
          f"| median USD per compaction | {agg['compaction_usd_median']} |",
          f"| tokens per input character | {agg['compaction_tokens_per_char']} |",
          f"| estimate for unmeasured skills | {agg['compaction_fit_intercept']} + {agg['compaction_fit_slope']} x chars |", "",
          "## Against what an agent run costs", "",
          f"| | value |", "|---|---|",
          f"| measured agent runs (usefulness experiment) | {measured.get('runs', 0)} |",
          f"| median tokens per run | {measured.get('median_run_tokens', 0)} |",
          f"| median USD per run | {measured.get('median_run_usd', 0)} |",
          f"| median turns per run | {measured.get('median_turns', 0)} |",
          f"| tokens spent on runs the checker refuted and that failed | {measured.get('wasted_tokens', 0)} |",
          f"| USD on those runs | {measured.get('wasted_usd', 0)} |", "",
          "## The comparison", "",
          f"Two regimes, and they are not close.", "",
          f"**Where the check is free** ({agg['free_skills']} of {agg['skills']} skills, including all "
          f"{agg['free_refutations_no_shell']} refutations in the file-only runtime): the check costs "
          f"**0 model tokens** and {agg['check_ms_median']} ms. Each refutation replaces an agent run whose measured "
          f"median is {measured.get('median_run_tokens', 0)} tokens (${measured.get('median_run_usd', 0)}). In the "
          f"usefulness experiment the runs the checker refuted and that then failed cost "
          f"{measured.get('wasted_tokens', 0)} tokens (${measured.get('wasted_usd', 0)}) --- the checker would have "
          f"spent none of it.", "",
          f"**Where the check needs an LLM** ({agg['escalate']} skills in the home runtime, where the deterministic "
          f"pack can only certify weakly): one compaction costs a median {agg['compaction_tokens_median']} tokens, "
          f"i.e. **{agg['escalated_share_of_measured_run_pct']}%** of one measured agent run "
          f"({agg['runs_saved_per_escalation']} runs). It is paid once per skill version and amortizes over every "
          f"run of that skill; against the per-skill runtime estimate the corpus share is "
          f"{agg['check_share_of_runtime_pct']}% (median {agg['check_share_median_pct']}%).", "",
          "## Per skill", "", "| skill | home | no-shell | escalate | compaction tokens | est. run tokens | check share |",
          "|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda x: -x["compaction_tokens"])[:40]:
        md.append(f"| `{r['path']}` | {'ok' if r['claude-ai']['achievable'] else r['claude-ai']['reason']} | "
                  f"{'ok' if r['no-shell']['achievable'] else r['no-shell']['reason']} | {'yes' if r['escalate'] else 'no'} | "
                  f"{r['compaction_tokens']}{'' if r['compaction_measured'] else ' (est)'} | {r['run_tokens_est']} | {r['check_share_pct']}% |")
    (ROOT / "docs" / "TOKEN_ECONOMICS.md").write_text("\n".join(md) + "\n")
    print(json.dumps(agg, indent=1))


if __name__ == "__main__":
    main()

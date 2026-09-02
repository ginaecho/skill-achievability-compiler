#!/usr/bin/env python3
"""Is the checker USEFUL?  Real skills, real agents, two runtimes.

For every (skill, task) pair in scripts/usefulness_tasks.json (real SKILL.md
files from public repositories, plus the authored specification cases in
benchmarks/spec-cases/) we do two things in each of two runtimes:

  checker:  compile the skill against the runtime's capability profile and
            decide achievability (milliseconds, no model);
  agent:    give a live agent (Claude Code in print mode, sandboxed in an
            empty directory, tools restricted to the runtime) the skill and
            the task, let it run, and VERIFY the artifact it produces.

Runtimes:  shell     Bash + file tools     (profile claude-code)
           no-shell  file tools only       (profile no-shell)

Outcomes of an agent run: success (claims done, artifact verified);
silent_wrong (claims done, artifact fails verification); honest_fail (claims
failed); no_status.  The comparison the paper makes is between running the
agent unconditionally and running it only where the checker certifies: on a
refuted configuration the unchecked agent's tokens are waste and its "done"
is a wrong result nobody detects.

Cached in paper/WIP/results/usefulness_runs.jsonl; outputs
paper/WIP/results/usefulness.json and docs/USEFULNESS.md.
"""
from __future__ import annotations
import argparse, json, os, re, shutil, subprocess, sys, tempfile, time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "paper" / "WIP" / "results"
RUNS = OUT / "usefulness_runs.jsonl"
TASKS = ROOT / "scripts" / "usefulness_tasks.json"

RUNTIMES = {
    "shell": {"profile": "claude-code", "tools": "Bash,Read,Write,Edit", "allowed": "Bash Read Write Edit"},
    "no-shell": {"profile": "no-shell", "tools": "Read,Write,Edit", "allowed": "Read Write Edit"},
}
STATUS_RE = re.compile(r"STATUS:\s*(done|failed)", re.I)


def checker_verdict(skill_path: str, profile_name: str) -> dict:
    from skillc.profiles import load_profile
    from skillc.frontend.markdown import compile_file
    from skillc.checker import check
    t0 = time.perf_counter()
    res = compile_file(str(ROOT / skill_path), load_profile(profile_name))
    v = check(res.pack)
    dt = time.perf_counter() - t0
    return {"achievable": v.achievable, "reason": v.reason, "detail": (v.detail or "")[:200],
            "ms": round(dt * 1000, 1)}


def prepare_sandbox(task: dict) -> str:
    d = tempfile.mkdtemp(prefix="usefulness_")
    if task.get("assets_dir"):
        shutil.copytree(ROOT / task["assets_dir"], d, dirs_exist_ok=True)
    shutil.copy(ROOT / task["skill"], os.path.join(d, "SKILL.md"))
    inputs = task.get("inputs") or {}
    gen = inputs.pop("generate_with_python", None) if isinstance(inputs, dict) else None
    for name, content in (inputs or {}).items():
        with open(os.path.join(d, name), "w") as fh:
            fh.write(content)
    if gen:
        subprocess.run([sys.executable, "-c", gen], cwd=d, check=False, capture_output=True, timeout=120)
    return d


def verify(task: dict, d: str) -> bool:
    code = task["verify"].strip()
    prog = code if "\n" in code or code.startswith("import") else f"print(bool({code}))"
    if "\n" in code and "print(" not in code:
        prog = code + "\nprint(True)"
    r = subprocess.run([sys.executable, "-c", prog], cwd=d, capture_output=True, text=True, timeout=120)
    return r.returncode == 0 and r.stdout.strip().splitlines()[-1:] == ["True"]


def run_agent(task: dict, runtime: str, model: str, seed: int, max_turns: int, budget: float) -> dict:
    rt = RUNTIMES[runtime]
    d = prepare_sandbox(task)
    skill_text = open(os.path.join(d, "SKILL.md"), encoding="utf-8").read()
    prompt = (f"You are an agent with the following skill loaded (it is also saved as ./SKILL.md):\n\n"
              f"<skill>\n{skill_text}\n</skill>\n\n"
              f"Task: {task['task']}\n\nWork only inside the current directory. Use only the tools you actually have. "
              f"When you are finished, end your reply with exactly one line `STATUS: done` if the task was completed "
              f"as requested, or `STATUS: failed` if it was not, followed by one line of justification.")
    cmd = ["claude", "-p", "--permission-mode", "acceptEdits", "--allowedTools", rt["allowed"],
           "--tools", rt["tools"], "--no-session-persistence", "--max-turns", str(max_turns),
           "--max-budget-usd", str(budget), "--model", model, "--output-format", "json", prompt]
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=d, capture_output=True, text=True, timeout=900)
        data = json.loads(r.stdout)
    except Exception as e:                                       # noqa: BLE001
        data = {"result": f"<agent error: {e}>", "num_turns": 0, "total_cost_usd": 0.0, "modelUsage": {}}
    elapsed = time.time() - t0
    text = data.get("result") or ""
    m = STATUS_RE.findall(text)
    claim = m[-1].lower() if m else None
    ok = False
    try:
        ok = verify(task, d)
    except Exception:                                            # noqa: BLE001
        ok = False
    usage = data.get("modelUsage") or {}
    toks = sum((u.get("inputTokens", 0) + u.get("outputTokens", 0) + u.get("cacheReadInputTokens", 0)
                + u.get("cacheCreationInputTokens", 0)) for u in usage.values())
    outcome = ("success" if claim == "done" and ok else "silent_wrong" if claim == "done"
               else "honest_fail" if claim == "failed" else ("verified_no_status" if ok else "no_status"))
    shutil.rmtree(d, ignore_errors=True)
    return {"skill": task["skill"], "id": task.get("id", task["skill"]), "size": task.get("size"),
            "runtime": runtime, "model": model, "seed": seed,
            "claim": claim, "verified": ok, "outcome": outcome, "turns": data.get("num_turns", 0),
            "cost_usd": round(data.get("total_cost_usd", 0.0) or 0.0, 5), "tokens": toks,
            "seconds": round(elapsed, 1), "tail": text[-300:]}


def load_runs() -> dict:
    runs = {}
    if RUNS.exists():
        for line in RUNS.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                runs[(r.get("id", r["skill"]), r["runtime"], r["model"], r["seed"])] = r
    return runs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="haiku,sonnet")
    ap.add_argument("--n", type=int, default=2)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-turns", type=int, default=12)
    ap.add_argument("--budget", type=float, default=0.6)
    ap.add_argument("--only", default="")
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()
    tasks = json.load(open(TASKS)) if TASKS.exists() else []
    for extra in ("usefulness_spec_tasks.json", "usefulness_tasks_large.json"):
        f = ROOT / "scripts" / extra
        if f.exists():
            tasks += json.load(open(f))
    for t in tasks:                       # scale-up entries share a skill path
        t["id"] = t["skill"] + ("|" + t["size"] if t.get("size") else "")
    tasks = [t for t in tasks if t.get("feasible_with_shell") and t.get("needs_shell")]
    if args.only:
        want = set(args.only.split(","))
        tasks = [t for t in tasks if any(w in t["skill"] for w in want)]
    models = args.models.split(",")
    def rts(t):
        return t.get("runtimes") or list(RUNTIMES)
    verdicts = {(t["id"], rt): checker_verdict(t["skill"], RUNTIMES[rt]["profile"])
                for t in tasks for rt in rts(t)}
    runs = load_runs()
    todo = [(t, rt, m, s) for t in tasks for rt in rts(t) for m in models for s in range(args.n)
            if (t["id"], rt, m, s) not in runs]
    print(f"{len(tasks)} tasks; {len(todo)} agent runs to do, {len(runs)} cached", file=sys.stderr)
    if not args.report_only:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(run_agent, t, rt, m, s, args.max_turns, args.budget): (t["id"], rt, m, s)
                    for t, rt, m, s in todo}
            for f in as_completed(futs):
                key = futs[f]
                try:
                    r = f.result()
                except Exception as e:                          # noqa: BLE001
                    print("FAILED", key, e, file=sys.stderr); continue
                runs[key] = r
                with open(RUNS, "a") as fh:
                    fh.write(json.dumps(r) + "\n")
                print(f"{r['skill'][-40:]:40s} {r['runtime']:8s} {r['model']:7s} #{r['seed']} "
                      f"{r['outcome']:16s} turns={r['turns']:2d} ${r['cost_usd']:.3f} {r['seconds']}s", file=sys.stderr)
    report(tasks, verdicts, runs, models)


def report(tasks, verdicts, runs, models):
    rows = []
    for t in tasks:
        for rt in (t.get("runtimes") or list(RUNTIMES)):
            v = verdicts[(t["id"], rt)]
            rs = [r for r in runs.values() if r.get("id", r["skill"]) == t["id"] and r["runtime"] == rt]
            c = defaultdict(int)
            for r in rs:
                c[r["outcome"]] += 1
            rows.append({"skill": t["skill"], "size": t.get("size"), "runtime": rt, "checker": "certified" if v["achievable"] else f"refuted:{v['reason']}",
                         "checker_ms": v["ms"], "runs": len(rs), **{k: c[k] for k in ("success", "silent_wrong", "honest_fail", "no_status", "verified_no_status", "timeout")},
                         "cost_usd": round(sum(r["cost_usd"] for r in rs), 3), "tokens": sum(r["tokens"] for r in rs),
                         "seconds": round(sum(r["seconds"] for r in rs), 1)})
    refuted = [r for r in rows if r["checker"].startswith("refuted")]
    certified = [r for r in rows if r["checker"] == "certified"]
    agg = {
        "tasks": len(tasks), "agent_runs": len(runs),
        "refuted_configs": len(refuted),
        "refuted_runs": sum(r["runs"] for r in refuted),
        "refuted_success": sum(r["success"] for r in refuted),
        "refuted_silent_wrong": sum(r["silent_wrong"] for r in refuted),
        "refuted_honest_fail": sum(r["honest_fail"] for r in refuted),
        "refuted_cost_usd": round(sum(r["cost_usd"] for r in refuted), 3),
        "refuted_tokens": sum(r["tokens"] for r in refuted),
        "refuted_seconds": round(sum(r["seconds"] for r in refuted), 1),
        "certified_configs": len(certified),
        "certified_runs": sum(r["runs"] for r in certified),
        "certified_success": sum(r["success"] for r in certified),
        "certified_silent_wrong": sum(r["silent_wrong"] for r in certified),
        "certified_honest_fail": sum(r["honest_fail"] for r in certified),
        "certified_cost_usd": round(sum(r["cost_usd"] for r in certified), 3),
        "checker_total_ms": round(sum(r["checker_ms"] for r in rows), 1),
        "models": models,
    }
    per_model = {}
    for m in models:
        rr = [r for r in runs.values() if r["model"] == m]
        ref = [r for r in rr if not verdicts[(r.get("id", r["skill"]), r["runtime"])]["achievable"]]
        cert = [r for r in rr if verdicts[(r.get("id", r["skill"]), r["runtime"])]["achievable"]]
        per_model[m] = {"refuted_runs": len(ref), "refuted_silent_wrong": sum(r["outcome"] == "silent_wrong" for r in ref),
                        "refuted_honest_fail": sum(r["outcome"] == "honest_fail" for r in ref),
                        "refuted_success": sum(r["outcome"] == "success" for r in ref),
                        "refuted_cost_usd": round(sum(r["cost_usd"] for r in ref), 3),
                        "certified_runs": len(cert), "certified_success": sum(r["outcome"] == "success" for r in cert),
                        "certified_silent_wrong": sum(r["outcome"] == "silent_wrong" for r in cert),
                        "certified_cost_usd": round(sum(r["cost_usd"] for r in cert), 3)}
    res = {"aggregate": agg, "per_model": per_model, "rows": rows,
           "verdicts": {f"{k[0]}||{k[1]}": v for k, v in verdicts.items()}}
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(OUT / "usefulness.json", "w"), indent=1)
    md = ["# Is the checker useful? Real skills, real agents, two runtimes", "",
          f"{agg['tasks']} skills/tasks, {agg['agent_runs']} agent runs, models {models}.", "",
          "## Aggregate", "", "| | refuted by the checker | certified by the checker |", "|---|---|---|",
          f"| configurations (skill × runtime) | {agg['refuted_configs']} | {agg['certified_configs']} |",
          f"| agent runs | {agg['refuted_runs']} | {agg['certified_runs']} |",
          f"| success (verified) | {agg['refuted_success']} | {agg['certified_success']} |",
          f"| silent wrong (claims done, fails verification) | {agg['refuted_silent_wrong']} | {agg['certified_silent_wrong']} |",
          f"| honest failure | {agg['refuted_honest_fail']} | {agg['certified_honest_fail']} |",
          f"| agent cost (USD) | {agg['refuted_cost_usd']} | {agg['certified_cost_usd']} |",
          f"| agent tokens | {agg['refuted_tokens']} | — |",
          f"| checker time, all configurations | {agg['checker_total_ms']} ms | |", "",
          "## Per model", "", "| model | refuted runs | silent wrong | honest fail | success | cost | certified runs | success | silent wrong | cost |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for m, v in per_model.items():
        md.append(f"| {m} | {v['refuted_runs']} | {v['refuted_silent_wrong']} | {v['refuted_honest_fail']} | {v['refuted_success']} | ${v['refuted_cost_usd']} | {v['certified_runs']} | {v['certified_success']} | {v['certified_silent_wrong']} | ${v['certified_cost_usd']} |")
    md += ["", "## Per skill and runtime", "", "| skill | runtime | checker (ms) | runs | success | silent wrong | honest fail | no status | timeout | cost | tokens |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['skill']} | {r['runtime']} | {r['checker']} ({r['checker_ms']}) | {r['runs']} | {r['success']} | {r['silent_wrong']} | {r['honest_fail']} | {r['no_status'] + r['verified_no_status']} | {r['timeout']} | ${r['cost_usd']} | {r['tokens']} |")
    (ROOT / "docs" / "USEFULNESS.md").write_text("\n".join(md) + "\n")
    print(json.dumps(agg, indent=1))


if __name__ == "__main__":
    main()

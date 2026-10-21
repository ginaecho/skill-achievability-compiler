"""Experiment R: compaction reliability and baselines (runs/20261015_review_response/PLAN.md).

  prepare OUT        freeze the 100 set2 documents, the claude-code-cloud manifest and
                     every round-1 prompt (frozen.json, sha256 of each)
  run OUT [--arm A]  call the models for every job whose output is missing; P2g arms
                     chain a located-error retry (round 2) and one guarded
                     counterexample repair (round 3), exactly as P2g
  score OUT          deterministic: results.json (one row per case/arm/sample) and
                     metrics.json (every metric and criterion R1..R5 of the PLAN)
  judge-prep OUT     blind fidelity items for sample 0 of P2g (no verdict, no truth)
  judge-score OUT    F1..F5 yes-rates, second-judge agreement, fills R5

  prepare OUT --set set3   the set3 validation of PLAN.md Addenda B and C (arms P2g,
                     P2g+, Rdet, D; P2g+ ∪ Rdet derived by score); run, score,
                     judge-prep and judge-score read frozen.json["experiment"] and
                     dispatch to the set3 code at the end of this file

  prepare --set benchmark/claude_env/set4 --out OUT   PLAN.md Addendum E (arms P2g+,
                     P2g++, Rllm, Rdet, Rdet2, D; unions U1 = P2g+ ∪ Rdet and
                     U2 = P2g++ ∪ Rdet2 ∪ Rllm derived by score); --arm / --samples
                     restrict a development run; run --dry-run lists pending jobs
  full --set DIR --out OUT [--prepare-only]   prepare + run + score (Addendum E)

Arms: P2g (gpt-5.4, samples 0..4), P2g-x (DeepSeek-V4-Pro, sample 0), D (gpt-5.4
direct verdict), D-x (DeepSeek direct verdict).  P, T and skillc are computed by
`score` on every P2g / P2g-x pack.

Model calls need the Azure CLI login and (in this shell)
  env -u AZURE_SUBSCRIPTION_ID -u AZURE_TENANT_ID \
      AZURE_OPENAI_ENDPOINT="https://foundary-tzuc06.openai.azure.com/openai/v1" \
      python scripts/reliability.py run OUT
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import random
import sys
import threading
import time
import traceback
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from skillc import check  # noqa: E402
from skillc.baselines import invoked_tools, planner_only, tool_lint  # noqa: E402
from skillc.formula import atoms  # noqa: E402
from skillc.frontend import providers  # noqa: E402
from skillc.frontend.ce import CEError, extract_ce, parse_ce_detailed, render_ce  # noqa: E402
from skillc.frontend.prompts import (CE_REPAIR_PROMPT, CE_RETRY_PROMPT,  # noqa: E402
                                     ce_runtime_messages, direct_messages,
                                     explain_refutation)
from skillc.frontend.providers import extract_json_object, metered  # noqa: E402
from skillc.frontend.runtime import bind_runtime, load_runtime, repair_violations  # noqa: E402
from skillc.pack import PackError, validate_pack  # noqa: E402

SET2 = ROOT / "benchmark" / "claude_env" / "set2"
RUNTIME = "claude-code-cloud"
MANIFEST = ROOT / "src" / "skillc" / "data" / "runtimes" / f"{RUNTIME}.json"
GPT, DS = "gpt-5.4", "DeepSeek-V4-Pro"
# arm -> (kind, model, samples)
ARMS = {"P2g": ("ce", GPT, 5), "P2g-x": ("ce", DS, 1),
        "D": ("direct", GPT, 1), "D-x": ("direct", DS, 1)}
CE_ARMS = [a for a, v in ARMS.items() if v[0] == "ce"]
TRUTH_MAP = {"BLOCKED": "IMPOSSIBLE", "ACHIEVABLE": "ACHIEVABLE"}
LABELS = ("ACHIEVABLE", "IMPOSSIBLE", "UNKNOWN", "INVALID")
TIMEOUT = 600
WORKERS = 6
RUBRIC = {
    "F1": "no invented Tool (every Tool corresponds to an instruction)",
    "F2": "no omitted mandatory step",
    "F3": "the Goal states the document's deliverable",
    "F4": "no invented ordering (every protocol order is stated or implied by the document)",
    "F5": "bindings plausible (each `via` names a runtime tool that can perform the Tool)",
}
IMPL_FILES = ["scripts/reliability.py", "src/skillc/baselines.py",
              "src/skillc/frontend/ce.py", "src/skillc/frontend/prompts.py",
              "src/skillc/frontend/runtime.py", "src/skillc/frontend/providers.py",
              "src/skillc/checker.py", "src/skillc/pack.py", "src/skillc/formula.py",
              "src/skillc/session.py", f"src/skillc/data/runtimes/{RUNTIME}.json"]


# ------------------------------------------------------------------ helpers
# wilson, mcnemar_exact, write_json and sha are copied from scripts/benchmark_ce.py
# (importing that module pulls in frontend.llm, which is being edited elsewhere).

def sha(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def wilson(k: int, n: int, z: float = 1.96) -> list:
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 4), round(c + h, 4)]


def mcnemar_exact(b: int, c: int) -> float | None:
    """Two-sided exact McNemar p-value over discordant pairs (b, c)."""
    n = b + c
    if n == 0:
        return None
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return round(min(1.0, 2 * p), 6)


def jaccard(a: set, b: set) -> float:
    return 1.0 if not a and not b else len(a & b) / len(a | b)


def rnd(x, k: int = 4):
    return None if x is None else round(x, k)


def impl_hashes() -> dict:
    return {f: sha((ROOT / f).read_bytes()) for f in IMPL_FILES}


def out_rel(arm: str, case: str, sample: int, rnd_: int = 1) -> tuple[str, str]:
    stem = f"{case}__s{sample}" + ("" if rnd_ == 1 else f"__r{rnd_}")
    return f"prompts/{arm}/{stem}.json", f"outputs/{arm}/{stem}.txt"


def usage_path(out: Path, rel_output: str) -> Path:
    return out / rel_output.replace(".txt", ".usage.json")


# ------------------------------------------------------------------ prepare

def prepare(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=False)
    rt = load_runtime(str(MANIFEST))
    meta = read_json(SET2 / "cases.json")
    cases, jobs = [], []
    for c in meta["cases"]:
        text = (SET2 / "cases" / f"{c['case']}.md").read_text(encoding="utf-8")
        h = sha((SET2 / "cases" / f"{c['case']}.md").read_bytes())
        if h != c["sha256"]:
            raise ValueError(f"{c['case']}: text sha256 {h} != cases.json {c['sha256']}")
        cases.append({"case": c["case"], "id": c["id"], "kind": c["kind"],
                      "repo_url": c["repo_url"], "commit": c["commit"],
                      "path_in_repo": c["path_in_repo"], "text_sha256": h})
        prompts = {"ce": ce_runtime_messages(text, rt), "direct": direct_messages(text, rt)}
        for arm, (kind, model, n) in ARMS.items():
            system, user = prompts[kind]
            for s in range(n):
                prel, orel = out_rel(arm, c["case"], s)
                write_json(out / prel, {"system": system, "user": user})
                jobs.append({"case": c["case"], "arm": arm, "model": model, "sample": s,
                             "round": 1, "prompt": prel, "output": orel,
                             "prompt_sha256": sha((out / prel).read_bytes())})
    (out / "runtime.json").write_bytes(MANIFEST.read_bytes())
    write_json(out / "frozen.json", {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "plan": "runs/20261015_review_response/PLAN.md#experiment-r",
        "set": "benchmark/claude_env/set2", "seed": meta["seed"],
        "runtime": RUNTIME, "runtime_sha256": sha(MANIFEST.read_bytes()),
        "arms": {a: {"kind": k, "model": m, "samples": n} for a, (k, m, n) in ARMS.items()},
        "bind": {"prune": False, "library": None, "software": False},
        "cases": cases, "jobs": jobs, "implementation_sha256": impl_hashes()})
    print(f"prepared {len(cases)} cases, {len(jobs)} round-1 jobs in {out}")


# ------------------------------------------------------------------ parsing

class _B:  # the Binding fields explain_refutation reads
    def __init__(self, withdrawn, blocked):
        self.withdrawn, self.blocked = withdrawn, blocked


def parse_p2g(text: str, rt) -> dict:
    """Parse, gate and bind one CE reply (benchmark_ce_runtime.parse_reply, ce_rt,
    no pruning, no library, no software resolution)."""
    try:
        parsed = parse_ce_detailed(extract_ce(text))
        validate_pack(parsed.pack)
        b = bind_runtime(parsed.pack, parsed.bindings, rt, prune=False, library=None,
                         software=False)
        return {"ok": True, "pack": b.pack, "parsed": parsed, "withdrawn": b.withdrawn,
                "blocked": b.blocked}
    except (PackError, CEError, ValueError, KeyError, TypeError, RecursionError) as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def parse_direct(text: str) -> dict:
    try:
        obj = extract_json_object(text)
        v = str(obj.get("verdict", "")).strip().upper()
        if v not in ("ACHIEVABLE", "IMPOSSIBLE", "UNKNOWN"):
            return {"ok": False, "verdict": "INVALID", "error": f"verdict {v!r}"}
        return {"ok": True, "verdict": v, "missing": obj.get("missing") or []}
    except (ValueError, TypeError, AttributeError) as e:
        return {"ok": False, "verdict": "INVALID", "error": f"{type(e).__name__}: {e}"}


def safe_check(pack: dict):
    try:
        return check(pack), None
    except Exception as e:  # noqa: BLE001 -- recorded, never hidden
        return None, f"{type(e).__name__}: {e}"


# ------------------------------------------------------------------ run

class Log:
    def __init__(self, path: Path):
        self.path, self.lock = path, threading.Lock()

    def __call__(self, msg: str) -> None:
        line = f"{datetime.now(timezone.utc).strftime('%H:%M:%S')} {msg}"
        with self.lock:
            print(line, flush=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")


_TOKEN = {"value": None, "at": 0.0}
_TOKEN_LOCK = threading.Lock()
_ORIG_TOKEN = providers.azure_cli_token


def _cached_token() -> str:
    """One Azure CLI token per 30 minutes instead of one `az` call per request."""
    with _TOKEN_LOCK:
        if _TOKEN["value"] is None or time.time() - _TOKEN["at"] > 1800:
            _TOKEN["value"], _TOKEN["at"] = _ORIG_TOKEN(), time.time()
        return _TOKEN["value"]


providers.azure_cli_token = _cached_token


def _transient(e: Exception) -> bool:
    s = str(e)
    if isinstance(e, RuntimeError) and ("HTTP 429" in s or "HTTP 5" in s):
        return True
    return isinstance(e, (TimeoutError, ConnectionError, OSError)) and not isinstance(
        e, RuntimeError)


def call_model(system: str, user: str, model: str, json_mode: bool, log: Log, tag: str):
    """One completion with backoff on 429/5xx/network errors (5 tries)."""
    for attempt in range(5):
        t0 = time.time()
        try:
            with metered() as usage:
                text = providers.azure_openai_complete(system, user, model, TIMEOUT,
                                                       json_mode=json_mode)
            return text, list(usage), json_mode, round(time.time() - t0, 1)
        except Exception as e:  # noqa: BLE001
            if json_mode and "HTTP 400" in str(e) and "response_format" in str(e):
                log(f"{tag}: response_format rejected, falling back to json_mode=False")
                json_mode = False
                continue
            if attempt < 4 and _transient(e):
                wait = 10 * 2 ** attempt + random.uniform(0, 5)
                log(f"{tag}: {type(e).__name__}: {str(e)[:160]} -- retry in {wait:.0f}s")
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("unreachable")


def _execute(out: Path, job: dict, log: Log) -> str:
    """Run one prompt file unless its output exists; returns the reply text."""
    o = out / job["output"]
    if o.exists():
        return o.read_text(encoding="utf-8")
    prompt = read_json(out / job["prompt"])
    kind = ARMS[job["arm"]][0]
    tag = f"{job['arm']}/{job['case']}/s{job['sample']}/r{job['round']}"
    text, usage, jm, secs = call_model(prompt["system"], prompt["user"], job["model"],
                                       kind == "direct", log, tag)
    write_json(usage_path(out, job["output"]), {
        "model": job["model"], "json_mode": jm, "elapsed_s": secs, "usage": usage,
        "utc": datetime.now(timezone.utc).isoformat()})
    o.parent.mkdir(parents=True, exist_ok=True)
    o.write_text(text, encoding="utf-8")
    tok = sum(u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) for u in usage)
    log(f"{tag}: done {secs}s in={tok} out={sum(u.get('output_tokens', 0) for u in usage)}")
    return text


def _followup(out: Path, job: dict, rnd_: int, user_tail: str) -> dict:
    """Write a round-2/3 prompt (base system + base user + tail) and return its job."""
    base = read_json(out / job["prompt"])
    prel, orel = out_rel(job["arm"], job["case"], job["sample"], rnd_)
    if not (out / prel).exists():
        write_json(out / prel, {"system": base["system"], "user": base["user"] + user_tail})
    return {**job, "round": rnd_, "prompt": prel, "output": orel,
            "prompt_sha256": sha((out / prel).read_bytes())}


def _pool(out: Path, jobs: list[dict], log: Log, what: str, workers: int = WORKERS,
          execute=None) -> list[str]:
    """Model calls only, in WORKERS threads.  z3 is not thread-safe (an AST
    assertion crashes the process), so every parse/bind/check runs in the main
    thread between the rounds."""
    failed = []
    execute = execute or _execute
    with ThreadPoolExecutor(workers) as pool:
        futs = {pool.submit(execute, out, j, log): j for j in jobs}
        for k, f in enumerate(as_completed(futs), 1):
            j = futs[f]
            try:
                f.result()
            except Exception as e:  # noqa: BLE001
                failed.append(f"{j['arm']}/{j['case']}/s{j['sample']}/r{j['round']}")
                log(f"FAILED {failed[-1]}: {type(e).__name__}: {str(e)[:300]} "
                    f"{traceback.format_exc(limit=3)}")
            if k % 25 == 0 or k == len(jobs):
                log(f"progress {what}: {k}/{len(jobs)}")
    return failed


def run(out: Path, arms: list[str] | None, limit: int | None,
        only_cases: list[str] | None = None, samples: list[int] | None = None) -> None:
    """Round 1 for every job; then, for P2g arms, as in benchmark_ce_runtime
    (retry, repair, score_all): round 2 = one located-error retry (CE_RETRY_PROMPT)
    when round 1 does not parse, gate and bind; round 3 = one counterexample-guided
    repair (CE_REPAIR_PROMPT + explain_refutation, added to the round-1 prompt as
    benchmark_ce_runtime.repair does) when the current final pack is IMPOSSIBLE.
    Whether a repair is kept (repair_violations guard) is decided by `score`."""
    frozen = read_json(out / "frozen.json")
    rt = load_runtime(str(out / "runtime.json"))
    log = Log(out / "run.log")
    jobs = [j for j in frozen["jobs"] if j["round"] == 1 and (not arms or j["arm"] in arms)]
    for j in jobs:
        if sha((out / j["prompt"]).read_bytes()) != j["prompt_sha256"]:
            raise ValueError(f"prompt changed: {j['prompt']}")
    if only_cases:
        jobs = [j for j in jobs if j["case"] in only_cases]
    if samples is not None:
        jobs = [j for j in jobs if j["sample"] in samples]
    if limit:
        jobs = jobs[:limit]
    log(f"run: {len(jobs)} round-1 jobs ({Counter(j['arm'] for j in jobs)})")
    failed = _pool(out, [j for j in jobs if not (out / j["output"]).exists()], log, "round 1")
    ce = [j for j in jobs if ARMS[j["arm"]][0] == "ce" and (out / j["output"]).exists()]
    current = {}
    retries = []
    for j in ce:
        reply = (out / j["output"]).read_text(encoding="utf-8")
        parsed = parse_p2g(reply, rt)
        current[id(j)] = (j, reply)
        if not parsed["ok"]:
            j2 = _followup(out, j, 2, CE_RETRY_PROMPT.format(error=parsed["error"],
                                                             text=reply.strip()))
            retries.append(j2)
            current[id(j)] = (j2, None)
    log(f"round 2: {len(retries)} retries")
    failed += _pool(out, [j for j in retries if not (out / j["output"]).exists()], log,
                    "round 2")
    repairs = []
    for j in ce:
        jf, reply = current[id(j)]
        if not (out / jf["output"]).exists():
            continue
        reply = reply if reply is not None else (out / jf["output"]).read_text(encoding="utf-8")
        parsed = parse_p2g(reply, rt)
        if not parsed["ok"]:
            continue
        v, _ = safe_check(parsed["pack"])
        if v is None or v.label != "IMPOSSIBLE" or v.unknown:
            continue
        expl = explain_refutation(v, _B(parsed["withdrawn"], parsed["blocked"]))
        repairs.append(_followup(out, j, 3, CE_REPAIR_PROMPT.format(
            explanation=expl, text=extract_ce(reply).strip())))
    log(f"round 3: {len(repairs)} repairs")
    failed += _pool(out, [j for j in repairs if not (out / j["output"]).exists()], log,
                    "round 3")
    _record_followups(out)
    log(f"run finished: {len(failed)} failed calls {failed}")


def _record_followups(out: Path) -> None:
    """frozen.json gains every round-2/3 job found on disk, with prompt sha256."""
    frozen = read_json(out / "frozen.json")
    by_key = {(j["arm"], j["case"], j["sample"]): j for j in frozen["jobs"] if j["round"] == 1}
    extra = []
    for p in sorted((out / "prompts").glob("*/*__r[23].json")):
        arm = p.parent.name
        case, s, r = p.stem.split("__")
        base = by_key[(arm, case, int(s[1:]))]
        extra.append({**base, "round": int(r[1:]),
                      "prompt": f"prompts/{arm}/{p.name}",
                      "output": f"outputs/{arm}/{p.stem}.txt",
                      "prompt_sha256": sha(p.read_bytes())})
    frozen["jobs"] = [j for j in frozen["jobs"] if j["round"] == 1] + extra
    write_json(out / "frozen.json", frozen)


# ------------------------------------------------------------------ score

def _usage_total(out: Path, outputs: list[str]) -> dict:
    tot = Counter()
    for o in outputs:
        p = usage_path(out, o)
        if p.exists():
            u = read_json(p)
            tot["calls"] += 1
            for b in u["usage"]:
                for k in ("input_tokens", "output_tokens", "cache_read_input_tokens"):
                    tot[k] += int(b.get(k, 0) or 0)
    return dict(tot)


def _verdict_fields(v, err) -> dict:
    if v is None:
        return {"verdict": "INVALID", "reason": "CHECK_ERROR", "detail": err, "frontier": []}
    return {"verdict": v.label, "reason": v.reason, "detail": v.detail,
            "frontier": [str(x) for x in v.frontier],
            "protocol": getattr(v, "protocol", ""),
            "protocol_reason": getattr(v, "protocol_reason", ""),
            "context_refuted": getattr(v, "context_refuted", None)}


def score_ce_sample(out: Path, jobs: dict, rt, retries: int = 1) -> dict:
    """Final pack of one (case, arm, sample).  Round handling follows
    benchmark_ce_runtime.score_all with guard=True: round 2 replaces round 1;
    an invalid round-3 reply keeps the pre-repair pack (repair_invalid); a round-3
    reply that repair_violations rejects keeps the refuted pack (repair_rejected).
    `retries` located-error retries occupy rounds 2..1+retries; the repair is
    round retries+2 (experiment R: retries=1, repair = round 3)."""
    rec: dict = {"rounds": 0, "repaired": False, "repair_rejected": None,
                 "repair_invalid": None}
    for r in sorted(jobs):
        job = jobs[r]
        p = out / job["output"]
        if not p.exists():
            continue
        parsed = parse_p2g(p.read_text(encoding="utf-8"), rt)
        rec["rounds"] = r
        if r == 1:
            rec["valid_first"] = parsed["ok"]
        if r == 2:
            rec["valid_after_one_retry"] = parsed["ok"]
        if r <= 1 + retries:
            rec["valid_after_retry"] = parsed["ok"]
        if r == retries + 2:
            if not parsed["ok"]:
                rec["repair_invalid"] = parsed["error"]
                continue
            if rec.get("parsed") is not None:
                bad = repair_violations(rec["parsed"], parsed["parsed"])
                if bad:
                    rec["repair_rejected"] = bad
                    continue
            rec["repaired"] = True
        if r == 1 and not parsed["ok"]:
            rec["first_error"] = parsed["error"]
        rec.pop("error", None)
        rec.update(parsed)
    return rec


def score(out: Path) -> None:
    frozen = read_json(out / "frozen.json")
    rt = load_runtime(str(out / "runtime.json"))
    truth = {c["case"]: TRUTH_MAP[read_json(SET2 / "truth" / f"{c['case']}.json")["verdict"]]
             for c in frozen["cases"]}
    kinds = {c["case"]: c["kind"] for c in frozen["cases"]}
    groups: dict = {}
    for j in frozen["jobs"]:
        if sha((out / j["prompt"]).read_bytes()) != j["prompt_sha256"]:
            raise ValueError(f"prompt changed: {j['prompt']}")
        groups.setdefault((j["arm"], j["case"], j["sample"]), {})[j["round"]] = j
    rows = []
    for (arm, case, s), jobs in sorted(groups.items()):
        outs = [j["output"] for j in jobs.values() if (out / j["output"]).exists()]
        row = {"case": case, "kind": kinds[case], "arm": arm, "model": ARMS[arm][1],
               "sample": s, "truth": truth[case], "usage": _usage_total(out, outs)}
        if not (out / jobs[1]["output"]).exists():
            row.update({"missing": True, "verdict": "MISSING"})
            rows.append(row)
            continue
        if ARMS[arm][0] == "direct":
            d = parse_direct((out / jobs[1]["output"]).read_text(encoding="utf-8"))
            row.update({"valid_first": d["ok"], "valid_final": d["ok"], "rounds": 1,
                        "verdict": d["verdict"], "missing_resources": d.get("missing"),
                        "error": d.get("error")})
            rows.append(row)
            continue
        rec = score_ce_sample(out, jobs, rt)
        row.update({"valid_first": rec.get("valid_first", False),
                    "valid_after_retry": rec.get("valid_after_retry", False),
                    "valid_final": rec.get("ok", False), "rounds": rec["rounds"],
                    "repaired": rec["repaired"], "repair_rejected": rec["repair_rejected"],
                    "repair_invalid": rec["repair_invalid"], "error": rec.get("error"),
                    "first_error": rec.get("first_error")})
        if rec.get("ok"):
            pack, parsed = rec["pack"], rec["parsed"]
            v, err = safe_check(pack)
            row.update(_verdict_fields(v, err))
            pl = planner_only(pack)
            tl = tool_lint(pack, rec["withdrawn"], rec["blocked"])
            row.update({
                "withdrawn": rec["withdrawn"], "blocked": rec["blocked"],
                "tools": sorted(parsed.pack["capabilities"]),
                "invoked": invoked_tools(parsed.pack),
                "goal_atoms": sorted(atoms(parsed.pack["goal"])),
                "P": {k: pl[k] for k in ("label", "reason", "frontier")},
                "T": tl})
            write_json(out / "packs" / arm / f"{case}__s{s}.json",
                       {"pack": pack, "pre_binding": parsed.pack,
                        "bindings": parsed.bindings, "live_goal": parsed.live_goal})
        else:
            row.update({"verdict": "INVALID", "P": {"label": "INVALID"},
                        "T": {"label": "INVALID"}})
        rows.append(row)
    write_json(out / "results.json", rows)
    metrics = compute_metrics(rows, truth, frozen)
    old = out / "metrics.json"
    if old.exists():   # keep a judge result already filled in
        prev = read_json(old)
        if "fidelity" in prev:
            metrics["fidelity"] = prev["fidelity"]
            metrics["criteria"]["R5"] = prev["criteria"]["R5"]
    write_json(old, metrics)
    print(json.dumps({k: metrics[k] for k in ("calls", "schema_gate", "criteria")}, indent=1))


# ------------------------------------------------------------------ metrics

def arm_accuracy(labels: dict, truth: dict) -> dict:
    """labels: key -> verdict; truth by case (key may be (case, sample))."""
    def t(k):
        return truth[k[0] if isinstance(k, tuple) else k]
    dec = {k: v for k, v in labels.items() if v in ("ACHIEVABLE", "IMPOSSIBLE")}
    right = sum(v == t(k) for k, v in dec.items())
    blocked = [k for k in labels if t(k) == "IMPOSSIBLE"]
    ach = [k for k in labels if t(k) == "ACHIEVABLE"]
    fr = sum(labels[k] == "IMPOSSIBLE" for k in ach)
    rec_ = sum(labels[k] == "IMPOSSIBLE" for k in blocked)
    return {"n": len(labels), "decided": len(dec), "correct": right,
            "accuracy_decided": rnd(right / len(dec)) if dec else None,
            "ci95": wilson(right, len(dec)),
            "blocked_total": len(blocked), "blocked_recall": rnd(rec_ / len(blocked))
            if blocked else None, "blocked_recall_ci95": wilson(rec_, len(blocked)),
            "blocked_recall_decided": rnd(rec_ / max(1, sum(labels[k] in (
                "ACHIEVABLE", "IMPOSSIBLE") for k in blocked))),
            "achievable_total": len(ach), "false_refutations": fr,
            "false_refutation_rate": rnd(fr / len(ach)) if ach else None,
            "counts": dict(Counter(labels.values()))}


def fleiss_kappa(table: list[list[int]]) -> float | None:
    """table[i][j] = raters assigning item i to category j (same raters per item)."""
    if not table:
        return None
    n = sum(table[0])
    N = len(table)
    if n < 2:
        return None
    pj = [sum(r[j] for r in table) / (N * n) for j in range(len(table[0]))]
    Pi = [(sum(x * x for x in r) - n) / (n * (n - 1)) for r in table]
    Pbar, Pe = sum(Pi) / N, sum(p * p for p in pj)
    return None if Pe == 1 else rnd((Pbar - Pe) / (1 - Pe))


def cohen_kappa(a: list, b: list) -> float | None:
    if not a:
        return None
    cats = sorted(set(a) | set(b))
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return None if pe == 1 else rnd((po - pe) / (1 - pe))


def mcnemar_pair(x: dict, y: dict, truth: dict) -> dict:
    """Paired correctness on cases both arms decided."""
    both = [c for c in x if c in y and x[c] in ("ACHIEVABLE", "IMPOSSIBLE")
            and y[c] in ("ACHIEVABLE", "IMPOSSIBLE")]
    b = sum(x[c] == truth[c] and y[c] != truth[c] for c in both)
    c_ = sum(x[c] != truth[c] and y[c] == truth[c] for c in both)
    return {"paired_cases": len(both), "first_right_second_wrong": b,
            "first_wrong_second_right": c_, "p": mcnemar_exact(b, c_),
            "first_acc": rnd(sum(x[c] == truth[c] for c in both) / len(both)) if both else None,
            "second_acc": rnd(sum(y[c] == truth[c] for c in both) / len(both)) if both else None}


def _witness(r: dict) -> tuple:
    """The missing runtime tool(s) or resource(s) behind an IMPOSSIBLE sample;
    without a binder witness, the checker's reason and frontier."""
    w = sorted(set(r.get("withdrawn", {}).values())
               | {x for rs in r.get("blocked", {}).values() for x in rs})
    if w:
        return tuple(w)
    return (r.get("reason"),) + tuple(sorted(r.get("frontier", [])))


def compute_metrics(rows: list[dict], truth: dict, frozen: dict) -> dict:
    cases = sorted(truth)
    R = {(r["arm"], r["case"], r["sample"]): r for r in rows}
    m: dict = {"created_utc": datetime.now(timezone.utc).isoformat(),
               "implementation_sha256_at_score": impl_hashes(),
               "implementation_sha256_at_prepare": frozen["implementation_sha256"],
               "truth": dict(Counter(truth.values())),
               "missing_outputs": sum(r.get("missing", False) for r in rows)}
    tot = Counter()
    per_arm = {}
    for r in rows:
        for k, v in r["usage"].items():
            tot[k] += v
        a = per_arm.setdefault(r["arm"], Counter())
        for k, v in r["usage"].items():
            a[k] += v
    m["calls"] = {"total": dict(tot), "per_arm": {a: dict(c) for a, c in per_arm.items()}}

    # schema gate
    sg = {}
    for arm in CE_ARMS:
        rs = [r for r in rows if r["arm"] == arm and not r.get("missing")]
        n = len(rs)
        f = sum(r["valid_first"] for r in rs)
        a = sum(r["valid_after_retry"] for r in rs)
        sg[arm] = {"samples": n, "valid_first": f, "valid_first_rate": rnd(f / n) if n else None,
                   "valid_first_ci95": wilson(f, n), "valid_after_retry": a,
                   "valid_after_retry_rate": rnd(a / n) if n else None,
                   "valid_after_retry_ci95": wilson(a, n),
                   "retried": sum(r["rounds"] >= 2 and r.get("valid_first") is False
                                  for r in rs),
                   "repair_rounds": sum(r["rounds"] == 3 for r in rs),
                   "repaired": sum(bool(r.get("repaired")) for r in rs),
                   "repair_rejected": sum(bool(r.get("repair_rejected")) for r in rs),
                   "repair_invalid": sum(bool(r.get("repair_invalid")) for r in rs)}
    for arm in ("D", "D-x"):
        rs = [r for r in rows if r["arm"] == arm and not r.get("missing")]
        sg[arm] = {"replies": len(rs), "valid": sum(r["valid_first"] for r in rs)}
    m["schema_gate"] = sg

    # accuracy per arm
    def lab(arm, s, key=None):
        out = {}
        for c in cases:
            r = R.get((arm, c, s))
            if r is None or r.get("missing"):
                out[c] = "MISSING"
            elif key is None:
                out[c] = r["verdict"]
            else:
                out[c] = r.get(key, {}).get("label", "INVALID")
        return out

    labels = {"skillc": lab("P2g", 0), "P": lab("P2g", 0, "P"), "T": lab("P2g", 0, "T"),
              "D": lab("D", 0), "D-x": lab("D-x", 0),
              "skillc-x": lab("P2g-x", 0), "P-x": lab("P2g-x", 0, "P"),
              "T-x": lab("P2g-x", 0, "T")}
    m["accuracy_sample0"] = {k: arm_accuracy(v, truth) for k, v in labels.items()}
    nS = ARMS["P2g"][2]
    pooled, persample = {}, {}
    for name, key in (("skillc", None), ("P", "P"), ("T", "T")):
        allv = {}
        accs = []
        for s in range(nS):
            ls = lab("P2g", s, key)
            accs.append(arm_accuracy(ls, truth)["accuracy_decided"])
            allv.update({(c, s): v for c, v in ls.items()})
        pooled[name] = arm_accuracy(allv, truth)
        persample[name] = accs
    m["accuracy_pooled_P2g_5samples"] = pooled
    m["accuracy_per_sample_P2g"] = persample
    m["accuracy_by_kind_sample0"] = {
        kind: {k: arm_accuracy({c: v for c, v in labels[k].items()
                                if R.get(("D", c, 0), {}).get("kind") == kind}, truth)
               for k in ("skillc", "P", "T", "D")}
        for kind in ("skill", "agent")}

    # cross-sample agreement (P2g, 5 samples)
    cats = list(LABELS)
    table, all_agree, tool_j, goal_j, wit_same, wit_docs, both_valid_agree = [], 0, [], [], 0, 0, []
    for c in cases:
        rs = [R.get(("P2g", c, s)) for s in range(nS)]
        if any(r is None or r.get("missing") for r in rs):
            continue
        vs = [r["verdict"] if r["verdict"] in cats else "INVALID" for r in rs]
        table.append([vs.count(k) for k in cats])
        all_agree += len(set(vs)) == 1
        if all(r["valid_final"] for r in rs):
            both_valid_agree.append(len(set(vs)) == 1)
        for a, b in itertools.combinations([r for r in rs if r["valid_final"]], 2):
            tool_j.append(jaccard(set(a["tools"]), set(b["tools"])))
            goal_j.append(jaccard(set(a["goal_atoms"]), set(b["goal_atoms"])))
        imp = [r for r in rs if r["verdict"] == "IMPOSSIBLE"]
        if len(imp) >= 2:
            wit_docs += 1
            wit_same += len({_witness(r) for r in imp}) == 1
    m["agreement_P2g"] = {
        "documents": len(table), "all_five_agree": all_agree,
        "all_five_agree_rate": rnd(all_agree / len(table)) if table else None,
        "all_five_agree_ci95": wilson(all_agree, len(table)),
        "fleiss_kappa": fleiss_kappa(table), "categories": cats,
        "documents_all_five_valid": len(both_valid_agree),
        "all_five_agree_rate_all_valid": rnd(sum(both_valid_agree) / len(both_valid_agree))
        if both_valid_agree else None,
        "mean_pairwise_jaccard_tools": rnd(sum(tool_j) / len(tool_j)) if tool_j else None,
        "mean_pairwise_jaccard_goal_atoms": rnd(sum(goal_j) / len(goal_j)) if goal_j else None,
        "valid_pairs": len(tool_j),
        "documents_with_2plus_impossible": wit_docs, "same_witness": wit_same,
        "same_witness_rate": rnd(wit_same / wit_docs) if wit_docs else None,
        "verdict_distribution": dict(Counter(r["verdict"] for r in rows if r["arm"] == "P2g"))}
    for name in ("P", "T"):
        tbl = []
        for c in cases:
            rs = [R.get(("P2g", c, s)) for s in range(nS)]
            if any(r is None or r.get("missing") for r in rs):
                continue
            vs = [r.get(name, {}).get("label", "INVALID") for r in rs]
            tbl.append([vs.count(k) for k in cats])
        m["agreement_P2g"][f"fleiss_kappa_{name}"] = fleiss_kappa(tbl)
        m["agreement_P2g"][f"all_five_agree_rate_{name}"] = rnd(
            sum(max(r) == nS for r in tbl) / len(tbl)) if tbl else None

    # cross-model
    a = [labels["skillc"][c] for c in cases]
    b = [labels["skillc-x"][c] for c in cases]
    bv = [(x, y) for x, y in zip(a, b) if x not in ("INVALID", "MISSING")
          and y not in ("INVALID", "MISSING")]
    m["cross_model"] = {
        "P2g_s0_vs_P2g_x": {"n": len(a), "agree": sum(x == y for x, y in zip(a, b)),
                            "cohen_kappa": cohen_kappa(a, b),
                            "n_both_valid": len(bv),
                            "cohen_kappa_both_valid": cohen_kappa([x for x, _ in bv],
                                                                  [y for _, y in bv])},
        "D_vs_D_x": {"cohen_kappa": cohen_kappa([labels["D"][c] for c in cases],
                                                [labels["D-x"][c] for c in cases])}}

    # McNemar pairs of the PLAN
    m["mcnemar"] = {
        "skillc_vs_D": mcnemar_pair(labels["skillc"], labels["D"], truth),
        "skillc_vs_P": mcnemar_pair(labels["skillc"], labels["P"], truth),
        "P2g_vs_P2g_x": mcnemar_pair(labels["skillc"], labels["skillc-x"], truth),
        "D_gpt_vs_D_deepseek": mcnemar_pair(labels["D"], labels["D-x"], truth),
        "skillc_vs_T": mcnemar_pair(labels["skillc"], labels["T"], truth)}

    # criteria
    acc = m["accuracy_sample0"]
    r1 = sg["P2g"]["valid_after_retry_rate"]
    ag = m["agreement_P2g"]
    fr = acc["skillc"]["false_refutation_rate"]
    sk, dd = acc["skillc"]["accuracy_decided"], acc["D"]["accuracy_decided"]
    m["criteria"] = {
        "R1": {"rule": "schema-gate pass after retry >= 0.95 (P2g, all samples)",
               "value": r1, "met": r1 is not None and r1 >= 0.95},
        "R2": {"rule": "all-five-agree rate >= 0.80 and Fleiss' kappa >= 0.6",
               "value": {"all_five_agree_rate": ag["all_five_agree_rate"],
                         "fleiss_kappa": ag["fleiss_kappa"]},
               "met": (ag["all_five_agree_rate"] or 0) >= 0.80
               and (ag["fleiss_kappa"] or 0) >= 0.6},
        "R3": {"rule": "false refutations (truth ACHIEVABLE, skillc IMPOSSIBLE) <= 10% of "
                       "ACHIEVABLE documents (P2g sample 0)",
               "value": fr, "count": acc["skillc"]["false_refutations"],
               "met": fr is not None and fr <= 0.10},
        "R4": {"rule": "skillc decided accuracy within 5 points of D (gpt-5.4), or better",
               "value": {"skillc": sk, "D": dd,
                         "difference_points": rnd(100 * (sk - dd), 2)
                         if sk is not None and dd is not None else None},
               "met": sk is not None and dd is not None and sk >= dd - 0.05},
        "R5": {"rule": "fidelity F1 and F4 >= 0.85 yes", "value": None,
               "met": "pending judge"}}
    return m


# ------------------------------------------------------------------ judge

JUDGE_README = """# Fidelity judge (experiment R, PLAN.md F1..F5)

Each file in `items/` is one document: `source_text` is the original SKILL.md or
agent.md, `ce` is the final Controlled English pack the compactor (gpt-5.4, P2g
sample 0) wrote for it, and `runtime` is the runtime it was bound to.  The item
holds no verdict, no truth label and no score: judge the pack against the source
text only.

For each of the five items in `rubric`, answer `yes`, `no` or `unclear` and give a
one-line reason that cites the document (a quoted phrase or a section) and the
pack (a Tool name, a protocol step or the Goal).

Write `scores/<case>.json`:

```json
{"case": "c001",
 "F1": "yes", "F1_reason": "...",
 "F2": "no",  "F2_reason": "...",
 "F3": "yes", "F3_reason": "...",
 "F4": "yes", "F4_reason": "...",
 "F5": "unclear", "F5_reason": "..."}
```

A second judge scores 20% of the items (the cases in `second_judge.json`) the same
way into `scores2/<case>.json`, without reading `scores/`.  Then run
`python scripts/reliability.py judge-score OUT`.

Notes for judging:
- F1: a Tool is invented when no sentence of the document asks for that operation.
- F2: a step is mandatory when the document's core deliverable cannot be produced
  without it; optional or follow-up work may be omitted or skippable.
- F3: the Goal must name the deliverable of one representative request.
- F4: an ordering is invented when the protocol puts two steps in an order the
  document neither states nor implies (e.g. by data dependence).
- F5: `via` must name a runtime tool from `runtime.tools` that can really perform
  the Tool; a `via` naming something outside that list is plausible only if the
  runtime indeed cannot perform the operation.
"""


def judge_prep(out: Path) -> None:
    frozen = read_json(out / "frozen.json")
    rt = read_json(out / "runtime.json")
    jd = out / "judge"
    n = 0
    for c in frozen["cases"]:
        p = out / "packs" / "P2g" / f"{c['case']}__s0.json"
        if not p.exists():
            continue
        d = read_json(p)
        ce = render_ce(d["pre_binding"], d["bindings"], d.get("live_goal"))
        write_json(jd / "items" / f"{c['case']}.json", {
            "case": c["case"], "kind": c["kind"],
            "source_text": (SET2 / "cases" / f"{c['case']}.md").read_text(encoding="utf-8"),
            "ce": ce,
            "runtime": {"name": rt["name"], "description": rt["description"],
                        "tools": rt["tools"]},
            "rubric": RUBRIC})
        n += 1
    ids = sorted(p.stem for p in (jd / "items").glob("*.json"))
    second = sorted(ids, key=lambda i: sha("judge2:" + i))[:max(1, round(0.2 * len(ids)))]
    write_json(jd / "second_judge.json", sorted(second))
    (jd / "README.md").write_text(JUDGE_README, encoding="utf-8")
    (jd / "scores").mkdir(exist_ok=True)
    (jd / "scores2").mkdir(exist_ok=True)
    print(f"{n} judge items, {len(second)} for the second judge, in {jd}")


def judge_score(out: Path) -> None:
    jd = out / "judge"
    first = {p.stem: read_json(p) for p in sorted((jd / "scores").glob("*.json"))}
    second = {p.stem: read_json(p) for p in sorted((jd / "scores2").glob("*.json"))}
    item_ids = {p.stem for p in (jd / "items").glob("*.json")}
    items = len(item_ids)
    first = {c: v for c, v in first.items() if c in item_ids}
    fid: dict = {"items": items, "scored": len(first), "per_item": {}}
    norm = {"yes": "yes", "no": "no", "unclear": "unclear"}
    for f in RUBRIC:
        vals = [norm.get(str(s.get(f, "")).strip().lower(), "unclear") for s in first.values()]
        y = vals.count("yes")
        fid["per_item"][f] = {"yes": y, "no": vals.count("no"),
                              "unclear": vals.count("unclear"),
                              "yes_rate": rnd(y / len(vals)) if vals else None,
                              "ci95": wilson(y, len(vals))}
    both = sorted(set(first) & set(second))
    if both:
        a, b = [], []
        per = {}
        for f in RUBRIC:
            x = [norm.get(str(first[c].get(f, "")).lower(), "unclear") for c in both]
            y = [norm.get(str(second[c].get(f, "")).lower(), "unclear") for c in both]
            per[f] = {"agree": sum(i == j for i, j in zip(x, y)), "n": len(both),
                      "cohen_kappa": cohen_kappa(x, y)}
            a += x
            b += y
        fid["second_judge"] = {"cases": len(both), "per_item": per,
                               "agreement": rnd(sum(i == j for i, j in zip(a, b)) / len(a)),
                               "cohen_kappa_pooled": cohen_kappa(a, b)}
    m = read_json(out / "metrics.json")
    f1, f4 = fid["per_item"]["F1"]["yes_rate"], fid["per_item"]["F4"]["yes_rate"]
    m["fidelity"] = fid
    complete = items > 0 and item_ids <= set(first)
    m["criteria"]["R5"].update({
        "value": {"F1": f1, "F4": f4, "scored": len(first), "items": items},
        "met": (f1 is not None and f4 is not None and f1 >= 0.85 and f4 >= 0.85)
        if complete else "pending judge"})
    write_json(out / "metrics.json", m)
    print(json.dumps(fid, indent=1))


# ------------------------------------------------------------------ set3 (Addendum C)
# `prepare OUT --set set3` freezes the set3 validation of PLAN.md Addenda B and C; the
# other commands read frozen.json["experiment"] and dispatch here.  Nothing above this
# line changes behaviour for an experiment-R directory.

SET3 = ROOT / "benchmark" / "claude_env" / "set3"
# arm -> (kind, model, samples, CE prompt version, located-error retries)
ARMS3 = {"P2g": ("ce", GPT, 3, "p2g", 1), "P2g+": ("ce", GPT, 3, "p2g+", 2),
         "D": ("direct", GPT, 1, None, 0), "Rdet": ("rdet", None, 1, None, 0)}
CE_ARMS3 = [a for a, v in ARMS3.items() if v[0] == "ce"]
UNION = "P2g+|Rdet"          # P2g+ ∪ Rdet, derived per sample by `score`
NS3 = 3
WORKERS3 = 4                 # at most 4 concurrent model calls
JUDGE_N3, JUDGE2_N3 = 30, 6
JUDGE_VARIANTS = {"P2g": "p2g", "P2g+": "p2gplus"}
IMPL_FILES3 = IMPL_FILES + ["src/skillc/frontend/llm.py", "src/skillc/env/manifest.py",
                            "src/skillc/env/nl.py"]


def text_sha(path: Path) -> str:
    """sha256 of a set3 text with CRLF read as LF: the working-tree files have CRLF
    line ends, cases.json pins the LF bytes, and read_text() gives the models LF."""
    return sha(path.read_bytes().replace(b"\r\n", b"\n"))


def impl_hashes3() -> dict:
    return {f: sha((ROOT / f).read_bytes()) for f in IMPL_FILES3}


def prepare3(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=False)
    rt = load_runtime(str(MANIFEST))
    meta = read_json(SET3 / "cases.json")
    cases, jobs = [], []
    for c in meta["cases"]:
        src = SET3 / "cases" / f"{c['case']}.md"
        text, h = src.read_text(encoding="utf-8"), text_sha(src)
        if sha(text) != h:
            raise ValueError(f"{c['case']}: read_text() does not give the pinned bytes")
        if h != c["sha256"]:
            raise ValueError(f"{c['case']}: text sha256 {h} != cases.json {c['sha256']}")
        cases.append({"case": c["case"], "id": c["id"], "kind": c["kind"],
                      "repo_url": c["repo_url"], "commit": c["commit"],
                      "path_in_repo": c["path_in_repo"], "text_sha256": h})
        for arm, (kind, model, n, version, _r) in ARMS3.items():
            if kind == "rdet":
                jobs.append({"case": c["case"], "arm": arm, "model": None, "sample": 0,
                             "round": 1, "kind": "rdet",
                             "input": f"benchmark/claude_env/set3/cases/{c['case']}.md",
                             "input_sha256": h,
                             "output": f"outputs/{arm}/{c['case']}__s0.json"})
                continue
            system, user = (ce_runtime_messages(text, rt, version=version) if kind == "ce"
                            else direct_messages(text, rt))
            for s in range(n):
                prel, orel = out_rel(arm, c["case"], s)
                write_json(out / prel, {"system": system, "user": user})
                jobs.append({"case": c["case"], "arm": arm, "model": model, "sample": s,
                             "round": 1, "kind": "first", "prompt": prel, "output": orel,
                             "prompt_sha256": sha((out / prel).read_bytes())})
    (out / "runtime.json").write_bytes(MANIFEST.read_bytes())
    write_json(out / "frozen.json", {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "set3",
        "plan": "runs/20261015_review_response/PLAN.md Addendum C (arms, C1..C3), Addendum B "
                "(F-a..F-f, B1..B3), amendments F-f and F-h",
        "set": "benchmark/claude_env/set3", "seed": meta["seed"],
        "runtime": RUNTIME, "runtime_sha256": sha(MANIFEST.read_bytes()),
        "arms": {a: {"kind": k, "model": m, "samples": n, "prompt_version": v,
                     "located_error_retries": r,
                     "repair": "one guarded counterexample repair (round retries+2)"
                     if k == "ce" else None}
                 for a, (k, m, n, v, r) in ARMS3.items()},
        "union": {"name": UNION, "rule": "per sample: IMPOSSIBLE if P2g+ or Rdet refutes; "
                  "ACHIEVABLE only if both say ACHIEVABLE; otherwise UNKNOWN"},
        "bind": {"prune": False, "library": None, "software": False},
        "rdet": "skillc.env.manifest.refute_text(text, runtime.json)",
        "workers": WORKERS3,
        "cases": cases, "jobs": jobs, "implementation_sha256": impl_hashes3()})
    print(f"prepared {len(cases)} cases, {sum(j['kind'] == 'first' for j in jobs)} round-1 "
          f"model jobs, {sum(j['kind'] == 'rdet' for j in jobs)} Rdet jobs in {out}")


def _execute3(out: Path, job: dict, log: Log) -> str:
    """_execute for set3 arms (JSON mode for the direct verdict only)."""
    o = out / job["output"]
    if o.exists():
        return o.read_text(encoding="utf-8")
    prompt = read_json(out / job["prompt"])
    tag = f"{job['arm']}/{job['case']}/s{job['sample']}/r{job['round']}"
    text, usage, jm, secs = call_model(prompt["system"], prompt["user"], job["model"],
                                       ARMS3[job["arm"]][0] == "direct", log, tag)
    write_json(usage_path(out, job["output"]), {
        "model": job["model"], "json_mode": jm, "elapsed_s": secs, "usage": usage,
        "utc": datetime.now(timezone.utc).isoformat()})
    o.parent.mkdir(parents=True, exist_ok=True)
    o.write_text(text, encoding="utf-8")
    tok = sum(u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) for u in usage)
    log(f"{tag}: done {secs}s in={tok} out={sum(u.get('output_tokens', 0) for u in usage)}")
    return text


def _rdet_eval(text: str, runtime_path: Path) -> dict:
    from skillc.env.manifest import refute_text
    return refute_text(text, str(runtime_path)).to_dict()


def _chain_next(out: Path, base: dict, rt) -> dict | None:
    """The next round of one CE chain from the replies on disk, or None when the
    chain is finished (or its round 1 is missing).  Round 1; at most `retries`
    located-error retries (CE_RETRY_PROMPT on the latest reply and its error, rounds
    2..1+retries); one counterexample repair (CE_REPAIR_PROMPT + explain_refutation
    on the current valid document, round retries+2) when the checker says
    IMPOSSIBLE.  P2g: experiment R's `run` (retries=1, no repair on an unknown
    verdict); P2g+: frontend.llm.compact_ce_rounds (retries=2, repair on label
    IMPOSSIBLE).  Reads disk, parses, binds, checks: main thread only."""
    arm = base["arm"]
    retries = ARMS3[arm][4]
    o = out / base["output"]
    if not o.exists():
        return None
    reply = o.read_text(encoding="utf-8")
    parsed = parse_p2g(reply, rt)
    k = 0
    while not parsed["ok"] and k < retries:
        k += 1
        j = _followup(out, base, 1 + k, CE_RETRY_PROMPT.format(error=parsed["error"],
                                                               text=reply.strip()))
        j["kind"] = "retry"
        if not (out / j["output"]).exists():
            return j
        reply = (out / j["output"]).read_text(encoding="utf-8")
        parsed = parse_p2g(reply, rt)
    if not parsed["ok"]:
        return None
    v, _ = safe_check(parsed["pack"])
    if v is None or v.label != "IMPOSSIBLE" or (arm == "P2g" and v.unknown):
        return None
    expl = explain_refutation(v, _B(parsed["withdrawn"], parsed["blocked"]))
    j = _followup(out, base, retries + 2, CE_REPAIR_PROMPT.format(
        explanation=expl, text=extract_ce(reply).strip()))
    j["kind"] = "repair"
    return None if (out / j["output"]).exists() else j


def run3(out: Path, arms: list[str] | None, limit: int | None,
         only_cases: list[str] | None = None, samples: list[int] | None = None) -> None:
    frozen = read_json(out / "frozen.json")
    rt = load_runtime(str(out / "runtime.json"))
    log = Log(out / "run.log")
    jobs = [j for j in frozen["jobs"] if j["round"] == 1 and (not arms or j["arm"] in arms)]
    for j in jobs:
        if j["kind"] == "rdet":
            if text_sha(ROOT / j["input"]) != j["input_sha256"]:
                raise ValueError(f"text changed: {j['input']}")
        elif sha((out / j["prompt"]).read_bytes()) != j["prompt_sha256"]:
            raise ValueError(f"prompt changed: {j['prompt']}")
    if only_cases:
        jobs = [j for j in jobs if j["case"] in only_cases]
    if samples is not None:
        jobs = [j for j in jobs if j["sample"] in samples]
    if limit:
        jobs = jobs[:limit]
    log(f"run (set3): {len(jobs)} round-1 jobs ({dict(Counter(j['arm'] for j in jobs))})")
    for j in jobs:          # Rdet: no model, main thread
        if j["kind"] == "rdet" and not (out / j["output"]).exists():
            write_json(out / j["output"], _rdet_eval((ROOT / j["input"]).read_text(
                encoding="utf-8"), out / "runtime.json"))
    calls = [j for j in jobs if j["kind"] == "first"]
    failed = _pool(out, [j for j in calls if not (out / j["output"]).exists()], log,
                   "round 1", WORKERS3, _execute3)
    ce = [j for j in calls if ARMS3[j["arm"]][0] == "ce"]
    for step in range(2, 6):
        nxt = [n for n in (_chain_next(out, j, rt) for j in ce) if n is not None]
        log(f"follow-up pass {step}: {len(nxt)} jobs ({dict(Counter(n['kind'] for n in nxt))})")
        if not nxt:
            break
        failed += _pool(out, nxt, log, f"follow-up pass {step}", WORKERS3, _execute3)
    _record_followups3(out)
    log(f"run finished: {len(failed)} failed calls {failed}")


def _record_followups3(out: Path) -> None:
    frozen = read_json(out / "frozen.json")
    by_key = {(j["arm"], j["case"], j["sample"]): j for j in frozen["jobs"]
              if j["round"] == 1 and j["kind"] != "rdet"}
    extra = []
    for arm in CE_ARMS3:
        for p in sorted((out / "prompts" / arm).glob("*__r[2-9].json")):
            case, s, r = p.stem.split("__")
            rr = int(r[1:])
            base = by_key[(arm, case, int(s[1:]))]
            extra.append({**base, "round": rr,
                          "kind": "repair" if rr == ARMS3[arm][4] + 2 else "retry",
                          "prompt": f"prompts/{arm}/{p.name}",
                          "output": f"outputs/{arm}/{p.stem}.txt",
                          "prompt_sha256": sha(p.read_bytes())})
    frozen["jobs"] = [j for j in frozen["jobs"] if j["round"] == 1] + extra
    write_json(out / "frozen.json", frozen)


# --- score

KIND_MAP = {"account": "credential", "credential": "credential", "program": "program",
            "installer": "program", "egress": "egress", "host": "egress", "tool": "tool",
            "mcp": "connector", "connector": "connector", "hardware": "hardware",
            "platform": "platform", "other": "other"}
NAME_STOP = frozenset("""a an the of for to and or with on in by api key keys token account
    accounts login access server mcp cli app sdk service services project endpoint
    endpoints official real""".split())


def _name_tokens(name: str) -> set:
    import re
    toks = set(re.findall(r"[a-z0-9]+", name.lower().replace("_", " ")))
    return {t for t in toks if t not in NAME_STOP and len(t) > 1}


def witness_agreement(rdet_blocking: list, truth_blocking: list) -> list:
    """For each Rdet blocking requirement `kind:name`: the truth `blocking` entries
    of the same kind (after KIND_MAP) whose names share a token (lowercase
    alphanumerics, minus NAME_STOP), and those of any kind sharing a token."""
    res = []
    for req in rdet_blocking:
        k, _, n = req.partition(":")
        kk, nt = KIND_MAP.get(k, k), _name_tokens(n)
        same, anyk = [], []
        for tb in truth_blocking:
            tk, _, tn = tb.partition(":")
            if nt & _name_tokens(tn):
                anyk.append(tb)
                if KIND_MAP.get(tk, tk) == kk:
                    same.append(tb)
        res.append({"rdet": req, "same_kind_and_name": same, "name_only": anyk})
    return res


def score3(out: Path) -> None:
    frozen = read_json(out / "frozen.json")
    rt = load_runtime(str(out / "runtime.json"))
    tdocs = {c["case"]: read_json(SET3 / "truth" / f"{c['case']}.json")
             for c in frozen["cases"]}
    truth = {c: TRUTH_MAP[d["verdict"]] for c, d in tdocs.items()}
    kinds = {c["case"]: c["kind"] for c in frozen["cases"]}
    groups: dict = {}
    for j in frozen["jobs"]:
        if j["kind"] == "rdet":
            if text_sha(ROOT / j["input"]) != j["input_sha256"]:
                raise ValueError(f"text changed: {j['input']}")
        elif sha((out / j["prompt"]).read_bytes()) != j["prompt_sha256"]:
            raise ValueError(f"prompt changed: {j['prompt']}")
        groups.setdefault((j["arm"], j["case"], j["sample"]), {})[j["round"]] = j
    rows = []
    for (arm, case, s), jobs in sorted(groups.items()):
        kind = ARMS3[arm][0]
        row = {"case": case, "kind": kinds[case], "arm": arm, "model": ARMS3[arm][1],
               "sample": s, "truth": truth[case]}
        if kind == "rdet":
            p = out / jobs[1]["output"]
            row["usage"] = {}
            if not p.exists():
                row.update({"missing": True, "verdict": "MISSING"})
            else:
                e = read_json(p)
                row.update({"valid_first": True, "valid_final": True, "rounds": 0,
                            "verdict": e["verdict"], "reason": e["reason"],
                            "blocking": e["blocking"], "witness": e["witness"],
                            "unknown_requirements": e["unknown"]})
            rows.append(row)
            continue
        outs = [j["output"] for j in jobs.values() if (out / j["output"]).exists()]
        row["usage"] = _usage_total(out, outs)
        if not (out / jobs[1]["output"]).exists():
            row.update({"missing": True, "verdict": "MISSING"})
            rows.append(row)
            continue
        if kind == "direct":
            d = parse_direct((out / jobs[1]["output"]).read_text(encoding="utf-8"))
            row.update({"valid_first": d["ok"], "valid_final": d["ok"], "rounds": 1,
                        "verdict": d["verdict"], "missing_resources": d.get("missing"),
                        "error": d.get("error")})
            rows.append(row)
            continue
        rec = score_ce_sample(out, jobs, rt, retries=ARMS3[arm][4])
        row.update({"valid_first": rec.get("valid_first", False),
                    "valid_after_one_retry": rec.get("valid_after_one_retry",
                                                     rec.get("valid_first", False)),
                    "valid_after_retry": rec.get("valid_after_retry", False),
                    "valid_final": rec.get("ok", False), "rounds": rec["rounds"],
                    "repaired": rec["repaired"], "repair_rejected": rec["repair_rejected"],
                    "repair_invalid": rec["repair_invalid"], "error": rec.get("error"),
                    "first_error": rec.get("first_error")})
        if rec.get("ok"):
            pack, parsed = rec["pack"], rec["parsed"]
            v, err = safe_check(pack)
            row.update(_verdict_fields(v, err))
            pl = planner_only(pack)
            tl = tool_lint(pack, rec["withdrawn"], rec["blocked"])
            row.update({
                "withdrawn": rec["withdrawn"], "blocked": rec["blocked"],
                "tools": sorted(parsed.pack["capabilities"]),
                "invoked": invoked_tools(parsed.pack),
                "goal_atoms": sorted(atoms(parsed.pack["goal"])),
                "P": {k: pl[k] for k in ("label", "reason", "frontier")},
                "T": tl})
            write_json(out / "packs" / arm / f"{case}__s{s}.json",
                       {"pack": pack, "pre_binding": parsed.pack,
                        "bindings": parsed.bindings, "live_goal": parsed.live_goal})
        else:
            row.update({"verdict": "INVALID", "P": {"label": "INVALID"},
                        "T": {"label": "INVALID"}})
        rows.append(row)
    # the union arm, per sample
    R = {(r["arm"], r["case"], r["sample"]): r for r in rows}
    for c in sorted(truth):
        rd = R.get(("Rdet", c, 0))
        for s in range(NS3):
            p = R.get(("P2g+", c, s))
            if p is None or rd is None or p.get("missing") or rd.get("missing"):
                rows.append({"case": c, "kind": kinds[c], "arm": UNION, "sample": s,
                             "truth": truth[c], "usage": {}, "missing": True,
                             "verdict": "MISSING"})
                continue
            pv, rv = p["verdict"], rd["verdict"]
            if "IMPOSSIBLE" in (pv, rv):
                v = "IMPOSSIBLE"
            elif pv == "ACHIEVABLE" and rv == "ACHIEVABLE":
                v = "ACHIEVABLE"
            else:
                v = "UNKNOWN"
            refuted_by = [a for a, x in (("P2g+", pv), ("Rdet", rv)) if x == "IMPOSSIBLE"]
            rows.append({"case": c, "kind": kinds[c], "arm": UNION, "sample": s,
                         "truth": truth[c], "usage": {}, "verdict": v,
                         "valid_final": True, "P2g+": pv, "Rdet": rv,
                         "refuted_by": refuted_by,
                         "witness": {"P2g+": list(_witness(p)) if pv == "IMPOSSIBLE"
                                     else None,
                                     "Rdet": rd["blocking"] if rv == "IMPOSSIBLE" else None}})
    write_json(out / "results.json", rows)
    metrics = compute_metrics3(rows, truth, tdocs, frozen, out)
    old = out / "metrics.json"
    if old.exists():
        prev = read_json(old)
        if "fidelity" in prev:
            metrics["fidelity"] = prev["fidelity"]
            metrics["criteria"]["B3"] = prev["criteria"]["B3"]
    write_json(old, metrics)
    print(json.dumps({k: metrics[k] for k in ("calls", "criteria")}, indent=1,
                     ensure_ascii=False))


def _union_witness(r: dict) -> tuple:
    w = r.get("witness") or {}
    return (tuple(w.get("P2g+") or ()), tuple(sorted(w.get("Rdet") or ())))


def _agreement3(R: dict, arm: str, cases: list, wit) -> dict:
    cats = list(LABELS)
    table, all_agree, tool_j, goal_j, wit_same, wit_docs, valid_agree = [], 0, [], [], 0, 0, []
    for c in cases:
        rs = [R.get((arm, c, s)) for s in range(NS3)]
        if any(r is None or r.get("missing") for r in rs):
            continue
        vs = [r["verdict"] if r["verdict"] in cats else "INVALID" for r in rs]
        table.append([vs.count(k) for k in cats])
        all_agree += len(set(vs)) == 1
        if all(r.get("valid_final") for r in rs):
            valid_agree.append(len(set(vs)) == 1)
        if arm in CE_ARMS3:
            for a, b in itertools.combinations([r for r in rs if r["valid_final"]], 2):
                tool_j.append(jaccard(set(a["tools"]), set(b["tools"])))
                goal_j.append(jaccard(set(a["goal_atoms"]), set(b["goal_atoms"])))
        imp = [r for r in rs if r["verdict"] == "IMPOSSIBLE"]
        if len(imp) >= 2:
            wit_docs += 1
            wit_same += len({wit(r) for r in imp}) == 1
    return {"documents": len(table), "samples": NS3, "all_agree": all_agree,
            "all_agree_rate": rnd(all_agree / len(table)) if table else None,
            "all_agree_ci95": wilson(all_agree, len(table)),
            "fleiss_kappa": fleiss_kappa(table), "categories": cats,
            "documents_all_valid": len(valid_agree),
            "all_agree_rate_all_valid": rnd(sum(valid_agree) / len(valid_agree))
            if valid_agree else None,
            "mean_pairwise_jaccard_tools": rnd(sum(tool_j) / len(tool_j)) if tool_j else None,
            "mean_pairwise_jaccard_goal_atoms": rnd(sum(goal_j) / len(goal_j))
            if goal_j else None,
            "valid_pairs": len(tool_j),
            "documents_with_2plus_impossible": wit_docs, "same_witness": wit_same,
            "same_witness_rate": rnd(wit_same / wit_docs) if wit_docs else None,
            "verdict_distribution": dict(Counter(r["verdict"] for k, r in R.items()
                                                 if k[0] == arm))}


def mcnemar_keys(x: dict, y: dict, tf) -> dict:
    """mcnemar_pair over arbitrary keys; tf(key) is the truth label."""
    both = [k for k in x if k in y and x[k] in ("ACHIEVABLE", "IMPOSSIBLE")
            and y[k] in ("ACHIEVABLE", "IMPOSSIBLE")]
    b = sum(x[k] == tf(k) and y[k] != tf(k) for k in both)
    c_ = sum(x[k] != tf(k) and y[k] == tf(k) for k in both)
    return {"paired": len(both), "first_right_second_wrong": b,
            "first_wrong_second_right": c_, "p": mcnemar_exact(b, c_),
            "first_acc": rnd(sum(x[k] == tf(k) for k in both) / len(both)) if both else None,
            "second_acc": rnd(sum(y[k] == tf(k) for k in both) / len(both)) if both else None}


def _first_error_class(err: str | None) -> str:
    import re
    if not err:
        return "none"
    e = err.split(":", 1)[-1].strip()
    e = re.sub(r"`[^`]*`", "`X`", e)
    e = re.sub(r"line \d+(, column \d+)?", "line N", e)
    e = re.sub(r"\d+", "N", e)
    return e[:90]


def compute_metrics3(rows: list[dict], truth: dict, tdocs: dict, frozen: dict,
                     out: Path) -> dict:
    cases = sorted(truth)
    R = {(r["arm"], r["case"], r["sample"]): r for r in rows}
    m: dict = {"created_utc": datetime.now(timezone.utc).isoformat(),
               "experiment": "set3",
               "implementation_sha256_at_score": impl_hashes3(),
               "implementation_sha256_at_prepare": frozen["implementation_sha256"],
               "truth": dict(Counter(truth.values())),
               "missing_outputs": sum(bool(r.get("missing")) for r in rows
                                      if r["arm"] != UNION)}
    tot, per_arm, rounds = Counter(), {}, {}
    for r in rows:
        if r["arm"] == UNION:
            continue
        a = per_arm.setdefault(r["arm"], Counter())
        for k, v in r["usage"].items():
            tot[k] += v
            a[k] += v
    for j in frozen["jobs"]:
        if j["kind"] != "rdet" and (out / j["output"]).exists():
            rounds.setdefault(j["arm"], Counter())[j["kind"]] += 1
    m["calls"] = {"total": dict(tot), "per_arm": {a: dict(c) for a, c in per_arm.items()},
                  "per_arm_by_round_kind": {a: dict(c) for a, c in rounds.items()}}

    sg = {}
    for arm in CE_ARMS3:
        rs = [r for r in rows if r["arm"] == arm and not r.get("missing")]
        n = len(rs)
        f = sum(r["valid_first"] for r in rs)
        a1 = sum(r["valid_after_one_retry"] for r in rs)
        a = sum(r["valid_after_retry"] for r in rs)
        sg[arm] = {"samples": n, "located_error_retries": ARMS3[arm][4],
                   "valid_first": f, "valid_first_rate": rnd(f / n) if n else None,
                   "valid_first_ci95": wilson(f, n),
                   "valid_after_one_retry": a1,
                   "valid_after_one_retry_rate": rnd(a1 / n) if n else None,
                   "valid_after_retries": a,
                   "valid_after_retries_rate": rnd(a / n) if n else None,
                   "valid_after_retries_ci95": wilson(a, n),
                   "retried": sum(r.get("valid_first") is False and r["rounds"] >= 2
                                  for r in rs),
                   "repair_rounds": sum(r["rounds"] == ARMS3[arm][4] + 2 for r in rs),
                   "repaired": sum(bool(r.get("repaired")) for r in rs),
                   "repair_rejected": sum(bool(r.get("repair_rejected")) for r in rs),
                   "repair_invalid": sum(bool(r.get("repair_invalid")) for r in rs),
                   "first_error_classes": dict(Counter(
                       _first_error_class(r.get("first_error")) for r in rs
                       if not r["valid_first"]).most_common(8))}
    rs = [r for r in rows if r["arm"] == "D" and not r.get("missing")]
    sg["D"] = {"replies": len(rs), "valid": sum(r["valid_first"] for r in rs)}
    m["schema_gate"] = sg

    def lab(arm, s, key=None):
        res = {}
        for c in cases:
            r = R.get((arm, c, s))
            if r is None or r.get("missing"):
                res[c] = "MISSING"
            elif key is None:
                res[c] = r["verdict"]
            else:
                res[c] = r.get(key, {}).get("label", "INVALID")
        return res

    def pooled(arm, key=None):
        return {(c, s): v for s in range(NS3) for c, v in lab(arm, s, key).items()}

    s0 = {"P2g": lab("P2g", 0), "P2g+": lab("P2g+", 0), "Rdet": lab("Rdet", 0),
          UNION: lab(UNION, 0), "D": lab("D", 0),
          "T on P2g": lab("P2g", 0, "T"), "T on P2g+": lab("P2g+", 0, "T"),
          "P on P2g": lab("P2g", 0, "P"), "P on P2g+": lab("P2g+", 0, "P")}
    m["accuracy_sample0"] = {k: arm_accuracy(v, truth) for k, v in s0.items()}
    pl = {"P2g": pooled("P2g"), "P2g+": pooled("P2g+"), UNION: pooled(UNION),
          "T on P2g": pooled("P2g", "T"), "T on P2g+": pooled("P2g+", "T")}
    m["accuracy_pooled_3samples"] = {k: arm_accuracy(v, truth) for k, v in pl.items()}
    for key, field in (("accuracy_per_sample", "accuracy_decided"),
                       ("recall_per_sample", "blocked_recall"),
                       ("false_refutations_per_sample", "false_refutations")):
        m[key] = {a: [arm_accuracy(lab(a, s), truth)[field] for s in range(NS3)]
                  for a in ("P2g", "P2g+", UNION)}
    m["accuracy_by_kind_sample0"] = {
        kind: {k: arm_accuracy({c: v for c, v in s0[k].items()
                                if R.get(("D", c, 0), {}).get("kind") == kind}, truth)
               for k in ("P2g", "P2g+", "Rdet", UNION, "D")}
        for kind in ("skill", "agent")}

    m["agreement"] = {"P2g": _agreement3(R, "P2g", cases, _witness),
                      "P2g+": _agreement3(R, "P2g+", cases, _witness),
                      UNION: _agreement3(R, UNION, cases, _union_witness)}

    def tf(k):
        return truth[k[0] if isinstance(k, tuple) else k]
    d_pooled = {(c, s): v for c, v in s0["D"].items() for s in range(NS3)}
    m["mcnemar"] = {
        "P2g_vs_P2g+_pooled_same_sample": mcnemar_keys(pl["P2g"], pl["P2g+"], tf),
        "P2g_vs_P2g+_sample0": mcnemar_keys(s0["P2g"], s0["P2g+"], tf),
        "union_vs_D_sample0": mcnemar_keys(s0[UNION], s0["D"], tf),
        "union_vs_D_pooled_D_repeated": mcnemar_keys(pl[UNION], d_pooled, tf),
        "P2g+_vs_D_sample0": mcnemar_keys(s0["P2g+"], s0["D"], tf),
        "P2g+_vs_D_pooled_D_repeated": mcnemar_keys(pl["P2g+"], d_pooled, tf),
        "note": "pooled pairs are (case, sample); the three samples of one document are "
                "not independent, so the pooled p-values are optimistic"}

    def fr_mcnemar(x, y, keys):
        b = sum(x[k] == "IMPOSSIBLE" and y[k] != "IMPOSSIBLE" for k in keys)
        c_ = sum(x[k] != "IMPOSSIBLE" and y[k] == "IMPOSSIBLE" for k in keys)
        return {"pairs": len(keys), "P2g_only": b, "P2g+_only": c_,
                "both": sum(x[k] == y[k] == "IMPOSSIBLE" for k in keys),
                "p": mcnemar_exact(b, c_)}
    ach_p = [k for k in pl["P2g"] if tf(k) == "ACHIEVABLE"]
    ach_0 = [c for c in cases if truth[c] == "ACHIEVABLE"]
    m["false_refutation_mcnemar"] = {
        "pooled": fr_mcnemar(pl["P2g"], pl["P2g+"], ach_p),
        "sample0": fr_mcnemar(s0["P2g"], s0["P2g+"], ach_0)}

    # Rdet: C3 and witness agreement
    rd_rows = {c: R[("Rdet", c, 0)] for c in cases if ("Rdet", c, 0) in R
               and not R[("Rdet", c, 0)].get("missing")}
    c3 = []
    for c, r in rd_rows.items():
        hard_unavail = [q for q in tdocs[c]["requirements"]
                        if q.get("hard") and q.get("status") == "unavailable"]
        if r["verdict"] == "IMPOSSIBLE" and not hard_unavail:
            c3.append({"case": c, "truth": tdocs[c]["verdict"],
                       "requirements": [{"requirement": w["requirement"],
                                         "basis": w["basis"],
                                         "evidence": w["evidence"][:3]}
                                        for w in r["witness"]]})
    wa = []
    for c, r in rd_rows.items():
        if r["verdict"] != "IMPOSSIBLE":
            continue
        agr = witness_agreement(r["blocking"], tdocs[c]["blocking"])
        wa.append({"case": c, "truth": tdocs[c]["verdict"], "rdet_blocking": r["blocking"],
                   "truth_blocking": tdocs[c]["blocking"], "match": agr,
                   "any_same_kind_and_name": any(a["same_kind_and_name"] for a in agr)})
    m["rdet"] = {"refutations": len(wa),
                 "false_refutations_without_unavailable_hard_requirement": c3,
                 "witness_agreement": wa,
                 "witness_agreement_summary": {
                     "refutations": len(wa),
                     "on_blocked_documents": sum(w["truth"] == "BLOCKED" for w in wa),
                     "same_kind_and_name_on_blocked": sum(
                         w["truth"] == "BLOCKED" and w["any_same_kind_and_name"]
                         for w in wa)},
                 "unknown_requirements_total": sum(len(r.get("unknown_requirements") or [])
                                                   for r in rd_rows.values())}
    m["union_refuted_by_pooled"] = dict(Counter(
        "+".join(r["refuted_by"]) or "none" for r in rows
        if r["arm"] == UNION and not r.get("missing")))

    ap, a0 = m["accuracy_pooled_3samples"], m["accuracy_sample0"]
    frp = m["false_refutation_mcnemar"]["pooled"]
    fr_p2g, fr_plus = ap["P2g"]["false_refutations"], ap["P2g+"]["false_refutations"]
    rec_p2g, rec_plus = ap["P2g"]["blocked_recall"], ap["P2g+"]["blocked_recall"]
    rec_u, rec_d = ap[UNION]["blocked_recall"], a0["D"]["blocked_recall"]
    fr_u = ap[UNION]["false_refutation_rate"]
    m["criteria"] = {
        "B1": {"rule": "P2g+ false refutations of ACHIEVABLE documents at most half of "
                       "P2g's (same samples, pooled over 3; exact McNemar)",
               "value": {"P2g": fr_p2g, "P2g+": fr_plus, "mcnemar_p": frp["p"],
                         "sample0": {"P2g": a0["P2g"]["false_refutations"],
                                     "P2g+": a0["P2g+"]["false_refutations"]}},
               "met": fr_plus <= 0.5 * fr_p2g},
        "B2": {"rule": "P2g+ BLOCKED recall not more than 5 points below P2g's (pooled)",
               "value": {"P2g": rec_p2g, "P2g+": rec_plus,
                         "difference_points": rnd(100 * (rec_plus - rec_p2g), 2)},
               "met": rec_plus >= rec_p2g - 0.05 - 1e-9},
        "B3": {"rule": "fidelity F1 and F4 yes-rates of P2g+ higher than P2g's on the same "
                       "30 documents", "value": None, "met": "pending judge"},
        "B4": {"rule": "finance agent (multi-role validation)", "value": None,
               "met": "not part of this run"},
        "C1": {"rule": "BLOCKED recall of P2g+ ∪ Rdet at least D's minus 5 points "
                       "(union pooled over 3 samples, D once)",
               "value": {UNION: rec_u, "D": rec_d,
                         "difference_points": rnd(100 * (rec_u - rec_d), 2),
                         "union_sample0": a0[UNION]["blocked_recall"]},
               "met": rec_u >= rec_d - 0.05 - 1e-9},
        "C2": {"rule": "false refutations of ACHIEVABLE documents for P2g+ ∪ Rdet <= 10% "
                       "(pooled)",
               "value": {"rate": fr_u, "count": ap[UNION]["false_refutations"],
                         "of": ap[UNION]["achievable_total"],
                         "sample0_rate": a0[UNION]["false_refutation_rate"]},
               "met": fr_u is not None and fr_u <= 0.10},
        "C3": {"rule": "Rdet has zero false refutations on documents whose truth lists no "
                       "unavailable hard requirement",
               "value": {"count": len(c3), "cases": [x["case"] for x in c3]},
               "met": len(c3) == 0}}
    dpath = out / "defects.json"
    if dpath.exists():
        m["defects_P2g+_false_refutations"] = read_json(dpath)
    return m


# --- judge (B3 prepared here, computed after the judges)

JUDGE_README3 = """# Fidelity judge (set3, PLAN.md Addendum B criterion B3, rubric F1..F5)

Each file in `items/` is one document compacted by one of two compaction methods.
File names are `<case>__<variant>.json`; the variant is `p2g` or `p2gplus`, two
versions of the compaction prompt.  Judge every item on its own, against its source
text only; do not compare the two variants of a case and do not try to tell which is
which.  Each item holds `source_text` (the original SKILL.md or agent.md), `ce` (the
final Controlled English pack the compactor, gpt-5.4, wrote for it, sample 0,
rendered with its bindings), `runtime` (the runtime it was bound to; `reply` is the
agent's own answer in the conversation) and `rubric`.  No item holds a verdict, a
truth label or a score.

The 30 documents are the first 30 in sha256("set3-judge:" + case) order among the
documents where both variants produced a valid sample-0 pack (`documents.json`).

For each of the five items in `rubric`, answer `yes`, `no` or `unclear` and give a
one-line reason that cites the document (a quoted phrase or a section) and the pack
(a Tool name, a protocol step or the Goal).

Write `scores/<case>__<variant>.json` (the same stem as the item):

```json
{"case": "c001", "variant": "p2g",
 "F1": "yes", "F1_reason": "...",
 "F2": "no",  "F2_reason": "...",
 "F3": "yes", "F3_reason": "...",
 "F4": "yes", "F4_reason": "...",
 "F5": "unclear", "F5_reason": "..."}
```

A second judge scores both variants of the 6 cases in `second_judge.json` (20% of the
30) the same way into `scores2/<case>__<variant>.json`, without reading `scores/`.
Then run `python scripts/reliability.py judge-score OUT`.

Notes for judging:
- F1: a Tool is invented when no sentence of the document asks for that operation.
- F2: a step is mandatory when the document's core deliverable cannot be produced
  without it; optional or follow-up work may be omitted or skippable.
- F3: the Goal must name the deliverable of one representative request.
- F4: an ordering is invented when the protocol puts two steps in an order the
  document neither states nor implies (e.g. by data dependence).
- F5: `via` must name a runtime tool from `runtime.tools` that can really perform
  the Tool; a `via` naming something outside that list is plausible only if the
  runtime indeed cannot perform the operation.
- A branch written `(assuming P)` states facts that hold once that branch is taken.
"""


def judge_prep3(out: Path) -> None:
    frozen = read_json(out / "frozen.json")
    rt = load_runtime(str(out / "runtime.json"))
    jd = out / "judge"
    order = sorted((c["case"] for c in frozen["cases"]), key=lambda c: sha("set3-judge:" + c))
    chosen, skipped = [], []
    for c in order:
        if len(chosen) == JUDGE_N3:
            break
        if all((out / "packs" / a / f"{c}__s0.json").exists() for a in JUDGE_VARIANTS):
            chosen.append(c)
        else:
            skipped.append(c)
    kinds = {c["case"]: c["kind"] for c in frozen["cases"]}
    for c in chosen:
        for arm, var in JUDGE_VARIANTS.items():
            d = read_json(out / "packs" / arm / f"{c}__s0.json")
            write_json(jd / "items" / f"{c}__{var}.json", {
                "case": c, "kind": kinds[c],
                "source_text": (SET3 / "cases" / f"{c}.md").read_text(encoding="utf-8"),
                "ce": render_ce(d["pre_binding"], d["bindings"], d.get("live_goal")),
                "runtime": {"name": rt.name, "description": rt.description,
                            "tools": rt.all_tools},
                "rubric": RUBRIC})
    second = sorted(sorted(chosen, key=lambda i: sha("judge2:" + i))[:JUDGE2_N3])
    write_json(jd / "second_judge.json", second)
    write_json(jd / "documents.json", {"order": "sha256('set3-judge:'+case), ascending",
                                       "documents": chosen,
                                       "skipped_no_valid_pack_for_both": skipped})
    (jd / "README.md").write_text(JUDGE_README3, encoding="utf-8")
    (jd / "scores").mkdir(exist_ok=True)
    (jd / "scores2").mkdir(exist_ok=True)
    print(f"{len(chosen)} documents x 2 variants, skipped {skipped}, "
          f"second judge {second}, in {jd}")


def judge_score3(out: Path) -> None:
    jd = out / "judge"
    norm = {"yes": "yes", "no": "no", "unclear": "unclear"}
    first = {p.stem: read_json(p) for p in sorted((jd / "scores").glob("*.json"))}
    second = {p.stem: read_json(p) for p in sorted((jd / "scores2").glob("*.json"))}
    items = {p.stem for p in (jd / "items").glob("*.json")}
    fid: dict = {"items": len(items), "scored": len(set(first) & items), "per_variant": {}}
    for arm, var in JUDGE_VARIANTS.items():
        sc = {k: v for k, v in first.items() if k in items and k.endswith("__" + var)}
        per = {}
        for f in RUBRIC:
            vals = [norm.get(str(s.get(f, "")).strip().lower(), "unclear") for s in sc.values()]
            y = vals.count("yes")
            per[f] = {"yes": y, "no": vals.count("no"), "unclear": vals.count("unclear"),
                      "yes_rate": rnd(y / len(vals)) if vals else None,
                      "ci95": wilson(y, len(vals))}
        fid["per_variant"][arm] = {"scored": len(sc), "per_item": per}
    both = sorted(set(first) & set(second))
    if both:
        a, b, per = [], [], {}
        for f in RUBRIC:
            x = [norm.get(str(first[c].get(f, "")).lower(), "unclear") for c in both]
            y = [norm.get(str(second[c].get(f, "")).lower(), "unclear") for c in both]
            per[f] = {"agree": sum(i == j for i, j in zip(x, y)), "n": len(both),
                      "cohen_kappa": cohen_kappa(x, y)}
            a += x
            b += y
        fid["second_judge"] = {"items": len(both), "per_item": per,
                               "agreement": rnd(sum(i == j for i, j in zip(a, b)) / len(a)),
                               "cohen_kappa_pooled": cohen_kappa(a, b)}
    m = read_json(out / "metrics.json")
    m["fidelity"] = fid
    pv = fid["per_variant"]
    complete = bool(items) and items <= set(first)
    val = {f: {a: pv[a]["per_item"][f]["yes_rate"] for a in JUDGE_VARIANTS}
           for f in ("F1", "F4")}
    m["criteria"]["B3"].update({
        "value": val,
        "met": all((val[f]["P2g+"] or 0) > (val[f]["P2g"] or 0) for f in val)
        if complete else "pending judge"})
    write_json(out / "metrics.json", m)
    print(json.dumps(fid, indent=1))


# ------------------------------------------------------------------ set4 (Addendum E)
# `prepare --set <dir> --out OUT` with any set directory other than the names set2 and
# set3 freezes the Addendum E arms on that set (written for set4; also used on set3 as
# a development run).  frozen.json["experiment"] == "addendum-e"; run, score dispatch
# here.  Nothing above this line changes behaviour for set2 or set3 directories.

# arm -> (kind, model, samples, CE prompt version, located-error retries)
ARMS4 = {"P2g+": ("ce", GPT, 3, "p2g+", 2), "P2g++": ("ce", GPT, 3, "p2g++", 2),
         "Rllm": ("rllm", GPT, 3, None, 1), "Rdet": ("rdet", None, 1, None, 0),
         "Rdet2": ("rdet2", None, 1, None, 0), "D": ("direct", GPT, 1, None, 0)}
CE_KINDS4 = ("ce",)
# union -> component arms; per sample: IMPOSSIBLE if any refutes, ACHIEVABLE if all
# say ACHIEVABLE, otherwise UNKNOWN.  A one-sample arm is the same for every sample.
UNIONS4 = {"U1": ("P2g+", "Rdet"), "U2": ("P2g++", "Rdet2", "Rllm"),
           "Rllm|Rdet": ("Rllm", "Rdet"), "Rllm|Rdet2": ("Rllm", "Rdet2"),
           "P2g++|Rdet2": ("P2g++", "Rdet2")}
EXPERIMENT4 = "addendum-e"
WORKERS4 = 4
IMPL_FILES4 = IMPL_FILES3 + ["src/skillc/frontend/reqllm.py", "src/skillc/env/rdet2.py",
                            "src/skillc/frontend/contracts.py"]


def impl_hashes4() -> dict:
    return {f: (sha((ROOT / f).read_bytes()) if (ROOT / f).exists() else None)
            for f in IMPL_FILES4}


def _rdet2_fn():
    """skillc.env.rdet2.refute_text_rdet2, or None while it does not exist."""
    try:
        from skillc.env.rdet2 import refute_text_rdet2
    except ImportError:
        return None
    return refute_text_rdet2


def _set_dir(name: str) -> Path:
    p = Path(name)
    if not p.is_absolute():
        p = ROOT / p if (ROOT / p).exists() or "/" in name or "\\" in name \
            else ROOT / "benchmark" / "claude_env" / name
    return p


def prepare4(out: Path, set_dir: Path, arms: list[str] | None = None,
             samples: int | None = None) -> None:
    """Freeze the Addendum E arms on `set_dir`: every round-1 prompt (sha256), the
    manifest, the implementation hashes.  No model call and no truth file is read."""
    out.mkdir(parents=True, exist_ok=False)
    rt = load_runtime(str(MANIFEST))
    meta = read_json(set_dir / "cases.json")
    chosen = {a: ARMS4[a] for a in (arms or ARMS4)}
    if samples is not None:
        chosen = {a: (k, m, n if n == 1 else min(n, samples), v, r)
                  for a, (k, m, n, v, r) in chosen.items()}
    from skillc.frontend.reqllm import reqllm_messages
    rel_set = set_dir.relative_to(ROOT).as_posix() if set_dir.is_relative_to(ROOT) \
        else str(set_dir)
    cases, jobs = [], []
    for c in meta["cases"]:
        src = set_dir / "cases" / f"{c['case']}.md"
        text, h = src.read_text(encoding="utf-8"), text_sha(src)
        if sha(text) != h:
            raise ValueError(f"{c['case']}: read_text() does not give the pinned bytes")
        if h != c["sha256"]:
            raise ValueError(f"{c['case']}: text sha256 {h} != cases.json {c['sha256']}")
        cases.append({"case": c["case"], "id": c["id"], "kind": c["kind"],
                      "repo_url": c["repo_url"], "commit": c["commit"],
                      "path_in_repo": c["path_in_repo"], "text_sha256": h})
        for arm, (kind, model, n, version, _r) in chosen.items():
            if kind in ("rdet", "rdet2"):
                jobs.append({"case": c["case"], "arm": arm, "model": None, "sample": 0,
                             "round": 1, "kind": kind,
                             "input": f"{rel_set}/cases/{c['case']}.md", "input_sha256": h,
                             "output": f"outputs/{arm}/{c['case']}__s0.json"})
                continue
            if kind == "ce":
                system, user = ce_runtime_messages(text, rt, version=version)
            elif kind == "rllm":
                system, user = reqllm_messages(text)
            else:
                system, user = direct_messages(text, rt)
            for s in range(n):
                prel, orel = out_rel(arm, c["case"], s)
                write_json(out / prel, {"system": system, "user": user})
                jobs.append({"case": c["case"], "arm": arm, "model": model, "sample": s,
                             "round": 1, "kind": "first", "prompt": prel, "output": orel,
                             "prompt_sha256": sha((out / prel).read_bytes())})
    (out / "runtime.json").write_bytes(MANIFEST.read_bytes())
    from skillc.frontend import reqllm
    _crm = ce_runtime_messages
    probe = _crm("x", rt, version="p2g++")[0]
    write_json(out / "frozen.json", {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": EXPERIMENT4,
        "plan": "runs/20261015_review_response/PLAN.md Addendum E (E-a Rdet2, E-b Rllm, "
                "E-c P2g++, G1..G5)",
        "set": rel_set, "seed": meta.get("seed"),
        "runtime": RUNTIME, "runtime_sha256": sha(MANIFEST.read_bytes()),
        "arms": {a: {"kind": k, "model": m, "samples": n, "prompt_version": v,
                     "located_error_retries": r,
                     "repair": "one guarded counterexample repair (round retries+2)"
                     if k == "ce" else None}
                 for a, (k, m, n, v, r) in chosen.items()},
        "unions": {u: {"arms": list(c), "rule": "per sample: IMPOSSIBLE if any arm "
                       "refutes; ACHIEVABLE only if every arm says ACHIEVABLE; otherwise "
                       "UNKNOWN; a one-sample arm is the same for every sample"}
                   for u, c in UNIONS4.items() if all(a in chosen for a in c)},
        "bind": {"prune": False, "library": None, "software": False},
        "p2g++_prune": "pack.prune_dead_reply on the bound pack; kept only when the "
                       "checker's label, reason and protocol status are unchanged",
        "rdet": "skillc.env.manifest.refute_text(text, runtime.json)",
        "rdet2": "skillc.env.rdet2.refute_text_rdet2(text, runtime.json)",
        "rllm": "skillc.frontend.reqllm: extraction_from_replies + evaluate_extraction "
                "(runtime.json); JSON mode; one located-error retry",
        "system_prompt_sha256": {"p2g+": sha(_crm("x", rt, version="p2g+")[0]),
                                 "p2g++": sha(probe), "rllm": sha(reqllm.SYSTEM)},
        "workers": WORKERS4,
        "cases": cases, "jobs": jobs, "implementation_sha256": impl_hashes4()})
    print(f"prepared {len(cases)} cases from {rel_set}: "
          f"{dict(Counter(j['arm'] for j in jobs))} round-1 jobs in {out}")


def _arms4(frozen: dict) -> dict:
    return {a: (v["kind"], v["model"], v["samples"], v["prompt_version"],
                v["located_error_retries"]) for a, v in frozen["arms"].items()}


def _execute4(out: Path, job: dict, log: Log) -> str:
    """One model call (JSON mode for the direct verdict and for Rllm)."""
    o = out / job["output"]
    if o.exists():
        return o.read_text(encoding="utf-8")
    prompt = read_json(out / job["prompt"])
    tag = f"{job['arm']}/{job['case']}/s{job['sample']}/r{job['round']}"
    text, usage, jm, secs = call_model(prompt["system"], prompt["user"], job["model"],
                                       ARMS4[job["arm"]][0] in ("direct", "rllm"), log, tag)
    write_json(usage_path(out, job["output"]), {
        "model": job["model"], "json_mode": jm, "elapsed_s": secs, "usage": usage,
        "utc": datetime.now(timezone.utc).isoformat()})
    o.parent.mkdir(parents=True, exist_ok=True)
    o.write_text(text, encoding="utf-8")
    tok = sum(u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) for u in usage)
    log(f"{tag}: done {secs}s in={tok} out={sum(u.get('output_tokens', 0) for u in usage)}")
    return text


def _chain_next4(out: Path, base: dict, rt, arms4: dict) -> dict | None:
    """_chain_next for the CE arms of Addendum E (P2g+ chain: retries=2, repair on
    label IMPOSSIBLE) and the Rllm retry (one located-error retry, no repair)."""
    arm = base["arm"]
    kind, retries = arms4[arm][0], arms4[arm][4]
    o = out / base["output"]
    if not o.exists():
        return None
    reply = o.read_text(encoding="utf-8")
    if kind == "rllm":
        from skillc.frontend.reqllm import ExtractionError, parse_extraction, RETRY_PROMPT
        try:
            parse_extraction(reply, strict=True)
            return None
        except ExtractionError as e:
            j = _followup(out, base, 2, RETRY_PROMPT.format(error=str(e), reply=reply.strip()))
            j["kind"] = "retry"
            return None if (out / j["output"]).exists() else j
    parsed = parse_p2g(reply, rt)
    k = 0
    while not parsed["ok"] and k < retries:
        k += 1
        j = _followup(out, base, 1 + k, CE_RETRY_PROMPT.format(error=parsed["error"],
                                                               text=reply.strip()))
        j["kind"] = "retry"
        if not (out / j["output"]).exists():
            return j
        reply = (out / j["output"]).read_text(encoding="utf-8")
        parsed = parse_p2g(reply, rt)
    if not parsed["ok"]:
        return None
    v, _ = safe_check(parsed["pack"])
    if v is None or v.label != "IMPOSSIBLE":
        return None
    expl = explain_refutation(v, _B(parsed["withdrawn"], parsed["blocked"]))
    j = _followup(out, base, retries + 2, CE_REPAIR_PROMPT.format(
        explanation=expl, text=extract_ce(reply).strip()))
    j["kind"] = "repair"
    return None if (out / j["output"]).exists() else j


def _deterministic4(out: Path, j: dict, log: Log) -> bool:
    """Rdet / Rdet2 for one document; False when Rdet2 is not implemented yet."""
    if (out / j["output"]).exists():
        return True
    text = (ROOT / j["input"]).read_text(encoding="utf-8")
    if j["kind"] == "rdet":
        write_json(out / j["output"], _rdet_eval(text, out / "runtime.json"))
        return True
    fn = _rdet2_fn()
    if fn is None:
        return False
    write_json(out / j["output"], fn(text, str(out / "runtime.json"), name=None).to_dict())
    return True


def run4(out: Path, arms: list[str] | None, limit: int | None,
         only_cases: list[str] | None = None, samples: list[int] | None = None,
         dry_run: bool = False) -> None:
    frozen = read_json(out / "frozen.json")
    arms4 = _arms4(frozen)
    rt = load_runtime(str(out / "runtime.json"))
    log = Log(out / "run.log")
    jobs = [j for j in frozen["jobs"] if j["round"] == 1 and (not arms or j["arm"] in arms)]
    for j in jobs:
        if j["kind"] in ("rdet", "rdet2"):
            if text_sha(ROOT / j["input"]) != j["input_sha256"]:
                raise ValueError(f"text changed: {j['input']}")
        elif sha((out / j["prompt"]).read_bytes()) != j["prompt_sha256"]:
            raise ValueError(f"prompt changed: {j['prompt']}")
    if only_cases:
        jobs = [j for j in jobs if j["case"] in only_cases]
    if samples is not None:
        jobs = [j for j in jobs if j["sample"] in samples]
    if limit:
        jobs = jobs[:limit]
    calls = [j for j in jobs if j["kind"] == "first"]
    todo = [j for j in calls if not (out / j["output"]).exists()]
    if dry_run:
        det = [j for j in jobs if j["kind"] in ("rdet", "rdet2")
               and not (out / j["output"]).exists()]
        print(json.dumps({"round1_model_calls_pending": dict(Counter(j["arm"] for j in todo)),
                          "deterministic_pending": dict(Counter(j["arm"] for j in det)),
                          "rdet2_available": _rdet2_fn() is not None,
                          "implementation_changed_since_prepare": sorted(
                              f for f, h in impl_hashes4().items()
                              if frozen["implementation_sha256"].get(f) != h)}, indent=1))
        return
    changed = sorted(f for f, h in impl_hashes4().items()
                     if frozen["implementation_sha256"].get(f) != h)
    if changed:
        log(f"WARNING implementation changed since prepare: {changed}")
    log(f"run ({EXPERIMENT4}): {len(jobs)} round-1 jobs ({dict(Counter(j['arm'] for j in jobs))})")
    for j in jobs:          # Rdet, Rdet2: no model, main thread
        if j["kind"] in ("rdet", "rdet2") and not _deterministic4(out, j, log):
            log(f"SKIPPED {j['arm']}/{j['case']}: skillc.env.rdet2 is not importable")
    failed = _pool(out, todo, log, "round 1", WORKERS4, _execute4)
    chained = [j for j in calls if arms4[j["arm"]][0] in ("ce", "rllm")]
    for step in range(2, 6):
        nxt = [n for n in (_chain_next4(out, j, rt, arms4) for j in chained) if n is not None]
        log(f"follow-up pass {step}: {len(nxt)} jobs ({dict(Counter(n['kind'] for n in nxt))})")
        if not nxt:
            break
        failed += _pool(out, nxt, log, f"follow-up pass {step}", WORKERS4, _execute4)
    _record_followups4(out)
    log(f"run finished: {len(failed)} failed calls {failed}")


def _record_followups4(out: Path) -> None:
    frozen = read_json(out / "frozen.json")
    arms4 = _arms4(frozen)
    by_key = {(j["arm"], j["case"], j["sample"]): j for j in frozen["jobs"]
              if j["round"] == 1 and j["kind"] == "first"}
    extra = []
    for arm, (kind, *_rest) in arms4.items():
        if kind not in ("ce", "rllm"):
            continue
        for p in sorted((out / "prompts" / arm).glob("*__r[2-9].json")):
            case, s, r = p.stem.split("__")
            rr = int(r[1:])
            base = by_key[(arm, case, int(s[1:]))]
            extra.append({**base, "round": rr,
                          "kind": "repair" if kind == "ce" and rr == arms4[arm][4] + 2
                          else "retry",
                          "prompt": f"prompts/{arm}/{p.name}",
                          "output": f"outputs/{arm}/{p.stem}.txt",
                          "prompt_sha256": sha(p.read_bytes())})
    frozen["jobs"] = [j for j in frozen["jobs"] if j["round"] == 1] + extra
    write_json(out / "frozen.json", frozen)


# --- score

def prune_checked(pack: dict, bindings: dict) -> tuple[dict, list, bool]:
    """P2g++'s dead-reply prune, kept only when the checker's label, reason and
    protocol status are unchanged (then the verdict cannot differ).  Returns
    (pack to check, removed tools, reverted)."""
    from skillc.pack import prune_dead_reply
    pruned, removed = prune_dead_reply(pack, bindings)
    if not removed:
        return pack, [], False
    a, ea = safe_check(pack)
    b, eb = safe_check(pruned)
    key = (lambda v: None if v is None else (v.label, v.reason, v.unknown,
                                              getattr(v, "protocol", None)))
    if ea or eb or key(a) != key(b):
        return pack, removed, True
    return pruned, removed, False


def _union_row(rows_by: dict, comps: tuple, case: str, s: int, arms4: dict) -> dict:
    parts = {}
    for a in comps:
        r = rows_by.get((a, case, 0 if arms4[a][2] == 1 else s))
        if r is None or r.get("missing"):
            return {"missing": True, "verdict": "MISSING",
                    "missing_arm": a}
        parts[a] = r
    vs = {a: r["verdict"] for a, r in parts.items()}
    if "IMPOSSIBLE" in vs.values():
        v = "IMPOSSIBLE"
    elif all(x == "ACHIEVABLE" for x in vs.values()):
        v = "ACHIEVABLE"
    else:
        v = "UNKNOWN"
    wit = {}
    for a, r in parts.items():
        if r["verdict"] != "IMPOSSIBLE":
            continue
        wit[a] = list(_witness(r)) if arms4[a][0] == "ce" else list(r.get("blocking") or [])
    return {"verdict": v, "valid_final": True, "components": vs,
            "refuted_by": [a for a, x in vs.items() if x == "IMPOSSIBLE"], "witness": wit}


def score4(out: Path) -> None:
    frozen = read_json(out / "frozen.json")
    arms4 = _arms4(frozen)
    set_dir = ROOT / frozen["set"]
    rt = load_runtime(str(out / "runtime.json"))
    tdocs = {c["case"]: read_json(set_dir / "truth" / f"{c['case']}.json")
             for c in frozen["cases"]}
    truth = {c: TRUTH_MAP[d["verdict"]] for c, d in tdocs.items()}
    kinds = {c["case"]: c["kind"] for c in frozen["cases"]}
    texts = {c["case"]: (set_dir / "cases" / f"{c['case']}.md").read_text(encoding="utf-8")
             for c in frozen["cases"]}
    from skillc.frontend.reqllm import (evaluate_extraction, extraction_from_replies,
                                        invalid_evaluation)
    groups: dict = {}
    for j in frozen["jobs"]:
        if j["kind"] in ("rdet", "rdet2"):
            if text_sha(ROOT / j["input"]) != j["input_sha256"]:
                raise ValueError(f"text changed: {j['input']}")
        elif sha((out / j["prompt"]).read_bytes()) != j["prompt_sha256"]:
            raise ValueError(f"prompt changed: {j['prompt']}")
        groups.setdefault((j["arm"], j["case"], j["sample"]), {})[j["round"]] = j
    rows = []
    for (arm, case, s), jobs in sorted(groups.items()):
        kind = arms4[arm][0]
        row = {"case": case, "kind": kinds[case], "arm": arm, "model": arms4[arm][1],
               "sample": s, "truth": truth[case]}
        if kind in ("rdet", "rdet2"):
            p = out / jobs[1]["output"]
            row["usage"] = {}
            if not p.exists():
                row.update({"missing": True, "verdict": "MISSING"})
            else:
                e = read_json(p)
                row.update({"valid_first": True, "valid_final": True, "rounds": 0,
                            "verdict": e["verdict"], "reason": e.get("reason"),
                            "blocking": e.get("blocking", []), "witness": e.get("witness", []),
                            "unknown_requirements": e.get("unknown", [])})
            rows.append(row)
            continue
        outs = [j["output"] for j in jobs.values() if (out / j["output"]).exists()]
        row["usage"] = _usage_total(out, outs)
        if not (out / jobs[1]["output"]).exists():
            row.update({"missing": True, "verdict": "MISSING"})
            rows.append(row)
            continue
        if kind == "direct":
            d = parse_direct((out / jobs[1]["output"]).read_text(encoding="utf-8"))
            row.update({"valid_first": d["ok"], "valid_final": d["ok"], "rounds": 1,
                        "verdict": d["verdict"], "missing_resources": d.get("missing"),
                        "error": d.get("error")})
            rows.append(row)
            continue
        if kind == "rllm":
            replies = [(out / jobs[r]["output"]).read_text(encoding="utf-8")
                       for r in sorted(jobs) if (out / jobs[r]["output"]).exists()]
            ext, err = extraction_from_replies(replies)
            ev = invalid_evaluation(str(out / "runtime.json"), err) if ext is None else \
                evaluate_extraction(ext, texts[case], str(out / "runtime.json"))
            write_json(out / "evals" / arm / f"{case}__s{s}.json", ev)
            first_ok, _e = extraction_from_replies(replies[:1])
            row.update({"valid_first": first_ok is not None and not first_ok.get("invalid")
                        and len(replies) == 1, "valid_final": ext is not None,
                        "rounds": len(replies), "verdict": ev["verdict"],
                        "reason": ev["reason"], "blocking": ev["blocking"],
                        "witness": ev["witness"], "unknown_requirements": ev["unknown"],
                        "quotes": ev["quotes"], "invalid_items": len(ev["invalid_items"]),
                        "requirements": len(ev["requirements"]),
                        "hard": sum(r["hard"] for r in ev["requirements"]),
                        "hard_cleared": sum(bool(r["hard_cleared"])
                                            for r in ev["requirements"]),
                        "error": err})
            rows.append(row)
            continue
        rec = score_ce_sample(out, jobs, rt, retries=arms4[arm][4])
        row.update({"valid_first": rec.get("valid_first", False),
                    "valid_after_one_retry": rec.get("valid_after_one_retry",
                                                     rec.get("valid_first", False)),
                    "valid_after_retry": rec.get("valid_after_retry", False),
                    "valid_final": rec.get("ok", False), "rounds": rec["rounds"],
                    "repaired": rec["repaired"], "repair_rejected": rec["repair_rejected"],
                    "repair_invalid": rec["repair_invalid"], "error": rec.get("error"),
                    "first_error": rec.get("first_error")})
        if rec.get("ok"):
            pack, parsed = rec["pack"], rec["parsed"]
            pruned, reverted = [], False
            if arms4[arm][3] == "p2g++":
                pack, pruned, reverted = prune_checked(pack, parsed.bindings)
            v, err = safe_check(pack)
            row.update(_verdict_fields(v, err))
            pl = planner_only(pack)
            tl = tool_lint(pack, rec["withdrawn"], rec["blocked"])
            row.update({
                "withdrawn": rec["withdrawn"], "blocked": rec["blocked"],
                "tools": sorted(set(parsed.pack["capabilities"])
                                - (set() if reverted else set(pruned))),
                "reply_tools": sorted(n for n, b in parsed.bindings.items()
                                      if b.get("via") == "reply"),
                "pruned": pruned, "prune_reverted": reverted,
                "invoked": invoked_tools(parsed.pack),
                "goal_atoms": sorted(atoms(parsed.pack["goal"])),
                "P": {k: pl[k] for k in ("label", "reason", "frontier")},
                "T": tl})
            write_json(out / "packs" / arm / f"{case}__s{s}.json",
                       {"pack": pack, "pre_binding": parsed.pack, "pruned": pruned,
                        "prune_reverted": reverted,
                        "bindings": parsed.bindings, "live_goal": parsed.live_goal})
        else:
            row.update({"verdict": "INVALID", "P": {"label": "INVALID"},
                        "T": {"label": "INVALID"}})
        rows.append(row)
    R = {(r["arm"], r["case"], r["sample"]): r for r in rows}
    unions = frozen.get("unions") or {}
    for u, spec in unions.items():
        comps = tuple(spec["arms"])
        ns = max(arms4[a][2] for a in comps)
        for c in sorted(truth):
            for s in range(ns):
                rows.append({"case": c, "kind": kinds[c], "arm": u, "sample": s,
                             "truth": truth[c], "usage": {}, "union": True,
                             **_union_row(R, comps, c, s, arms4)})
    write_json(out / "results.json", rows)
    metrics = compute_metrics4(rows, truth, tdocs, frozen, out)
    write_json(out / "metrics.json", metrics)
    print(json.dumps({k: metrics[k] for k in ("summary", "criteria")}, indent=1,
                     ensure_ascii=False))


def _agreement4(R: dict, arm: str, cases: list, ns: int) -> dict:
    cats = list(LABELS)
    table, all_agree = [], 0
    for c in cases:
        rs = [R.get((arm, c, s)) for s in range(ns)]
        if any(r is None or r.get("missing") for r in rs):
            continue
        vs = [r["verdict"] if r["verdict"] in cats else "INVALID" for r in rs]
        table.append([vs.count(k) for k in cats])
        all_agree += len(set(vs)) == 1
    return {"documents": len(table), "samples": ns, "all_agree": all_agree,
            "all_agree_rate": rnd(all_agree / len(table)) if table else None,
            "all_agree_ci95": wilson(all_agree, len(table)),
            "fleiss_kappa": fleiss_kappa(table) if ns > 1 else None}


def compute_metrics4(rows: list[dict], truth: dict, tdocs: dict, frozen: dict,
                     out: Path) -> dict:
    arms4 = _arms4(frozen)
    cases = sorted(truth)
    R = {(r["arm"], r["case"], r["sample"]): r for r in rows}
    names = list(arms4) + list(frozen.get("unions") or {})
    nsamp = {a: arms4[a][2] for a in arms4}
    for u, spec in (frozen.get("unions") or {}).items():
        nsamp[u] = max(arms4[a][2] for a in spec["arms"])
    m: dict = {"created_utc": datetime.now(timezone.utc).isoformat(),
               "experiment": EXPERIMENT4, "set": frozen["set"],
               "implementation_sha256_at_score": impl_hashes4(),
               "implementation_sha256_at_prepare": frozen["implementation_sha256"],
               "implementation_changed_since_prepare": sorted(
                   f for f, h in impl_hashes4().items()
                   if frozen["implementation_sha256"].get(f) != h),
               "truth": dict(Counter(truth.values())),
               "missing_outputs": dict(Counter(r["arm"] for r in rows if r.get("missing")))}
    tot, per_arm = Counter(), {}
    for r in rows:
        if r.get("union"):
            continue
        a = per_arm.setdefault(r["arm"], Counter())
        for k, v in (r.get("usage") or {}).items():
            tot[k] += v
            a[k] += v
    m["calls"] = {"total": dict(tot), "per_arm": {a: dict(c) for a, c in per_arm.items()}}

    def lab(arm, s):
        return {c: (R[(arm, c, s)]["verdict"] if (arm, c, s) in R
                    and not R[(arm, c, s)].get("missing") else "MISSING") for c in cases}

    def pooled(arm):
        return {(c, s): v for s in range(nsamp[arm]) for c, v in lab(arm, s).items()}

    def tf(k):
        return truth[k[0] if isinstance(k, tuple) else k]

    m["accuracy_sample0"] = {a: arm_accuracy(lab(a, 0), truth) for a in names}
    m["accuracy_pooled"] = {a: arm_accuracy(pooled(a), truth) for a in names}
    m["accuracy_per_sample"] = {a: [arm_accuracy(lab(a, s), truth) for s in range(nsamp[a])]
                                for a in names if nsamp[a] > 1}
    m["agreement"] = {a: _agreement4(R, a, cases, nsamp[a]) for a in names if nsamp[a] > 1}

    # schema gate of the model arms
    sg = {}
    for a in arms4:
        rs = [r for r in rows if r["arm"] == a and not r.get("missing")]
        if arms4[a][0] in ("ce", "rllm", "direct") and rs:
            sg[a] = {"samples": len(rs), "valid_first": sum(bool(r.get("valid_first"))
                                                            for r in rs),
                     "valid_final": sum(bool(r.get("valid_final")) for r in rs)}
    m["schema_gate"] = sg

    # P2g++: prune and paired verdicts against P2g+
    for a in arms4:
        if arms4[a][3] != "p2g++":
            continue
        rs = [r for r in rows if r["arm"] == a and r.get("valid_final")]
        m["prune"] = {"packs": len(rs), "packs_pruned": sum(bool(r.get("pruned"))
                                                            and not r.get("prune_reverted")
                                                            for r in rs),
                      "tools_removed": sum(len(r.get("pruned") or []) for r in rs
                                           if not r.get("prune_reverted")),
                      "reverted": sum(bool(r.get("prune_reverted")) for r in rs),
                      "reply_tools_per_pack": rnd(sum(len(r.get("reply_tools") or [])
                                                      for r in rs) / len(rs)) if rs else None}
    if "P2g+" in arms4:
        rs = [r for r in rows if r["arm"] == "P2g+" and r.get("valid_final")]
        m["reply_tools_per_pack_P2g+"] = rnd(sum(len(r.get("reply_tools") or [])
                                                 for r in rs) / len(rs)) if rs else None

    # Rllm: G5 and extraction statistics
    for a in arms4:
        if arms4[a][0] != "rllm":
            continue
        rs = [r for r in rows if r["arm"] == a and not r.get("missing")]
        qt = sum((r.get("quotes") or {}).get("total", 0) for r in rs)
        qv = sum((r.get("quotes") or {}).get("verbatim", 0) for r in rs)
        m["rllm"] = {"samples": len(rs), "quotes_total": qt, "quotes_verbatim": qv,
                     "quote_verbatim_rate": rnd(qv / qt) if qt else None,
                     "requirements_kept": sum(r.get("requirements", 0) for r in rs),
                     "hard": sum(r.get("hard", 0) for r in rs),
                     "hard_cleared": sum(r.get("hard_cleared", 0) for r in rs),
                     "invalid_items": sum(r.get("invalid_items", 0) for r in rs),
                     "invalid_extractions": sum(r["verdict"] == "UNKNOWN" for r in rs),
                     "retried": sum(r.get("rounds", 1) > 1 for r in rs)}
        fr = []
        for r in rs:
            if r["verdict"] == "IMPOSSIBLE" and truth[r["case"]] == "ACHIEVABLE":
                fr.append({"case": r["case"], "sample": r["sample"],
                           "witness": [{"requirement": w["requirement"], "basis": w["basis"],
                                        "quote": w["quote"]} for w in r["witness"]]})
        m["rllm"]["false_refutations"] = fr
        m["rllm"]["missed_blocked"] = [
            {"case": r["case"], "sample": r["sample"], "truth_blocking":
             tdocs[r["case"]].get("blocking")} for r in rs
            if truth[r["case"]] == "IMPOSSIBLE" and r["verdict"] != "IMPOSSIBLE"]

    mc = {}
    pairs = [("U2", "U1"), ("P2g++", "P2g+"), ("Rdet2", "Rdet"), ("Rllm", "Rdet"),
             ("Rllm|Rdet", "Rdet"), ("U2", "D"), ("U1", "D")]
    for x, y in pairs:
        if x in nsamp and y in nsamp:
            px, py = pooled(x), pooled(y)
            if nsamp[y] == 1 and nsamp[x] > 1:
                py = {(c, s): v for (c, _s), v in py.items() for s in range(nsamp[x])}
            mc[f"{x}_vs_{y}_pooled"] = mcnemar_keys(px, py, tf)
            mc[f"{x}_vs_{y}_sample0"] = mcnemar_keys(lab(x, 0), lab(y, 0), tf)
    if "P2g++" in nsamp and "P2g+" in nsamp:
        a, b = pooled("P2g++"), pooled("P2g+")
        mc["P2g++_vs_P2g+_verdict_changes"] = dict(Counter(
            f"{b[k]}->{a[k]}" for k in a if k in b and a[k] != b[k]))
    m["mcnemar"] = mc
    m["mcnemar_note"] = ("pooled pairs are (case, sample); samples of one document are not "
                        "independent, so pooled p-values are optimistic")

    ap = m["accuracy_pooled"]

    def get(a, f):
        return ap.get(a, {}).get(f)
    m["summary"] = {a: {"recall": get(a, "blocked_recall"),
                        "false_refutations": get(a, "false_refutations"),
                        "false_refutation_rate": get(a, "false_refutation_rate"),
                        "accuracy_decided": get(a, "accuracy_decided"),
                        "counts": get(a, "counts")} for a in names}
    crit = {}
    if "U2" in ap and "D" in ap:
        r_u, r_d = get("U2", "blocked_recall"), get("D", "blocked_recall")
        crit["G1"] = {"rule": "U2 recall of BLOCKED (pooled) >= D's recall - 10 points",
                      "value": {"U2": r_u, "D": r_d},
                      "met": None if None in (r_u, r_d) else r_u >= r_d - 0.10 - 1e-9}
    if "U2" in ap:
        fr = get("U2", "false_refutation_rate")
        crit["G2"] = {"rule": "U2 false refutations of ACHIEVABLE (pooled) <= 10%",
                      "value": {"rate": fr, "count": get("U2", "false_refutations"),
                                "of": get("U2", "achievable_total")},
                      "met": None if fr is None else fr <= 0.10}
    if "U2" in ap and "U1" in ap:
        k = mc.get("U2_vs_U1_pooled", {})
        crit["G3"] = {"rule": "U2 decided accuracy higher than U1's (exact McNemar, same "
                              "samples)",
                      "value": {"U2": get("U2", "accuracy_decided"),
                                "U1": get("U1", "accuracy_decided"), "mcnemar": k},
                      "met": None if None in (get("U2", "accuracy_decided"),
                                              get("U1", "accuracy_decided"))
                      else get("U2", "accuracy_decided") > get("U1", "accuracy_decided")}
    if "Rdet2" in ap and "Rdet" in ap:
        f2, f1 = get("Rdet2", "false_refutations"), get("Rdet", "false_refutations")
        r2 = round((get("Rdet2", "blocked_recall") or 0) * get("Rdet2", "blocked_total"))
        r1 = round((get("Rdet", "blocked_recall") or 0) * get("Rdet", "blocked_total"))
        crit["G4"] = {"rule": "Rdet2 false refutations <= half of Rdet's, and Rdet2 recall "
                              "not lower than Rdet's by more than one document",
                      "value": {"Rdet2_fr": f2, "Rdet_fr": f1, "Rdet2_blocked_caught": r2,
                                "Rdet_blocked_caught": r1},
                      "met": None if "Rdet2" in m["missing_outputs"]
                      else (f2 <= 0.5 * f1 and r2 >= r1 - 1)}
    if "rllm" in m:
        ag = m["agreement"].get("Rllm", {})
        crit["G5"] = {"rule": "Rllm quote-verbatim rate >= 0.95; all-samples-agree rate "
                              "reported",
                      "value": {"quote_verbatim_rate": m["rllm"]["quote_verbatim_rate"],
                                "all_agree_rate": ag.get("all_agree_rate"),
                                "all_agree_ci95": ag.get("all_agree_ci95")},
                      "met": None if m["rllm"]["quote_verbatim_rate"] is None
                      else m["rllm"]["quote_verbatim_rate"] >= 0.95}
    for g, what in (("G6", "fidelity judge (rubric v1/v2, F6)"),
                    ("G7", "Decision-1 hardness filter (scripts/decision1.py)"),
                    ("G8", "Agent 365 alignment (development)")):
        crit[g] = {"rule": what, "value": None, "met": "not part of this script"}
    m["criteria"] = crit
    return m


def _experiment(out: Path) -> str | None:
    f = out / "frozen.json"
    return read_json(f).get("experiment") if f.exists() else None


def full4(out: Path, set_dir: Path, arms, samples, prepare_only: bool) -> None:
    """prepare + run + score in one command; --prepare-only stops after prepare and
    prints the pending jobs (no model call)."""
    if not (out / "frozen.json").exists():
        prepare4(out, set_dir, arms, samples)
    if prepare_only:
        run4(out, None, None, dry_run=True)
        return
    run4(out, None, None)
    score4(out)


def _is_set3(out: Path) -> bool:
    f = out / "frozen.json"
    return f.exists() and read_json(f).get("experiment") == "set3"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def e_options(p):
        p.add_argument("--arm", action="append", choices=sorted(ARMS4), dest="e_arm",
                       help="Addendum E sets only: freeze only these arms (default: all)")
        p.add_argument("--samples", type=int, help="Addendum E sets only: at most this many "
                       "samples per multi-sample arm (development runs)")

    pr = sub.add_parser("prepare")
    pr.add_argument("out", type=Path, nargs="?")
    pr.add_argument("--out", type=Path, dest="out_opt")
    pr.add_argument("--set", default="set2",
                    help="set2: experiment R (default); set3: PLAN.md Addendum C; any other "
                         "set directory (e.g. benchmark/claude_env/set4): PLAN.md Addendum E")
    e_options(pr)
    fu = sub.add_parser("full", help="Addendum E: prepare (if needed), run and score")
    fu.add_argument("out", type=Path, nargs="?")
    fu.add_argument("--out", type=Path, dest="out_opt")
    fu.add_argument("--set", required=True)
    fu.add_argument("--prepare-only", action="store_true",
                    help="freeze prompts and hashes, print pending jobs, call no model")
    e_options(fu)
    for name in ("score", "judge-prep", "judge-score"):
        sp = sub.add_parser(name)
        sp.add_argument("out", type=Path, nargs="?")
        sp.add_argument("--out", type=Path, dest="out_opt")
    r = sub.add_parser("run")
    r.add_argument("out", type=Path, nargs="?")
    r.add_argument("--out", type=Path, dest="out_opt")
    r.add_argument("--arm", action="append",
                   choices=sorted(set(ARMS) | set(ARMS3) | set(ARMS4)))
    r.add_argument("--limit", type=int, help="only the first N chains (smoke test)")
    r.add_argument("--case", action="append", help="only these cases (smoke test)")
    r.add_argument("--sample", action="append", type=int, help="only these samples")
    r.add_argument("--dry-run", action="store_true",
                   help="Addendum E: list pending jobs and changed hashes, call no model")
    a = ap.parse_args()
    a.out = a.out_opt or a.out
    if a.out is None:
        ap.error("an output directory is required (OUT or --out OUT)")
    if a.cmd in ("prepare", "full") and a.set not in ("set2", "set3"):
        set_dir = _set_dir(a.set)
        if a.cmd == "prepare":
            prepare4(a.out, set_dir, a.e_arm, a.samples)
        else:
            full4(a.out, set_dir, a.e_arm, a.samples, a.prepare_only)
        return
    if a.cmd == "full":
        ap.error("full is for Addendum E sets (not set2 or set3)")
    exp = None if a.cmd == "prepare" else _experiment(a.out)
    if exp == EXPERIMENT4:
        if a.cmd == "run":
            run4(a.out, a.arm, a.limit, a.case, a.sample, a.dry_run)
        elif a.cmd == "score":
            score4(a.out)
        else:
            ap.error(f"{a.cmd} is not implemented for Addendum E directories")
        return
    s3 = exp == "set3"
    {"prepare": lambda: (prepare3 if a.set == "set3" else prepare)(a.out),
     "run": lambda: (run3 if s3 else run)(a.out, a.arm, a.limit, a.case, a.sample),
     "score": lambda: (score3 if s3 else score)(a.out),
     "judge-prep": lambda: (judge_prep3 if s3 else judge_prep)(a.out),
     "judge-score": lambda: (judge_score3 if s3 else judge_score)(a.out)}[a.cmd]()


if __name__ == "__main__":
    main()

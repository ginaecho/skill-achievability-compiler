"""Experiment H of runs/20261015_review_response/PLAN.md: hosts end to end.

The packs the host evidence rests on were written by hand. Here gpt-5.4 compacts the
natural-language inputs with P2g (ce_runtime_messages, one located-error retry, and for
maf/scout one counterexample-guided repair guarded by repair_violations), and the
compacted packs go through the same offline checks as the authored ones.

    python scripts/hosts_e2e.py a365  prepare|run|score
    python scripts/hosts_e2e.py maf   prepare|run|score
    python scripts/hosts_e2e.py scout prepare|run|score

    run --limit N    only the first N chains (to read raw replies before the full run)
    --out DIR        another output directory (default runs/20261015_hosts/<part>)

Every prompt is written before its call and every reply right after it; frozen.json
holds their sha256s and the provider-reported usage. `score` re-checks the sha256s
and is deterministic.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import re
import shutil
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from skillc.checker import check  # noqa: E402
from skillc.formula import atoms  # noqa: E402
from skillc.frontend.contracts import bind_environment  # noqa: E402
from skillc.frontend.ce import CEError, extract_ce, parse_ce_detailed, render_ce  # noqa: E402
from skillc.frontend.prompts import (CE_REPAIR_PROMPT, CE_RETRY_PROMPT,  # noqa: E402
                                     ce_runtime_messages, explain_refutation)
from skillc.frontend.providers import azure_openai_complete, metered  # noqa: E402
from skillc.frontend.runtime import (Runtime, bind_runtime, load_runtime,  # noqa: E402
                                     repair_violations)
from skillc.pack import PackError  # noqa: E402

MODEL = "gpt-5.4"
TIMEOUT = 600
WORKERS = 4
OUT = ROOT / "runs" / "20261015_hosts"
PLAN = ROOT / "runs" / "20261015_review_response" / "PLAN.md"
A365 = ROOT / "examples" / "agent365-cases"
FINANCE = ROOT / "examples" / "hosted-agent-finance"
SET2 = ROOT / "benchmark" / "claude_env" / "set2"
SAMPLES = {"a365": 3, "maf": 3, "scout": 1}
REPAIR = {"a365": False, "maf": True, "scout": True}   # a365: retry only (the plan's H.a365)
CONFIGS = ["azure.yaml", "azure.search.yaml", "azure.isolated.yaml"]
ROLES = ("Fetcher", "ExpenseAnalyst", "RevenueAnalyst", "TaxSpecialist", "TaxVerifier", "Writer")
EMAIL_STEP = "\n\nFinal step: email the report to the CFO.\n"
MAF_NOTE = (
    "\nNote: the document above describes several roles (agents) that exchange messages. "
    "The pack must declare one Role per agent, the messages between them as `tells` steps, "
    "and the approval ordering (which step may run only after an approval), with the "
    "deliverable as the Goal.\n")
COPY_IGNORE = shutil.ignore_patterns("*.log", "logs", ".azure", ".skillc", "__pycache__",
                                     ".venv", "out", ".env", "skillc_plan.ce")
PARSE_ERRORS = (PackError, CEError, ValueError, KeyError, TypeError)


# --------------------------------------------------------------------------
# Files
# --------------------------------------------------------------------------

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def wj(path: Path, obj) -> None:
    """Atomic write, retried: Windows can hold a transient lock on the target."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(obj, indent=1, ensure_ascii=False) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    for attempt in range(20):
        try:
            tmp.write_text(data, encoding="utf-8")
            tmp.replace(path)
            return
        except OSError:
            if attempt == 19:
                raise
            time.sleep(0.5)


def rj(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def implementation() -> dict:
    files = [ROOT / "scripts" / "hosts_e2e.py", ROOT / "src/skillc/frontend/prompts.py",
             ROOT / "src/skillc/frontend/ce.py", ROOT / "src/skillc/frontend/runtime.py",
             ROOT / "src/skillc/frontend/contracts.py", ROOT / "src/skillc/frontend/grants.py",
             ROOT / "src/skillc/checker.py", ROOT / "src/skillc/gate.py",
             A365 / "run_cases.py", ROOT / "src/skillc/data/runtimes/foundry-hosted.json",
             ROOT / "src/skillc/data/runtimes/scout-desktop.json"]
    return {str(p.relative_to(ROOT)).replace("\\", "/"): sha(p.read_bytes()) for p in files}


# --------------------------------------------------------------------------
# Inputs per part
# --------------------------------------------------------------------------

def a365_cases() -> list[Path]:
    return sorted(p.parent for p in A365.glob("*/case.json"))


BLIND = False   # Addendum A: --blind-vocab (no state names anywhere in the manifest)


def a365_runtime(directory: Path, blind: bool | None = None) -> Runtime:
    """The case's grants as the only tools; descriptions from case.json actions and the
    environment's state vocabulary.  Blind (Addendum A): the action text only, and a
    runtime description that names no state."""
    blind = BLIND if blind is None else blind
    case, env = rj(directory / "case.json"), rj(directory / "environment.json")
    actions = {a["id"]: a for a in case.get("actions", [])}
    tools = {}
    for grant in env["grants"]:
        text = actions.get(grant, {}).get("description", "").strip() or grant
        adds = env["contracts"].get(grant, {}).get("add", [])
        if adds and not blind:
            text += " Establishes " + ", ".join(f"`{a}`" for a in adds) + "."
        tools[grant] = text
    states = "; ".join(f"`{k}`: {v}" for k, v in env.get("states", {}).items())
    description = (f"Microsoft Agent 365 enterprise runtime for the workflow \"{case['title']}\". "
                   "The agent acts only through the operations this tenant grants it."
                   + ("" if blind else f" State names the environment publishes: {states}."))
    return Runtime.from_dict({
        "name": f"agent365-{case['id']}", "description": description, "tools": tools,
        "grants": ["enterprise_runtime"], "lacks": ["any operation not listed"],
        "forbid_effects": [], "software": "none"})


def coordinator_instructions() -> str:
    tree = ast.parse((FINANCE / "src/finance-agent/main.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "COORDINATOR_INSTRUCTIONS"
                for t in node.targets):
            return ast.literal_eval(node.value)
    raise KeyError("COORDINATOR_INSTRUCTIONS not found in main.py")


def maf_text(email: bool) -> str:
    parts = ["# Coordinator instructions (src/finance-agent/main.py, "
             "constant COORDINATOR_INSTRUCTIONS)\n\n" + coordinator_instructions().strip()]
    for role in ROLES:
        body = (FINANCE / "skills" / f"{role}.md").read_text(encoding="utf-8").strip()
        if email and role == "Writer":
            body += EMAIL_STEP.rstrip("\n")
        parts.append(f"# Role: {role} (skills/{role}.md)\n\n{body}")
    return "\n\n".join(parts) + "\n"


def scout_cases() -> list[dict]:
    return [c for c in rj(SET2 / "cases.json")["cases"] if c["kind"] == "skill"]


def runtime_for(part: str, case: str) -> Runtime:
    if part == "a365":
        return a365_runtime(A365 / case)
    return load_runtime("foundry-hosted" if part == "maf" else "scout-desktop")


# --------------------------------------------------------------------------
# prepare
# --------------------------------------------------------------------------

def prepare(part: str, out: Path) -> None:
    if (out / "frozen.json").exists():
        raise SystemExit(f"{out} already prepared; use a fresh --out to re-prepare")
    chains = []           # (case, variant, text, runtime)
    if part == "a365":
        for d in a365_cases():
            chains.append((d.name, "main", (d / "intent.md").read_text(encoding="utf-8"),
                           a365_runtime(d)))
    elif part == "maf":
        rt = load_runtime("foundry-hosted")
        chains += [("finance", "main", maf_text(False), rt),
                   ("finance_email", "email", maf_text(True), rt)]
    else:
        rt = load_runtime("scout-desktop")
        for c in scout_cases():
            chains.append((c["case"], "main",
                           (SET2 / "cases" / f"{c['case']}.md").read_text(encoding="utf-8"), rt))
    jobs = []
    for k in range(SAMPLES[part]):            # sample-major: --limit picks different cases
        for case, variant, text, rt in chains:
            system, user = ce_runtime_messages(text, rt)
            if part == "maf":
                user = user.replace("\nCE document:", MAF_NOTE + "\nCE document:")
            rel = f"prompts/{case}__s{k}.json"
            wj(out / rel, {"system": system, "user": user})
            jobs.append({"id": f"{case}__s{k}", "case": case, "variant": variant, "sample": k,
                         "round": 1, "prompt": rel, "output": f"outputs/{case}__s{k}.txt",
                         "prompt_sha256": sha((out / rel).read_bytes())})
    for case, _, text, _ in chains:
        (out / "inputs").mkdir(parents=True, exist_ok=True)
        (out / "inputs" / f"{case}.md").write_text(text, encoding="utf-8")
    wj(out / "frozen.json", {
        "created_utc": datetime.now(timezone.utc).isoformat(), "experiment": "H", "part": part,
        "model": MODEL, "method": "P2g (ce_runtime_messages; one CE retry"
                  + ("; one guarded repair)" if REPAIR[part] else "; no repair round)"),
        "samples": SAMPLES[part], "blind_vocab": BLIND, "cases": sorted({c[0] for c in chains}),
        "runtimes": {c[0]: {"name": c[3].name, "tools": sorted(c[3].tools)} for c in chains},
        "jobs": jobs, "implementation_sha256": implementation()})
    print(f"prepared {len(jobs)} round-1 prompts in {out}")


# --------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------

def _retryable(e: Exception) -> bool:
    text = str(e)
    return bool(re.search(r"\b(429|5\d\d)\b", text)) or any(
        s in text.lower() for s in ("timed out", "timeout", "temporarily", "connection",
                                    "remote end closed", "urlopen error"))


def call_model(system: str, user: str) -> tuple[str, dict, float]:
    delay = 10.0
    for attempt in range(7):
        start = time.time()
        try:
            with metered() as usage:
                text = azure_openai_complete(system, user, MODEL, TIMEOUT, json_mode=False)
            total = Counter()
            for u in usage:
                total.update({k: v for k, v in u.items() if isinstance(v, int)})
            return text, dict(total), round(time.time() - start, 1)
        except Exception as e:  # noqa: BLE001 - provider errors are RuntimeError/URLError/...
            if attempt == 6 or not _retryable(e):
                raise
            print(f"  retryable error ({e}); sleeping {delay:.0f}s", flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 120)
    raise RuntimeError("unreachable")


def analyze(text: str, rt: Runtime) -> dict:
    """P2g's parse_reply for a manifest-bound document: parse, bind (no pruning), check."""
    try:
        parsed = parse_ce_detailed(extract_ce(text))
        bound = bind_runtime(parsed.pack, parsed.bindings, rt, prune=False)
        verdict = check(bound.pack)
        return {"ok": True, "parsed": parsed, "bound": bound, "verdict": verdict}
    except PARSE_ERRORS as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


class _B:  # the Binding fields explain_refutation reads
    def __init__(self, withdrawn, blocked):
        self.withdrawn, self.blocked = withdrawn, blocked


def followups(part: str, out: Path, frozen: dict, allowed: set | None) -> list[dict]:
    chains: dict = {}
    for job in frozen["jobs"]:
        chains.setdefault(job["id"], []).append(job)
    new = []
    for cid, jobs in chains.items():
        if allowed is not None and cid not in allowed:
            continue
        last = max(jobs, key=lambda j: j["round"])
        if not last.get("output_sha256") or last["round"] >= 3:
            continue
        reply = (out / last["output"]).read_text(encoding="utf-8")
        res = analyze(reply, runtime_for(part, last["case"]))
        base = rj(out / jobs[0]["prompt"])
        if not res["ok"]:
            if last["round"] != 1:
                continue
            rnd, tail = 2, CE_RETRY_PROMPT.format(error=res["error"], text=reply.strip())
        elif REPAIR[part] and res["verdict"].label == "IMPOSSIBLE":
            rnd = 3
            expl = explain_refutation(res["verdict"], _B(res["bound"].withdrawn,
                                                         res["bound"].blocked))
            tail = CE_REPAIR_PROMPT.format(explanation=expl, text=extract_ce(reply).strip())
        else:
            continue
        rel = f"prompts/{cid}__r{rnd}.json"
        wj(out / rel, {"system": base["system"], "user": base["user"] + tail})
        new.append({**{k: last[k] for k in ("id", "case", "variant", "sample")}, "round": rnd,
                    "prompt": rel, "output": f"outputs/{cid}__r{rnd}.txt",
                    "prompt_sha256": sha((out / rel).read_bytes())})
    return new


def run(part: str, out: Path, limit: int | None) -> None:
    path = out / "frozen.json"
    frozen = rj(path)
    order = [j["id"] for j in frozen["jobs"] if j["round"] == 1]
    allowed = set(order[:limit]) if limit else None
    while True:
        pending = [j for j in frozen["jobs"] if not j.get("output_sha256")
                   and (allowed is None or j["id"] in allowed)]
        if not pending:
            new = followups(part, out, frozen, allowed)
            if not new:
                break
            frozen["jobs"] += new
            wj(path, frozen)
            print(f"{len(new)} follow-up prompts frozen "
                  f"({Counter(j['round'] for j in new)})", flush=True)
            continue
        print(f"running {len(pending)} calls", flush=True)
        with ThreadPoolExecutor(WORKERS) as pool:
            futures = {}
            for job in pending:
                prompt_bytes = (out / job["prompt"]).read_bytes()
                if sha(prompt_bytes) != job["prompt_sha256"]:
                    raise ValueError(f"prompt changed: {job['prompt']}")
                prompt = json.loads(prompt_bytes)
                futures[pool.submit(call_model, prompt["system"], prompt["user"])] = job
            for fut in as_completed(futures):
                job = futures[fut]
                try:
                    text, usage, secs = fut.result()
                except Exception as e:  # noqa: BLE001
                    job["call_error"] = f"{type(e).__name__}: {e}"
                    print(f"  FAILED {job['id']} r{job['round']}: {e}", flush=True)
                    text, usage, secs = "", {}, 0.0
                target = out / job["output"]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")
                job.update({"output_sha256": sha(target.read_bytes()), "usage": usage,
                            "seconds": secs})
                wj(path, frozen)
                print(f"  done {job['id']} r{job['round']} ({secs}s, {usage})", flush=True)
    frozen["usage_total"] = usage_total(frozen)
    wj(path, frozen)
    print(json.dumps(frozen["usage_total"]))


def usage_total(frozen: dict) -> dict:
    total = Counter()
    for j in frozen["jobs"]:
        total.update(j.get("usage") or {})
    return {"calls": sum(1 for j in frozen["jobs"] if j.get("output_sha256")), **total}


# --------------------------------------------------------------------------
# score: shared
# --------------------------------------------------------------------------

def final_packs(part: str, out: Path) -> tuple[dict, dict]:
    """P2g's selection: the last valid round; a repair that does not parse or that
    repair_violations rejects keeps the refuted pack."""
    frozen = rj(out / "frozen.json")
    final: dict = {}
    for job in sorted(frozen["jobs"], key=lambda j: j["round"]):
        if sha((out / job["prompt"]).read_bytes()) != job["prompt_sha256"]:
            raise ValueError(f"prompt changed: {job['prompt']}")
        if not job.get("output_sha256"):
            raise ValueError(f"not run: {job['id']} round {job['round']}")
        if sha((out / job["output"]).read_bytes()) != job["output_sha256"]:
            raise ValueError(f"reply changed: {job['output']}")
        reply = (out / job["output"]).read_text(encoding="utf-8")
        res = analyze(reply, runtime_for(part, job["case"]))
        rec = final.setdefault(job["id"], {"id": job["id"], "case": job["case"],
                                           "variant": job["variant"], "sample": job["sample"],
                                           "rounds": [], "ok": False})
        rec["rounds"].append(job["round"])
        if job["round"] == 1:
            rec["valid_first"] = res["ok"]
        if job["round"] == 3:
            if not res["ok"]:
                rec["repair_invalid"] = res["error"]
                continue
            bad = repair_violations(rec["res"]["parsed"], res["parsed"])
            if bad:
                rec["repair_rejected"] = bad
                continue
            rec["repaired"] = True
        if job["round"] == 2 or res["ok"] or not rec.get("ok"):
            rec.update({"ok": res["ok"], "error": res.get("error"), "res": res,
                        "reply": reply, "final_round": job["round"]})
    return final, frozen


def walk_caps(steps, rename=None, found=None) -> set:
    """Capability names used by act steps (protocol or behaviour); rename in place."""
    found = set() if found is None else found
    if isinstance(steps, dict):
        if "cap" in steps and isinstance(steps["cap"], str):
            if rename and steps["cap"] in rename:
                steps["cap"] = rename[steps["cap"]]
            found.add(steps["cap"])
        for v in steps.values():
            walk_caps(v, rename, found)
    elif isinstance(steps, list):
        for v in steps:
            walk_caps(v, rename, found)
    return found


def count_msgs(steps) -> int:
    if isinstance(steps, dict):
        return int("msg" in steps) + sum(count_msgs(v) for v in steps.values())
    if isinstance(steps, list):
        return sum(count_msgs(v) for v in steps)
    return 0


def vdict(v) -> dict:
    return {"verdict": v.label, "reason": v.reason, "refuted": v.refuted,
            "unknown": v.unknown, "protocol": getattr(v, "protocol", ""),
            "protocol_reason": getattr(v, "protocol_reason", ""), "detail": v.detail}


def summarize_rec(rec: dict) -> dict:
    out = {k: rec.get(k) for k in ("id", "case", "variant", "sample", "rounds", "ok",
                                   "valid_first", "final_round", "error", "repaired",
                                   "repair_invalid", "repair_rejected")}
    if rec.get("ok"):
        res = rec["res"]
        out.update({"p2g_bound": vdict(res["verdict"]),
                    "withdrawn": res["bound"].withdrawn, "blocked": res["bound"].blocked})
    return out


# --------------------------------------------------------------------------
# score: a365
# --------------------------------------------------------------------------

def load_run_cases():
    spec = importlib.util.spec_from_file_location("run_cases", A365 / "run_cases.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def map_to_grants(parsed, grants: list[str]) -> tuple[dict, dict, list[str]]:
    """Rename every Tool bound `via G` (G a grant) to G; a second Tool on the same grant
    gets a suffix (a vocabulary_merge note); other Tools are left as they are."""
    pack = deepcopy(parsed.pack)
    rename, taken, notes = {}, {}, []
    for name in list(pack["capabilities"]):
        via = (parsed.bindings.get(name) or {}).get("via")
        if via in grants:
            if via in taken:
                target = f"{via}__merge{len([t for t in rename.values() if t.startswith(via)]) + 1}"
                notes.append(f"vocabulary_merge: `{name}` and `{taken[via]}` both via `{via}`; "
                             f"`{name}` renamed `{target}`")
            else:
                target = via
                taken[via] = name
            rename[name] = target
    caps = {}
    for name, cap in pack["capabilities"].items():
        caps[rename.get(name, name)] = cap
    pack["capabilities"] = caps
    walk_caps(pack["protocol"], rename)
    if pack.get("skills"):
        walk_caps(pack["skills"], rename)
    pack.setdefault("init_true", [])
    return pack, rename, notes


def agrees(actual: dict, expected: dict) -> bool:
    return not actual.get("error") and all(actual.get(k) == v for k, v in expected.items())


def classify(actual: dict, compacted: dict, authored: dict, grants: list[str], notes: list,
             parsed, goal_scope_same: bool) -> str:
    vias = {(parsed.bindings.get(n) or {}).get("via") for n in parsed.pack["capabilities"]}
    if actual.get("error") or notes or any(v not in grants for v in vias):
        return "vocabulary"
    used, declared = walk_caps(compacted["protocol"]), set(compacted["capabilities"])
    a_used = walk_caps(authored["protocol"])
    if a_used - used or (used - a_used) or (declared - a_used):
        return "compaction_error"
    if atoms(compacted["goal"]) != atoms(authored["goal"]):
        return "goal"
    if goal_scope_same:
        return "protocol"
    return "other"


def score_a365(out: Path) -> dict:
    rc = load_run_cases()
    final, frozen = final_packs("a365", out)
    per_sample, disagreements, rows = [], [], []
    per_check: dict = {}
    authored_ok = authored_total = 0
    separation, vocab = [], []
    for d in a365_cases():
        intent, env = rj(d / "intent.json"), rj(d / "environment.json")
        checks = [c for c in rj(d / "checks.json") if c["kind"] == "static"]
        runtime_checks = sum(1 for c in rj(d / "checks.json") if c["kind"] == "runtime")
        for c in checks:
            a = rc.static_check(intent, env, c)
            authored_total += 1
            authored_ok += agrees(a, c["expected"])
            if "role_separation" in c:
                separation.append({"case": d.name, "check": c["id"], "pack": "authored", **a})
        for k in range(SAMPLES["a365"]):
            rec = final[f"{d.name}__s{k}"]
            row = summarize_rec(rec)
            row["runtime_checks_out_of_scope"] = runtime_checks
            outcomes = {}
            if not rec["ok"]:
                for c in checks:
                    outcomes[c["id"]] = {"agree": False, "actual": {"error": rec["error"]},
                                         "cause": "compaction_error"}
                    disagreements.append({"case": d.name, "sample": k, "check": c["id"],
                                          "expected": c["expected"], "actual": "invalid pack",
                                          "cause": "compaction_error",
                                          "note": rec["error"]})
            else:
                parsed = rec["res"]["parsed"]
                pack, rename, notes = map_to_grants(parsed, env["grants"])
                row.update({"rename": rename, "notes": notes,
                            "mapped_ce": render_ce(pack),
                            "goal_atoms": sorted(atoms(pack["goal"])),
                            "authored_goal_atoms": sorted(atoms(intent["goal"])),
                            "protocol_caps": sorted(walk_caps(pack["protocol"])),
                            "authored_caps": sorted(walk_caps(intent["protocol"])),
                            "roles": pack["roles"], "init_true": pack.get("init_true", [])})
                states = set(env.get("states", {}))
                try:
                    unaligned = list(bind_environment(pack, env["grants"], env).unaligned)
                except (ValueError, PackError) as e:
                    unaligned = [f"error: {e}"]
                pre_out = sorted({a for cap in pack["capabilities"].values()
                                  for a in atoms(cap.get("pre", True))} - states)
                row.update({"unaligned": unaligned, "preconditions_outside_vocabulary": pre_out})
                vocab.append({"case": d.name, "sample": k, "unaligned": unaligned,
                              "preconditions_outside_vocabulary": pre_out})
                for c in checks:
                    if "role_separation" in c:
                        act = rc.static_check(pack, env, c)
                        separation.append({"case": d.name, "check": c["id"], "sample": k,
                                           "pack": "compacted", **act})
                        agree = agrees(act, c["expected"])
                        item = {"agree": agree, "actual": act}
                        if not agree:
                            item["cause"] = "compaction_error"
                            disagreements.append({
                                "case": d.name, "sample": k, "check": c["id"],
                                "expected": c["expected"], "actual": act,
                                "cause": "compaction_error",
                                "note": "roles collapsed: " + json.dumps(act["owners"])})
                        outcomes[c["id"]] = item
                        continue
                    try:
                        act = rc.static_check(pack, env, c)
                        actual = {"verdict": act["verdict"], "reason": act["reason"],
                                  "protocol": act.get("protocol", ""),
                                  "protocol_reason": act.get("protocol_reason", ""),
                                  "unavailable": act["unavailable_capabilities"],
                                  "contracts_applied": act["contracts_applied"]}
                    except (ValueError, PackError) as e:
                        actual = {"error": f"{type(e).__name__}: {e}"}
                    agree = agrees(actual, c["expected"])
                    item = {"agree": agree, "actual": actual}
                    if not agree:
                        same = False
                        if not actual.get("error"):
                            g = {**c, "scope": "goal"}
                            try:
                                ca, aa = rc.static_check(pack, env, g), rc.static_check(intent, env, g)
                                same = (ca["verdict"], ca["reason"]) == (aa["verdict"], aa["reason"])
                            except (ValueError, PackError):
                                same = False
                        cause = classify(actual, pack, intent, env["grants"], notes, parsed, same)
                        item["cause"] = cause
                        disagreements.append({
                            "case": d.name, "sample": k, "check": c["id"],
                            "expected": c["expected"],
                            "actual": actual.get("error") or
                            f"{actual['verdict']} {actual['reason']}",
                            "cause": cause, "rename": rename, "notes": notes,
                            "goal_atoms": row["goal_atoms"],
                            "protocol_caps": row["protocol_caps"],
                            "authored_caps": row["authored_caps"]})
                    outcomes[c["id"]] = item
            row["checks"] = outcomes
            row["agreed"] = sum(o["agree"] for o in outcomes.values())
            row["total"] = len(outcomes)
            for cid, o in outcomes.items():
                pc = per_check.setdefault(cid, [0, 0])
                pc[0] += o["agree"]
                pc[1] += 1
            per_sample.append({"case": d.name, "sample": k, "agreed": row["agreed"],
                               "total": row["total"], "valid_first": rec.get("valid_first"),
                               "final_round": rec.get("final_round")})
            rows.append(row)
    # cross-sample agreement
    by_case: dict = {}
    for r in rows:
        by_case.setdefault(r["case"], []).append(r)
    outcome_same = struct_same = 0
    for case, rs in by_case.items():
        vec = [json.dumps({c: (o["actual"].get("verdict"), o["actual"].get("reason"))
                           for c, o in r["checks"].items()}, sort_keys=True) for r in rs]
        outcome_same += len(set(vec)) == 1
        st = [json.dumps([r.get("protocol_caps"), r.get("goal_atoms")]) for r in rs]
        struct_same += len(set(st)) == 1
    agreed = sum(r["agreed"] for r in rows)
    total = sum(r["total"] for r in rows)
    summary = {
        "part": "a365", "model": MODEL, "samples": SAMPLES["a365"],
        "authored_static_checks_matching": f"{authored_ok}/{authored_total}",
        "agreed": agreed, "total": total,
        "valid_first": sum(bool(r.get("valid_first")) for r in rows),
        "valid_final": sum(bool(r.get("ok")) for r in rows), "packs": len(rows),
        "per_sample": per_sample,
        "per_check": {k: f"{v[0]}/{v[1]}" for k, v in per_check.items()},
        "per_case": {c: f"{sum(r['agreed'] for r in rs)}/{sum(r['total'] for r in rs)}"
                     for c, rs in by_case.items()},
        "causes": dict(Counter(x["cause"] for x in disagreements)),
        "cases_all_samples_same_outcomes": f"{outcome_same}/{len(by_case)}",
        "cases_all_samples_same_structure": f"{struct_same}/{len(by_case)}",
        "blind_vocab": BLIND,
        "packs_with_unaligned": sum(bool(v["unaligned"]) for v in vocab),
        "packs_with_preconditions_outside_vocabulary":
            sum(bool(v["preconditions_outside_vocabulary"]) for v in vocab),
        "unaligned_names": dict(Counter(n for v in vocab for n in v["unaligned"])),
        "separation_of_duty": separation,
        "runtime_checks_out_of_scope": sum(r["runtime_checks_out_of_scope"] for r in rows)
        // SAMPLES["a365"],
        "usage": usage_total(frozen)}
    wj(out / "results.json", rows)
    wj(out / "disagreements.json", disagreements)
    wj(out / "summary.json", summary)
    return summary


# --------------------------------------------------------------------------
# score: maf
# --------------------------------------------------------------------------

def copy_project(dst: Path) -> Path:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(FINANCE, dst, ignore=COPY_IGNORE)
    vendored = dst / "src" / "finance-agent" / "skillc"
    if vendored.exists():
        shutil.rmtree(vendored)
    return dst


def gate_entries(project: Path, pack_name: str) -> dict:
    from skillc.gate import GateError, gate
    out = {}
    for cfg in CONFIGS:
        try:
            report = gate(project, declared=cfg)
        except GateError as e:
            out[cfg] = {"verdict": "GATE_ERROR", "reason": str(e)}
            continue
        packs = [e for e in report.packs if e.name == pack_name]
        e = packs[0] if packs else None
        out[cfg] = {"report_verdict": report.verdict,
                    "verdict": e.verdict if e else "NO_PACK",
                    "reason": e.reason if e else "",
                    "fixes": e.fixes if e else [], "assumptions": e.assumptions if e else [],
                    "via": e.detail.get("via") if e else None,
                    "withdrawn": e.detail.get("withdrawn") if e else None,
                    "blocked": e.detail.get("blocked") if e else None,
                    "pruned": e.detail.get("pruned") if e else None,
                    "pure_verdict": e.detail.get("pure_verdict") if e else None,
                    "bound_protocol": e.detail.get("bound_protocol") if e else None,
                    "skills": {s.name: s.verdict for s in report.skills},
                    "topology_note": report.topology_note}
    return out


def test_expectation(cfg: str, g: dict, email: bool) -> dict:
    """The expectations tests/test_gate.py encodes for the authored packs."""
    if email:
        ok = (g["verdict"] == "IMPOSSIBLE")
        return {"expected": "pack IMPOSSIBLE naming `email_account` and `email_report`",
                "label_matches": ok,
                "names_email_account": "`email_account`" in g.get("reason", ""),
                "names_email_tool": "email" in g.get("reason", "").lower()}
    exp = {"azure.yaml": "pack ACHIEVABLE, via [code_interpreter, write], nothing withdrawn "
                         "or pruned; gate ACHIEVABLE",
           "azure.search.yaml": "gate ACHIEVABLE",
           "azure.isolated.yaml": "gate ACHIEVABLE; no pack assumptions"}[cfg]
    ok = g["verdict"] == "ACHIEVABLE" and g.get("report_verdict") == "ACHIEVABLE"
    detail = {}
    if cfg == "azure.yaml":
        detail = {"via_matches": g.get("via") == ["code_interpreter", "write"],
                  "nothing_withdrawn_or_pruned": not g.get("withdrawn") and not g.get("pruned")}
    if cfg == "azure.isolated.yaml":
        detail = {"no_assumptions": g.get("assumptions") == []}
    return {"expected": exp, "label_matches": ok, **detail}


def _norm(name) -> str:
    return re.sub(r"[^a-z]", "", str(name or "").lower())


def structure(pack: dict, bindings: dict) -> dict:
    caps = pack["capabilities"]
    adders: dict = {}
    for name, cap in caps.items():
        for a in cap.get("add", []):
            adders.setdefault(a, []).append(name)
    approving = {n: caps[n].get("owner") for n in caps if "approv" in n.lower()
                 or any("approv" in a.lower() for a in caps[n].get("add", []))}
    wra = next((n for n in caps if n == "write_revenue_analysis"), None) or next(
        (n for n in caps if "revenue_analysis" in n), None)
    gated = None
    if wra:
        pre = atoms(caps[wra].get("pre", True))
        gated = any(a in adders and all(_norm(caps[t].get("owner")) == "taxverifier"
                                        for t in adders[a]) for a in pre)
    return {"roles": sorted(pack["roles"]),
            "roles_normalized": sorted(_norm(r) for r in pack["roles"]),
            "tool_count": len(caps), "tools": sorted(caps),
            "message_count": count_msgs(pack["protocol"]),
            "via": sorted({b.get("via") for b in bindings.values() if b.get("via")}),
            "goal": sorted(atoms(pack["goal"])),
            "revenue_analysis_tool": wra,
            "approval_gates_revenue_analysis": gated,
            "requires_approved_literal": bool(wra and "approved" in atoms(caps[wra].get("pre", True))),
            "approving_tool_owners": approving,
            "has_choice": '"choice"' in json.dumps(pack["protocol"]),
            "behaviours": sorted((pack.get("skills") or {}).keys())}


def score_maf(out: Path) -> dict:
    final, frozen = final_packs("maf", out)
    authored = parse_ce_detailed((FINANCE / "protocol/quarterly_finance_report.ce")
                                 .read_text(encoding="utf-8"))
    email_authored = parse_ce_detailed((FINANCE / "protocol-variants/"
                                        "quarterly_finance_report.email.ce")
                                       .read_text(encoding="utf-8"))
    ref = gate_entries(copy_project(out / "project_authored"), "quarterly_finance_report.ce")
    ep = copy_project(out / "project_authored_email")
    shutil.copy(ep / "protocol-variants" / "quarterly_finance_report.email.ce", ep / "protocol")
    ref_email = gate_entries(ep, "quarterly_finance_report.email.ce")["azure.yaml"]
    rows = []
    for rid, rec in sorted(final.items()):
        email = rec["variant"] == "email"
        k = rec["sample"]
        row = summarize_rec(rec)
        name = "quarterly_finance_report.email.ce" if email else "quarterly_finance_report.ce"
        proj = copy_project(out / (f"project_email_s{k}" if email else f"project_s{k}"))
        shutil.rmtree(proj / "protocol-variants", ignore_errors=True)
        for f in (proj / "protocol").glob("*.ce"):
            f.unlink()
        try:
            ce_text = extract_ce(rec["reply"])
        except CEError as e:
            ce_text = f"# no CE document: {e}\n"
        (proj / "protocol" / name).write_text(ce_text, encoding="utf-8")
        g = gate_entries(proj, name)
        if email:
            g = {"azure.yaml": g["azure.yaml"]}
        row["gate"] = g
        row["vs_authored"] = {cfg: {"label_same": v["verdict"] == (ref_email if email
                                                                   else ref[cfg])["verdict"]}
                              for cfg, v in g.items()}
        row["vs_tests"] = {cfg: test_expectation(cfg, v, email) for cfg, v in g.items()}
        if rec["ok"]:
            parsed = rec["res"]["parsed"]
            row["structure"] = structure(parsed.pack, parsed.bindings)
            row["ce"] = ce_text
        rows.append(row)
    false_imp = [{"sample": r["sample"], "config": cfg, "reason": v["reason"]}
                 for r in rows if r["variant"] == "main"
                 for cfg, v in r["gate"].items() if v["verdict"] == "IMPOSSIBLE"]
    summary = {
        "part": "maf", "model": MODEL, "samples": SAMPLES["maf"],
        "false_impossible_on_correct_configs": false_imp,
        "authored_reference": {cfg: {"verdict": v["verdict"], "reason": v["reason"]}
                               for cfg, v in ref.items()},
        "authored_email_reference": {"verdict": ref_email["verdict"],
                                     "reason": ref_email["reason"]},
        "authored_structure": structure(authored.pack, authored.bindings),
        "authored_email_structure": structure(email_authored.pack, email_authored.bindings),
        "table": [{"variant": r["variant"], "sample": r["sample"],
                   **{cfg: f"{v['verdict']}" for cfg, v in r["gate"].items()},
                   "agrees_authored": all(x["label_same"] for x in r["vs_authored"].values()),
                   "meets_tests": all(x["label_matches"] for x in r["vs_tests"].values()),
                   "rounds": r["rounds"], "repaired": r.get("repaired"),
                   "repair_rejected": r.get("repair_rejected")} for r in rows],
        "usage": usage_total(frozen)}
    wj(out / "results.json", rows)
    wj(out / "summary.json", summary)
    return summary


# --------------------------------------------------------------------------
# score: scout
# --------------------------------------------------------------------------

def rubric() -> dict:
    text = PLAN.read_text(encoding="utf-8")
    out = {}
    for k in range(1, 6):
        m = re.search(rf"^\s*F{k} (.+?)[;.]?\s*$", text, re.M)
        if not m:
            raise ValueError(f"F{k} not found in {PLAN}")
        out[f"F{k}"] = m.group(1).rstrip(";").rstrip(".")
    return out


JUDGE_README = """# Fidelity judge for the Scout arm of experiment H

Each file in `items/` is one SKILL.md and the pack gpt-5.4 compacted from it against the
`scout-desktop` runtime, written in SkillC Controlled English (`ce`, with each Tool's `via`
binding). The 20 items were chosen by sha256("scout-judge:" + case) order. Nothing in an
item says what the checker decided; do not look it up.

For every item, read `source_text` (the document) and `ce` (the pack), and answer each
rubric question with `yes`, `no` or `unclear`, plus one line saying why. The rubric is the
one pre-registered in `runs/20261015_review_response/PLAN.md` (experiment R), copied into
every item under `rubric`:

{rubric}

`runtime` gives the runtime's name, description and tools (needed for F5).

Write your scores to `scores.json` (or `scores_<judge>.json` for a second judge) as a JSON
list, one object per item:

```json
{{"case": "c001", "F1": "yes", "F2": "no", "F3": "yes", "F4": "unclear", "F5": "yes",
  "F1_reason": "...", "F2_reason": "...", "F3_reason": "...", "F4_reason": "...",
  "F5_reason": "..."}}
```

Score from the two texts only. Do not run anything, and do not open files outside this
folder.
"""


def score_scout(out: Path) -> dict:
    final, frozen = final_packs("scout", out)
    rt = load_runtime("scout-desktop")
    rows = []
    for rid, rec in sorted(final.items()):
        row = summarize_rec(rec)
        rows.append(row)
    ok = [r for r in rows if r["ok"]]
    verdicts = Counter(r["p2g_bound"]["verdict"] for r in ok)
    reasons = Counter(f"{r['p2g_bound']['verdict']} {r['p2g_bound']['reason']}" for r in ok)
    withdrawn = Counter(v for r in ok for v in r["withdrawn"].values())
    blocked = Counter(x for r in ok for xs in r["blocked"].values() for x in xs)
    summary = {
        "part": "scout", "model": MODEL, "runtime": rt.name, "documents": len(rows),
        "valid_first": sum(bool(r["valid_first"]) for r in rows),
        "valid_final": len(ok), "repaired": sum(bool(r.get("repaired")) for r in rows),
        "repair_rejected": sum(bool(r.get("repair_rejected")) for r in rows),
        "repair_invalid": sum(bool(r.get("repair_invalid")) for r in rows),
        "verdicts": dict(verdicts), "unknown": verdicts.get("UNKNOWN", 0),
        "reasons": dict(reasons.most_common()),
        "withdrawn_via": dict(withdrawn.most_common()),
        "blocked_needs": dict(blocked.most_common()),
        "protocol_rejected": sum(r["p2g_bound"]["protocol"] == "REJECTED" for r in ok),
        "usage": usage_total(frozen)}
    wj(out / "results.json", rows)
    wj(out / "summary.json", summary)
    # judge items
    rub = rubric()
    picked = sorted((c["case"] for c in scout_cases()),
                    key=lambda c: hashlib.sha256(f"scout-judge:{c}".encode()).hexdigest())[:20]
    jd = out / "judge"
    for case in picked:
        rec = final[f"{case}__s0"]
        if rec["ok"]:
            p = rec["res"]["parsed"]
            ce = render_ce(p.pack, p.bindings, p.live_goal)
        else:
            ce = f"(no valid pack: {rec['error']})"
        wj(jd / "items" / f"{case}.json", {
            "case": case,
            "source_text": (SET2 / "cases" / f"{case}.md").read_text(encoding="utf-8"),
            "ce": ce,
            "runtime": {"name": rt.name, "description": rt.description, "tools": rt.tools},
            "rubric": rub})
    (jd / "README.md").write_text(JUDGE_README.format(
        rubric="\n".join(f"- {k}: {v}" for k, v in rub.items())), encoding="utf-8")
    wj(jd / "picked.json", picked)
    return summary


# --------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("part", choices=["a365", "maf", "scout"])
    ap.add_argument("stage", choices=["prepare", "run", "score"])
    ap.add_argument("--out", type=Path)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--blind-vocab", action="store_true",
                    help="a365 only (Addendum A): the manifest names no state")
    args = ap.parse_args(argv)
    global BLIND
    BLIND = args.blind_vocab
    if BLIND and args.part != "a365":
        ap.error("--blind-vocab applies to a365 only")
    out = args.out or OUT / (args.part + ("_blind" if BLIND else ""))
    if args.stage != "prepare" and (out / "frozen.json").exists():
        prepared = rj(out / "frozen.json").get("blind_vocab", False)
        if prepared != BLIND:
            ap.error(f"{out} was prepared with blind_vocab={prepared}")
    if args.stage == "prepare":
        prepare(args.part, out)
    elif args.stage == "run":
        run(args.part, out, args.limit)
    else:
        summary = {"a365": score_a365, "maf": score_maf, "scout": score_scout}[args.part](out)
        print(json.dumps(summary, indent=1)[:6000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

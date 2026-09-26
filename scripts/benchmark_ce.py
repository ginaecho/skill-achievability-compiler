"""A/B benchmark: JSON compaction (original) vs Controlled-English compaction.

Both arms receive the same source text and the same modelling rules; they
differ only in the output representation the model writes:

  json  -- frontend.llm.SYSTEM: the model writes the pack as JSON
  ce    -- frontend.llm.CE_SYSTEM: the model writes CE, parsed deterministically

The model call itself is outside this script.  `prepare` freezes one prompt
file ({"system", "user"}) per (case, arm, sample); any executor writes the
model's raw reply to the matching output path; `retry` freezes one located-
error retry prompt per failed output (the same budget for both arms); `score`
parses, gates and checks every reply deterministically and writes
results.json and metrics.json.

Two case sets:

  real      -- a stratified sample of pinned public SKILL.md files
               (benchmark/ce_sources), compacted as in `skillc compile --llm
               --llm-runtime developer`.  No ground-truth labels exist; the
               metrics are validity, structural defects, verdicts, output
               size, cross-arm agreement and sample-to-sample stability.
  labelled  -- the 32 contract-labelled scenarios of the compaction
               benchmark (runs/20260921_114226Z_compaction_comparison),
               scored exactly as scripts/benchmark_compaction.py scores them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from scripts.benchmark_compaction import SYSTEM_NOTE, VARIANTS, assess, score  # noqa: E402
from skillc import check  # noqa: E402
from skillc.formula import atoms  # noqa: E402
from skillc.frontend.ce import CEError, compile_ce, extract_ce, render_ce, parse_ce, canonical_pack  # noqa: E402
from skillc.frontend.llm import (CE_RETRY_PROMPT, RUNTIME_ABILITIES_NOTE,  # noqa: E402
                                 RUNTIME_ABILITY_PROFILES, SYSTEM,
                                 _extract_json_object, ce_messages, CE_SYSTEM)
from skillc.frontend.markdown import compile_markdown  # noqa: E402
from skillc.pack import PackError, validate_pack  # noqa: E402
from skillc.profiles import load_profile  # noqa: E402
from skillc.tokens import estimate_tokens  # noqa: E402

ARMS = ("json", "ce")
SOURCES = ROOT / "benchmark" / "ce_sources"
LABELLED_RUN = ROOT / "runs" / "20260921_114226Z_compaction_comparison"
RUNTIME = "developer"
JSON_RETRY = ("\n\nYour previous output:\n{text}\n\nSchema validation failed: "
              "{error}. Return a valid pack; do not weaken the task or change "
              "the contract.")


def sha(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


# --------------------------------------------------------------------------
# Case selection and prompts
# --------------------------------------------------------------------------

def select_real(n: int) -> list[dict]:
    """Deterministic stratified sample: round-robin over repositories, each
    repository's skills in sha256(id) order."""
    sources = json.loads((SOURCES / "sources.json").read_text())
    by_repo: dict[str, list[dict]] = {}
    for s in sources:
        by_repo.setdefault(s["repo_url"], []).append(s)
    for items in by_repo.values():
        items.sort(key=lambda s: sha("ce-ab:" + s["id"]))
    picked: list[dict] = []
    while len(picked) < n and any(by_repo.values()):
        for repo in sorted(by_repo):
            if by_repo[repo] and len(picked) < n:
                picked.append(by_repo[repo].pop(0))
    return picked


def real_prompt(arm: str, text: str) -> dict:
    abilities = RUNTIME_ABILITY_PROFILES[RUNTIME]
    if arm == "json":             # exactly frontend.llm.compact()
        system = SYSTEM + RUNTIME_ABILITIES_NOTE.format(
            abilities="; ".join(abilities))
        user = f"Natural-language skill:\n```\n{text}\n```\nJSON pack:"
        return {"system": system, "user": user}
    system, user = ce_messages(text, abilities)   # exactly compact_ce()
    return {"system": system, "user": user}


CE_SYSTEM_NOTE = SYSTEM_NOTE.replace("identifiers, goal,", "identifiers (in backticks), goal,")


def labelled_prompt(arm: str, text: str) -> dict:
    # exactly scripts/benchmark_compaction.py's messages for the JSON arm
    if arm == "json":
        return {"system": SYSTEM + SYSTEM_NOTE, "user": text}
    return {"system": CE_SYSTEM + CE_SYSTEM_NOTE, "user": text}


def prepare(out: Path, n_real: int, n_stable: int, samples: int) -> None:
    out.mkdir(parents=True, exist_ok=False)
    cases = []
    for i, s in enumerate(select_real(n_real)):
        if sha((SOURCES / s["id"] / "SKILL.md").read_bytes()) != s["sha256"]:
            raise ValueError(f"source integrity failure: {s['id']}")
        cases.append({"id": s["id"], "set": "real", "repo": s["repo_url"],
                      "domain": s["domain"], "source_sha256": s["sha256"],
                      "samples": samples if i < n_stable else 1})
    frozen_labelled = json.loads((LABELLED_RUN / "frozen.json").read_text())
    for sc in frozen_labelled["scenarios"]:
        cases.append({"id": sc["id"], "set": "labelled", "source": sc["source"],
                      "profile": sc["profile"], "category": sc["category"],
                      "truth": sc["truth"], "samples": 1})
    jobs = []
    for case in cases:
        if case["set"] == "real":
            text = (SOURCES / case["id"] / "SKILL.md").read_text(encoding="utf-8")  # as the CLI
        else:
            d = LABELLED_RUN / case["id"]
            raw = (d / "input.md").read_bytes()
            text = (d / "input.md").read_text(encoding="utf-8")   # as the original harness
            if sha(raw) != next(
                    s["input_sha256"] for s in frozen_labelled["scenarios"]
                    if s["id"] == case["id"]):
                raise ValueError(f"labelled input changed: {case['id']}")
            for f in ("contract.json", "oracle.json"):
                target = out / "labelled" / case["id"] / f
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((d / f).read_bytes())
        for arm in ARMS:
            for k in range(case["samples"]):
                prompt = (real_prompt if case["set"] == "real"
                          else labelled_prompt)(arm, text)
                rel = f"prompts/{arm}/{case['id']}__s{k}.json"
                write_json(out / rel, prompt)
                jobs.append({"case": case["id"], "arm": arm, "sample": k,
                             "round": 1, "prompt": rel,
                             "output": f"outputs/{arm}/{case['id']}__s{k}.txt",
                             "prompt_sha256": sha((out / rel).read_bytes())})
    impl = {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in
            [ROOT / "src/skillc/frontend/ce.py", ROOT / "src/skillc/frontend/llm.py",
             ROOT / "src/skillc/checker.py", ROOT / "src/skillc/pack.py",
             ROOT / "scripts/benchmark_ce.py", ROOT / "scripts/benchmark_compaction.py"]}
    write_json(out / "frozen.json", {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "runtime_abilities": RUNTIME, "cases": cases, "jobs": jobs,
        "implementation_sha256": impl,
    })
    print(f"prepared {len(cases)} cases, {len(jobs)} round-1 jobs in {out}")


# --------------------------------------------------------------------------
# Parsing a reply
# --------------------------------------------------------------------------

def parse_reply(arm: str, text: str) -> dict:
    try:
        if arm == "json":
            pack = _extract_json_object(text)
            validate_pack(pack)
        else:
            pack = compile_ce(extract_ce(text))
        return {"ok": True, "pack": pack}
    except (PackError, CEError, ValueError, KeyError, TypeError) as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def retry(out: Path) -> None:
    frozen = json.loads((out / "frozen.json").read_text())
    new = []
    for job in frozen["jobs"]:
        if job["round"] != 1:
            continue
        path = out / job["output"]
        if not path.exists():
            raise ValueError(f"missing round-1 output: {job['output']}")
        reply = path.read_text(encoding="utf-8")
        parsed = parse_reply(job["arm"], reply)
        if parsed["ok"]:
            continue
        prompt = json.loads((out / job["prompt"]).read_text())
        if job["arm"] == "json":
            user = prompt["user"] + JSON_RETRY.format(text=reply.strip(),
                                                      error=parsed["error"])
        else:
            user = prompt["user"] + CE_RETRY_PROMPT.format(error=parsed["error"],
                                                           text=reply.strip())
        rel = job["prompt"].replace(".json", "__r2.json")
        write_json(out / rel, {"system": prompt["system"], "user": user})
        new.append({**job, "round": 2, "prompt": rel,
                    "output": job["output"].replace(".txt", "__r2.txt"),
                    "prompt_sha256": sha((out / rel).read_bytes())})
    frozen["jobs"] = [j for j in frozen["jobs"] if j["round"] == 1] + new
    write_json(out / "frozen.json", frozen)
    print(f"{len(new)} retry jobs")


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------

def _possible(f, made: set) -> bool:
    """Could `f` hold when only the predicates in `made` can be true?
    Over-approximate: negations and comparisons are assumed satisfiable."""
    if f is True or f is False:
        return f
    if isinstance(f, str):
        return f in made
    if "and" in f:
        return all(_possible(x, made) for x in f["and"])
    if "or" in f:
        return any(_possible(x, made) for x in f["or"])
    return True


def premature_checkpoints(pack: dict) -> int:
    """Goal checkpoints reached, on some path, at a point where the goal
    cannot hold yet: a positive goal atom has been neither initially true
    nor added by any declared act earlier on that path."""
    caps = pack["capabilities"]
    count = 0

    def walk(steps, made):
        nonlocal count
        made = set(made)
        for s in steps:
            (kind, body), = s.items()
            if kind == "act" and body["cap"] in caps:
                made |= set(caps[body["cap"]].get("add", []))
            elif kind == "goal":
                if not _possible(body, made):
                    count += 1
            elif kind == "choice":
                for br in body["branches"].values():
                    walk(br, made)
            elif kind == "rec":
                walk(body["body"], made)
        return made

    walk(pack["protocol"], set(pack.get("init_true", [])))
    return count


def token_proxy(text: str) -> int:
    return len(re.findall(r"[A-Za-z]+|\d+|[^\sA-Za-z\d]", text))


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


def load_attempts(out: Path, frozen: dict) -> dict:
    """(case, arm, sample) -> final attempt record."""
    rec: dict = {}
    for job in sorted(frozen["jobs"], key=lambda j: j["round"]):
        path = out / job["output"]
        if not path.exists():
            raise ValueError(f"missing output: {job['output']}")
        if sha((out / job["prompt"]).read_bytes()) != job["prompt_sha256"]:
            raise ValueError(f"prompt changed: {job['prompt']}")
        reply = path.read_text(encoding="utf-8")
        parsed = parse_reply(job["arm"], reply)
        key = (job["case"], job["arm"], job["sample"])
        r = rec.setdefault(key, {"rounds": 0, "output_chars": 0,
                                 "output_tokens_est": 0, "output_token_proxy": 0})
        r["rounds"] = job["round"]
        r["output_chars"] += len(reply)
        r["output_tokens_est"] += estimate_tokens(reply)
        r["output_token_proxy"] += token_proxy(reply)
        if job["round"] == 1:
            r["valid_first"] = parsed["ok"]
            r["first_chars"] = len(reply)
            r["first_tokens_est"] = estimate_tokens(reply)
            r["first_token_proxy"] = token_proxy(reply)
        r["valid"] = parsed["ok"]
        r["error"] = parsed.get("error")
        r["pack"] = parsed.get("pack")
    return rec


def summarize_arm(rows: list[dict]) -> dict:
    n = len(rows)
    valid = [r for r in rows if r["valid"]]
    labels = Counter(r["verdict"] for r in valid)
    reasons = Counter(r["reason"] for r in valid)
    first = sum(r["valid_first"] for r in rows)
    fin = len(valid)
    return {
        "n": n,
        "valid_first_attempt": first, "valid_first_rate": round(first / n, 4),
        "valid_first_ci95": wilson(first, n),
        "valid_final": fin, "valid_final_rate": round(fin / n, 4),
        "valid_final_ci95": wilson(fin, n),
        "verdicts": dict(labels), "reasons": dict(reasons),
        "impossible_rate_of_valid": round(labels["IMPOSSIBLE"] / fin, 4) if fin else None,
        "impossible_ci95": wilson(labels["IMPOSSIBLE"], fin),
        "premature_checkpoint_packs": sum(r["premature_checkpoints"] > 0 for r in valid),
        "checkpoint_packs": sum(r["checkpoints"] > 0 for r in valid),
        "trivial_goal_packs": sum(r["goal"] is True for r in valid),
        "median_first_output_chars": _median([r["first_chars"] for r in rows]),
        "median_first_output_tokens_est": _median([r["first_tokens_est"] for r in rows]),
        "median_first_output_token_proxy": _median([r["first_token_proxy"] for r in rows]),
        "total_output_tokens_est": sum(r["output_tokens_est"] for r in rows),
        "total_output_token_proxy": sum(r["output_token_proxy"] for r in rows),
        "median_caps": _median([r["n_caps"] for r in valid]),
        "median_steps": _median([r["n_steps"] for r in valid]),
        "median_goal_atoms": _median([r["n_goal_atoms"] for r in valid]),
    }


def _median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2


def _steps(steps) -> int:
    n = 0
    for s in steps:
        (kind, body), = s.items()
        n += 1
        if kind == "choice":
            n += sum(_steps(b) for b in body["branches"].values())
        elif kind == "rec":
            n += _steps(body["body"])
    return n


def describe(pack: dict) -> dict:
    v = check(pack)
    g = check(pack, scope="goal")
    return {"verdict": v.label, "reason": v.reason, "goal_only_verdict": g.label,
            "goal": pack["goal"], "n_caps": len(pack["capabilities"]),
            "n_steps": _steps(pack["protocol"]),
            "n_goal_atoms": len(atoms(pack["goal"])),
            "checkpoints": sum(1 for _ in re.finditer(r'"goal":', json.dumps(pack["protocol"]))),
            "premature_checkpoints": premature_checkpoints(pack),
            "cap_names": sorted(pack["capabilities"])}


def score_all(out: Path) -> None:
    frozen = json.loads((out / "frozen.json").read_text())
    attempts = load_attempts(out, frozen)
    cases = {c["id"]: c for c in frozen["cases"]}
    rows = []
    for (cid, arm, k), r in sorted(attempts.items()):
        case = cases[cid]
        row = {"case": cid, "set": case["set"], "arm": arm, "sample": k,
               **{x: r[x] for x in ("rounds", "valid_first", "valid", "error",
                                    "first_chars", "first_tokens_est",
                                    "first_token_proxy", "output_chars",
                                    "output_tokens_est", "output_token_proxy")}}
        if r["valid"]:
            row.update(describe(r["pack"]))
            # representational closure: every pack either arm produced is
            # expressible in CE and survives the round-trip unchanged
            try:
                row["ce_round_trip"] = parse_ce(render_ce(r["pack"])) == canonical_pack(r["pack"])
            except CEError:
                row["ce_round_trip"] = False
            write_json(out / "packs" / arm / f"{cid}__s{k}.json", r["pack"])
        rows.append(row)
    write_json(out / "results.json", rows)

    metrics: dict = {"created_utc": datetime.now(timezone.utc).isoformat()}
    # ---- real set --------------------------------------------------------
    real = [r for r in rows if r["set"] == "real"]
    s0 = {(r["case"], r["arm"]): r for r in real if r["sample"] == 0}
    ids = sorted({r["case"] for r in real})
    metrics["real"] = {arm: summarize_arm([s0[(i, arm)] for i in ids]) for arm in ARMS}
    pairs = [(s0[(i, "json")], s0[(i, "ce")]) for i in ids]
    b = sum(a["valid_first"] and not c["valid_first"] for a, c in pairs)
    c_ = sum(c["valid_first"] and not a["valid_first"] for a, c in pairs)
    both = [(a, c) for a, c in pairs if a["valid"] and c["valid"]]
    imp_b = sum(a["verdict"] == "IMPOSSIBLE" and c["verdict"] != "IMPOSSIBLE" for a, c in both)
    imp_c = sum(c["verdict"] == "IMPOSSIBLE" and a["verdict"] != "IMPOSSIBLE" for a, c in both)
    metrics["real_paired"] = {
        "cases": len(ids),
        "valid_first_json_only": b, "valid_first_ce_only": c_,
        "valid_first_mcnemar_p": mcnemar_exact(b, c_),
        "both_valid": len(both),
        "verdict_agreement": sum(a["verdict"] == c["verdict"] for a, c in both),
        "impossible_json_only": imp_b, "impossible_ce_only": imp_c,
        "impossible_mcnemar_p": mcnemar_exact(imp_b, imp_c),
        "mean_cap_name_jaccard": round(sum(jaccard(set(a["cap_names"]), set(c["cap_names"]))
                                           for a, c in both) / len(both), 4) if both else None,
        "json_packs_expressible_in_ce": sum(bool(a.get("ce_round_trip")) for a, _ in both),
        "first_output_token_proxy_ratio_ce_over_json": round(
            sum(c["first_token_proxy"] for _, c in pairs)
            / sum(a["first_token_proxy"] for a, _ in pairs), 4),
        "first_output_chars_ratio_ce_over_json": round(
            sum(c["first_chars"] for _, c in pairs)
            / sum(a["first_chars"] for a, _ in pairs), 4),
    }
    by_domain: dict = {}
    for i in ids:
        dom = cases[i]["domain"]
        for arm in ARMS:
            r = s0[(i, arm)]
            d = by_domain.setdefault(dom, {}).setdefault(arm, Counter())
            d["n"] += 1
            d["valid"] += r["valid"]
            d["impossible"] += r.get("verdict") == "IMPOSSIBLE"
    metrics["real_by_domain"] = {k: {a: dict(v) for a, v in d.items()}
                                 for k, d in sorted(by_domain.items())}
    # ---- stability -------------------------------------------------------
    stab: dict = {}
    multi = sorted({r["case"] for r in real if r["sample"] > 0})
    for arm in ARMS:
        same_label = same_goal_atoms = same_caps = complete = 0
        jac = []
        for i in multi:
            rs = [r for r in real if r["case"] == i and r["arm"] == arm]
            if not all(r["valid"] for r in rs):
                continue
            complete += 1
            same_label += len({r["verdict"] for r in rs}) == 1
            same_goal_atoms += len({json.dumps(sorted(atoms(r["goal"]))) for r in rs}) == 1
            same_caps += len({tuple(r["cap_names"]) for r in rs}) == 1
            for x in range(len(rs)):
                for y in range(x + 1, len(rs)):
                    jac.append(jaccard(set(rs[x]["cap_names"]), set(rs[y]["cap_names"])))
        stab[arm] = {"cases": len(multi), "all_samples_valid": complete,
                     "same_verdict_all_samples": same_label,
                     "same_goal_atoms_all_samples": same_goal_atoms,
                     "same_capability_names_all_samples": same_caps,
                     "mean_pairwise_cap_jaccard": round(sum(jac) / len(jac), 4) if jac else None}
    metrics["stability"] = stab
    # ---- labelled set ----------------------------------------------------
    lab_rows = {arm: [] for arm in ARMS}
    lab_arm = {arm: [] for arm in ARMS}
    for r in rows:
        if r["set"] != "labelled":
            continue
        case = cases[r["case"]]
        lab_arm[r["arm"]].append(r)
        scenario = {"id": case["id"], "source": case["source"], "profile": case["profile"],
                    "category": case["category"], "truth": case["truth"]}
        contract = json.loads((out / "labelled" / case["id"] / "contract.json").read_text())
        if r["valid"]:
            pack = json.loads((out / "packs" / r["arm"] / f"{case['id']}__s0.json").read_text())
            lab_rows[r["arm"]].extend(assess(pack, contract, scenario, r["arm"], r["arm"]))
        else:
            for variant in VARIANTS:
                lab_rows[r["arm"]].append({**scenario, "mode": r["arm"], "variant": variant,
                                           "predicted": "UNKNOWN", "reason": "COMPACTION_ERROR",
                                           "error": r["error"]})
    write_json(out / "labelled_results.json", lab_rows)
    metrics["labelled"] = {}
    for arm in ARMS:
        metrics["labelled"][arm] = {
            "compaction": summarize_arm(lab_arm[arm]),
            **{variant: score([x for x in lab_rows[arm] if x["variant"] == variant])
               for variant in VARIANTS},
            "goal_exact_match": sum(x.get("goal_exact_match", False) for x in lab_rows[arm]
                                    if x["variant"] == "unbound_protocol"),
        }
    # ---- original deterministic front-end on the whole corpus -------------
    det = Counter()
    det_verdicts = Counter()
    profile = load_profile("claude-code")
    for s in json.loads((SOURCES / "sources.json").read_text()):
        res = compile_markdown((SOURCES / s["id"] / "SKILL.md").read_text(encoding="utf-8"),
                               profile, name=s["id"])
        det[res.goal_source] += 1
        det_verdicts[check(res.pack).label] += 1
    metrics["deterministic_original_all_294"] = {"goal_source": dict(det),
                                                 "verdicts": dict(det_verdicts)}
    write_json(out / "metrics.json", metrics)
    print(json.dumps({k: metrics[k] for k in ("real_paired", "stability")}, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("out", type=Path)
    p.add_argument("--real", type=int, default=150)
    p.add_argument("--stable", type=int, default=20)
    p.add_argument("--samples", type=int, default=3)
    p = sub.add_parser("retry")
    p.add_argument("out", type=Path)
    p = sub.add_parser("score")
    p.add_argument("out", type=Path)
    a = ap.parse_args()
    if a.cmd == "prepare":
        prepare(a.out, a.real, a.stable, a.samples)
    elif a.cmd == "retry":
        retry(a.out)
    else:
        score_all(a.out)


if __name__ == "__main__":
    main()

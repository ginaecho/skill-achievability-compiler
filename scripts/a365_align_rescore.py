"""PLAN Addendum E-e: re-score the Agent 365 packs on disk with alignment through bindings.

    python scripts/a365_align_rescore.py [--out runs/20261016_a365_align]

No model calls. For the 30 named-vocabulary packs (runs/20261015_hosts/a365) and the 30
blind-vocabulary packs (runs/20261015_hosts/a365_blind), every static check of the case's
checks.json is run as scripts/hosts_e2e.py score_a365 runs it (final_packs, map_to_grants,
run_cases.static_check, agrees: imported, not copied), in three modes:

    none        the pack as hosts_e2e scores it (no alignment)
    aligned     the pack aligned once against the environment as published
                (environment.json: align_to_contracts), then the check's scenario
    aligned_at_check
                alignment inside bind_environment, i.e. against the scenario's
                contracts (replace_contracts included); a sensitivity arm that
                shows what alignment would hide if the environment's contract
                were the defective one

A check is decided when the checker ran (no unaligned-vocabulary or schema error).
Role-separation checks do not depend on state names and run in every mode.
Writes results.json (one row per pack, check and mode) and summary.json.
"""
from __future__ import annotations

import argparse
import functools
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from skillc.frontend.contracts import align_to_contracts, bind_environment  # noqa: E402
from skillc.pack import PackError  # noqa: E402

ARMS = {"named": ROOT / "runs" / "20261015_hosts" / "a365",
        "blind": ROOT / "runs" / "20261015_hosts" / "a365_blind"}
MODES = ("none", "aligned", "aligned_at_check")


def load_hosts():
    spec = importlib.util.spec_from_file_location("hosts_e2e", ROOT / "scripts" / "hosts_e2e.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def actual_of(rc, pack: dict, env: dict, check: dict) -> dict:
    """hosts_e2e.score_a365's `actual` for one check."""
    act = rc.static_check(pack, env, check)
    if "role_separation" in check:
        return act
    return {"verdict": act["verdict"], "reason": act["reason"],
            "protocol": act.get("protocol", ""),
            "protocol_reason": act.get("protocol_reason", ""),
            "unavailable": act["unavailable_capabilities"],
            "contracts_applied": act["contracts_applied"]}


def run_mode(h, rc, mode: str, pack: dict, env: dict, check: dict) -> dict:
    original = rc.bind_environment
    try:
        if mode == "aligned":
            pack = align_to_contracts(pack, env["contracts"], env.get("states", {})).pack
        elif mode == "aligned_at_check":
            rc.bind_environment = functools.partial(bind_environment, align=True)
        return actual_of(rc, pack, env, check)
    except (ValueError, PackError) as e:
        return {"error": f"{type(e).__name__}: {e}"}
    finally:
        rc.bind_environment = original


def score_arm(h, rc, arm: str, out: Path) -> list[dict]:
    h.BLIND = arm == "blind"
    final, _ = h.final_packs("a365", out)
    rows = []
    for d in h.a365_cases():
        env = h.rj(d / "environment.json")
        checks = [c for c in h.rj(d / "checks.json") if c["kind"] == "static"]
        for k in range(h.SAMPLES["a365"]):
            rec = final[f"{d.name}__s{k}"]
            if not rec["ok"]:
                for c in checks:
                    for mode in MODES:
                        rows.append({"arm": arm, "case": d.name, "sample": k, "check": c["id"],
                                     "mode": mode, "expected": c["expected"],
                                     "actual": {"error": rec["error"]}, "decided": False,
                                     "agree": False, "renamed": []})
                continue
            pack, rename, notes = h.map_to_grants(rec["res"]["parsed"], env["grants"])
            alignment = align_to_contracts(pack, env["contracts"], env.get("states", {}))
            for c in checks:
                for mode in MODES:
                    actual = run_mode(h, rc, mode, pack, env, c)
                    rows.append({
                        "arm": arm, "case": d.name, "sample": k, "check": c["id"],
                        "mode": mode, "expected": c["expected"], "actual": actual,
                        "decided": not actual.get("error"),
                        "agree": h.agrees(actual, c["expected"]),
                        "renamed": [list(r) for r in alignment.renamed] if mode != "none" else [],
                        "dropped_init": list(alignment.dropped_init) if mode != "none" else [],
                        "tool_rename": rename, "notes": notes})
    return rows


def summarize(rows: list[dict]) -> dict:
    out = {}
    for arm in ARMS:
        for mode in MODES:
            rs = [r for r in rows if r["arm"] == arm and r["mode"] == mode]
            decided = [r for r in rs if r["decided"]]
            exp_v = lambda r: r["expected"].get("verdict")  # noqa: E731
            dis = [r for r in decided if not r["agree"]]
            dis_ach = [r for r in dis if exp_v(r) == "ACHIEVABLE"]
            masked = [r for r in decided if exp_v(r) == "IMPOSSIBLE"
                      and r["actual"].get("verdict") == "ACHIEVABLE"]
            out[f"{arm}|{mode}"] = {
                "checks": len(rs), "decided": len(decided), "agreed": sum(r["agree"] for r in rs),
                "disagreements_decided": len(dis),
                "disagreements_expected_achievable": len(dis_ach),
                "expected_impossible_judged_achievable": len(masked),
                "disagreements": [{k: r[k] for k in ("case", "sample", "check", "expected")}
                                  | {"actual": r["actual"].get("error") or
                                     f"{r['actual'].get('verdict')} {r['actual'].get('reason')}"}
                                  for r in dis],
                "undecided_errors": dict(Counter(
                    r["actual"]["error"].split(":")[0] for r in rs if not r["decided"])),
                "packs_renamed": len({(r["case"], r["sample"]) for r in rs if r["renamed"]}),
            }
    blind = out["blind|aligned"]
    named = out["named|aligned"]
    out["G8"] = {
        "criterion": "with alignment, blind arm decides >= half of 195 checks with zero "
                     "disagreements whose expectation is ACHIEVABLE; named arm stays at 189/195",
        "blind_decided": f"{blind['decided']}/{blind['checks']}",
        "blind_disagreements_expected_achievable": blind["disagreements_expected_achievable"],
        "named_agreed": f"{named['agreed']}/{named['checks']}",
        "met": (blind["decided"] * 2 >= blind["checks"]
                and blind["disagreements_expected_achievable"] == 0
                and named["agreed"] == 189 and named["checks"] == 195),
        "mode": "aligned (alignment against the environment as published)"}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=ROOT / "runs" / "20261016_a365_align")
    args = ap.parse_args(argv)
    h = load_hosts()
    rc = h.load_run_cases()
    rows = []
    for arm, out in ARMS.items():
        rows += score_arm(h, rc, arm, out)
    summary = summarize(rows)
    args.out.mkdir(parents=True, exist_ok=True)
    h.wj(args.out / "results.json", rows)
    h.wj(args.out / "summary.json", summary)
    for key, s in summary.items():
        if key == "G8":
            print("G8", json.dumps(s))
        else:
            print(key, {k: v for k, v in s.items() if k not in ("disagreements",)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Criterion B4 of runs/20261015_review_response/PLAN.md (Addendum B, F-d/F-f):
the finance hosted agent and the finance group, compacted with P2g+ against the
EFFECTIVE runtime (skillc.gate.compact_project) and gated with gate(packs=...).

    python runs/20261015_hosts/maf_v2/run_b4.py smoke   one sample, finance azure.yaml (not scored)
    python runs/20261015_hosts/maf_v2/run_b4.py run     all compactions (3 samples per job)
    python runs/20261015_hosts/maf_v2/run_b4.py freeze  prompts/, outputs/, frozen.json from the logs
    python runs/20261015_hosts/maf_v2/run_b4.py score   deterministic: gate, structure, tables

compact_project needs the declared azure.yaml to build the effective runtime, so the
finance agent is compacted once per configuration (3 samples each) in its own project
copy. As a supplement the azure.yaml packs are also gated under the other two files.
Model calls are made only by skillc.gate.compact_project (src/, unchanged).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import hosts_e2e as H  # noqa: E402  reuse: structure, count_msgs, EMAIL_STEP, COPY_IGNORE
from skillc.frontend.ce import parse_ce_detailed  # noqa: E402
from skillc.gate import GateError, MULTI_ROLE_NOTE, compact_project, gate  # noqa: E402

MODEL, PROVIDER, VERSION, SAMPLES = "gpt-5.4", "azure-openai", "p2g+", 3
FINANCE = ROOT / "examples" / "hosted-agent-finance"
GROUP = ROOT / "examples" / "hosted-agent-finance-group"
OUT_MAF = HERE
OUT_GROUP = HERE.parent / "maf_group_v2"
CONFIGS = H.CONFIGS
PACK = "quarterly_finance_report.ce"
EMAIL_PACK = "quarterly_finance_report.email.ce"

# job id -> (source project, declared file, variant, out dir)
JOBS = {
    "finance_azure": (FINANCE, "azure.yaml", "main", OUT_MAF),
    "finance_search": (FINANCE, "azure.search.yaml", "main", OUT_MAF),
    "finance_isolated": (FINANCE, "azure.isolated.yaml", "main", OUT_MAF),
    "finance_email": (FINANCE, "azure.yaml", "email", OUT_MAF),
    "group_azure": (GROUP, "azure.yaml", "main", OUT_GROUP),
}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def copy(src: Path, dst: Path, email: bool = False) -> Path:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=H.COPY_IGNORE)
    for vend in dst.glob("src/*/skillc"):
        shutil.rmtree(vend)
    if email:
        w = dst / "skills" / "Writer.md"
        w.write_text(w.read_text(encoding="utf-8").rstrip("\n") + H.EMAIL_STEP, encoding="utf-8")
        shutil.copy(dst / "protocol-variants" / EMAIL_PACK, dst / "protocol" / EMAIL_PACK)
    return dst


def run_job(jid: str, samples: int, tag: str = "") -> dict:
    src, cfg, variant, out = JOBS[jid]
    proj = copy(src, out / f"project_{jid}{tag}", email=(variant == "email"))
    t0 = time.time()
    try:
        recs = compact_project(proj, cfg, model=MODEL, samples=samples, provider=PROVIDER,
                               version=VERSION)
        err = None
    except Exception as e:  # noqa: BLE001  recorded, not raised
        recs, err = [], f"{type(e).__name__}: {e}"
    res = {"job": jid + tag, "project": proj.relative_to(ROOT).as_posix(), "declared": cfg,
           "variant": variant, "records": recs, "error": err,
           "seconds": round(time.time() - t0, 1)}
    H.wj(out / f"compaction_{jid}{tag}.json", res)
    print(f"[{jid}{tag}] done in {res['seconds']}s err={err} "
          f"labels={[r.get('label') for r in recs]}", flush=True)
    return res


def _usage(blocks: list[dict]) -> dict:
    use = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cached_input_tokens": 0}
    for u in blocks:
        use["calls"] += 1
        use["input_tokens"] += int(u.get("input_tokens") or 0) + int(
            u.get("cache_read_input_tokens") or 0)
        use["output_tokens"] += int(u.get("output_tokens") or 0)
        use["cached_input_tokens"] += int(u.get("cache_read_input_tokens") or 0)
    return use


def freeze(out: Path, jids: list[str]) -> dict:
    """prompts/, outputs/ and frozen.json from the compaction logs."""
    (out / "prompts").mkdir(exist_ok=True)
    (out / "outputs").mkdir(exist_ok=True)
    jobs = []
    tot = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cached_input_tokens": 0}
    for jid in jids:
        _, cfg, variant, _ = JOBS[jid]
        proj = out / f"project_{jid}"
        for k in range(SAMPLES):
            log_path = proj / "protocol" / f"compacted_s{k}.json"
            if not log_path.is_file():
                jobs.append({"id": f"{jid}__s{k}", "missing_log": True})
                continue
            log = H.rj(log_path)
            for r in log["rounds"]:
                rid = f"{jid}__s{k}__r{r['round']}"
                p = out / "prompts" / f"{rid}.json"
                H.wj(p, {"system": log["system"], "user": r["user"], "kind": r["kind"]})
                o = out / "outputs" / f"{rid}.txt"
                o.write_text(r["reply"], encoding="utf-8")
                use = _usage(r["usage"])
                for key in tot:
                    tot[key] += use[key]
                jobs.append({"id": rid, "job": jid, "declared": cfg, "variant": variant,
                             "sample": k, "round": r["round"], "kind": r["kind"],
                             "ok": r["ok"], "error": r["error"],
                             "prompt": p.relative_to(out).as_posix(),
                             "output": o.relative_to(out).as_posix(),
                             "prompt_sha256": sha(p.read_bytes()),
                             "output_sha256": sha(o.read_bytes()), "usage": use,
                             "raw_usage": r["usage"]})
            jobs.append({"id": f"{jid}__s{k}__log", "log": log_path.relative_to(out).as_posix(),
                         "sha256": sha(log_path.read_bytes())})
            ce = proj / "protocol" / f"compacted_s{k}.ce"
            if ce.is_file():
                jobs.append({"id": f"{jid}__s{k}__ce", "ce": ce.relative_to(out).as_posix(),
                             "sha256": sha(ce.read_bytes())})
    frozen = {"created_utc": datetime.now(timezone.utc).isoformat(), "criterion": "B4",
              "method": "P2g+ via skillc.gate.compact_project (effective runtime, "
                        "MULTI_ROLE_NOTE, two located-error retries, one guarded repair)",
              "model": MODEL, "provider": PROVIDER, "version": VERSION, "samples": SAMPLES,
              "multi_role_note": MULTI_ROLE_NOTE,
              "src_sha256": {p: sha((ROOT / p).read_bytes()) for p in (
                  "src/skillc/gate.py", "src/skillc/frontend/llm.py",
                  "src/skillc/frontend/prompts.py", "src/skillc/frontend/ce.py",
                  "src/skillc/frontend/runtime.py", "scripts/hosts_e2e.py")},
              "jobs": jobs, "usage_total": tot}
    H.wj(out / "frozen.json", frozen)
    return frozen


def cmd_run() -> None:
    with ThreadPoolExecutor(max_workers=3) as ex:   # at most 3 concurrent model calls
        list(ex.map(lambda j: run_job(j, SAMPLES), list(JOBS)))
    cmd_freeze()


def cmd_freeze() -> None:
    freeze(OUT_MAF, [j for j in JOBS if JOBS[j][3] == OUT_MAF])
    freeze(OUT_GROUP, [j for j in JOBS if JOBS[j][3] == OUT_GROUP])


# --------------------------------------------------------------------------
# score
# --------------------------------------------------------------------------

def entry_dict(e) -> dict:
    if e is None:
        return {"verdict": "NO_PACK"}
    d = e.detail
    return {"verdict": e.verdict, "reason": e.reason, "fixes": e.fixes,
            "assumptions": e.assumptions, "via": d.get("via"), "withdrawn": d.get("withdrawn"),
            "blocked": d.get("blocked"), "pruned": d.get("pruned"),
            "pure_verdict": d.get("pure_verdict"), "bound_verdict": d.get("bound_verdict"),
            "bound_protocol": d.get("bound_protocol")}


def gate_pack(proj: Path, cfg: str, ce: Path, ref_name: str) -> dict:
    try:
        rep = gate(proj, cfg, packs=[ce])
    except GateError as e:
        return {"verdict": "GATE_ERROR", "reason": str(e)}
    mine = next((e for e in rep.packs if e.name == ce.name), None)
    ref = next((e for e in rep.authored if e.name == ref_name), None)
    return {**entry_dict(mine), "report_verdict": rep.verdict,
            "skills": {s.name: s.verdict for s in rep.skills},
            "topology": [{"name": t.name, "verdict": t.verdict, "reason": t.reason}
                         for t in rep.topology],
            "topology_note": rep.topology_note,
            "authored_reference": entry_dict(ref)}


def rule14(pack: dict) -> dict:
    """Approving tools: named `approv*`, or adding an `approv*` atom the revenue-analysis
    tool requires. (hosts_e2e.structure's `approving_tool_owners` also counts any tool
    whose added atom merely contains "approv", e.g. a coordinator's
    `user_reported_branch_approval_and_path`; it is kept as reported, this is stricter.)"""
    caps = pack["capabilities"]
    wra = next((n for n in caps if "revenue_analysis" in n), None)
    pre = set(H.atoms(caps[wra].get("pre", True))) if wra else set()
    owners = {n: c.get("owner") for n, c in caps.items()
              if "approv" in n.lower()
              or any("approv" in a.lower() and a in pre for a in c.get("add", []))}
    others = {t: o for t, o in owners.items() if H._norm(o) != "taxverifier"}
    return {"approving_tools": owners, "non_verifier_owns_approving_tool": bool(others),
            "violations": others}


def email_check(parsed, g: dict) -> dict:
    caps = parsed.pack["capabilities"]
    tools = [n for n in caps if "mail" in n.lower()]
    needs = sorted({r for t in tools for r in (parsed.bindings.get(t) or {}).get("needs") or []})
    reason = g.get("reason", "")
    named = [r for r in needs if f"`{r}`" in reason]
    return {"email_tools": {t: parsed.bindings.get(t) for t in tools}, "email_needs": needs,
            "impossible": g.get("verdict") == "IMPOSSIBLE",
            "names_missing_connection": g.get("verdict") == "IMPOSSIBLE" and bool(named),
            "named_needs": named, "pure_refuted": g.get("pure_verdict") == "IMPOSSIBLE"}


def sample_rows(out: Path, jid: str, configs: list[str], ref_name: str) -> list[dict]:
    _, cfg0, variant, _ = JOBS[jid]
    proj = out / f"project_{jid}"
    comp = H.rj(out / f"compaction_{jid}.json")
    rows = []
    for rec in comp["records"]:
        k = rec["sample"]
        log = H.rj(proj / "protocol" / f"compacted_s{k}.json")
        row = {"job": jid, "variant": variant, "compacted_under": cfg0, "sample": k,
               "rounds": [r["kind"] for r in log["rounds"]],
               "round_errors": [r["error"] for r in log["rounds"]],
               "ok": rec["ok"], "error": rec["error"], "repaired": rec["repaired"],
               "repair_rejected": log.get("repair_rejected"),
               "compaction_label": rec["label"], "compaction_reason": rec["reason"],
               "effective_tools": log["effective_tools"]}
        ce = proj / "protocol" / f"compacted_s{k}.ce"
        if not rec["ok"] or not ce.is_file():
            row["gate"] = {c: {"verdict": "NO_PACK", "reason": rec["error"]} for c in configs}
            rows.append(row)
            continue
        text = ce.read_text(encoding="utf-8")
        parsed = parse_ce_detailed(text)
        row["ce"] = text
        row["gate"] = {c: gate_pack(proj, c, ce, ref_name) for c in configs}
        row["structure"] = H.structure(parsed.pack, parsed.bindings)
        row["rule14"] = rule14(parsed.pack)
        if variant == "email":
            row["email"] = email_check(parsed, row["gate"]["azure.yaml"])
        rows.append(row)
    return rows


def short(g: dict) -> str:
    v = g["verdict"]
    if v in ("IMPOSSIBLE", "REJECTED", "UNKNOWN", "NO_PACK", "GATE_ERROR"):
        return f"{v}: {str(g.get('reason', ''))[:200]}"
    return v


def cmd_score() -> None:
    main_rows = []
    for jid, cfg in (("finance_azure", "azure.yaml"), ("finance_search", "azure.search.yaml"),
                     ("finance_isolated", "azure.isolated.yaml")):
        main_rows += sample_rows(OUT_MAF, jid, [cfg], PACK)
    cross_rows = sample_rows(OUT_MAF, "finance_azure", CONFIGS, PACK)
    email_rows = sample_rows(OUT_MAF, "finance_email", ["azure.yaml"], EMAIL_PACK)
    group_rows = sample_rows(OUT_GROUP, "group_azure", ["azure.yaml"], PACK)

    authored = parse_ce_detailed((FINANCE / "protocol" / PACK).read_text(encoding="utf-8"))
    authored_email = parse_ce_detailed((FINANCE / "protocol-variants" / EMAIL_PACK)
                                       .read_text(encoding="utf-8"))
    authored_group = parse_ce_detailed((GROUP / "protocol" / PACK).read_text(encoding="utf-8"))

    def false_imp(rows):
        return [{"sample": r["sample"], "config": c, "compacted_under": r["compacted_under"],
                 "reason": g.get("reason")} for r in rows for c, g in r["gate"].items()
                if g["verdict"] == "IMPOSSIBLE"]

    def per_sample(rows):
        out = {}
        for r in rows:
            out[r["sample"]] = out.get(r["sample"], 0) + sum(
                g["verdict"] == "IMPOSSIBLE" for g in r["gate"].values())
        return out

    fi, ps = false_imp(main_rows), per_sample(main_rows)
    zero = sorted(k for k, n in ps.items() if n == 0)
    cross_fi, cross_ps = false_imp(cross_rows), per_sample(cross_rows)
    email_ok = [r["sample"] for r in email_rows
                if (r.get("email") or {}).get("names_missing_connection")]
    b4_a = len(zero) >= 2
    b4_b = len(email_ok) >= 2
    summary = {
        "criterion": "B4", "model": MODEL, "version": VERSION, "samples": SAMPLES,
        "finance": {
            "note": "each configuration compacted separately (compact_project builds the "
                    "effective runtime from the declared file); sample k of one "
                    "configuration is independent of sample k of another",
            "table": [{"sample": r["sample"], "config": c, "pack": g["verdict"],
                       "report": g.get("report_verdict"),
                       "authored": (g.get("authored_reference") or {}).get("verdict"),
                       "reason": g.get("reason"), "withdrawn": g.get("withdrawn"),
                       "blocked": g.get("blocked"), "rounds": r["rounds"]}
                      for r in main_rows for c, g in r["gate"].items()],
            "false_impossible": fi, "false_impossible_count": len(fi), "of": 9,
            "false_impossible_per_sample_index": ps,
            "sample_indices_with_zero_false_impossible": zero,
            "cross_gated_azure_yaml_packs": {
                "table": [{"sample": r["sample"], "config": c, "pack": g["verdict"],
                           "reason": g.get("reason")} for r in cross_rows
                          for c, g in r["gate"].items()],
                "false_impossible_count": len(cross_fi),
                "false_impossible_per_sample": cross_ps},
            "first_run": {"false_impossible": 6, "of": 9,
                          "source": "runs/20261015_hosts/maf/summary.json"}},
        "email": {
            "table": [{"sample": r["sample"], "pack": r["gate"]["azure.yaml"]["verdict"],
                       "reason": r["gate"]["azure.yaml"].get("reason"),
                       "authored": (r["gate"]["azure.yaml"].get("authored_reference") or {})
                       .get("verdict"),
                       "authored_reason": (r["gate"]["azure.yaml"].get("authored_reference")
                                           or {}).get("reason"),
                       **(r.get("email") or {})} for r in email_rows],
            "samples_naming_missing_connection": email_ok},
        "group": {
            "table": [{"sample": r["sample"], "pack": g["verdict"],
                       "report": g.get("report_verdict"),
                       "authored": (g.get("authored_reference") or {}).get("verdict"),
                       "reason": g.get("reason"),
                       "topology": [(t["verdict"], t["name"]) for t in g.get("topology", [])]}
                      for r in group_rows for c, g in r["gate"].items()],
            "false_impossible": false_imp(group_rows)},
        "structure": {
            "authored": H.structure(authored.pack, authored.bindings),
            "authored_email": H.structure(authored_email.pack, authored_email.bindings),
            "authored_group": H.structure(authored_group.pack, authored_group.bindings),
            "finance": [{"job": r["job"], "sample": r["sample"], **r["structure"],
                         "rule14": r["rule14"]} for r in main_rows if "structure" in r],
            "email": [{"sample": r["sample"], **r["structure"], "rule14": r["rule14"]}
                      for r in email_rows if "structure" in r],
            "group": [{"sample": r["sample"], **r["structure"], "rule14": r["rule14"]}
                      for r in group_rows if "structure" in r]},
        "B4": {"zero_false_impossible_in_2_of_3_samples": b4_a,
               "email_refuted_naming_missing_connection_in_2_of_3": b4_b,
               "met": b4_a and b4_b},
    }
    usage = {}
    for out in (OUT_MAF, OUT_GROUP):
        f = out / "frozen.json"
        if f.is_file():
            usage[out.name] = H.rj(f)["usage_total"]
    summary["usage"] = usage
    H.wj(OUT_MAF / "results.json", {"finance": main_rows, "finance_cross": cross_rows,
                                    "email": email_rows})
    H.wj(OUT_MAF / "summary.json", {k: v for k, v in summary.items() if k != "group"})
    H.wj(OUT_GROUP / "results.json", {"group": group_rows})
    H.wj(OUT_GROUP / "summary.json", {
        "criterion": "B4 (second multi-role case)", "group": summary["group"],
        "structure": {"authored_group": summary["structure"]["authored_group"],
                      "group": summary["structure"]["group"]},
        "usage": usage.get(OUT_GROUP.name)})
    for r in main_rows:
        for c, g in r["gate"].items():
            print(f"finance s{r['sample']} {c}: {short(g)} (authored "
                  f"{(g.get('authored_reference') or {}).get('verdict')}) rounds={r['rounds']}")
    for r in cross_rows:
        for c, g in r["gate"].items():
            print(f"cross s{r['sample']} {c}: {short(g)}")
    for r in email_rows:
        print(f"email s{r['sample']}: {short(r['gate']['azure.yaml'])} rounds={r['rounds']} "
              f"email={r.get('email')}")
    for r in group_rows:
        g = r["gate"]["azure.yaml"]
        print(f"group s{r['sample']}: {short(g)} report={g.get('report_verdict')} "
              f"rounds={r['rounds']}")
    print(json.dumps(summary["B4"]), json.dumps(usage))


def main(argv) -> int:
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "smoke":
        res = run_job("finance_azure", 1, tag="_smoke")
        print(json.dumps(res, indent=1, default=str)[:3000])
    elif cmd == "run":
        cmd_run()
    elif cmd == "freeze":
        cmd_freeze()
    elif cmd == "score":
        cmd_score()
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

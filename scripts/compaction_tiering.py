#!/usr/bin/env python
"""Offline simulation of a *tiered* compaction policy for SkillC.

Both compaction modes (deterministic rule-based, and gpt-5.4) have already been
run over the same inputs; this script only re-combines the stored verdicts.  It
makes no LLM call and imports nothing from the checker -- only the token model
in ``skillc.tokens`` (read-only) to price the LLM calls a tier would make.

Tiers (rule = rule-based verdict, llm = gpt-5.4 verdict), per input:

  T0  rule only
  T1  LLM only when rule is UNKNOWN (or ERROR), else keep rule
  T2  keep rule IMPOSSIBLE, LLM otherwise
  T3  keep rule IMPOSSIBLE, keep rule ACHIEVABLE when its goal_source is a
      semantic reading (not ``tool_usage_only``), LLM otherwise
  T4  LLM always (= pure gpt-5.4)

Metric definitions match docs/BENCHMARK_REPORT.md (positive = IMPOSSIBLE):
  false alarm rate = FP / (FP + TN)       over truly-ACHIEVABLE inputs that got a verdict
  precision        = TP / (TP + FP)
  recall           = TP / all truly-IMPOSSIBLE inputs (UNKNOWN counts as a miss)
  accuracy         = correct / inputs where a verdict (not UNKNOWN/ERROR) was given
  gave a verdict   = share of labelled inputs not answered UNKNOWN/ERROR
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "demo" / "skillc-architecture-app"
sys.path.insert(0, str(ROOT / "src"))
from skillc.tokens import compaction_cost, _TYPICAL_PACK_TOKENS  # noqa: E402

TIERS = ["T0", "T1", "T2", "T3", "T4"]
TIER_NAME = {
    "T0": "T0 rule only",
    "T1": "T1 LLM if rule UNKNOWN",
    "T2": "T2 keep rule IMPOSSIBLE",
    "T3": "T3 keep rule IMPOSSIBLE + semantic ACHIEVABLE",
    "T4": "T4 LLM always",
}
NO_VERDICT = ("UNKNOWN", "ERROR")
SKILL_POOLS = ("ce_sources", "ce_sources_ext", "ce_sources_div",
               "ce_sources_gr", "compaction_sources")


# ---------------------------------------------------------------- routing
def uses_llm(tier: str, rule_verdict: str, rule_goal_source: str) -> bool:
    if tier == "T0":
        return False
    if tier == "T4":
        return True
    if tier == "T1":
        return rule_verdict in NO_VERDICT
    if tier == "T2":
        return rule_verdict != "IMPOSSIBLE"
    if tier == "T3":
        if rule_verdict == "IMPOSSIBLE":
            return False
        if rule_verdict == "ACHIEVABLE" and rule_goal_source != "tool_usage_only":
            return False
        return True
    raise ValueError(tier)


# ---------------------------------------------------------------- tokens
def pack_tokens_cost(text: str | None, pack: dict | None) -> int:
    """Token-model cost (skillc.tokens.compaction_cost, 0 repair rounds)."""
    if text is None:
        return -1
    return compaction_cost(text, pack=pack).total_tokens


def build_text_index(data_root: Path | None):
    """Return (data_root, real: (kind, id) -> path) lookups."""
    if data_root is None:
        return {}, {}
    real = {}
    bench = data_root / "benchmark"
    for pool in SKILL_POOLS:
        src = bench / pool / "sources.json"
        if src.is_file():
            for rec in json.loads(src.read_text(encoding="utf-8")):
                p = bench / pool / rec["id"] / "SKILL.md"
                if p.is_file():
                    real.setdefault(("skill", rec["id"]), p)
    src = bench / "copilot_sources" / "sources.json"
    if src.is_file():
        for rec in json.loads(src.read_text(encoding="utf-8")):
            p = bench / "copilot_sources" / rec["path"]
            if p.is_file():
                real.setdefault((rec["kind"], rec["id"]), p)
    return data_root, real


def labelled_text(data_root, source_path: str) -> str | None:
    if not data_root:
        return None
    p = data_root / source_path
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else None


# ---------------------------------------------------------------- metrics
def labelled_metrics(pairs):
    """pairs: list of (expected, verdict) for labelled rows only."""
    tp = sum(1 for e, v in pairs if e == "IMPOSSIBLE" and v == "IMPOSSIBLE")
    fn = sum(1 for e, v in pairs if e == "IMPOSSIBLE" and v == "ACHIEVABLE")
    fp = sum(1 for e, v in pairs if e == "ACHIEVABLE" and v == "IMPOSSIBLE")
    tn = sum(1 for e, v in pairs if e == "ACHIEVABLE" and v == "ACHIEVABLE")
    n_imp = sum(1 for e, _ in pairs if e == "IMPOSSIBLE")
    n_ach = sum(1 for e, _ in pairs if e == "ACHIEVABLE")
    gave = sum(1 for _, v in pairs if v not in NO_VERDICT)
    div = lambda a, b: (a / b) if b else None  # noqa: E731
    return {
        "labelled": len(pairs), "truly_impossible": n_imp, "truly_achievable": n_ach,
        "tp": tp, "fn": fn, "fp": fp, "tn": tn,
        "unknown_on_impossible": sum(1 for e, v in pairs if e == "IMPOSSIBLE" and v in NO_VERDICT),
        "unknown_on_achievable": sum(1 for e, v in pairs if e == "ACHIEVABLE" and v in NO_VERDICT),
        "false_alarm_rate": div(fp, fp + tn), "false_alarm_den": fp + tn,
        "precision": div(tp, tp + fp), "precision_den": tp + fp,
        "recall": div(tp, n_imp), "recall_den": n_imp,
        "accuracy": div(tp + tn, tp + tn + fp + fn), "accuracy_den": tp + tn + fp + fn,
        "gave_verdict": div(gave, len(pairs)), "gave_den": len(pairs), "gave_n": gave,
    }


def real_metrics(items):
    """items: list of (verdict, audit) -- no answer key, so audit-based only."""
    v = Counter(x for x, _ in items)
    imp = [(x, a) for x, a in items if x == "IMPOSSIBLE"]
    a = Counter(a for _, a in imp)
    audited = a["confirmed"] + a["false_refutation"]
    return {
        "n": len(items), "verdicts": dict(v), "impossible": len(imp),
        "confirmed": a["confirmed"], "false_refutation": a["false_refutation"],
        "unaudited": len(imp) - audited,
        "audited_precision": (a["confirmed"] / audited) if audited else None,
        "audited_den": audited,
        "gave_verdict": sum(1 for x, _ in items if x not in NO_VERDICT) / len(items),
        "gave_n": sum(1 for x, _ in items if x not in NO_VERDICT),
    }


# ---------------------------------------------------------------- labelled
def run_labelled(rule_path, llm_path, data_root):
    rule = {r["id"]: r for r in json.load(open(rule_path, encoding="utf-8"))["rows"]}
    llm = {r["id"]: r for r in json.load(open(llm_path, encoding="utf-8"))["rows"]}
    ids = sorted(set(rule) & set(llm))
    assert len(ids) == len(rule) == len(llm), "id sets differ"
    tok = {}
    n_missing = 0
    for i in ids:
        t = labelled_text(data_root, llm[i]["source_path"])
        c = pack_tokens_cost(t, llm[i].get("compacted_pack"))
        if c < 0:
            n_missing += 1
            c = None
        tok[i] = c
    known = [c for c in tok.values() if c is not None]
    mean_tok = round(sum(known) / len(known)) if known else None
    for i in ids:
        if tok[i] is None:
            tok[i] = mean_tok if mean_tok is not None else compaction_cost("", pack=None).total_tokens
    labelled = [i for i in ids if rule[i]["expected"] in ("IMPOSSIBLE", "ACHIEVABLE")]

    def pick(tier, i):
        return llm[i] if uses_llm(tier, rule[i]["observed"], rule[i]["goal_source"]) else rule[i]

    out = {"inputs": len(ids), "labelled": len(labelled), "tokens_missing_text": n_missing,
           "tokens_fallback_mean": mean_tok, "tiers": {}}
    full_tokens = sum(tok[i] for i in ids)
    for t in TIERS:
        called = [i for i in ids if uses_llm(t, rule[i]["observed"], rule[i]["goal_source"])]
        m = labelled_metrics([(rule[i]["expected"], pick(t, i)["observed"]) for i in labelled])
        m["llm_calls"] = len(called)
        m["llm_calls_pct"] = len(called) / len(ids)
        m["tokens"] = sum(tok[i] for i in called)
        m["tokens_saved_vs_T4"] = full_tokens - m["tokens"]
        out["tiers"][t] = m
    # oracle: best of the two modes per labelled row
    orc = []
    for i in labelled:
        e = rule[i]["expected"]
        orc.append((e, e if rule[i]["observed"] == e else
                    (e if llm[i]["observed"] == e else llm[i]["observed"])))
    out["oracle"] = labelled_metrics(orc)
    out["oracle_right_by"] = {
        "both": sum(1 for i in labelled if rule[i]["observed"] == rule[i]["expected"] == llm[i]["observed"]),
        "rule_only": sum(1 for i in labelled if rule[i]["observed"] == rule[i]["expected"] != llm[i]["observed"]),
        "llm_only": sum(1 for i in labelled if llm[i]["observed"] == rule[i]["expected"] != rule[i]["observed"]),
        "neither": sum(1 for i in labelled if rule[i]["observed"] != rule[i]["expected"] != llm[i]["observed"]),
    }
    # disagreement analysis (labelled rows only)
    dis = [i for i in labelled if rule[i]["observed"] != llm[i]["observed"]]
    out["disagree_n"] = len(dis)
    out["disagree_crosstab"] = [
        {"rule": r, "llm": l, "truth": e, "n": n}
        for (r, l, e), n in sorted(Counter(
            (rule[i]["observed"], llm[i]["observed"], rule[i]["expected"]) for i in dis).items(),
            key=lambda kv: -kv[1])]
    def by(key):
        res = {}
        for k in sorted({rule[i][key] for i in labelled}):
            sub = [i for i in labelled if rule[i][key] == k]
            d = [i for i in sub if i in set(dis)]
            res[k] = {"labelled": len(sub), "disagree": len(d),
                      "rule_right": sum(rule[i]["observed"] == rule[i]["expected"] for i in d),
                      "llm_right": sum(llm[i]["observed"] == rule[i]["expected"] for i in d),
                      "neither_right": sum(rule[i]["observed"] != rule[i]["expected"] and
                                           llm[i]["observed"] != rule[i]["expected"] for i in d)}
        return res
    out["disagree_by_input_type"] = by("input_type")
    out["disagree_by_suite"] = by("suite")
    out["llm_false_alarms"] = [
        {"id": i, "name": rule[i]["name"], "input_type": rule[i]["input_type"],
         "rule_verdict": rule[i]["observed"], "rule_reason": rule[i]["reason"],
         "llm_reason": llm[i]["reason"], "llm_frontier": llm[i]["frontier"]}
        for i in labelled if rule[i]["expected"] == "ACHIEVABLE" and llm[i]["observed"] == "IMPOSSIBLE"]
    out["rule_goal_sources"] = dict(Counter(rule[i]["goal_source"] for i in ids))
    # tier-vs-pure-mode errors: which rows does each tier lose relative to T4 / gain relative to T0
    for t in ("T1", "T2", "T3"):
        lost = [i for i in labelled if llm[i]["observed"] == rule[i]["expected"]
                and pick(t, i)["observed"] != rule[i]["expected"]]
        out["tiers"][t]["rows_right_in_T4_wrong_here"] = len(lost)
        out["tiers"][t]["lost_by"] = dict(Counter(
            (rule[i]["input_type"], rule[i]["observed"], llm[i]["observed"], rule[i]["expected"])
            .__repr__() for i in lost))
    return out


# ---------------------------------------------------------------- real
def run_real(rule_path, llm_path, data_root, env):
    # an id is not unique across kinds (the same upstream name can be both an
    # agent and a prompt), so the join key is (kind, id)
    # The rule-based run covers 899 rows; the gpt-5.4 run only the balanced
    # subset, so restrict both to rows flagged balanced (one skill id also
    # appears twice in the rule file, only one copy being in the subset).
    rule = {(r["kind"], r["id"]): r for r in json.load(open(rule_path, encoding="utf-8"))["rows"]
            if r.get("balanced", True)}
    llm = {(r["kind"], r["id"]): r for r in json.load(open(llm_path, encoding="utf-8"))["rows"]
           if r.get("balanced", True)}
    ids = sorted(set(rule) & set(llm))
    _, real_paths = build_text_index(data_root)
    tok, miss = {}, 0
    for i in ids:
        p = real_paths.get(i)
        c = (pack_tokens_cost(p.read_text(encoding="utf-8", errors="replace"),
                              llm[i].get("compacted_pack")) if p else -1)
        if c < 0:
            miss += 1
            c = None
        tok[i] = c
    known = [c for c in tok.values() if c is not None]
    mean_tok = round(sum(known) / len(known)) if known else compaction_cost("", pack=None).total_tokens
    for i in ids:
        if tok[i] is None:
            tok[i] = mean_tok
    R = lambda i: rule[i][env]  # noqa: E731
    L = lambda i: llm[i][env]  # noqa: E731
    full = sum(tok.values())
    out = {"env": env, "inputs": len(ids), "rule_only_rows": len(set(rule) - set(llm)),
           "llm_only_rows": len(set(llm) - set(rule)), "tokens_missing_text": miss,
           "tokens_fallback_mean": mean_tok, "tiers": {}}
    out["rule_goal_sources"] = dict(Counter(R(i).get("goal_source") for i in ids))

    def sel(tier, i):
        return L(i) if uses_llm(tier, R(i)["verdict"], R(i).get("goal_source")) else R(i)

    def group(tier, ids_):
        return real_metrics([(sel(tier, i)["verdict"], sel(tier, i).get("audit")) for i in ids_])

    for t in TIERS:
        called = [i for i in ids if uses_llm(t, R(i)["verdict"], R(i).get("goal_source"))]
        m = group(t, ids)
        m["llm_calls"], m["llm_calls_pct"] = len(called), len(called) / len(ids)
        m["tokens"] = sum(tok[i] for i in called)
        m["tokens_saved_vs_T4"] = full - m["tokens"]
        m["by_kind"] = {k: group(t, [i for i in ids if i[0] == k])
                        for k in ("skill", "agent", "prompt")}
        out["tiers"][t] = m

    # audit oracle: avoid false refutations, prefer confirmed IMPOSSIBLE, then any verdict
    def oracle(i):
        c = [R(i), L(i)]
        for x in c:
            if x["verdict"] == "IMPOSSIBLE" and x.get("audit") == "confirmed":
                return x
        ok = [x for x in c if not (x["verdict"] == "IMPOSSIBLE" and x.get("audit") == "false_refutation")]
        for x in ok:
            if x["verdict"] not in NO_VERDICT:
                return x
        return (ok or c)[-1]
    o = real_metrics([(oracle(i)["verdict"], oracle(i).get("audit")) for i in ids])
    o["calls_note"] = "not a policy: needs the answer"
    out["oracle"] = o

    dis = [i for i in ids if R(i)["verdict"] != L(i)["verdict"]]
    out["disagree_n"] = len(dis)
    out["disagree_crosstab"] = [
        {"rule": r, "llm": l, "llm_audit": a, "n": n}
        for (r, l, a), n in sorted(Counter(
            (R(i)["verdict"], L(i)["verdict"], L(i).get("audit")) for i in dis).items(),
            key=lambda kv: -kv[1])]
    out["rule_impossible_audit"] = dict(Counter(R(i).get("audit") for i in ids if R(i)["verdict"] == "IMPOSSIBLE"))
    out["llm_impossible_audit"] = dict(Counter(L(i).get("audit") for i in ids if L(i)["verdict"] == "IMPOSSIBLE"))
    out["rule_impossible_where_llm_differs"] = [
        {"id": i[1], "kind": i[0], "rule_audit": R(i).get("audit"), "llm": L(i)["verdict"],
         "llm_audit": L(i).get("audit")} for i in dis if R(i)["verdict"] == "IMPOSSIBLE"]
    out["both_impossible_audit_pairs"] = dict(Counter(
        f"rule={R(i).get('audit')} llm={L(i).get('audit')}"
        for i in ids if R(i)["verdict"] == L(i)["verdict"] == "IMPOSSIBLE"))
    return out


# ---------------------------------------------------------------- markdown
def pc(x, d=1):
    return "n/a" if x is None else f"{100 * x:.{d}f}%"


def frac(x, n, d, dp=1):
    return "n/a" if x is None else f"{pc(x, dp)} ({n} of {d})"


def md_labelled(r):
    L = ["| tier | LLM calls (n, %) | false alarm rate | precision | recall | accuracy | gave a verdict | est. tokens |",
         "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for t in TIERS:
        m = r["tiers"][t]
        L.append(f"| {TIER_NAME[t]} | {m['llm_calls']} ({pc(m['llm_calls_pct'])}) "
                 f"| {frac(m['false_alarm_rate'], m['fp'], m['false_alarm_den'])} "
                 f"| {frac(m['precision'], m['tp'], m['precision_den'])} "
                 f"| {frac(m['recall'], m['tp'], m['recall_den'])} "
                 f"| {frac(m['accuracy'], m['tp'] + m['tn'], m['accuracy_den'])} "
                 f"| {pc(m['gave_verdict'])} ({m['gave_n']} of {m['gave_den']}) "
                 f"| {m['tokens']:,} |")
    o = r["oracle"]
    L.append(f"| oracle (best of both per row) | - "
             f"| {frac(o['false_alarm_rate'], o['fp'], o['false_alarm_den'])} "
             f"| {frac(o['precision'], o['tp'], o['precision_den'])} "
             f"| {frac(o['recall'], o['tp'], o['recall_den'])} "
             f"| {frac(o['accuracy'], o['tp'] + o['tn'], o['accuracy_den'])} "
             f"| {pc(o['gave_verdict'])} | - |")
    return "\n".join(L)


def md_real(r):
    L = [f"| tier | LLM calls (n, %) | IMPOSSIBLE verdicts (confirmed / false / unaudited) | audited precision | ACHIEVABLE | UNKNOWN+ERROR | gave a verdict | est. tokens |",
         "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for t in TIERS:
        m = r["tiers"][t]
        v = m["verdicts"]
        L.append(f"| {TIER_NAME[t]} | {m['llm_calls']} ({pc(m['llm_calls_pct'])}) "
                 f"| {m['impossible']} ({m['confirmed']} / {m['false_refutation']} / {m['unaudited']}) "
                 f"| {frac(m['audited_precision'], m['confirmed'], m['audited_den'])} "
                 f"| {v.get('ACHIEVABLE', 0)} | {v.get('UNKNOWN', 0) + v.get('ERROR', 0)} "
                 f"| {pc(m['gave_verdict'])} ({m['gave_n']} of {m['n']}) | {m['tokens']:,} |")
    o = r["oracle"]
    v = o["verdicts"]
    L.append(f"| audit oracle | - | {o['impossible']} ({o['confirmed']} / {o['false_refutation']} / {o['unaudited']}) "
             f"| {frac(o['audited_precision'], o['confirmed'], o['audited_den'])} | {v.get('ACHIEVABLE', 0)} "
             f"| {v.get('UNKNOWN', 0) + v.get('ERROR', 0)} | {pc(o['gave_verdict'])} | - |")
    return "\n".join(L)


def md_disagree_labelled(r):
    L = [f"Rows where rule and gpt-5.4 disagree: {r['disagree_n']} of {r['labelled']} labelled.", "",
         "| rule | gpt-5.4 | truth | n |", "|---|---|---|---:|"]
    for x in r["disagree_crosstab"]:
        L.append(f"| {x['rule']} | {x['llm']} | {x['truth']} | {x['n']} |")
    for key, title in (("disagree_by_input_type", "input_type"), ("disagree_by_suite", "suite")):
        L += ["", f"| {title} | labelled | disagree | rule right | gpt-5.4 right | neither |", "|---|---:|---:|---:|---:|---:|"]
        for k, v in r[key].items():
            L.append(f"| {k} | {v['labelled']} | {v['disagree']} | {v['rule_right']} | {v['llm_right']} | {v['neither_right']} |")
    L += ["", "| gpt-5.4 false alarm | form | rule-based said | rule reason | gpt-5.4 reason |", "|---|---|---|---|---|"]
    for f in r["llm_false_alarms"]:
        L.append(f"| {f['id']} ({f['name']}) | {f['input_type']} | {f['rule_verdict']} | {f['rule_reason']} | {f['llm_reason']} |")
    return "\n".join(L)


def md_disagree_real(r):
    L = [f"Rows where rule and gpt-5.4 disagree: {r['disagree_n']} of {r['inputs']}.", "",
         "| rule | gpt-5.4 | audit of the gpt-5.4 IMPOSSIBLE | n |", "|---|---|---|---:|"]
    for x in r["disagree_crosstab"]:
        L.append(f"| {x['rule']} | {x['llm']} | {x['llm_audit'] or '-'} | {x['n']} |")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--labelled-rule", type=Path, default=APP / "benchmark-results.json")
    ap.add_argument("--labelled-llm", type=Path, default=APP / "benchmark-results-llm.json")
    ap.add_argument("--real-rule", type=Path, default=APP / "real-benchmark-results.json")
    ap.add_argument("--real-llm", type=Path, default=APP / "real-benchmark-results-llm.json")
    ap.add_argument("--data-root", type=Path, default=None,
                    help="checkout of gc/data_train_test (for source text lengths); without it every "
                         "input is priced at the typical pack size + system prompt only")
    ap.add_argument("--env", choices=("home", "observed"), default="home",
                    help="which environment's verdict block to use for real files (default home, as the report)")
    ap.add_argument("--json", type=Path, default=None, metavar="OUT", help="write all numbers here")
    a = ap.parse_args()

    lab = run_labelled(a.labelled_rule, a.labelled_llm, a.data_root)
    real = run_real(a.real_rule, a.real_llm, a.data_root, a.env)
    print("## Labelled topics\n\n" + md_labelled(lab) + "\n\n" + md_disagree_labelled(lab))
    print(f"\n## Real files ({a.env} environment)\n\n" + md_real(real) + "\n\n" + md_disagree_real(real))
    if a.json:
        a.json.write_text(json.dumps({"labelled": lab, "real": real}, indent=2, default=str), encoding="utf-8")
        print(f"\nwrote {a.json}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Repairs for the 18 real severity protocols (benchmarks/severity_real).

For every case this regenerates, deterministically and without a model:

  pack_enforced.json   result_enforced.json   the policy-only rules moved into the tool
                                              (a precondition `pre` on the capability they protect)
  pack_narrowed.json   result_narrowed.json   the tool's own narrowing repair applied
  repairs_summary.json                        numbers behind the table
  REPAIRS.md                                  the write-up (rules moved, table, paragraphs)

Usage: PYTHONPATH=src python3 scripts/severity_repairs.py [--check]
(--check regenerates in memory and fails if a shipped file differs.)
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from skillc.checker import initial_state                      # noqa: E402
from skillc.pack import Pack                                  # noqa: E402
from skillc.severity import SeverityAnalyzer, analyze, CATASTROPHIC  # noqa: E402

REAL = ROOT / "benchmarks" / "severity_real"
KMAX = 4
MAX_ROUNDS = 12

MOVED, ENFORCED, CANNOT = "moved", "enforced", "cannot"

# ---------------------------------------------------------------------------
# Rules per case.  status:
#   moved     policy-only rule (explicit guard, no `pre`): its condition becomes a precondition of `cap`
#   enforced  the source tool already checks it (it is in the pack's `pre` today); nothing to do
#   cannot    stays a guard: not expressible as a tool precondition
# `late` marks a condition whose atoms can change between the choice and the action
# (the condition is then read as it holds at the action).
# ---------------------------------------------------------------------------
CONFIRM_WHY = ("a user answer (\"yes\"): the tool cannot observe what the user said, only the agent "
               "reports it, so a `pre` on it would check the agent's own claim; it stays the agent's "
               "execute/hold choice")
NOT_VENDORED = "tool code not vendored (tau2-bench): treated as policy-only"
NO_TOOL = "no tool code (role file states no precondition on the action)"


def R(id, policy, status, cap=None, pre=None, source="", why="", late="", sens=None):
    return dict(id=id, policy=policy, status=status, cap=cap, pre=pre, source=source,
                why=why, late=late, sens=sens)


def _or(*a):
    return {"or": list(a)}


def _and(*a):
    return {"and": list(a)}


def _not(a):
    return {"not": a}


CONFIRM_SENS = "confirmed"

RULES = {
    "airline_baggage_update": [
        R("no-removal", "L48 \"The user can add but not remove checked bags.\"", MOVED,
          "update_reservation_baggages", "req_add_bags",
          "not enforced: the tool overwrites total_baggages, so a removal passes"),
        R("confirm", "L7 explicit user confirmation (yes) before editing baggage", CANNOT,
          source="user answer", why=CONFIRM_WHY, sens=CONFIRM_SENS),
    ],
    "airline_book_reservation": [
        R("max-5-pax", "L32 \"Each reservation can have at most five passengers.\"", MOVED,
          "book_reservation", "pax_ok", "not enforced: the tool does not count passengers"),
        R("payment-mix", "L34 \"at most one travel certificate, at most one credit card, and at most three gift cards\"",
          MOVED, "book_reservation", "pay_ok",
          "not enforced for the per-kind counts; the profile / balance part (pay_bad_tool) is enforced"),
        R("payment-profile", "L34 \"All payment methods must already be in user profile\"", ENFORCED,
          source="enforced (pre = not pay_bad_tool)"),
        R("confirm", "L7 explicit user confirmation (yes) before booking", CANNOT,
          source="user answer", why=CONFIRM_WHY, sens=CONFIRM_SENS),
    ],
    "airline_cancel_reservation": [
        R("not-flown", "L60 \"The agent can only cancel the whole trip that is not flown.\"", MOVED,
          "cancel_reservation", "not_flown", "not enforced: the tool only checks that the reservation exists"),
        R("grounds", "L58 cancellable within 24 h, airline-cancelled, business, or insured with a covered reason",
          MOVED, "cancel_reservation", "eligible",
          "not enforced (\"The API does not check these for the agent\")"),
    ],
    "airline_change_cabin": [
        R("none-flown", "L116 \"Cabin cannot be changed if any flight in the reservation has already been flown.\"",
          MOVED, "change_cabin", "none_flown", NOT_VENDORED),
        R("whole-reservation", "L118 \"Cabin class must remain the same across all the flights in the same reservation\"",
          MOVED, "change_cabin", "whole_reservation", NOT_VENDORED),
        R("confirm", "L7 explicit user confirmation (yes) before changing cabin class", CANNOT,
          source="user answer", why=CONFIRM_WHY, sens=CONFIRM_SENS),
    ],
    "airline_compensation": [
        R("only-if-asked", "L155 \"Do not proactively offer a compensation unless the user explicitly asks for one.\"",
          MOVED, "send_certificate", "asked", NOT_VENDORED),
        R("profile", "L157/L161 compensate only silver/gold members, travel insurance or business", MOVED,
          "send_certificate", "profile_ok", NOT_VENDORED),
        R("reason-and-amount",
          "L163/L165/L167 $100 x passengers for cancelled flights, $50 x passengers for delayed flights "
          "with a change or cancellation, no other reason", MOVED, "send_certificate",
          _or(_and("reason_cancelled", "amt_100"), _and("reason_delayed", "amt_50")), NOT_VENDORED,
          late="amt_100 / amt_50 are set by the quote act after the choice; read at the action"),
    ],
    "airline_modify_flights": [
        R("no-basic-economy", "L44 \"Basic economy flights cannot be modified.\"", MOVED,
          "update_reservation_flights", "other_cabin",
          "not enforced (\"The API does not check these for the agent\")"),
        R("route-unchanged", "L44 \"... without changing the origin, destination, and trip type.\"", MOVED,
          "update_reservation_flights", "route_unchanged", "not enforced (same sentence)"),
        R("payment", "L52 one gift card or credit card as payment/refund method", ENFORCED,
          source="enforced (pre = pay_valid)"),
        R("confirm", "L7 explicit user confirmation (yes) before modifying flights", CANNOT,
          source="user answer", why=CONFIRM_WHY, sens=CONFIRM_SENS),
    ],
    "retail_cancel_pending_order": [
        R("authentication", "L5 authenticate the user (email, or name + zip) before any action", MOVED,
          "cancel_pending_order", "auth_ok", "not enforced: no retail tool checks authentication"),
        R("status-pending", "L35 \"An order can only be cancelled if its status is 'pending'\"", ENFORCED,
          source="enforced (pre includes status_pending)"),
        R("reason", "L37 reason 'no longer needed' or 'ordered by mistake'", ENFORCED,
          source="enforced (pre includes reason_ok)"),
        R("confirm", "L11 explicit user confirmation (yes) before cancelling", CANNOT,
          source="user answer", why=CONFIRM_WHY, sens=CONFIRM_SENS),
    ],
    "retail_exchange_delivered_order": [
        R("authentication", "L5 authenticate the user (email, or name + zip) before any action", MOVED,
          "exchange_delivered_order_items", "auth_ok", "not enforced: no retail tool checks authentication"),
        R("status-delivered", "L75 only a 'delivered' order can be exchanged", ENFORCED,
          source="enforced (pre includes status_delivered)"),
        R("items-same-product", "L77 same product, different option", ENFORCED,
          source="enforced (pre includes items_ok)"),
        R("payment-covers", "L79 gift card must cover the price difference", ENFORCED,
          source="enforced (pre includes pay_ok)"),
        R("confirm-all-items", "L11 explicit yes; L75 \"remind the customer to confirm they have provided all items\"; "
          "L31 the tool can be called once", CANNOT, source="user answer", why=CONFIRM_WHY + "; the "
          "all-items-given answer is the same user answer", sens=CONFIRM_SENS),
    ],
    "retail_modify_pending_items": [
        R("authentication", "L5 authenticate the user (email, or name + zip) before any action", MOVED,
          "modify_pending_order_items", "auth_ok", "not enforced: no retail tool checks authentication"),
        R("status-pending", "L43 only a 'pending' order can be modified", ENFORCED,
          source="enforced (pre includes status_pending)"),
        R("items-same-product", "L59 same product, different option", ENFORCED,
          source="enforced (pre includes items_ok)"),
        R("payment-covers", "L61 gift card must cover the price difference", ENFORCED,
          source="enforced (pre includes pay_ok)"),
        R("confirm-all-items", "L11 explicit yes; L57 \"remind the customer to confirm they have provided all "
          "items\"; L31 the tool can be called once", CANNOT, source="user answer",
          why=CONFIRM_WHY + "; the all-items-given answer is the same user answer", sens=CONFIRM_SENS),
    ],
    "retail_return_delivered_order": [
        R("authentication", "L5 authenticate the user (email, or name + zip) before any action", MOVED,
          "return_delivered_order_items", "auth_ok", "not enforced: no retail tool checks authentication"),
        R("status-delivered", "L65 only a 'delivered' order can be returned", ENFORCED,
          source="enforced (pre includes status_delivered)"),
        R("refund-destination", "L69 refund to the original payment method or an existing gift card", ENFORCED,
          source="enforced (pre includes dest_ok)"),
        R("confirm", "L11 explicit user confirmation (yes) before returning", CANNOT,
          source="user answer", why=CONFIRM_WHY, sens=CONFIRM_SENS),
    ],
    "telecom_refuel_data": [
        R("usage-exceeded", "tech_support_workflow L176-181 / main_policy L132 refuel only if the data usage exceeds the limit",
          MOVED, "refuel_data", "usage_exceeded",
          "not enforced: refuel_data checks only that the amount is positive and the plan exists"),
        R("max-2gb", "main_policy L134 \"The maximum amount of data that can be refueled is 2GB.\"", MOVED,
          "refuel_data", "amount_ok", "not enforced (same tool)"),
        R("confirm-price", "L137 \"Confirm the price.\"", CANNOT, source="user answer", why=CONFIRM_WHY,
          sens=CONFIRM_SENS),
    ],
    "telecom_overdue_payment_resume": [
        R("bill-overdue", "L105 / L117 \"You should always check that the bill is overdue before sending a payment "
          "request.\" (the send tool leads to make_payment, the declared irreversible action; the pre goes on the "
          "tool the guard protects)", MOVED, "send_payment_request", "bill_overdue",
          "not enforced (\"will not check if the bill is overdue\")"),
        R("contract-valid", "L126 \"You are not allowed to lift the suspension if the line's contract end date is in "
          "the past\" (resume_line is not declared irreversible: no effect on k*)", MOVED, "resume_line",
          "contract_ok", "not enforced"),
    ],
    "pr_review_merge": [
        R("quality-clear", "CodeReviewer: \"Critical findings block the merge: ... wait for a revision before "
          "re-reviewing\"", MOVED, "merge", _or(_not("quality_defect"), "quality_fixed"), NO_TOOL,
          late="quality_fixed is set after the choice (the fix act); read at the merge"),
        R("security-clear", "SecurityReviewer: \"Ready for Production: No\" while findings are open", MOVED, "merge",
          _or(_not("security_vuln"), "security_fixed"), NO_TOOL,
          late="security_fixed is set after the choice; read at the merge"),
    ],
    "doc_coauthor_ship": [
        R("reader-test-clear", "DocLead: only once the reader answers correctly and no new gaps turn up is the "
          "document ready", MOVED, "ship", _or(_not("draft_has_gaps"), "draft_revised"), NO_TOOL,
          late="draft_revised is set after the choice; read at the ship"),
    ],
    "sdlc_release_gate": [
        R("reviews-pass", "Merger (case description): ships only after all four reviews pass", MOVED, "deploy",
          _or(_not("open_findings"), "findings_addressed"), NO_TOOL,
          late="findings_addressed is set after the choice; read at the deploy"),
    ],
    "sdlc_release_gate_concurrent": [
        R("reviews-pass", "Merger (protocol header): any NO -> revise, all four OK -> deploy", MOVED, "deploy",
          _or(_not("open_findings"), "findings_addressed"), NO_TOOL,
          late="findings_addressed is set after the choice; read at the deploy"),
    ],
    "sdlc_release_gate_concurrent_withhold": [
        R("reviews-pass", "Merger (protocol header): any NO -> revise, all four OK -> deploy", MOVED, "deploy",
          _or(_not("open_findings"), "findings_addressed"), NO_TOOL,
          late="findings_addressed is set after the choice; read at the deploy"),
        R("reject-unfixable", "reject branch iff the findings are unresolvable (a refusal, not a gate on an action)",
          CANNOT, source="not a precondition", why="the reject branch is the safe terminal, not a rule an action "
          "must satisfy; nothing is moved"),
    ],
    "gem_dev_team": [
        R("critic-on-high-risk", "gem-orchestrator: delegate to gem-critic \"only if: High-risk signal exists\"; "
          "a high-risk change is not deployed without the critique", MOVED, "deploy",
          _or(_not("high_risk"), "critiqued"),
          "not enforced: gem-devops' Pre-Deploy list (tests passing, code review, ...) does not mention the critic",
          late="critiqued is set after the choice; read at the deploy"),
        R("plan-approved-tests-green", "gem-devops Pre-Deploy: tests passing, code review", ENFORCED,
          source="enforced (pre = plan_approved and (not tests_red or replanned))"),
    ],
}

SOURCES = {
    "pr_review_merge": "awesome-copilot", "doc_coauthor_ship": "anthropics/skills",
    "sdlc_release_gate": "awesome-copilot", "sdlc_release_gate_concurrent": "awesome-copilot",
    "sdlc_release_gate_concurrent_withhold": "awesome-copilot", "gem_dev_team": "awesome-copilot",
    "airline_baggage_update": "tau airline", "airline_book_reservation": "tau airline",
    "airline_cancel_reservation": "tau airline", "airline_change_cabin": "tau2 airline",
    "airline_compensation": "tau2 airline", "airline_modify_flights": "tau airline",
    "retail_cancel_pending_order": "tau retail", "retail_exchange_delivered_order": "tau retail",
    "retail_modify_pending_items": "tau retail", "retail_return_delivered_order": "tau retail",
    "telecom_overdue_payment_resume": "tau2 telecom", "telecom_refuel_data": "tau2 telecom",
}


# ---------------------------------------------------------------------------
# enforcement
# ---------------------------------------------------------------------------
def conj(existing, extra):
    parts = []
    for f in [existing] + list(extra):
        if f is None or f is True:
            continue
        if isinstance(f, dict) and list(f) == ["and"]:
            parts += f["and"]
        else:
            parts.append(f)
    if not parts:
        return True
    return parts[0] if len(parts) == 1 else {"and": parts}


def enforce(pack, rules, with_confirmation=False):
    p = copy.deepcopy(pack)
    add = {}
    for r in rules:
        if r["status"] == MOVED:
            add.setdefault(r["cap"], []).append(r["pre"])
        elif with_confirmation and r["sens"]:
            add.setdefault(_irreversible_cap(pack), []).append(r["sens"])
    for cap, extra in add.items():
        c = p["capabilities"][cap]
        c["pre"] = conj(c.get("pre"), extra)
    p["name"] = pack["name"] + ("_enforced_plus_confirmation" if with_confirmation else "_enforced")
    return p


def _irreversible_cap(pack):
    return pack["irreversible"][0]


# ---------------------------------------------------------------------------
# narrowing: remove the branches the tool names, context-sensitively
# ---------------------------------------------------------------------------
_fresh = [0]


def _rename_continue(x, old, new):
    if isinstance(x, list):
        return [_rename_continue(v, old, new) for v in x]
    if isinstance(x, dict):
        if list(x) == ["continue"] and x["continue"] == old:
            return {"continue": new}
        return {k: _rename_continue(v, old, new) for k, v in x.items()}
    return copy.deepcopy(x)


def _leaf(steps, recenv):
    """steps unchanged, except that `continue X` re-enters the loop X as a fresh rec."""
    def sub(x):
        if isinstance(x, list):
            return [sub(v) for v in x]
        if isinstance(x, dict):
            if list(x) == ["continue"]:
                name = x["continue"]
                _fresh[0] += 1
                new = f"{name}_{_fresh[0]}"          # rec names must be unique in a pack
                return {"rec": {"name": new, "body": _rename_continue(recenv[name], name, new)}}
            return {k: sub(v) for k, v in x.items()}
        return x
    return sub(copy.deepcopy(list(steps)))


def apply_narrowing(protocol, narrowing):
    """Remove each (node path, branch) the tool names.  Node paths are those of
    SeverityAnalyzer.hazard_within (indices into the flattened residual), so the
    protocol is unfolded along the named paths (tail duplication, loops unrolled)
    and left unchanged elsewhere."""
    removed = {(n, b) for n, b in narrowing}
    paths = sorted({n for n, _ in narrowing})

    def relevant(node):
        return any(q == node or q.startswith(node + "/") for q in paths)

    def rw(steps, path, recenv):
        out = []
        for i, s in enumerate(steps):
            rest = steps[i + 1:]
            if "choice" in s:
                body = s["choice"]
                node = f"{path}/choice@{body['by']}#{i}"
                if not relevant(node):
                    return out + _leaf(steps[i:], recenv)
                nb = {}
                for label, br in body["branches"].items():
                    if (node, label) in removed:
                        continue
                    nb[label] = rw(list(br) + rest, f"{node}/{label}", recenv)
                c = {k: v for k, v in body.items() if k not in ("branches", "guards", "assumes")}
                c["branches"] = nb
                for key in ("guards", "assumes"):
                    if key in body:
                        c[key] = {l: g for l, g in body[key].items() if l in nb}
                out.append({"choice": c})
                return out
            if "rec" in s:
                name = s["rec"]["name"]
                unf = list(s["rec"]["body"]) + rest
                return out + rw(unf, path, {**recenv, name: unf})
            if "continue" in s:
                return out + rw(recenv[s["continue"]], path, recenv)
            out.append(copy.deepcopy(s))
        return out

    return rw(list(protocol), "", {})


def narrow_to_fixpoint(pack):
    """Apply the tool's narrowing, re-run, repeat until it names nothing (or MAX_ROUNDS)."""
    _fresh[0] = 0
    cur = copy.deepcopy(pack)
    rounds = []
    for _ in range(MAX_ROUNDS):
        rep = analyze(cur, kmax=KMAX).to_dict()
        n = [tuple(x) for x in rep["narrowing"]]
        rounds.append({"branches_named": len(n), "k_star": rep["tolerance_degree"]})
        if not n:
            break
        cur = {**cur, "protocol": apply_narrowing(cur["protocol"], n)}
    cur["name"] = pack["name"] + "_narrowed"
    return cur, rounds


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def volatile(d):
    d = dict(d)
    d.pop("elapsed_s", None)
    return json.loads(json.dumps(d))


def run(pack):
    return volatile(analyze(pack, kmax=KMAX).to_dict())


def goal_reachable(pack):
    p = Pack.load({k: v for k, v in pack.items() if k != "irreversible"})
    a = SeverityAnalyzer(p, kmax=KMAX)
    return a.goal_reachable(list(p.protocol), initial_state(p), {})


def kval(k):
    return float("inf") if k is None else k


def kstr(k):
    return f">={KMAX + 1}" if k is None else str(k)


def dump(obj):
    return json.dumps(obj, indent=1, ensure_ascii=False) + "\n"


def cases():
    return sorted(p.parent.name for p in REAL.glob("*/pack.json"))


def compute(case):
    pack = json.loads((REAL / case / "pack.json").read_text())
    rules = RULES[case]
    orig = json.loads((REAL / case / "result.json").read_text())
    enf = enforce(pack, rules)
    nar, rounds = narrow_to_fixpoint(pack)
    r_enf, r_nar = run(enf), run(nar)
    sens = None
    if any(r["sens"] for r in rules):
        sens = run(enforce(pack, rules, with_confirmation=True))
    return dict(case=case, pack=pack, orig=volatile(orig), enf=enf, nar=nar, r_enf=r_enf, r_nar=r_nar,
                rounds=rounds, sens=sens, goal_ok=dict(
                    orig=goal_reachable(pack), enforced=goal_reachable(enf), narrowed=goal_reachable(nar)))


def summary_row(c):
    o, e, n = c["orig"], c["r_enf"], c["r_nar"]
    rules = RULES[c["case"]]
    return dict(
        case=c["case"], source=SOURCES[c["case"]],
        k_orig=o["tolerance_degree"], k_enforced=e["tolerance_degree"], k_narrowed=n["tolerance_degree"],
        k_enforced_plus_confirmation=None if c["sens"] is None else c["sens"]["tolerance_degree"],
        rules_moved=[r["id"] for r in rules if r["status"] == MOVED],
        rules_cannot=[r["id"] for r in rules if r["status"] == CANNOT],
        pnr_orig=o["pnr_action"], pnr_enforced=e["pnr_action"], pnr_narrowed=n["pnr_action"],
        counts_orig=o["counts"], counts_enforced=e["counts"], counts_narrowed=n["counts"],
        narrowing_branches=len(o["narrowing"]), narrowing_rounds=c["rounds"],
        goal_reachable=c["goal_ok"], sensitivity_confirmation=c["sens"] is not None)


# ---------------------------------------------------------------------------
# REPAIRS.md
# ---------------------------------------------------------------------------
def fmt_counts(d):
    return f"{d.get('Benign', 0)} / {d.get('Futile', 0)} / {d.get('Catastrophic', 0)}"


def fmt_pre(f):
    if isinstance(f, str):
        return f
    (op, args), = f.items()
    if op == "not":
        return f"not {fmt_pre(args)}" if isinstance(args, str) else f"not ({fmt_pre(args)})"
    return "(" + f" {op} ".join(fmt_pre(a) for a in args) + ")"


def render(rows, data):
    n = len(rows)
    raised = [r for r in rows if kval(r["k_enforced"]) > kval(r["k_orig"])]
    raised_inf = [r for r in raised if r["k_enforced"] is None]
    still0 = [r for r in rows if r["k_enforced"] == 0]
    nar_raised = [r for r in rows if kval(r["k_narrowed"]) > kval(r["k_orig"])]
    sens_rows = [r for r in rows if r["sensitivity_confirmation"]]
    sens_raised = [r for r in sens_rows if kval(r["k_enforced_plus_confirmation"]) > kval(r["k_enforced"])]
    L = []
    L += ["# Repairs on the real protocols: what the analysis buys an engineer", "",
          "Generated by `scripts/severity_repairs.py` from `<case>/pack.json` (deterministic, no model, no network); "
          "`tests/test_severity.py` checks that the shipped `pack_*.json` / `result_*.json` are current. "
          f"kmax = {KMAX} throughout; k* is the tolerance degree, and \"k* >= {KMAX + 1}\" means no hazard is "
          f"reachable within the tested budgets 0..{KMAX} (the tool reports it as null).", "",
          "## Two repairs, and how they differ", "",
          "**ENFORCE** moves a rule from the policy text into the tool: for every explicit guard that "
          "`PROVENANCE.md` says the source tool does not check, the guard's condition becomes a precondition "
          "(`pre`, conjoined with any existing one) of the capability it protects, exactly as the source tool "
          "code does for the rules it does enforce. Nothing else changes: every choice, branch and guard stays. "
          "**NARROW** is the tool's own repair (`skillc severity` prints it): remove the branches it names "
          "(every Catastrophic misselection) from the protocol. Narrowing removes choices, so the agent can no "
          "longer take the wrong branch at all; enforcement keeps every choice but makes the irreversible "
          "capability refuse when a rule is violated, so the wrong branch is still takeable and becomes a "
          "detour or a dead end (Benign or Futile) instead of a point of no return. In practice narrowing "
          "changes the protocol (the agent loses the ability to act on its own judgement at that node, and "
          "the engineer must know which branch is wrong), whereas enforcement changes the tool and leaves "
          "the protocol, and any agent following it, as it is. Both can only remove runs, so by the "
          "anti-monotonicity and narrowing-soundness arguments of Sections 6 and 11, hazard reachability "
          "can only shrink and k* cannot fall (asserted per case in `tests/test_severity.py`).", "",
          "Conditions that change between the choice and the action are read as they hold at the action "
          "(marked *late* below). Every enforced precondition is a conjunction of atoms the pack already "
          "uses; no atom and no capability was added. Narrowing is applied context-sensitively (the "
          "protocol is unfolded along the paths the tool names) and repeated until the tool names no more "
          "branches; the number of rounds is in the table.", "",
          "## Summary", "",
          "k* = tolerance degree; PNR = point-of-no-return action (the irreversible action reached by the "
          "witness); verdicts are Benign / Futile / Catastrophic over all branches. \"Moved\" = policy-only "
          "rules turned into preconditions; \"cannot\" = rules left as guards. PNR after repair is `-` when "
          "no hazard is reachable within the tested budgets.", "",
          "| case | source | k* original | k* enforced | k* narrowed | rules moved | cannot enforce | PNR before | PNR after (enforced) | "
          "verdicts before B/F/C | verdicts enforced B/F/C | verdicts narrowed B/F/C | narrowing applications |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['case']} | {r['source']} | {kstr(r['k_orig'])} | {kstr(r['k_enforced'])} | "
                 f"{kstr(r['k_narrowed'])} | {', '.join(r['rules_moved']) or '-'} | "
                 f"{', '.join(r['rules_cannot']) or '-'} | {r['pnr_orig']} | {r['pnr_enforced'] or '-'} | "
                 f"{fmt_counts(r['counts_orig'])} | {fmt_counts(r['counts_enforced'])} | "
                 f"{fmt_counts(r['counts_narrowed'])} | {len(r['narrowing_rounds']) - 1} |")
    L += ["", "### Sensitivity (not shipped as packs): what if the confirmation were also a precondition", "",
          "If the explicit-yes answer were recorded by the system and checked by the tool (a different "
          "architecture from the source tools; the answer is only reported by the agent today), "
          "adding `confirmed` to the irreversible action's `pre` would give:", "",
          "| case | k* enforced | k* enforced + confirmation |", "|---|---|---|"]
    for r in sens_rows:
        L.append(f"| {r['case']} | {kstr(r['k_enforced'])} | {kstr(r['k_enforced_plus_confirmation'])} |")
    L += ["", "## What enforcing the policy-only rules buys", ""]
    L.append(
        f"Of the {n} protocols, enforcing the policy-only rules raises k* above 0 for {len(raised)} "
        f"({', '.join(r['case'] for r in raised) or 'none'}); "
        f"{len(raised_inf)} of them reach k* >= {KMAX + 1} (no hazard within the tested budgets)"
        + ("" if len(raised_inf) == len(raised) else
           ", the others " + ", ".join(f"{r['case']} to {kstr(r['k_enforced'])}" for r in raised if r['k_enforced'] is not None))
        + f". {len(still0)} protocols stay at k* = 0 "
        f"({', '.join(r['case'] for r in still0) or 'none'}). ")
    L.append("")
    L.append(data["remaining_paragraph"])
    L += ["", f"Narrowing, for comparison, raises k* above 0 for {len(nar_raised)} of the {n} protocols "
          f"({', '.join(f'{r['case']} to {kstr(r['k_narrowed'])}' for r in nar_raised) or 'none'}); "
          "it removes every Catastrophic branch the tool names, including the explicit-yes `execute` "
          "branch after a `not_yes` answer, which enforcement cannot touch.", ""]
    L += ["## Rules per case", "",
          "Status: *moved* = policy-only, now a `pre` in `pack_enforced.json`; *enforced* = the source tool "
          "already checks it (already in `pre`); *cannot* = stays a guard.", ""]
    for r in rows:
        c = r["case"]
        L += [f"### {c}", ""]
        caps = {}
        for ru in RULES[c]:
            if ru["status"] == MOVED:
                caps.setdefault(ru["cap"], []).append(ru)
        L += ["| rule | policy sentence | source-tool status | repair |", "|---|---|---|---|"]
        for ru in RULES[c]:
            if ru["status"] == MOVED:
                rep = f"moved: `{ru['cap']}.pre` += `{fmt_pre(ru['pre'])}`" + (f" ({ru['late']})" if ru["late"] else "")
            elif ru["status"] == ENFORCED:
                rep = "none needed"
            else:
                rep = "left as a guard: " + ru["why"]
            L.append(f"| {ru['id']} | {ru['policy']} | {ru['source']} | {rep} |")
        L.append("")
        e = data["cases"][c]
        L.append(f"k* {kstr(r['k_orig'])} -> {kstr(r['k_enforced'])} (enforced), -> {kstr(r['k_narrowed'])} (narrowed, "
                 f"{r['narrowing_branches']} branches named by the tool, {len(r['narrowing_rounds']) - 1} application round(s) until it names none); "
                 f"PNR {r['pnr_orig']} -> {r['pnr_enforced'] or 'none within budget'}; "
                 f"verdicts {fmt_counts(r['counts_orig'])} -> {fmt_counts(r['counts_enforced'])}. "
                 f"{e}")
        L.append("")
    return "\n".join(L) + "\n"


def remaining_paragraph(rows):
    still0 = [r for r in rows if r["k_enforced"] == 0]
    conf = [r for r in still0 if "confirm" in " ".join(r["rules_cannot"]) or r["rules_cannot"]]
    no_conf = [r for r in still0 if not r["rules_cannot"]]
    cases = ", ".join(r["case"] for r in conf)
    txt = (f"What remains is, in every one of the {len(conf)} protocols that stay at k* = 0 and has an explicit "
           f"confirmation ({cases}), the confirmation step itself: the user's answer is not a fact the tool can "
           "check, so an `execute` after a `not_yes` answer is still one misselection from the irreversible action "
           "(the hazard witness of each is `...not_yes, execute, <action>`). ")
    if no_conf:
        txt += (f"{', '.join(r['case'] for r in no_conf)} stay at k* = 0 without a confirmation node; see their "
                "entries. ")
    txt += ("The nine protocols that rise are those with no confirmation step to leave behind: the three tau "
            "policies that name none (cancellation, compensation, overdue payment) and the six ProtoGuard "
            "protocols, whose skills state none. Two caveats: for the six ProtoGuard protocols the moved rule is "
            "the engineer's choice (the source role files state the condition but no tool enforces it, so the "
            "repair is a proposal about the tool, not a re-reading of existing tool code); and enforcement turns "
            "former Catastrophic branches into Futile ones (the run is stuck at the refusing tool, the goal is "
            "lost, nothing irreversible happened), so the protocol is safer, not more successful. ")
    txt += ("The sensitivity table shows what closing even that would give. The engineering reading: the analysis "
            "points, per protocol, at the gates whose rule lives only in the policy text; moving those into the "
            "tool is a local code change that raises k*, and the residual k* = 0 is exactly the part that "
            "needs a different mechanism (a system-recorded confirmation, or an irreversibility window).")
    return txt


def case_notes(rows, cmap):
    notes = {}
    for r in rows:
        c = r["case"]
        parts = []
        if r["k_enforced"] == 0:
            w = cmap[c]["r_enf"]["hazard_witness"]
            labels = [x[1] for x in w if x[0] == "choose"]
            parts.append("Remaining hazard witness (choices): " + (", ".join(labels) or "none") + ".")
        notes[c] = " ".join(parts)
    return notes


def build():
    cmap = {c: compute(c) for c in cases()}
    rows = [summary_row(cmap[c]) for c in cases()]
    data = dict(cases=case_notes(rows, cmap), remaining_paragraph=remaining_paragraph(rows))
    files = {}
    for c, x in cmap.items():
        d = REAL / c
        files[d / "pack_enforced.json"] = dump(x["enf"])
        files[d / "result_enforced.json"] = dump(x["r_enf"])
        files[d / "pack_narrowed.json"] = dump(x["nar"])
        files[d / "result_narrowed.json"] = dump(x["r_nar"])
    files[REAL / "repairs_summary.json"] = dump(rows)
    files[REAL / "REPAIRS.md"] = render(rows, data)
    return cmap, rows, files


def main(argv):
    cmap, rows, files = build()
    if "--check" in argv:
        bad = [str(p) for p, t in files.items() if not p.exists() or p.read_text() != t]
        print("stale: " + ", ".join(bad) if bad else "current")
        return 1 if bad else 0
    for p, t in files.items():
        p.write_text(t)
    for r in rows:
        print(f"{r['case']:42s} k* {kstr(r['k_orig']):>3} -> enf {kstr(r['k_enforced']):>3}  nar {kstr(r['k_narrowed']):>3}"
              f"  rounds {[x['branches_named'] for x in r['narrowing_rounds']]}  goal {r['goal_reachable']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

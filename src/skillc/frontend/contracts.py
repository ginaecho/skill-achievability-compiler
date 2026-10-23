"""Replace an intent's assumed tool behaviour with the environment's contracts.

An intent can only assume what its tools do; the environment decides. When the
environment publishes formal contracts (pre / add / del / nondet / assigns) for
the tools it grants, the binder substitutes them for the intent's assumed
definitions, so the checker judges the intent's plan against what the tools
actually do.

Substitution is sound only when the intent's goal and initial state are written
in the environment's state vocabulary; otherwise an environment effect named
`confirmation_sent` could not establish an intent goal named `sent`, and the
checker would refute a plan that may well succeed. In that case nothing is
substituted and the unaligned names are reported, so the result can only fall
back to the existence-only binding, never become a false refutation.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass

from ..formula import atoms, numeric_vars
from ..pack import validate_pack

CONTRACT_FIELDS = ("pre", "add", "del", "nondet", "assigns")


def abstain_outside_vocabulary(verdict, states):
    """abstain_ungrounded with only the environment's state vocabulary."""
    return abstain_ungrounded(verdict, states=states)


def abstain_ungrounded(verdict, *, states=None, source_text=None, extracted=(), pack=None):
    """Turn a refutation whose deciding names appear in no input into UNKNOWN.

    A refutation is evidence only if it names something the inputs contain:
      * GOAL_UNSAT names goal conditions nothing establishes, and BLOCKED_GUARD
        names capabilities whose guard conditions nothing establishes. If the
        environment publishes a state vocabulary (even an empty one), conditions
        are grounded only in it; otherwise in the intent text, as whole identifiers.
      * MISSING_CAPABILITY names absent tools. A tool is grounded if the intent
        text names it or deterministic extraction took it from the text.
    When no deciding name is grounded, a compactor invented it (e.g.
    `card_selected`, `provide_triage_plan`), so the refutation is about the
    compaction, not the intent, and the checker abstains. Without any
    grounding evidence the verdict is unchanged. Other reasons are untouched.
    """
    from ..checker import Verdict

    if not verdict.refuted:
        return verdict
    names = [str(name) for name in verdict.frontier]
    if verdict.reason == "BLOCKED_GUARD":
        names = _blocked_guard_conditions(names, pack)
    elif verdict.reason == "GOAL_UNSAT" and not names and pack:
        names = sorted(atoms(pack["goal"]) | numeric_vars(pack["goal"]))
    if verdict.reason in CONDITION_REASONS and names and states is not None:
        grounded, reason = (lambda name: name in states), "UNALIGNED_CONDITION"
    elif verdict.reason in CONDITION_REASONS and names and source_text:
        grounded, reason = (lambda name: _mentions(source_text, name)), "UNALIGNED_CONDITION"
    elif verdict.reason == "MISSING_CAPABILITY" and source_text:
        grounded = lambda name: name in extracted or _mentions(source_text, name)  # noqa: E731
        reason = "UNGROUNDED_TOOL"
    else:
        return verdict
    if any(grounded(name) for name in names):
        return verdict
    listed = ", ".join(names)
    return Verdict(
        False, reason,
        f"{verdict.reason} rests only on names that appear in neither the intent "
        f"nor the environment ({listed}); the compaction must be grounded before deciding",
        frontier=verdict.frontier, unknown=True, semantics=verdict.semantics,
        pack_digest=verdict.pack_digest, decision_scope=verdict.decision_scope,
        protocol=verdict.protocol, protocol_reason=verdict.protocol_reason,
        protocol_detail=verdict.protocol_detail,
        assumed_conformant=verdict.assumed_conformant)


CONDITION_REASONS = ("GOAL_UNSAT", "BLOCKED_GUARD")
_BLOCKED_CAPABILITY_RE = re.compile(r"capability '([^']+)'")


def _mentions(text: str, name: str) -> bool:
    """Whether `text` contains `name` as a whole identifier (case-insensitive)."""
    pattern = rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])"
    return re.search(pattern, text, re.IGNORECASE) is not None


def _blocked_guard_conditions(frontier: list[str], pack: dict | None) -> list[str]:
    """Condition names (Boolean atoms and numeric variables) in the guards of the
    capabilities a BLOCKED_GUARD names."""
    if not pack:
        return []
    capabilities = pack.get("capabilities", {})
    names = set()
    for entry in frontier:
        for capability in _BLOCKED_CAPABILITY_RE.findall(entry):
            guard = capabilities.get(capability, {}).get("pre", True)
            names |= atoms(guard) | numeric_vars(guard)
    return sorted(names)


@dataclass(frozen=True)
class ContractBinding:
    pack: dict
    applied: tuple[str, ...]
    unaligned: tuple[str, ...]
    dropped: tuple[str, ...] = ()   # names of init constraints outside the vocabulary
    renamed: tuple[tuple[str, str], ...] = ()   # (pack atom, contract atom) by alignment


@dataclass(frozen=True)
class Alignment:
    pack: dict
    renamed: tuple[tuple[str, str], ...]     # (pack atom, environment atom)
    dropped_init: tuple[str, ...]            # init_true names outside the vocabulary


def _rename_formula(f, names: dict):
    if isinstance(f, str):
        return names.get(f, f)
    if isinstance(f, dict):
        if "and" in f or "or" in f:
            key = "and" if "and" in f else "or"
            return {**f, key: [_rename_formula(x, names) for x in f[key]]}
        if "not" in f:
            return {**f, "not": _rename_formula(f["not"], names)}
    return f


def _rename_steps(steps, names: dict) -> None:
    """Rename predicates in protocol (or behaviour) steps in place: goal markers,
    branch assumptions and message labels."""
    if isinstance(steps, list):
        for s in steps:
            _rename_steps(s, names)
        return
    if not isinstance(steps, dict):
        return
    for key, value in list(steps.items()):
        if key == "goal":
            steps[key] = _rename_formula(value, names)
        elif key == "label" and isinstance(value, str):
            steps[key] = names.get(value, value)
        elif key == "assumes" and isinstance(value, dict):
            steps[key] = {lbl: [names.get(p, p) for p in preds] for lbl, preds in value.items()}
        else:
            _rename_steps(value, names)


def align_to_contracts(pack: dict, contracts: dict, states: Iterable[str]) -> Alignment:
    """Alignment through bindings (PLAN Addendum E-e).

    A pack capability bound to an environment tool (same name, as the binder
    leaves it) whose contract adds exactly one atom `q` of the state vocabulary,
    and which itself adds exactly one atom `p` that no other pack capability
    adds, establishes what the tool establishes: `p` is renamed `q` everywhere
    in the pack (goal, guards, effects, init, goal markers, branch assumptions,
    message labels).  No rename when `p` is already a vocabulary name, when `q`
    is already used by the pack, or when two pack atoms would map to the same
    `q`.  Pack `init_true` names still outside the vocabulary are dropped (the
    environment's initial state replaces them once contracts apply).  Names
    left outside the vocabulary keep the pack unaligned."""
    vocabulary = set(states)
    caps = pack.get("capabilities", {})
    adders: dict[str, list[str]] = {}
    for name, cap in caps.items():
        for a in set(cap.get("add", [])):
            adders.setdefault(a, []).append(name)
    used = set(atoms(pack["goal"])) | set(pack.get("init_true", []))
    for cap in caps.values():
        used |= atoms(cap.get("pre", True)) | set(cap.get("add", [])) | set(cap.get("del", []))
    candidates: dict[str, str] = {}
    for name, cap in caps.items():
        contract = contracts.get(name)
        if contract is None:
            continue
        q_add, p_add = set(contract.get("add", [])), set(cap.get("add", []))
        if len(q_add) != 1 or len(p_add) != 1:
            continue
        (q,), (p,) = q_add, p_add
        if p == q or p in vocabulary or q not in vocabulary or q in used:
            continue
        if len(adders.get(p, [])) != 1:
            continue
        candidates[p] = q
    targets = [q for q in candidates.values()]
    names = {p: q for p, q in candidates.items() if targets.count(q) == 1}
    out = deepcopy(pack)
    if names:
        out["goal"] = _rename_formula(out["goal"], names)
        for cap in out["capabilities"].values():
            if "pre" in cap:
                cap["pre"] = _rename_formula(cap["pre"], names)
            for key in ("add", "del"):
                if key in cap:
                    cap[key] = [names.get(a, a) for a in cap[key]]
            if cap.get("nondet"):
                cap["nondet"] = {v: _rename_formula(f, names) for v, f in cap["nondet"].items()}
        if "init_constraints" in out:
            out["init_constraints"] = [_rename_formula(f, names)
                                       for f in out["init_constraints"]]
        _rename_steps(out.get("protocol", []), names)
        if out.get("skills"):
            _rename_steps(out["skills"], names)
    dropped: tuple[str, ...] = ()
    if "init_true" in out:
        renamed_init = [names.get(a, a) for a in out["init_true"]]
        dropped = tuple(sorted({a for a in renamed_init if a not in vocabulary}))
        out["init_true"] = [a for a in renamed_init if a in vocabulary]
    return Alignment(out, tuple(sorted(names.items())), dropped)


@dataclass(frozen=True)
class EnvironmentBinding:
    pack: dict
    required: tuple[str, ...]
    granted: tuple[str, ...]
    unavailable: tuple[str, ...]
    contracts_applied: tuple[str, ...]
    unaligned: tuple[str, ...]
    matched: tuple[tuple[str, str], ...] = ()


def bind_environment(pack: dict, grants: Iterable[str],
                     manifest: dict | None = None, align: bool = False,
                     equivalents: bool = False) -> EnvironmentBinding:
    """Bind an intent pack to an environment: tool existence, then tool contracts.
    `align=True` first aligns the pack's names through its bindings
    (`align_to_contracts`); off by default. `equivalents=True` also counts a granted
    tool that does the same job under another name (`skillc.equivalents`); off by
    default, so verdicts published against exact names are unchanged."""
    from .grants import bind_grants

    existence = bind_grants(pack, grants, equivalents=equivalents)
    contracts = (manifest or {}).get("contracts") or {}
    bound = apply_contracts(
        existence.pack, contracts, (manifest or {}).get("states", {}),
        (manifest or {}).get("init_true", []), align=align,
    ) if contracts else ContractBinding(existence.pack, (), ())
    return EnvironmentBinding(bound.pack, existence.required, existence.granted,
                              existence.unavailable, bound.applied, bound.unaligned,
                              existence.matched)


def apply_contracts(pack: dict, contracts: dict, states: Iterable[str],
                    init_true: Iterable[str] = (), align: bool = False) -> ContractBinding:
    """Substitute environment contracts for the pack's granted capabilities.

    `init_true` is the environment's initial state; it replaces the intent's
    assumed facts whenever environment contracts are applied. An intent cannot
    manufacture prior approval or authentication. Under those contracts, an initial
    constraint naming anything outside the state vocabulary is a compaction
    artifact the environment cannot confirm, so it is dropped: removing a
    constraint only widens the initial states and can never create a refutation.

    `align=True` (opt-in) first renames pack names through the bindings
    (`align_to_contracts`); what stays outside the vocabulary is unaligned.
    """
    validate_pack(pack)
    vocabulary = set(states)
    renamed: tuple[tuple[str, str], ...] = ()
    if align and contracts:
        alignment = align_to_contracts(pack, contracts, vocabulary)
        pack, renamed = alignment.pack, alignment.renamed
        validate_pack(pack)
    used = (
        atoms(pack["goal"]) | numeric_vars(pack["goal"]) | set(pack.get("init_true", []))
    )
    unaligned = tuple(sorted(used - vocabulary))
    if unaligned or not contracts:
        return ContractBinding(deepcopy(pack), (), unaligned, (), renamed)
    bound = deepcopy(pack)
    applied = []
    for name, capability in bound["capabilities"].items():
        contract = contracts.get(name)
        if contract is None:
            continue
        owner = {"owner": capability["owner"]} if "owner" in capability else {}
        bound["capabilities"][name] = {
            **owner,
            **{key: deepcopy(contract[key]) for key in CONTRACT_FIELDS if key in contract},
        }
        applied.append(name)
    dropped: set[str] = set()
    if applied:
        bound["init_true"] = sorted(set(init_true))
        kept = []
        for constraint in bound.get("init_constraints", []):
            outside = (atoms(constraint) | numeric_vars(constraint)) - vocabulary
            dropped |= outside
            if not outside:
                kept.append(constraint)
        if "init_constraints" in bound:
            bound["init_constraints"] = kept
    validate_pack(bound)
    return ContractBinding(bound, tuple(sorted(applied)), (), tuple(sorted(dropped)), renamed)

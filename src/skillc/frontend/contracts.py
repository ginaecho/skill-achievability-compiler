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

    if not verdict.refuted or not verdict.frontier:
        return verdict
    names = [str(name) for name in verdict.frontier]
    if verdict.reason == "BLOCKED_GUARD":
        names = _blocked_guard_conditions(names, pack)
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
        pack_digest=verdict.pack_digest, decision_scope=verdict.decision_scope)


CONDITION_REASONS = ("GOAL_UNSAT", "BLOCKED_GUARD")
_BLOCKED_CAPABILITY_RE = re.compile(r"capability '([^']+)'")


def _mentions(text: str, name: str) -> bool:
    """Whether `text` contains `name` as a whole identifier (case-insensitive)."""
    pattern = rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])"
    return re.search(pattern, text, re.IGNORECASE) is not None


def _blocked_guard_conditions(frontier: list[str], pack: dict | None) -> list[str]:
    """Condition names in the guards of the capabilities a BLOCKED_GUARD names."""
    if not pack:
        return []
    capabilities = pack.get("capabilities", {})
    names = set()
    for entry in frontier:
        for capability in _BLOCKED_CAPABILITY_RE.findall(entry):
            names |= atoms(capabilities.get(capability, {}).get("pre", True))
    return sorted(names)


@dataclass(frozen=True)
class ContractBinding:
    pack: dict
    applied: tuple[str, ...]
    unaligned: tuple[str, ...]


@dataclass(frozen=True)
class EnvironmentBinding:
    pack: dict
    required: tuple[str, ...]
    granted: tuple[str, ...]
    unavailable: tuple[str, ...]
    contracts_applied: tuple[str, ...]
    unaligned: tuple[str, ...]


def bind_environment(pack: dict, grants: Iterable[str],
                     manifest: dict | None = None) -> EnvironmentBinding:
    """Bind an intent pack to an environment: tool existence, then tool contracts."""
    from .grants import bind_grants

    existence = bind_grants(pack, grants)
    contracts = (manifest or {}).get("contracts") or {}
    bound = apply_contracts(
        existence.pack, contracts, (manifest or {}).get("states", {}),
        (manifest or {}).get("init_true", []),
    ) if contracts else ContractBinding(existence.pack, (), ())
    return EnvironmentBinding(bound.pack, existence.required, existence.granted,
                              existence.unavailable, bound.applied, bound.unaligned)


def apply_contracts(pack: dict, contracts: dict, states: Iterable[str],
                    init_true: Iterable[str] = ()) -> ContractBinding:
    """Substitute environment contracts for the pack's granted capabilities.

    `init_true` is the environment's initial state; it holds whenever the
    environment's contracts are in force.
    """
    validate_pack(pack)
    vocabulary = set(states)
    used = (
        atoms(pack["goal"]) | numeric_vars(pack["goal"]) | set(pack.get("init_true", []))
    )
    unaligned = tuple(sorted(used - vocabulary))
    if unaligned or not contracts:
        return ContractBinding(deepcopy(pack), (), unaligned)
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
    if applied:
        bound["init_true"] = sorted(set(bound.get("init_true", [])) | set(init_true))
    validate_pack(bound)
    return ContractBinding(bound, tuple(sorted(applied)), ())

"""Bind untrusted extraction to an explicit, separately reviewed task contract."""
from __future__ import annotations

from copy import deepcopy

from ..pack import PackError, validate_pack


def bind_contract(pack: dict, contract: dict) -> dict:
    """Keep the extracted protocol, but never let it invent grants or goals.

    The contract is an additional trust input, not inferred ground truth.
    All granted capabilities remain in Gamma, even if extraction missed an
    alternative producer. This does not repair a malformed protocol.
    """
    fields = {"goal", "capabilities", "roles", "init_true", "init_constraints"}
    if (not isinstance(contract, dict) or not set(contract) <= fields
            or not {"goal", "capabilities"} <= set(contract)):
        raise PackError("contract needs goal+capabilities and only supported context fields")
    validate_pack({"name": "contract", "protocol": [], **contract})
    validate_pack(pack)
    bound = deepcopy(pack)
    bound["goal"] = deepcopy(contract["goal"])
    bound["capabilities"] = deepcopy(contract["capabilities"])
    bound["init_true"] = deepcopy(contract.get("init_true", []))
    bound["init_constraints"] = deepcopy(contract.get("init_constraints", []))
    if "roles" in contract:
        bound["roles"] = deepcopy(contract["roles"])

    def rebind_markers(steps):
        for step in steps:
            if "goal" in step:
                step["goal"] = deepcopy(contract["goal"])
            elif "rec" in step:
                rebind_markers(step["rec"]["body"])
            else:
                for kind in ("choice", "select", "branch"):
                    if kind in step:
                        for branch in step[kind]["branches"].values():
                            rebind_markers(branch)

    rebind_markers(bound["protocol"])
    for behavior in bound.get("skills", {}).values():
        rebind_markers(behavior)
    validate_pack(bound)
    return bound

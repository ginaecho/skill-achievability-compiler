"""Bind intent-required capabilities to an environment's independent grants."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from collections.abc import Iterable

from ..pack import validate_pack
from ..profiles import normalize_tool


@dataclass(frozen=True)
class GrantBinding:
    pack: dict
    required: tuple[str, ...]
    granted: tuple[str, ...]
    unavailable: tuple[str, ...]
    matched: tuple[tuple[str, str], ...] = ()   # (required, the equivalent that provides it)


def bind_grants(pack: dict, environment_grants: Iterable[str],
                equivalents: bool = True) -> GrantBinding:
    """Remove capability definitions the environment does not grant.

    The protocol remains unchanged. Consequently, a required action whose
    capability was removed is reported by the checker as MISSING_CAPABILITY.
    With `equivalents`, a capability also counts as granted when the environment
    grants a tool that does the same job under another name (`skillc.equivalents`).
    """
    from ..equivalents import match

    validate_pack(pack)
    environment_grants = list(environment_grants)
    granted_names = {normalize_tool(name) for name in environment_grants}
    required = tuple(sorted(pack["capabilities"]))
    matched = []
    available = []
    for name in required:
        if normalize_tool(name) in granted_names:
            available.append(name)
        elif equivalents and (other := match(name, environment_grants)):
            available.append(name)
            matched.append((name, other))
    available = tuple(available)
    unavailable = tuple(name for name in required if name not in available)
    bound = deepcopy(pack)
    bound["capabilities"] = {
        name: capability
        for name, capability in bound["capabilities"].items()
        if name in available
    }
    validate_pack(bound)
    return GrantBinding(bound, required, available, unavailable, tuple(matched))

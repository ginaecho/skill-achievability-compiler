"""Built-in tools that do the same job under different names in different runtimes.

claude.ai asks the user with `ask_user_input_v0`, Claude Code with `AskUserQuestion`, GitHub
Copilot CLI with `ask_user`. A skill names the tools of the runtime it was written for, so
matching names exactly calls it IMPOSSIBLE elsewhere even where the same tool exists. The
reviewed groups in `data/tool_equivalents.json` say which names are the same tool.

Counting an equivalent only ever adds a grant: it can turn a refutation into ACHIEVABLE,
never the reverse, so it cannot create a false refutation. It is opt-in where verdicts are
published against exact names.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from functools import lru_cache
from importlib import resources

from .profiles import normalize_tool


@lru_cache(maxsize=1)
def groups() -> tuple[tuple[str, frozenset[str]], ...]:
    """(what the tools do, their normalized names), one per reviewed group."""
    raw = resources.files("skillc").joinpath("data/tool_equivalents.json")
    data = json.loads(raw.read_text(encoding="utf-8"))
    return tuple((g["does"], frozenset(normalize_tool(n) for n in g["names"]))
                 for g in data["groups"])


def same_tool(name: str) -> frozenset[str]:
    """Every name of the tool `name` (itself included)."""
    n = normalize_tool(name)
    for _does, names in groups():
        if n in names:
            return names
    return frozenset({n})


def match(required: str, grants: Iterable[str]) -> str | None:
    """The granted name that provides `required`: itself, else an equivalent, else None."""
    n = normalize_tool(required)
    granted = {normalize_tool(g) for g in grants}
    if n in granted:
        return n
    return next((g for g in sorted(same_tool(n) & granted)), None)

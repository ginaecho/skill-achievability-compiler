"""Environment capability profiles.

A profile declares the tool capabilities a target agent runtime grants (the
capability context Γ).  Achievability of a skill is always judged *relative*
to a profile: the same SKILL.md can be ACHIEVABLE under `claude-ai` (which
grants `ask_user_input_v0`) and IMPOSSIBLE under `claude-code` (which does
not) -- an operational illustration of relativity to Gamma and the
contrapositive of Coq T3 (`cap_monotone`).

Built-in profiles live in skillc/data/profiles/*.json:

    {
      "name": "claude-code",
      "description": "...",
      "tools": ["bash", "read", ...],   // normalized lower-case tool names
      "shell": true                     // grants a POSIX shell (via bash)
    }

A profile may also be loaded from an arbitrary JSON file path.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from importlib import resources
from pathlib import Path


def normalize_tool(name: str) -> str:
    """Canonical form used for capability matching: lower-case, qualifier-free.

    `Bash(git:*)` -> `bash`;  `WebFetch` -> `webfetch`;  `mcp__github__get_me`
    stays a distinct name.
    """
    name = name.strip()
    name = re.sub(r"\(.*\)$", "", name)      # strip Claude Code qualifiers
    return name.strip().lower()


class ProfileError(ValueError):
    """A profile document does not have the documented shape."""


def _validate(d) -> None:
    if not isinstance(d, dict):
        raise ProfileError("a profile must be a JSON object")
    if not isinstance(d.get("name"), str) or not d["name"].strip():
        raise ProfileError("profile name must be a non-empty string")
    if not isinstance(d.get("description", ""), str):
        raise ProfileError("profile description must be a string")
    tools = d.get("tools", [])
    if not isinstance(tools, list) or not all(
            isinstance(tool, str) and normalize_tool(tool) for tool in tools):
        raise ProfileError("profile tools must be a list of non-empty strings")
    if not isinstance(d.get("shell", False), bool):
        raise ProfileError("profile shell must be true or false")


@dataclass
class Profile:
    name: str
    description: str = ""
    tools: frozenset = frozenset()
    shell: bool = False
    extra: list[str] = field(default_factory=list)

    def grants(self, tool: str) -> bool:
        return normalize_tool(tool) in self.tools

    @staticmethod
    def from_dict(d: dict) -> Profile:
        _validate(d)
        tools = frozenset(normalize_tool(t) for t in d.get("tools", []))
        return Profile(name=d["name"], description=d.get("description", ""),
                       tools=tools, shell=d.get("shell", False))

    def with_tools(self, extra: list[str]) -> Profile:
        return replace(self, tools=self.tools | {normalize_tool(t) for t in extra},
                       extra=self.extra + list(extra))


def builtin_profiles() -> list[str]:
    root = resources.files("skillc").joinpath("data/profiles")
    return sorted(p.name[:-5] for p in root.iterdir() if p.name.endswith(".json"))


def load_profile(name_or_path: str) -> Profile:
    """Load a built-in profile by name, or any profile from a JSON file path."""
    p = Path(name_or_path)
    if p.suffix == ".json" and p.exists():
        return Profile.from_dict(json.loads(p.read_text(encoding="utf-8")))
    ref = resources.files("skillc").joinpath(f"data/profiles/{name_or_path}.json")
    try:
        data = ref.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise KeyError(
            f"unknown profile {name_or_path!r}; built-ins: {builtin_profiles()}"
        ) from None
    return Profile.from_dict(json.loads(data))

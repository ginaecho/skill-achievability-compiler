"""Editable literal vocabulary for the heuristic Markdown front-end, not CE."""
from __future__ import annotations

import json
import os
import re
from collections.abc import Collection
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from pathlib import Path

PHRASE_FIELDS = ("invocation_verbs", "completion_phrases", "workflow_headings")
ACTION_FIELDS = ("phrases", "tool_names", "tool_prefixes")


def _strings(value: object, field: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list of non-empty strings")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{field} must contain non-empty strings")
    return [" ".join(item.split()).lower() for item in value]


def _alternatives(phrases: Collection[str]) -> str:
    parts = []
    for phrase in sorted(set(phrases), key=lambda item: (-len(item), item)):
        literal = r"\s+".join(re.escape(word) for word in phrase.split())
        literal = literal.replace(":", r"\s*:")
        parts.append(literal + (r"(?!\w)" if phrase[-1].isalnum() else ""))
    return "(?:" + "|".join(parts) + ")"


@dataclass(frozen=True)
class Action:
    name: str
    pattern: re.Pattern[str]
    tool_names: tuple[str, ...]
    tool_prefixes: tuple[str, ...]

    def target(self, tools: Collection[str]) -> str | None:
        """Resolve a phrase to an independently named tool, not a grant."""
        for name in (*self.tool_names, self.name):
            if name in tools:
                return name
        return next((tool for tool in tools if tool.startswith(self.tool_prefixes)), None)


@dataclass(frozen=True)
class Vocabulary:
    actions: dict[str, Action]
    invoke_re: re.Pattern[str]
    done_re: re.Pattern[str]
    workflow_heading: str

    def action_matches(self, text: str) -> list[tuple[Action, re.Match[str]]]:
        """Leftmost, longest literal phrase wins when configured phrases overlap."""
        candidates = [
            (action, match) for action in self.actions.values()
            for match in action.pattern.finditer(text)
        ]
        candidates.sort(key=lambda item: (item[1].start(), -item[1].end(), item[0].name))
        matches = []
        end = 0
        for action, match in candidates:
            if match.start() >= end:
                matches.append((action, match))
                end = match.end()
        return matches


@lru_cache(maxsize=16)
def _load(path: str | None) -> Vocabulary:
    builtin = resources.files("skillc").joinpath("data/deterministic_vocabulary.json")
    documents = [json.loads(builtin.read_text(encoding="utf-8"))]
    if path:
        documents.append(json.loads(Path(path).read_text(encoding="utf-8-sig")))
    phrases: dict[str, list[str]] = {field: [] for field in PHRASE_FIELDS}
    actions: dict[str, dict[str, list[str]]] = {}
    for document in documents:
        if not isinstance(document, dict):
            raise ValueError("deterministic vocabulary must be an object")
        unsupported = set(document) - {*PHRASE_FIELDS, "actions"}
        if unsupported:
            raise ValueError(f"unsupported deterministic vocabulary fields: {sorted(unsupported)}")
        for field in PHRASE_FIELDS:
            if field in document:
                phrases[field].extend(_strings(document[field], field))
        raw_actions = document.get("actions", {})
        if not isinstance(raw_actions, dict):
            raise ValueError("actions must be an object")
        for name, spec in raw_actions.items():
            if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
                raise ValueError(f"invalid action name: {name!r}")
            if not isinstance(spec, dict):
                raise ValueError(f"action {name!r} must be an object")
            unsupported = set(spec) - set(ACTION_FIELDS)
            if unsupported:
                raise ValueError(f"action {name!r} has unsupported fields: {sorted(unsupported)}")
            fields = actions.setdefault(name, {field: [] for field in ACTION_FIELDS})
            for field in ACTION_FIELDS:
                if field in spec:
                    fields[field].extend(_strings(spec[field], f"actions.{name}.{field}"))
    if any(not values for values in phrases.values()):
        raise ValueError("deterministic vocabulary phrase lists must be non-empty")
    seen: dict[str, str] = {}
    compiled = {}
    for name, fields in actions.items():
        if not fields["phrases"]:
            raise ValueError(f"action {name!r} needs non-empty phrases")
        for phrase in fields["phrases"]:
            if phrase in seen and seen[phrase] != name:
                raise ValueError(f"ambiguous action phrase {phrase!r}: {seen[phrase]} and {name}")
            seen[phrase] = name
        for field in ("tool_names", "tool_prefixes"):
            if any(not re.fullmatch(r"[a-z][a-z0-9_.:-]*", tool) for tool in fields[field]):
                raise ValueError(f"actions.{name}.{field} contains an invalid tool name")
        compiled[name] = Action(
            name, re.compile(r"(?<!\w)" + _alternatives(fields["phrases"]), re.I),
            tuple(fields["tool_names"]), tuple(fields["tool_prefixes"]),
        )
    return Vocabulary(
        compiled,
        re.compile(r"(?<!\w)" + _alternatives(phrases["invocation_verbs"])
                   + r"\s+(?:the\s+)?`([A-Za-z][A-Za-z0-9_.:-]*)`", re.I),
        re.compile(r"(?<!\w)" + _alternatives(phrases["completion_phrases"])
                   + r"(.{0,400}?)(?<!\d)\.(?:\s|$)", re.I | re.S),
        r"(?<!\w)" + _alternatives(phrases["workflow_headings"]),
    )


def vocabulary() -> Vocabulary:
    """Load defaults plus optional project extensions; restart after editing the file."""
    path = os.environ.get("SKILLC_DETERMINISTIC_VOCABULARY")
    return _load(str(Path(path).resolve()) if path else None)

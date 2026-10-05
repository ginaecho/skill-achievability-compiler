"""Tool-policy library: accumulated, checked knowledge of what skills require.

The runtime binder (`frontend.runtime`) can only reject what the compaction
states: a `via` the runtime lacks or a `needs` it does not grant.  When the
model omits a credential, hides a missing program behind `via bash`, or says
nothing about an external write, nothing is left to reject.  The library
moves that knowledge out of the model into data:

  evidence (patterns in the skill text)  ->  requirement
      requirement = a resource the runtime must grant   (needs `R`)
                  | a runtime tool                      (via `T`)
                  | a program                           (runs `P`)
                  | an effect class                     (effect `E`)

A match creates an *obligation*: the compaction must carry the requirement on
some Tool (on a skippable branch if the work is optional).  Coverage is
checked deterministically; an unmet obligation is a located error.  A match
never decides a verdict by itself: the runtime manifest and the checker do.

Entries carry provenance (the execution reports they were learned from), in
the spirit of API->permission maps such as PScout (CCS 2012).
"""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from ..pack import iter_steps

__all__ = ["Library", "Obligation", "load_library", "match", "obligations_note",
           "coverage", "resolve_program", "core_lines", "unmet", "veto"]


@dataclass(frozen=True)
class Obligation:
    entry: str            # library entry id
    kind: str             # resource | runtime_tool | program | effect
    value: str            # e.g. azure_account, notion_mcp, writes_external
    line: int             # first matching line of the skill text (1-based)
    text: str             # the matching text
    note: str = ""
    substitutes: str = ""

    def clause(self) -> str:
        return {"resource": f"needs `{self.value}`",
                "runtime_tool": f"via `{self.value}`",
                "program": f"runs `{self.value}`",
                "effect": f"effect `{self.value}`"}[self.kind]


@dataclass
class Library:
    version: str
    entries: list
    programs: dict = field(default_factory=dict)


def load_library(path: str | Path | None = None) -> Library:
    if path is None:
        raw = resources.files("skillc").joinpath("data/toolpolicy/library.json") \
            .read_text(encoding="utf-8")
    else:
        raw = Path(path).read_text(encoding="utf-8")
    d = json.loads(raw)
    return Library(d["version"], d["entries"], d.get("programs", {}))


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def match(text: str, library: Library) -> list[Obligation]:
    """Obligations raised by `text`, in order of first appearance; one per
    distinct (kind, value)."""
    lines = text.splitlines()
    found: dict[tuple, Obligation] = {}
    for e in library.entries:
        (kind, template), = e["requires"].items()
        ignore = set(e.get("ignore_captures", []))
        for pat in e["evidence"]:
            rx = re.compile(pat, re.IGNORECASE)
            for no, line in enumerate(lines, 1):
                for m in rx.finditer(line):
                    if e.get("parametric"):
                        cap = m.group(1) if m.groups() else ""
                        if not cap or cap.lower() in ignore:
                            continue
                        value = template.replace("{1}", _norm(cap))
                    else:
                        value = template
                    key = (kind, value)
                    if key not in found or no < found[key].line:
                        found[key] = Obligation(e["id"], kind, value, no,
                                                m.group(0)[:80], e.get("note", ""),
                                                e.get("substitutes", ""))
    return sorted(found.values(), key=lambda o: (o.line, o.value))


def obligations_note(obligations: list[Obligation]) -> str:
    """Prompt section listing the obligations the compaction must cover."""
    if not obligations:
        return ("\nTOOL-POLICY LIBRARY: no known requirement was detected in this "
                "skill.\n")
    rows = []
    for o in obligations:
        rows.append(f"  - line {o.line} ('{o.text}'): {o.note} Write "
                    f"{o.clause()} on the Tool that does it."
                    + (f" Known local alternative: {o.substitutes}"
                       if o.substitutes else ""))
    return ("\nTOOL-POLICY LIBRARY: the skill text shows these requirements. "
            "Each one MUST appear on some Tool exactly as written. If the work "
            "that needs it is optional, follow-up or only one of several ways, "
            "put that Tool in a 'chooses one of (observed)' with a branch that "
            "skips it (and, if a local alternative does the core job, add that "
            "alternative as its own Tool):\n" + "\n".join(rows) + "\n")


def coverage(parsed, obligations: list[Obligation]) -> list[str]:
    """Unmet obligations of a parsed CE document (`ParseResult`), as located,
    actionable messages; [] when every obligation is carried by some Tool."""
    b = parsed.bindings
    vias = {v.get("via") for v in b.values()}
    needs = {r for v in b.values() for r in (v.get("needs") or [])}
    runs = {p for v in b.values() for p in (v.get("runs") or [])}
    effects = {v.get("effect") for v in b.values()}
    spawns = any("spawn" in s for s in iter_steps(parsed.pack.get("protocol", [])))
    out = []
    for o in obligations:
        ok = {"resource": o.value in needs,
              "runtime_tool": o.value in vias or (o.value == "agent_spawn" and spawns),
              "program": o.value in runs,
              "effect": o.value in effects}[o.kind]
        if not ok:
            out.append(f"skill line {o.line} ('{o.text}') requires {o.clause()}, "
                       "but no Tool carries it")
    return out


def resolve_program(program: str, runtime, library: Library,
                    probe_host: bool = False) -> tuple[str, str]:
    """('present' | 'installable' | 'unavailable', why).

    The library's catalogue decides known programs (unpublished helpers,
    OS-specific toolchains); with `probe_host`, a program on this machine's
    PATH is 'present'.  Anything else is assumed installable from the public
    registries the runtime grants: absence on PATH is never evidence that a
    program cannot be installed."""
    info = library.programs.get(program, {})
    if info.get("status") == "unavailable":
        return "unavailable", info.get("why", "not available")
    os_need = info.get("requires_os")
    if os_need and os_need not in runtime.grants:
        return "unavailable", f"requires {os_need}"
    if probe_host and shutil.which(program):
        return "present", "on PATH"
    return "installable", "assumed installable from public registries"


def core_lines(text: str) -> set[int]:
    """1-based line numbers of a skill's core statement: its frontmatter
    (name, description, allowed tools) and the title/introduction before the
    first `## ` section."""
    lines = text.splitlines()
    core, start = set(), 0
    if lines and lines[0].strip() == "---":
        core.add(1)
        for i in range(1, len(lines)):
            core.add(i + 1)
            if lines[i].strip() == "---":
                start = i + 1
                break
    for i in range(start, len(lines)):
        if lines[i].startswith("## "):
            break
        core.add(i + 1)
    return core


def unmet(o: Obligation, runtime, library: Library) -> bool:
    """Whether the runtime cannot satisfy this obligation."""
    if o.kind == "resource":
        return o.value not in runtime.grants
    if o.kind == "runtime_tool":
        return o.value not in runtime.tools
    if o.kind == "program":
        return resolve_program(o.value, runtime, library)[0] == "unavailable"
    return o.value in runtime.forbid_effects       # effect


def veto(text: str, runtime, library: Library, scope: str = "core") -> list[Obligation]:
    """Requirements the library finds in the skill that the runtime cannot
    meet; with scope='core', only those stated in the skill's core statement.
    A non-empty result is a deterministic IMPOSSIBLE, independent of the LLM."""
    obs = [o for o in match(text, library) if unmet(o, runtime, library)]
    if scope == "core":
        cl = core_lines(text)
        obs = [o for o in obs if o.line in cl]
    return obs

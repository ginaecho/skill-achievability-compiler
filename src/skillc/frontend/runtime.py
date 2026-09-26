"""Bind compacted tools to an explicit runtime manifest (Gamma from the runtime).

A manifest-bound CE document says, for every tool, which runtime tool
performs it (`via`) and which resources outside the runtime it needs
(`needs`).  This module turns those bindings into the pack's capability
context deterministically, so the model no longer decides whether a tool
"exists": it only maps each operation onto a closed list.

  * `via T` with T in the manifest      -> the capability is granted;
  * `via T` with T not in the manifest  -> the capability is withdrawn, and
    every step that uses it is reported as MISSING_CAPABILITY;
  * `needs R`                           -> R becomes a precondition; it holds
    initially only if the manifest grants R, otherwise the step is reported as
    BLOCKED_GUARD naming R.

A tool with no `via` is an error, not a guess: the caller retries with the
located message.  Nothing here reads the skill; like every front-end step,
the result is only as faithful as the bindings the model wrote.
"""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from ..pack import validate_pack
from .ce import CEError


@dataclass(frozen=True)
class Runtime:
    name: str
    description: str
    tools: dict            # runtime tool -> what it does
    grants: tuple          # resources the runtime provides
    lacks: tuple           # human-readable list of what it does not provide

    @staticmethod
    def from_dict(d: dict) -> "Runtime":
        return Runtime(d["name"], d.get("description", ""), dict(d["tools"]),
                       tuple(d.get("grants", [])), tuple(d.get("lacks", [])))


def load_runtime(name_or_path: str) -> Runtime:
    p = Path(name_or_path)
    if p.suffix == ".json" and p.exists():
        return Runtime.from_dict(json.loads(p.read_text(encoding="utf-8")))
    ref = resources.files("skillc").joinpath(f"data/runtimes/{name_or_path}.json")
    try:
        return Runtime.from_dict(json.loads(ref.read_text(encoding="utf-8")))
    except FileNotFoundError:
        raise KeyError(f"unknown runtime {name_or_path!r}") from None


@dataclass
class Binding:
    pack: dict
    withdrawn: dict = field(default_factory=dict)   # tool -> runtime tool it named
    blocked: dict = field(default_factory=dict)     # tool -> resources not granted


def bind_runtime(pack: dict, bindings: dict, runtime: Runtime) -> Binding:
    """Apply `via`/`needs` bindings to a parsed pack under `runtime`."""
    out = deepcopy(pack)
    res = Binding(out)
    for name in list(out["capabilities"]):
        b = bindings.get(name)
        if not b or not b.get("via"):
            raise CEError(f"Tool `{name}` has no 'via' clause: say which runtime "
                          f"tool performs it ({', '.join(sorted(runtime.tools))}), "
                          "or name what it would need", b.get("line") if b else None)
        if b["via"] not in runtime.tools:
            res.withdrawn[name] = b["via"]
            del out["capabilities"][name]
            continue
        needs = list(b.get("needs") or [])
        if needs:
            cap = out["capabilities"][name]
            pre = cap.get("pre", True)
            guards = [f"needs:{r}" for r in needs]
            cap["pre"] = ({"and": guards} if pre is True
                          else {"and": guards + [pre]})
            missing = [r for r in needs if r not in runtime.grants]
            if missing:
                res.blocked[name] = missing
            for r in needs:
                if r in runtime.grants and f"needs:{r}" not in out["init_true"]:
                    out["init_true"].append(f"needs:{r}")
    validate_pack(out)
    return res


def repair_violations(before, after) -> list[str]:
    """Deterministic guard for a counterexample-guided repair.

    `before` and `after` are `ParseResult`s of the refuted document and of the
    model's repair.  The repair prompt forbids weakening the Goal and dropping
    a `needs` the skill really has; a prompt rule is not a guarantee, so the
    two checkable halves are enforced here: the Goal must be unchanged, and a
    Tool that survives the repair must keep every resource it needed.  (A Tool
    may still be removed or made skippable; that judgement stays semantic.)
    """
    out = []
    if (json.dumps(before.pack.get("goal"), sort_keys=True)
            != json.dumps(after.pack.get("goal"), sort_keys=True)):
        out.append("the Goal changed")
    for name, b in sorted(before.bindings.items()):
        a = after.bindings.get(name)
        if a is None:
            continue
        dropped = sorted(set(b.get("needs") or []) - set(a.get("needs") or []))
        if dropped:
            out.append(f"Tool `{name}` kept but no longer needs "
                       + ", ".join(f"`{r}`" for r in dropped))
    return out


def runtime_note(runtime: Runtime) -> str:
    """The prompt section that tells the compactor what the runtime is."""
    tools = "\n".join(f"  - `{t}`: {d}" for t, d in runtime.tools.items())
    lacks = "\n".join(f"  - {x}" for x in runtime.lacks)
    grants = ", ".join(f"`{g}`" for g in runtime.grants)
    return (
        f"\nRUNTIME `{runtime.name}`: {runtime.description}\n"
        f"Its tools (the ONLY values allowed after 'via'):\n{tools}\n"
        f"It does NOT provide:\n{lacks}\n"
        f"Resources it grants (usable after 'needs'): {grants}.\n")

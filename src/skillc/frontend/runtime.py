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
    forbid_effects: tuple = ()   # effect classes the runtime's policy forbids
    software: str = "installable"  # installable | preinstalled | none (see resolve_software)

    @staticmethod
    def from_dict(d: dict) -> "Runtime":
        return Runtime(d["name"], d.get("description", ""), dict(d["tools"]),
                       tuple(d.get("grants", [])), tuple(d.get("lacks", [])),
                       tuple(d.get("forbid_effects", [])),
                       d.get("software", "installable"))


def load_runtime(name_or_path: str) -> Runtime:
    p = Path(name_or_path)
    if p.suffix == ".json" and p.exists():
        return Runtime.from_dict(json.loads(p.read_text(encoding="utf-8")))
    ref = resources.files("skillc").joinpath(f"data/runtimes/{name_or_path}.json")
    try:
        return Runtime.from_dict(json.loads(ref.read_text(encoding="utf-8")))
    except FileNotFoundError:
        raise KeyError(f"unknown runtime {name_or_path!r}") from None


_INVENTORY: dict = {}


def inventory() -> set:
    """Names of the software installed on the machine the runtimes describe
    (data/runtimes/inventory.json, from scripts/snapshot_inventory.py)."""
    if not _INVENTORY:
        ref = resources.files("skillc").joinpath("data/runtimes/inventory.json")
        d = json.loads(ref.read_text(encoding="utf-8"))
        _INVENTORY["names"] = set(d["python"]) | set(d["executables"]) | set(d["npm"])
    return _INVENTORY["names"]


def _variants(name: str) -> set:
    n = name.strip().lower().split("==")[0].split(">=")[0].split("[")[0]
    base = {n, n.replace("_", "-"), n.replace("-", "_"), n.split("/")[-1]}
    return base | {b[len("python-"):] for b in base if b.startswith("python-")} \
        | {b[len("py"):] for b in base if b.startswith("py") and len(b) > 4}


def resolve_software(name: str, runtime: "Runtime") -> tuple[bool, str]:
    """Whether a Tool that `runs` this software can run in the runtime.

    installable  -> always (a registry is reachable; absence on the machine is
                    never evidence that software cannot be installed);
    preinstalled -> only if the machine's inventory has it (no installs);
    none         -> never (the runtime cannot execute software at all)."""
    if runtime.software == "none":
        return False, "this runtime cannot run software"
    if runtime.software == "preinstalled":
        if _variants(name) & inventory():
            return True, "installed on the machine"
        return False, "not installed, and this runtime cannot install software"
    return True, "installable from public registries"


@dataclass
class Binding:
    pack: dict
    withdrawn: dict = field(default_factory=dict)   # tool -> runtime tool it named
    blocked: dict = field(default_factory=dict)     # tool -> resources not granted
    pruned: list = field(default_factory=list)      # "role:branch" labels removed


def _prune(steps: list, dead: set, pruned: list) -> bool:
    """Drop the branches of the agent's own (non-external) choices that invoke
    a dead Tool, when a runnable branch remains.  Returns whether `steps` can
    run.  The whole-session typing judgment quantifies over every branch of a
    choice, so without this a skippable branch the runtime cannot run would
    refute the protocol even though the agent never needs to take it."""
    ok = True
    for step in steps:
        (kind, body), = step.items()
        if kind == "act":
            ok &= body["cap"] not in dead
        elif kind == "rec":
            ok &= _prune(body["body"], dead, pruned)
        elif kind == "choice":
            live = {lbl: _prune(br, dead, pruned)
                    for lbl, br in body["branches"].items()}
            if body.get("external"):
                ok &= all(live.values())
            elif any(live.values()):
                for lbl in [lbl for lbl, run in live.items() if not run]:
                    del body["branches"][lbl]
                    pruned.append(f"{body['by']}:{lbl}")
            else:
                ok = False
    return ok


def _spawn_to_act(steps: list, by: str) -> list:
    out = []
    for s in steps:
        (kind, body), = s.items()
        if kind == "spawn":
            out.append({"act": {"cap": SPAWN_TOOL, "by": by}})
        elif kind == "choice":
            out.append({"choice": {**body, "branches": {
                k: _spawn_to_act(v, by) for k, v in body["branches"].items()}}})
        elif kind == "rec":
            out.append({"rec": {**body, "body": _spawn_to_act(body["body"], by)}})
        else:
            out.append(s)
    return out


SPAWN_TOOL = "agent_spawn"


def bind_runtime(pack: dict, bindings: dict, runtime: Runtime,
                 prune: bool = True, library=None, software: bool = False) -> Binding:
    """Apply `via`/`needs` bindings to a parsed pack under `runtime`.

    With `prune` (the default), branches of the agent's own choices that only
    a withdrawn or blocked Tool could run are removed: the runtime restricts
    what the agent can choose, not what the environment can.

    With a tool-policy `library` (frontend.toolpolicy), three more facts are
    bound: a Tool whose `effect` the runtime forbids is blocked by a
    `policy:<effect>` guard; a Tool that `runs` a program the library knows
    to be unavailable here is withdrawn; and, when the runtime has no
    `agent_spawn` tool, every `spawn` step becomes an act of that missing
    capability (MISSING_CAPABILITY is decided before the undecidable
    dynamic-topology boundary)."""
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
        if software:
            for prog in b.get("runs") or []:
                ok, why = resolve_software(prog, runtime)
                if not ok:
                    res.withdrawn[name] = f"software:{prog} ({why})"
                    del out["capabilities"][name]
                    break
            if name not in out["capabilities"]:
                continue
        if library is not None:
            from .toolpolicy import resolve_program
            for prog in b.get("runs") or []:
                status, why = resolve_program(prog, runtime, library)
                if status == "unavailable":
                    res.withdrawn[name] = f"program:{prog} ({why})"
                    del out["capabilities"][name]
                    break
            if name in out["capabilities"] and b.get("effect") in runtime.forbid_effects:
                cap = out["capabilities"][name]
                guard = f"policy:{b['effect']}"
                pre = cap.get("pre", True)
                cap["pre"] = {"and": [guard]} if pre is True else {"and": [guard, pre]}
                res.blocked.setdefault(name, []).append(guard)
    dead = set(res.withdrawn) | set(res.blocked)
    if library is not None and SPAWN_TOOL not in runtime.tools:
        by = (out.get("roles") or ["agent"])[0]
        converted = _spawn_to_act(out["protocol"], by)
        if converted != out["protocol"]:
            out["protocol"] = converted
            if by not in out["roles"]:
                out["roles"] = list(out["roles"]) + [by]
            res.withdrawn[SPAWN_TOOL] = SPAWN_TOOL
            dead.add(SPAWN_TOOL)
    if prune:
        _prune(out["protocol"], dead, res.pruned)
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
    if (json.dumps(getattr(before, "live_goal", None), sort_keys=True)
            != json.dumps(getattr(after, "live_goal", None), sort_keys=True)):
        out.append("the Live goal changed")
    for name, b in sorted(before.bindings.items()):
        a = after.bindings.get(name)
        if a is None:
            continue
        dropped = sorted(set(b.get("needs") or []) - set(a.get("needs") or []))
        if dropped:
            out.append(f"Tool `{name}` kept but no longer needs "
                       + ", ".join(f"`{r}`" for r in dropped))
        lost = sorted(set(b.get("runs") or []) - set(a.get("runs") or []))
        if lost:
            out.append(f"Tool `{name}` kept but no longer runs "
                       + ", ".join(f"`{p}`" for p in lost))
        if b.get("effect") and a.get("effect") != b.get("effect"):
            out.append(f"Tool `{name}` kept but its effect changed from "
                       f"`{b['effect']}`")
    return out


def check_levels(pack: dict, live_goal=None, scope: str = "protocol") -> dict:
    """Two-level verdicts for a runtime-bound pack.

    `core` checks the pack's own Goal (the deliverable the runtime can hand
    over); `live` checks Goal and Live goal together (the effect outside the
    runtime, e.g. a public deployment).  Both are ordinary, deterministic
    `check` calls; `live` is None when the document has no Live goal.
    """
    from ..checker import check
    core = check(pack, scope=scope)
    if live_goal is None:
        return {"core": core, "live": None}
    both = deepcopy(pack)
    both["goal"] = {"and": [pack["goal"], live_goal]}
    return {"core": core, "live": check(both, scope=scope)}


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

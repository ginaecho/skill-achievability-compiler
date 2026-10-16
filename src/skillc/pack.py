"""The achievability *pack*: the formal object the checker consumes.

A pack is what a front-end (deterministic markdown compaction or an untrusted
LLM compaction) distills from a natural-language skill:

    {
      "name": "string",
      "roles": ["string", ...],
      "capabilities": {
        "<cap>": {
          "owner": "<role>",
          "pre":  <formula>,           // guard; default true
          "add":  ["pred", ...],       // predicates set TRUE  (STRIPS effect)
          "del":  ["pred", ...],       // predicates set FALSE
          "assigns": {"var": <expr>},  // deterministic numeric update v := expr
          "nondet":  {"var": <formula over the NEW value>}
        }
      },
      "protocol": [<step>, ...],       // goal-marked global protocol
      "goal": <formula>,
      "init_true": ["pred", ...],      // predicates true at start (frame: else false)
      "init_constraints": [<formula>, ...]
    }

    <step> ::= {"act":    {"cap": "<cap>", "by": "<role>"}}
             | {"msg":    {"from": "<role>", "to": "<role>", "label": "<l>"}}
             | {"choice": {"by": "<role>", "branches": {"<label>": [<step>...], ...},
                           "assumes": {"<label>": ["pred", ...]}}}   // optional
             | {"goal":   <formula>}       // explicit goal marker (optional)
             | {"rec":    {"name": "X", "body": [<step>...]}}   // tail-recursive loop
             | {"continue": "X"}           // jump back to the enclosing rec X
             | {"spawn":  {"role": "<role>"}}  // dynamic participant (outside
                                               // the decidable fragment -> UNKNOWN)

A choice may carry branch assumptions ("assumes"): facts the environment or
the user decides, which hold once that branch is taken (what kind of project
this is, whether an input was provided).  The checker adds them to the world
on entry to the branch, like an `add` effect; they are declared by the pack,
so refutation soundness relative to the pack is unchanged.

A pack may also declare per-role behaviours ("skills": {"<role>": [<local
step>...]}); the checker verifies the conformance premise S_p <= G|p via
Gay-Hole subtyping (see session.py for the local-type grammar).

validate_pack() is the deterministic schema gate on untrusted front-end
output: it rejects malformed packs before they reach the checker.  It does NOT
check semantic faithfulness (that declared effects match real tools) -- that
is the honest-declaration obligation of the runtime layer.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from collections.abc import Iterator

from .formula import FormulaError, validate_expr, validate_formula

CAP_FIELDS = frozenset({"owner", "pre", "add", "del", "assigns", "nondet"})


class PackError(ValueError):
    """Raised when a pack is structurally malformed."""


@dataclass
class Capability:
    name: str
    owner: str = "?"
    pre: Any = True                                       # guard formula
    add: list[str] = field(default_factory=list)          # predicates -> true
    dele: list[str] = field(default_factory=list)         # predicates -> false
    assigns: dict[str, Any] = field(default_factory=dict)  # var := expr
    nondet: dict[str, Any] = field(default_factory=dict)   # var := * s.t. formula

    @staticmethod
    def from_dict(name: str, c: dict) -> Capability:
        return Capability(
            name=name,
            owner=c.get("owner", "?"),
            pre=c.get("pre", True),
            add=list(c.get("add", [])),
            dele=list(c.get("del", [])),
            assigns=dict(c.get("assigns", {})),
            nondet=dict(c.get("nondet", {})),
        )

    def to_dict(self) -> dict:
        """The JSON shape this capability was loaded from ('del', not 'dele')."""
        return {
            "owner": self.owner,
            "pre": self.pre,
            "add": list(self.add),
            "del": list(self.dele),
            "assigns": dict(self.assigns),
            "nondet": dict(self.nondet),
        }


@dataclass
class Pack:
    name: str
    roles: list[str]
    capabilities: dict[str, Capability]
    protocol: list[dict]
    goal: Any
    init_true: list[str] = field(default_factory=list)
    init_constraints: list[Any] = field(default_factory=list)
    skills: dict[str, list] = field(default_factory=dict)  # declared S_p

    @staticmethod
    def load(d: dict) -> Pack:
        validate_pack(d)
        return Pack(
            name=d["name"],
            roles=list(d.get("roles", [])),
            capabilities={n: Capability.from_dict(n, c)
                          for n, c in d.get("capabilities", {}).items()},
            protocol=canon_assumes(d.get("protocol", [])),
            goal=d["goal"],
            init_true=list(d.get("init_true", [])),
            init_constraints=list(d.get("init_constraints", [])),
            skills=dict(d.get("skills", {})),
        )

    @staticmethod
    def load_file(path: str | Path) -> Pack:
        with open(path, encoding="utf-8") as fh:
            return Pack.load(json.load(fh))

    def to_dict(self) -> dict:
        """Convert back to the JSON pack shape, so that a Pack built in
        memory can be put through the same schema gate as untrusted
        front-end output.  Typed conversion: a capability table that does not
        hold Capability values is itself a malformed pack."""
        if not isinstance(self.capabilities, dict):
            raise PackError("capabilities must be a dict")
        caps = {}
        for n, c in self.capabilities.items():
            if not isinstance(c, Capability):
                raise PackError(
                    f"cap[{n}]: expected a Capability, got "
                    f"{type(c).__name__}")
            caps[n] = c.to_dict()
        return {
            "name": self.name,
            "roles": list(self.roles),
            "capabilities": caps,
            "protocol": list(self.protocol),
            "goal": self.goal,
            "init_true": list(self.init_true),
            "init_constraints": list(self.init_constraints),
            "skills": {r: list(s) for r, s in self.skills.items()},
        }


def normalize(pack: Pack | dict) -> Pack:
    """The schema-gated typed form of a pack, from either accepted shape.

    Both inputs (raw dict, Pack object) go through validate_pack, so nothing
    reaches the checker unvalidated, and both converge on the same normalized
    object, so a pack's identity does not depend on how it was handed over.
    """
    return Pack.load(pack.to_dict() if isinstance(pack, Pack) else pack)


def pack_digest(pack: Pack | dict) -> str:
    """Deterministic identity of a pack: sha256 of its canonical JSON.

    Packs that differ only in omitted defaults or key order share a digest;
    any change to a capability, the protocol, or the goal changes it.  This
    is what makes a verdict quotable: it names the object it decided.
    """
    canon = json.dumps(normalize(pack).to_dict(), sort_keys=True,
                       separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _has_assumes(steps: list) -> bool:
    return any("choice" in s and "assumes" in s["choice"] for s in iter_steps(steps))


def canon_assumes(steps: list) -> list:
    """`steps` with every choice's `assumes` in normal form: labels sorted,
    predicates sorted and deduplicated, empty entries dropped.  A protocol with
    no `assumes` is returned unchanged (the same object), so packs written
    before branch assumptions existed normalize exactly as before."""
    if not _has_assumes(steps):
        return steps
    out = []
    for s in steps:
        (kind, body), = s.items()
        if kind == "choice":
            b = {k: v for k, v in body.items() if k not in ("branches", "assumes")}
            b["branches"] = {lbl: canon_assumes(br) for lbl, br in body["branches"].items()}
            assumes = {lbl: sorted(set(preds))
                       for lbl, preds in sorted((body.get("assumes") or {}).items()) if preds}
            if assumes:
                b["assumes"] = assumes
            out.append({"choice": b})
        elif kind == "rec":
            out.append({"rec": {**body, "body": canon_assumes(body["body"])}})
        else:
            out.append(s)
    return out


def assumed_atoms(steps: list) -> set:
    """Every predicate some choice branch of `steps` assumes."""
    return {pred for s in iter_steps(steps) if "choice" in s
            for preds in (s["choice"].get("assumes") or {}).values() for pred in preds}


def iter_steps(steps: list[dict]) -> Iterator[dict]:
    """Every step of a protocol block, depth-first: nested choice branches and
    rec bodies included."""
    for s in steps:
        yield s
        if "choice" in s:
            for branch in s["choice"]["branches"].values():
                yield from iter_steps(branch)
        elif "rec" in s:
            yield from iter_steps(s["rec"]["body"])


def _is_name(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _check_goal_marker(body: Any, p: str, goal: Any, what: str) -> None:
    try:
        validate_formula(body, p)
    except FormulaError as e:
        raise PackError(str(e)) from e
    if body != goal:
        raise PackError(f"{p}: goal {what} must equal the pack's declared goal")


def _check_rec_head(body: Any, p: str, rec_names: set) -> None:
    if not (isinstance(body, dict) and set(body) == {"name", "body"}
            and _is_name(body.get("name"))
            and isinstance(body.get("body"), list)):
        raise PackError(f"{p}: rec needs name+body")
    if body["name"] in rec_names:
        raise PackError(f"{p}: duplicate rec name {body['name']!r}")


def _check_steps(steps: Any, path: str, goal: Any,
                 rec_scope: frozenset = frozenset(),
                 rec_names: set | None = None) -> None:
    if rec_names is None:
        rec_names = set()
    if not isinstance(steps, list):
        raise PackError(f"{path}: protocol block must be a list")
    for i, s in enumerate(steps):
        p = f"{path}[{i}]"
        if not (isinstance(s, dict) and len(s) == 1):
            raise PackError(f"{p}: step must be a single-key dict")
        (kind, body), = s.items()
        if kind == "act":
            if not (isinstance(body, dict)
                    and set(body) == {"cap", "by"}
                    and _is_name(body["cap"]) and _is_name(body["by"])):
                raise PackError(f"{p}: act needs cap+by")
            # An undeclared cap is deliberately allowed through the gate:
            # the checker reports it as MISSING_CAPABILITY with a frontier.
        elif kind == "msg":
            if not isinstance(body, dict):
                raise PackError(f"{p}: msg body must be a dict")
            if set(body) != {"from", "to", "label"}:
                raise PackError(f"{p}: msg needs exactly from+to+label")
            for k in ("from", "to", "label"):
                if not _is_name(body[k]):
                    raise PackError(f"{p}: msg needs {k!r}")
            if body["from"] == body["to"]:
                raise PackError(f"{p}: message sender and receiver must differ")
        elif kind == "choice":
            if not (isinstance(body, dict) and "by" in body
                    and _is_name(body["by"])
                    and isinstance(body.get("branches"), dict)
                    and set(body) <= {"by", "branches", "external", "observed",
                                      "assumes"}):
                raise PackError(f"{p}: choice needs by+branches")
            if not body["branches"]:
                raise PackError(f"{p}: choice needs at least one branch")
            if "assumes" in body:
                _check_assumes(body["assumes"], body["branches"], p)
            for flag in ("external", "observed"):
                if not isinstance(body.get(flag, False), bool):
                    raise PackError(f"{p}: choice {flag!r} must be a bool")
            for lbl, br in body["branches"].items():
                if not _is_name(lbl):
                    raise PackError(f"{p}: choice labels must be non-empty strings")
                _check_steps(br, f"{p}.{lbl}", goal, rec_scope, rec_names)
        elif kind == "goal":
            _check_goal_marker(body, p, goal, "marker")
        elif kind == "rec":
            _check_rec_head(body, p, rec_names)
            if (len(body["body"]) == 1
                    and body["body"][0] == {"continue": body["name"]}):
                raise PackError(
                    f"{p}: recursion must be guarded by a protocol step")
            rec_names.add(body["name"])
            _check_steps(body["body"], f"{p}.body", goal,
                         rec_scope | {body["name"]}, rec_names)
        elif kind == "continue":
            if not isinstance(body, str):
                raise PackError(f"{p}: continue needs a rec name")
            if body not in rec_scope:
                raise PackError(f"{p}: continue {body!r} has no enclosing rec")
            if i != len(steps) - 1:
                raise PackError(f"{p}: continue must be in tail position "
                                f"(the decidable fragment is tail-recursive)")
        elif kind == "spawn":
            if not (isinstance(body, dict) and set(body) == {"role"}
                    and _is_name(body["role"])):
                raise PackError(f"{p}: spawn needs role")
        else:
            raise PackError(f"{p}: unknown step kind {kind!r}")


def _check_assumes(assumes: Any, branches: dict, p: str) -> None:
    """`assumes` maps branch labels of this choice to predicate-name lists."""
    if not isinstance(assumes, dict):
        raise PackError(f"{p}: choice 'assumes' must map branch labels to predicate lists")
    for lbl, preds in assumes.items():
        if lbl not in branches:
            raise PackError(f"{p}: choice 'assumes' names {lbl!r}, which is not a branch "
                            "of this choice")
        if not (isinstance(preds, list) and all(_is_name(x) for x in preds)):
            raise PackError(f"{p}: choice 'assumes'[{lbl!r}] must be a list of predicate "
                            "names")


def _check_local_steps(steps: Any, path: str,
                       goal: Any,
                       rec_scope: frozenset = frozenset(),
                       rec_names: set | None = None) -> None:
    if rec_names is None:
        rec_names = set()
    if not isinstance(steps, list):
        raise PackError(f"{path}: local behaviour must be a list")
    for i, s in enumerate(steps):
        p = f"{path}[{i}]"
        if not (isinstance(s, dict) and len(s) == 1):
            raise PackError(f"{p}: local step must be a single-key dict")
        (kind, body), = s.items()
        if kind == "send":
            if not (isinstance(body, dict) and set(body) == {"to", "label"}
                    and _is_name(body["to"]) and _is_name(body["label"])):
                raise PackError(f"{p}: send needs to+label")
        elif kind == "recv":
            if not (isinstance(body, dict) and set(body) == {"from", "label"}
                    and _is_name(body["from"]) and _is_name(body["label"])):
                raise PackError(f"{p}: recv needs from+label")
        elif kind == "act":
            if not (isinstance(body, dict) and set(body) == {"cap"}
                    and _is_name(body["cap"])):
                raise PackError(f"{p}: act needs cap")
        elif kind in ("select", "branch"):
            if not (isinstance(body, dict) and isinstance(body.get("branches"), dict)
                    and body["branches"]
                    and set(body) == ({"branches"} if kind == "select"
                                      else {"from", "branches"})):
                raise PackError(f"{p}: {kind} needs non-empty branches")
            if kind == "branch" and not _is_name(body["from"]):
                raise PackError(f"{p}: branch needs from")
            for lbl, br in body["branches"].items():
                if not _is_name(lbl):
                    raise PackError(f"{p}: choice labels must be non-empty strings")
                _check_local_steps(br, f"{p}.{lbl}", goal,
                                   rec_scope, rec_names)
        elif kind == "rec":
            _check_rec_head(body, p, rec_names)
            meaningful = [step for step in body["body"]
                          if not (isinstance(step, dict) and "goal" in step)]
            if meaningful == [{"continue": body["name"]}]:
                raise PackError(
                    f"{p}: recursion must be guarded by a local action")
            rec_names.add(body["name"])
            _check_local_steps(body["body"], f"{p}.body",
                               goal, rec_scope | {body["name"]}, rec_names)
        elif kind == "continue":
            if not (isinstance(body, str) and body in rec_scope):
                raise PackError(f"{p}: continue needs an enclosing rec name")
            if i != len(steps) - 1:
                raise PackError(f"{p}: continue must be in tail position")
        elif kind == "goal":
            _check_goal_marker(body, p, goal, "annotation")
        else:
            raise PackError(f"{p}: unknown local step kind {kind!r}")


def _check_owners(caps: dict, protocol: list) -> None:
    """An act must be performed by its capability's declared owner, when one is declared."""
    for step in iter_steps(protocol):
        act = step.get("act")
        if not isinstance(act, dict):
            continue
        owner = (caps.get(act.get("cap")) or {}).get("owner")
        if owner not in (None, "?") and owner != act.get("by"):   # "?": no owner declared
            raise PackError(f"act {act.get('cap')!r} by {act.get('by')!r}: capability is "
                            f"owned by {owner!r}")


def validate_pack(pack: Any) -> None:
    """Raise PackError if structurally malformed.  Returns None on success.

    This is the only gate between untrusted front-end output and the trusted
    core; check() runs it on dicts and on Pack objects alike (via
    Pack.to_dict), so no in-memory pack can slip past it.
    """
    if not isinstance(pack, dict):
        raise PackError("pack must be a JSON object")
    for k in ("name", "capabilities", "protocol", "goal"):
        if k not in pack:
            raise PackError(f"missing top-level key {k!r}")
    if not _is_name(pack["name"]):
        raise PackError("name must be a non-empty string")
    roles = pack.get("roles", [])
    if not (isinstance(roles, list) and all(_is_name(r) for r in roles)):
        raise PackError("roles must be a list of non-empty strings")
    if len(roles) != len(set(roles)):
        raise PackError("roles must be unique")
    caps = pack["capabilities"]
    if not isinstance(caps, dict):
        raise PackError("capabilities must be a dict")
    try:
        for cn, c in caps.items():
            if not _is_name(cn):
                raise PackError("capability names must be non-empty strings")
            if not isinstance(c, dict):
                raise PackError(f"cap[{cn}] must be a dict")
            if not set(c) <= CAP_FIELDS:
                raise PackError(f"cap[{cn}] has unknown fields")
            if "owner" in c and not _is_name(c["owner"]):
                raise PackError(f"cap[{cn}].owner must be a non-empty string")
            validate_formula(c.get("pre", True), f"cap[{cn}].pre")
            for lst in ("add", "del"):
                v = c.get(lst, [])
                if not (isinstance(v, list) and all(isinstance(x, str) for x in v)):
                    raise PackError(f"cap[{cn}].{lst} must be a list of predicate names")
            assigns = c.get("assigns", {})
            nondet = c.get("nondet", {})
            if not isinstance(assigns, dict):
                raise PackError(f"cap[{cn}].assigns must be a dict")
            if not isinstance(nondet, dict):
                raise PackError(f"cap[{cn}].nondet must be a dict")
            for v, expr in assigns.items():
                if not _is_name(v):
                    raise PackError(f"cap[{cn}].assigns keys must be variable names")
                validate_expr(expr, f"cap[{cn}].assigns[{v}]")
            for v, constr in nondet.items():
                if not _is_name(v):
                    raise PackError(f"cap[{cn}].nondet keys must be variable names")
                validate_formula(constr, f"cap[{cn}].nondet[{v}]")
        validate_formula(pack["goal"], "goal")
        _check_steps(pack["protocol"], "protocol", pack["goal"])
        _check_owners(caps, pack["protocol"])
        skills = pack.get("skills", {})
        if not isinstance(skills, dict):
            raise PackError("skills must be a dict role -> local behaviour")
        for role, ssteps in skills.items():
            if not _is_name(role):
                raise PackError("skills keys must be non-empty role names")
            _check_local_steps(ssteps, f"skills[{role}]", pack["goal"])
        it = pack.get("init_true", [])
        if not (isinstance(it, list) and all(isinstance(x, str) for x in it)):
            raise PackError("init_true must be a list of predicate names")
        init_constraints = pack.get("init_constraints", [])
        if not isinstance(init_constraints, list):
            raise PackError("init_constraints must be a list")
        for i, f in enumerate(init_constraints):
            validate_formula(f, f"init_constraints[{i}]")
    except FormulaError as e:
        raise PackError(str(e)) from e


# --------------------------------------------------------------------------
# P2g++ dead-reply prune (PLAN.md Addendum E-c)
# --------------------------------------------------------------------------

def _read_atoms(pack: dict, skip: set) -> set:
    """Every predicate the pack reads, ignoring the capabilities in `skip`:
    capability guards and nondet constraints, the goal and goal markers,
    init constraints, and message labels."""
    from .formula import atoms
    read = set(atoms(pack.get("goal")))
    for name, c in (pack.get("capabilities") or {}).items():
        if name in skip:
            continue
        read |= atoms(c.get("pre", True))
        for f in (c.get("nondet") or {}).values():
            read |= atoms(f)
    for f in pack.get("init_constraints") or []:
        read |= atoms(f)
    for s in iter_steps(pack.get("protocol") or []):
        if "goal" in s:
            read |= atoms(s["goal"])
        elif "msg" in s:
            read.add(s["msg"]["label"])
    return read


def _drop_acts(steps: list, caps: set) -> list | None:
    """`steps` without the act steps of `caps`; None when that would leave a
    loop body with no protocol step before its `continue` (an unguarded
    recursion the schema gate rejects)."""
    out = []
    for s in steps:
        (kind, body), = s.items()
        if kind == "act" and body["cap"] in caps:
            continue
        if kind == "choice":
            branches = {}
            for lbl, br in body["branches"].items():
                nb = _drop_acts(br, caps)
                if nb is None:
                    return None
                branches[lbl] = nb
            out.append({"choice": {**body, "branches": branches}})
        elif kind == "rec":
            nb = _drop_acts(body["body"], caps)
            if nb is None or not nb or all("continue" in x for x in nb):
                return None
            out.append({"rec": {**body, "body": nb}})
        else:
            out.append(s)
    return out


def prune_dead_reply(pack: dict, bindings: dict, via: str = "reply") -> tuple[dict, list]:
    """P2g++'s deterministic prune of dead `reply` Tools.

    A capability bound `via reply` (in the CE `bindings`) that only adds
    predicates -- no `del`, `assigns`, `nondet` or `needs` -- and whose added
    predicates occur in no guard, no Goal (or goal marker), no init
    constraint and no message label is removed, together with its act steps.
    Removal repeats until nothing more is dead (a reply Tool read only by a
    removed one is dead too).  A capability is kept when removing its steps
    would leave a loop without a guarding step, and nothing is pruned in a
    pack that declares per-role `skills`.  Returns (new pack, removed names);
    the input is not modified."""
    import copy
    if pack.get("skills"):
        return pack, []
    caps = pack.get("capabilities") or {}

    def candidate(name: str, c: dict) -> bool:
        b = bindings.get(name) or {}
        return (b.get("via") == via and not b.get("needs") and not c.get("del")
                and not c.get("assigns") and not c.get("nondet"))

    removed: list = []
    protocol = pack.get("protocol") or []
    while True:
        read = _read_atoms(pack, set(removed))
        dead = [n for n, c in caps.items() if n not in removed and candidate(n, c)
                and not (set(c.get("add") or []) & read)]
        kept_any = False
        for n in sorted(dead):
            nb = _drop_acts(protocol, set(removed) | {n})
            if nb is None:
                continue
            removed.append(n)
            protocol = nb
            kept_any = True
        if not kept_any:
            break
    if not removed:
        return pack, []
    out = copy.deepcopy(pack)
    for n in removed:
        del out["capabilities"][n]
    out["protocol"] = protocol
    return out, removed

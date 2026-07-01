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
             | {"choice": {"by": "<role>", "branches": {"<label>": [<step>...], ...}}}
             | {"goal":   <formula>}       // explicit goal marker (optional)

validate_pack() is the deterministic schema gate on untrusted front-end
output: it rejects malformed packs before they reach the checker.  It does NOT
check semantic faithfulness (that declared effects match real tools) -- that
is the honest-declaration obligation of the runtime layer.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .formula import FormulaError, validate_expr, validate_formula

STEP_KINDS = ("act", "msg", "choice", "goal")


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


@dataclass
class Pack:
    name: str
    roles: list[str]
    capabilities: dict[str, Capability]
    protocol: list[dict]
    goal: Any
    init_true: list[str] = field(default_factory=list)
    init_constraints: list[Any] = field(default_factory=list)

    @staticmethod
    def load(d: dict) -> "Pack":
        validate_pack(d)
        caps = {}
        for n, c in d.get("capabilities", {}).items():
            caps[n] = Capability(
                name=n,
                owner=c.get("owner", "?"),
                pre=c.get("pre", True),
                add=list(c.get("add", [])),
                dele=list(c.get("del", [])),
                assigns=dict(c.get("assigns", {})),
                nondet=dict(c.get("nondet", {})),
            )
        return Pack(
            name=d["name"],
            roles=list(d.get("roles", [])),
            capabilities=caps,
            protocol=d.get("protocol", []),
            goal=d["goal"],
            init_true=list(d.get("init_true", [])),
            init_constraints=list(d.get("init_constraints", [])),
        )

    @staticmethod
    def load_file(path: str | Path) -> "Pack":
        with open(path, encoding="utf-8") as fh:
            return Pack.load(json.load(fh))


def _check_steps(steps: Any, path: str) -> None:
    if not isinstance(steps, list):
        raise PackError(f"{path}: protocol block must be a list")
    for i, s in enumerate(steps):
        p = f"{path}[{i}]"
        if not (isinstance(s, dict) and len(s) == 1):
            raise PackError(f"{p}: step must be a single-key dict")
        (kind, body), = s.items()
        if kind == "act":
            if not (isinstance(body, dict) and "cap" in body and "by" in body):
                raise PackError(f"{p}: act needs cap+by")
            # An undeclared cap is deliberately allowed through the gate:
            # the checker reports it as MISSING_CAPABILITY with a frontier.
        elif kind == "msg":
            if not isinstance(body, dict):
                raise PackError(f"{p}: msg body must be a dict")
            for k in ("from", "to", "label"):
                if k not in body:
                    raise PackError(f"{p}: msg needs {k!r}")
        elif kind == "choice":
            if not (isinstance(body, dict) and "by" in body
                    and isinstance(body.get("branches"), dict)):
                raise PackError(f"{p}: choice needs by+branches")
            if not body["branches"]:
                raise PackError(f"{p}: choice needs at least one branch")
            for lbl, br in body["branches"].items():
                _check_steps(br, f"{p}.{lbl}")
        elif kind == "goal":
            try:
                validate_formula(body, p)
            except FormulaError as e:
                raise PackError(str(e)) from e
        else:
            raise PackError(f"{p}: unknown step kind {kind!r}")


def validate_pack(pack: Any) -> None:
    """Raise PackError if structurally malformed.  Returns None on success."""
    if not isinstance(pack, dict):
        raise PackError("pack must be a JSON object")
    for k in ("name", "capabilities", "protocol", "goal"):
        if k not in pack:
            raise PackError(f"missing top-level key {k!r}")
    caps = pack["capabilities"]
    if not isinstance(caps, dict):
        raise PackError("capabilities must be a dict")
    try:
        for cn, c in caps.items():
            if not isinstance(c, dict):
                raise PackError(f"cap[{cn}] must be a dict")
            validate_formula(c.get("pre", True), f"cap[{cn}].pre")
            for lst in ("add", "del"):
                v = c.get(lst, [])
                if not (isinstance(v, list) and all(isinstance(x, str) for x in v)):
                    raise PackError(f"cap[{cn}].{lst} must be a list of predicate names")
            for v, expr in c.get("assigns", {}).items():
                validate_expr(expr, f"cap[{cn}].assigns[{v}]")
            for v, constr in c.get("nondet", {}).items():
                validate_formula(constr, f"cap[{cn}].nondet[{v}]")
        _check_steps(pack["protocol"], "protocol")
        validate_formula(pack["goal"], "goal")
        it = pack.get("init_true", [])
        if not (isinstance(it, list) and all(isinstance(x, str) for x in it)):
            raise PackError("init_true must be a list of predicate names")
        for i, f in enumerate(pack.get("init_constraints", [])):
            validate_formula(f, f"init_constraints[{i}]")
    except FormulaError as e:
        raise PackError(str(e)) from e

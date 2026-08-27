"""Session-type engine: projection, merge, and Gay-Hole subtyping.

Implements the realizability and conformance premises of the achievability
judgment (paper section 5.2):

    Ach:   Γ ⊇ caps(G)     G ⇓ {T_p}     ∀p. S_p ≤ G↾p     Γ;G ⊨ ◇goal

* **Projection** G↾p (Proj-Sel / Proj-Brn / Proj-Mrg): extracts role p's
  local type from the global protocol.  For a choice p does not make, either
  every branch informs p with a distinguishing receive (Proj-Brn) or the
  branch behaviours must *merge* (Proj-Mrg).  Projection is partial:
  undefined exactly on the unobserved-choice condition, the static signature
  of a deadlocking handoff.
* **Merge** ⊓: label-union on external branches from the same sender,
  structural recursion on equal prefixes.
* **Subtyping** ≤ (Gay-Hole): a skill may offer MORE external (receive)
  choices and FEWER internal (send) choices than its contract (Sub-Ext /
  Sub-Int), decided coinductively over the regular trees.  Kept as a generic
  utility; it is *not* what the checker's conformance premise uses.
* **Direct conformance** ⊑ (canonical T-Comm): the relation the checker
  adapter `conformance_failure` decides.  Sender/internal selections must
  carry EXACTLY the contract's labels with conforming continuations;
  receiver/external branches may safely offer a superset.  Full Sub-Int is
  unsound here: a selector that drops a contract branch is not the protocol's
  sender, yet the checker's reachability may still return a witness through
  the excluded branch -- an unrealisable plan.

Local types are hashable tuples:

    ("end",)
    ("act",  cap, cont)
    ("send", to,  label, cont)
    ("recv", frm, label, cont)
    ("select", ((label, cont), ...))          # internal choice  (+)
    ("branch", frm, ((label, cont), ...))     # external choice  (&)
    ("rec", name, body) | ("var", name)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

END = ("end",)


class ProjectionError(ValueError):
    """Raised when the global type is not projectable to some role."""


# --------------------------------------------------------------------------
# Participants  prt(G)   (tas.tex; Lemma "participant agreement")
# --------------------------------------------------------------------------

def participants(steps: list[dict]) -> frozenset:
    """`prt(G)`: the roles a global protocol actually involves.

    Transcribes the paper's definition over the pack's step-list encoding of
    global types::

        prt(p->q:{l_i.G_i})  = {p,q} u U_i prt(G_i)
        prt(a@p.G)           = {p} u prt(G)
        prt(#phi.G)          = prt(G)          # a goal marker involves nobody
        prt(End)             = {}

    A `choice` by p is the encoding of an internal selection, so p is a
    participant of it even when a branch is empty; `rec`/`continue` are the
    tail-recursive encoding of mu X.G, so the binder contributes its body.
    `spawn` names the role it creates -- that role is a participant of any
    run in which the spawn fires, even though the pack as a whole then falls
    outside the decidable fragment.

    This is the `prt` of the paper's typing side conditions: T-Comm, T-Act
    and T-Goal each require the protocol's participants to agree with the
    session's, and the Participant-agreement lemma (`G |- (M;W)` implies
    `prt(G) = prt(M)`) is what subject reduction re-establishes at every
    step.
    """
    out: set[str] = set()
    for s in steps:
        if "act" in s:
            out.add(s["act"].get("by", "?"))
        elif "msg" in s:
            out.add(s["msg"]["from"])
            out.add(s["msg"]["to"])
        elif "choice" in s:
            out.add(s["choice"]["by"])
            for br in s["choice"]["branches"].values():
                out |= participants(br)
        elif "rec" in s:
            out |= participants(s["rec"]["body"])
        elif "spawn" in s:
            out.add(s["spawn"]["role"])
        # "goal" and "continue" contribute no participants
    return frozenset(out)


# --------------------------------------------------------------------------
# Merge  (Proj-Mrg)
# --------------------------------------------------------------------------

def merge(a: tuple, b: tuple) -> tuple:
    """The partial merge ⊓ on local types; raises ProjectionError when
    undefined."""
    if a == b:
        return a
    if a[0] == "branch" and b[0] == "branch" and a[1] == b[1]:
        da, db = dict(a[2]), dict(b[2])
        out = {}
        for lbl in sorted(set(da) | set(db)):
            if lbl in da and lbl in db:
                out[lbl] = merge(da[lbl], db[lbl])
            else:
                out[lbl] = da.get(lbl, db.get(lbl))
        return ("branch", a[1], tuple(sorted(out.items())))
    if a[0] == b[0] == "act" and a[1] == b[1]:
        return ("act", a[1], merge(a[2], b[2]))
    if a[0] == b[0] == "send" and a[1:3] == b[1:3]:
        return ("send", a[1], a[2], merge(a[3], b[3]))
    if a[0] == b[0] == "recv" and a[1:3] == b[1:3]:
        return ("recv", a[1], a[2], merge(a[3], b[3]))
    if a[0] == b[0] == "select" and {l for l, _ in a[1]} == {l for l, _ in b[1]}:
        da, db = dict(a[1]), dict(b[1])
        return ("select",
                tuple(sorted((l, merge(da[l], db[l])) for l in da)))
    raise ProjectionError(f"behaviours do not merge: {a[0]} vs {b[0]}")


# --------------------------------------------------------------------------
# Projection  G|p   (over the JSON step-list grammar of the pack)
# --------------------------------------------------------------------------

def project(steps: list[dict], role: str) -> tuple:
    """Project the global protocol onto `role`.  Raises ProjectionError on
    the unobserved-choice condition."""
    return _proj(list(steps), role)


def _proj(steps: list[dict], role: str) -> tuple:
    if not steps:
        return END
    s, rest = steps[0], steps[1:]
    (kind, body), = s.items()
    if kind == "goal":
        return _proj(rest, role)                       # contract annotation
    if kind == "act":
        cont = _proj(rest, role)
        if body.get("by") == role:
            return ("act", body["cap"], cont)
        return cont
    if kind == "msg":
        cont = _proj(rest, role)
        if body["from"] == role:
            return ("send", body["to"], body["label"], cont)
        if body["to"] == role:
            return ("recv", body["from"], body["label"], cont)
        return cont
    if kind == "rec":
        # tail-recursive loop: the fall-through continuation folds into the
        # body, so the whole remainder projects inside the rec binder.
        # A role with no behaviour in the loop projects to end (mu X.X = end).
        inner = _proj(list(body["body"]) + rest, role)
        if not _has_behavior(inner):
            return END
        if _occurs(inner, body["name"]):
            return ("rec", body["name"], inner)
        return inner
    if kind == "continue":
        return ("var", body)
    if kind == "spawn":
        raise ProjectionError(
            "dynamic participant spawning is outside the projectable fragment")
    if kind == "choice":
        chooser = body["by"]
        parts = {lbl: _proj(list(br) + rest, role)
                 for lbl, br in body["branches"].items()}
        if chooser == role:
            return ("select", tuple(sorted(parts.items())))
        if body.get("observed", False):
            # Observed choice: the selection happens on a medium every role
            # perceives directly (a live call, a shared thread) -- an
            # implicit broadcast of the branch label.  A role whose behaviour
            # does not depend on the branch merges as usual; otherwise
            # project as an external choice on the choice labels themselves
            # (Proj-Brn with the announcement made implicit).
            if len(set(parts.values())) == 1:
                return next(iter(parts.values()))
            return ("branch", chooser, tuple(sorted(parts.items())))
        # Proj-Brn: every branch informs `role` with a distinguishing receive
        heads = list(parts.values())
        if (all(h[0] == "recv" for h in heads)
                and len({h[2] for h in heads}) == len(heads)
                and len({h[1] for h in heads}) == 1):
            return ("branch", heads[0][1],
                    tuple(sorted((h[2], h[3]) for h in heads)))
        # Proj-Mrg: otherwise the branch behaviours must merge
        vals = list(parts.values())
        try:
            out = vals[0]
            for v in vals[1:]:
                out = merge(out, v)
            return out
        except ProjectionError:
            raise ProjectionError(
                f"role '{role}' must act in a branch of the choice by "
                f"'{chooser}' but receives no message distinguishing the "
                f"branches, and the branch behaviours do not merge "
                f"(unobserved choice -> deadlock/handoff failure)") from None
    raise ProjectionError(f"unknown step kind {kind!r}")


def _has_behavior(t: tuple) -> bool:
    """True if the local type contains any observable action or choice."""
    if t[0] in ("act", "send", "recv", "select", "branch"):
        return True
    if t[0] == "rec":
        return _has_behavior(t[2])
    return False


def _occurs(t: tuple, name: str) -> bool:
    if t[0] == "var":
        return t[1] == name
    if t[0] == "rec":
        return t[1] != name and _occurs(t[2], name)
    if t[0] in ("act",):
        return _occurs(t[2], name)
    if t[0] in ("send", "recv"):
        return _occurs(t[3], name)
    if t[0] == "select":
        return any(_occurs(c, name) for _, c in t[1])
    if t[0] == "branch":
        return any(_occurs(c, name) for _, c in t[2])
    return False


# --------------------------------------------------------------------------
# Declared skills:  parse the local-type step-list grammar into terms
# --------------------------------------------------------------------------

def parse_local(steps: list) -> tuple:
    """Parse a declared local behaviour S_p (JSON step list) into a term.

    Grammar mirrors the protocol:
      {"send": {"to","label"}} | {"recv": {"from","label"}}
      | {"select": {"branches": {label: [...]}}}
      | {"branch": {"from", "branches": {label: [...]}}}
      | {"act": {"cap"}} | {"rec": {"name","body"}} | {"continue": name}
      | {"goal": formula}                    (ignored: contract annotation)
    """
    if not steps:
        return END
    s, rest = steps[0], steps[1:]
    (kind, body), = s.items()
    if kind == "goal":
        return parse_local(rest)
    if kind == "send":
        return ("send", body["to"], body["label"], parse_local(rest))
    if kind == "recv":
        return ("recv", body["from"], body["label"], parse_local(rest))
    if kind == "act":
        return ("act", body["cap"], parse_local(rest))
    if kind == "select":
        return ("select", tuple(sorted(
            (l, parse_local(list(br) + rest))
            for l, br in body["branches"].items())))
    if kind == "branch":
        return ("branch", body["from"], tuple(sorted(
            (l, parse_local(list(br) + rest))
            for l, br in body["branches"].items())))
    if kind == "rec":
        inner = parse_local(list(body["body"]) + rest)
        return ("rec", body["name"], inner) if _occurs(inner, body["name"]) else inner
    if kind == "continue":
        return ("var", body)
    raise ProjectionError(f"unknown local step kind {kind!r}")


# --------------------------------------------------------------------------
# Gay-Hole subtyping   S <= T
# --------------------------------------------------------------------------

def _subst(t: tuple, name: str, rep: tuple) -> tuple:
    if t[0] == "var":
        return rep if t[1] == name else t
    if t[0] == "rec":
        return t if t[1] == name else ("rec", t[1], _subst(t[2], name, rep))
    if t[0] == "act":
        return ("act", t[1], _subst(t[2], name, rep))
    if t[0] in ("send", "recv"):
        return (t[0], t[1], t[2], _subst(t[3], name, rep))
    if t[0] == "select":
        return ("select", tuple((l, _subst(c, name, rep)) for l, c in t[1]))
    if t[0] == "branch":
        return ("branch", t[1], tuple((l, _subst(c, name, rep)) for l, c in t[2]))
    return t


def _unfold(t: tuple) -> tuple:
    while t[0] == "rec":
        t = _subst(t[2], t[1], t)
    return t


def subtype(s: tuple, t: tuple) -> bool:
    """Decide S <= T coinductively (regular trees: memo on visited pairs)."""
    return _sub(s, t, set())


def _sub(s: tuple, t: tuple, seen: set) -> bool:
    s, t = _unfold(s), _unfold(t)
    if (s, t) in seen:
        return True                       # coinductive hypothesis
    seen = seen | {(s, t)}
    if s == END and t == END:
        return True
    if s[0] == t[0] == "act":
        return s[1] == t[1] and _sub(s[2], t[2], seen)
    if s[0] == t[0] == "send" or s[0] == t[0] == "recv":
        return s[1] == t[1] and s[2] == t[2] and _sub(s[3], t[3], seen)
    if s[0] == t[0] == "branch":          # Sub-Ext: S offers MORE receives
        if s[1] != t[1]:
            return False
        ds, dt = dict(s[2]), dict(t[2])
        return set(ds) >= set(dt) and all(
            _sub(ds[l], dt[l], seen) for l in dt)
    if s[0] == t[0] == "select":          # Sub-Int: S makes FEWER selections
        ds, dt = dict(s[1]), dict(t[1])
        return set(ds) <= set(dt) and all(
            _sub(ds[l], dt[l], seen) for l in ds)
    return False


# --------------------------------------------------------------------------
# Direct conformance   S |- T   (canonical T-Comm)
# --------------------------------------------------------------------------

def conforms(s: tuple, t: tuple) -> bool:
    """Decide direct conformance S ⊑ T coinductively.

    Identical to ≤ on prefixes, but on choices it follows the canonical
    direct rule rather than Gay-Hole:

    * internal choice (``select``, the role's own sends): the declared label
      set must be EXACTLY the contract's.  Dropping a branch would leave the
      checker free to witness the goal through a branch the deployed skill
      never selects; adding one would emit a label no receiver expects.
    * external choice (``branch``, receives): the declared label set may be a
      SUPERSET of the contract's -- unrequested branches are simply never
      triggered -- and every contract label must conform.
    """
    return _conf(s, t, set())


def _conf(s: tuple, t: tuple, seen: set) -> bool:
    s, t = _unfold(s), _unfold(t)
    if (s, t) in seen:
        return True                       # coinductive hypothesis
    seen = seen | {(s, t)}
    if s == END and t == END:
        return True
    if s[0] == t[0] == "act":
        return s[1] == t[1] and _conf(s[2], t[2], seen)
    if s[0] == t[0] == "send" or s[0] == t[0] == "recv":
        return s[1] == t[1] and s[2] == t[2] and _conf(s[3], t[3], seen)
    if s[0] == t[0] == "branch":          # receiver: superset of labels is safe
        if s[1] != t[1]:
            return False
        ds, dt = dict(s[2]), dict(t[2])
        return set(ds) >= set(dt) and all(
            _conf(ds[l], dt[l], seen) for l in dt)
    if s[0] == t[0] == "select":          # sender: exactly the contract labels
        ds, dt = dict(s[1]), dict(t[1])
        return set(ds) == set(dt) and all(
            _conf(ds[l], dt[l], seen) for l in dt)
    return False


@dataclass(frozen=True)
class ConformanceReport:
    """Outcome of the conformance premise, including what it had to assume.

    `failure` is the refutation reason (None when the premise holds).
    `assumed` are the participants of G for which the pack declares no
    behaviour: the paper's judgment ranges over a whole session
    `M = prod_p p[S_p]` with `prt(G) = prt(M)`, so a pack that declares only
    some roles leaves the rest *assumed* to behave exactly as their projected
    contract.  That assumption is sound-by-construction for the reachability
    verdict (the checker decides G, not M), but it is a real premise of
    transporting the verdict to a deployment, so it is reported rather than
    left implicit.
    """
    failure: Optional[str] = None
    assumed: tuple = ()

    @property
    def ok(self) -> bool:
        return self.failure is None


def conformance_report(skills: dict[str, list],
                       protocol: list[dict]) -> ConformanceReport:
    """Decide ∀p. S_p ⊑ G↾p and record the participant-agreement residue.

    Two obligations, from the paper's side conditions:

    1. **Direct conformance** of every declared behaviour against its
       projected contract (exact sender labels, receiver-side extra branches
       only) -- the canonical direct rule, not full Gay-Hole subtyping.
    2. **Participant agreement** (`prt(G) = prt(M)`).  A declared role that
       is not a participant of G projects to `end`, so a non-trivial
       behaviour for it already fails obligation 1; the remaining direction
       -- a participant of G with no declared behaviour -- cannot be refuted
       (there is nothing to refute against), so it is returned in `assumed`.
    """
    for role, ssteps in sorted(skills.items()):
        try:
            contract = project(protocol, role)
        except ProjectionError as e:
            return ConformanceReport(
                f"cannot project contract for role '{role}': {e}")
        declared = parse_local(ssteps)
        if not conforms(declared, contract):
            return ConformanceReport(
                f"declared behaviour of role '{role}' does not conform to "
                f"its projected contract (S_{role} </= G|{role}): declared "
                f"{_show(declared)}, contract {_show(contract)}")
    assumed = tuple(sorted(participants(protocol) - set(skills)))
    return ConformanceReport(None, assumed)


def conformance_failure(skills: dict[str, list],
                        protocol: list[dict]) -> Optional[str]:
    """Check ∀p. S_p ⊑ G↾p (direct conformance).  Returns None if conformant,
    else a reason.

    This is the adapter the checker's conformance premise calls, so it decides
    the canonical *direct* rule (exact sender labels, receiver-side extra
    branches only) rather than full Gay-Hole subtyping."""
    return conformance_report(skills, protocol).failure


def _show(t: tuple, depth: int = 0) -> str:
    if depth > 4:
        return "..."
    if t == END:
        return "end"
    if t[0] == "act":
        return f"{t[1]}.{_show(t[2], depth + 1)}"
    if t[0] == "send":
        return f"{t[1]}!{t[2]}.{_show(t[3], depth + 1)}"
    if t[0] == "recv":
        return f"{t[1]}?{t[2]}.{_show(t[3], depth + 1)}"
    if t[0] == "select":
        return "+{" + ", ".join(f"{l}: {_show(c, depth + 1)}" for l, c in t[1]) + "}"
    if t[0] == "branch":
        return "&{" + ", ".join(f"{l}: {_show(c, depth + 1)}" for l, c in t[2]) + "}"
    if t[0] == "rec":
        return f"rec {t[1]}.{_show(t[2], depth + 1)}"
    if t[0] == "var":
        return t[1]
    return repr(t)

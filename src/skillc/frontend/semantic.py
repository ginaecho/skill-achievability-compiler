"""Build an achievability pack from what a skill document actually says.

`prose.py` reads the document; this module turns the reading into a pack:
roles, capabilities with guards/effects/numeric bounds, a protocol with
choices, messages and spawns, a goal formula, and declared per-role
behaviours.

The pack is only built when the document states a completion condition
("Your job is finished when ...") and lists workflow steps.  Anything less and
the caller keeps the legacy `used_<tool>` compaction, which is weaker but
never over-claims: a document that does not say when it is finished gives the
front-end nothing to refute.

Nothing here is specific to any skill: every rule keys on an ordinary English
convention.  Like the rest of the front-end it is untrusted -- a misreading
means the checker decides a different pack, not that the checker is wrong.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from ..profiles import normalize_tool
from .prose import (INVOKE_RE, Condition, Role, condition_predicate,
                    content_stems, find_num_clause, find_section, negated_before,
                    numbered_steps, parse_goal, parse_roles, quantity_var,
                    sentences, split_bullets, split_sections, stem,
                    stem_index)

WORKFLOW_HEADING = r"\b(workflow|contract|steps|procedure|process|protocol|instructions)\b"
TOOLS_HEADING = r"\btools?\b"
BEHAVIOUR_HEADING = r"declared\s+(?:(\w+)\s+)?behaviou?rs?"

# "The router inspects the ticket and picks one of two paths:"
CHOICE_CUE_RE = re.compile(
    r"\b(?:picks?|choose[sn]?|chooses|decides?|selects?|branches?)\b"
    r"[^.:]{0,60}?\b(?:one\s+of|whether|which|between|either|two|three)\b",
    re.I)

SPAWN_RE = re.compile(
    r"\bspawn(?:s|ed|ing)?\b\s+(?:a\s+|an\s+|the\s+)?"
    r"(?:fresh\s+|new\s+|extra\s+|additional\s+|further\s+)?([A-Za-z]+)", re.I)

SAY_VERBS = (r"tells?|told|informs?|notifies|notify|announces?|signals?"
             r"|sends?|messages?|passes")

WAITS_RE = re.compile(r"\bwaits?\s+for\s+`([A-Za-z][\w-]*)`", re.I)

BOLD_LABEL_RE = re.compile(r"^\s*[-*+]\s*\*\*([^*]+?)\*\*")
TICK_LABEL_RE = re.compile(r"^\s*[-*+]\s*`([A-Za-z][\w-]*)`")
LABEL_NOISE = ("branch", "branches", "path", "paths", "rail", "rails",
               "route", "routes", "case", "option")


# --------------------------------------------------------------------------
# Extracted events
# --------------------------------------------------------------------------

@dataclass
class Event:
    kind: str                       # "act" | "msg" | "spawn"
    pos: int
    cap: str = ""
    by: str = ""
    frm: str = ""
    to: str = ""
    label: str = ""
    role: str = ""                  # spawn: the role created

    def as_step(self) -> dict:
        if self.kind == "act":
            return {"act": {"cap": self.cap, "by": self.by}}
        if self.kind == "msg":
            return {"msg": {"from": self.frm, "to": self.to,
                            "label": self.label}}
        return {"spawn": {"role": self.role}}


@dataclass
class Build:
    """Accumulated pack pieces plus provenance for the inspection report."""
    predicates: dict[str, str] = field(default_factory=dict)   # stem -> name
    effects: dict[str, set] = field(default_factory=dict)      # cap -> preds
    owners: dict[str, str] = field(default_factory=dict)       # cap -> role
    notes: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Naming states
# --------------------------------------------------------------------------

def register_predicate(build: Build, phrase: str) -> Optional[str]:
    """Canonical predicate name for a state description, keyed by stem so
    "a confirmation has been sent" and "Send the email" name one state."""
    head = condition_predicate(phrase)
    if head is None:
        return None
    key = stem(head)
    return build.predicates.setdefault(key, head)


# --------------------------------------------------------------------------
# Tool mentions
# --------------------------------------------------------------------------

def _tool_stems(tool: str) -> list[str]:
    return [stem(p) for p in re.split(r"[_\-.]+", tool) if p]


def match_tools(text: str, tools: list[str]) -> list[tuple[str, int]]:
    """Declared tools this span names, with the offset that names them.

    A tool is named when every part of its name appears in the span -- as a
    backticked identifier, or in plain English ("Look up the order" names
    `lookup_order`).  When one tool's name is contained in another's, only the
    more specific one counts (`deliver_direct` beats `deliver`).
    """
    idx = stem_index(text)
    hits: dict[str, tuple[int, frozenset]] = {}
    for t in tools:
        parts = _tool_stems(t)
        if not parts or any(p not in idx for p in parts):
            continue
        lit = re.search(r"\b" + re.escape(t) + r"\b", text, re.I)
        pos = lit.start() if lit else max(idx[p] for p in parts)
        hits[t] = (pos, frozenset(parts))
    out = []
    for t, (pos, parts) in hits.items():
        if any(other != t and parts < oparts
               for other, (_, oparts) in hits.items()):
            continue
        out.append((t, pos))
    return sorted(out, key=lambda x: x[1])


# --------------------------------------------------------------------------
# Scanning one span of prose for protocol events
# --------------------------------------------------------------------------

def _role_at(roles: list[Role], text: str, pos: int, default: str) -> str:
    """The participant the sentence most recently named before `pos`."""
    best, best_pos = default, -1
    for r in roles:
        for alias in r.aliases:
            for m in re.finditer(r"\b" + re.escape(alias) + r"\b", text, re.I):
                if m.start() <= pos and m.start() > best_pos:
                    best, best_pos = r.name, m.start()
    return best


def _msg_events(text: str, roles: list[Role]) -> list[Event]:
    if len(roles) < 2:
        return []
    alt = "|".join(sorted((re.escape(a) for r in roles for a in r.aliases),
                          key=len, reverse=True))
    by_alias = {a: r.name for r in roles for a in r.aliases}
    out: list[Event] = []
    pat_a = re.compile(
        rf"\b(?:the\s+)?({alt})\s+(?:{SAY_VERBS})\s+(?:the\s+)?({alt})\s+"
        rf"(?:that\s+|with\s+|to\s+|the\s+label\s+)*`([A-Za-z][\w-]*)`", re.I)
    pat_b = re.compile(
        rf"\b(?:the\s+)?({alt})\s+(?:{SAY_VERBS})\s+`([A-Za-z][\w-]*)`\s+"
        rf"to\s+(?:the\s+)?({alt})", re.I)
    for m in pat_a.finditer(text):
        out.append(Event("msg", m.start(), frm=by_alias[m.group(1).lower()],
                         to=by_alias[m.group(2).lower()], label=m.group(3)))
    for m in pat_b.finditer(text):
        out.append(Event("msg", m.start(), frm=by_alias[m.group(1).lower()],
                         to=by_alias[m.group(3).lower()], label=m.group(2)))
    return out


def scan_span(text: str, tools: list[str], roles: list[Role],
              default_role: str) -> list[Event]:
    """Ordered protocol events a span of prose describes."""
    events: list[Event] = _msg_events(text, roles)
    msg_labels = {e.label for e in events}

    for tool, pos in match_tools(text, tools):
        events.append(Event("act", pos, cap=tool,
                            by=_role_at(roles, text, pos, default_role)))
    seen = {e.cap for e in events if e.kind == "act"}
    for m in INVOKE_RE.finditer(text):
        if negated_before(text, m.start()):
            continue
        cap = normalize_tool(m.group(1))
        if cap in seen or cap in msg_labels or "." in m.group(1):
            continue
        seen.add(cap)
        events.append(Event("act", m.start(1), cap=cap,
                            by=_role_at(roles, text, m.start(1), default_role)))

    for m in SPAWN_RE.finditer(text):
        if negated_before(text, m.start()):
            continue
        events.append(Event("spawn", m.start(),
                            role=m.group(1).lower().rstrip("s") or "helper"))

    return sorted(events, key=lambda e: e.pos)


def attribute_by_name(build: Build, conds: list[Condition],
                      invoked: list[str]) -> None:
    """A tool named after what a condition talks about establishes it.

    "the asset register has been **updated**" and a step that runs
    `register_asset`: the step's verb ("register") is not the goal's verb
    ("updated"), but the tool is named for exactly the thing the condition is
    about, so it is the establisher.  Applied only to conditions no step has
    already established, and only when the tool's name covers *every*
    content word of the condition -- a deliberate lean toward
    establishment, since a missed establisher is a false refutation and the
    checker's whole asymmetry is that refutations must not be wrong.
    """
    established = {p for preds in build.effects.values() for p in preds}
    for c in conds:
        if not c.predicate:
            continue
        name = build.predicates[stem(c.predicate)]
        if name in established:
            continue
        text = c.context or c.text
        head = stem(c.predicate)
        want = {s for s in content_stems(text) if s != head}
        if not want:
            continue
        for tool in invoked:
            if want <= set(_tool_stems(tool)):
                build.effects.setdefault(tool, set()).add(name)
                build.notes.append(
                    f"effect: `{tool}` is named for {sorted(want)} and so "
                    f"establishes '{name}'")
                break


def attribute_effects(build: Build, text: str, events: list[Event]) -> None:
    """Whichever act a span names next to a state description establishes it."""
    acts = [e for e in events if e.kind == "act"]
    if not acts:
        return
    idx = stem_index(text)
    for key, name in build.predicates.items():
        if key not in idx:
            continue
        off = idx[key]
        best = min(acts, key=lambda e: (0 if e.pos <= off else 1,
                                        abs(e.pos - off)))
        build.effects.setdefault(best.cap, set()).add(name)


# --------------------------------------------------------------------------
# Branch labels
# --------------------------------------------------------------------------

def branch_label(bullet: str, fallback: str) -> str:
    m = BOLD_LABEL_RE.match(bullet) or TICK_LABEL_RE.match(bullet)
    if not m:
        return fallback
    words = [w for w in re.split(r"[^A-Za-z0-9_]+", m.group(1).lower()) if w]
    words = [w for w in words if w not in LABEL_NOISE] or words
    return "_".join(words) or fallback


# --------------------------------------------------------------------------
# Tool notes: guards and numeric bounds
# --------------------------------------------------------------------------

REQUIRES_RE = re.compile(
    r"\b(?:requires?|needs?|only\s+runs?|will\s+only\s+run|refuses?)\b"
    r"[^.]*?\*\*([^*]+?)\*\*", re.I)


def read_tool_notes(build: Build, tools_body: str, tools: list[str],
                    var: Optional[str]) -> tuple[dict, dict, Optional[str]]:
    """Guards and numeric bounds the Tools section states about each tool."""
    pres: dict[str, list] = {}
    nondet: dict[str, dict] = {}
    for sent in sentences(tools_body):
        named = [t for t in tools
                 if re.search(r"`" + re.escape(t) + r"`", sent, re.I)]
        if not named:
            continue
        subject = named[0]
        for m in REQUIRES_RE.finditer(sent):
            pred = register_predicate(build, m.group(1))
            if pred:
                pres.setdefault(subject, []).append(pred)
                build.notes.append(
                    f"guard: `{subject}` requires {pred} ({m.group(1).strip()})")
        num = find_num_clause(sent)
        if num is not None:
            v = var or quantity_var(num.noun)
            var = var or v
            nondet[subject] = {v: {"cmp": [v, num.op, num.value]}}
            build.notes.append(
                f"bound: `{subject}` leaves {v} {num.op} {num.value}")
    return pres, nondet, var


# --------------------------------------------------------------------------
# Declared per-role behaviour
# --------------------------------------------------------------------------

def read_declared_behaviour(section_title: str, body: str, tools: list[str],
                            roles: list[Role]) -> tuple[Optional[str], list]:
    """(role, branch entries) from a 'Declared handler behaviour' section."""
    m = re.search(BEHAVIOUR_HEADING, section_title, re.I)
    if not m:
        return None, []
    who = (m.group(1) or "").lower()
    role = next((r.name for r in roles if who in r.aliases), None)
    if role is None:
        role = next((r.name for r in roles
                     if any(a in body.lower() for a in r.aliases)), None)
    if role is None:
        return None, []

    entries: list[tuple[str, str]] = []      # (label, body span)
    _, bullets = split_bullets(body)
    for b in bullets:
        lm = TICK_LABEL_RE.match(b)
        if lm:
            entries.append((lm.group(1), b[lm.end():]))
    if not entries:
        for sent in sentences(body):
            for wm in WAITS_RE.finditer(sent):
                if negated_before(sent, wm.start()):
                    continue
                entries.append((wm.group(1), sent[wm.end():]))
    return role, entries


# --------------------------------------------------------------------------
# The builder
# --------------------------------------------------------------------------

@dataclass
class SemanticResult:
    pack: dict
    notes: list[str]


def build(name: str, prose: str, declared: dict[str, str]) -> Optional[SemanticResult]:
    """Compile a skill document into a semantic pack, or None if the document
    does not state what "finished" means."""
    conds, var = parse_goal(prose)
    if not conds:
        return None
    sections = split_sections(prose)
    wf = find_section(sections, WORKFLOW_HEADING)
    if wf is None:
        return None
    steps_text = numbered_steps(wf.body)
    if not steps_text:
        return None

    roles = parse_roles(prose) or [Role("agent", frozenset({"agent"}))]
    default_role = roles[0].name
    tools = sorted(declared)

    build_ = Build()
    for c in conds:
        if c.predicate:
            build_.predicates.setdefault(stem(c.predicate), c.predicate)

    tools_sec = find_section(sections, TOOLS_HEADING)
    pres, nondet, var = read_tool_notes(
        build_, tools_sec.body if tools_sec else "", tools, var)

    # ---- protocol ------------------------------------------------------
    protocol: list[dict] = []
    choosers: list[str] = []
    for text in steps_text:
        head, bullets = split_bullets(text)
        if bullets and CHOICE_CUE_RE.search(head):
            chooser = _role_at(roles, head, len(head), default_role)
            choosers.append(chooser)
            branches: dict[str, list] = {}
            for i, b in enumerate(bullets):
                label = branch_label(b, f"b{i + 1}")
                evs = scan_span(b, tools, roles, default_role)
                attribute_effects(build_, b, evs)
                _record_owners(build_, evs)
                branches[label] = [e.as_step() for e in evs]
            if branches:
                protocol.append({"choice": {"by": chooser,
                                            "branches": branches}})
            continue
        evs = scan_span(text, tools, roles, default_role)
        attribute_effects(build_, text, evs)
        _record_owners(build_, evs)
        protocol.extend(e.as_step() for e in evs)

    if not protocol:
        return None
    attribute_by_name(build_, conds, _invoked_caps(protocol))

    # ---- capabilities ---------------------------------------------------
    capabilities: dict[str, dict] = {}
    for t in tools:
        cap: dict = {"owner": build_.owners.get(t, default_role)}
        guard = pres.get(t, [])
        if guard:
            cap["pre"] = guard[0] if len(guard) == 1 else {"and": guard}
        cap["add"] = sorted(build_.effects.get(t, ()))
        if t in nondet:
            cap["nondet"] = nondet[t]
        capabilities[t] = cap

    # ---- goal -----------------------------------------------------------
    conjuncts: list = []
    for c in conds:
        if c.predicate:
            conjuncts.append(build_.predicates[stem(c.predicate)])
        if c.num is not None:
            v = var or quantity_var(c.num.noun)
            conjuncts.append({"cmp": [v, c.num.op, c.num.value]})
    if not conjuncts:
        return None
    goal = conjuncts[0] if len(conjuncts) == 1 else {"and": conjuncts}

    # ---- declared behaviours -------------------------------------------
    skills: dict[str, list] = {}
    for sec in sections:
        role, entries = read_declared_behaviour(sec.title, sec.body, tools,
                                                roles)
        if not role or not entries:
            continue
        sender = _sender_to(protocol, role) or _other_role(roles, role) \
            or (choosers[0] if choosers else default_role)
        branches = {}
        for label, span in entries:
            evs = [e for e in scan_span(span, tools, roles, role)
                   if e.kind == "act"]
            branches[label] = [{"act": {"cap": e.cap}} for e in evs]
        skills[role] = [{"branch": {"from": sender, "branches": branches}}]
        build_.notes.append(
            f"declared behaviour for '{role}': {sorted(branches)}")

    pack = {
        "name": name,
        "roles": [r.name for r in roles],
        "capabilities": capabilities,
        "protocol": protocol,
        "goal": goal,
        "init_true": [],
    }
    if skills:
        pack["skills"] = skills
    return SemanticResult(pack, build_.notes)


def _invoked_caps(protocol: list[dict]) -> list[str]:
    out: list[str] = []
    for s in protocol:
        if "act" in s and s["act"]["cap"] not in out:
            out.append(s["act"]["cap"])
        if "choice" in s:
            for br in s["choice"]["branches"].values():
                out.extend(c for c in _invoked_caps(br) if c not in out)
        if "rec" in s:
            out.extend(c for c in _invoked_caps(s["rec"]["body"]) if c not in out)
    return out


def _record_owners(build_: Build, events: list[Event]) -> None:
    for e in events:
        if e.kind == "act":
            build_.owners.setdefault(e.cap, e.by)


def _sender_to(protocol: list[dict], role: str) -> Optional[str]:
    for s in protocol:
        if "msg" in s and s["msg"]["to"] == role:
            return s["msg"]["from"]
        if "choice" in s:
            for br in s["choice"]["branches"].values():
                got = _sender_to(br, role)
                if got:
                    return got
        if "rec" in s:
            got = _sender_to(s["rec"]["body"], role)
            if got:
                return got
    return None


def _other_role(roles: list[Role], role: str) -> Optional[str]:
    for r in roles:
        if r.name != role:
            return r.name
    return None

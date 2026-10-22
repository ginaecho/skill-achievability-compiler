"""The easy way in to `skillc twin`: explore a graph, paste a workflow.

    skillc twin explore building.ttl
        what the graph holds, how its entities connect, and which verifier
        questions it can already answer; the user describes nothing

    skillc twin check building.ttl --workflow workflow.md
        the workflow is pasted as written (a brief with "Evidence needed"
        tables, a bullet list, or a Markdown table); each evidence line is
        mapped to a built-in need or, failing that, searched for by name in
        the target's neighbourhood; the mapping is printed so the user can
        see how each line was understood

Reading the workflow is deterministic (patterns, no model), so the same text
always gives the same needs.  A line that says "when required", "where
required", "if available" or "optional" is a non-critical need.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from .twin import (PROBES, SCENARIOS, Evidence, Twin, TwinError, _is_bnode, _rdf_type,
                   _walk, candidates, decide, local, verify_all)

# --------------------------------------------------------------- reading a workflow

# built-in need -> patterns over the lower-cased need text
NEED_PATTERNS = {
    "target_scope": r"target scope|\bscope\b",
    "setpoint_identity": r"set[- ]?point identity|identity and type|\bidentity\b",
    "equipment": r"\bequipment\b|\bdevices?\b",
    "controlled_places": r"controlled place|\bplaces?\b|\bzones?\b|\brooms?\b|affected spaces?",
    "min_max_units": r"\bmin(imum)?\b|\bmax(imum)?\b|\blimits?\b|\bunits?\b|\bbounds?\b",
    "priority_state": r"\bpriority\b",
    "external_reference": r"external reference|bacnet (reference|object)|object identifier",
    "history": r"histor|time[- ]?series|\btrends?\b",
    "current_schedule": r"\bschedules?\b",
    "timezone": r"time ?zone|daylight",
    "calendar_rules": r"recurrence|\bexceptions?\b|\boverlaps?\b|\bholidays?\b",
    "operating_policy": r"polic(y|ies)|permitted hours|operating hours|\bconstraints?\b|approval",
    "operational_state": r"operational state|\boverrides?\b|\binterlocks?\b|current state",
}
# needs that only make sense for a schedule-like target
SCHEDULE_KEYS = {"target_scope", "current_schedule", "timezone", "calendar_rules",
                 "operating_policy", "operational_state"}
OPTIONAL = re.compile(r"when required|where required|if (available|required|needed)|optional|"
                      r"nice to have|if present", re.I)
WHY_VERBS = {"verify", "derive", "check", "assess", "add", "determine", "evaluate", "interpret",
             "identify", "ensure", "confirm", "compute", "detect", "establish", "provide",
             "avoid", "prevent", "show", "use", "read", "compare", "find", "know", "decide",
             "allow", "make", "get", "give", "tell", "trace"}
STOP = {"and", "the", "for", "with", "from", "that", "this", "when", "where", "required", "by",
        "relevant", "current", "associated", "configured", "evaluation", "of", "or", "if",
        "any", "all", "its", "their", "which", "data", "information", "value", "values"}
SCENARIO_HEAD = re.compile(r"^(?:#+\s*)?(?:scenario|workflow|use case|verifier)\b[^:]*"
                           r"[:\-–]\s*(.+)$", re.I)
EVIDENCE_HEAD = re.compile(r"^(?:#+\s*)?(evidence( needed| needs)?|needs|"
                           r"what (it|the verifier) needs)\s*:?\s*$", re.I)


@dataclass
class Need:
    text: str
    keys: list                      # built-in needs it maps to; empty = search by name
    critical: bool
    words: list = field(default_factory=list)

    def describe(self) -> str:
        how = (", ".join(self.keys) if self.keys
               else "search the graph for " + ", ".join(repr(w) for w in self.words))
        return f"{self.text!r} -> {how}{'' if self.critical else '  (when required)'}"


@dataclass
class Workflow:
    title: str
    kind: str                       # setpoint | schedule: which targets and probes
    needs: list

    def describe(self) -> str:
        what = "set points" if self.kind == "setpoint" else "zones, spaces or equipment"
        lines = [f"workflow {self.title!r}: checks {what}; {len(self.needs)} evidence needs"]
        lines += [f"  {n.describe()}" for n in self.needs]
        return "\n".join(lines)


def _keywords(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z\-]+", text.lower())
    out = []
    for w in words:
        for part in w.split("-"):
            if len(part) >= 4 and part not in STOP:
                part = part[:-1] if part.endswith("s") and not part.endswith("ss") else part
                if part not in out:
                    out.append(part)
    return out


def map_need(text: str) -> Need:
    low = text.lower()
    keys = [k for k, pat in NEED_PATTERNS.items() if re.search(pat, low)]
    if "target_scope" in keys:              # "target scope, affected spaces and equipment"
        keys = [k for k in keys if k not in ("equipment", "controlled_places")]
    if "current_schedule" in keys:          # "current schedule" is not "current state"
        keys = [k for k in keys if k != "operational_state" or "state" in low]
    if "priority_state" in keys and "external_reference" not in keys and "reference" in low:
        keys.append("external_reference")
    m = OPTIONAL.search(text)
    clean = (text[:m.start()] if m else text).strip(" ,;.-(")
    return Need(clean, keys, not OPTIONAL.search(text), [] if keys else _keywords(clean))


def _is_why(line: str) -> bool:
    first = re.split(r"\W+", line.strip(), maxsplit=1)[0].lower()
    return first in WHY_VERBS or line[:1].islower()


def _is_paragraph(line: str) -> bool:
    words = len(line.split())
    return words > 20 or (words >= 10 and line.rstrip().endswith((".", "?", "!")))


def _evidence_lines(block: list[str]) -> list[str]:
    """Evidence lines in one workflow block, from bullets, a Markdown table, or
    a flattened two-column table (need line, why line, need line, ...)."""
    out, in_section = [], False
    for i, line in enumerate(block):
        nxt = block[i + 1] if i + 1 < len(block) else ""
        if EVIDENCE_HEAD.match(line):
            in_section = True
            continue
        if not in_section:
            continue
        if re.match(r"^why( it matters)?\s*:?$", line, re.I):
            continue
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if cells and cells[0] and not re.match(r"^[-: ]+$", cells[0]) \
                    and not EVIDENCE_HEAD.match(cells[0]):
                out.append(cells[0])
            continue
        m = re.match(r"^\s*(?:[-*•]|\d+[.)])\s+(.*)$", line)
        if m:
            out.append(m.group(1).split(" — ")[0].split(": ")[0].strip())
            continue
        if _is_paragraph(line) or re.match(r"^(the verifier|verification|missing|note)\b",
                                           line, re.I):
            in_section = False
            continue
        if _is_why(line):
            continue
        if _is_paragraph(nxt) and not map_need(line).keys:
            in_section = False          # a heading followed by a paragraph
            continue
        out.append(line)
    return out


def _kind(title: str, needs: list[Need]) -> str:
    t = title.lower()
    if "schedule" in t:
        return "schedule"
    if "set-point" in t or "setpoint" in t or "set point" in t:
        return "setpoint"
    keys = {k for n in needs for k in n.keys}
    return "schedule" if keys & SCHEDULE_KEYS else "setpoint"


def read_workflows(text: str) -> list[Workflow]:
    """Every workflow in a pasted text: one per "Scenario N: ..." heading, or the
    whole text as one workflow."""
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    blocks, title, cur = [], None, []
    for ln in lines:
        m = SCENARIO_HEAD.match(ln)
        if m and len(ln.split()) <= 12:
            if cur and title is not None:
                blocks.append((title, cur))
            title, cur = m.group(1).strip(" #"), []
        elif title is not None:
            cur.append(ln)
    if title is not None:
        blocks.append((title, cur))
    if not blocks:
        blocks = [(lines[0].lstrip("# ") if lines else "workflow", lines)]
    out = []
    for title, block in blocks:
        needs = [map_need(t) for t in _evidence_lines(block)]
        if needs:
            out.append(Workflow(title, _kind(title, needs), needs))
    if not out:
        raise TwinError("no evidence needs found in the workflow; list them under a line "
                        "'Evidence needed', one per line or as bullets")
    return out


# --------------------------------------------------------------- checking a workflow

def _neighbourhood(twin: Twin, node) -> list:
    near = {node}
    for rel in ("point_of", "feeds", "part_of"):
        for direction in ("forward", "backward"):
            near.update(_walk(twin, node, rel, direction, lambda n: True, 2))
    return sorted(near, key=twin.label)


def _search(twin: Twin, node, need: Need, ev: Evidence):
    """A need with no built-in probe: look for its words in the names of the
    predicates and classes around the target."""
    from rdflib import Literal
    for n in _neighbourhood(twin, node):
        for p, o in twin.graph.predicate_objects(n):
            name = local(p).lower()
            cls = " ".join(twin.types(o)) if not _is_bnode(o) else ""
            for w in need.words:
                if w in name or (p != _rdf_type() and w in cls):
                    ev.status = "found"
                    shown = str(o) if isinstance(o, Literal) else twin.label(o)
                    ev.found.append(f"name match {w!r}: {twin.label(n)} {local(p)} {shown}")
                    break
        for t in twin.types(n):
            if any(w in t for w in need.words) and n != node:
                ev.status = "found"
                ev.found.append(f"name match: {twin.label(n)} is a {t}")
    if ev.status != "found":
        ev.note = "no predicate or class named like " + ", ".join(repr(w) for w in need.words) \
            + " near the target"


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return (s[:40].rstrip("_") or "need")


def verify_workflow(twin: Twin, wf: Workflow, target, declared=None):
    node = twin.resolve(target) if isinstance(target, str) else target
    probed = PROBES[wf.kind](twin, node)
    ev: dict[str, Evidence] = {}
    for need in wf.needs:
        if need.keys:
            for key in need.keys:
                if key in ev:
                    ev[key].critical = ev[key].critical or need.critical
                    continue
                if key in probed:
                    e = probed[key]
                    e.need, e.critical = need.text, need.critical
                else:   # a built-in need the other kind of probe answers: search by name
                    e = Evidence(key, need.text, "", need.critical)
                    _search(twin, node, Need(need.text, [], need.critical, _keywords(key)), e)
                ev[key] = e
        else:
            key = _slug(need.text)
            e = Evidence(key, need.text, "", need.critical)
            _search(twin, node, need, e)
            ev[key] = e
    return decide(twin, _slug(wf.title).replace("_", "-"), node, ev, declared)


def workflow_targets(twin: Twin, wf: Workflow):
    return candidates(twin, wf.kind)


# --------------------------------------------------------------- exploring a graph

def _cls(twin: Twin, n) -> str:
    names = sorted(local(c) for c in twin.graph.objects(n, _rdf_type()))
    return names[0] if names else "(untyped)"


def explore(twin: Twin, top: int = 20) -> str:
    """What the graph holds, how it connects, and what it can answer."""
    g = twin.graph
    onto = len(twin.schema) - len(g)
    out = [f"graph {twin.source}" + (f" (tenant {twin.tenant})" if twin.tenant else ""),
           f"  {len(g)} facts in the building data" + (f"; {onto} ontology facts used for "
                                                      "class names only" if onto > 0 else ""),
           ""]
    kinds = Counter(local(t) for _s, t in g.subject_objects(_rdf_type()))
    out.append("what is in it (entities by kind):")
    out += [f"  {n:4d}  {k}" for k, n in kinds.most_common(top)]

    links, values, structs = Counter(), {}, {}
    for s, p, o in g:
        if p == _rdf_type() or _is_bnode(s):
            continue
        if _is_bnode(o):
            fields = sorted({local(q) for q in g.predicates(o)} - {"type"})
            structs.setdefault((_cls(twin, s), local(p)), set()).update(fields)
        elif (o, None, None) in g:
            links[(_cls(twin, s), local(p), _cls(twin, o))] += 1
        else:
            values.setdefault(_cls(twin, s), set()).add(local(p))
    out += ["", "how it connects (kind --relation--> kind):"]
    out += [f"  {a} --{p}--> {b}  x{n}" for (a, p, b), n in links.most_common(top)]
    if structs:
        out += ["", "nested structures (read through their owner):"]
        out += [f"  {a} --{p}--> {{{', '.join(sorted(f))}}}"
                for (a, p), f in sorted(structs.items())]
    if values:
        out += ["", "properties with values:"]
        out += [f"  {a}: {', '.join(sorted(ps))}" for a, ps in sorted(values.items())]

    out += ["", "what it can answer (built-in verifiers):"]
    for name, s in SCENARIOS.items():
        res = verify_all(twin, name)
        if not res:
            out.append(f"  {s['title']}: no {s['target']} found")
            continue
        ok = sum(r.verdict == "ACHIEVABLE" for r in res)
        miss = Counter(e.key for r in res for e in r.missing)
        line = f"  {s['title']}: {ok} of {len(res)} targets have all critical evidence"
        if miss:
            line += "; most often missing: " + ", ".join(f"{k} ({n})"
                                                         for k, n in miss.most_common(4))
        out.append(line)
    out += ["", "next: paste your workflow into a file and run",
            f"  skillc twin check {twin.source} --workflow workflow.md"]
    return "\n".join(out) + "\n"

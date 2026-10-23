"""What a verifier can establish from an uploaded building graph (digital twin).

    building graph (RDF)  +  scenario evidence contract  +  target entity
        -> per evidence need: found (with the graph path that proves it),
           declared (an outside source the caller vouches for), or missing
        -> a pack whose `verify` step requires every critical need,
           decided by the trusted checker: ACHIEVABLE, or IMPOSSIBLE with
           the missing evidence as the reason

The graph is read offline from a file; nothing is fetched and no model is
called.  Evidence comes only from the tenant's instance data.  Ontology graphs
(named graphs whose name contains "ontology", or files passed as ontologies)
are used only to resolve class hierarchies: a vocabulary that *can* express a
relationship does not prove the relationship exists in this building.

Vocabularies differ between buildings (Brick, RealEstateCore, BOT, vendor
extensions), so predicates and classes are matched by local name, and every
relationship is followed in both directions (`hasPoint` / `isPointOf`,
`feeds` / `isFedBy`, `hasPart` / `isPartOf`, ...).  Blank-node structures such
as a BACnet priority array or an external reference are read through the
anchored relationship, never treated as reusable entities.

Refutations are relative to the graph that was read: "missing" means the
graph has no such evidence for this target, so the verifier cannot reach a
verdict from it, and missing evidence is never read as approval.
"""
from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from ..checker import check
from ..frontend.ce import compile_ce

TWIN_SCHEMA = "skillc.twin/1"

# Only formats that cannot pull remote content while parsing (JSON-LD can fetch
# a remote @context, so it is refused).
FORMATS = {".ttl": "turtle", ".turtle": "turtle", ".trig": "trig", ".nt": "nt",
           ".nq": "nquads", ".n3": "n3", ".rdf": "xml", ".owl": "xml", ".xml": "xml"}


class TwinError(ValueError):
    pass


# ---------------------------------------------------------------- vocabulary

def local(term) -> str:
    s = str(term)
    for sep in ("#", "/", ":"):
        if sep in s:
            s = s.rsplit(sep, 1)[1] or s
    return s


def _low(term) -> str:
    return local(term).lower().replace("_", "").replace("-", "")


# relation name -> (forward local names, inverse local names)
RELATIONS = {
    "point_of": ({"ispointof"}, {"haspoint"}),
    "feeds": ({"feeds", "serves", "suppliesto"}, {"isfedby", "servedby", "isservedby"}),
    "part_of": ({"ispartof", "locatedin", "islocatedin", "haslocation"},
                {"haspart", "islocationof", "containszone", "hasspace", "hasstorey",
                 "hasbuilding", "contains", "includes"}),
}

PLACE_WORDS = ("zone", "room", "space", "floor", "storey", "building", "site", "location",
               "wing", "region", "campus")
EQUIP_WORDS = ("equipment", "ahu", "vav", "fcu", "unit", "boiler", "chiller", "fan", "pump",
               "damper", "valve", "terminal", "hvac", "heater", "coil", "radiator")
POINT_WORDS = ("point", "setpoint", "sensor", "command", "status", "parameter", "alarm")
CALENDAR_WORDS = ("weekly", "recurr", "rrule", "exception", "holiday", "period", "day",
                  "effective")
POLICY_WORDS = ("policy", "operatinghours", "constraint", "permittedhours")


# ---------------------------------------------------------------- the graph

@dataclass
class Twin:
    graph: object                         # rdflib Graph: tenant instance data only
    schema: object                        # rdflib Graph: instance + ontology (types only)
    source: str
    tenant: str | None = None
    _types: dict = field(default_factory=dict)

    def label(self, node) -> str:
        from rdflib import BNode
        if isinstance(node, BNode):
            return "[blank node]"
        try:
            return self.graph.namespace_manager.normalizeUri(node)
        except Exception:
            return str(node)

    def resolve(self, name: str):
        """A full IRI, a prefixed name, or a local name unique in the graph."""
        from rdflib import URIRef
        subjects = set(self.graph.subjects())
        if ":" in name and not name.startswith("_"):
            try:
                iri = self.graph.namespace_manager.expand_curie(name)
                if iri in subjects:
                    return iri
            except Exception:
                pass
            if URIRef(name) in subjects:
                return URIRef(name)
        hits = [s for s in subjects if not _is_bnode(s) and local(s) == name]
        if len(hits) == 1:
            return hits[0]
        if not hits:
            raise TwinError(f"no entity named {name!r} in the building graph")
        raise TwinError(f"{name!r} is ambiguous: " + ", ".join(sorted(self.label(h) for h in hits)))

    def types(self, node) -> set[str]:
        """Lower-cased local names of the node's classes and their superclasses."""
        if node in self._types:
            return self._types[node]
        from rdflib import RDF, RDFS
        seen, out, todo = set(), set(), list(self.graph.objects(node, RDF.type))
        while todo:
            c = todo.pop()
            if c in seen:
                continue
            seen.add(c)
            out.add(_low(c))
            todo.extend(self.schema.objects(c, RDFS.subClassOf))
        self._types[node] = out
        return out

    def is_a(self, node, words) -> bool:
        return any(w in t for t in self.types(node) for w in words)

    def related(self, node, relation, direction="forward"):
        """Neighbours along a relation, whichever way round the graph states it.
        Yields (neighbour, predicate local name, stated_as_inverse)."""
        fwd, inv = RELATIONS[relation]
        if direction == "backward":
            fwd, inv = inv, fwd
        for p, o in self.graph.predicate_objects(node):
            if _low(p) in fwd:
                yield o, local(p), False
        for s, p in self.graph.subject_predicates(node):
            if _low(p) in inv:
                yield s, local(p), True

    def props(self, node, test):
        """(predicate local name, value) pairs whose predicate passes `test`."""
        return [(local(p), o) for p, o in self.graph.predicate_objects(node) if test(_low(p))]

    def fields(self, node) -> dict:
        """The fields of a (usually blank) structure, read through its anchor."""
        out = {}
        for p, o in self.graph.predicate_objects(node):
            out.setdefault(local(p), []).append(o)
        return out


def _is_bnode(term) -> bool:
    from rdflib import BNode
    return isinstance(term, BNode)


def _format(path: Path) -> str | None:
    """The rdflib format of a graph file; a sketch (.txt, .sketch) is read as TriG."""
    from .twin_sketch import SUFFIXES
    return "trig" if path.suffix.lower() in SUFFIXES else FORMATS.get(path.suffix.lower())


def _parse(path: Path, into):
    fmt = _format(path)
    if fmt is None:
        raise TwinError(f"{path.name}: unsupported graph format (use one of "
                        f"{', '.join(sorted(FORMATS))}, or a .txt sketch; JSON-LD is refused "
                        "because it can fetch remote contexts)")
    if path.suffix.lower() in FORMATS:
        into.parse(source=str(path), format=fmt)
        return
    from .twin_sketch import read_sketch
    into.parse(data=read_sketch(path.read_text(encoding="utf-8")).trig(), format="trig")


def load_twin(path, tenant: str | None = None, ontologies=()) -> Twin:
    """Read a building graph file, or a sketch of one (`env.twin_sketch`). A TriG / N-Quads
    file with several named graphs must say which tenant graph to use; ontology graphs are
    kept apart."""
    try:
        from rdflib import Dataset, Graph
    except ImportError as e:  # pragma: no cover - exercised only without the extra
        raise TwinError("reading a building graph needs rdflib: pip install 'skillc[twin]'") from e
    path = Path(path)
    instance, schema = Graph(), Graph()
    if _format(path) in ("trig", "nquads"):
        ds = Dataset()
        _parse(path, ds)
        default = str(ds.default_graph.identifier)
        named = [g for g in ds.graphs() if len(g) and str(g.identifier) != default
                 and "urn:x-rdflib:default" not in str(g.identifier)]
        onto = [g for g in named if "ontology" in str(g.identifier).lower()]
        tenants = [g for g in named if g not in onto]
        if tenant is not None:
            tenants = [g for g in tenants if str(g.identifier) == tenant
                       or str(g.identifier).endswith(f"tenant:{tenant}")]
            if not tenants:
                raise TwinError(f"no tenant graph {tenant!r} in {path.name}")
        if len(tenants) > 1:
            raise TwinError("several tenant graphs; choose one with --tenant: "
                            + ", ".join(str(g.identifier) for g in tenants))
        if tenants:
            for t in tenants[0]:
                instance.add(t)
        else:
            for t in ds.default_graph:
                instance.add(t)
        for g in onto:
            for t in g:
                schema.add(t)
        for prefix, ns in ds.namespaces():
            instance.bind(prefix, ns, override=False)
    else:
        _parse(path, instance)
    for o in ontologies:
        _parse(Path(o), schema)
    for t in instance:
        schema.add(t)
    if not len(instance):
        raise TwinError(f"{path.name}: the tenant graph is empty")
    return Twin(instance, schema, str(path), tenant)


# ---------------------------------------------------------------- evidence

@dataclass
class Evidence:
    key: str
    need: str
    why: str
    critical: bool
    status: str = "missing"          # found | declared | missing
    found: list = field(default_factory=list)    # human-readable proof lines
    note: str = ""

    def as_dict(self) -> dict:
        return {"key": self.key, "need": self.need, "why": self.why, "critical": self.critical,
                "status": self.status, "found": self.found, "note": self.note}


def _walk(twin: Twin, start, relation, direction, keep, max_hops=3):
    """Breadth-first along one relation; returns {node: path text} for nodes passing keep."""
    out, seen = {}, {start}
    todo = deque([(start, 0, twin.label(start))])
    while todo:
        node, hops, trail = todo.popleft()
        if hops >= max_hops:
            continue
        for nb, pred, inverse in twin.related(node, relation, direction):
            if nb in seen or _is_bnode(nb):
                continue
            seen.add(nb)
            step = f"{trail} {'<-' if inverse else '->'}{pred} {twin.label(nb)}"
            if keep(nb):
                out[nb] = step
            todo.append((nb, hops + 1, step))
    return out


def _is_point(twin, n):
    return twin.is_a(n, POINT_WORDS + ("limit",))


def _is_place(twin, n):
    # "Zone_Air_Temperature_Setpoint" names a zone but is a point
    return twin.is_a(n, PLACE_WORDS) and not _is_point(twin, n)


def _equipment_of(twin: Twin, point) -> dict:
    return _walk(twin, point, "point_of", "forward", lambda n: not _is_place(twin, n), 1)


def _places_of(twin: Twin, point, equipment: dict) -> dict:
    """Places a point affects: direct place of the point, places its equipment
    feeds (through intermediate equipment), places the equipment sits in, and
    the parts of those places (a zone's rooms)."""
    places = _walk(twin, point, "point_of", "forward", lambda n: _is_place(twin, n), 1)
    for eq in equipment:
        places.update(_walk(twin, eq, "feeds", "forward", lambda n: _is_place(twin, n)))
        places.update(_walk(twin, eq, "part_of", "forward", lambda n: _is_place(twin, n), 1))
    for place in list(places):
        for sub, path in _walk(twin, place, "part_of", "backward",
                               lambda n: _is_place(twin, n), 2).items():
            places.setdefault(sub, places[place] + path[len(twin.label(place)):])
    return places


def _bounds(twin: Twin, node):
    lo = twin.props(node, lambda p: any(w in p for w in
                                        ("minpresentvalue", "minvalue", "minimum", "minlimit",
                                         "lowlimit", "lowerlimit", "hasmin")))
    hi = twin.props(node, lambda p: any(w in p for w in
                                        ("maxpresentvalue", "maxvalue", "maximum", "maxlimit",
                                         "highlimit", "upperlimit", "hasmax")))
    return lo, hi


def _unit(twin: Twin, node):
    units = twin.props(node, lambda p: p in ("hasunit", "unit", "unitofmeasure",
                                             "hasunitofmeasure"))
    if units:
        return units[0][1]
    for _p, v in twin.props(node, lambda p: True):
        if _is_bnode(v):
            inner = twin.props(v, lambda p: p in ("hasunit", "unit", "unitofmeasure"))
            if inner:
                return inner[0][1]
    return None


def _limit_points(twin: Twin, equipment: dict):
    out = []
    for eq in equipment:
        for pt, _pred, _inv in twin.related(eq, "point_of", "backward"):
            ts = " ".join(twin.types(pt))
            if "limit" in ts and any(w in ts for w in ("min", "max", "low", "high")):
                out.append(pt)
    return out


def _structure(twin: Twin, node, words):
    """Values of predicates whose local name contains one of words, with their fields."""
    hits = []
    for pred, v in twin.props(node, lambda p: any(w in p for w in words)):
        anchored = _is_bnode(v) or (v, None, None) in twin.graph
        hits.append((pred, v, twin.fields(v) if anchored else {}))
    return hits


def _external_refs(twin: Twin, node):
    refs = _structure(twin, node, ("externalreference", "bacnetreference", "hasbacnet",
                                   "timeseriesreference"))
    bacnet, series = [], []
    for pred, v, f in refs:
        kinds = " ".join(_low(t) for t in twin.graph.objects(v, _rdf_type()))
        names = " ".join(k.lower() for k in f)
        text = f"{pred} {kinds} {names}"
        if "bacnet" in text or "objectidentifier" in names or "objectof" in names:
            bacnet.append((pred, v, f))
        if "timeseries" in text or "storedat" in names:
            series.append((pred, v, f))
    return bacnet, series


def _rdf_type():
    from rdflib import RDF
    return RDF.type


def _fields_text(f: dict) -> str:
    return ", ".join(sorted(f)) if f else "no fields"


def _priority(twin, pt):
    return _structure(twin, pt, ("priority",))


def _commandable_points(twin: Twin, equipment: dict):
    pts = []
    for eq in equipment:
        for pt, _pred, _inv in twin.related(eq, "point_of", "backward"):
            if twin.is_a(pt, ("setpoint", "command")):
                pts.append(pt)
    return pts


# ---------------------------------------------------------------- scenarios

SCENARIOS = {
    "setpoint": {
        "title": "Set-point verifier",
        "request": "Change this temperature set point to 22 degrees Celsius.",
        "target": "a set point",
        "evidence": [
            ("setpoint_identity", "Set-point identity and type", True,
             "Verify that the requested entity is the intended control point"),
            ("equipment", "Associated equipment", True,
             "Derive the affected scope from the graph"),
            ("controlled_places", "Controlled place(s)", True,
             "Derive the affected scope from the graph, rather than trusting a "
             "caller-provided place"),
            ("min_max_units", "Configured minimum/maximum and units", True,
             "Check the proposed value against the applicable equipment limits"),
            ("priority_state", "BACnet priority state", True,
             "Assess priority masking"),
            ("external_reference", "BACnet external reference", True,
             "Assess whether a commandable object is bounded"),
            ("history", "Historical series reference (BSTS)", False,
             "Time-series context, when the evaluation requires it"),
        ],
    },
    "schedule": {
        "title": "Schedule-update verifier",
        "request": "Add a Saturday cleaning period from 08:00 to 13:00 at 20 degrees Celsius.",
        "target": "a zone, space or piece of equipment",
        "evidence": [
            ("target_scope", "Target scope, affected spaces and equipment", True,
             "Determine which physical systems the schedule change affects"),
            ("priority_state", "BACnet priority state", True, "Assess priority masking"),
            ("external_reference", "BACnet external reference", True,
             "Assess whether a commandable object is bounded"),
            ("current_schedule", "Current schedule", True,
             "Evaluate the actual delta and revision consistency"),
            ("timezone", "Timezone", True,
             "Interpret the requested periods correctly, including daylight-saving transitions"),
            ("calendar_rules", "Recurrence, exceptions and overlaps", False,
             "Interpret recurrence and exception days"),
            ("operating_policy", "Authoritative operating policies and constraints", True,
             "Check permitted hours, limits, priorities and approval requirements"),
            ("operational_state", "Current operational state (overrides, interlocks)", False,
             "Identify applicable overrides or interlocks, where required"),
            ("history", "Historical series reference (BSTS)", False,
             "Time-series context, when the evaluation requires it"),
        ],
    },
}


def _new(scenario: str) -> dict[str, Evidence]:
    return {k: Evidence(k, need, why, crit)
            for k, need, crit, why in SCENARIOS[scenario]["evidence"]}


def _found(ev: Evidence, *lines):
    ev.status = "found"
    ev.found.extend(lines)


def _probe_setpoint(twin: Twin, t) -> dict[str, Evidence]:
    ev = _new("setpoint")
    types = twin.types(t)
    if any("setpoint" in x for x in types):
        classes = sorted(local(c) for c in twin.graph.objects(t, _rdf_type()))
        _found(ev["setpoint_identity"], f"{twin.label(t)} is a " + ", ".join(classes))
    else:
        shown = f" (types: {', '.join(sorted(types))})" if types else " (no type)"
        ev["setpoint_identity"].note = "the entity is not typed as a set point" + shown
    equipment = _equipment_of(twin, t)
    if equipment:
        _found(ev["equipment"], *equipment.values())
    else:
        ev["equipment"].note = "no point-of / has-point relationship to equipment"
    places = _places_of(twin, t, equipment)
    if places:
        _found(ev["controlled_places"], *places.values())
    else:
        ev["controlled_places"].note = ("no place reachable from the set point or its equipment "
                                        "(point-of, feeds, part-of / located-in)")
    _probe_limits(twin, t, equipment, ev["min_max_units"])
    _probe_bacnet(twin, [t], ev["priority_state"], ev["external_reference"], ev["history"])
    return ev


def _probe_limits(twin, t, equipment, ev: Evidence):
    lo, hi = _bounds(twin, t)
    unit = _unit(twin, t)
    if lo and hi:
        lines = [f"{twin.label(t)} {lo[0][0]} / {hi[0][0]}"]
    else:
        lims = _limit_points(twin, equipment)
        lines = [f"limit point {twin.label(p)}" for p in lims]
        if len(lims) < 2:
            lines = []
        if unit is None:
            for p in lims:
                unit = unit or _unit(twin, p)
    if lines and unit is not None:
        from rdflib import Literal
        _found(ev, *lines, f"unit {unit if isinstance(unit, Literal) else twin.label(unit)}")
    elif lines:
        ev.note = "limits present but no unit"
    else:
        ev.note = "no minimum/maximum on the set point and no min/max limit points on its equipment"


def _probe_bacnet(twin, points, priority: Evidence, external: Evidence, history: Evidence):
    for pt in points:
        for pred, _v, f in _priority(twin, pt):
            _found(priority, f"{twin.label(pt)} {pred} ({_fields_text(f)})")
        bacnet, series = _external_refs(twin, pt)
        for pred, _v, f in bacnet:
            _found(external, f"{twin.label(pt)} {pred} ({_fields_text(f)})")
        for pred, _v, f in series:
            _found(history, f"{twin.label(pt)} {pred} ({_fields_text(f)}); "
                            "the series itself is in BSTS, not read")
    where = "the point" if len(points) == 1 else "any commandable point"
    if priority.status != "found":
        priority.note = "no priority property on " + where
    if external.status != "found":
        external.note = "no BACnet external reference on " + where
    if history.status != "found":
        history.note = "no time-series reference"


def _schedules(twin: Twin, nodes):
    out = []
    for n in nodes:
        for pred, v in twin.props(n, lambda p: "schedule" in p):
            out.append((n, pred, v))
        for s, p in twin.graph.subject_predicates(n):
            if "schedule" in _low(p) or twin.is_a(s, ("schedule",)):
                out.append((n, local(p), s))
    return out


def _ancestors(twin: Twin, n) -> dict:
    return _walk(twin, n, "part_of", "forward", lambda x: True, max_hops=5)


def _probe_schedule(twin: Twin, t) -> dict[str, Evidence]:
    ev = _new("schedule")
    if _is_place(twin, t):
        spaces = {t: twin.label(t)}
        spaces.update(_walk(twin, t, "part_of", "backward", lambda n: _is_place(twin, n), 2))
        equipment = {}
        for sp in list(spaces):
            equipment.update(_walk(twin, sp, "feeds", "backward", lambda n: not _is_place(twin, n)))
            equipment.update(_walk(twin, sp, "part_of", "backward",
                                   lambda n: twin.is_a(n, EQUIP_WORDS), 1))
    else:
        equipment = {t: twin.label(t)}
        spaces = _places_of(twin, t, equipment)
    if spaces and equipment:
        _found(ev["target_scope"], *[f"space: {p}" for p in spaces.values()],
               *[f"equipment: {p}" for p in equipment.values()])
    else:
        ev["target_scope"].note = ("no equipment serving the target" if not equipment
                                   else "no space the target affects")
    points = _commandable_points(twin, equipment)
    _probe_bacnet(twin, points, ev["priority_state"], ev["external_reference"], ev["history"])
    if not points:
        none = "no commandable point on the equipment"
        ev["priority_state"].note = ev["external_reference"].note = none

    scope_nodes = [t, *spaces, *equipment, *points]
    scheds = _schedules(twin, scope_nodes)
    if scheds:
        _found(ev["current_schedule"],
               *[f"{twin.label(n)} {p} {twin.label(s)}" for n, p, s in scheds])
        sched_nodes = [s for _n, _p, s in scheds]
        rules = [(twin.label(s), k) for s in sched_nodes for k in twin.fields(s)
                 if any(w in k.lower() for w in CALENDAR_WORDS)]
        if rules:
            _found(ev["calendar_rules"], *[f"{s} {k}" for s, k in rules])
        else:
            ev["calendar_rules"].note = "the schedule has no recurrence or exception fields"
    else:
        sched_nodes = []
        ev["current_schedule"].note = ("no schedule linked to the target, its spaces, "
                                       "equipment or points")
        ev["calendar_rules"].note = "no schedule"

    up = {}
    for n in [t, *spaces, *equipment]:
        up.update(_ancestors(twin, n))
    tz_nodes = [t, *spaces, *equipment, *sched_nodes, *up]
    for n in tz_nodes:
        for pred, v in twin.props(n, lambda p: "timezone" in p or p == "tz"):
            _found(ev["timezone"], f"{twin.label(n)} {pred} {v}")
    if ev["timezone"].status != "found":
        ev["timezone"].note = "no timezone on the target, its schedule or any containing place"

    for n in [*tz_nodes, *points]:
        for pred, v in twin.props(n, lambda p: any(w in p for w in POLICY_WORDS)):
            _found(ev["operating_policy"], f"{twin.label(n)} {pred} {twin.label(v)}")
        for s, p in twin.graph.subject_predicates(n):
            if twin.is_a(s, ("policy", "operatinghours")):
                _found(ev["operating_policy"], f"{twin.label(s)} {local(p)} {twin.label(n)}")
    if ev["operating_policy"].status != "found":
        ev["operating_policy"].note = ("no operating policy, permitted hours or constraint "
                                       "in the graph")

    state = []
    for eq in equipment:
        for pt, _pred, _inv in twin.related(eq, "point_of", "backward"):
            if twin.is_a(pt, ("status", "override", "interlock", "mode")):
                state.append(f"{twin.label(eq)} point {twin.label(pt)}")
    if state:
        _found(ev["operational_state"], *state, "point values live in BSTS / BACnet, not read")
    else:
        ev["operational_state"].note = ("no status, override, interlock or mode point "
                                        "on the equipment")
    return ev


PROBES = {"setpoint": _probe_setpoint, "schedule": _probe_schedule}


def candidates(twin: Twin, scenario: str):
    """Every target the scenario can be asked about in this graph."""
    subjects = {s for s in twin.graph.subjects() if not _is_bnode(s)}
    if scenario == "setpoint":
        keep = [s for s in subjects
                if any("setpoint" in t and "limit" not in t for t in twin.types(s))]
    else:
        keep = [s for s in subjects if twin.is_a(s, ("zone",)) and not _is_point(twin, s)]
    return sorted(keep, key=twin.label)


# ---------------------------------------------------------------- the verdict

@dataclass
class TwinResult:
    scenario: str
    target: str
    evidence: list
    verdict: str            # ACHIEVABLE | IMPOSSIBLE
    reason: str
    coverage: str
    ce: str

    @property
    def missing(self):
        return [e for e in self.evidence if e.critical and e.status == "missing"]

    @property
    def assumed(self):
        return [e for e in self.evidence if e.critical and e.status == "declared"]

    def as_dict(self) -> dict:
        return {"scenario": self.scenario, "target": self.target, "verdict": self.verdict,
                "reason": self.reason, "coverage": self.coverage,
                "missing": [e.key for e in self.missing], "assumed": [e.key for e in self.assumed],
                "evidence": [e.as_dict() for e in self.evidence], "ce": self.ce}


def _pack_ce(scenario: str, evidence: list[Evidence]) -> str:
    """The verifier as a pack: one read per available evidence need, and a
    verify step that requires every critical need."""
    lines = [f"Skill `twin-{scenario}-verifier`.", "Roles: `deim`."]
    have = [e for e in evidence if e.status != "missing"]
    for e in have:
        src = "graph" if e.status == "found" else "declared"
        lines.append(f"Tool `read_{e.key}` (owner `deim`): adds `{e.key}`.  # {src}")
    crit = [e.key for e in evidence if e.critical]
    lines.append("Tool `verify` (owner `deim`): requires "
                 + " and ".join(f"`{k}`" for k in crit) + "; adds `verdict`.")
    lines += ["Goal: `verdict`.", "Protocol:"]
    lines += [f"  - `deim` uses `read_{e.key}`." for e in have]
    lines.append("  - `deim` uses `verify`.")
    return "\n".join(lines) + "\n"


def verify_target(twin: Twin, scenario: str, target, declared: dict | None = None) -> TwinResult:
    if scenario not in PROBES:
        raise TwinError(f"unknown scenario {scenario!r}; known: {', '.join(SCENARIOS)}")
    node = twin.resolve(target) if isinstance(target, str) else target
    return decide(twin, scenario, node, PROBES[scenario](twin, node), declared)


def decide(twin: Twin, scenario: str, node, ev: dict[str, Evidence],
           declared: dict | None = None) -> TwinResult:
    """Apply declared sources, build the verifier pack and let the checker decide."""
    for key, src in (declared or {}).items():
        if key not in ev:
            raise TwinError(f"--source {key}: not an evidence need here "
                            f"({', '.join(ev)})")
        if ev[key].status == "missing":
            ev[key].status = "declared"
            ev[key].found.append(f"declared outside the graph: {src} (not verified)")
    evidence = list(ev.values())
    ce = _pack_ce(scenario, evidence)
    v = check(compile_ce(ce))
    verdict = "UNKNOWN" if v.unknown else ("ACHIEVABLE" if v.achievable else "IMPOSSIBLE")
    return TwinResult(scenario, twin.label(node), evidence, verdict, v.reason, v.coverage, ce)


def verify_all(twin: Twin, scenario: str, declared=None) -> list[TwinResult]:
    return [verify_target(twin, scenario, n, declared) for n in candidates(twin, scenario)]


# ---------------------------------------------------------------- reports

def text_report(results: list[TwinResult], verbose: bool = True) -> str:
    out = []
    for r in results:
        tag = r.verdict
        if r.verdict == "ACHIEVABLE" and r.assumed:
            tag = "ACHIEVABLE under assumptions"
        head = f"{r.target}: {tag}"
        if r.missing:
            head += "  missing: " + ", ".join(e.key for e in r.missing)
        out.append(head)
        if not verbose:
            continue
        for e in r.evidence:
            mark = {"found": "OK ", "declared": "OK*",
                    "missing": "NO " if e.critical else "-- "}[e.status]
            crit = "" if e.critical else " (when required)"
            out.append(f"  {mark} {e.key}{crit}")
            for line in e.found[:4]:
                out.append(f"        {line}")
            if len(e.found) > 4:
                out.append(f"        ... {len(e.found) - 4} more")
            if e.status == "missing" and e.note:
                out.append(f"        {e.note}")
        out.append(f"  checker: {r.reason} ({r.coverage})")
        out.append("")
    if len(results) > 1:
        ok = sum(r.verdict == "ACHIEVABLE" for r in results)
        counts: dict[str, int] = {}
        for r in results:
            for e in r.missing:
                counts[e.key] = counts.get(e.key, 0) + 1
        line = f"{len(results)} targets: {ok} achievable, {len(results) - ok} impossible"
        if counts:
            line += " (missing: " + ", ".join(f"{k} x{n}" for k, n in
                                               sorted(counts.items(), key=lambda kv: -kv[1])) + ")"
        out.append(line)
    return "\n".join(out).rstrip() + "\n"


def as_json(twin: Twin, results: list[TwinResult]) -> str:
    return json.dumps({"schema": TWIN_SCHEMA, "graph": twin.source, "tenant": twin.tenant,
                       "results": [r.as_dict() for r in results]}, indent=1)


def scenarios_text() -> str:
    out = []
    for name, s in SCENARIOS.items():
        out.append(f"{name}: {s['title']} (target: {s['target']})")
        out.append(f'  e.g. "{s["request"]}"')
        for key, need, crit, _why in s["evidence"]:
            out.append(f"  {'*' if crit else ' '} {key:20s} {need}")
    out.append("* = critical: the verifier cannot reach a verdict without it")
    return "\n".join(out) + "\n"

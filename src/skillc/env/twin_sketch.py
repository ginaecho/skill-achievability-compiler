"""Read a building sketch (a plain description or an arrow scribble) into a building graph.

People describe a building's interactions the way they talk or draw on a whiteboard:

    AHU-1 -> VAV-11 -> Zone 11              (an arrow: the first feeds the next)
    Zone 11 is in Floor 1                   (part of; also "contains", "has rooms")
    SP-11 on VAV-11: 16..26 degC, priority 9, BACnet analog-value,11, history ts-sp11
    Schedule S-1 for VAV-11: Mon-Fri 07:00-19:00, Sat 08:00-13:00, except 2026-12-25
    Policy office-hours for Zone 11: hours 06:00-20:00, setpoints 18..24
    HQ timezone Europe/Berlin

The same statements can be written as sentences ("AHU-1 feeds VAV-11. Room 101 is in Zone
11."). Each line or sentence is read deterministically into the triples `make_campus.py`
writes, so the twin verifiers (`env.twin`) work on a sketch exactly as on an RDF file.
Nothing is guessed: a line that matches no statement form is reported as not understood, and
a fact a sketch does not state stays missing.  Kinds come from names: AHU, VAV, FCU, boiler,
pump are equipment; building, floor, zone, room are places; SP / set point, occupancy and
sensor names are points.  A picture of a sketch is turned into this text by a model first
(the demo does that, opt-in), and the text is then read here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

SUFFIXES = (".txt", ".sketch")
ARROW = re.compile(r"\s*(?:-->|->|→|=>)\s*")
LIST = re.compile(r"\s*(?:,|;|&|\band\b)\s*", re.I)
NUM = r"-?\d+(?:\.\d+)?"
RANGE = re.compile(rf"({NUM})\s*(?:\.\.|to|–|—)\s*({NUM})\s*(°\s*[CF]|deg\s*[CF]|[CF]\b)?",
                   re.I)
TIME = r"\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}"
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

EQUIPMENT = {"ahu": "AHU", "vav": "VAV", "fcu": "FCU", "rtu": "RTU", "boiler": "Boiler",
             "chiller": "Chiller", "pump": "Pump", "fan": "Fan", "heat pump": "Heat_Pump",
             "radiator": "Radiator", "damper": "Damper", "valve": "Valve"}
PLACES = {"building": "Building", "hq": "Building", "site": "Building", "campus": "Building",
          "floor": "Floor", "level": "Floor", "storey": "Floor", "zone": "HVAC_Zone",
          "room": "Room", "office": "Room", "space": "Room", "wing": "Wing"}
POINTS = {"sp": "Zone_Air_Temperature_Setpoint", "setpoint": "Zone_Air_Temperature_Setpoint",
          "set point": "Zone_Air_Temperature_Setpoint", "occupancy": "Occupancy_Status",
          "occ": "Occupancy_Status", "temperature sensor": "Zone_Air_Temperature_Sensor",
          "sensor": "Zone_Air_Temperature_Sensor", "status": "Status"}

HEAD = """# Building graph read from a sketch by skillc (env/twin_sketch.py).
@prefix brick: <https://brickschema.org/schema/Brick#> .
@prefix ref:   <https://brickschema.org/schema/Brick/ref#> .
@prefix bacnet: <http://data.ashrae.org/bacnet/2020#> .
@prefix unit:  <http://qudt.org/vocab/unit/> .
@prefix rdfs:  <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex:    <urn:bdt:sketch:> .

<bdt:ontology:sketch> {
  ex:WeeklySchedule rdfs:subClassOf ex:Schedule .
  ex:OperatingPolicy rdfs:subClassOf ex:Policy .
}
"""


@dataclass
class Entity:
    key: str
    label: str
    cls: str | None = None                       # e.g. "brick:VAV"
    facts: list[str] = field(default_factory=list)


@dataclass
class Sketch:
    entities: dict[str, Entity] = field(default_factory=dict)
    read: list[tuple[int, str, str]] = field(default_factory=list)   # line, text, meaning
    ignored: list[tuple[int, str]] = field(default_factory=list)

    def trig(self) -> str:
        body = [HEAD, "<bdt:tenant:sketch> {"]
        for e in self.entities.values():
            parts = ([f"a {e.cls}"] if e.cls else []) + [f'rdfs:label "{_esc(e.label)}"']
            parts += list(dict.fromkeys(e.facts))
            body.append(f"  ex:{e.key} " + " ;\n      ".join(parts) + " .")
        body.append("}")
        return "\n".join(body) + "\n"

    def summary(self) -> str:
        lines = [f"read {len(self.read)} statement(s) into {len(self.entities)} entities"]
        lines += [f"  line {n}: {meaning}" for n, _t, meaning in self.read]
        if self.ignored:
            lines.append(f"not understood ({len(self.ignored)}), so not in the graph:")
            lines += [f"  line {n}: {t}" for n, t in self.ignored]
        return "\n".join(lines)


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "unnamed"


def _clean(name: str) -> str:
    name = re.sub(r"^(?:the|a|an)\s+", "", name.strip().strip("`*\"'"), flags=re.I)
    return name.strip(" .:")


def _kind(name: str) -> tuple[str, str] | None:
    """(group, class) from the name's leading words, e.g. ("equipment", "brick:VAV")."""
    low = name.lower()
    for group, table in (("point", POINTS), ("equipment", EQUIPMENT), ("place", PLACES)):
        for word in sorted(table, key=len, reverse=True):
            if re.match(rf"{re.escape(word)}(?![a-z])", low):
                return group, f"brick:{table[word]}"
    return None


class _Reader:
    def __init__(self):
        self.s = Sketch()

    def node(self, name: str, default: str | None = None) -> Entity:
        name = _clean(name)
        key = _slug(name)
        e = self.s.entities.get(key)
        if e is None:
            e = self.s.entities[key] = Entity(key, name)
        if e.cls is None:
            kind = _kind(name)
            e.cls = kind[1] if kind else default
        return e

    def names(self, text: str) -> list[str]:
        return [n for n in (_clean(x) for x in LIST.split(text)) if n]

    # -- statement forms; each returns a description of what it read, or None ----------

    def arrows(self, line: str) -> str | None:
        parts = [p for p in ARROW.split(line) if p.strip()]
        if len(parts) < 2 or not ARROW.search(line):
            return None
        for a, b in zip(parts, parts[1:], strict=False):
            for x in self.names(a):
                for y in self.names(b):
                    self.link(x, y)
        return "feeds: " + " -> ".join(_clean(p) for p in parts)

    def link(self, a: str, b: str) -> None:
        """An arrow between two places draws containment (a zone -> its rooms); any other
        arrow is a feed (equipment -> equipment or place)."""
        ka, kb = _kind(_clean(a)), _kind(_clean(b))
        if ka and kb and ka[0] == kb[0] == "place":
            self.node(b).facts.append(f"brick:isPartOf ex:{self.node(a).key}")
        else:
            self.node(a, "brick:Equipment").facts.append(f"brick:feeds ex:{self.node(b).key}")

    def feeds(self, line: str) -> str | None:
        m = re.match(r"(.+?)\s+(?:feeds|serves|supplies(?: air to)?)\s+(.+)$", line, re.I)
        if not m:
            return None
        for x in self.names(m[1]):
            for y in self.names(m[2]):
                self.link(x, y)
        return f"feeds: {m[1]} -> {m[2]}"

    def timezone(self, line: str) -> str | None:
        tz = r"([A-Za-z_]+/[A-Za-z_]+|UTC)"
        m = (re.match(rf"(?:the\s+)?time ?zone of (.+?) is {tz}$", line, re.I)
             or re.match(rf"(.+?)[,:]?\s+(?:has\s+)?time ?zone\s*(?:is\s*)?{tz}$", line, re.I))
        if not m:
            return None
        self.node(m[1], "brick:Building").facts.append(f'brick:timezone "{m[2]}"')
        return f"timezone of {_clean(m[1])}: {m[2]}"

    def schedule(self, line: str) -> str | None:
        m = re.match(r"(?:weekly\s+)?schedule\s+(.+?)\s+(?:for|on|applies to)\s+(.+?)\s*:\s*(.+)$",
                     line, re.I)
        if not m:
            return None
        s = self.node(m[1])
        s.cls = "ex:WeeklySchedule"
        targets = self.names(m[2])
        week = []
        for d1, d2, t in re.findall(
                rf"\b([A-Za-z]{{3}})[a-z]*(?:\s*(?:-|to|–)\s*([A-Za-z]{{3}})[a-z]*)?\s+({TIME})",
                m[3]):
            days = _days(d1, d2)
            week += [f'ex:{d} "{t.replace(" ", "")}"' for d in days]
        exceptions = re.findall(r"\d{4}-\d{2}-\d{2}", m[3])
        if not week:
            return None
        s.facts += [f"ex:appliesTo ex:{self.node(t).key}" for t in targets]
        s.facts.append("ex:weeklySchedule [ " + " ; ".join(week) + " ]")
        s.facts += [f'ex:exceptionSchedule [ ex:date "{d}" ]' for d in exceptions]
        return f"schedule {s.label} for {', '.join(targets)}"

    def policy(self, line: str) -> str | None:
        m = re.match(r"(?:operating\s+)?policy\s+(.+?)\s+(?:for|on|applies to)\s+(.+?)\s*:\s*(.+)$",
                     line, re.I)
        if not m:
            return None
        p = self.node(m[1])
        p.cls = "ex:OperatingPolicy"
        hours = re.search(rf"hours?\s+({TIME})", m[3], re.I)
        if hours:
            p.facts.append(f'ex:permittedHours "{hours[1].replace(" ", "")}"')
        limits = RANGE.search(re.sub(rf"hours?\s+{TIME}", "", m[3], flags=re.I))
        if limits:
            p.facts += [f"ex:minSetpoint {float(limits[1])}", f"ex:maxSetpoint {float(limits[2])}"]
        for t in self.names(m[2]):
            self.node(t).facts.append(f"ex:operatingPolicy ex:{p.key}")
        return f"policy {p.label} for {_clean(m[2])}"

    def point_on(self, line: str) -> str | None:
        m = re.match(r"(.+?)\s+(?:is a point (?:of|on)|is on|on|point of)\s+(.+?)"
                     r"(?:\s*:\s*(.+))?$", line, re.I)
        if m:
            point, owner, attrs = m[1], m[2], m[3]
        else:
            m = re.match(r"(.+?)\s+has points?\s+(.+)$", line, re.I)
            if not m:
                return None
            owner, point, attrs = m[1], m[2], None
        e = self.node(owner, "brick:Equipment")
        names = self.names(point)
        for name in names:
            e.facts.append(f"brick:hasPoint ex:{self.node(name, 'brick:Point').key}")
        said = f"point {', '.join(names)} on {e.label}"
        if attrs and len(names) == 1:
            said += "; " + self.attributes(names[0], attrs)
        return said

    def part_of(self, line: str) -> str | None:
        m = re.match(r"(.+?)\s+(?:is in|is part of|is located in|located in|belongs to|"
                     r"are in|are part of|are located in|belong to|inside|in)\s+(.+)$", line, re.I)
        if m:
            children, parent = self.names(m[1]), m[2]
        else:
            m = re.match(r"(.+?)\s+(?:contains|includes|has)\s+(?:(?:rooms|zones|floors|spaces)"
                         r"\s*:?\s+)?(.+)$", line, re.I)
            if not m:
                return None
            children, parent = self.names(m[2]), m[1]
        if not children:
            return None
        p = self.node(parent, "brick:Location")
        for c in children:
            self.node(c, "brick:Location").facts.append(f"brick:isPartOf ex:{p.key}")
        return f"part of {p.label}: {', '.join(children)}"

    def attributes(self, name: str, spec: str) -> str:
        e = self.node(name, "brick:Point")
        said = []
        rng = RANGE.search(spec)
        if rng:
            e.facts += [f"brick:minPresentValue {float(rng[1])}",
                        f"brick:maxPresentValue {float(rng[2])}"]
            said.append(f"limits {rng[1]}..{rng[2]}")
        named = re.search(r"\bunit\s+(°\s*[CF]|deg\s*[CF])", spec, re.I)
        unit = (rng and rng[3]) or (named[1] if named else None)
        if unit:
            e.facts.append("brick:hasUnit unit:" + ("DEG_F" if unit.strip()[-1].upper() == "F"
                                                    else "DEG_C"))
            said.append("unit")
        prio = re.search(r"\bpriority\s+(\d+)", spec, re.I)
        if prio:
            e.facts.append(f"ex:priorityArray [ ex:activePriority {int(prio[1])} ]")
            said.append(f"priority {prio[1]}")
        refs = []
        bac = re.search(r"\bbacnet\s+([\w-]+(?:\s*,\s*\d+)?)", spec, re.I)
        if bac:
            refs.append(f'[ a ref:BACnetReference ; bacnet:object-identifier '
                        f'"{bac[1].replace(" ", "")}" ]')
            said.append("BACnet reference")
        ts = re.search(r"\b(?:history|time ?series|timeseries|bsts)\s+([\w-]+)", spec, re.I)
        if ts:
            refs.append(f'[ a ref:TimeseriesReference ; ref:hasTimeseriesId "{ts[1]}" ]')
            said.append("history reference")
        if refs:
            e.facts.append("ref:hasExternalReference " + " , ".join(refs))
        return ", ".join(said) or "no attribute understood"

    def attrs_line(self, line: str) -> str | None:
        m = re.match(r"([^:]+?)\s*:\s*(.+)$", line)
        if not m:
            return None
        said = self.attributes(m[1], m[2])
        return None if said == "no attribute understood" else f"{_clean(m[1])}: {said}"


def _days(d1: str, d2: str | None) -> list[str]:
    short = [d[:3] for d in DAYS]
    try:
        a = short.index(d1.lower()[:3])
        b = short.index(d2.lower()[:3]) if d2 else a
    except ValueError:
        return []
    return DAYS[a:b + 1] if a <= b else DAYS[a:] + DAYS[:b + 1]


def _statements(text: str):
    """(line number, statement): one per line, and one per sentence in a prose line."""
    for n, raw in enumerate(text.splitlines(), 1):
        line = re.sub(r"\s+#.*$|^#.*$", "", raw).strip()
        line = re.sub(r"^(?:[-*•]|\d+[.)])\s+", "", line).strip()
        if not line:
            continue
        for part in re.split(r"(?<=[a-z0-9)])\.\s+(?=[A-Z])", line):
            part = part.strip().rstrip(".").strip()
            if part:
                yield n, part


def read_sketch(text: str) -> Sketch:
    r = _Reader()
    forms = (r.arrows, r.schedule, r.policy, r.timezone, r.feeds, r.point_on, r.part_of,
             r.attrs_line)
    for n, stmt in _statements(text):
        for form in forms:
            said = form(stmt)
            if said:
                r.s.read.append((n, stmt, said))
                break
        else:
            r.s.ignored.append((n, stmt))
    return r.s

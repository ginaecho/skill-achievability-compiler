"""Room context for the demo, derived from the same graph relations as the verifier."""
from skillc.env.twin import (
    EQUIP_WORDS,
    POLICY_WORDS,
    _ancestors,
    _equipment_of,
    _is_place,
    _places_of,
    _schedules,
    candidates,
)


def describe_case(twin):
    subjects = sorted(set(twin.graph.subjects()), key=twin.label)
    places = [n for n in subjects if _is_place(twin, n)]
    rooms = [n for n in places if twin.is_a(n, ("room",))]
    points = {}
    for point in candidates(twin, "setpoint"):
        equipment = _equipment_of(twin, point)
        points[point] = (equipment, _places_of(twin, point, equipment))
    zones = set(candidates(twin, "schedule"))
    descriptions = []
    for room in rooms:
        ancestors = _ancestors(twin, room)
        controls = [p for p, (_eq, scope) in points.items() if room in scope]
        equipment = {eq for p in controls for eq in points[p][0]}
        scope = {room, *ancestors, *controls, *equipment}
        schedules = {s for _n, _p, s in _schedules(twin, scope)}
        scope.update(schedules)
        policies = set()
        for node in scope:
            policies.update(v for _p, v in twin.props(
                node, lambda p: any(word in p for word in POLICY_WORDS))
                if (v, None, None) in twin.graph)
            policies.update(s for s, _p in twin.graph.subject_predicates(node)
                            if twin.is_a(s, ("policy", "operatinghours")))
        details = [str(v) for _p, v in twin.props(
            room, lambda p: p in ("description", "comment"))]
        descriptions.append({
            "id": twin.label(room),
            "description": " ".join(details),
            "containers": [twin.label(n) for n in ancestors],
            "equipment": sorted(twin.label(n) for n in equipment),
            "setpoints": [twin.label(n) for n in controls],
            "schedule_targets": sorted(twin.label(n) for n in zones & {room, *ancestors}),
            "paths": [points[p][1][room] for p in controls],
            "context_nodes": sorted(twin.label(n) for n in scope | policies),
        })
    return {
        "counts": {
            "buildings": sum(twin.is_a(n, ("building",)) for n in places),
            "floors": sum(twin.is_a(n, ("floor", "storey")) for n in places),
            "zones": len(zones),
            "rooms": len(rooms),
            "equipment": sum(twin.is_a(n, EQUIP_WORDS) for n in subjects
                             if n not in places and n not in points),
            "setpoints": len(points),
        },
        "rooms": descriptions,
    }

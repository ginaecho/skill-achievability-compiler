import json
from pathlib import Path

import pytest

pytest.importorskip("rdflib")

from skillc.cli import main  # noqa: E402
from skillc.env.twin import TwinError, load_twin, verify_all, verify_target  # noqa: E402

DEMO = Path(__file__).resolve().parents[1] / "examples" / "building-twin" / "demo-building.trig"

PREFIXES = """@prefix brick: <https://brickschema.org/schema/Brick#> .
@prefix ex: <urn:bdt:t:> .
"""


@pytest.fixture(scope="module")
def twin():
    return load_twin(DEMO)


def verdicts(results):
    return {r.target: (r.verdict, [e.key for e in r.missing]) for r in results}


def test_setpoints_in_the_demo_building(twin):
    assert verdicts(verify_all(twin, "setpoint")) == {
        "ex:sp1": ("ACHIEVABLE", []),
        "ex:sp2": ("IMPOSSIBLE", ["min_max_units"]),
        "ex:sp3": ("IMPOSSIBLE", ["external_reference"]),
        "ex:sp4": ("IMPOSSIBLE", ["equipment", "controlled_places", "min_max_units",
                                  "priority_state", "external_reference"]),
    }


def test_scope_is_derived_through_inverse_and_extra_hops(twin):
    r = verify_target(twin, "setpoint", "sp3")
    places = next(e for e in r.evidence if e.key == "controlled_places")
    assert places.found == ["ex:ahu3 ->feeds ex:vav3 ->feeds ex:zone3"]
    r = verify_target(twin, "setpoint", "sp1")
    eq = next(e for e in r.evidence if e.key == "equipment")
    assert eq.found == ["ex:sp1 <-hasPoint ex:vav1"]


def test_schedule_needs_a_policy_and_a_declared_source_is_an_assumption(twin):
    assert verdicts(verify_all(twin, "schedule"))["ex:zone1"] == ("IMPOSSIBLE", ["operating_policy"])
    r = verify_target(twin, "schedule", "zone1", {"operating_policy": "policy service"})
    assert r.verdict == "ACHIEVABLE" and [e.key for e in r.assumed] == ["operating_policy"]
    with pytest.raises(TwinError):
        verify_target(twin, "schedule", "zone1", {"no_such_need": "x"})


def test_set_point_named_after_a_zone_is_not_a_place(twin):
    from skillc.env.twin import candidates
    assert [twin.label(c) for c in candidates(twin, "schedule")] == ["ex:zone1", "ex:zone3"]


def test_vendor_class_needs_the_ontology_and_ontology_is_never_evidence(tmp_path):
    g = tmp_path / "b.trig"
    g.write_text(PREFIXES + """@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
<bdt:ontology:v> { ex:MySP rdfs:subClassOf brick:Setpoint . ex:sp brick:isPointOf ex:vav . }
<bdt:tenant:a> { ex:sp a ex:MySP . ex:vav a brick:VAV . }
""", encoding="utf-8")
    r = verify_target(load_twin(g), "setpoint", "sp")
    status = {e.key: e.status for e in r.evidence}
    assert status["setpoint_identity"] == "found"      # class hierarchy from the ontology
    assert status["equipment"] == "missing"            # the relationship sits only in the ontology


def test_several_tenants_must_be_chosen(tmp_path):
    g = tmp_path / "b.trig"
    g.write_text(PREFIXES + """<bdt:tenant:a> { ex:sp a brick:Setpoint . }
<bdt:tenant:b> { ex:sp a brick:Setpoint ; brick:isPointOf ex:vav . ex:vav a brick:VAV . }
""", encoding="utf-8")
    with pytest.raises(TwinError, match="--tenant"):
        load_twin(g)
    a = verify_target(load_twin(g, tenant="a"), "setpoint", "sp")
    b = verify_target(load_twin(g, tenant="b"), "setpoint", "sp")
    assert "equipment" in [e.key for e in a.missing]
    assert "equipment" not in [e.key for e in b.missing]


def test_blank_node_structures_are_read_through_their_anchor(tmp_path):
    g = tmp_path / "b.ttl"
    g.write_text(PREFIXES + """ex:sp a brick:Setpoint ;
  ex:priorityArray [ ex:activePriority 8 ] ;
  ex:hasExternalReference [ ex:objectIdentifier "analog-value,1" ] .
""", encoding="utf-8")
    r = verify_target(load_twin(g), "setpoint", "sp")
    ev = {e.key: e for e in r.evidence}
    assert ev["priority_state"].found == ["ex:sp priorityArray (activePriority)"]
    assert ev["external_reference"].status == "found"


def test_json_ld_is_refused(tmp_path):
    g = tmp_path / "b.jsonld"
    g.write_text("{}", encoding="utf-8")
    with pytest.raises(TwinError, match="JSON-LD"):
        load_twin(g)


def test_cli_exit_codes_and_json(capsys):
    assert main(["twin", "check", str(DEMO), "--scenario", "setpoint", "--target", "sp1"]) == 0
    assert main(["twin", "check", str(DEMO), "--scenario", "setpoint", "--brief"]) == 1
    assert main(["twin", "check", str(DEMO), "--scenario", "schedule", "--target", "zone1",
                 "--source", "operating_policy=policy service"]) == 3
    capsys.readouterr()
    assert main(["twin", "check", str(DEMO), "--scenario", "setpoint", "--target", "sp2",
                 "--json"]) == 1
    doc = json.loads(capsys.readouterr().out)
    assert doc["schema"] == "skillc.twin/1"
    assert doc["results"][0]["missing"] == ["min_max_units"]
    assert main(["twin", "check", str(DEMO), "--scenario", "setpoint", "--target", "nope"]) == 2

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


# ---------------------------------------------------------------- explore and workflows

from skillc.env.twin_workflow import explore, map_need, read_workflows, verify_workflow  # noqa: E402

FLAT_BRIEF = """Scenario 1: Set-Point Verifier
Illustrative request: "Change this set point to 22 degrees."
Evidence needed
Why it matters
Set-point identity and type
Verify that the requested entity is the intended control point
Controlled place(s) and associated equipment
Derive the affected scope from the graph
BACnet priority state and external reference
Assess priority masking and whether a commandable
object is bounded
Relevant historical series, when required by the evaluation
Add time series context
The verifier returns a verdict, findings, and supporting evidence and never treats missing evidence as approval.
Scenario 2: Schedule-Update Verifier
Evidence needed
Why it matters
Target scope, affected spaces, and equipment
Determine which systems the change affects
Authoritative operating policies and constraints
Check permitted hours and approval requirements
Current operational state, where required
Identify applicable overrides or interlocks
Shared architectural problems
Both verifiers need reliable graph evidence but their evidence contracts differ in several important ways today.
"""


def test_a_pasted_two_column_brief_is_read_line_by_line():
    sp, sch = read_workflows(FLAT_BRIEF)
    assert (sp.title, sp.kind) == ("Set-Point Verifier", "setpoint")
    assert [(n.text, n.keys, n.critical) for n in sp.needs] == [
        ("Set-point identity and type", ["setpoint_identity"], True),
        ("Controlled place(s) and associated equipment", ["equipment", "controlled_places"], True),
        ("BACnet priority state and external reference",
         ["priority_state", "external_reference"], True),
        ("Relevant historical series", ["history"], False),
    ]
    assert sch.kind == "schedule"
    assert [n.keys for n in sch.needs] == [["target_scope"], ["operating_policy"],
                                           ["operational_state"]]
    assert sch.needs[-1].critical is False        # "where required"; the heading is not a need


def test_bullets_and_markdown_tables():
    (wf,) = read_workflows("# Check\nEvidence needed:\n- Configured minimum/maximum and units\n"
                           "- Occupancy sensor, if available\n")
    assert [n.keys for n in wf.needs] == [["min_max_units"], []]
    assert wf.needs[1].words == ["occupancy", "sensor"] and not wf.needs[1].critical
    (wf,) = read_workflows("Evidence needed\n| Evidence | Why |\n|---|---|\n"
                           "| Current schedule | delta |\n| Timezone | DST |\n")
    assert [n.keys for n in wf.needs] == [["current_schedule"], ["timezone"]]
    assert wf.kind == "schedule"


def test_no_needs_is_an_error():
    with pytest.raises(TwinError, match="Evidence needed"):
        read_workflows("just some prose about buildings")


def test_a_custom_need_is_searched_by_name(twin):
    (wf,) = read_workflows("Evidence needed:\n- Set-point identity and type\n- Occupancy sensor\n")
    ok = verify_workflow(twin, wf, "sp1")
    assert ok.verdict == "ACHIEVABLE"
    occ = next(e for e in ok.evidence if e.key == "occupancy_sensor")
    assert occ.found[0].startswith("name match 'occupancy'")
    bad = verify_workflow(twin, wf, "sp2")
    assert [e.key for e in bad.missing] == ["occupancy_sensor"]


def test_map_need_keeps_scope_lines_whole():
    assert map_need("Target scope, affected spaces, and equipment").keys == ["target_scope"]


def test_explore_describes_the_graph(twin):
    text = explore(twin)
    assert "VAV --feeds--> HVAC_Zone  x2" in text
    assert "VendorTempSP --priorityArray--> {activePriority, relinquishDefault}" in text
    assert "Set-point verifier: 1 of 4 targets" in text


def test_cli_workflow_and_explore(capsys):
    wf = DEMO.parent / "workflow.md"
    assert main(["twin", "explore", str(DEMO)]) == 0
    assert main(["twin", "check", str(DEMO), "--workflow", str(wf), "--target", "sp1"]) == 0
    capsys.readouterr()
    assert main(["twin", "check", str(DEMO), "--workflow", str(wf), "--json"]) == 1
    doc = json.loads(capsys.readouterr().out)
    assert doc["workflows"][0]["title"] == "Comfort complaint check"
    assert main(["twin", "check", str(DEMO)]) == 2          # neither --workflow nor --scenario

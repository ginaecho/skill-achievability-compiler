"""Write campus-building.trig: a larger, made-up building graph for the skillc twin demo.

Three floors; each floor has one AHU feeding three VAVs, each VAV feeds a zone of two rooms and
has a zone set point. The evidence varies on purpose so the demo shows every outcome:

* VAV 1 of each floor: full evidence (limits and unit, priority array, BACnet and time-series
  references, an occupancy sensor);
* VAV 2: no limits;
* VAV 3: no BACnet reference.

Floor 1's zones have a schedule and an operating policy; floor 2's have a schedule but no
policy; floor 3's have neither. One orphan set point has nothing at all. The building has a
timezone. Nothing here is real tenant data.

Run: python examples/building-twin/make_campus.py
"""
from pathlib import Path

HEAD = """# A larger, made-up building graph for the skillc twin demo, written by make_campus.py.
# No real tenant data.
@prefix brick: <https://brickschema.org/schema/Brick#> .
@prefix rec:   <https://w3id.org/rec#> .
@prefix ref:   <https://brickschema.org/schema/Brick/ref#> .
@prefix bacnet: <http://data.ashrae.org/bacnet/2020#> .
@prefix unit:  <http://qudt.org/vocab/unit/> .
@prefix rdfs:  <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex:    <urn:bdt:campus:> .

# The ontology graph: vocabulary only. It never counts as building evidence.
<bdt:ontology:vendor> {
  ex:VendorTempSP rdfs:subClassOf brick:Zone_Air_Temperature_Setpoint .
  ex:WeeklySchedule rdfs:subClassOf ex:Schedule .
  ex:OperatingPolicy rdfs:subClassOf ex:Policy .
}

# The tenant instance graph.
<bdt:tenant:campus> {
  ex:hq a brick:Building ; brick:timezone "Europe/Berlin" .
"""


def floor(f: int) -> list[str]:
    out = [f"  ex:floor{f} a brick:Floor ; brick:isPartOf ex:hq .",
           f"  ex:ahu{f} a brick:AHU ; brick:isPartOf ex:floor{f} ; "
           f"brick:feeds {', '.join(f'ex:vav{f}{v}' for v in (1, 2, 3))} ."]
    for v in (1, 2, 3):
        vav, zone, sp = f"ex:vav{f}{v}", f"ex:zone{f}{v}", f"ex:sp{f}{v}"
        rooms = [f"ex:room{f}{v}{r}" for r in (1, 2)]
        out += [f"  {zone} a brick:HVAC_Zone ; brick:isPartOf ex:floor{f} ; "
                f"brick:hasPart {', '.join(rooms)} ."]
        out += [f"  {r} a brick:Room ." for r in rooms]
        points = [sp] + ([f"ex:occ{f}{v}"] if v == 1 else [])
        out.append(f"  {vav} a brick:VAV ; brick:feeds {zone} ; "
                   f"brick:hasPoint {', '.join(points)} .")
        if v == 1:
            out.append(f"  ex:occ{f}{v} a brick:Occupancy_Status .")
        props = [f"a {'ex:VendorTempSP' if v == 1 else 'brick:Zone_Air_Temperature_Setpoint'}",
                 "brick:hasUnit unit:DEG_C",
                 f"ex:priorityArray [ ex:activePriority {8 + v} ; ex:relinquishDefault 21.0 ]"]
        if v != 2:
            props.append("brick:minPresentValue 16.0 ; brick:maxPresentValue 26.0")
        refs = []
        if v != 3:
            refs.append("[ a ref:BACnetReference ; "
                        f'bacnet:object-identifier "analog-value,{f}{v}" ]')
        refs.append(f'[ a ref:TimeseriesReference ; ref:hasTimeseriesId "ts-sp{f}{v}" ]')
        props.append("ref:hasExternalReference " + " , ".join(refs))
        out.append(f"  {sp} " + " ;\n      ".join(props) + " .")
        if f in (1, 2):
            out.append(f"  ex:sched{f}{v} a ex:WeeklySchedule ; ex:appliesTo {vav} ;\n"
                       '      ex:weeklySchedule [ ex:monday "07:00-19:00" ; '
                       'ex:saturday "08:00-13:00" ] ;\n'
                       f'      ex:exceptionSchedule [ ex:date "2026-12-25" ] .')
        if f == 1:
            out.append(f"  {zone} ex:operatingPolicy ex:policy_office_hours .")
    return out


def main() -> None:
    body = [HEAD.rstrip("\n")]
    body.append('  ex:policy_office_hours a ex:OperatingPolicy ; '
                'ex:permittedHours "06:00-20:00" ; ex:minSetpoint 18.0 ; ex:maxSetpoint 24.0 .')
    for f in (1, 2, 3):
        body.append(f"\n  # Floor {f}")
        body += floor(f)
    body.append("\n  # An orphan set point: no equipment, place, limits or references.")
    body.append("  ex:sp_orphan a brick:Room_Air_Temperature_Setpoint .")
    body.append("}")
    out = Path(__file__).with_name("campus-building.trig")
    out.write_text("\n".join(body) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

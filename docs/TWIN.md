# Building digital twin: what can a verifier establish? (`skillc twin`)

A DEIM verifier, such as a set-point verifier or a schedule-update verifier, needs
evidence from the building graph before it can judge an operational change.
`skillc twin` reads an uploaded building graph and decides, for each target, whether
that evidence is there. It reports ACHIEVABLE, or IMPOSSIBLE with the missing evidence
and the reason.

```console
$ pip install -e ".[twin]"           # rdflib, to read RDF files
$ skillc twin scenarios               # the scenarios and their evidence needs
$ skillc twin check building.trig --scenario setpoint --tenant demo
$ skillc twin check building.trig --scenario setpoint --target sp2
$ skillc twin check building.trig --scenario schedule --target zone1 \
      --source operating_policy=policy-service
$ skillc twin check building.trig --scenario setpoint --brief   # one line per target
$ skillc twin check building.trig --scenario setpoint --json    # skillc.twin/1
```

Exit codes: `0` every target is achievable from the graph; `3` achievable, but only
with evidence declared by `--source`; `1` at least one target is impossible; `2` error.

## Explore a graph, then paste a workflow

You need no description of the graph:

```console
$ skillc twin explore building.trig                       # what it holds and can answer
$ skillc twin check building.trig --workflow workflow.md  # your workflow, pasted as written
```

`explore` lists:
* the kinds of entity in the graph;
* how those kinds connect (for example `VAV --feeds--> HVAC_Zone`);
* the nested structures, such as priority arrays and references;
* the properties that carry values;
* how many targets each built-in verifier can already handle.

`--workflow` reads the evidence needs from any of these:
* a brief with "Evidence needed" / "Why it matters" tables, even when pasting has flattened the
  table into alternating lines;
* bullets under an "Evidence needed:" line;
* a Markdown table.

A heading such as "Scenario 2: Schedule-Update Verifier" starts a new workflow. Each line is mapped
to a recognised need, or, if none fits, searched for by name around the target. The mapping is
printed before the results. A line containing "when required", "where required", "optional" or "if
available" is not critical. Reading the workflow is deterministic, so the same text always gives
the same needs.

## Adding a recognised need (for developers)

1. Add the need to a scenario in `SCENARIOS`. Then teach the scenario's probe in `PROBES` how to
   find it, in `src/skillc/env/twin.py`. The probe follows relations by local name, in both
   directions, with a bounded number of hops. It reads blank-node structures through their anchor.
   It returns the graph path that proves the need, or what it looked for.
2. Add a pattern to `NEED_PATTERNS` in `src/skillc/env/twin_workflow.py`, so that workflow lines
   map to the new need.
3. Cover the new need in the sample graph, `examples/building-twin/demo-building.trig`, and add a
   test.

## How it decides

1. **Read the graph offline.** The tool reads Turtle, TriG, N-Triples, N-Quads or
   RDF/XML. JSON-LD is refused because it can fetch remote contexts. Nothing is sent
   anywhere and no model is called.
2. **Tenant scope.** In a TriG or N-Quads file, evidence comes only from the tenant graph
   (`--tenant`). Named graphs whose name contains "ontology", and files passed with
   `--ontology`, are used only to resolve class hierarchies. A vocabulary that can express
   a relationship does not prove that the relationship exists in this building.
3. **Vocabulary variation.** Classes and predicates are matched by local name, so Brick,
   RealEstateCore, BOT and vendor extensions are all read. Every relationship is followed
   in both directions: `hasPoint`/`isPointOf`, `feeds`/`isFedBy`,
   `hasPart`/`isPartOf`/`locatedIn`. Scope is followed through extra equipment hops, for
   example from an AHU to a VAV to a zone and then to its rooms.
4. **Blank nodes.** Priority arrays and external references are often blank nodes. Their
   fields are read through the relationship that anchors them, never as reusable entities.
5. **Evidence per need.** Each need is reported as found (with the graph path that proves
   it), declared (`--source`, an assumption the caller vouches for) or missing (with what
   was looked for).
6. **Verdict.** The verifier becomes a pack: one read step for each available need, and a
   `verify` step that requires every critical need. The trusted checker decides it. A
   missing critical need gives `IMPOSSIBLE [BLOCKED_GUARD]`, so missing evidence is never
   read as approval. Needs marked "when required" (history, operational state, calendar
   rules) are reported but do not block.

| scenario | critical evidence | reported when present |
|---|---|---|
| `setpoint` | set-point identity and type, equipment, controlled places, min/max and units, BACnet priority state, BACnet external reference | time-series reference |
| `schedule` | target scope (spaces and equipment), BACnet priority state, external reference, current schedule, timezone, operating policy | recurrence and exceptions, operational state, time-series reference |

## Limits

* The result depends on the graph that was read. A time-series reference shows that a
  series exists in BSTS, but the series itself is not read. Live point values, overrides
  and the full BACnet priority array are not read either.
* Matching by local name is a heuristic. A vendor predicate with an unusual name is
  reported as missing until it is added to the word lists in `skillc/env/twin.py`.
* The tool checks that evidence exists, not that it is correct. It does not decide
  whether 22 °C lies inside the limits, or whether the policy permits the change. Those
  checks belong to the verifier, which runs once this check says the evidence is there.

The illustrative graph `examples/building-twin/demo-building.trig` has four set points
and two zones. Each shows one pattern from the BDT brief:

* inverse relationships;
* an extra equipment hop;
* a vendor class that is defined only in the ontology graph;
* limit points kept separately from the set point;
* evidence that is missing.

# Skill Achievability

This context asks whether a declared agent skill admits a goal-reaching run
before execution. Its guarantee is asymmetric: refutations are sound relative
to the declaration, while positive verdicts remain deliberately incomplete.

## Language

**Declared pack**:
The formal declaration of capabilities, guarded effects, protocol, initial
state, goal, and optional role behaviours that the checker judges.
_Avoid_: Skill, real execution

**Concrete run**:
An execution in the actual agent runtime with real tool behavior and payloads.
It is not an artifact produced or observed by the checker.
_Avoid_: Witness path, abstract run

**Abstract run**:
A path through the declared pack's over-approximating transition system.
_Avoid_: Concrete run

**Structural admissibility**:
The meaning of `ACHIEVABLE`: the declared pack admits an abstract run that
reaches the goal. It does not guarantee that a concrete run will succeed.
_Avoid_: Verified success, guaranteed achievement

**Refutation**:
An `IMPOSSIBLE` verdict proving, relative to the declared pack and abstraction
assumptions, that no concrete run reaches the goal.
_Avoid_: Failure, negative result

**Abstention**:
An `UNKNOWN` verdict made outside the decidable fragment. It is not a
refutation and makes no achievability claim.
_Avoid_: Impossible

**Realizability**:
The condition that each role can determine the protocol behavior it must
follow, including which branch was selected when its behavior depends on it.
_Avoid_: Reachability, conformance

**Declarative conformance**:
The whole-session judgment relating declared role behaviors, a global protocol,
and a world without first constructing local types.
_Avoid_: Projection adapter

**Conformance adapter**:
The executable projection-based approximation of declarative conformance:
senders match protocol choices exactly while receivers may accept additional
labels.
_Avoid_: Declarative conformance, full session subtyping

**Verified specification**:
A proved theorem schema that constrains the checker when its simulation
hypotheses are discharged. It is not a mechanization of the Python program.
_Avoid_: Verified checker

**Intent fidelity**:
Whether the formal goal captures what the human intended. It is a human-review
obligation at the top edge of the trust boundary.
_Avoid_: Goal satisfiability

**Payload faithfulness**:
Whether a capability's declared effects match the tool's concrete behavior. It
is a runtime-monitoring obligation at the bottom edge of the trust boundary.
_Avoid_: Capability availability

**Static topology**:
A fixed, finite set of roles known before execution, defining the decidable
fragment.
_Avoid_: Non-agentic

**Dynamic spawning**:
Creation of an unbounded number of participants during execution. It moves the
problem outside the decidable fragment and yields an abstention unless an
independent structural refutation already applies.
_Avoid_: Autonomy

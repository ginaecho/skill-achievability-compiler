# skill-achievability-compiler

**`skillc`** — a static compiler that decides whether the *goal* of an agent
skill (a `SKILL.md`, agent markdown, or a formal achievability pack) is
achievable in a given capability context.  It is **sound for refutation**:
an `IMPOSSIBLE` verdict is a proof (relative to the declared capabilities and
frame assumption) that no run of the declared pack can reach its goal.  It is
deliberately **incomplete for achievement**: `ACHIEVABLE` means "structurally
admissible", not "guaranteed".

The checker uses z3 with **no LLM in the trusted decision path**. It can gate
execution before an agent spends tokens on an invalid protocol or unreachable
goal.

```
 natural-language skill ──► [ front-end compaction ] ──► pack ──► [ checker ] ──► verdict
      (SKILL.md)              UNTRUSTED                           TRUSTED
                              deterministic or LLM                sound for refutation
```

## Quick start

```bash
pip install -e ".[dev]"        # installs the `skillc` CLI
```

Check a real skill against the runtime that will execute it:

```console
$ skillc check call-to-book/SKILL.md --profile claude-ai
call-to-book: ACHIEVABLE

$ skillc check call-to-book/SKILL.md --profile claude-code
call-to-book: IMPOSSIBLE [MISSING_CAPABILITY]
  protocol invokes undeclared capabilities: ['ask_user_input_v0']
  missing: ask_user_input_v0 (line 7)
```

The same skill, two verdicts: achievability is **relative to the declared
environment**. Profiles and self-declared `allowed-tools`/`tools` metadata are
distinct trust inputs; the frontend combines them but does not discover or
verify actual runtime grants.

Batch-scan a skill tree, compile a pack, or run the evaluation corpus:

```console
$ skillc scan /mnt/skills --profile claude-ai      # 36/36 achievable
$ skillc compile SKILL.md -o pack.json             # inspect the formal object
$ skillc check pack.json --json                    # machine-readable verdict
$ skillc eval                                      # corpus + soundness audit
$ skillc cost --corpus                             # token economics of checking
$ skillc profiles                                  # claude-ai, claude-code, none
```

Exit codes: `0` achievable, `1` impossible, `2` error, `3` unknown (an
abstention, including outside the decidable fragment) — so `skillc check` can
gate CI for skill repositories.

### Protocol checks versus goal-only checks

The default check judges the **declared protocol**, not every alternative plan.
Use a reviewed environment contract and `--goal-only` when rejection must mean
the goal is unreachable across the available capabilities:

```powershell
skillc check SKILL.md --contract task-contract.json --goal-only --json
```

A contract declares `goal` and `capabilities`, with optional roles and initial
conditions. A contract-only impossibility preflight can skip LLM compaction.
Without a protocol-independent refutation, protocol errors become `UNKNOWN`,
not a rejection of all alternative plans. `UNKNOWN` is neither rejection nor
permission to execute; this policy cannot be combined with `--adversarial`.

For a trusted single-role Boolean contract,
`skillc plan task-contract.json -o generated-pack.json` constructs a checked
alternative protocol without an LLM. It does not certify the source's original
protocol; unsupported inputs and search limits produce abstentions.

Details: [compaction and goal-only policy](docs/COMPACTION_PRECISION_ASSESSMENT_20260921.md).

## What the checker decides

A **pack** declares capabilities (STRIPS pre/effects, numeric assignments,
constrained non-determinism), a goal-marked global protocol (`act` / `msg` /
`choice` / tail-recursive `rec`/`continue` loops / `spawn`), a goal formula,
the initial state, and optionally per-role declared behaviours (`skills`).
The executable checker decides four algorithmic checks for direct conformance
and achievability:

```
   Γ ⊇ caps(G)          capability soundness   — no hallucinated tools
   G ⇓ {T_p}            realizability          — projection defined for every role
   ∀p. S_p ⊑ G↾p        direct conformance     — exact sender labels;
                                                  receivers may offer more
   Γ; G ⊨ ◇goal         liveness               — goal may-reachable (z3)
   ─────────────────────
   Γ ⊢ {S_p} : G ▷ ◇goal
```

Refutations name the failing check:

| reason | failure mode it catches |
|---|---|
| `MISSING_CAPABILITY` | hallucinated planning — the protocol invokes a tool that is not granted |
| `GOAL_UNSAT` | no establisher for a goal conjunct, or a numeric refinement (e.g. *under $500*) unsatisfiable on every run |
| `BLOCKED_GUARD` | a mandatory action's precondition can never be satisfied (the retry-forever cause) |
| `NON_PROJECTABLE` | a role must act inside a branch it is never told about and the branches do not merge (unobserved choice → deadlock/handoff freeze) |
| `NON_CONFORMANT` | a declared role behaviour does not refine its projected contract — the verdict on `G` cannot be transported to it |

## More than tool checking: stop impossible agent coordination

`skillc` does not only check whether tools exist. It also checks whether the
goal is reachable, action guards and numeric constraints can be satisfied, and
the interactions among agents form a realizable protocol.

For example, suppose a main agent privately chooses either a security review
or a performance review. A reviewer performs the selected analysis, while an
editor must publish the corresponding report. Every required capability may
exist, but if the editor is never told which branch the main agent selected,
the editor cannot know which publication action its local contract requires.
`skillc` refutes this before any agents are launched:

```text
private-review-routing: IMPOSSIBLE [NON_PROJECTABLE]
  role 'editor' must behave differently across an unobserved choice
```

The repair is a protocol change, not another tool: the main agent must send the
editor a branch label such as `publish_security_report` or
`publish_performance_report`.

Compaction has three paths; none puts an LLM in the trusted decision:

| Input path | Use |
|---|---|
| Deterministic frontend | Supported markdown/prose patterns; zero LLM tokens |
| `skillc compile --llm` | Unrestricted prose via Anthropic or Azure OpenAI |
| Embedded `skillc-pack` | Author-reviewed formal capabilities and protocol |

The corpus contains two protocol-specific refutations:

| case | protocol defect | verdict |
|---|---|---|
| `deadlock_unobserved` | a planner must react to a worker's private choice | `NON_PROJECTABLE` |
| `nonconformant_handler` | a handler omits one route required by its contract | `NON_CONFORMANT` |

For `deadlock_unobserved`, the published token model estimates **1,888 tokens**
for one-time LLM compaction versus **231,870 tokens** for a typical two-agent
deadlock run (54,948–778,740 low–high). Deterministic compaction costs zero
tokens. These are modeled economics: the repository does not yet claim a valid
measured multi-agent with/without benchmark for protocol failures. See
[Impossible agent coordination example](docs/IMPOSSIBLE_AGENT_COORDINATION.md)
for the complete skill, repair, benchmark cases, and evidence boundary.

## Results on real, public skills

Validated against Anthropic's public skills corpus
([anthropics/skills](https://github.com/anthropics/skills), 36 `SKILL.md`
files mounted at `/mnt/skills`, or fetched with
`python3 scripts/fetch_skills.py`):

* **36/36 achievable under the `claude-ai` profile** — their home runtime.
  Zero false refutations on deployed skills.
* **16/36 refuted under the `claude-code` profile**, each with the exact
  missing tool named (`ask_user_input_v0`, `read_page`, `upload_file`,
  `create_file`, `str_replace`, `show_widget`, `search_mcp_registry`, …) and
  the source line.  Granting the named tools flips every one of them back to
  achievable.

These are snapshot results, not a guarantee of concrete success.
Full table: [real-skills report](docs/REAL_SKILLS_REPORT.md).

**Semantic level** ([`docs/SEMANTIC_VALIDATION.md`](docs/SEMANTIC_VALIDATION.md),
`scripts/semantic_validation.py`): four representative consumer skills were
LLM-compacted into semantic packs (goals like *booked ∧ calendar-updated ∧
user-informed* with per-step guards), through the schema gate and at most one
repair round — **4/4 check ACHIEVABLE** (no false alarms on deployed skills).
Seeded faults removed capabilities or goal establishers: **6/6 mutants
refuted**, naming the missing tool or unreachable goal conjunct.

On the 15-spec ground-truth corpus (`skillc eval`): **FN = 0** (no achievable
goal ever refuted) and the only false `ACHIEVABLE`s are the two planted
`SPURIOUS` cases (payload faithfulness / intent fidelity), i.e. exactly the
residues the compiler openly defers to runtime monitoring and human review.
No structural failure was missed in this proof-of-concept corpus.

**Watch the pipeline:** the [107-second demo](demo/real-skill-cases/skillc-real-skills-demo.mp4)
compiles five real skills through Azure OpenAI, the schema gate, and the
checker. [Sources, artifacts, and reproduction](demo/real-skill-cases/README.md).

## What checking costs (`skillc cost`)

The trusted core spends **zero tokens**: no model sits in the decision path,
so a check costs exactly what its front-end costs — and the deterministic
front-end's is zero too. The only stage that spends tokens is the optional LLM
compaction, and it is one-shot, per skill *version*.

The model assumes each agent turn re-sends its growing conversation:
`T·(S+K) + g·T(T−1)/2` input tokens. Compaction is paid once per unchanged
skill version; unchecked execution costs recur on every invocation.

```console
$ skillc cost --corpus --price-llm
```

Modeled estimates for a median real skill (leverage = wasted per prevented run
÷ tokens spent checking; turns shown as low–typical–high):

| reason | turns before it stops the agent | leverage |
|---|---|---|
| `MISSING_CAPABILITY` | 3–8–14, one agent | 18× |
| `GOAL_UNSAT` | 8–18–30, and the run may *believe it succeeded* | 63× |
| `NON_PROJECTABLE` / `NON_CONFORMANT` | 6–15–30, **two** agents billed | 94× |
| `BLOCKED_GUARD` | 12–25–50 — retry-forever runs to the turn cap | 110× |

`UNKNOWN` deliberately claims no savings: an abstention prevents nothing.

Runtime waste is a **model**, not a measurement — it prices a run that, if the
refutation is right, never happens. It is reported as a band, every parameter
is overridable, and the caveat prints on every invocation. Compaction usage is
**measured** when a live call reports it. Full method, defaults and their
rationale: [`docs/TOKEN_ECONOMICS.md`](docs/TOKEN_ECONOMICS.md) and
[`src/skillc/tokens.py`](src/skillc/tokens.py).

## Honest limitations

**Declarations, not reality.** Static validation judges the declared pack.
Either frontend can misrepresent the source; human review must establish intent
fidelity, and runtime verification must establish actual tool effects.
`ACHIEVABLE` is an abstract witness, not a guarantee of concrete success.
Protocol rejection does not rule out a repaired or alternative plan.

**Coordination assumptions.** Roles without declared local behaviors are
reported as assumed conformant. Projection implements a restricted merge;
loop widening conservatively forgets numeric state. Dynamic spawning normally
yields `UNKNOWN` unless an independent refutation already applies.

**Proof boundary.** The [refutation-sound abstraction theorem](proof/SkillAchievability.v)
is mechanized in Coq with zero axioms, but the exact Python transition system
is not instantiated in Coq. The conformance adapter's equivalence to the
declarative whole-session judgment remains an open proof obligation.

## Development and resources

Run `python -m pytest` for the test suite. `skillc audit .\my-skill` provides a
deterministic pre-pass for manifest inconsistencies, suspicious metadata,
risky code patterns, and permission mismatches; it is not a security guarantee.

[Source](src/skillc/) · [Examples](examples/) ·
[Compaction prompt](docs/COMPACTION_PROMPT.md) ·
[Citation](CITATION.cff) · [MIT License](LICENSE)

# skill-achievability-compiler

**`skillc`** checks, **before an agent spends a single token**, whether the goal
of an agent skill (a `SKILL.md`, an agent markdown file, a prompt, or a formal
achievability pack) can be reached with the tools and permissions the agent
actually has, and then keeps checking while the agent acts.

* **Static validation (before the run).** A z3-based checker with **no LLM in
  the trusted decision path** decides achievability. It is **sound for
  refutation**: `IMPOSSIBLE` is a proof, relative to the declared capabilities
  and frame assumption, that no run of the declared pack reaches its goal. It is
  deliberately **incomplete for achievement**: `ACHIEVABLE` means "structurally
  admissible", not "guaranteed".
* **Runtime verification (during the run).** A monitor holds the agent to its
  approved plan, refuses actions whose preconditions or permissions are missing,
  and can require a user's single-use approval for sensitive operations.

```
 natural-language skill ──► [ front-end compaction ] ──► pack ──► [ checker ] ──► verdict
      (SKILL.md)              UNTRUSTED                           TRUSTED
                              deterministic or LLM                sound for refutation
                                                                      │
                     agent runtime ◄── [ runtime monitor: plan, actions, approvals ]
```

## Where skillc runs today

| Where | What skillc does there | Activate | Read |
|---|---|---|---|
| **CLI and CI** | Static validation of skills, agents, prompts and packs | `skillc check SKILL.md --profile claude-code` | [Quick start](#quick-start) |
| **Claude Code** | Runtime monitor through Claude Code hooks | `skillc monitor init --runtime developer-sandbox` | [Runtime monitor](https://github.com/ginaecho/skill-achievability-compiler/blob/main/docs/RUNTIME_MONITOR.md) |
| **GitHub Copilot** (CLI and cloud agent) | Runtime monitor through Copilot hooks | `skillc monitor init --copilot --runtime developer-sandbox` | [Copilot hooks](https://github.com/ginaecho/skill-achievability-compiler/blob/main/docs/RUNTIME_MONITOR.md#github-copilot-hooks-copilot-cli-and-the-copilot-cloud-agent) |
| **Microsoft Agent 365** (agents built with Microsoft Agent Framework, incl. Foundry hosted agents) | **Enforced** runtime gate as Agent Framework middleware; evidence-bound approvals; ten source-backed cases | `pip install -e ".[agent-framework]"`, then `skillc_monitor(..., strict=True, fail_open=False)` | [Agent 365 security](https://github.com/ginaecho/skill-achievability-compiler/blob/main/docs/AGENT365_SECURITY.md) · [cases](https://github.com/ginaecho/skill-achievability-compiler/blob/main/examples/agent365-cases/README.md) |
| **Microsoft Scout** | Same checks and approvals as MCP tools the agent calls (**cooperative**, not enforced) | `skillc monitor scout-install`, then restart Scout | [Scout parity](https://github.com/ginaecho/skill-achievability-compiler/blob/main/docs/SCOUT_PARITY.md) |
| **Browser demo** | Watch a skill move through the real compiler | `python demo/skillc-architecture-app/app.py` | [Execution Atlas](https://github.com/ginaecho/skill-achievability-compiler/blob/main/demo/skillc-architecture-app/README.md) |

The decisions are the same everywhere; the guarantee depends on **where skillc
sits**. In Agent 365 (Agent Framework) skillc is inside the tool-call path, so a
denied tool cannot run. In Scout skillc is a tool beside the agent, so a
compliant agent follows the same verdicts, but nothing forces it to.

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

```console
$ skillc scan /mnt/skills --profile claude-ai      # every skill achievable (42/42)
$ skillc compile SKILL.md -o pack.json             # inspect the formal object
$ skillc check pack.json --json                    # machine-readable verdict
$ skillc eval                                      # corpus + soundness audit
$ skillc cost --corpus                             # token economics of checking
$ skillc profiles                                  # claude-ai, claude-code, none
```

Exit codes: `0` admissible (achievable, and the protocol is not rejected),
`1` impossible or protocol rejected, `2` error, `3` unknown (an abstention,
including outside the decidable fragment), so `skillc check` can gate CI for
skill repositories.

## skillc in Microsoft Agent 365

Agent 365 governs agents (identity, observability, policy); it does not run
their tool loop. skillc therefore attaches to the agent's own runtime, Microsoft
Agent Framework, as middleware, and adds what Agent 365 does not provide: a
proof before execution that the plan can succeed, and an enforced gate on each
action.

**What is implemented**

* **Strict, fail-closed runtime gate.** `strict=True, fail_open=False` with a
  host-owned plan: raw tool aliases, unknown owners and unknown preconditions are
  denied; restrictions pruned at plan time are re-checked on every call; re-reading
  a source invalidates approvals and artifacts derived from it.
* **Evidence-bound approvals** (`skillc.security.ApprovalGate`): approval is bound
  to the exact document version, content, operation, destinations and amount; it
  is single-use, expiring and revocable, and is consumed before the send runs.
* **Environment-authoritative facts.** An intent can no longer claim prior approval
  or completed work that the environment does not declare.
* **Ten source-backed cases** (KPMG, Genspark, Zendesk, Rox, Gloat, Kasisto,
  Egnyte, Celonis, Sophos, Adobe), each a folder with its published workflow,
  primary-source links, formal model, checks, results and limitations:
  **123/123** expectations met.

**Activate**

```bash
pip install -e ".[agent-framework]"
```

```python
from skillc.integrations.agent_framework import skillc_monitor

monitor = skillc_monitor(runtime="foundry-hosted", root=state_dir,
                         plan_path=reviewed_plan, strict=True, fail_open=False)
agent = Agent(client=client, tools=tools, middleware=monitor.middleware_for("Writer"))
```

**Reproduce the evidence (offline, no tenant, no model)**

```bash
python examples/agent365-cases/run_cases.py --write
python examples/agent365-finance/security_demo.py --state-dir runs/agent365-security-offline
python -m pytest tests/test_agent365_cases.py tests/test_security.py tests/test_finance_security.py -q
```

**See it:** `python demo/skillc-a365-demo/app.py` replays published incidents side by side, with and without skillc ([demo](demo/skillc-a365-demo/README.md)).

**Read:**
[Agent 365 security](https://github.com/ginaecho/skill-achievability-compiler/blob/main/docs/AGENT365_SECURITY.md) ·
[ten cases](https://github.com/ginaecho/skill-achievability-compiler/blob/main/examples/agent365-cases/README.md) ·
[case report](https://github.com/ginaecho/skill-achievability-compiler/blob/main/docs/AGENT365_CASE_REPORT.md) ·
[integration research](https://github.com/ginaecho/skill-achievability-compiler/blob/main/docs/archive/MICROSOFT_AGENT_365_INTEGRATION_RESEARCH.md) ·
[hosted agents](https://github.com/ginaecho/skill-achievability-compiler/blob/main/docs/HOSTED_AGENT.md) ·
[hosted-agent comparison](https://github.com/ginaecho/skill-achievability-compiler/blob/main/docs/HOSTED_AGENT_COMPARISON.md)

*Scope:* these are local models of published workflows and an offline security
demo, not a deployed tenant integration; they do not claim the named
organizations use skillc. Live Entra permissions, authenticated cross-agent
receipts and actual Microsoft 365 delivery need a host adapter.

## skillc in Microsoft Scout

Scout gives plugins no hook before a tool runs, so skillc is served as MCP tools
that the `skillc-check` skill tells the agent to call. Scout now has the same
capabilities as the Agent 365 adapter: plan checking, strict host-owned plans,
runtime restriction checks, and single-use approvals that **the user** grants
through MCP elicitation (the agent cannot approve itself).

**Activate** (with the Python that Scout should run, with skillc installed):

```bash
pip install -e ".[mcp]"
skillc monitor scout-install                                  # advisory (default)
skillc monitor scout-install --strict --host-plan plan.ce     # host-owned plan
skillc monitor scout-install --approval-policy policy.json    # protected operations
```

Then **restart Scout**. The installer updates only the `skillc` entry in
`~/.scout/m-mcp-servers.json` and the `skillc-check` skill, keeping
`.bak-skillc-<time>` backups. An approval policy names the protected runtime
tools and the allowed destinations:

```json
{"protected_tools": ["teams_message"], "destinations": ["teams:<chat-or-channel-id>"],
 "ttl_seconds": 900, "audit_above": "50000.00"}
```

**Why weaker than Agent 365:** checks are voluntary (no pre-tool hook), skillc
approves but does not perform the send, the approval prompt depends on Scout
rendering MCP elicitation, the agent shares the user's account and machine, and
there is no fail-closed mode. Same verdicts, cooperative checking rather than
enforcement.

**Read:**
[Scout parity and enforcement differences](https://github.com/ginaecho/skill-achievability-compiler/blob/main/docs/SCOUT_PARITY.md) ·
[runtime monitor](https://github.com/ginaecho/skill-achievability-compiler/blob/main/docs/RUNTIME_MONITOR.md)

## Runtime monitor in coding agents

The same monitor attaches to Claude Code and GitHub Copilot through their hooks:
the agent first writes its plan in Controlled English, only an `ACHIEVABLE` plan
unlocks implementation, and every action is checked before it runs.

```bash
skillc monitor init --runtime developer-sandbox             # Claude Code hooks
skillc monitor init --copilot --runtime developer-sandbox   # writes .github/hooks/skillc.json
```

See [`docs/RUNTIME_MONITOR.md`](https://github.com/ginaecho/skill-achievability-compiler/blob/main/docs/RUNTIME_MONITOR.md).
The monitor is active only in a project that runs `skillc monitor init`.

## Controlled English (CE)

A pack can also be written, reviewed or generated in SkillC Controlled English,
a small formal language that reads as English. Every sentence form denotes
exactly one pack construct, so parsing is deterministic and errors name the line
and column:

```text
Skill `book-flight`.
Tool `book_flight` (owner `agent`): requires `flight_selected`; adds `booked`.
Goal: `booked` and `confirmation_sent`.
Protocol:
  - `agent` uses `book_flight`.
  - `agent` uses `send_email`.
```

`skillc check skill.ce` checks a CE file, `skillc ce pack.json` renders any pack
as CE for review, and `skillc check SKILL.md --llm --via-ce` has the model write
CE instead of JSON. See
[`docs/CONTROLLED_ENGLISH.md`](https://github.com/ginaecho/skill-achievability-compiler/blob/main/docs/CONTROLLED_ENGLISH.md),
[`docs/P2G_RUNTIME_BINDING.md`](https://github.com/ginaecho/skill-achievability-compiler/blob/main/docs/P2G_RUNTIME_BINDING.md)
(runtime-bound compaction, tested on 200 blindly executed skills) and
[`docs/LIBRARY_TEST.md`](https://github.com/ginaecho/skill-achievability-compiler/blob/main/docs/LIBRARY_TEST.md).

All of this is **optional**: the default `skillc check` / `compile` path and the
original JSON LLM front-end (`--llm`) are unchanged. The experiment data behind
these documents (`runs/`, `benchmark/` corpora) lives on the branch
`gc/data_train_test`; the scripts under `scripts/` that reproduce the
experiments expect that branch.

## What can I achieve in *my* environment? (`skillc reach`)

`skillc env probe` reads, read-only, the environment you work in: Azure role
assignments and scopes, deny assignments, policies, registered services,
resources, and configured MCP servers and tools. It saves this as a
provider-neutral graph (`skillc.env/1`). `skillc reach` then answers, for an
intent such as *"model a building's topology in Azure Digital Twins"*, which goal
conditions you can achieve, a checked plan for them, and which are blocked, why,
and the exact fix.

```console
$ skillc reach building-topology --env examples/environment/contoso-contributor.env.json
conditions (OK = achievable, OK* = achievable under assumptions, NO = blocked):
  OK  dt_instance
  OK  building_data
  NO  dt_models
  NO  topology_twins
...
2/6 conditions achievable; blocked conditions are certified unreachable with the operations this environment allows (checker: GOAL_UNSAT)
```

Anything that could not be read becomes an assumption, never a refusal.
`skillc env watch` re-probes on a schedule. See
[`docs/ENVIRONMENT.md`](https://github.com/ginaecho/skill-achievability-compiler/blob/main/docs/ENVIRONMENT.md).

## Graphs and ontologies: what can be established from this data? (`skillc twin`)

Some agents answer from a knowledge graph: a digital twin, a CMDB or a product graph,
read with the help of an ontology. Before such an agent explores the graph, skillc can
decide whether the answer is reachable from the data, and if not, what is missing.
This takes no model call and no query generation.

**The mapping.** The graph plays the role of the environment, and each evidence need
becomes a condition:

| your application | skillc |
|---|---|
| the instance graph (one tenant, one building) | the environment: the only source of evidence |
| the ontology | class hierarchy only; it never proves that a fact exists |
| an evidence need ("the places this set point controls") | a condition |
| a need found in the graph, with its path | a read step that establishes the condition |
| evidence held outside the graph (policy service, live values) | a declared source, counted as an assumption |
| the decision ("verify this change") | a `verify` step that requires every critical condition |

**Recipe for a new application**

1. **Write the evidence contract.** List each need and mark whether it is critical.
   This is a scenario in `SCENARIOS` in `src/skillc/env/twin.py`.
2. **Say how each need is found.** Write a probe in `PROBES`. A probe follows relations
   by local name in both directions (`hasPoint`/`isPointOf`) and allows a bounded number
   of hops. It reads blank-node structures through their anchor. For every need it
   returns the path that proves it, or what it looked for.
3. **Keep instance and vocabulary apart.** Pass the tenant graph as data. Pass ontologies
   as named graphs whose names contain "ontology", or with `--ontology`.
4. **Let the checker decide.** Each target becomes a pack, and the checker gives
   `ACHIEVABLE`, or `IMPOSSIBLE [BLOCKED_GUARD]` naming the missing condition. Missing
   evidence is never read as approval.
5. **Test with a small illustrative graph** that covers one variant per case: inverse
   relationships, extra hops, vendor classes and a missing fact. Then run it on real
   exports.

For example, the pack generated for a set point whose graph has no limits:

```text
Tool `read_equipment` (owner `deim`): adds `equipment`.             # graph
Tool `read_priority_state` (owner `deim`): adds `priority_state`.   # graph
Tool `verify` (owner `deim`): requires `equipment` and `min_max_units` and `priority_state` ...
Goal: `verdict`.                     -> IMPOSSIBLE: nothing establishes `min_max_units`
```

**Built in:** a set-point verifier and a schedule-update verifier for building digital
twins (Brick, RealEstateCore, BOT). Install with `pip install -e ".[twin]"`; it reads
Turtle, TriG, N-Triples, N-Quads or RDF/XML files offline.

```console
$ skillc twin check examples/building-twin/demo-building.trig --scenario setpoint --brief
ex:sp1: ACHIEVABLE
ex:sp2: IMPOSSIBLE  missing: min_max_units
ex:sp3: IMPOSSIBLE  missing: external_reference
ex:sp4: IMPOSSIBLE  missing: equipment, controlled_places, min_max_units, priority_state, external_reference
$ skillc twin check building.trig --tenant demo --scenario schedule --target zone1 \
      --source operating_policy=policy-service      # evidence held outside the graph
```

skillc checks that the evidence exists, not that its values are right; the verifier
still judges the values. See [`docs/TWIN.md`](docs/TWIN.md).

## Protocol checks versus goal-only checks

The default check judges the **declared protocol**, not every alternative plan.
Use a reviewed environment contract and `--goal-only` when rejection must mean
the goal is unreachable across the available capabilities:

```bash
skillc check SKILL.md --contract task-contract.json --goal-only --json
```

Without a protocol-independent refutation, protocol errors become `UNKNOWN`,
not a rejection of all alternative plans. `UNKNOWN` is neither rejection nor
permission to execute. For a trusted single-role Boolean contract,
`skillc plan task-contract.json -o generated-pack.json` constructs a checked
alternative protocol without an LLM. Details:
[compaction and goal-only policy](https://github.com/ginaecho/skill-achievability-compiler/blob/main/docs/archive/COMPACTION_PRECISION_ASSESSMENT_20260921.md).

## What the checker decides

A **pack** declares capabilities (STRIPS pre/effects, numeric assignments,
constrained non-determinism), a goal-marked global protocol (`act` / `msg` /
`choice` / tail-recursive `rec`/`continue` loops / `spawn`), a goal formula, the
initial state, and optionally per-role declared behaviours (`skills`):

```
   Γ ⊇ caps(G)          capability soundness   — no hallucinated tools
   G ⇓ {T_p}            realizability          — projection defined for every role
   ∀p. S_p ⊑ G↾p        direct conformance     — exact sender labels;
                                                  receivers may offer more
   Γ; G ⊨ ◇goal         liveness               — goal may-reachable (z3)
   ─────────────────────
   Γ ⊢ {S_p} : G ▷ ◇goal
```

A verdict reports two separate results (verdict schema `skillc.verdict/2`):
**goal reachability** (`ACHIEVABLE` / `IMPOSSIBLE` / `UNKNOWN`) and
**protocol typing** (`protocol`: `WELL_TYPED` / `REJECTED` / `NOT_CHECKED`).
Only goal refutations are `IMPOSSIBLE`. These are the results the refutation
soundness theorem covers.

| goal reason (`IMPOSSIBLE`) | failure mode it catches |
|---|---|
| `MISSING_CAPABILITY` | hallucinated planning — the protocol invokes a tool that is not granted |
| `GOAL_UNSAT` | no establisher for a goal conjunct, or a numeric refinement (e.g. *under $500*) unsatisfiable on every run |
| `BLOCKED_GUARD` | a mandatory action's precondition can never be satisfied (the retry-forever cause) |

| protocol reason (`protocol: REJECTED`) | failure mode it catches |
|---|---|
| `NON_PROJECTABLE` | a role must act inside a branch it is never told about (unobserved choice → deadlock/handoff freeze) |
| `NON_CONFORMANT` | a declared role behaviour does not refine its projected contract |

A protocol rejection is not a goal refutation. T-Comm requires every branch to
conform, so one bad branch rejects the protocol even when another branch
reaches the goal. Such a verdict reads `ACHIEVABLE` with `protocol: REJECTED`,
and `admissible` is false. Gates and monitors allow only admissible verdicts.
Each verdict also carries a `coverage` tag that names the formal result behind
it. See [`docs/VERDICT_COVERAGE.md`](https://github.com/ginaecho/skill-achievability-compiler/blob/main/docs/VERDICT_COVERAGE.md).

### How a verdict is produced for a natural-language skill

With `skillc check SKILL.md --llm --runtime M`, three stages run in this order. A stage that
refutes ends the check, so later stages (and the model call) do not run.

1. **Deterministic markdown front-end** (only with `--llm-when needed`). It compiles the
   skill without a model and keeps an `IMPOSSIBLE` verdict. Covered by the checker's
   theorems, relative to the pack the front-end extracted (`front_end: deterministic`).
2. **Deterministic requirement reader** (`env.manifest.refute_text`) against the manifest
   `M`. It refutes when a hard requirement is unavailable in `M`, with reason
   `REQUIREMENT_UNAVAILABLE` and the evidence line. Not covered by Theorem 1; `coverage` is
   `deterministic-reader:manifest` (`front_end: deterministic-reader`). `--no-rdet` skips
   it; `--rdet-only` runs only it.
3. **LLM compaction (P2g+) and the checker**. The model writes Controlled English, which is
   bound to `M` and checked. A refutation is covered by Theorem 1 relative to that pack
   (`front_end: llm`).

On the blind set3 (100 documents, 18 BLOCKED, judgement labels against the manifest text;
three samples pooled), P2g+ alone found 4 of 54 BLOCKED (recall 0.07) with 2 false
refutations of 246. The reader alone found 8 of 18 (0.44) with 7 false refutations of 82
(0.085). Their union found 24 of 54 (0.44) with 23 of 246 (0.093), against 0.41 and 50 of 246
(0.20) for the earlier P2g prompt. See
[`docs/COMPACTION_RELIABILITY.md`](https://github.com/ginaecho/skill-achievability-compiler/blob/main/docs/COMPACTION_RELIABILITY.md),
section "set3: P2g against P2g+".

## More than tool checking: stop impossible agent coordination

Suppose a main agent privately chooses a security or a performance review; a
reviewer performs it, and an editor must publish the matching report. Every
capability may exist, but if the editor is never told which branch was chosen,
it cannot know what to publish. Each branch reaches the goal on its own, so
the goal is not refuted. The coordination is still not realizable, and
`skillc` rejects the protocol before any agent starts:

```text
private-review-routing: ACHIEVABLE
  ACHIEVABLE  goal reachable along witness path
  PROTOCOL REJECTED (NON_PROJECTABLE): role 'editor' must act in a branch of
    the main agent's choice but receives no message distinguishing the branches
  coverage: none:witness-only
```

The repair is a protocol change: tell the editor the branch label. Compaction
has three paths, none of which puts an LLM in the trusted decision:

| Input path | Use |
|---|---|
| Deterministic frontend | Supported markdown/prose patterns; zero LLM tokens |
| `skillc compile --llm` | Unrestricted prose via Anthropic or Azure OpenAI |
| `skillc check --llm --llm-when needed` | Deterministic front-end first; the LLM is called only if it does not already refute (default `always`) |
| Embedded `skillc-pack` | Author-reviewed formal capabilities and protocol |

For the `deadlock_unobserved` corpus case, the published token model estimates
**1,888 tokens** of one-time compaction versus **231,870 tokens** for a typical
two-agent deadlock run (modeled, not measured). See
[Impossible agent coordination](https://github.com/ginaecho/skill-achievability-compiler/blob/main/docs/IMPOSSIBLE_AGENT_COORDINATION.md).

## Results

* **Public skills** ([anthropics/skills](https://github.com/anthropics/skills),
  42 `SKILL.md`): **42/42 achievable** in their home runtime (`claude-ai`), and
  **18/42 refuted** under `claude-code`, each naming the missing tool and source
  line; granting the named tools flips every one back.
  [Real-skills report](https://github.com/ginaecho/skill-achievability-compiler/blob/main/docs/REAL_SKILLS_REPORT.md) ·
  [benchmark report](https://github.com/ginaecho/skill-achievability-compiler/blob/main/docs/BENCHMARK_REPORT.md).
* **Semantic level** (recorded with `skillc 0.2.0`): 4/4 LLM-compacted consumer
  skills `ACHIEVABLE`, 6/6 seeded faults refuted.
  [Semantic validation](https://github.com/ginaecho/skill-achievability-compiler/blob/main/docs/SEMANTIC_VALIDATION.md).
* **Ground-truth corpus** (`skillc eval`): **FN = 0**; the only false
  `ACHIEVABLE`s are the two planted payload/intent residues.
* **Hosted agents** (Foundry, Agent Framework): with the policy removed from the
  prompt, the bare agent delivered unapproved reports and skillc refused them
  every time. [Comparison](https://github.com/ginaecho/skill-achievability-compiler/blob/main/docs/HOSTED_AGENT_COMPARISON.md).
* **Agent 365 cases**: 10 source-backed workflows, **123/123** expectations met
  (63 static, 60 runtime; every denied runtime attempt invoked no transport).
* **Scout parity**: 31 parity and MCP tests pass under Scout's own interpreter.

These are snapshot results, not a guarantee of concrete success. Watch the
[107-second demo](https://github.com/ginaecho/skill-achievability-compiler/blob/main/demo/real-skill-cases/skillc-real-skills-demo.mp4).

## What checking costs (`skillc cost`)

The trusted core spends **zero tokens**; the only token cost is the optional
LLM compaction, paid once per skill version. Modeled leverage (wasted tokens per
prevented run ÷ tokens spent checking) for a median real skill:

| reason | turns before it stops the agent | leverage |
|---|---|---|
| `MISSING_CAPABILITY` | 3–8–14, one agent | 17× |
| `GOAL_UNSAT` | 8–18–30, and the run may *believe it succeeded* | 61× |
| `NON_PROJECTABLE` / `NON_CONFORMANT` (protocol rejection, not a goal refutation) | 6–15–30, **two** agents billed | 91× |
| `BLOCKED_GUARD` | 12–25–50 — retry-forever runs to the turn cap | 106× |

`UNKNOWN` claims no savings. Runtime waste is a **model**, not a measurement.
See [`docs/TOKEN_ECONOMICS.md`](https://github.com/ginaecho/skill-achievability-compiler/blob/main/docs/TOKEN_ECONOMICS.md).

## Honest limitations

**Declarations, not reality.** Static validation judges the declared pack;
human review must establish intent fidelity, and runtime verification must
establish actual tool effects. `ACHIEVABLE` is an abstract witness, not a
guarantee. Protocol rejection does not rule out an alternative plan.

**Enforcement depends on placement.** Inside a tool-call path (Agent Framework
middleware, Claude Code and Copilot hooks) a denial stops the tool. As MCP tools
(Scout) skillc is cooperative. Approvals are only as trustworthy as the host
channel that issues them and the identities it supplies.

**Coordination assumptions.** Roles without declared behaviours are assumed
conformant; dynamic spawning yields `UNKNOWN` unless a refutation already applies.

**Proof boundary.** The [refutation-sound abstraction theorem](https://github.com/ginaecho/skill-achievability-compiler/blob/main/proof/SkillAchievability.v)
is mechanized in Coq with zero axioms, but the Python transition system is not
instantiated in Coq, and the conformance adapter's equivalence to the
declarative judgment remains an open proof obligation.

## Development and resources

Run `python -m pytest` for the full suite. `skillc audit ./my-skill` is a
deterministic pre-pass for manifest inconsistencies and risky patterns; it is
not a security guarantee.

[Source](https://github.com/ginaecho/skill-achievability-compiler/tree/main/src/skillc) ·
[Examples](https://github.com/ginaecho/skill-achievability-compiler/tree/main/examples) ·
[Context and terms](https://github.com/ginaecho/skill-achievability-compiler/blob/main/CONTEXT.md) ·
[Compaction prompt](https://github.com/ginaecho/skill-achievability-compiler/blob/main/docs/COMPACTION_PROMPT.md) ·
[Citation](https://github.com/ginaecho/skill-achievability-compiler/blob/main/CITATION.cff) ·
[MIT License](https://github.com/ginaecho/skill-achievability-compiler/blob/main/LICENSE)

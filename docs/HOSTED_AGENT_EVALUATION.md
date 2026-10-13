# Does skillc help hosted multi-agent deployments? An evaluation plan

**Status:** plan, 2026-10-07. Companion to `docs/HOSTED_AGENT.md` and
`docs/HOSTED_AGENT_IMPLEMENTATION_PLAN.md`. The question is not "does
skillc run" but "what goes better, by how much, against what people would
otherwise do". That needs a comparison with controls, on outcomes the
operator cares about, with enough repetitions to separate signal from model
noise.

## 1. The claims, each with the comparison that can falsify it

| claim | comparison | metric | what would falsify it |
|---|---|---|---|
| C1 **Pre-deploy refutation.** skillc catches deployment faults before `azd deploy`, with no model call | skillc gate vs. (a) no check, (b) `azd deploy` itself, (c) an LLM judge given the same files | detection rate per fault class; false alarms on correct configurations; seconds and tokens to a verdict | a fault class skillc misses that `azd deploy` or the judge catches; any false IMPOSSIBLE on a correct configuration (soundness) |
| C2 **Run-time protocol enforcement.** With per-agent monitors, runs violate the protocol policies less and reach the goals more | bare vs. monitor (and the alternatives in section 3) | goal attainment G1 to G14; policy violations S1, S2, D1, A1; attainment by branch | no difference beyond confidence intervals, or attainment drops because the monitor over-denies |
| C3 **Impossible tasks stop early and honestly.** When the deliverable cannot be achieved here, the monitored agent stops and says so instead of burning turns or claiming success | bare vs. monitor on impossible variants | tool calls and tokens after the point of impossibility; honest-report rate; hallucinated-completion rate | monitored agents loop as long or report completion as often |
| C4 **Cheap.** The checks cost nothing in model tokens and little in latency | measured | gate wall time; middleware overhead per tool call; monitor plan-check time | overhead comparable to a model call |
| C5 **Generalizes.** The results hold beyond the finance case | 3+ cases, 2 models | same metrics per case | effects confined to finance or to one model |

Soundness (no false refutation) is the claim skillc stakes its design on, so
C1's false-alarm column is reported first, before any detection rate.

## 2. Datasets (cases)

The session-typed-agents repository has 27 protocol cases with goals and
policies already written (`experiments/cases/*`). Three are the minimum,
chosen for different shapes:

| case | shape | why |
|---|---|---|
| `finance` | 6 roles, one data-dependent choice, approval ordering, 14 goals, 4 policies | the deployed example; high and standard branches |
| `clinical_enrollment` or `banking` | approval and separation-of-duty heavy | tests D1-style ownership properties under A2A identities |
| `trade_settlement` or `travel_saga` | retry or compensation loop | tests the `loop` fragment and observations that revoke a plan mid-run |

For C1 only, the 100-document `benchmark/claude_env` corpus and the real-skill
rejection benchmark already in this repository add breadth for the gate's
skill reading, but they are not hosted deployments.

### Fault injection for C1 (per case, from the correct `azure.yaml` and pack)

Each fault is one edit; correct configurations are included as negatives.

| id | fault | expected skillc verdict |
|---|---|---|
| F1 | remove one `RemoteA2A` connection (a protocol edge) | IMPOSSIBLE at the first `tells` on that edge |
| F2 | callee without `a2a` in `agentEndpoint.protocols` | IMPOSSIBLE for every message into it |
| F3 | remove a toolbox tool a role needs (`azure_ai_search`) | IMPOSSIBLE on the branch that needs it, or UNKNOWN-assumed if the data choice can avoid it, stated as such |
| F4 | deliverable needs a connection that is not declared (email) | IMPOSSIBLE, BLOCKED_GUARD naming the connection |
| F5 | approval tool owned by the wrong role (D1 violation) | refuted by ownership check |
| F6 | network isolated, public host in a skill | UNKNOWN with the assumption named, never IMPOSSIBLE (soundness) |
| F7 | skill asks for a tool no role has | IMPOSSIBLE, MISSING_CAPABILITY |
| N1 to N3 | correct base, search, and isolated configurations | ACHIEVABLE or UNKNOWN-assumed; never IMPOSSIBLE |

Deploying each faulty configuration once to see which faults `azd deploy`
or the first invocation would have caught, and at what cost, is the control
for C1 (one deploy per fault class is enough; the cost is minutes and a
version each).

## 3. Arms (what we compare against)

Mirrors the design the finance case already used (`campaign_full_n30.json`:
arms × models × n=30, branch schedule 15 high and 15 standard), so results
are comparable with the earlier session-typed study.

| arm | description | stands for |
|---|---|---|
| **bare** | the agents as deployed today: skills as instructions, no checks | what most teams ship |
| **prompt-only** | bare plus the protocol and policies written into every agent's instructions | "just tell the model the rules" |
| **llm-judge** | bare plus an LLM that reviews each agent's plan and tool call against the protocol text (same model) | the common guardrail pattern; costs tokens, not sound |
| **foundry-approval** | bare plus `require_approval: always` on the approval and delivery tools, auto-approved by a scripted policy | the platform's own control |
| **skillc-gate** | gate only: faulty configurations never deploy; correct ones run bare | C1 alone |
| **skillc-monitor** | per-agent monitor middleware, no gate | C2, C3 alone |
| **skillc-full** | gate plus monitor | the proposal |

Models: `gpt-5.4` and `gpt-5-mini` (both deployed in the project), because
weaker models benefit more from structure and that interaction matters.

## 4. Metrics, collected from traces, not from the agents' own claims

* **Goal attainment**: each case's goal predicates evaluated on the message
  trace (the finance case has them as `predicate` fields in `case.yaml`).
  Reported overall and per branch.
* **Policy violations**: sequence, separation and aggregate policies
  (`v1.policy`) checked on the trace, counting violations per run.
* **Cost**: tool calls, model calls, input and output tokens per run (from
  OpenTelemetry in Application Insights, which the platform injects), and
  wall time.
* **Waste on impossible tasks**: tool calls and tokens after the first step
  that could not succeed (defined per impossible variant), and the
  honest-report rate: did the final answer say the deliverable was not done.
* **Over-denial**: monitored runs where a denial blocked a step that the
  bare run performed correctly (false positives of the monitor).
* **Overhead**: middleware latency per tool call; gate seconds per
  configuration; tokens: zero for skillc by construction, measured for the
  LLM judge.

## 5. Statistics

n = 30 runs per arm, model and case for C2 and C3 (the same n as the
earlier campaign), balanced across branches by the schedule. Proportions
with Wilson 95% intervals; attainment differences by Fisher's exact test
paired by scenario and seed; costs by medians with bootstrap intervals.
Report effect sizes, not only p-values. Pre-register the fault list and
the predicates before running; no post-hoc metric changes.

## 6. Stages

| stage | scope | cost | exit |
|---|---|---|---|
| **S-A offline** | C1 on finance: gate over F1 to F7 and N1 to N3, versus the LLM judge | no deployment; minutes | a confusion table per fault; zero false IMPOSSIBLE |
| **S-B single case, live** | C2, C3, C4 on the finance group deployment: 7 arms × 2 models × n=30 | about 420 runs per model, each 30 to 60 s; model tokens are the main cost | attainment and violation tables with intervals |
| **S-C controls deployed** | one deploy per fault class to measure what the platform catches and what it costs | 7 deploys | cost of late detection versus the gate |
| **S-D generalize** | S-A and S-B on two more cases | as S-B per case | effects replicated or not |
| **S-E ablations** | skillc-full minus one component at a time: plan gate, action gate, reasoning scan, observations, conformance check, declared-environment binding | subset of S-B cells | which component carries the effect |

S-A needs nothing new beyond the gate (S2 of the implementation plan). S-B
needs the group deployment and the adapter. Budget note: the earlier finance
campaign set `paid_launch_authorized: false` until the cell count was
reviewed; this plan should follow the same discipline.

## 7. Threats to validity, and what we do about them

* **We wrote the pack.** If the protocol pack is hand-tuned to the agents,
  the comparison favours skillc. Mitigation: the pack is derived from the
  same `v1.scr` and skills the agents run from, the derivation is in the
  repository, and S-E includes an arm where the pack is produced by the
  compaction front-end from the skills alone.
* **The judge is a straw man.** Give the LLM judge the same artifacts skillc
  gets, a strong prompt, and the same model as the agents; report its token
  cost honestly.
* **Model nondeterminism.** n=30 and intervals; both branches; two models.
* **Over-fitting to finance.** S-D.
* **The monitor changes the prompt.** Monitored agents receive skillc
  instructions; the prompt-only arm controls for "more instructions".
* **Single tenant and region.** State it; the platform facts are the same
  everywhere, the latency numbers are not.

## 8. What "useful" would look like in one table

| | bare | prompt-only | llm-judge | foundry-approval | skillc-full |
|---|---|---|---|---|---|
| faults caught before deploy (of 7) | 0 | 0 | ? | 0 | ? |
| false IMPOSSIBLE on correct configs | 0 | 0 | ? | 0 | must be 0 |
| goal attainment, high branch | ? | ? | ? | ? | ? |
| policy violations per run | ? | ? | ? | ? | ? |
| tokens wasted on impossible tasks | ? | ? | ? | ? | ? |
| honest "not done" on impossible tasks | ? | ? | ? | ? | ? |
| extra model tokens for the guardrail | 0 | small | large | 0 | 0 |

If skillc-full is not better than llm-judge on the middle rows while costing
less on the last row, the usefulness claim is only "cheaper", and the paper
should say so.

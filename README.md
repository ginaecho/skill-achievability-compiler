# skillc: the skill achievability compiler

**skillc decides, before an agent runs, whether its goal can be reached with the tools, permissions
and data it actually has. While the agent runs, it can also stop actions that leave the approved plan.**
The decision is made by a z3-based checker with no model in it. `IMPOSSIBLE` is a proof relative to what
was declared; `ACHIEVABLE` means nothing blocks the goal, not that the run will succeed.

## Contents

1. [What skillc is](#what-skillc-is)
2. [The problem it solves](#the-problem-it-solves)
3. [Tools](#tools)
4. [Benchmark: performance and cost](#benchmark-performance-and-cost)
5. [Limitations](#limitations)
6. [Learn more](#learn-more)

## What skillc is

```
 skill / agent file / prompt / graph workflow
        │  read deterministically (or by a model: untrusted)
        ▼
      pack ──► [ checker: no model, sound for refutation ] ──► ACHIEVABLE | IMPOSSIBLE | UNKNOWN
        ▲                                                         │
 environment: tools, permissions, MCP servers, tenant data         ▼
                                       [ runtime monitor: plan, actions, approvals ]
```

* **Static check (before the run).** It reads a `SKILL.md`, an agent file, a prompt or a formal
  pack, binds it to an environment and decides whether the goal is reachable. `IMPOSSIBLE` always
  names its reason:
  * `MISSING_CAPABILITY`: a tool that isn't granted;
  * `GOAL_UNSAT`: a goal nothing can establish;
  * `BLOCKED_GUARD`: a precondition that can never hold.
* **Runtime monitor (during the run).** It holds the agent to its approved plan, refuses actions
  whose preconditions or permissions are missing, and can require a single-use user approval.
* **Same answer every time.** For the same input, skillc always gives the same verdict and the same
  reason.

## The problem it solves

**Agents find out too late that a task cannot be done.** They spend tokens, retry forever, believe
they succeeded, or take an action they shouldn't. skillc moves that discovery to before the run, and
puts a gate outside the model during it.

**When you don't need skillc.** For a one-off, read-only task, the agent should just try. Take "summarise
the tables in this Databricks workspace and suggest KPIs":
* The agent looks for a Databricks CLI profile, token or connector.
* If there is none, it says so at once. If there is one, it runs `DESCRIBE` and `COUNT(*)` and
  profiles the columns.

Failure is cheap and visible, so trying is the best check. A SKILL.md that says "check your tools
and permissions first" covers most of the rest.

**Where an agent's own check falls short:**

| | the agent checks itself | skillc |
|---|---|---|
| Guarantee | Best effort: it can skip the check, invent a tool or misread a permission | `IMPOSSIBLE` is a proof; the same input always gives the same verdict |
| When | During the run, after tokens and maybe side effects | Before any run, with zero model tokens |
| What it sees | "Is the tool there?" | Also ordering and preconditions (send needs approval first), handoffs between agents, deadlocks |
| Against prompt injection | Its instructions can be overridden | As middleware outside the model, a refused call cannot run |

**Best applications**, strongest first:

1. **A runtime guard for agents that act.** A delete, payment or send cannot happen outside the
   approved plan, whatever the model was told. Example: Microsoft Agent 365 agents built with Agent
   Framework.
2. **A pre-deployment gate for skill and agent catalogs.** Many skills across many runtimes
   (claude.ai, Claude Code, Copilot, one tenant or another) are checked in CI without running an
   agent. The same skill can be `ACHIEVABLE` in one runtime and `IMPOSSIBLE` in another.
3. **Data-readiness checks.** Can this workflow's evidence come from this tenant's graph or schema,
   for each of many tenants, before anyone builds it? Missing evidence is never read as approval.

Not a fit: ad-hoc interactive tasks, and free-form prompts. The deterministic reader needs authored
text that says what "done" means; otherwise it answers `UNKNOWN`, which never counts as permission.

## Tools

```bash
pip install -e .                       # the skillc CLI (Python 3.10+)
pip install -e ".[twin]"               # + rdflib, for graphs (skillc twin)
pip install -e ".[agent-framework]"    # + Microsoft Agent Framework middleware (Agent 365)
pip install -e ".[mcp]"                # + MCP server, for hosts without hooks (Scout)
pip install -e ".[dev]"                # + tests and lint
```

| Tool | What it does | Use it when |
|---|---|---|
| `skillc check SKILL.md --profile claude-code` | Verdict for one skill, agent file, prompt or pack in a runtime | Before publishing or installing a skill; exit codes `0` ok, `1` impossible, `3` unknown, `2` error gate CI |
| `skillc scan DIR` | `check` for every skill under a folder | CI for a skill repository |
| `skillc reach SKILL.md --claude` or `--env FILE` | What the skill can achieve in *this* environment, a checked plan, and the fix for what is blocked | Before running in a real workspace or subscription |
| `skillc env probe` | Read the environment read-only into a graph: Azure roles and policies, MCP servers, tools | To snapshot, `diff` or `watch` what an agent may do |
| `skillc twin explore GRAPH` · `skillc twin check GRAPH --workflow FILE` | What a graph holds, and per target which workflow evidence it has and which is missing | Before building a verifier or report on tenant data |
| `skillc monitor init` | Runtime monitor through Claude Code or Copilot hooks: plan first, every action checked | Coding agents with write or shell access |
| `skillc_monitor(..., strict=True, fail_open=False)` | Enforced gate as Agent Framework middleware, with evidence-bound approvals | Agent 365 and Foundry hosted agents that send, pay or delete |
| `skillc monitor scout-install` | The same checks as MCP tools (cooperative, not enforced) | Microsoft Scout |
| `skillc gate` | Packs, skills and topology against an azd project's `azure.yaml` | Before `azd deploy` |
| `skillc compile` · `skillc ce` · `skillc audit` · `skillc cost` | The formal pack; Controlled English; a risky-pattern pre-pass; token economics | Reviewing or explaining a verdict |

**Try it in two minutes:** `python demo/skillc-here/app.py`. It reads your machine by itself and shows
one skill's verdict in claude.ai, Claude Code and here. See [all demos](demo/README.md).

```console
$ skillc check call-to-book/SKILL.md --profile claude-ai
call-to-book: ACHIEVABLE
$ skillc check call-to-book/SKILL.md --profile claude-code
call-to-book: IMPOSSIBLE [MISSING_CAPABILITY]
  missing: ask_user_input_v0 (line 7)
```

## Benchmark: performance and cost

**Performance**

| Benchmark | Result |
|---|---|
| Public skills: 42 `SKILL.md` from Anthropic's skills repository | 42/42 `ACHIEVABLE` in their home runtime; 18/42 `IMPOSSIBLE` in Claude Code, each naming the missing tool and line, and every one flips back when that tool is granted |
| Ground-truth corpus (`skillc eval`) | 0 false negatives; the only false `ACHIEVABLE`s are two planted residues |
| Agent 365: ten source-backed workflows | 123/123 expectations met (63 static, 60 runtime); no denied call reached a transport |
| Hosted agents (Foundry, Agent Framework) | With the policy removed from the prompt, the bare agent sent unapproved reports; skillc refused every one |
| Natural-language skills, blind set (model reader + deterministic reader) | Found 44% of blocked skills, with 9% false refutations |
| Runtime guard for wrong actions, blind incident traces | 27% recall (90–100% on development sets); 1 false hit per 1,000 reasoning units and no false denials of legitimate actions |

The blind numbers are the honest ones. Static refutation is strong when the skill states its tools
and goal. Catching risky intent from free-form reasoning, with no model, generalises only partly.

**Cost**

* **The checker spends zero model tokens.** The only token cost is optional model compaction of
  prose, paid once per skill version.
* **Modeled savings for a median real skill** (tokens wasted by a prevented run ÷ tokens spent
  checking):

| Reason | How long the agent runs before it stops | Leverage |
|---|---|---|
| `MISSING_CAPABILITY` | 3–8–14 turns | 17× |
| `GOAL_UNSAT` | 8–18–30 turns, and it may *believe it succeeded* | 61× |
| Protocol rejected (deadlocked hand-off) | 6–15–30 turns, two agents billed | 91× |
| `BLOCKED_GUARD` | 12–25–50 turns, retrying until the turn cap | 106× |

Runtime waste is a model, not a measurement. `UNKNOWN` claims no savings. Run `skillc cost`, and see
[`docs/TOKEN_ECONOMICS.md`](docs/TOKEN_ECONOMICS.md).

## Limitations

* **Declarations, not reality.** skillc judges what was declared. Whether the declaration matches the
  intent needs review, and whether tools do what they claim needs the runtime monitor.
* **Placement decides enforcement.** In a tool-call path (Agent Framework middleware, Claude Code and
  Copilot hooks) a refusal stops the call. As MCP tools (Scout), the agent must cooperate.
* **Free-form text abstains.** It gives `UNKNOWN` unless a model or a reviewed contract supplies the
  goal.
* **Proof boundary.** The refutation theorem is mechanized in Coq with no axioms
  ([`proof/`](proof/SkillAchievability.v)); the Python implementation is not itself proved.

## Learn more

* [Full reference](docs/REFERENCE.md): every integration, the checker's judgments and the full results.
* [Demos](demo/README.md) · [Agent 365 security](docs/AGENT365_SECURITY.md) · [Scout](docs/SCOUT_PARITY.md) · [Runtime monitor](docs/RUNTIME_MONITOR.md)
* [Environment and `reach`](docs/ENVIRONMENT.md) · [Graphs and `twin`](docs/TWIN.md) · [Controlled English](docs/CONTROLLED_ENGLISH.md) · [Verdict coverage](docs/VERDICT_COVERAGE.md)
* [Benchmark report](docs/BENCHMARK_REPORT.md) · [Real skills](docs/REAL_SKILLS_REPORT.md) · [Compaction reliability](docs/COMPACTION_RELIABILITY.md) · [Interaction benchmark](docs/INTERACTION_BENCHMARK_REPORT.md)
* [Context and terms](CONTEXT.md) · [Citation](CITATION.cff) · [MIT License](LICENSE)

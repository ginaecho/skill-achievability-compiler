# SkillC benchmark report (2026-10-05)

This report explains, in plain English, what we tested SkillC on and how well it did.

## What SkillC answers

You give SkillC an *intent*: a SKILL.md, an agent.md, or a prompt. You also give it an
*environment*: the tools and permissions the agent will actually have. SkillC answers with
one of three verdicts:

| Verdict | Meaning |
|---|---|
| **ACHIEVABLE** | Nothing in the environment stops the intent. |
| **IMPOSSIBLE** | SkillC can prove the intent cannot succeed here, and says why (for example, a missing tool). |
| **UNKNOWN** | SkillC is not sure, so it does not guess. The agent should not run until a person checks it. |

The verdict that matters most is **IMPOSSIBLE**. A *false alarm* means SkillC said
IMPOSSIBLE when the intent was actually fine.

## Two ways to read the text ("compaction")

Before checking, SkillC turns the natural-language text into a small structured summary.
It can do this in two ways:

- **Rule-based**: no AI, fully repeatable. It only picks up things written very explicitly.
- **gpt-5.4**: an LLM (Azure AI Foundry) reads the text. It catches far more, and sometimes
  misreads. SkillC then double-checks the LLM's summary against the original text and the
  environment. Anything the LLM invented becomes **UNKNOWN**, not IMPOSSIBLE.

The checking step after the summary is the same in both modes, and it is deterministic.

## Test set 1: labelled topics (we know the right answer)

### What was tested

- **132 topics**, each written as **3 separate texts**: a SKILL.md, an agent.md, and a
  prompt. That makes **396 test inputs**. Each form is written on its own; none is generated
  from another.
  - **32 reference topics.** Each covers one known failure type, such as a missing tool, a
    goal that can never be reached, a blocked step, or agents that misroute messages.
    Examples: "Book a flight and send email confirmation", "Route a ticket to a handler".
  - **100 everyday business topics** in 8 areas, including travel and events, finance, HR,
    DevOps, data and ML, customer support, public services, and marketing and legal.
    Examples: "Card dispute triage", "Canary model release", "Campaign spend plan".
- Each topic comes with its own environment (tools and conditions). Each topic also has a
  correct answer, checked automatically by a validator.
- The texts give **no hints**. They never say "this is impossible", and they never name the
  answer.
- **345 of the 396 inputs have a correct answer of ACHIEVABLE or IMPOSSIBLE**, and these
  are scored below. The other 51 are either topics whose correct answer is UNKNOWN (27), or
  topics used only to test the summary step (24).

### Results

"Positive" means SkillC said **IMPOSSIBLE**.

| | Rule-based | gpt-5.4 |
|---|---:|---:|
| **False alarm rate** (fine intents wrongly called IMPOSSIBLE) | **0%** (0 of 136) | **2.0%** (3 of 149) |
| **Precision** (when it says IMPOSSIBLE, how often it is right) | 100% (36 of 36) | 98% (149 of 152) |
| **Recall** (impossible intents it actually caught) | 19% (36 of 189) | **79%** (149 of 189) |
| **Accuracy** (on inputs where it gave a verdict) | 56% | 89% |
| **Gave a verdict** (did not say UNKNOWN) | 88% | 97% |

### Confusion matrix: gpt-5.4 (345 labelled inputs)

| | SkillC said IMPOSSIBLE | SkillC said ACHIEVABLE | SkillC said UNKNOWN |
|---|---:|---:|---:|
| **Truly IMPOSSIBLE (189)** | ✅ 149 caught | ❌ 35 missed | 5 |
| **Truly ACHIEVABLE (156)** | ⚠️ 3 false alarms | ✅ 146 | 7 |

### Confusion matrix: rule-based (345 labelled inputs)

| | SkillC said IMPOSSIBLE | SkillC said ACHIEVABLE | SkillC said UNKNOWN |
|---|---:|---:|---:|
| **Truly IMPOSSIBLE (189)** | ✅ 36 caught | ❌ 133 missed | 20 |
| **Truly ACHIEVABLE (156)** | ⚠️ 0 false alarms | ✅ 136 | 20 |

### Results by form (gpt-5.4)

Each form has 115 labelled inputs.

| Form | Caught | Missed | False alarms | Correct ACHIEVABLE | UNKNOWN | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|---:|
| SKILL.md | 48 | 12 | 1 | 48 | 6 | 98% | 76% |
| agent.md | 49 | 12 | 1 | 47 | 6 | 98% | 78% |
| prompt | 52 | 11 | 1 | 51 | 0 | 98% | 83% |

All three forms now perform about the same.

The 3 false alarms are all in multi-agent hand-offs, where SkillC judged that one agent
could not tell which branch another agent took: "Itinerary routing" (agent.md), "Card
dispute triage" (SKILL.md), and "Return label retry" (prompt).

### In one sentence

The rule-based mode almost never raises a false alarm, but it misses most problems.
gpt-5.4 catches about 4 in 5 problems, and about 1 in 50 of its IMPOSSIBLE verdicts is a
false alarm.

## Test set 2: real files from public repositories

### What was tested

These are **unchanged files written by real people**, pinned to exact commits:

- **SKILL.md**: 588 skills from public repositories, including `anthropics/skills`,
  `addyosmani/agent-skills`, `alirezarezvani/claude-skills`, and `google/langextract`.
- **agent.md**: 168 agents from `github/awesome-copilot` (MIT).
- **prompt**: 143 prompts from `github/awesome-copilot` (MIT).

To compare the three forms fairly, we used **143 of each** (429 files). Each file was
checked against its **home environment**, the product it was written for: Claude Code for
skills, and VS Code Copilot for agents and prompts.

### Why there is no full confusion matrix here

These files have no answer key. Nobody has labelled which real skills are "really
achievable". So we can only check **SkillC's IMPOSSIBLE verdicts**: a person looked at each
reported missing tool and decided whether it really is missing. The measure below is
therefore **precision**: when SkillC said IMPOSSIBLE, how often was it right?

### Results: precision of IMPOSSIBLE verdicts

| | Rule-based | gpt-5.4 |
|---|---:|---:|
| **Skills** | 50% (5 of 10) | 67% (6 of 9), plus 13 multi-step or blocked-step refutations not yet checked by hand |
| **Agents** | 92% (22 of 24) | 76% (58 of 76), plus 8 not yet checked |
| **Prompts** | 100% (5 of 5) | 60% (15 of 25), plus 9 not yet checked |

### All verdicts on the 429 real files

| Form | Mode | ACHIEVABLE | IMPOSSIBLE | UNKNOWN | Error |
|---|---|---:|---:|---:|---:|
| Skills | Rule-based | 41 | 10 | 92 | 0 |
| Skills | gpt-5.4 | 82 | 22 | 36 | 3 |
| Agents | Rule-based | 27 | 24 | 92 | 0 |
| Agents | gpt-5.4 | 41 | 84 | 18 | 0 |
| Prompts | Rule-based | 27 | 5 | 111 | 0 |
| Prompts | gpt-5.4 | 94 | 34 | 14 | 1 |

### Why real files score lower than the topics

- **Unofficial tool names.** Many real agents and prompts use tool names that VS Code
  accepts but does not document, such as `findTestFiles`, `terminalCommand`, or `todo`.
  SkillC checks against the documented list, so it reports these as missing.
- **Invented tool names.** The LLM sometimes makes up an operation name, for example
  `create_dashboard_via_web_ui`. SkillC turns many of these into UNKNOWN, but not all.
- **Few cases.** For skills, only 9 to 10 IMPOSSIBLE verdicts have been checked, so one
  verdict moves the percentage by about 10 points.

## Honest caveats

- We improved SkillC while looking at these same results. The numbers are therefore likely
  somewhat **optimistic**. A fresh, unseen test set would give a fairer estimate.
- The 100 everyday business topics were written with AI help and are somewhat formulaic.
- The ranges in square brackets in the raw results files are 95% confidence intervals.
  With small counts, such as the real-skill rows, they are wide.

## How to reproduce

The data lives on the `gc/data_train_test` branch.

```
# Labelled topics (omit --llm for rule-based)
python demo/skillc-architecture-app/benchmark_catalog.py --catalog-root <data checkout> --llm gpt-5.4

# Real files (omit --llm for rule-based)
python demo/skillc-architecture-app/benchmark_real_artifacts.py --data-root <data checkout> --balanced-only --per-kind 143 --llm gpt-5.4
```

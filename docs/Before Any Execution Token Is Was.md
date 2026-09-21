# Before Any Execution Token Is Wasted

A little proof. A smarter start.

### ⚙️ SkillC is the achievability compiler for agent skills

AI agents burn tokens pursuing goals they can never achieve. A tool is missing.
A constraint has no solution. Two agents wait forever for each other. Teams
usually discover these failures only after the agent has reasoned, retried, and
spent its runtime budget.

SkillC catches them before execution. It compiles an agent skill into a formal
model of its goal, tools, constraints, and coordination protocol, then checks
whether the goal is reachable in the declared environment.

If the answer is `IMPOSSIBLE`, SkillC names the blocker so an integrating
runtime or CI gate can stop the run.

> **Not another LLM judging an LLM. A compiler backed by a formal framework.**

---

## 🚨 Why agents need a compiler

Programming languages have compilers that reject invalid programs before they
run. Agent skills are becoming the language we use to program agents, but we
still ship them without checking whether their goals are reachable.

Today's loop is expensive:

```text
write -> run -> fail -> inspect traces -> patch -> retry
```

SkillC moves failure discovery to compile time:

```text
author -> compile -> check -> reject impossible work -> run what remains
```

The result is fewer doomed executions, faster repairs, and a reusable quality
gate for agent development, CI/CD, frameworks, and skill marketplaces.

---

## 🔍 What SkillC catches

| Failure | Example | Verdict evidence |
|---|---|---|
| 📭 Missing capability | The skill sends email, but no email tool exists | Missing tool and source location |
| 💸 Unsatisfiable goal | The goal requires a flight under $500, but every available result exceeds it | Unreachable goal constraint |
| 🔄 Coordination failure | The planner waits for the worker while the worker waits for the planner | Blocked or unobservable handoff |

These failures may be hidden in natural language. Once represented with
explicit semantics, they become machine-checkable before runtime.

---

## 🛡️ Why the verdict is trustworthy

SkillC separates language understanding from the trusted decision:

```text
natural-language skill
  -> optional LLM compaction
  -> schema-validated formal pack
  -> deterministic checker
  -> evidence-carrying verdict
```

An LLM may translate the skill into a formal pack, much like a compiler
front-end creates an intermediate representation. The LLM does not decide
whether the skill is possible.

The trusted checker applies explicit inference rules and solver-backed
reachability analysis. Its central refutation theorem is mechanized in Coq with
zero axioms:

> If SkillC returns `IMPOSSIBLE` for the formal pack in the declared
> environment, no execution represented by that pack can reach its goal.

The guarantee is deliberately precise:

* ❌ `IMPOSSIBLE` is a proof-backed refutation.
* ✅ `ACHIEVABLE` provides an abstract witness path, not a guarantee of concrete success.
* ⚪ `UNKNOWN` refuses to overclaim outside the supported decision boundary.

This is the differentiator: not a prediction, not an AI opinion, but a
machine-checked refutation theorem. The theorem is relative to the declared
model and its simulation assumptions; the exact Python checker is not
mechanized in Coq. See the [paper scope](../paper/README.md).

---

## 📊 Measured impact

In our larger evaluation, 46 checker-refuted agent runs produced no correct
result and consumed **15,841,106 runtime tokens**.

| Evidence set | With SkillC | Without SkillC | With as % of without | Tokens saved |
|---|---:|---:|---:|---:|
| 46 rejected and unsuccessful runs | 209,195 | 15,841,106 | **1.32%** | **98.68%** |
| Fully measured PDF and XLSX subset | 54,039 | 367,220 | **14.72%** | **85.28%** |

Across the full failure set, SkillC used **1.32%** as many tokens as the
unchecked executions, equivalent to **75.7x leverage**. Runtime tokens were
measured from real agent and subagent API calls. The full-set compaction total
combines 54,039 measured tokens with 155,156 tokens estimated from separate
measured compactions.

The PDF and XLSX subset is measured on both sides: one compaction per skill
versus eight failed executions.

Measurement demonstrates the savings. The Coq theorem explains why the
`IMPOSSIBLE` verdict can be trusted.

---

## 🔌 Built to go anywhere

SkillC is a pre-execution gate, not a replacement agent framework:

```text
your skill -> SkillC -> reject with evidence or continue to runtime
```

It can run in an editor, CI/CD pipeline, agent framework, skill registry, or
enterprise governance layer.
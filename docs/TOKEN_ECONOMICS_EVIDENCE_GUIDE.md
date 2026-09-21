# Understanding SkillC token-economics measurements

SkillC token economics compare two paths for a skill that cannot complete in
the available runtime:

* With SkillC, an LLM may compact the natural-language skill into a formal
  pack. SkillC checks the pack and rejects the skill before task execution.
* Without SkillC, an agent or subagent attempts the task. It consumes runtime
  tokens until it fails, produces no usable result, or produces a wrong result.

The compaction call and the agent execution call are separate API calls. A real
agent run does not imply that a real compaction call was also made for the same
skill.

## API calls, subagents, and estimates

The experiments contain two distinct kinds of model activity.

### LLM compaction

The compaction model reads a `SKILL.md` file and generates the formal SkillC
pack. A measured compaction value comes from the token-usage block returned by
that API call.

```text
SKILL.md
  -> compaction-model API call
  -> formal SkillC pack
  -> provider-reported compaction tokens
```

An estimated compaction value means that the experiment did not make this
compaction API call for that particular skill. Instead, it predicted the cost
from skill length using a model fitted to separate, real compaction calls:

```text
estimated compaction tokens
  = 17,939 + 0.595 * skill characters
```

### Agent or subagent execution

The runtime experiment asks an agent or subagent to perform the skill. These
are real model API calls, and their provider-reported token usage is measured.

```text
task and skill
  -> agent or subagent API calls
  -> success, failure, no result, or wrong result
  -> provider-reported runtime tokens
```

Therefore, an experiment row can contain:

* measured runtime tokens from real agent or subagent API calls; and
* estimated compaction tokens because no separate compaction API call was made
  for that skill.

> [!IMPORTANT]
> "Estimated compaction" does not mean that no model or API was used anywhere.
> It means that no compaction-model API call was made for that skill. The agent
> or subagent execution can still be real and fully measured.

## What an invocation means

An invocation is one request to execute a skill.

For example, suppose a skill promises to process a spreadsheet:

```text
Invocation 1: one user asks the agent to process a spreadsheet
Invocation 2: another request asks the agent to process a spreadsheet
Invocation 3: the task is requested again
```

Each request is a separate invocation. If the skill is impossible in the
available runtime and there is no pre-execution check, every invocation can
repeat the same failure and consume tokens again.

## Why test one invocation and repeated invocations

Compaction is normally paid once per unchanged skill version. Runtime cost is
paid every time the skill is invoked.

The one-invocation comparison answers:

> Does checking pay for itself even if the skill would be executed only once?

The repeated-invocation comparison answers:

> What happens when the same unchanged skill is requested repeatedly by one or
> more users?

The distinction matters because the compaction cost stays fixed while avoided
runtime waste grows with every prevented execution.

| Invocations of one unchanged skill | With SkillC | Without SkillC |
|---:|---:|---:|
| 1 | Compact once | Pay for one failed execution |
| 2 | Reuse the existing pack | Pay for two failed executions |
| 5 | Reuse the existing pack | Pay for five failed executions |

Five invocations in the September benchmark mean five experimental repetitions
of the same unchanged case. They simulate five separate uses. They do not prove
that five independent users invoked the skill.

## September five-skill benchmark

> [!WARNING]
> The historical simulator described in this section ignored preconditions
> and numeric effects/goals. These outcome and savings figures are not a
> validated comparison under the corrected semantics. See the
> [September 21 correction and accuracy report](BENCHMARK_CORRECTION_20260921.md)
> for regression evidence, a fresh runtime comparison, and the distinction
> between protocol rejection and goal impossibility. Raw historical token
> measurements remain preserved.

The September benchmark contains five natural-language skills and five runtime
trials per skill. Four skills failed in every ungated trial. The web-app testing
skill reported success in all five trials, so it is excluded from the
failure-only comparison.

For one expected invocation of each of the four consistently failing skills:

| Path | Tokens |
|---|---:|
| With SkillC compaction | 22,892 |
| Without SkillC, one failed invocation per skill | 58,333 |
| Tokens avoided | 35,441 |

For this comparison:

```text
with as a share of without = 22,892 / 58,333 = 39.2%
token reduction           = 1 - 39.2%          = 60.8%
runtime-to-check leverage = 58,333 / 22,892    = 2.55x
```

In plain language, checking first uses 39.2% as many tokens as allowing one
failed invocation of each skill. It avoids 60.8% of the token use.

Across all five experimental repetitions per failing skill:

| Path | Tokens |
|---|---:|
| With SkillC, compaction paid once | 22,892 |
| Without SkillC, five failed invocations per skill | 291,667 |
| Tokens avoided | 268,775 |

In this repeated-use comparison, checking first uses 7.8% as many tokens and
avoids 92.2%. The improvement is larger because the pack is reused while the
unchecked failure repeats.

The raw September artifacts are under
[`../runs/20260916_132708Z_real_rejection_benchmark/`](../runs/20260916_132708Z_real_rejection_benchmark/).
That directory is currently a local, uncommitted benchmark artifact and is not
part of the evidence committed with this guide.

## Larger 134-run experiment

The larger experiment is preserved on Git branch `gc/paper-WIP` at commit
`dbb855d1e51c550ce7cdabaf4624e0c2de0325ec`.

It contains 134 measured agent runs. SkillC refuted 66 of those runs:

| Outcome among checker-refuted runs | Runs | Runtime tokens |
|---|---:|---:|
| Verified success on small inputs | 20 | 1,222,156 |
| Honest failure | 30 | 4,640,283 |
| No usable status or result | 9 | 7,628,853 |
| Silently wrong result | 7 | 3,571,970 |
| **Total** | **66** | **17,063,262** |

The 20 verified successes were five small-input configurations repeated four
times. The agent manually computed a correct result despite the unavailable
expected capability. The remaining 46 runs did not produce a correct result:

```text
46 unsuccessful runs
15,841,106 measured runtime tokens
344,372 mean tokens per unsuccessful run
85,218.5 median tokens per unsuccessful run
```

The 344,372 value is the arithmetic mean, not the median. A few very expensive
runs, especially runs with no final status, raise the mean substantially.

The reported 80,331-token median is the median across all 134 agent runs. It is
not the median of the 46 unsuccessful runs.

## Compaction cost for the larger failure set

The 46 unsuccessful runs came from 12 distinct configurations:

* eight natural-language skills that can require LLM compaction; and
* four already-formal benchmark specifications that do not require
  natural-language compaction.

The token-economics result assigns the following compaction costs to the eight
natural-language skills:

| Skill | Compaction tokens | Evidence |
|---|---:|---|
| PDF | 22,011 | Measured compaction API call |
| XLSX | 32,028 | Measured compaction API call |
| DOCX | 22,024 | Estimated from skill length |
| Bulk RNA-seq | 26,596 | Estimated from skill length |
| Data-quality auditor | 23,310 | Estimated from skill length |
| Google Workspace CLI | 25,099 | Estimated from skill length |
| Kubernetes operator | 24,569 | Estimated from skill length |
| Writing skills | 33,558 | Estimated from skill length |
| **Total** | **209,195** | **54,039 measured and 155,156 estimated** |

All 46 unsuccessful agent executions are real runtime measurements. The
compaction side is only partially measured:

```text
measured compaction tokens:   54,039
estimated compaction tokens: 155,156
combined compaction tokens:  209,195
```

Comparing the combined compaction cost with all 46 unsuccessful executions:

```text
with SkillC compaction:       209,195 tokens
without SkillC execution:  15,841,106 tokens
with as a share of without:      1.32%
token reduction:                98.68%
runtime-to-check leverage:       75.7x
```

This is a measured-runtime and partly estimated-compaction comparison. It is
not a fully measured comparison on both sides.

## Fully measured PDF and XLSX comparison

PDF and XLSX are the only two failure-set skills with both:

* a recorded compaction-model API call; and
* recorded unsuccessful agent execution calls.

Each skill was executed four times:

| Skill | One measured compaction | Failed executions | Measured runtime tokens |
|---|---:|---:|---:|
| PDF | 22,011 | 4 | 157,454 |
| XLSX | 32,028 | 4 | 209,766 |
| **Total** | **54,039** | **8** | **367,220** |

Across all eight measured failed executions:

```text
with SkillC compaction:       54,039 tokens
without SkillC execution:   367,220 tokens
with as a share of without:   14.72%
token reduction:              85.28%
runtime-to-check leverage:      6.8x
```

For one expected execution of each skill, use the mean of the four trials:

```text
with SkillC compaction:       54,039 tokens
without SkillC execution:    91,805 tokens
with as a share of without:    58.9%
token reduction:               41.1%
```

The eight-run comparison measures compaction once per skill and reuses it over
four repetitions. The one-execution comparison asks whether compaction pays for
itself on the first use.

## Which comparison to report

Use the comparison that matches the intended claim:

| Intended claim | Appropriate evidence |
|---|---|
| Fully measured cost on both sides | PDF and XLSX: 54,039 versus 367,220 tokens |
| First-use cost on the fully measured subset | PDF and XLSX: 54,039 versus 91,805 tokens |
| Full 46-run failure set | 209,195 versus 15,841,106 tokens, with compaction partly estimated |
| Typical compaction across the broader sample | 22,440-token median over 20 successful compactions |

Do not describe the 22,440-token broader-sample median as the failure-set
median. The mixed measured-and-estimated median for the eight natural-language
failure-set skills is 24,834 tokens. Only two of those eight values are direct
compaction measurements, so it is not a fully measured failure-set median.

## Evidence locations

The larger experiment is available at the following commit-pinned locations:

* [Raw agent executions](https://github.com/ginaecho/skill-achievability-compiler/blob/dbb855d1e51c550ce7cdabaf4624e0c2de0325ec/paper/WIP/results/usefulness_runs.jsonl)
* [Aggregated agent outcomes](https://github.com/ginaecho/skill-achievability-compiler/blob/dbb855d1e51c550ce7cdabaf4624e0c2de0325ec/paper/WIP/results/usefulness.json)
* [Raw compaction calls](https://github.com/ginaecho/skill-achievability-compiler/blob/dbb855d1e51c550ce7cdabaf4624e0c2de0325ec/paper/WIP/results/compaction_runs.jsonl)
* [Combined token analysis](https://github.com/ginaecho/skill-achievability-compiler/blob/dbb855d1e51c550ce7cdabaf4624e0c2de0325ec/paper/WIP/results/token_economics.json)

The current token model and its assumptions are implemented in
[`../src/skillc/tokens.py`](../src/skillc/tokens.py).

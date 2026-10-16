# Token economics: what the check costs, and what it saves

The paper's broader-impact section says pre-execution refutation "can reduce
wasted computation." This document asks two questions: **how many tokens does
checking a skill cost, and how many does an unchecked run of a skill that cannot
succeed spend?** Section 1 answers them by measurement. Sections 2 to 9 are the
cost model in [`src/skillc/tokens.py`](../src/skillc/tokens.py). The model is
kept because its structure is useful, but its figures are predictions, and
section 1 shows that its defaults sit far above what we measured.

---

## 1. Measured

Experiment C of the review-response plan
(`runs/20261015_review_response/PLAN.md`). Real model calls, simulated tool
results grounded in the annotators' verified observations.

**Set.** 62 documents from `benchmark/claude_env/set2`: all 31 whose truth
verdict is BLOCKED, and 31 ACHIEVABLE documents taken in `sha256("cost:"+case)`
order. The texts (sha256), the selection and every prompt were frozen in
`runs/20261015_cost/main/frozen.json` before the first scored call. The truth
labels say whether each hard requirement of a document is available in the
Claude Code cloud session in which annotators probed them. They are not
execution outcomes.

**Runtime.** `claude-code-cloud` (`src/skillc/data/runtimes/claude-code-cloud.json`).
Both arms get this manifest.

**Arm (a), ungated run.** gpt-5.4 is told to carry out what the document is for,
for one representative request that it chooses. The prompt gives it the
manifest's description and tool list. Each turn it outputs one JSON object: a
tool call, or a final status (`achieved`, `blocked` or `impossible`). The limit
is 12 turns; after turn 12 the status is `timeout`. Each turn re-sends the whole
transcript. A deterministic stub (`scripts/measure_cost.py`, class `Stub`)
produces the tool results from the document's truth file:

- An `installable` program is "command not found" until an install command for
  it runs, and is present after that.
- An `unavailable` program fails to install and stays absent.
- A host is answered only if it is on the allow-list or the truth marks it
  available. Otherwise the result is "CONNECT tunnel failed, response 403".
- A credential variable is unset unless the truth marks it present.
- A CLI tied by the truth to an unavailable account or host fails when it runs.
- Docker has no daemon, and there is no GPU.
- Connectors succeed.
- `ask_user` always returns "Use your best judgement; I have nothing to add."
- A program with no truth entry is present. This optimistic default means the
  simulation never adds a blocker that the annotators did not verify.

The stub returns short summaries in place of real program output.

**Arm (b), gated.** One P2g compaction by gpt-5.4 against the same manifest
(`ce_runtime_messages`, plus one `CE_RETRY_PROMPT` round after a parse or gate
error), then `bind_runtime(prune=False)` and `check`. **The checker spends zero
tokens by construction**: no model is in its decision path, so there is nothing
to meter, and we did not measure it.

All token counts are the API's own `usage` block (prompt and completion
tokens). We captured it with `providers.azure_openai_complete` inside
`metered()`. The intervals are percentile bootstraps of the median (2,000
resamples).

### Tokens per document (real model calls, simulated tool results grounded in the annotators' verified observations)

| truth class | arm | input, median [95% CI] | output, median [95% CI] | total, median [95% CI] | turns / calls, median |
|---|---|---|---|---|---|
| BLOCKED (31) | (a) ungated run | 8,862 [6,597, 10,843] | 290 [182, 698] | **9,486** [6,887, 11,554] | 2 turns |
| BLOCKED (31) | (b) compaction + checker | 5,682 [4,452, 7,827] | 639 [558, 877] | **6,289** [4,857, 8,653] | 1 call (+0 checker) |
| ACHIEVABLE (31) | (a) ungated run | 11,456 [9,866, 15,685] | 1,097 [691, 1,657] | **13,121** [10,450, 18,456] | 3 turns |
| ACHIEVABLE (31) | (b) compaction + checker | 4,787 [4,069, 5,037] | 425 [312, 533] | **5,028** [4,600, 5,787] | 1 call (+0 checker) |

**Ratio on BLOCKED documents** (real model calls, simulated tool results
grounded in the annotators' verified observations): (a)/(b) is **1.58x** as the
median of per-document ratios [1.01, 2.11], and **1.51x** as the ratio of
medians [0.96, 1.96]. On the 15 BLOCKED documents that the gate actually
refuted, the median per-document ratio is 1.69x. **The measured ratio is below
the modelled 87x by a factor of about 55 to 58.**

**Overhead on ACHIEVABLE documents** (same label): (b)/(a) is **0.36** as the
median of per-document ratios [0.29, 0.45], and **0.38** as the ratio of
medians [0.25, 0.49]. On a document that works, the check costs about a third
of one ungated run. The model predicts 3 to 4% (section 6).

### How the ungated agent ended (real model calls, simulated tool results grounded in the annotators' verified observations)

| truth class | achieved | blocked | impossible | timeout (12 turns) | agrees with truth |
|---|---|---|---|---|---|
| BLOCKED (31) | **10 (32%): hallucinated completion** | 18 | 3 | 0 | 21 (68%): honest stop |
| ACHIEVABLE (31) | 22 | 7 (false stop) | 0 | 2 | 22 (71%) |

- **Honest stop on BLOCKED documents: 21/31 (68%).** The agent ran into the
  blocker (or saw it in the manifest), reported `blocked` or `impossible`, and
  stopped after a median of 2 turns. No BLOCKED run reached the 12-turn limit
  (the maximum was 7), so the limit did not truncate this class.
- **Hallucinated completion on BLOCKED documents: 10/31 (32%).** The agent
  reported `achieved` on a document whose hard requirement is not available.
  The usual pattern: it wrote the code or configuration and never ran the step
  that needs the missing account or host (c001 Terraform with no
  `terraform validate`, c022 Neon Auth with no Neon account). Their median cost
  was 10,897 tokens. These runs are the silent `GOAL_UNSAT` cost that
  `FailureProfile.silent` describes. The token bill is small; the false claim
  is the expensive part.
- In this run the gate refuted 15/31 BLOCKED documents, and 17/31 ACHIEVABLE
  documents were refuted falsely (2 BLOCKED documents failed to parse after the
  retry). Experiment R measures verdict accuracy, not this experiment. We give
  these counts only so that the token ratio is not read as the value of a
  correct refutation. With `prune=False` and this prompt, the gate is not
  accurate enough to be the reason for stopping a run.

### Measured against the model

For each document we ran `skillc.tokens.economics(text, reason, llm=True)` with
its defaults unchanged. `reason` is the checker's reason, or
`MISSING_CAPABILITY` when the checker did not refute. The table puts the model's
predictions next to the measurements.

| quantity | the model predicts (median) | measured (median) | modelled / measured |
|---|---|---|---|
| wasted run, BLOCKED documents (`waste_typical`) | 217,044 | 9,486 | **22.9x** |
| successful run, ACHIEVABLE documents (`successful_run`, 10 turns) | 77,040 | 13,121 | **5.9x** |
| LLM compaction, BLOCKED documents | 3,950 | 6,289 | 0.63x |
| LLM compaction, ACHIEVABLE documents | 3,613 | 5,028 | 0.72x |
| turns of a doomed run (typical band) | 15 | 2 | 7.5x |
| leverage (wasted run / check), BLOCKED documents | 51x (median per document) | 1.58x | about 32x |

Where the defaults sit against the measured parameters of the ungated runs:

| parameter | model default | measured median (mean) |
|---|---|---|
| `S + K`: first-turn input (harness prompt + document) | 2,500 + skill | 3,073 |
| `g`: input growth per turn | 700 | 242 (424) |
| `o`: output per turn | 250 | 95 (361) |
| turns of a doomed run | 3 to 50 (typical 8 to 25) | 2 (maximum 7) |

The model's main error is the turn count. Its failure profiles assume that an
agent flails for 8 to 25 turns before a structural failure stops it. Under this
protocol gpt-5.4 stopped after a median of 2 turns, or claimed success without
trying the blocked step. The quadratic term the model relies on never had room
to grow. The model also underestimates compaction: P2g's runtime-bound CE prompt
is larger than the JSON prompt the model prices, and 13 of 62 documents needed
the retry round.

### What this does not show

- **Tool results are simulated.** Each stub result is a short summary, while
  real tool output (a file read, a web page, a build log) is often far larger.
  Measured `g` is therefore a lower bound, and a real run of the same length
  would cost more. The stub's optimistic default also means that some runs met
  no blocker that a real environment would have shown.
- **Bounded and single-shot.** One agent, one model (gpt-5.4), one sample per
  document, a 12-turn limit, no human in the loop. A production harness with a
  larger system prompt and tool schemas (often 10K+ tokens) would raise both
  `S` and the per-turn cost of every run.
- **The truth labels are requirement availability, not execution outcomes.**
  An "honest stop" means the agent stopped on a document whose hard requirement
  the annotators found unavailable. It does not mean the agent named that
  requirement.
- **Development.** The stub and the agent prompt were revised four times on
  eight trial documents (`runs/20261015_cost/trial1` to `trial5`), each time
  into a fresh directory, to fix harness bugs: hidden file contents, shell
  operator handling, bundled-script paths and `npx` package names. The scored
  run, `runs/20261015_cost/main`, was prepared once and not changed. The trial
  documents are part of the scored set.

Reproduce (the model calls need Azure OpenAI access):

```console
$ python scripts/measure_cost.py prepare runs/20261015_cost/<new-dir>
$ python scripts/measure_cost.py run     runs/20261015_cost/<new-dir>
$ python scripts/measure_cost.py score   runs/20261015_cost/<new-dir>   # deterministic
```

`results.json` holds the per-document rows; `metrics.json` holds the medians,
intervals and rates; `ungated/*.json` and `gated/*.json` hold every prompt hash,
reply, tool call, stub result and usage block.

---

# A model, not a measurement

Everything below is the cost model in
[`src/skillc/tokens.py`](../src/skillc/tokens.py), unchanged. Its runtime-waste
figures are **predictions of a parameterized model**. Section 1 shows that they
sit one to two orders of magnitude above what we measured. Read every waste
figure, leverage and break-even below as "the model predicts". Every rendered
`Cost` carries its basis (`modelled`, `measured`, or `zero by construction`).

```console
$ skillc cost --corpus                 # the 15-spec evaluation corpus (modelled)
$ skillc cost --corpus --price-llm     # priced against the LLM front-end (modelled)
$ skillc cost /mnt/skills --profile claude-code --json
```

## 2. Where the tokens go

| stage | tokens | paid |
|---|---|---|
| deterministic markdown front-end | **0** | per skill |
| LLM compaction (`--llm`) | system prompt + skill + emitted pack | per skill *version* |
| schema gate | **0** | per check |
| **trusted checker** (projection, conformance, z3) | **0** | per check |
| Coq metatheory (T1–T3, SR, fidelity) | **0** | **once, ever** |
| an agent run — *the thing being avoided* | quadratic in turns | **per invocation** |

The headline fact is the one that is easy to miss: **the trusted core spends
no tokens at all.** No model sits in the decision path, by construction — that
is the same design choice that makes an `IMPOSSIBLE` verdict a proof rather
than an opinion. So the entire token cost of a check is its *front-end's*, and
the deterministic front-end's is zero too.

The LLM compaction front-end is the only stage that spends tokens, and it is
optional, one-shot, and untrusted.

## 3. Why a doomed run is expensive: the quadratic term

An agent turn re-sends the whole conversation. Writing `S` for the harness
prompt (system prompt + tool schemas), `K` for the skill loaded into context,
`g` for the mean tokens appended per turn, and `o` for the assistant's output
per turn, a run of `T` turns reads

```
input  =  T·(S + K)  +  g · T(T−1)/2
output =  T·o
```

The marginal cost of turn `T` is `S + K + (T−1)·g`, so in the model a run that
flails for 40 turns costs far more than four runs that flail for 10. Measured
runs (section 1) stopped after a median of 2 turns, so the quadratic term had
little room to grow. Compaction, by
contrast, reads the skill exactly once, so its cost is *linear* in the skill's
length. Static refutation deletes the whole run — quadratic term included.

Defaults, chosen to be conservative: `S = 2,500`, `g = 700`, `o = 250`, and
`K` = the skill's own token count. Section 1 measured `g` at a median of 242
and `o` at 95, under simulated tool results that understate real output.

Prompt caching changes the **price** of the wasted tokens, not their
**number**: a cached prefix is still read, just billed at a discount. `skillc
cost --cache-hit-rate 0.9` shows the discounted dollars; the token counts do
not move.

## 4. What each refutation reason prevents

In the model, each verdict reason maps to a distinct flailing profile: how
long an agent runs before that structural failure stops it, and how many agents
are billed for it. The turn bands are engineering judgement, not measurements;
section 1 measured a median of 2 turns. Numbers below are for `call-to-book`, a median-sized real
consumer skill (≈1.1K tokens), priced against the LLM front-end with the
*modelled* compaction cost (`skillc cost --price-llm`; the figure moves with
the prompt and the skill text, so re-run it after either changes).

| reason | modelled turns (lo–typ–hi) | agents | modelled waste per run (typical) | modelled check | modelled leverage |
|---|---|---|---|---|---|
| `MISSING_CAPABILITY` | 3–8–14 | 1 | 50,240 | 2,889 | **17×** |
| `GOAL_UNSAT` | 8–18–30 | 1 | 176,040 | 2,889 | **61×** |
| `NON_CONFORMANT` | 6–15–30 | 2 | 261,900 | 2,889 | **91×** |
| `NON_PROJECTABLE` | 6–15–30 | 2 | 261,900 | 2,889 | **91×** |
| `BLOCKED_GUARD` | 12–25–50 | 1 | 305,750 | 2,889 | **106×** |

The model's ordering of the reasons is argued below. It has not been measured
per reason:

* **`MISSING_CAPABILITY` is the cheapest** to hit at run time — the agent
  calls a tool that is not there and finds out immediately. Most of its cost
  is the *improvisation* that follows, not the error itself.
* **`BLOCKED_GUARD` is the most expensive.** A precondition no run can satisfy
  is the retry-forever cause: the model assumes the agent has no way to
  *learn* that the guard is unsatisfiable, so it runs to the harness turn cap. This is exactly the
  failure mode a static checker is best at and an agent is worst at.
* **The two multi-party reasons bill two contexts.** A deadlocked handoff
  leaves both agents holding full context and waiting until a timeout.
* **`GOAL_UNSAT` has a cost the token bill does not show.** When a goal
  conjunct has no establisher, the run can terminate *believing it succeeded*
  (`FailureProfile.silent`). The tokens are the small part; the trust is the
  large part.

`DYNAMIC_TOPOLOGY` deliberately has **no** profile. `UNKNOWN` is an
abstention, not a refutation — nothing was prevented, so there is no avoided
waste to claim.

## 5. Break-even

Verification is paid **once per skill version**, at authoring time. Waste is
paid **on every invocation**, by every user. So the question is not "does the
check pay for itself?" but "how far into the *first* prevented run?"

| front-end | tokens per skill | break-even |
|---|---|---|
| deterministic | 0 | immediate — there is nothing to repay |
| LLM compaction | ~2,900 (modelled) | the model predicts **0.9%–5.8% of one prevented run** |

The model predicts that even in the cheapest failure mode (`MISSING_CAPABILITY`)
the check repays itself before 6% of the first doomed run has elapsed, and in
the retry-forever case before 1%. **Measured** (section 1, real model calls,
simulated tool results grounded in the annotators' verified observations): the
LLM check cost about two thirds of the doomed run it replaces (ratio 1.5x), so
it repays itself only after most of the first prevented run, not after a few
percent of it.

## 6. What it costs when the skill is fine

The honest denominator. Most skills are *not* broken, and for those the check
buys nothing and still costs something. So: **how much is that?**

For a median real skill, the model predicts LLM compaction at ≈2,900 tokens
against a 10-turn successful run of ≈69,800, so the check would be 4.1% of
running the skill once. Over the 15-spec corpus (whose natural-language sources
are short) the model predicts 3.1%. **Measured** (section 1, real model calls,
simulated tool results grounded in the annotators' verified observations): the
P2g check is **36%** of one ungated run of an ACHIEVABLE document (median per
document [29%, 45%]).

With the deterministic front-end it is **0.0%**, exactly.

The model's version of the trade is a one-time 3–4% surcharge on skills that
work, in exchange for deleting whole runs of the ones that do not. The measured
version is a surcharge of about a third of one run, in exchange for runs that
cost about 1.5 times the check. The deterministic front-end has no surcharge at
all.

## 7. Corpus results

Every waste and leverage figure in these outputs is **modelled** (section 1
shows how far the defaults sit from measurement). The "tokens spent checking"
lines are modelled too, unless the run used `--llm`.

### The 15-spec evaluation corpus (`skillc cost --corpus --price-llm`)

```
refuted 7 skill(s) before execution
  tokens spent checking : 13,016 ($0.0936)
  tokens NOT wasted     : 1,067,913 typical ($3.5787), band 281,547-3,146,804
  leverage (typical)    : 82.0x, per invocation avoided

8 skill(s) not refuted -- the check bought no savings, so this is what it cost them:
  tokens spent checking : 14,900
  one successful run    : 476,280 (modelled)
  checking is 3.1% of running each skill once
```

With the deterministic front-end the same seven refutations cost **0 tokens**.

This snapshot predates verdict schema v2. One of the seven,
`deadlock_unobserved`, is now reported as a protocol rejection, not a goal
refutation: its goal is reachable along the `direct` branch, but the
coordination can deadlock. It is still priced with the `NON_PROJECTABLE`
failure profile, so the totals do not change. `skillc cost` now prints
`stopped 7 skill(s) before execution: 6 goal refutation(s), 1 protocol
rejection(s)`. See [verdict coverage](VERDICT_COVERAGE.md).

### 42 real public skills under `claude-code` (`skillc cost /mnt/skills --profile claude-code`)

The public skills repository grows, so these counts are a snapshot (42 skills
at the time of writing).

```
refuted 18 skill(s) before execution
  tokens spent checking : 0 ($0.0000)
  tokens NOT wasted     : 1,039,720 typical ($3.5512), band 295,395-2,348,710
  leverage (typical)    : unbounded -- the check spends no tokens at all
```

Those eighteen are the skills that invoke tools the default Claude Code
toolset does not grant (consumer-app tools, and the browser tools of the two
browser skills). Each would fail on its first invocation under that profile; the
deterministic front-end names the missing tool and the source line for free.

## 8. What is measured and what is modelled

This matters more than the numbers.

**Measured.** Compaction usage, when a live API call reports it. Every
provider call made inside `frontend.llm.metered()` records the API's own
`usage` block; `skillc cost --llm` compacts each skill that way and prices
exactly that usage (`Cost.measured` is `True`, and the report says
"measured"). `compact_with_repair_measured` does the same across the repair
round. Where no call reported usage (`--price-llm`, `--corpus`, or JSON packs),
the cost is modelled and labelled so. Nothing else in the pipeline has anything
to measure — it spends no tokens.

**Modelled.** Runtime waste, in `skillc cost`. It is the cost of a run that,
if the refutation is correct, *never happens*, so in production it cannot be
measured, only estimated. Section 1 measures it in a bounded simulation
instead (real model calls, simulated tool results grounded in the annotators'
verified observations), and finds the model's typical waste 23 times the
measured median. It is reported as a low/typical/high band, produced by an explicit
parameterized model with published defaults, and every parameter is
overridable. `skillc cost` prints the caveat on every invocation.

**Heuristic.** Token counts from `estimate_tokens` use a 3.8 chars/token
ratio, not a tokenizer. `count_tokens_exact` upgrades them to real counts when
`ANTHROPIC_API_KEY` is set, and refuses rather than silently estimating when
it is not.

The model predicts that halving every waste default still leaves leverage of
9× to 55×. The measured leverage of the LLM check was 1.5×, so the size of the
saving does rest on the parameterization, above all on the turn counts.
Structurally, compaction is still paid once per skill version while a doomed
run recurs on every invocation, and with the deterministic front-end the check
costs zero tokens, so any avoided run is a net saving.

## 9. The proof's amortization

The Coq development costs zero tokens and is paid **once for the entire
system**, not once per skill. T1 is what licenses acting on a refutation
without re-litigating it: the theorem is proved once, and every `IMPOSSIBLE`
verdict thereafter inherits it. Under any usage at all, its amortized
per-skill cost rounds to zero.

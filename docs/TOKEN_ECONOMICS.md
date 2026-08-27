# Token economics: what the check costs, and what it saves

The paper's broader-impact section says pre-execution refutation "can reduce
wasted computation." This document turns that sentence into arithmetic:
**how many tokens does checking a skill cost, and how many does an unrefuted
impossible skill burn at run time?**

Everything here is reproducible:

```console
$ skillc cost --corpus                 # the 15-spec evaluation corpus
$ skillc cost --corpus --price-llm     # priced against the LLM front-end
$ skillc cost /mnt/skills --profile claude-code --json
```

The model lives in [`src/skillc/tokens.py`](../src/skillc/tokens.py); every
parameter is overridable and every default is justified in that file's
docstrings.

---

## 1. Where the tokens go

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

## 2. Why a doomed run is expensive: the quadratic term

An agent turn re-sends the whole conversation. Writing `S` for the harness
prompt (system prompt + tool schemas), `K` for the skill loaded into context,
`g` for the mean tokens appended per turn, and `o` for the assistant's output
per turn, a run of `T` turns reads

```
input  =  T·(S + K)  +  g · T(T−1)/2
output =  T·o
```

The marginal cost of turn `T` is `S + K + (T−1)·g`. **A run that flails for 40
turns costs far more than four runs that flail for 10.** Compaction, by
contrast, reads the skill exactly once, so its cost is *linear* in the skill's
length. Static refutation deletes the whole run — quadratic term included.

Defaults (deliberately conservative — they understate the waste):
`S = 2,500`, `g = 700`, `o = 250`, `K` = the skill's own token count.

Prompt caching changes the **price** of the wasted tokens, not their
**number**: a cached prefix is still read, just billed at a discount. `skillc
cost --cache-hit-rate 0.9` shows the discounted dollars; the token counts do
not move.

## 3. What each refutation reason prevents

Each verdict reason maps to a distinct flailing profile — how long an agent
runs before that particular structural failure stops it, and how many agents
are billed for it. Numbers below are for `call-to-book`, a median-sized real
consumer skill (≈1.7K tokens), priced against the LLM front-end.

| reason | turns (lo–typ–hi) | agents | wasted per run (typical) | check | leverage |
|---|---|---|---|---|---|
| `MISSING_CAPABILITY` | 3–8–14 | 1 | 50,240 | 2,778 | **18×** |
| `GOAL_UNSAT` | 8–18–30 | 1 | 176,040 | 2,778 | **63×** |
| `NON_CONFORMANT` | 6–15–30 | 2 | 261,900 | 2,778 | **94×** |
| `NON_PROJECTABLE` | 6–15–30 | 2 | 261,900 | 2,778 | **94×** |
| `BLOCKED_GUARD` | 12–25–50 | 1 | 305,750 | 2,778 | **110×** |

The ordering is the robust part, and it is not arbitrary:

* **`MISSING_CAPABILITY` is the cheapest** to hit at run time — the agent
  calls a tool that is not there and finds out immediately. Most of its cost
  is the *improvisation* that follows, not the error itself.
* **`BLOCKED_GUARD` is the most expensive.** A precondition no run can satisfy
  is the retry-forever cause: the agent has no way to *learn* that the guard
  is unsatisfiable, so it runs to the harness turn cap. This is exactly the
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

## 4. Break-even

Verification is paid **once per skill version**, at authoring time. Waste is
paid **on every invocation**, by every user. So the question is not "does the
check pay for itself?" but "how far into the *first* prevented run?"

| front-end | tokens per skill | break-even |
|---|---|---|
| deterministic | 0 | immediate — there is nothing to repay |
| LLM compaction | ~2,800 | **0.9%–5.5% of one prevented run** |

Even in the cheapest failure mode (`MISSING_CAPABILITY`), the check has repaid
itself before 6% of the first doomed run has elapsed. In the retry-forever
case it repays in under 1%.

## 5. What it costs when the skill is fine

The honest denominator. Most skills are *not* broken, and for those the check
buys nothing and still costs something. So: **how much is that?**

For a median real skill, LLM compaction is ≈2,800 tokens against a modelled
10-turn successful run of ≈69,800 — **the check is 4.0% of running the skill
once.** Over the 15-spec corpus (whose natural-language sources are short) the
same figure is **2.9%**.

With the deterministic front-end it is **0.0%**, exactly.

That is the trade in one line: **a one-time 3–4% surcharge on skills that
work, in exchange for deleting entire runs of the ones that don't** — or no
surcharge at all if you use the deterministic front-end.

## 6. Corpus results

### The 15-spec evaluation corpus (`skillc cost --corpus --price-llm`)

```
refuted 7 skill(s) before execution
  tokens spent checking : 12,239        ($0.09)
  tokens NOT wasted     : 1,067,913 typical ($3.58), band 281,547–3,146,804
  leverage (typical)    : 87×, per invocation avoided

8 skill(s) not refuted — the check bought no savings, so this is what it cost:
  tokens spent checking : 14,012
  one successful run    : 476,280 (modelled)
  checking is 2.9% of running each skill once
```

With the deterministic front-end the same seven refutations cost **0 tokens**.

### 36 real public skills under `claude-code` (`skillc cost /mnt/skills --profile claude-code`)

```
refuted 16 skill(s) before execution
  tokens spent checking : 0
  tokens NOT wasted     : 930,384 typical, band 264,894–2,098,572
  leverage (typical)    : unbounded — the check spends no tokens at all
```

Those sixteen are the consumer-app skills that invoke tools Claude Code does
not grant. Each would fail on its first invocation under that profile; the
deterministic front-end names the missing tool and the source line for free.

## 7. What is measured and what is modelled

This matters more than the numbers.

**Measured.** Compaction usage, when a live API call reports it.
`frontend.llm.compact_measured` returns the API's own `usage` block and
`Cost.measured` is `True`. Nothing else in the pipeline has anything to
measure — it spends no tokens.

**Modelled.** Runtime waste, always. It is the cost of a run that, if the
refutation is correct, *never happens* — so it cannot be measured, only
estimated. It is reported as a low/typical/high band, produced by an explicit
parameterized model with published defaults, and every parameter is
overridable. `skillc cost` prints the caveat on every invocation.

**Heuristic.** Token counts from `estimate_tokens` use a 3.8 chars/token
ratio, not a tokenizer. `count_tokens_exact` upgrades them to real counts when
`ANTHROPIC_API_KEY` is set, and refuses rather than silently estimating when
it is not.

The conclusion does not rest on the parameterization. Compaction is linear and
one-shot; a run is quadratic and recurs. Halve every waste default and the
leverage is still 9×–55×; the ordering of the failure modes does not move at
all.

## 8. The proof's amortization

The Coq development costs zero tokens and is paid **once for the entire
system**, not once per skill. T1 is what licenses acting on a refutation
without re-litigating it: the theorem is proved once, and every `IMPOSSIBLE`
verdict thereafter inherits it. Under any usage at all, its amortized
per-skill cost rounds to zero.

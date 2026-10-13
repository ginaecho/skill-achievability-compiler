# Tiered compaction: deterministic first, LLM only when needed

Question: if SkillC runs the rule-based front-end first and calls the LLM only on some inputs,
how much accuracy does it lose, and how many LLM calls and tokens does it save?

Everything here is computed offline from four result files that already exist. No LLM was
called and nothing in `src/` was changed. Reproduce with:

```
python scripts/compaction_tiering.py --data-root <gc/data_train_test checkout> --json OUT.json
```

`--data-root` is only used to read the source text lengths for the token estimate.

## Method

**Inputs.**

| Benchmark | Rule-based file | gpt-5.4 file | Rows used |
|---|---|---|---:|
| Labelled topics | `benchmark-results.json` | `benchmark-results-llm.json` | 396 (join on `id`; 345 labelled) |
| Real public files | `real-benchmark-results.json` | `real-benchmark-results-llm.json` | 429 (the balanced subset) |

**Tiers** (rule = rule-based verdict, llm = gpt-5.4 verdict, chosen per input):

| Tier | Rule |
|---|---|
| T0 | rule only |
| T1 | LLM only when rule is UNKNOWN (or ERROR), else keep rule |
| T2 | keep rule IMPOSSIBLE, LLM otherwise |
| T3 | keep rule IMPOSSIBLE, keep rule ACHIEVABLE when its `goal_source` is not `tool_usage_only`, LLM otherwise |
| T4 | LLM always (= pure gpt-5.4) |
| oracle | per row, whichever mode is right (upper bound, not a policy) |

**Metrics** follow `docs/BENCHMARK_REPORT.md` exactly. Positive = IMPOSSIBLE.
False alarm rate = FP / (FP + TN), over truly-ACHIEVABLE inputs that got a verdict.
Precision = TP / (TP + FP). Recall = TP / all truly-IMPOSSIBLE inputs, so an UNKNOWN on an
impossible input is a miss. Accuracy = correct / inputs where a verdict was given.
Gave a verdict = share of labelled inputs not answered UNKNOWN (or ERROR).

**Assumptions.**

1. *LLM calls* are counted over every input in the join (396 and 429), not only the labelled
   345, because a deployed policy would see all of them. Metrics use the 345 labelled inputs.
   One input is one LLM compaction call.
2. *Tokens* are an estimate. The result files carry no per-row usage (there is no `usage`
   field), so measured usage is not available. Each LLM call is priced with
   `skillc.tokens.compaction_cost(source_text, pack=gpt-5.4 pack)` with zero repair rounds:
   system prompt (1,159 tokens) plus the source text at 3.8 characters per token, plus the
   stored gpt-5.4 pack as output. Source text was read from the `gc/data_train_test`
   checkout. This is a lower bound: repair rounds and the explanation call are not included.
   Mean cost is 1,483 tokens per labelled input and 3,660 per real file. Quote it to two
   significant figures.
3. *Real files have no answer key.* False alarm rate, recall and accuracy cannot be computed
   there. The only ground truth is the hand audit of IMPOSSIBLE verdicts (`audit` =
   confirmed, false_refutation, or unaudited). A tier's IMPOSSIBLE verdict carries the audit
   of the mode that supplied it. "Audited precision" = confirmed / (confirmed + false); it
   leaves the unaudited ones out, so it is neither a lower nor an upper bound.
4. Real files use the `home` environment verdict, as the report does (`--env observed` gives
   the other view). Rows are joined on (kind, id): the id alone is not unique, since the same
   upstream name exists as both an agent and a prompt.
5. The stored result files predate the 2026-10-06 change that moved one skill and one agent
   from IMPOSSIBLE to UNKNOWN, so gpt-5.4 shows one more unaudited IMPOSSIBLE for each than
   the report prints. The report says this itself.
6. T3 needs a rule verdict with a semantic `goal_source`. In both rule-based files every
   row has `goal_source = tool_usage_only` (396 of 396 and 429 of 429), so the T3 condition
   never fires and **T3 is identical to T2** here. Making T3 useful needs a rule front-end
   that can read a goal.
7. A tier uses the stored verdicts only. There are no repairs, and there is no fallback from
   an LLM ERROR back to the rule verdict (4 real rows are ERROR in T4; in T1 to T3 they stay
   ERROR if the LLM was called on them).

## Sanity check: the two pure modes against the report

| Quantity (labelled, 345) | Report | Reproduced |
|---|---|---|
| Rule: false alarm rate | 0% (0 of 136) | 0.0% (0 of 136) |
| Rule: precision | 100% (36 of 36) | 100.0% (36 of 36) |
| Rule: recall | 19% (36 of 189) | 19.0% (36 of 189) |
| Rule: accuracy | 56% | 56.4% (172 of 305) |
| Rule: gave a verdict | 88% | 88.4% (305 of 345) |
| gpt-5.4: false alarm rate | 2.0% (3 of 149) | 2.0% (3 of 149) |
| gpt-5.4: precision | 98% (149 of 152) | 98.0% (149 of 152) |
| gpt-5.4: recall | 79% (149 of 189) | 78.8% (149 of 189) |
| gpt-5.4: accuracy | 89% | 88.6% (295 of 333) |
| gpt-5.4: gave a verdict | 97% | 96.5% (333 of 345) |

The confusion matrices match too: rule 36 / 133 / 20 on impossible and 0 / 136 / 20 on
achievable; gpt-5.4 149 / 35 / 5 and 3 / 146 / 7.

Real files, IMPOSSIBLE verdicts, home environment (confirmed / audited wrong / unaudited):

| Form | Mode | Report | Reproduced |
|---|---|---|---|
| Skills | rule | 5 of 10 | 10 verdicts: 5 / 5 / 0 |
| Agents | rule | 22 of 24 | 24 verdicts: 22 / 2 / 0 |
| Prompts | rule | 5 of 5 | 5 verdicts: 5 / 0 / 0 |
| Skills | gpt-5.4 | 6 of 9, plus 12 unchecked | 22 verdicts: 6 / 3 / 13 (report: 21, one fewer unaudited) |
| Agents | gpt-5.4 | 58 of 76, plus 7 unchecked | 84 verdicts: 58 / 18 / 8 (report: 83, one fewer unaudited) |
| Prompts | gpt-5.4 | 15 of 25, plus 9 unchecked | 34 verdicts: 15 / 10 / 9 |

The rule-mode verdict counts on the 429 files also match the report (skills 41 / 10 / 92,
agents 27 / 24 / 92, prompts 27 / 5 / 111 for ACHIEVABLE / IMPOSSIBLE / UNKNOWN).

## Labelled topics (396 inputs, 345 labelled)

| tier | LLM calls (n, %) | false alarm rate | precision | recall | accuracy | gave a verdict | est. tokens |
|---|---:|---:|---:|---:|---:|---:|---:|
| T0 rule only | 0 (0.0%) | 0.0% (0 of 136) | 100.0% (36 of 36) | 19.0% (36 of 189) | 56.4% (172 of 305) | 88.4% (305 of 345) | 0 |
| T1 LLM if rule UNKNOWN | 46 (11.6%) | 0.6% (1 of 154) | 98.1% (53 of 54) | 28.0% (53 of 189) | 60.1% (206 of 343) | 99.4% (343 of 345) | 67,955 |
| T2 keep rule IMPOSSIBLE | 360 (90.9%) | 2.0% (3 of 149) | 98.0% (149 of 152) | 78.8% (149 of 189) | 88.6% (295 of 333) | 96.5% (333 of 345) | 533,561 |
| T3 keep rule IMPOSSIBLE + semantic ACHIEVABLE (= T2, assumption 6) | 360 (90.9%) | 2.0% (3 of 149) | 98.0% (149 of 152) | 78.8% (149 of 189) | 88.6% (295 of 333) | 96.5% (333 of 345) | 533,561 |
| T4 LLM always | 396 (100.0%) | 2.0% (3 of 149) | 98.0% (149 of 152) | 78.8% (149 of 189) | 88.6% (295 of 333) | 96.5% (333 of 345) | 587,262 |
| oracle (best of both per row) | - | 0.6% (1 of 154) | 99.3% (149 of 150) | 78.8% (149 of 189) | 89.3% (302 of 338) | 98.0% (338 of 345) | - |

Token savings against T4 (587,262): T1 saves 519,307 (88.4%); T2 and T3 save 53,701 (9.1%).

Oracle headroom is small. Of the 345 labelled inputs, both modes are right on 165, only
gpt-5.4 on 130, only the rule mode on 7, and neither on 43. Picking the better mode per row
adds those 7 (accuracy 88.6% to 89.3%) and removes 2 of the 3 false alarms. The oracle still
has 1 false alarm, because on that input the rule mode abstained. Recall does not move: the
43 "neither" rows are the real ceiling.

## Real public files (429 files, home environment)

| tier | LLM calls (n, %) | IMPOSSIBLE verdicts (confirmed / false / unaudited) | audited precision | ACHIEVABLE | UNKNOWN+ERROR | gave a verdict | est. tokens |
|---|---:|---:|---:|---:|---:|---:|---:|
| T0 rule only | 0 (0.0%) | 39 (32 / 7 / 0) | 82.1% (32 of 39) | 95 | 295 | 31.2% (134 of 429) | 0 |
| T1 LLM if rule UNKNOWN | 295 (68.8%) | 124 (72 / 30 / 22) | 70.6% (72 of 102) | 253 | 52 | 87.9% (377 of 429) | 1,019,243 |
| T2 keep rule IMPOSSIBLE | 390 (90.9%) | 149 (83 / 37 / 29) | 69.2% (83 of 120) | 213 | 67 | 84.4% (362 of 429) | 1,415,322 |
| T3 keep rule IMPOSSIBLE + semantic ACHIEVABLE (= T2) | 390 (90.9%) | 149 (83 / 37 / 29) | 69.2% (83 of 120) | 213 | 67 | 84.4% (362 of 429) | 1,415,322 |
| T4 LLM always | 429 (100.0%) | 140 (79 / 31 / 30) | 71.8% (79 of 110) | 217 | 72 | 83.2% (357 of 429) | 1,570,222 |
| audit oracle (avoid false refutations, prefer confirmed IMPOSSIBLE) | - | 105 (83 / 0 / 22) | 100.0% (83 of 83) | 246 | 78 | 81.8% (351 of 429) | - |

There is no false alarm rate, recall or accuracy here, because there is no answer key
(assumption 3). The number of audited-wrong IMPOSSIBLE verdicts ("false") is the closest
measure of false alarms. The audit oracle is a heuristic upper bound: it knows the audit
labels, so treat it as a ceiling on mode selection, not a target.

Token savings against T4 (1,570,222): T1 saves 550,979 (35.1%); T2 and T3 save 154,900
(9.9%). T1 skips 31.2% of the calls but 35.1% of the tokens, because the files the rule mode
can read are longer on average than those it cannot.

## Disagreement analysis

### Labelled topics: 146 of 345 labelled inputs disagree

| rule | gpt-5.4 | truth | n |
|---|---|---|---:|
| ACHIEVABLE | IMPOSSIBLE | IMPOSSIBLE | 96 |
| UNKNOWN | IMPOSSIBLE | IMPOSSIBLE | 17 |
| UNKNOWN | ACHIEVABLE | ACHIEVABLE | 17 |
| ACHIEVABLE | UNKNOWN | ACHIEVABLE | 5 |
| ACHIEVABLE | UNKNOWN | IMPOSSIBLE | 5 |
| UNKNOWN | ACHIEVABLE | IMPOSSIBLE | 3 |
| ACHIEVABLE | IMPOSSIBLE | ACHIEVABLE | 2 |
| UNKNOWN | IMPOSSIBLE | ACHIEVABLE | 1 |

By form. All 345 labelled inputs are in the "Topics" suite, so the suite breakdown is one row.

| input_type | labelled | disagree | rule right | gpt-5.4 right | neither |
|---|---:|---:|---:|---:|---:|
| agent | 115 | 60 | 2 | 53 | 5 |
| prompt | 115 | 49 | 1 | 48 | 0 |
| skill | 115 | 37 | 4 | 29 | 4 |
| Topics (all) | 345 | 146 | 7 | 130 | 9 |

The rule mode is right on only 7 of the 146 disagreements. In 113 of them (96 ACHIEVABLE,
17 UNKNOWN) the rule mode missed an impossible input that gpt-5.4 caught. The rule mode never
contradicts gpt-5.4 when it says IMPOSSIBLE: all 36 of its IMPOSSIBLE verdicts are also
gpt-5.4 IMPOSSIBLE, and correct. That is why T2 loses nothing here.

The 3 gpt-5.4 false alarms, and what the rule mode said:

| Input | Form | Rule-based said | gpt-5.4 said |
|---|---|---|---|
| topic:n1-itinerary-routing:agent (Route an itinerary booking) | agent | UNKNOWN (INCOMPLETE_COMPACTION) | IMPOSSIBLE (NON_CONFORMANT) |
| topic:n2-card-dispute-triage:skill (Card dispute triage) | skill | ACHIEVABLE (OK) | IMPOSSIBLE (NON_CONFORMANT) |
| topic:n6-return-label-retry:prompt (named "Return label detail loop" in the file; "Return label retry" in the report) | prompt | ACHIEVABLE (OK) | IMPOSSIBLE (NON_PROJECTABLE) |

On two of the three the rule mode was right (ACHIEVABLE), but only by default: it gave the
same answer on 96 impossible inputs, so a tier cannot use its ACHIEVABLE as a veto against the
LLM. On the third it abstained.

What the cheaper tiers lose against T4 on the labelled set: T1 gets 96 inputs wrong that T4
gets right. All 96 are impossible inputs that the rule mode called ACHIEVABLE (agent 27,
prompt 42, skill 27). T2 and T3 lose none.

### Real files: 294 of 429 disagree

| rule | gpt-5.4 | audit of the gpt-5.4 IMPOSSIBLE | n |
|---|---|---|---:|
| UNKNOWN | ACHIEVABLE | - | 158 |
| UNKNOWN | IMPOSSIBLE | confirmed | 40 |
| UNKNOWN | IMPOSSIBLE | false_refutation | 23 |
| UNKNOWN | IMPOSSIBLE | unaudited | 22 |
| ACHIEVABLE | UNKNOWN | - | 14 |
| ACHIEVABLE | IMPOSSIBLE | confirmed | 11 |
| ACHIEVABLE | IMPOSSIBLE | false_refutation | 7 |
| ACHIEVABLE | IMPOSSIBLE | unaudited | 7 |
| IMPOSSIBLE | UNKNOWN | - | 4 |
| IMPOSSIBLE | ACHIEVABLE | - | 4 |
| UNKNOWN | ERROR | - | 2 |
| IMPOSSIBLE | ERROR | - | 1 |
| ACHIEVABLE | ERROR | - | 1 |

The premise of T2 ("the rule mode is 100% precise when it says IMPOSSIBLE") does not hold on
real files: of its 39 IMPOSSIBLE verdicts, 32 are confirmed and 7 are false refutations
(82.1%). gpt-5.4 agrees on 30 of the 39 (28 confirmed by both audits, 1 where only the rule
verdict was confirmed and the gpt-5.4 one was a false refutation, 1 where gpt-5.4's was
unaudited). On the 9 where they differ:

- 7 rule verdicts were false refutations. gpt-5.4 said UNKNOWN on 3 and ACHIEVABLE on 4, so the
  LLM was the better judge.
- 2 rule verdicts were confirmed. gpt-5.4 said UNKNOWN on one and ERROR on the other.

So keeping the rule IMPOSSIBLE (T2) rather than asking the LLM (T4) on real files costs 6
extra audited-wrong verdicts (37 vs 31) and gains 4 confirmed ones (83 vs 79). The 29 to 30
unaudited gpt-5.4 IMPOSSIBLE verdicts could shift any audited precision above by a few points.

## Conclusions

**(a) Does deterministic-first compaction lose accuracy, and where?**

It depends on which rule verdicts are trusted. On the labelled topics, keeping the rule
mode's IMPOSSIBLE verdicts (T2) loses nothing: all 36 agree with gpt-5.4 and are correct, so
T2 has the same 88.6% accuracy, 78.8% recall and 2.0% false alarm rate as T4, with 36 fewer
calls. Every loss comes from trusting the rule mode where it does not say IMPOSSIBLE. T1 (use
the rule mode unless it is UNKNOWN) cuts calls and tokens by 88%, but recall falls from 78.8%
to 28.0% and accuracy from 88.6% to 60.1%. The rule mode reads a tool list and no goal, so it
says ACHIEVABLE on 133 of the 189 impossible inputs, in all three forms. The oracle shows
little complementary signal: only 7 labelled inputs are right in the rule mode and wrong in
gpt-5.4, and they cannot be told apart from the 96 where the rule mode's ACHIEVABLE is wrong.
T3 cannot help yet, because the rule mode never produces a semantic goal (every row is
`tool_usage_only`).

On real files the cheap tiers cost in a different way, since recall cannot be measured. T1
raises the share of files that get a verdict from 31.2% to 87.9%, but false refutations go
from 7 to 30 (both are the raw audited-wrong counts). T2 is not safer there: the rule mode's
IMPOSSIBLE is only 82% precise on real files (7 of 39 wrong), mostly where a real file uses a
tool name that is not in the documented list. gpt-5.4 did not call any of those 7 IMPOSSIBLE (UNKNOWN or
ACHIEVABLE).

**(b) Recommended tier.**

T2: run the rule front-end first, and send every input it does not call IMPOSSIBLE to the
LLM. It is lossless on the labelled topics and saves 9.1% of LLM calls and tokens there (36
calls, about 54k tokens). On real public files it saves 9.9% (39 calls, about 155k tokens),
but it is not lossless: it keeps 7 rule false refutations that the LLM would have avoided. If
false IMPOSSIBLE verdicts matter more than about 10% of the cost, send those 39 to the LLM
too, which is T4. The large savings of T1 (35% to 88% of tokens) are not worth it, because of
the recall and accuracy it gives up. T3 becomes a real option only once the rule front-end can
read a goal.

**Limits.** The token numbers are modelled estimates (no measured usage in the files, no
repair rounds). The real-file results rest on a hand audit that covers only IMPOSSIBLE
verdicts and leaves 30 of the gpt-5.4 ones unchecked. The numbers inherit the report's caveat
that SkillC was tuned while looking at these same results.

**Implemented.** T2 ships as `skillc check|compile|scan|cost --llm --llm-when needed`
(default `always`, which keeps the old behaviour). The deterministic front-end runs first;
a definite IMPOSSIBLE is returned without calling the LLM, an error falls back to the LLM,
and every verdict carries `front_end: "deterministic" | "llm"`. `scan` prints "LLM calls: k
of n (saved m)". The tool-policy library veto is not part of the CLI check path, so only the
markdown front-end's IMPOSSIBLE short-circuits. Tests: `tests/test_llm_when.py`.

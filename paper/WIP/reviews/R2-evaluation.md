# R2 — Review of the EVALUATION ONLY (Section 10)

Paper: `paper/WIP/main.pdf` (source `paper/WIP/main.tex`, §10 `sec:eval`, ll. 836–1213).
Theory (§§3–9) reviewed by another referee and not assessed here.
Everything below was checked by reading `paper/WIP/results/*.json`, `*.jsonl`,
`scripts/*.py`, `docs/*.md` and `benchmarks/` directly, and by re-running the
authors' own aggregation logic on the shipped data.

---

## (a) Summary judgement

**Score: C (weak reject). Confidence: high (4/5).**

This is a far better-instrumented artifact than the median ECOOP tool paper. There is a
Coq-extracted kernel, a differential test against it, a 162-skill real corpus, agent runs
with *recomputed* artifact verification rather than an LLM grader, a security scan of the
corpus, and a cost model. The authors volunteer several unflattering facts (the corpus
cannot pose the severity question; the first version of the usefulness experiment measured
their own task sizes; a tool bug found by the live-agent run). I want to be clear that I am
not accusing anyone of dressing things up. That is why the specific failures below matter
so much: they are all fixable, and most of them are fixable in a week.

The evaluation does not currently support the claims made of it, for four reasons.

1. **Six numbers in §10 are not the numbers in `results/`.** One is wrong by a factor of
   three (`5.1 M tokens / $4.259` vs. `15.84 M / $14.30`), one whole table's timings come
   from a run that no longer exists in the artifact, and one table cell contradicts both
   `severity.json` and the paper's own text three lines above it (Table 1's Benign column
   sums to 28; the text says 29). See W1–W6.
2. **The headline predictive-validity result is not statistically significant, and is
   non-monotone in the direction the theory predicts.** `0 of 120` vs. `7 of 220` is
   Fisher two-sided *p* = 0.055 treating all 340 runs as independent, which they are not;
   at the correct clustering unit (protocol×model×condition cell) it is *p* = 0.54. Within
   the bucket the paper collapses, catastrophe rate is 1.1 % at *k*\*=0 and 12.5 % at
   *k*\*=1 — *backwards*, and significantly so (*p* = 0.0025). The binning hides it. See W7–W8.
3. **Two of Finding 4's "three checks of the theory" cannot fail.** Misselection,
   catastrophe and *k*\* are all computed by the same `SeverityAnalyzer` object inside
   `scripts/live_agents.py`. `consistency_violations = 0` is a unit test, not a prediction.
   The paper half-admits this in a subordinate clause and then counts it as evidence. See W9.
4. **Finding 5 is confounded and 82 % of its refutations are a set difference.** 14 of the
   17 refuted configurations are `MISSING_CAPABILITY` — "the document invokes bash, the
   runtime has no bash" — produced by a front-end rule the authors say was *added for this
   experiment*. The same intervention that makes the checker refute is the intervention that
   makes the agent fail. Only 3 refutations (2 `GOAL_UNSAT`, 1 `BLOCKED_GUARD`) exercise the
   paper's actual machinery, and all 3 are author-constructed. There is **no baseline of any
   kind** — no LLM judge, no grep, no run-and-retry. See W10–W13.

Fix W1–W6 (arithmetic), W7–W8 (statistics), W9 (relabel), and W10 (one new experiment) and
this is a B. As it stands the evaluation section would not survive artifact evaluation.

---

## (b) Three strengths

**S1. The verification target is a verifier, not a vibe.** `scripts/usefulness.py:96–113`
runs the agent in a temp dir with `--allowedTools` restricted, then executes an
author-written Python verifier that *recomputes* the answer from the generated inputs and
compares exactly (`usefulness_tasks_large.json` regenerates 1000 rows from a fixed
`random.seed` and recomputes the expected `quality_report.json`). The `silent_wrong`
category — claims done, artifact fails verification — is the right outcome variable and is
almost never measured in this literature. The 5 silent wrong results at realistic scale are
the most interesting fact in the paper and are currently under-sold.

**S2. Differential testing against an extracted kernel is the right idea and is rare.**
`scripts/differential_test.py` samples random protocols inside the shared fragment and
compares the hand-written analyzer to the OCaml extracted from `Kernel.v`. The claim "they
share no code, so a disagreement is a defect in one of them" is correct and is a genuinely
stronger form of evidence than the 16 hand-picked protocols. See W14/W15 for why the
reported number oversells it, but the design is sound and should be kept and expanded.

**S3. The negative results are reported.** Finding 1 (no corpus pack declares an
irreversible effect; the 17 vendor skills contain zero choice points — confirmed:
`severity.json` `real_skills` rows all have `choices: 0`) is an admission that the paper's
own question is invisible to existing benchmarks. The abandoned small-input experiment
("that was a measurement of our task sizes, not of the checker") is reported *and kept in
Table 3*. The `benchmarks/home_refutation_audit.json` hand audit of all 13 home refutations,
finding 7 of them to be the authors' own extraction bugs, is exactly the kind of thing most
authors bury. Credit where due.

---

## (c) Weaknesses, numbered, with severity and the concrete fix

### Numbers that the data does not support

**W1 — BLOCKING. Finding 6's waste figure is wrong by 3.1×; `results/token_economics.json`
is stale.**
§10, l. 1209: *"the runs this experiment's refuted configurations spent before failing came
to 5.1 M tokens and \$4.259."*
`results/token_economics.json` says `wasted_runs: 34, wasted_tokens: 5098701, wasted_usd:
4.259`. But that file was written at `12:41:57`; `usefulness_runs.jsonl` was last appended
at `13:07:33` and `usefulness.json` at `13:23:20`. The scale-up runs — the entire point of
the rebuilt experiment — post-date it. Re-running `token_economics.py`'s own definition
(`wasted = [x for x in ref if x["outcome"] != "success"]`, ll. 194–201) over the *shipped*
`usefulness_runs.jsonl` gives:

| quantity | paper / `token_economics.json` | shipped data |
|---|---|---|
| measured runs | 114 | **134** |
| median tokens per run | 72001 | **80331** |
| median USD per run | $0.0489 | **$0.0548** |
| median turns per run | 5 | **6** |
| wasted runs | 34 | **46** |
| wasted tokens | 5,098,701 | **15,841,106** |
| wasted USD | $4.259 | **$14.296** |

Consequently *"one compaction is 31.2 % of a single run"* (22440/72001) becomes **27.9 %**
(22440/80331). `docs/TOKEN_ECONOMICS.md` carries the same stale numbers.
*Fix:* re-run `python3 scripts/token_economics.py --report-only` after the usefulness data
and update ll. 1201–1213 and `docs/TOKEN_ECONOMICS.md`. Add a `make results` target that
re-derives every dependent JSON in topological order so this cannot recur.

**W2 — MAJOR. Table 1 (`tab:bench`) has a wrong cell, and its own column does not sum to
the text.**
Row `claim_ineligible` is printed `& 1 & 0 & refund & 0 & 0 & 0 & 1` (main.tex l. 936;
main.pdf l. 709), i.e. Benign = 0. `severity.json` gives that protocol
`counts: {Benign: 1, Futile: 0, Catastrophic: 1}`. Summing the printed Benign column gives
**28**; the text at l. 913 says **29 \Ben{}** (which is what the data says). Every other row
matches the JSON exactly.
*Fix:* change that cell to `1`. Then the column sums to 29 and agrees with the prose.

**W3 — MAJOR. Every wall-clock number in Table 2 (`tab:mod`) and its caption disagrees with
`severity.json`.** The structural counts (`exits`, `interface`) match exactly; the times do not.

| n | whole (paper) | whole (`severity.json`) | proj. (paper) | proj. (data) |
|---|---|---|---|---|
| 1 | 18.6 | 19.2 | 18.6 | 19.2 |
| 2 | 108.6 | 111.3 | 38.4 | 40.5 |
| 3 | 494.5 | 482.1 | 67.1 | 60.0 |
| 4 | 2130.5 | 2016.9 | 81.5 | 91.8 |
| 5 | 9217.6 | 8411.6 | 114.7 | 104.0 |
| 6 | 35752.0 | 37499.1 | 132.9 | 126.6 |

Also l. 976 *"At n = 6 that is 35.8 s against 0.13 s"* → 37.5 s vs 0.127 s; l. 977
*"the full run (172 ms)"* → 211.6 ms; caption *"whole-system 16–172 ms … modular 19–25 ms"*
→ 18.7–211.6 ms and 19.2–22.4 ms; caption *"(728 ms vs 59 ms at n = 6)"* → 734.8 ms vs
65.8 ms. The n=5 whole-system figure differs by **9.6 %** between two runs of the same
code — which is itself the point: these are **single, unreplicated wall-clock measurements
printed to six significant figures** with no machine, no CPU, no repetition count and no
variance.
*Fix:* two options, both acceptable. (i) Re-run with `n≥5` repetitions and print
median ± IQR to two significant figures, and state the machine. (ii) Better and cheaper:
**replace the times with the `configs` and `goal_queries` counters already in
`severity.json`** — they are machine-independent and reproduce exactly — and give wall-clock
only as a single sentence ("the n=6 whole-system run takes ≈37 s on a laptop").

**W4 — MAJOR. "499 random protocols" is 500 generated, one of which crashed the analyzer,
and the crash is not reported.** §10 l. 872 and the abstract's C5 (*"agrees … on 499 of 499
random protocols"*). `results/differential.json` `cumulative.runs` = `[{n:150, agree:149},
{n:350, agree:350}]`. The missing comparison is in
`results/differential_failures.json`: `{"kind": "analyzer-crash", "error": "protocol[2]:
duplicate rec name 'L'"}` on pack `rand136`. `differential_test.py:107` swallows analyzer
exceptions with `continue`, so the crash never enters `compared`. Presenting 499/499 while
suppressing a 1/500 crash of the very component under test is not acceptable.
Worse: `differential_test.py` was modified at `20:12:41`, `differential.json` written at
`20:17:59`. I re-ran `gen_pack` with the shipped generator at seed `20260902` for n=150:
**150/150, zero crashes** — the seed-20260902 corpus in the cumulative total is not
reproducible from the shipped script, because the generator was changed (the `loop_id`
guard now prevents duplicate `rec` names) to stop producing the input that crashed. The
cumulative 499 therefore mixes two different generators.
*Fix:* delete `cumulative`, re-run a single clean campaign with the current generator at
≥2 seeds, and report `generated / compared / agree / disagree / analyzer-crash` as four
numbers. State the crash if one recurs. Fixing a generator so it no longer produces the
input that crashed your analyzer, and then reporting no failures, must not happen silently.

**W5 — MAJOR. The security paragraph contradicts `results/security_scan.json` and itself.**
§10 l. 1189: *"zero hits for fake harness turns, hidden instructions, invisible characters
or configuration edits."* `security_scan.json` `by_rule` contains
`"self_config/high/write-outside-workdir": 2` and `"injection/high/ignore-previous": 1`
(plus 3 `injection/medium/disclose-secrets`). The `self_config` family is the one the paper
singles out two lines earlier as *"the one that would change what every later skill may
do."* Four lines later the paper says *"one appends an API key to a shell profile"* — that
**is** the `write-outside-workdir` hit at `langsmith-fetch/SKILL.md:393–394`. The sentence
is false against the shipped scan and against the next paragraph.
*Fix:* rewrite as "nine files raised flags across five rule families; none is an attack on
the agent — the one `ignore-previous` hit is a security skill quoting a payload it teaches
you to test, and the two `write-outside-workdir` hits are a skill appending an API key to a
shell profile. Zero hits for fake harness turns and zero for invisible characters."

**W6 — MAJOR. `no_status` is reported as "exhausted their turn budget"; it is not.**
§10 l. 1128: *"7 runs that exhausted their turn budget"*; l. 1104: *"2 exhausted their
turns."* `usefulness.py:113` defines `no_status` as *"no `STATUS:` line was found and the
artifact did not verify"* — full stop. Turn counts of the 7 `no_status` runs at realistic
scale are **9, 11, 21, 21, 65, 113, 122**; the runs at 9/11/21 exhausted nothing. Meanwhile
the two runs that ran *longest* (126 and 127 turns, `writing-skills`/haiku) are classified
`silent_wrong`, not turn exhaustion. There is also a `--max-budget-usd` cap
(`usefulness.py:93`), so a run can stop for money rather than turns, and neither cap value
is recorded in `usefulness_runs.jsonl`.
*Fix:* rename the column "no verdict" → "no status line" in Table 3 and in the prose, and
record `max_turns` and `budget` per run. If you want a turn-exhaustion count, emit it from
the CLI's own stop reason.

**W7 — MINOR (but embarrassing). Two medians are misreported.** *"median 8 turns"* → the 20
realistic-scale shell runs have median **7.5**; *"a median of 21 turns"* → the 18
realistic-scale file-only runs have median **20.5**. Both are even-sized samples.
*Fix:* print 7.5 and 20.5, or report the IQR.

**W8 — MAJOR. Table 3's caption says "two runs each"; the last row is 18 runs, not 20, and
the two missing runs are never mentioned.** `data-quality-auditor` / `no-shell` / `sonnet`
has **zero** realistic-scale runs in `usefulness_runs.jsonl` (its only two entries, indices
44–45, are small-input). The missing cell is in the most expensive and most load-bearing
row — the one that produces "\$13.21, 14.28 M tokens, 4.5× the tokens".
*Fix:* run the two missing runs, or state in the caption "18 runs; one (skill, model) cell
failed to launch and is excluded."

### Statistics

**W9 — BLOCKING. The ordering result is not significant, and the paper reports no
uncertainty anywhere in §10.** `grep -in "confiden\|interval\|p-value\|significan\|variance"
main.tex` returns nothing in the evaluation. From `live_agents.json` `by_kstar_class`:

| class | runs | catastrophes | rate |
|---|---|---|---|
| *k*\*≥5 | 120 | 0 | 0 % |
| *k*\*=0 | 180 | 2 | 1.1 % |
| *k*\*=1 | 40 | 5 | 12.5 % |

- `0/120` vs `7/220` (the paper's comparison): Fisher exact two-sided **p = 0.055**. Not
  significant even under the false assumption that 340 runs are independent.
- The runs are *not* independent: 5 runs share a protocol, model, condition and prompt. At
  the cell level the same contrast is **0/24 vs 2/44 cells, p = 0.54**.
- The two "significant-looking" cells are the whole result: `booking_fastpath`/haiku/
  pressured (2 catastrophes) and `staged_commit`/haiku/pressured (5). Of 68 cells, **5 have
  any misselection at all** and **2 have any catastrophe**. Effective n = 2.
- The repair claim is likewise 2/5 → 0/5, Fisher **p = 0.44**.

**W10 — BLOCKING. The catastrophe rate is *not* "ordered as the classes predict"; it is
ordered backwards within the bucket the paper collapses.** The theory says smaller *k*\*
means catastrophe on fewer misselections, so *k*\*=0 should be at least as dangerous as
*k*\*=1. Observed: 1.1 % at *k*\*=0, 12.5 % at *k*\*=1, Fisher **p = 0.0025** — a
significant *inversion*. Binning `{0,1}` against `≥5` is exactly what conceals it, and the
paper does not report the per-class table it computed and shipped in
`live_agents.json`.
*Fix:* (i) print the three-row table above verbatim in the paper; (ii) delete the words
"ordered as the classes predict" and replace with "catastrophes occurred only on protocols
with finite *k*\*; the two finite classes are not separated by this sample, and the ordering
between them runs the other way — with 7 events in 5 cells the experiment cannot resolve
it"; (iii) report Fisher *p* or a Wilson interval for every rate in §10 (e.g. 0/18 →
[0, 0.18]; 19/20 → [0.76, 0.99]; 32/32 → [0.89, 1.00]).

**W11 — MAJOR. Finding 5 is n=2 per (configuration, model) with no uncertainty and no
per-model reporting, and the one model effect that exists is large and unreported.**
`usefulness.json` `per_model`: haiku has **7 of the 7** refuted silent-wrong results and the
single certified one; sonnet has **zero silent wrong results anywhere**. Sonnet also spent
\$10.26 vs haiku's \$5.33 on refuted runs — so the flagship "4.5× tokens" ratio is
model-dependent. The paper mentions "the small model fabricated the approval" once and never
reports that fabrication is entirely a one-model phenomenon in this sample.
*Fix:* add a per-model split to Table 3 (the data is already in `usefulness.json`), and add
one sentence: "every silent wrong result in the experiment came from the smaller model."

### Circularity — what is actually being tested

**W12 — BLOCKING. Two of Finding 4's "three checks of the theory" are tautologies.**
In `scripts/live_agents.py`:

- `misselection` = `not an._intended(...)` (l. 213) — the analyzer's own guard semantics.
- `catastrophe` = `cap.name in an.perm and not an.goal_reachable(rest, nxt, recenv)` (l. 177)
  — the analyzer's own reachability.
- `kstar` = `analyze(...).tolerance_degree` (l. 289) — the analyzer.

So *"Every catastrophe had more than k\* misselections and none occurred on a protocol
tolerant at every tested budget"* is `SeverityAnalyzer` agreeing with `SeverityAnalyzer`.
`consistency_violations = 0` and `catastrophes_on_tolerant_protocols = 0` **cannot** be
non-zero unless the analyzer is internally inconsistent. The paper concedes this in a
subordinate clause (*"the harness and the tool share semantics, so this checks the harness
against Theorem 13"*) and then still writes *"Three checks of the theory hold exactly."*
Only one thing in Finding 4 is empirical: **which label string the model emits**.
*Fix:* (i) delete "Three checks of the theory hold exactly"; (ii) move the consistency check
out of Finding 4 entirely and into the implementation paragraph as what it is — "an
end-to-end self-consistency assertion on the harness (11 tests + this)"; (iii) restate the
finding as: "Finding 4 measures one thing: whether a live agent selects branches the tool
labels Catastrophic. It does: 6 of 19 such branches were taken, 17 times, all under
pressure, by one model."

**W13 — MAJOR. "Sixteen of seventeen verdicts matched the pre-stated expectation" is not a
pre-registration, and the one mismatch was resolved by editing the benchmark.** The
"provenance notes" live in the *same file as the packs*
(`src/skillc/data/severity_corpus.json`, field `note`) and were committed in the *same
commit* as the tool and the evaluation (`fffda39`, "Paper v4: … severity tool and
evaluation"). Nothing in the artifact establishes that any expectation predates any run.
The `order_fulfilment` note now reads *"the second goal disjunct requires not-shipped"* —
i.e. it was rewritten after the disagreement the paper describes. So the honest reading is
"17/17 after we edited the one that disagreed."
*Fix:* either (a) drop the 16/17 score and say "each protocol carries a design note; one
authoring error was found by the tool and corrected", or (b) do it properly for a future
version: commit the expectations in a separate, earlier commit with a hash cited in the paper.

**W14 — MAJOR. The differential test's 499 agreements are mostly agreement on "nothing
happened", and the fragment excludes the two features the benchmark actually exercises.**
I re-ran the shipped `gen_pack` and computed the analyzer's tolerance degree distribution
over the same two seeds (`kmax=2`, as in `differential.json`):

| seed | n | degree ≥3/tolerant (`None`) | `-1` | 0 | 1 |
|---|---|---|---|---|---|
| 20260902 | 150 | 97 (65 %) | 25 | 23 | 5 |
| 4242 | 350 | 230 (66 %) | 63 | 46 | 11 |

Two-thirds of the comparisons are "no hazard found" — a verdict both implementations reach
by finding nothing. Only ~85 of 499 carry a discriminating finite degree, and only 16 have
degree 1. Because `kmax=2`, **no degree ≥2 is ever distinguished.** Further, the generator's
docstring says the fragment excludes *"no environment choice, no arithmetic"* — but the
paper's own §10 opening advertises "predicates concrete, numerics symbolic, **widened at
loop heads**", and Table 1's `order_fulfilment` is specifically an environment-choice
protocol. The widening — the single component most likely to be unsound — and environment
choice are **entirely untested** by the differential campaign, and §10 says so only in the
Scope paragraph 500 lines later.
*Fix:* (i) report the degree distribution alongside the agreement count (one extra line in
`differential.json`); (ii) raise `--kmax` to 4 to match the benchmark; (iii) bias the
generator toward finite degrees (reject-sample until ≥40 % of packs have degree < kmax);
(iv) say in Finding-0 text, not only in Scope, that arithmetic and environment choice are
outside the differentially tested fragment. Then "the strongest evidence we can offer" is
defensible.

### Baselines — none exist

**W15 — BLOCKING. There is no baseline of any kind in §10.** `grep -i baseline main.tex`
returns nothing. The paper's central usefulness claim ("the checker's refusals are the runs
that would have been wasted") is never compared against anything a practitioner would
actually do. Four obvious baselines, in ascending order of how badly their absence hurts:

1. **The one-line grep.** 14 of the 17 refuted configurations are `MISSING_CAPABILITY`
   (`Counter` over `usefulness.json` rows: `certified 17, MISSING_CAPABILITY 14,
   GOAL_UNSAT 2, BLOCKED_GUARD 1`). §10 l. 1032 concedes the mechanism: *"A code fence the
   document expects the agent to execute is an invocation of the shell (a front-end rule
   added for this experiment)."* A three-line script — "does the SKILL.md contain an
   executable fence or a shell command, and does the profile lack Bash?" — reproduces every
   one of those 14 refutations at zero cost. **You must show this baseline and show where
   the checker beats it**, or the reader concludes that Finding 5 evaluates a grep.
2. **The LLM judge.** Hand the model the skill and the tool list and ask "can this be done
   with these tools?" This is the obvious cheap alternative and its absence is the first
   thing a referee reaches for. I note `scripts/llm_judge_baseline.py` and
   `results/llm_judge.json` exist (written 20:41, after `main.tex`), but **every judge cell
   is null** (`"scored": 0` for both models) and neither is referenced anywhere in
   `main.tex`. So as submitted: no LLM-judge baseline. Also, when you run it: the
   `"observed"` half of its ground truth is *derived from the same agent runs Table 3
   reports* (`llm_judge_baseline.py:60–69`), so the checker will score 16/16 on it by
   construction. Score the judge only against the `constructed` cases and against
   held-out configurations.
3. **Run-and-observe.** The real operational alternative to a static check is: run the
   agent once, look at the artifact, don't retry. Its cost is one run, not zero — but the
   paper's savings arithmetic (Finding 6) implicitly assumes the alternative is *unbounded*
   retrying. Report cost-to-first-honest-failure as the comparator.
4. **A random / scripted chooser for Finding 4.** `live_agents.py` already ships one
   (`chooser`, "wrong 1 in 3", l. 261). Running it gives the floor against which "6 of 19
   Catastrophic branches were taken" means something. Right now there is no reference point
   for whether 6/19 is high or low.

**W16 — BLOCKING. Finding 5's treatment and its outcome are the same intervention.** The
independent variable is "delete Bash from the profile". That is simultaneously (a) what
makes the checker emit `MISSING_CAPABILITY` and (b) the direct cause of the agent's failure.
No operator needs a session-type checker to predict that an agent whose skill is a bash
script fails without bash. The three configurations that *do* test something
non-trivial — `order-in-budget/B` (`GOAL_UNSAT`), `onboard-badge/B` (`GOAL_UNSAT`),
`publish-with-approval/B` (`BLOCKED_GUARD`) — are author-written `benchmarks/spec-cases`,
n=4 runs each, 12 runs total. The entire non-tautological empirical support for the
achievability half of the paper is **12 agent runs on 3 protocols the authors wrote to be
refuted.**
*Fix:* see (d) below. This is the single most important change.

**W17 — MAJOR. "4.3 % false refutation" is not precision, and the precision figure is 46 %.**
§10 l. 1050: *"That is a false refutation on 4.3 % of the corpus, and it is the achievability
half's real precision figure."* `benchmarks/home_refutation_audit.json`: 13 home refutations,
**6 genuine, 7 misextraction**. Precision of the refutation verdict is therefore
**6/13 = 46.2 %** — more than half of home refutations are the front end mistaking a
dataframe method, a Cargo crate or an HTML meta tag for an agent tool. 7/162 is a base rate
over the corpus, not precision, and reporting it in place of precision reads as flattering.
Compounding this: **no false-certification analysis exists.** 149 home certifications are
unaudited, and all **108** no-shell refutations — the ones Finding 5 rests on — are
unaudited. A checker that certifies everything achieves 0 % false refutation.
*Fix:* (i) say "6 of 13 home refutations are genuine (precision 46 %); the 7 false ones are
extraction bugs, 4.3 % of the corpus"; (ii) hand-audit a random sample of ~30 of the 149
home certifications and report the false-certification rate, or state explicitly that it is
unmeasured; (iii) the audit is single-rater by the authors — either say so or get a second
rater and report agreement.

**W18 — MAJOR. The aggregate refutation result is never stated; the reader is given two
narratives instead.** `usefulness.json` `aggregate`: of 66 refuted runs, **20 succeeded**
(30 %). The paper's headline *"no refuted run succeeded"* holds only after partitioning off
the block where 20/20 refuted runs succeeded, and that block is still in Table 3 (row 5,
"verified 20 (by hand)"). The partition ("where the skill's procedure is the only route")
is a *post hoc* criterion introduced after seeing the result.
*Fix:* state the aggregate once — "over all 66 refuted runs, 46 failed and 20 succeeded by
routes around the skill; restricted to realistic input sizes, 0 of 18 succeeded" — and label
the partition explicitly as post hoc.

### Reproducibility

**W19 — BLOCKING. The corpus is not in the artifact and is not pinned.** `.gitignore:11`
excludes `real-skills/` (the 17 vendor skills) entirely, and `.gitignore:29` excludes
`real-skills-ext/*/` (the 145 third-party ones). `real-skills-ext/PROVENANCE.json` *is*
tracked, but each entry has only `{path, url, repo, fetched, license_note}` — the URLs point
at `.../main/...` and there is **no commit SHA and no content hash** for any of the 145
files, despite the paper saying the corpus was "de-duplicated by content hash". Upstream
`main` moves; a reviewer re-running `scripts/fetch_skills_ext.py` next month gets a different
corpus and cannot tell. The 17 vendor skills have no provenance file at all.
*Fix:* add `sha256` and the resolved commit SHA to every PROVENANCE entry, pin the raw URLs
to that SHA, and ship a hash manifest for `real-skills/` too. If licences permit, archive
the 162 files in the supplementary zip.

**W20 — MAJOR. No model identity, no sampling control, no cost caps recorded.**
`live_agents.py:122` invokes `claude -p --model haiku|sonnet`; `usefulness.py:91–93` the
same. `ask()` reads `d.get("modelUsage")` into `meta["models"]` and then **throws it away**
(only `meta["cost"]` is used, l. 209), so `live_agents_runs.jsonl` contains no model version:
`grep -o 'claude-[a-z0-9.-]*'` over all 340 records returns the empty set. No temperature,
no top-p, no sampling seed — the `seed` field is only the environment-choice RNG and the
cache key (`live_agents.py:157`). No `claude` CLI version. `--max-turns` (default 12) and
`--max-budget-usd` (default 0.6) are not recorded per run, yet runs reach **127 turns** and
one refuted configuration costs \$3.88, so both defaults were overridden by an unrecorded
amount. That makes "\$13.21 and 14.28 M tokens" a *policy choice* rather than a measurement:
raise the cap, raise the number.
*Fix:* record `model_version`, CLI version, `max_turns`, `budget`, and the resolved
`modelUsage` in every JSONL record; state them in §10; and re-report the refuted-runtime
cost under a cap *equal to the certified runtime's*, or as cost-to-first-failure.

**W21 — MINOR. Unpinned toolchain.** `pyproject.toml`: `z3-solver>=4.12`, `pyyaml>=6.0` —
no lock file, no Coq/OCaml version, no OS/CPU for the Table 2 timings. Also, the differential
campaign took **317.5 s for 350 protocols** (`differential.json` `seconds`) — worth stating
so a reviewer knows what re-running costs.

**W22 — MINOR. `usefulness_runs.jsonl` cannot reconstruct Table 3.** The run log has no
`size` / task-variant field, so the small-input and realistic-input runs of the same
(skill, runtime, model, seed) are indistinguishable except by line order — I had to split
them at index 96. `token_economics.py`'s `vd()` lookup (l. 187–192) silently falls through
to the small-task verdict key for every realistic-scale run for exactly this reason.
*Fix:* write `id` (which `usefulness.py` already computes, l. 148) into each JSONL record.

**W23 — MINOR. "Eleven tests check the tool's verdicts…"** — `tests/test_severity.py`
defines **15** test functions. Either the count is stale or it refers to a subset; say which.

### Tables and what to cut

**W24 — MINOR. Table 2 does not earn a full-width table.** Six rows of unreplicated
wall-clock at up to six significant figures, none of which reproduces (W3). The `loops`
column of Table 1 is 0 in 16 of 17 rows and `choices` is 1 in 12 of 17 — both are nearly
constant and could be folded into the protocol name.
*Fix:* cut Table 2 to three columns (n, exits, interface) plus one sentence of timing, or
convert it to a two-line log-scale plot. Drop Table 1's `loops` column.

**W25 — MINOR. Finding 3 is the least interesting result in the section and costs a page.**
"Projecting the interface onto the cone of influence makes analysis of a self-chained
protocol linear instead of exponential" is what a reader expects, on a synthetic chain of
the authors' own benchmark segment with atoms renamed per segment. It supports a theorem
that is reviewed elsewhere.
*Fix:* compress to one paragraph and two numbers (35.8 s → 0.13 s at n=6; interface 256 → 2),
cite `severity.json` for the rest, and spend the reclaimed space on the baselines of W15.

**W26 — MINOR. Table 3's "verified" column silently includes runs with no status line.**
Three of the 32 in row 1 are `verified_no_status` (`xlsx` 2, `docx` 1), i.e. the artifact
passed but the agent never said it was done. The caption discloses the convention; the prose
("32 of 32 real-skill runs … produced a verified artifact") does not. The convention happens
to help only the certified arm (all refuted rows have `verified_no_status: 0`).
*Fix:* split the column, or add "(29 with a status line, 3 verified without one)".

---

## (d) The single change that would most raise the score

**Add ~20 refutation cases whose refutation is *not* "the runtime lacks a tool the document
names", drawn from the real corpus, and run every baseline against them.**

Concretely: hold the runtime fixed (shell, everything available) and construct refuted
configurations the way `benchmarks/spec-cases/*/B` already does — a bound the only tool
cannot meet, a guard nothing establishes, a goal condition with no establisher — but derive
them from the 145 third-party skills rather than authoring them from scratch (e.g. by
tightening a budget or removing one establisher from a real skill and recording the edit).
Target ≥20 cases, ≥4 runs each. Then report, on the *same* configurations:

| | checker | grep-for-bash | LLM judge (both models, 3 votes) | run-once |
|---|---|---|---|---|
| accuracy vs. verified outcome | ? | ? | ? | — |
| false certifications | ? | ? | ? | — |
| cost | 0 tokens | 0 tokens | ? | ? |

This one experiment fixes W15 and W16 simultaneously, and it is the only thing that can
separate the paper's contribution from a capability set-difference. Today, 14 of 17 refuted
configurations are a grep and the other 3 are self-authored: whatever the theory is worth,
§10 does not yet measure it. Everything else on this list — W1–W8's arithmetic, W9–W11's
Fisher tests and Wilson intervals, W12's relabelling, W19–W20's pins — is a week of careful
work with no new science. That week plus this experiment is a B, and a good one.

---

### Appendix: what I verified as *correct*

So the authors know which numbers I am not disputing. All of the following reproduce
exactly from the shipped data.

- Table 1: all 17 rows except the `claim_ineligible` Benign cell; 55 branch verdicts;
  29/7/19 (data: 29 Benign — the *text* is right, the table cell is wrong); *k*\* distribution
  9×0, 2×1, 6×≥5; 0.33 s; every point-of-no-return action.
- Finding 1: 15 + 6 + 17 = 38 packs; zero `irreversible_caps` anywhere; all 17 `real_skills`
  rows have `choices: 0`; all corpus verdicts Benign.
- Finding 4: 340 runs, 400 agent decisions, \$1.592; 0/120 and 7/220; 6 of 19 Catastrophic
  branches taken 17 times; 1 of 7 Futile taken once; the single Benign branch taken 10 times;
  0 misselections in 170 plain runs; `staged_commit` haiku pressured 5/5 with 3 misselections
  each; `booking_fastpath` 2/5; 0 misselections on both bystander protocols in 40 runs;
  the repair pairs 2→0.
- Finding 5 / Table 3: **every cell** of all seven rows, under the caption's
  "verified = success + verified-without-status" convention; 134 runs; checker total 260.1 ms.
- Finding 6: 130/162 = 80.2 % escalation; 149 certified / 13 refuted at home; 108 refuted
  file-only; 95 flips; 49 escalations file-only; 1812.9 ms census; 20 compactions measured;
  median 22440 tokens / \$0.08793; fit 17939 + 0.595·chars; 32 free skills.
- Audit: 13 home refutations = 6 genuine + 7 misextractions; 7/162 = 4.3 %.
- Corpus: 17 vendor + 145 third-party over 12 collections = 162.
- Security: 162 scanned, 9 flagged, 1 `curl-pipe-shell`, 1 shell-profile append.

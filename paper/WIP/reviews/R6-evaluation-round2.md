# R6 — Review of the EVALUATION and PRESENTATION, round 2

**Paper:** *Affordable Mistakes: Severity-Aware Multiparty Session Types for Participants that
Choose Wrongly* — `paper/WIP/main.tex` (§10 `sec:eval`, ll. 1039–1474), `main.pdf` 26 pp.
**Lane:** evaluation design and arithmetic; presentation. The metatheory is another referee's
(R1/R4); I take the theorems on trust and never argue with them.
**Version reviewed:** `main.tex` md5 `546c7e6e0c02c777b9515fc37b6bec66`, 2026-09-02 22:29 UTC.
The file changed twice while I was reading it (*"Fifteen tests"* → *"Eighteen tests"* landed at
22:29); every quotation below is from that snapshot, and I say where a change had already landed.
**Live revision:** the paper changed again at 22:36 while this review was being written. The
changes touch W1 and are recorded in **Appendix B**, which says exactly which items they close and
which survive. Sections (a)–(f) describe the 22:29 snapshot.
**Method:** every number in §10 was re-derived from `paper/WIP/results/`, `benchmarks/`,
`real-skills*/`, and by re-running the shipped code. The reproduction log is Appendix A. Live model
calls fail with auth errors, so nothing that needs the API was re-run; everything else was.

---

## (a) Summary judgement

**Score: C (weak reject). Confidence: 4/5 (high).**
**It is a near miss.** Fix W1–W4 and this is a B I would argue for.

Round 1 (R2) listed six numbers that disagreed with the shipped data. **All six are fixed**, and
fixed properly rather than papered over: the waste figure is now \$14.296 / 15.8 M and matches
`token_economics.json`; the `claim_ineligible` cell is 1 and Table 1 now sums to the prose; Table 2
has been rebuilt on machine-independent counters that reproduce to the digit; the security
paragraph now says what the scan says; the `no_status` column is described honestly; the aggregate
(20 of 66 refuted runs succeeded) is stated *before* the partition and labelled post hoc; refutation
precision is reported as 6/13 = 46 %, not as 4.3 %; `PROVENANCE.json` now carries a `sha256` and a
byte count for all 145 third-party files, and **all 145 hashes verify**. R3's structural asks landed
too: §13 is a five-sentence subparagraph inside Limitations, Table 4 and Figure 3 are gone, Figure 1
has been redrawn on the running example, Table 1 has a `guards` column, the `✓` convention and
"pack" are defined. That is a serious, honest revision and I want it on the record.

It is not enough, for four reasons, and one of them is new.

1. **The headline predictive-validity claim is still not supported, and I can now show the number
   that carries it is unfalsifiable.** *(Partly revised at 22:36 — see Appendix B; the ordering
   wording is gone, a two-sided Fisher p is now given, and points (i) and (iii) below survive.)* §10: *"The catastrophe rate is ordered as the classes predict: 0 of 120 runs
   on k\*≥5 protocols, 7 of 220 on k\*∈{0,1}."* The abstract repeats it. R2 showed the ordering runs
   backwards inside the collapsed bucket (1.1 % at k\*=0, 12.5 % at k\*=1, Fisher p = 0.0025). That
   is unchanged. Worse: I ran the harness's own scripted chooser — *no model at all*, wrong 1 in 3 —
   over the same 340 cells and got **0 of 120 on k\*≥5**. The six tolerant protocols have one choice
   point each and are tolerant to ≥4 misselections, so a catastrophe there is arithmetically
   impossible. The paper's flagship contrast is a theorem about its own semantics that a coin can
   reproduce. (W1)
2. **The abstract and C5 say the agents ran on 162 skills. Sixteen documents were ever executed.**
   *"on 162 skills from thirteen public repositories, run in two runtimes with every artifact
   verified by recomputation"*; C5: *"134 verified runs over 162 real skills in two runtimes"*. The
   162 is a static census that spends no tokens; the 134 runs cover 8 real skills, 4 specification
   pairs and 5 rescaled variants. Every reader will take the stronger reading. (W2)
3. **The one new baseline is, on this dataset, a lookup of the runtime's name — and half its
   ground truth is the checker's own previous result.** `grep_baseline.py` returns `True` whenever
   `runtime != "no-shell"`, so on all 18 shell-runtime configurations it is a constant; on the 16
   observed ones the runtime alone predicts the truth perfectly (8 shell = achievable, 8 no-shell =
   not). A classifier that reads nothing but the runtime string scores **25/34 — the grep's exact
   score.** Meanwhile 16 of the 34 ground-truth labels *are* the outcomes of Table 3, so the
   checker's 34/34 restates Finding 5 rather than testing it; and 5 of the 9 specification pairs
   were authored at 21:01–21:02 on 2 Sep, i.e. after R2 asked for a baseline and long after the
   agent runs ended at 13:07, and **have never been run by an agent**. (W3)
4. **Three sentences assert things the artifact contradicts.** *"we ran the same two production
   models … for nine authored specification pairs"* — Table 3 shows four. *"each run recording the
   model identifiers actually served and its turn and spend caps"* — **no record in either run log
   contains any of the three fields** (0 of 340, 0 of 134); the code that would record them was
   written after the runs. *"every run and every reply is in `results/`"* — the five discarded
   `order_fulfilment` sonnet runs are in no shipped file and in no git object. (W4, W9)

Everything in W1–W4 is a writing-and-analysis problem, not a science problem: the data to state
each of them correctly is already in `results/`. That is why this is a C and not a D.

---

## (b) Three strengths (evaluation)

**S1. Table 2 is now the model of how to report a scaling result.** Replacing six-significant-figure
unreplicated wall-clock with `goal_queries` and `interface` counters was exactly right, and every
one of the 36 cells reproduces from `severity.json` to the digit. More venues should demand this.

**S2. The corpus census is completely reproducible and the audit is exemplary.** 162 skills,
149/13/108/95/130/49/32 — every one recomputed from `token_economics.json` rows. The 13 home
refutations in `home_refutation_audit.json` are exactly the 13 rows the census refutes, path for
path, and the 6-genuine/7-misextraction split is stated *against the authors' interest* along with
"we have not audited the other direction … no false-certification rate is claimed" and "the audit is
single-rater and ours". Three separate self-inflicted wounds in four sentences. Credit.

**S3. The verified kernel reproduces exactly and the differential idea is right.** I re-ran the
kernel on all 17 benchmark packs: 16 in-fragment, 16 agreements, 0 disagreements, max 18.4 ms
(paper: "under 50 ms"). And I re-ran both differential campaigns end to end: seed 4242 gives
350/350 and seed 20260902 gives 150/150. The design — a hand-written analyzer against an
extraction of its own proof, sharing no code — is rare and worth keeping.

---

## (c) Re-derivation of §10, number by number

Legend: **✓** reproduces exactly · **≈** stale (right method, old run) · **✗** disagrees or
unsupported.

| § | claim in the paper | shipped data | |
|---|---|---|---|
| open | 15 → **18** tests | 18 `def test_` in `tests/test_severity.py` | ✓ (fixed at 22:29) |
| kernel | 16 in-fragment protocols agree, <50 ms each | 16/16, max 18.4 ms, `order_fulfilment` skipped (env choice) | ✓ |
| diff | 500 generated, **499 compared**, 499 agree, 0 disagree | shipped `differential.json` cumulative 499; **re-running the shipped generator gives 500/500** | ✗ W7 |
| diff | "the 500th was rejected by the pack schema, a generator bug" | `differential_failures.json` labels it `analyzer-crash`; error is `PackError` from `pack.py:214`; the pack has two `rec L`, which the current `loop_id` guard makes impossible | ≈ W7 |
| diff | "two thirds have no reachable hazard" | 327/500 = 65.4 % (97/150 and 230/350) | ✓ |
| F1 | 38 packs, none irreversible, 17 real skills no choice point | 15+6+17; `irreversible_caps` empty everywhere; `real_skills` all `choices: 0`; all `k_star` null | ✓ |
| F2 | 55 branch verdicts; 29 Ben / 7 Fut / 19 Cat | 55; 29/7/19 | ✓ (but see W5) |
| F2 | k\* distribution 9×0, 2×1, 6×≥5 | 9, 2, 6 | ✓ |
| F2 | PNR actions (9 named) | identical set | ✓ |
| F2 | **0.33 s** total | Σ`elapsed_s` over the 17 benchmark rows = **0.262 s** (all 55 rows = 0.616 s) | ≈ W11 |
| F2 | every Table 1 cell | all 17 rows match `severity.json`, `claim_ineligible` Benign now 1 | ✓ |
| F3 | Table 2, all 36 counter cells | exact | ✓ |
| F3 | "27.6 s against 0.11 s" | 27572.2 ms vs 108.1 ms | ✓ |
| F3 | caption "whole-system **16–172 ms**; modular **19–25 ms**" | recheck: **15.3–130.6 ms** and **16.2–18.6 ms** | ≈ W11 |
| F3 | caption "deployment … **728 ms vs 59 ms** at n=6" | deploy n=6: 661.4 vs 62.0 (complete/projected) or 59.4 vs 10.8 (recheck) | ≈ W11 |
| F3 | "grows about fourfold per segment" | time ×4.2; **counters ×2.0** — and the paper says it reports counters | ≈ W11 |
| F4 | 340 runs, 400 decisions, \$1.59 | 340, 400, \$1.592 | ✓ |
| F4 | 0/120 and 7/220 | 0/120; 2/180 + 5/40 | ✓ arithmetically, ✗ as inference (W1) |
| F4 | 6 of 19 Cat taken 17×; 1 of 7 Fut once; 1 Ben 10× | identical | ✓ |
| F4 | 0 misselections in 170 plain runs | 0 — *after* the prompt revision (W9) | ≈ |
| F4 | staged\_commit 5/5 with 3 misselections; booking 2/5; bystanders 0/40 | identical | ✓ |
| F4 | "recording the model identifiers … and its turn and spend caps" | **0 of 340 records contain any of them**; `live_agents.py:130` collects `models` and `:208` discards it; the harness has no turn or spend cap at all | ✗ W4 |
| F5 | 162 skills = 17 vendor + 145 over 12 collections | 17 + 145, 12 distinct repos | ✓ |
| F5 | 149 / 13 / 108 / 95 | identical | ✓ |
| F5 | 6 genuine / 7 misextraction; 4.3 %; 46 % | 6/7; 7/162 = 4.32 %; 6/13 = 46.2 % | ✓ |
| F5 | census **1.8 s** | `check_ms_total` = **2133.9 ms** | ≈ W11 |
| F5 | "**nine** authored specification pairs … we ran" | Table 3 and `usefulness.json`: **four** pairs, 32 runs | ✗ W4 |
| F5 | Table 3, every cell of all 7 rows | all 7 rows reproduce: runs/verified/silent/honest/no-status/cost/tokens | ✓ |
| F5 | 134 runs; 28 runs cost \$1.09 / 1.56 M | 134; \$1.087 / 1,556,728 | ✓ |
| F5 | realistic shell 19/20, \$1.64, 3.19 M, **median 8 turns** | 19/20, \$1.645, 3,189,893, **median 7.5** | ≈ W13 |
| F5 | realistic file-only 0/18 (6+5+7), \$13.21, 14.28 M, **median 21 turns**, 4.5× | 0/18 (6/5/7), \$13.21, 14,284,378, **median 20.5**, 4.48× | ≈ W13 |
| F5 | aggregate 20 of 66 refuted runs succeeded | 20/66 | ✓ |
| F5 | checker total over 34 configurations **260 ms** | Σ = **227.9 ms** | ≈ W11 |
| F5 | caption "one cell timed out and contributes no runs" | the cell contributes **2** runs (18 = 20−2); `timeout` counter is 0 in every row | ✗ W16 |
| grep | 34 configurations, grep 25, checker 34 | 25 and 34 | ✓ arithmetically, ✗ as a baseline (W3) |
| grep | "the checker gets 34, **in 0.2 ms**" | 0.22 ms is `grep_ms`; the checker takes **227.9 ms** over the same 34 | ✗ W12 |
| grep | "at realistic input size" | 6 of the 16 observed configurations (pdf/xlsx/docx) have `size: null` | ✗ W12 |
| sec | 162 scanned, 9 flagged, zero fake-harness / hidden-comment / invisible-char hits | 162, 9; those three rules have zero hits | ✓ |
| sec | 1 curl-pipe-shell, 1 shell-profile append, neither among the 16 executed | `curl-pipe-shell: 1`, `write-outside-workdir: 2` in `langsmith-fetch`; not executed | ✓ |
| F6 | 130 (80.2 %) escalate at home; 49 file-only; 108 free; 32 free skills | identical | ✓ |
| F6 | 20 compactions, median 22440 tok / \$0.088, fit 17939 + 0.595·chars | identical (R² = 0.891, unreported) | ✓ (W14) |
| F6 | median run 80331 tok / \$0.055; 27.9 % | identical | ✓ |
| F6 | 15.8 M / \$14.296 wasted | `wasted_tokens` 15,841,106, `wasted_usd` 14.296 | ✓ |

**Score:** 34 claims reproduce exactly, 9 are stale, 6 disagree or are unsupported. The arithmetic
is in far better shape than at round 1; what is left is the *inference*.

---

## (d) Weaknesses, ranked

### BLOCKING

**W1 — "The catastrophe rate is ordered as the classes predict" is false, and the number that
supports it can be produced without a model.**
Three separate problems, in increasing severity.

*(i) The ordering is backwards where the data can see it.* `live_agents.json.by_kstar_class`:

| class | runs | catastrophes | rate | Wilson 95 % |
|---|---|---|---|---|
| k\*≥5 | 120 | 0 | 0 % | [0.000, 0.031] |
| k\*=0 | 180 | 2 | **1.1 %** | [0.003, 0.040] |
| k\*=1 | 40 | 5 | **12.5 %** | [0.055, 0.261] |

The theory predicts k\*=0 is at least as dangerous as k\*=1. Observed inversion, Fisher
p = 0.0025. The paper ships this table and prints the binned version instead. Unchanged from R2 W10.

*(ii) The surviving contrast is not significant and is driven by two cells.* 0/120 vs 7/220 is
Fisher two-sided **p = 0.055** even pretending all 340 runs are independent. They are not: five runs
share protocol, model, condition and prompt. At the cell level, **0/24 vs 2/44, p = 0.54**. All
seven catastrophes come from two cells (`staged_commit`/haiku/pressured ×5,
`booking_fastpath`/haiku/pressured ×2). The repair claim is 2/5 → 0/5, **p = 0.44**. §10 contains no
p-value, no interval and no clustering unit — `grep -i "confiden\|interval\|significan"` over the
section still returns nothing.

*(iii) New: the 0/120 is structurally guaranteed.* I ran `live_agents.simulate` with the harness's
own scripted chooser (`--dry`, "wrong 1 in 3"), 20 runs × 17 protocols:

| class | scripted chooser | live models |
|---|---|---|
| k\*≥5 | **0 / 120 (0 %)** | 0 / 120 (0 %) |
| k\*=0 | 59 / 180 (32.8 %) | 2 / 180 (1.1 %) |
| k\*=1 | 8 / 40 (20.0 %) | 5 / 40 (12.5 %) |

The six k\*≥5 protocols have **exactly one choice point each** and are tolerant to ≥4 misselections,
so no run can reach a hazard whatever the agent does. The k\*∈{0,1} group averages 1.4 decisions per
run (k\*=1 averages 2.5). The headline contrast is therefore confounded by decision count and
guaranteed by the analyzer's semantics — precisely R2's W12, restated in a place the paper still
presents as an empirical result.

And the agents' *misselection* rate points the other way: 0.011 per decision on k\*=0 protocols,
**0.092 on the tolerant ones**, 0.150 on k\*=1. Agents misselect ~8× more often on the protocols the
tool calls safe. Nothing bad happened — which is what tolerance means, and is worth saying plainly.

*Fix.* (i) Print the three-row table. (ii) Delete "ordered as the classes predict" from §10 **and
from the abstract**. (iii) Replace with what is true and still interesting: *"Agents misselected on
tolerant protocols 11 times in 120 runs and no hazard was reached, which is what tolerance means;
all seven catastrophes fell on finite-k\* protocols, in two cells, under pressure, from one model.
The two finite classes are not separated by this sample and the point estimates run the wrong way;
with seven events the experiment cannot resolve them."* (iv) Report the scripted-chooser floor in
the paper — it is one line of the authors' own code and it makes the 0/120 honest instead of
hollow. (v) Give a Wilson interval for every rate in §10: 0/18 → [0, 0.18], 19/20 → [0.76, 0.99],
32/32 → [0.89, 1.00], 6/13 → [0.23, 0.71].

---

**W2 — The abstract and C5 report the static census as if the agents had run it.**
Abstract: *"on 162 skills from thirteen public repositories, run in two runtimes with every artifact
verified by recomputation, the refusals coincide with the runs that ended in wasted tokens or a
fabricated result."* C5: *"134 verified runs over 162 real skills in two runtimes."*
The census is `check()` on 162 documents in 2.1 s and 0 tokens. The runs are 134, over 21 tasks
drawn from 8 real skills, 4 specification pairs and 5 rescaled variants — **16 distinct documents
were ever handed to an agent**, out of 162. §10 is careful about this; the abstract and C5 are not,
and they are what a PC member reads first and quotes in the meeting.
*Fix.* Abstract: *"a 162-skill static census, and 134 agent runs over 21 tasks with every artifact
verified by recomputation, in which no refuted configuration produced a correct artifact at
realistic input size."* Same surgery on C5. And take R3's advice: sell the 340 runs, not the 162
files.

---

**W3 — The grep baseline does not discriminate, and half its ground truth is the result it is
supposed to check.**
Three defects, each independently fatal to the paragraph's claim of an "honest division of credit".

*(i) The baseline is a runtime-name lookup.* `grep_baseline.py:31` — `if runtime != "no-shell":
return True`. All 18 constructed configurations are shell, so the grep answers `True` on all of them
by construction and is wrong on exactly the 9 B variants. On the 16 observed ones the runtime alone
is a perfect predictor (8 shell all achievable, 8 no-shell all not). Verdict-for-verdict, **the grep
equals the constant classifier "shell ⇒ achievable"** on all 34 rows, which also scores 25. The
paragraph's regular expression never fires in a case that could distinguish it from reading the
profile name.

*(ii) There is no case in the ground-truth set where the grep can produce a false refutation.* Every
grep error is a false *certification*. The regime where a grep would actually hurt — a document with
a bash fence that is nonetheless achievable without a shell — is not represented, and the 108
no-shell census refutations that would populate it are unaudited and unrun.

*(iii) 16 of the 34 labels come from Table 3.* `llm_judge_baseline.ground_truth()` derives the
"observed" half from `usefulness_runs.jsonl` — the very runs Finding 5 reports. Scoring the checker
34/34 on that set restates Finding 5 for 16 rows and evaluates 18 author-written cases for the rest,
**5 of which were created after this criticism was made** (`index-then-search`,
`migrate-with-quota`, `quota-send`, `sign-then-ship`, `two-person-release`, all mtime 21:01–21:02 on
2 Sep; the agent runs ended at 13:07) and have never been executed. Those 5 supply 5 of the 9
grep errors — i.e. **the margin between 25 and 34 is more than half composed of cases authored after
the reviewer asked for the comparison.**

To be fair: the 9 B variants are a genuinely better refutation set than the 4 of round 1 — 5
`GOAL_UNSAT`, 3 `BLOCKED_GUARD`, 1 `MISSING_CAPABILITY`, all reproducing, and the paper's
"three bounds / three guards / two goal conditions / one undeclared tool" taxonomy maps onto them
exactly. The problem is that they are scored against a baseline that cannot lose in an interesting
way, and 5 of them have no behavioural evidence at all.

*Fix.* (i) Say what the grep is on this data: *"a classifier that reads only the runtime scores the
same 25."* (ii) Make the baseline discriminating: run it on the 108 no-shell census refutations and
report its false-refutation rate against a hand audit, as you did for the checker's 13. (iii) Report
the grep comparison separately on `constructed` and `observed`, stating that the observed half is
the same evidence as Table 3. (iv) Run the 5 new pairs with agents, or mark them clearly as
"checker-only, no runs". (v) The LLM judge is still missing: `llm_judge.json` has `scored: 0` for
both models, `llm_judge_runs.jsonl` is empty, and `docs/LLM_JUDGE.md` ships a table of `None ✗` over
a *24*-configuration ground truth that no longer matches the grep's 34. Either run it or delete the
doc; shipping a baseline artifact with no data invites the worst reading.

---

### MAJOR

**W4 — Three sentences state things the artifact contradicts.**
- *"for nine authored specification pairs … we ran the same two production models"* (l. 1339).
  `usefulness.json` has four pairs, 16 A-runs and 16 B-runs. Table 3 says four. The prose says nine.
- *"each run recording the model identifiers actually served and its turn and spend caps"*
  (l. 1296). Field coverage of `live_agents_runs.jsonl` (340 records): `pack, model, cond, seed,
  choices, outcome, pnr, misselections, agent_calls, cost_usd`. No served model, no cap — and
  `live_agents.py` has no `--max-turns` or budget flag at all; those live in `usefulness.py`, whose
  own 134 records also carry none of `served_models`/`max_turns`/`budget_usd` (the code that writes
  them, `usefulness.py:120`, post-dates the data). `grep -o 'claude-[a-z0-9.-]*'` over both logs is
  still empty.
- *"every run and every reply is in `results/`"* — see W9.
*Fix.* Correct the first to "four", cut the second (or re-run and record), qualify the third.

**W5 — Table 1's trichotomy conflates intended branches with misselections, and the class the
paper's thesis needs has n = 1.**
`live_agents.json.branches` splits the same 55 verdicts by `intended`:

| | intended | misselection |
|---|---|---|
| Benign | **28** | **1** |
| Futile | 0 | 7 |
| Catastrophic | 0 | 19 |

So "29 Ben, 7 Fut, 19 Cat" reads as a roughly balanced trichotomy over wrong choices, when the
trichotomy over wrong choices is **1 / 7 / 19**. The single Benign misselection is
`shipping_detour/express`, one of the two protocols with author-written explicit guards. Benign is
the class that carries the paper's slogan — *"a system that blocks Futile is useless"* — and the
benchmark exhibits it once, by construction. This is not dishonest (the caption does say "per branch
and abstract world") but it is the most flattering possible presentation of the one weak spot.
*Fix.* Split the columns into intended / misselected, or report "29 Benign (28 intended branches,
1 Benign misselection)". Then say plainly that constructing Benign misselections that arise from
reachability rather than policy is open — it is a much more interesting sentence than the one there
now.

**W6 — No uncertainty anywhere in §10.** See W1(ii) for the numbers. Every rate in Finding 5 is
n ≤ 20 with no interval; 0/18 and 32/32 are reported as though they were 0 % and 100 %.

**W7 — The differential campaign is not reproducible from the shipped generator, and its scope is
narrower than the paper implies.**
I re-ran both campaigns with the shipped `gen_pack` (Appendix A): seed 20260902 n=150 → **150
compared, 150 agree, 0 crashes**; seed 4242 n=350 → **350/350**. The shipped `differential.json`
records the first as `agree: 149`, and the missing pack (`rand136`) contains two `rec` nodes named
`L`, which the current generator's `loop_id` guard makes impossible. So the cumulative 499 mixes two
generator versions, and the correct number for the shipped artifact is **500 of 500**. The paper's
new sentence — "the five-hundredth was rejected by the pack schema, a generator bug rather than a
tool one" — is *true of the record* (`PackError`, `pack.py:214`) but describes a run nobody can
reproduce. Separately: the campaign ran at **`kmax=2`**, which §10 never states while the tool and
benchmark run at `kmax=4`. Degrees observed over the 500: `None` 327, `−1` 88, `0` 69, `1` 16 —
**no degree ≥2 is ever distinguished**, and only 16 packs in 500 carry the k\*=1 case the benchmark
is about.
*Fix.* Delete `cumulative`, re-run one clean campaign at `kmax=4` over ≥2 seeds, report
`generated / compared / agree / disagree / crash` as four numbers plus the degree histogram, and say
in the Finding-0 text — not only in Scope 400 lines later — that arithmetic and environment choice
are outside the tested fragment.

**W8 — Finding 3's comparator is the enumeration variant; the decision the tool actually makes is
linear and beats the modular analysis on this benchmark.**
`severity.json.modularity` ships both `whole_system` (early-exiting hazard decision) and
`whole_system_complete` (enumerates hazard-free terminations). Table 2 uses the latter. The former,
migration family:

| n | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| whole (early-exit) goal queries | 7 | 10 | 13 | 16 | 19 | **22** |
| whole (complete) goal queries | 8 | 26 | 62 | 134 | 278 | **566** |
| modular projected goal queries | 8 | 16 | 24 | 32 | 40 | **48** |

At n=6 the whole-system *decision* asks 22 queries in 0.13 s; the projected modular analysis asks 48
in 0.11 s. The exponential the finding is built on belongs to a variant the tool does not run by
default. §10 justifies the choice in one parenthesis — *"(like-for-like with computing an
interface)"* — which is fair on its own terms, but a reader is entitled to know that on the paper's
own benchmark the unabstracted check is linear. The re-check argument survives (130.6 ms vs 16.8 ms,
a constant factor ≈8, constant in n) and is the honest version of the claim.
*Fix.* Add the `whole_system` row to Table 2 and one sentence: *"The hazard decision alone
early-exits and is linear here; the exponential is in computing the exit set, which is what
composition needs. Modularity buys a constant factor on re-check (≈8× at n=6) and independence from
n, not an asymptotic win over the decision procedure."* Also reconcile "grows about fourfold per
segment" (that is the time; the counters grow twofold) with "we report the counters".

**W9 — A prompt was revised after an unfavourable result and the discarded runs are not in the
artifact.** §10: *"an earlier form of the prompt that hid what the environment's branches do led the
larger model to ship before charging in 5 of 5 plain runs; we count that against the prompt, re-ran
those cells with the branch contents shown, and report the re-run."* Those 5 runs are in no shipped
file and in no git object (checked at `3b8083c` and `9abbe33`; both contain only the post-revision
`order_fulfilment` cells, all successes, 0 misselections). The headline *"in the plain condition
neither model misselected once in 170 runs"* is therefore a post-intervention number, and the
intervention was triggered by exactly the observation that would have broken it. Disclosure is good;
disclosure plus deletion is not enough.
*Fix.* Ship the discarded runs as `live_agents_runs_prompt_v1.jsonl`, report both numbers
("5 of 5 under the first prompt; 0 of 170 under the second, which shows the branch contents"), and
state the revision rule that was applied *before* seeing results, if there was one.

**W10 — Input size is a free parameter that was turned after seeing the result.** At the original
sizes, 20 of 20 refuted runs produced a verified artifact; at the rescaled sizes, 0 of 18. The paper
reports both, labels the partition post hoc and says "the earlier task was too easy" — all good. But
the chosen sizes (1000 transcripts, 1000 rows, 500 users, 150 manifests, 120 files) have no stated
criterion, and the headline "0 of 18" is a function of that knob. There is no sweep.
*Fix.* One extra size point per task (say 10× smaller) turns a knob into a curve and would let the
paper say where hand computation stops working — which is a genuinely useful result and costs about
\$3 of agent time.

### MINOR

**W11 — Four stale timings** (the same class of defect R2 flagged; there is still no `make results`
to re-derive dependents in order). "0.33 s" → 0.262 s; "260 ms" → 227.9 ms; "1.8 s" census →
2.13 s; Table 2's caption ranges "16–172 ms / 19–25 ms / 728 vs 59 ms" → 15.3–130.6 / 16.2–18.6 /
661 vs 62 (or 59.4 vs 10.8 for the re-check reading).

**W12 — "The grep gets 25; the checker gets 34, in 0.2 ms."** 0.22 ms is `grep_ms`, the regex time.
The checker takes 227.9 ms over the same 34 configurations — a factor of 1000. Whatever was meant,
the sentence as written credits the checker with the baseline's speed. Same paragraph: "at realistic
input size" is false for 6 of the 16 observed configurations (`pdf`, `xlsx`, `docx` have
`size: null`).

**W13 — Two medians still rounded silently** (unfixed from R2 W7): "median 8 turns" → 7.5;
"a median of 21 turns" → 20.5. Both even-sized samples.

**W14 — Four of 24 compaction runs failed and are dropped without mention.** `compaction_runs.jsonl`
has `ok: false` for `docx`, `algorithmic-art`, `pptx`, `golang-pro` (72–180 s, no reason recorded).
A 17 % failure rate of the escalation path is a result about the escalation path — it belongs in the
"decision procedure for spending money" paragraph, since 17 % of the time you pay and get nothing.
Also: the fit's R² = 0.891 is unreported and rests on one point at 85,677 chars (next largest
32,987); dropping it gives R² = 0.499, dropping two gives 0.214. The slope is stable (0.595 → 0.568)
so the conclusion holds, but "fitted as 17939 + 0.595·chars" should carry the R² and the caveat that
over the bulk of the corpus the cost is effectively the intercept.

**W15 — "Sixteen of seventeen verdicts matched the pre-stated expectation" is still not
pre-registered.** The `note` fields remain inside `severity_corpus.json`, committed with the tool at
`fffda39`; the `order_fulfilment` note still reads *"the second goal disjunct requires
not-shipped"*, i.e. as amended after the disagreement. Nothing in the artifact dates any expectation
before any run. Either drop the 16/17 score or commit expectations separately with a citable hash.

**W16 — "one cell timed out and contributes no runs."** The cell contributes 2 of 4 runs
(`data-quality-auditor`/no-shell, realistic), and `timeout` is 0 in all 34 rows. Say "one (skill,
model) cell contributed 2 of 4 runs; the other two did not complete."

**W17 — Reproducibility, residual.** The 145 third-party hashes verify, which is a real improvement,
but the URLs still point at `…/main/…` with no commit SHA, so a hash mismatch next month is
undiagnosable. The 17 vendor skills are `.gitignore`d with **no manifest, no hashes and no
provenance file** — a third of the executed corpus cannot be obtained or verified. No lock file, no
Coq/OCaml version in the paper, no machine named for the one surviving wall-clock sentence.

---

## (e) Presentation

The prose is still the best thing about this paper and R3's structural surgery landed: 14 sections
(from 15), §13 demoted to five sentences inside Limitations, Table 4 and Figure 3 cut, Figure 1
redrawn on the running example, Table 1 given a `guards` column, `✓` and "pack" defined, the italic
claim box gone, the `[title to verify]` references cleaned. **Page budget is fine**: the body ends
mid-page 24 where the references begin, so ≈23.5 pages against ECOOP's 25 excluding references,
with ~1.5 pages of slack.

**P1 — R3's W3 was declined without a replacement argument, and the off-thesis share grew.**
By tex lines: opening + kernel + differential 66, F1 13, F2 67, F3 53, **F4 55**, **F5 108**, grep
17, security 25, F6 27. The achievability half (F5 + grep + security + F6) is **177 lines, 41 % of
§10** — up ~40 lines from round 1 — and Finding 4, the only experiment that tests *this paper's*
thesis, is still half the length of Finding 5. R2 wanted baselines added; R3 wanted the section cut;
the authors took R2. That is a defensible choice, but the paper never argues it. As it stands a
reader gets three pages on a checker the paper inherits and did not contribute.
*Fix (cheap, keeps both reviewers happy).* Recast the achievability material as evidence for
**Figure 2's trust boundary** — "the untrusted compaction is cheap to police, and the deterministic
half predicts run outcomes without a model" — which *is* a contribution of this paper, and move the
census tables and the security paragraph to an appendix with a one-paragraph summary in §10. Spend
the reclaimed page on Finding 4: the three-row k\* table, the scripted-chooser floor, the per-cell
clustering, and the discarded-prompt runs. That page is the difference between "we ran some agents"
and "we know what our experiment can and cannot resolve."

**P2 — Submission hygiene still blocks a real submission.** The title footnote renders
*"WORKING DRAFT — not for submission."* in red; a boxed *"WIP: Status"* note sits on page 2;
`\funding` and `\acknowledgements` render "To be completed for the camera-ready" under anonymous
review; line 4 carries `DO-NOT-SUBMIT-WHILE-THIS-LINE-EXISTS`. The status box also leaks the
withdrawn predecessor draft, which R3 flagged as an anonymity risk and which the §15 subparagraph
now repeats.

**P3 — §12 (TRAC) is still a section with its own figure.** R3 asked for it to become a subsection
of Related Work; deleting Table 4 fixed the duplication but the structural signal remains — one
related paper with a numbered section and a full-width figure, and no other. Demote it.

**P4 — Figure 1 now matches the running example, but both branch labels read `[goal survives]`.**
The intended edge is annotated "intended: guard holds" and the misselected edge "misselection: guard
fails", with the *same* bracketed guard text on both. That is technically right under the
rational-choice default (one guard schema, two truth values in W) and reads as a typo. One clause in
the caption — "under the default both branches carry the same guard schema; it holds in W on `safe`
and fails on `fast`" — removes the double-take. Also, the figure draws all three fates out of
`fast`, while in G_bad only the Catastrophic one exists; the caption's last sentence says so, but
the picture and the example are doing different jobs in the same frame.

**P5 — Small table debts.** Table 1's `loops` column is 0 in 16 of 17 rows. Table 3's column header
is still "no verdict" while the prose (correctly, now) says "without the status line the harness asks
for" — make them agree. Table 3 row 5's `20 (by hand)` is still a value in a different unit from
every other cell in its column.

**P6 — Legibility on one pass: yes for §§1–2 and §10's findings, no for the §10 opening.** The first
two subparagraphs (implementation, verified kernel) run 66 lines before Finding 1 and contain the
kernel's goal-notion mismatch, the extraction story, the differential campaign and its caveats. A
reader arriving from §9 hits four distinct arguments before the first result. Split: put the kernel
and the differential test under their own heading ("Finding 0: the tool computes what the proof
defines") and lead §10 with one sentence saying what the tool is and what the section will show.

---

## (f) Verdict and ranked weaknesses

**C (weak reject), confidence 4/5.** The artifact is well above the median ECOOP tool paper and the
round-1 arithmetic is genuinely repaired. But the evaluation still asserts a predictive-validity
result its own data contradicts, still advertises a 162-skill run that never happened, and its one
new baseline cannot lose. None of that needs new science — item 1, 2, 4, 5, 6 and 11–17 below are a
week of careful rewriting against data already in `results/`, and items 3 and 10 are about \$20 of
agent time. I would move to B on W1–W4 alone.

Ranked by how much each costs the paper:

1. **W1** — the 0/120 is reproduced by a coin, the k\*=0 / k\*=1 inversion is still unprinted, and
   the new p = 0.055 is computed at the wrong unit (cell-level p = 0.54). *(blocking; the abstract
   half was fixed at 22:36)*
2. **W2** — abstract and C5 report the 162-skill census as agent runs; 16 documents were executed.
   *(blocking)*
3. **W3** — the grep baseline equals a runtime-name lookup, 16/34 of its ground truth is Table 3's
   own outcome, 5 of its 9 constructed pairs were authored after the criticism and never run; the
   LLM-judge baseline still has no data. *(blocking)*
4. **W4** — "nine pairs were run" (four were), "each run recording … caps" (no record has them),
   "every run … is in results/" (five are not). *(major)*
5. **W5** — Table 1's 29/7/19 conflates 28 intended branches with the one Benign misselection in
   the whole benchmark. *(major)*
6. **W6** — no p-value, interval or clustering unit anywhere in §10. *(major)*
7. **W7** — the differential campaign is not reproducible from the shipped generator (500/500, not
   499/500), ran at an unstated `kmax=2`, and never distinguishes a degree ≥2. *(major)*
8. **W8** — Finding 3 compares against the enumeration variant; the tool's own decision is linear
   here and beats the modular analysis. *(major)*
9. **W9** — prompt revised after an unfavourable result; the five discarded runs are in no shipped
   file. *(major)*
10. **W10** — input size is a post-hoc knob with no sweep. *(major)*
11. **W11** — four stale timings; still no `make results`. *(minor)*
12. **W12** — the checker credited with the grep's 0.2 ms; "realistic input size" false for 6 of 16.
    *(minor)*
13. **W13** — medians 8/21 should be 7.5/20.5. *(minor)*
14. **W14** — four compaction failures dropped silently; fit R² unreported and leverage-driven.
    *(minor)*
15. **W15** — the 16/17 "pre-stated expectation" is still not pre-registered. *(minor)*
16. **W16/W17** — "one cell timed out" unsupported; the 17 vendor skills have no manifest or hashes.
    *(minor)*
17. **P1–P6** — 41 % of the evaluation is off-thesis and grew; draft markers still render; §12 still
    a section; Figure 1's duplicated guard label; §10's 66-line preamble. *(presentation)*

**The single change I would ask for.** Rewrite Finding 4 around what the experiment can resolve, and
put the scripted-chooser floor next to the 0/120. Six lines of the authors' own code turn the
paper's weakest claim into its most credible one: *"a mechanical chooser that errs one time in three
also reaches no hazard on the tolerant protocols — that is what the analysis guarantees, and the
experiment confirms the harness. What the experiment measures is that live agents take branches the
tool calls catastrophic: 6 of 19, seventeen times, all under pressure, all from one model, in two of
sixty-eight cells."* That paragraph is honest, is fully supported by the shipped data, and is
stronger than the claim it replaces, because it is the only one a sceptic cannot take apart.

---

## Appendix A — reproduction log

All runs from `/home/user/skill-achievability-compiler`, `python3`, no network, no model calls.

- Table 1, Finding 1, Finding 2, k\* distribution, PNR set, benchmark time: aggregation over
  `paper/WIP/results/severity.json` `rows` filtered by `set == "severity_benchmark"` (17 rows,
  Σ`counts` = 29/7/19, Σ`branches` = 55, Σ`elapsed_s` = 0.262).
- Table 2: `severity.json.modularity`, `family == "migration"`, fields
  `whole_system_complete.goal_queries|exits`, `modular.goal_queries|final_interface`,
  `modular_projected.goal_queries|final_interface`. All 36 cells exact. `whole_system` (early-exit)
  read from the same records for W8.
- Kernel: `run_kernel(pack, kmax=4)` vs `analyze(pack, kmax=4).tolerance_degree` over
  `src/skillc/data/severity_corpus.json` — 16 agree, 1 skipped (`order_fulfilment`, environment
  choice), max 18.4 ms.
- Differential: `gen_pack` imported from `scripts/differential_test.py`, driven by a private loop
  that writes nothing. Seed 20260902 n=150 kmax=2 → 150/150/0 crashes, 131.7 s. Seed 4242 n=350
  kmax=2 → 350/350/0, 280.0 s. Degree histograms as reported in W7.
- Finding 4: `live_agents_runs.jsonl` (340 records) — 400 non-external decisions, Σ`cost_usd` =
  1.592, plain-condition misselections 0/170, per-class run/decision/misselection/catastrophe
  counts, field-coverage check for W4.
- Scripted-chooser floor: `live_agents.simulate(entry, "dry", "plain", seed, chooser)` with the
  `--dry` chooser from `live_agents.py:261`, 20 seeds × 17 protocols, `random.seed(7)`. Writes
  nothing.
- Table 3, Finding 5: `usefulness.json` `rows`/`aggregate`/`per_model` and `usefulness_runs.jsonl`
  (134 records) — all seven rows recomputed cell by cell; medians 7.5 / 20.5; token ratio 4.48.
- Grep baseline: `grep_baseline.json` (34 rows) — source split 18 constructed / 16 observed, truth
  split 17 true / 17 false, grep verdict compared against the constant `runtime == "shell"`.
- Spec cases: `check(compile_file(f, load_profile("claude-code")).pack)` over all 18 variants — 9
  certified, 9 refuted (5 `GOAL_UNSAT`, 3 `BLOCKED_GUARD`, 1 `MISSING_CAPABILITY`).
- Census, Finding 6: `token_economics.json` `rows` (162) — 149/13/108/95/130/49/32,
  Σ`check_ms` = 2133.9; `compaction_runs.jsonl` (24 records, 20 `ok`) — median 22440 / \$0.08793,
  OLS on the 20 → 17939 + 0.595·chars, R² 0.891, leverage checks by dropping the largest one and two.
- Audit and corpus: `benchmarks/home_refutation_audit.json` (13 entries, 6/7) matched path-for-path
  against the 13 census home refutations; `real-skills-ext/PROVENANCE.json` — 145 entries, every
  `sha256` and `bytes` re-hashed against the file on disk, **145/145 match**; 12 distinct repos.
- Security: `security_scan.json` — 162 scanned, 9 flagged, `by_rule` cross-checked against the rule
  table in `scripts/scan_skills.py` for the three "zero hits" families.
- Statistics: Fisher exact (two-sided, hypergeometric enumeration) and Wilson score intervals
  computed in-session; values quoted in W1 and W6.


---

## Appendix B — changes that landed at 22:36, while this review was being written

`main.tex` md5 `bb5b8646e79c735aa9d1af3755e8dd60`. The diff against the reviewed snapshot touches
the front matter, C2–C5, and exactly one paragraph of §10. Its effect on my list:

**Closed, or nearly.**

- *Abstract.* *"the catastrophe rate ordered by tolerance degree"* → *"six of the nineteen `Cat`
  verdicts taken by a live agent"*. This is the right sentence and it is fully supported by the
  data. **W1's abstract half is closed.**
- *§10, Finding 4.* *"Three checks of the theory hold exactly"* → *"Two checks"*, and the ordering
  claim becomes: *"A third check is directionally as the classes predict but does not reach
  conventional significance and we do not claim it does: 0 of 120 … against 7 of 220 …, one-sided
  Fisher p = 0.046, two-sided p = 0.055 … Read it as consistent with the ordering, not as evidence
  for a rate."* The two-sided p reproduces exactly (I get 0.0547); this is a real improvement and
  the first inferential statistic in the section.

**Still open, and the new paragraph does not address them.**

1. **The unit of analysis is still the run.** p = 0.055 assumes 340 independent observations; five
   runs share protocol, model, condition and prompt. At the cell level the same contrast is
   **0/24 vs 2/44, p = 0.54**, and all seven events sit in two of sixty-eight cells. Reporting a
   one-sided p at the wrong unit is weaker evidence than reporting no p at all, because it looks
   like the question has been answered. Add the clustering unit, or say "two cells" out loud.
2. **The inversion is still not shown.** "Directionally as the classes predict" is true only of the
   *collapsed* comparison. Inside the collapsed bucket the direction reverses — 1.1 % at k\*=0
   against 12.5 % at k\*=1, **p = 0.0025** — and `live_agents.json` ships the three-row table the
   paper still does not print. A sentence that says "directionally as predicted" while the
   theory-relevant contrast inside it runs the other way is not yet honest arithmetic.
3. **The 0/120 is still presented as an observation.** It is guaranteed: the six k\*≥5 protocols
   have one choice point each and tolerate ≥4 misselections. The authors' own scripted chooser
   reproduces **0/120** with no model involved (W1(iii), Appendix A). Until that is stated, a
   p-value on this contrast dresses a tautology in inferential clothing.

**Untouched by the revision.** W2 (abstract and C5 still report *"162 skills … run in two
runtimes"* and *"134 verified runs over 162 real skills"*), W3 (grep baseline), W4 (all three
sentences — *"for nine authored specification pairs … we ran"* is verbatim at l. 1345–1349;
*"its turn and spend caps"* at l. 1276; *"every run and every reply is in `results/`"*), W5–W17, and
every presentation item. C5 also still reports *"499 of 499"*, which the shipped generator now
contradicts (W7).

**Note on process.** Three revisions landed during a two-hour review, each changing numbers the
review had already verified ("160 → 165 → 168 theorems", "Fifteen → Eighteen tests"). That is
healthy for the artifact and hostile to reviewing: a PC cannot check a moving target, and an
artifact-evaluation committee will check the frozen one. Freeze the submission, re-derive every
dependent JSON from a single `make results` (which still does not exist — see W11), and rebuild the
PDF from that state once.
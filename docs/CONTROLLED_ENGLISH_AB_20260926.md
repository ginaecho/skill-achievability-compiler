# Controlled English vs JSON compaction: an A/B on 150 real skills

Date: 2026-09-26. Branch: `gc/controlled-English`.
Evidence: [`runs/20260926_ce_ab`](../runs/20260926_ce_ab).
Primary result commit: `9567231` (frozen CE grammar 1.0).

## Main conclusion

Compaction through SkillC Controlled English (CE) is implemented and works end
to end on real skills. After one located-error retry, every CE document for
150 real skills parsed into a valid pack. On the 32 contract-labelled
scenarios it matched the original JSON path exactly: 32/32 correct in every
checking scope.

Its measured advantages are:

- **Shorter output.** CE output is about 35% shorter (median 797 vs 1,212
  characters per compaction). Total output tokens across the run were about
  24% lower, even counting CE's extra retries.
- **Deterministic second half.** CE→pack is deterministic and exactly
  invertible. All 444 packs produced by either arm in this run, and all 169
  earlier packs in the repository, round-trip through CE with an identical
  verdict.
- **Possibly more stable verdicts.** Across three samples of the same skill,
  CE's verdict was stable for 15/20 skills vs 11/20 for JSON. With n = 20 this
  is suggestive, not significant (p = 0.22).

It did **not** show an accuracy gain. The labelled benchmark is saturated for
both arms. On unlabelled real skills, the two arms disagree about as often as
two samples of the same arm do. The dominant source of disagreement is which
tools the model decides to declare, and that is a semantic choice the output
format does not control.

CE's first-attempt validity was lower (115/150 vs 141/150). Almost all of
that came from one gap in my grammar, not from the model: the line
`Initially true: none.` was rejected. With that gap fixed (grammar 1.1,
applied post hoc to the same outputs), CE reaches 219/222 first-attempt
valid, against 222/222 for JSON when its own most common near-miss is fixed
the same way.

## What was built

| Component | Where |
|---|---|
| CE language: tokenizer, formula and expression parser, document parser, renderer, canonical form, extraction from model output | `src/skillc/frontend/ce.py` |
| NL→CE compaction with a located-error retry; the JSON `SYSTEM` prompt is unchanged | `src/skillc/frontend/llm.py` (`compact_ce`, `CE_SYSTEM`) |
| CLI: `.ce` files are accepted wherever a pack is; `--llm --via-ce`; `skillc ce FILE` renders or parses | `src/skillc/cli.py` |
| Tests: sentence forms, 24 located-error cases, round-trip on every repository pack and its mutants, Hypothesis properties, mocked LLM retry, CLI | `tests/test_ce.py` |
| Worked example (walk or drive to the gas station) | `examples/controlled-english/` |
| Real-skill corpus: 294 skills, 15 repositories | `benchmark/ce_sources/` |
| A/B harness (prepare / retry / score / posthoc) | `scripts/benchmark_ce.py` |

The deterministic half is tested as follows:

- **Round-trip.** `parse_ce(render_ce(p)) == canonical_pack(p)` and
  `render_ce(parse_ce(t)) == t` for canonical documents.
- **Generated packs.** Hypothesis generated 400 packs that round-trip exactly,
  with adversarial identifiers: `and`, `true`, `#x`, `a b`, non-ASCII. For 150
  valid generated packs, the checker's verdict, reason, frontier and context
  refutation are identical before and after the round-trip.
- **Full suite.** 686 tests in `tests/test_ce.py` pass. The full repository
  suite passes except for the 2 `test_real_skills.py` failures that already
  fail on `main`; they depend on skills installed under `/mnt/skills`.

## Corpus

294 `SKILL.md` files were collected from 15 public repositories at pinned
commits. They are byte-identical to upstream, and every one carries its
license: MIT 126, Apache-2.0 117, CC-BY-SA-4.0 31, MPL-2.0 20. The
repositories are openai/skills, github/awesome-copilot, microsoft/skills,
trailofbits/skills, getsentry/skills, expo/skills, huggingface/skills,
hashicorp/agent-skills, obra/superpowers, cloudflare/skills,
anthropics/skills, cli/cli, neondatabase/agent-skills,
microsoft/aspire-skills and supabase/agent-skills.

The corpus is disjoint from `benchmark/compaction_sources`. Exclusions and
their reasons are in `benchmark/ce_sources/README.md`: non-open licenses,
missing license files, near-duplicates, and files over 60 KB.

The A/B sample is 150 of these skills, drawn by a deterministic round-robin
over repositories. They cover 14 domains; the largest are cloud/devops 28,
AI agents 21, security 17 and testing 14.

## Method

**Arms.** Both arms receive the same source text and the same eight modelling
rules. They differ only in the representation the model writes.

- **JSON arm.** Exactly `frontend.llm.compact()`: the `SYSTEM` prompt plus the
  `developer` runtime-abilities note.
- **CE arm.** Exactly `frontend.llm.compact_ce()`: `CE_SYSTEM`, whose rules
  are the JSON rules reworded only where JSON syntax is named, plus the CE
  grammar summary and one example.

For the labelled scenarios, each arm gets the original benchmark's contract
note appended. Its wording is kept, and "(in backticks)" is added for CE.

**Cases.**

- 150 real skills with one sample each.
- The first 20 of them have 3 independent samples, to measure stability.
- The 32 contract-labelled scenarios from
  `runs/20260921_114226Z_compaction_comparison`, with identical input hashes.

That makes 182 cases and 444 first-round compactions.

**Model execution.** No Anthropic or Azure API key was available in this
environment, so each "model call" was executed by a Claude subagent on the
same model for both arms. Each subagent received the frozen system and user
messages and wrote only its reply. It was instructed not to run code or
validators, not to look at other outputs, and not to revise its reply.

Each subagent handled a batch of up to 12 jobs from a single arm, in hashed
order, so both arms experienced the same batching. This differs from a direct
API call in two ways: the subagent has its own framing, and earlier jobs in a
batch are in its context. Both effects apply equally to the two arms, but
absolute numbers may not transfer to a direct API call.

**Retry.** Each arm gets one retry, triggered only by a parse or schema-gate
error.

- CE retries receive the parser's located message, for example
  `line 7, column 17: expected a backticked identifier, got word 'none'`.
- JSON retries receive the schema-gate message, using the wording of the
  original benchmark's retry.

The retry prompts were frozen before the retry round ran.

**Integrity.** All prompts were frozen with sha256 hashes in `frozen.json`
before any output existed. The scorer refuses to run if a prompt changed.
Outputs are committed verbatim.

**Scoring.** Scoring is deterministic: parse, schema gate, then the checker.
The labelled scenarios are scored with `benchmark_compaction.assess`/`score`,
unchanged from the original benchmark.

## Results

### Labelled scenarios (ground truth known)

| Arm | Valid on first attempt | Valid after retry | Goal exact | unbound protocol | contract protocol | contract goal-only |
|---|---:|---:|---:|---|---|---|
| JSON | 32/32 | 32/32 | 32/32 | 16 TP, 0 FP, 0 FN, 16 TN | 16/0/0/16 | 16/0/0/16 |
| CE | 27/32 | 32/32 | 32/32 | 16 TP, 0 FP, 0 FN, 16 TN | 16/0/0/16 | 16/0/0/16 |

Both arms are perfect. This benchmark cannot separate them any more: the
clarified goal-marker prompt of 2026-09-21 already removed the placement
errors that CE was designed to eliminate.

Neither arm produced a single goal checkpoint (placement-defect count 0 in
both). So the hypothesis that CE removes premature-checkpoint errors could
not be tested here: the prompt fix already removed them for both arms.

### 150 real skills (no ground-truth labels)

| Metric | JSON | CE | Paired test |
|---|---:|---:|---|
| Valid on first attempt | 141/150 (94.0%, 95% CI 89.0–96.8) | 115/150 (76.7%, CI 69.3–82.7) | McNemar p = 1.1e-4 (35 vs 9 discordant) |
| Valid after one retry | 150/150 | 150/150 | — |
| ACHIEVABLE / IMPOSSIBLE / UNKNOWN | 115 / 28 / 7 | 117 / 24 / 9 | IMPOSSIBLE: p = 0.60 (18 vs 14 discordant) |
| IMPOSSIBLE rate on deployed skills | 18.7% (CI 13.2–25.7) | 16.0% (CI 11.0–22.7) | — |
| Median output per compaction (first attempt) | 1,212 characters, ≈319 tokens | 797 characters, ≈211 tokens | 0.65× characters, 0.55× word/punctuation proxy |
| Total output tokens, including retries (≈, characters/3.8) | 55,481 | 42,108 | −24% |
| Median tools / protocol steps / goal atoms | 5 / 6 / 1 | 5 / 6 / 2 | — |
| Packs with a trivial `true` goal | 0 | 0 | — |
| JSON-arm packs expressible in CE and round-tripping exactly | 150/150 | — | — |

The token figures are estimates. `tiktoken` could not download its
vocabulary through this environment's proxy, and the subagent executor does
not report API usage. The figures therefore use the repository's own
`estimate_tokens` (characters ÷ 3.8) and a word/punctuation proxy.

**"IMPOSSIBLE on a deployed skill"** is a proxy, not a label. The
repository's own real-skills test treats it as a probable false refutation.
Here, though, some skills genuinely need tools outside the `developer`
runtime abilities, such as cloud credentials. The 7–9 UNKNOWN verdicts are
abstentions, mostly because the skill spawns subagents (`DYNAMIC_TOPOLOGY`).

### Stability: 20 skills × 3 independent samples

| Metric | JSON | CE |
|---|---:|---:|
| Verdict identical across all 3 samples | 11/20 | 15/20 (paired p = 0.22) |
| Pairwise verdict agreement across samples | 41/60 | 50/60 |
| Goal atom set identical across samples | 4/20 | 5/20 |
| Tool name set identical across samples | 0/20 | 1/20 |
| Mean pairwise Jaccard of tool names | 0.35 | 0.41 |

### Where the two arms disagree

The arms agree on 117/150 verdicts (78%). For comparison, on the same 20
skills the two arms agree 16/20, while two samples of the *same* arm agree
68% (JSON) and 83% (CE) of the time. Cross-arm disagreement is therefore of
the same order as sampling noise.

Its largest category is exactly symmetric. In 9 cases JSON declared all tools
and CE left one undeclared (`MISSING_CAPABILITY`), and in 9 cases the
reverse happened. Which tools a model declares is a semantic decision. It
varies between samples of the same prompt, and changing the output format
does not stabilise it.

This matches the earlier assessment: an explicit task contract, or tool
manifest, that fixes Γ is what removes this variance. The output
representation does not.

### First-attempt failures, and the post-hoc near-miss analysis

| Arm | Invalid on first attempt (all 222) | Cause |
|---|---:|---|
| JSON | 11 | All 11: `"pre": ["x"]`, a list where a formula is required |
| CE | 48 | 45: `Initially true: none.` (grammar 1.0 accepted `none` for `Roles:` and `Protocol:` but not here). 3: genuine syntax slips |

The second finding is a defect in the language design, not in the model. The
model generalised a pattern that the grammar itself taught. Grammar 1.1 (this
branch) accepts `Initially true: none.`.

Re-parsing the **same** recorded round-1 outputs, with each arm's single most
common near-miss accepted (no new model calls; `posthoc.json`):

| Arm | Valid on first attempt, near-miss accepted | 95% CI |
|---|---:|---|
| JSON (list `pre` read as a conjunction) | 222/222 | 98.3–100 |
| CE (grammar 1.1) | 219/222 | 96.1–99.5 |

This part is post hoc and development-on-test. It explains the primary gap;
it does not replace it. A fresh run with grammar 1.1 is needed before
claiming CE's first-attempt validity is 98.6%.

### The original deterministic front-end

On all 294 real skills, `markdown.py`/`prose.py` fell back to
`tool_usage_only` 294/294 times. This extends the 32/32 fallback of the
2026-09-21 assessment from 8 to 294 documents: the heuristic prose reader
never extracts a goal from real-world skills. In the CE design, the
deterministic part is a complete parser for a formal language. It is not a
heuristic reader of free prose, and that is the change this branch makes.

## What this does and does not show

It shows:

- CE is a viable compaction target for current models.
- Everything after the model is deterministic, exact and located in its
  error messages.
- Output is substantially shorter.
- Accuracy on the labelled benchmark is unchanged.

It does not show that CE is more accurate than JSON, and it does not show
that CE reduces false refutations on real skills (18 vs 14 discordant,
p = 0.60). The stability advantage (15/20 vs 11/20) needs a larger sample.

The experiment identifies what dominates end-to-end reliability on real
skills. It is not syntax: both arms produce valid output after one retry.
It is semantic variance in which tools and goals the model chooses. That
points to contract or manifest binding of Γ and review of the goal (intent
fidelity), rather than to further work on output format.

## Limitations

- **Executor.** Subagents on one model, not direct API calls; there is one
  model family and no temperature control. Batches of 12 share context
  within an arm.
- **Sample size.** One sample per real skill except the 20-skill stability
  subset. The skills come from 15 repositories, so they are correlated
  within a repository.
- **No labels for real skills.** Only validity, structure, verdict
  distribution, agreement and stability can be measured there.
- **Token counts** are estimates (see above).
- **Grammar 1.1** was motivated by this run's outputs. Its effect is measured
  post hoc only.
- **Prompt change.** The CE prompt summary gained one parenthetical
  ("or: Initially true: none.") after the run. The frozen prompts in
  `runs/20260926_ce_ab/prompts` are what the models actually saw.

## Reproduction

```bash
pip install -e ".[dev]"
python -m pytest -q tests/test_ce.py
python scripts/benchmark_ce.py prepare runs/NEW --real 150 --stable 20 --samples 3
# run each runs/NEW/prompts/<arm>/*.json through a model; write the reply to
# the matching runs/NEW/outputs/<arm>/*.txt
python scripts/benchmark_ce.py retry runs/NEW      # then run the __r2 prompts
python scripts/benchmark_ce.py score runs/NEW
python scripts/benchmark_ce.py posthoc runs/NEW
```

With an API key, `skillc check SKILL.md --llm --via-ce --llm-runtime developer`
runs the CE path directly.

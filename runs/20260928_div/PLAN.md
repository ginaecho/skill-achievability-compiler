# Diversity test, policy index and small-model arms: plan (pre-registered)

**Timing of the freeze.**
- The test set, runtimes and executor prompts were frozen in commit 44a72e4, before any
  execution.
- This plan, the index procedure and the P2g prompts were committed while executions
  were in progress. At that point about 45 of 170 executions had finished.
- Executors were told to reply only "done", but many returned their outcome in their
  final message, so the analyst saw some outcomes before this commit. Nothing below
  depends on them: the methods, labels and criteria are fixed here, and the index is
  built only by the stated procedure.

## Questions

1. **Diversity.** Is P2g only good for some kinds of skill? We measure it on
   non-developer domains, on two further runtimes, and on created skills that probe
   unfamiliar tool names.
2. **Policy index.** Does an indexing library that the model *looks up* improve P2g?
   The index maps terms to what past executions showed they require, and it grows as
   new executions are labelled.
3. **Small models (steps 3 and 5 of the proposal).** The dataset and splits are defined
   here. The runs themselves are blocked until model weights can be downloaded; see
   "Blocked".

## Test set: `--cases div`, 170 skill-runtime pairs (commit 44a72e4)

| stratum | skills | runtimes |
|---|---|---|
| real non-developer skills (`benchmark/ce_sources_div`) | 100, from 21 domains | assigned by hash: 52 developer-sandbox, 26 offline-workstation, 22 office-assistant |
| real skills already executed in developer-sandbox | 50 | re-run in offline-workstation (25) or office-assistant (25) |
| created skills (`benchmark/ce_sources_created`) | 20 | as stated per skill |

### Runtimes

- `developer-sandbox`: unchanged.
- `offline-workstation`: a shell with installed software only; no network and no
  installs.
- `office-assistant`: text files and web reading only; no code execution and no binary
  output.

### Ground truth

Every pair is executed blindly with the frozen prompt for its runtime.

**Labels (L2, primary):**
- **Achieved:** the executor reports outcome achieved.
- **Confirmed impossible:** blocker `missing_tool_in_runtime`,
  `needs_credentials_or_account` or `forbidden_by_safety_rules`. In
  `offline-workstation` only, `network_or_service_unavailable` also counts, because
  that runtime lacks network access.
- **Inconclusive:** everything else, left out of the decided metrics.

**Sensitivity analyses, reported regardless of outcome:**
- **Strict adjudication.** A separate adjudicator agent, blind to all verdicts, reads
  each achieved report and classifies it as genuine or simulated. Simulated means the
  executor substituted mock data, a mock service or a reimplemented missing tool for
  the skill's own core dependency. The strict reading counts simulated reports as
  inconclusive.
- **Protocol violations.** Executors that broke their runtime's limits (for example,
  network use in `offline-workstation`) are listed in `protocol_violations.txt`. A
  second analysis excludes them.

## Methods

### P2g (`ce_rt`)

Unchanged from `docs/P2G_RUNTIME_BINDING.md`, except that each case uses its own
runtime manifest. The steps are:
- one retry after a located error;
- one repair guided by the counterexample, subject to the guard;
- no pruning.

### P2g + policy index (`ce_idx`)

The same as P2g, but the system prompt also carries a REFERENCE INDEX section
(`llm.render_index_facts`):

- **Known terms.** For each term the deterministic extractor finds
  (`policyindex.extract_terms`) that the index already contains, the section gives:
  - how many attempts mentioned it;
  - the distribution of its requirement class;
  - how often it was core;
  - how often it stopped an attempt;
  - one note.
- **Unknown terms.** Terms the index has never seen are listed as "not in the index",
  with a registry probe. Candidates that look like programs (from code blocks or
  backticks) are looked up once on PyPI and npm, and the result ("found on PyPI",
  "found on npm", or "not found on PyPI or npm") is frozen into the prompt.
- **What it does not add.** No obligations, no suggested substitutes and no veto.

**Index contents.**
- The labelled mentions (`keep: true`) from the 270 prior execution reports, labelled
  by `labels/LABELLER_PROMPT.md`.
- **Prequential growth.** The 170 cases are ordered by `sha256("div-preq:" + id)` and
  cut into 17 batches of 10. The prompts for batch *k* use an index that also contains
  the labelled mentions of the div executions in batches before *k*. Their reports are
  labelled with the same prompt. The index therefore grows as new unknowns are
  resolved.

The repair and guard rounds are as in P2g.

## Success criteria (div set, L2)

### Q1 (diversity, P2g only)

**P2g generalises** if both hold:
- its decided accuracy on the 100 real non-developer skills is at least 0.80;
- its decided accuracy in each of the three runtimes is at least 0.75.

Also reported:
- metrics by domain, stratum, runtime and blocker kind, with Wilson intervals;
- recall on missing-tool impossibles compared with account/credential impossibles.

### Q2 (P2g + index against P2g, the same 170 pairs)

1. **Recall.** Recall of confirmed impossibles rises by at least 10 points, or recall
   on `missing_tool_in_runtime` impossibles rises by at least 15 points. The second
   version needs at least 10 such cases.
2. **False rejections.** They rise by at most 2.
3. **Decided accuracy.** It is at least P2g's.

Also reported:
- exact McNemar tests;
- the prequential curve: index accuracy on batches 1–8 compared with batches 9–17;
- results by stratum;
- how many unknown terms were resolved by the index or by the registry probe.

## Small-model arms (steps 3 and 5)

**Dataset.** One row per (skill, term): the term, its context line, and the labels
`cls`, `core` and `blocked`. It covers the 270 prior reports and the 170 div reports.

**Splits.**
- *Held-out repositories*: leave one repository out, grouped by GitHub organisation.
- *Unseen terms*: a test term never appears in training in any skill.

**Arms.** One base model of 0.5–3B parameters, compared across:
- (a) retrieval of the k most similar labelled mentions in the prompt;
- (b) LoRA fine-tuning;
- (c) neologism embeddings: one learned embedding per term, with the base model
  frozen.

**Metrics.** Macro-F1 on `cls` and accuracy on `core`, on both splits.

**Integration.** The winning arm proposes `needs`, `via` and `runs` clauses as evidence
only, in the same slot as the index facts. P2g's binder, guard and checker still decide
the verdict.

**Distillation (step 5).** The dataset of about 500 checker-valid CE compactions with
execution labels is defined. The target is cost, not accuracy.

## Blocked

Model weights cannot be downloaded in this environment. The network policy rejects
huggingface.co, hf-mirror.com and modelscope.cn, and there is no GPU. The arms run once
the environment allows huggingface.co, and preferably with a GPU. Until then only the
dataset, splits and scripts are delivered.

# Diversity test and the policy index

- **Plan:** [`runs/20260928_div/PLAN.md`](../runs/20260928_div/PLAN.md). The test set was frozen in
  commit 44a72e4. The methods and criteria were frozen in a735fb6. Amendment A (commit d29e5fa)
  was made before any index prompt existed.
- **Data:** everything is under `runs/20260928_div/`.
- **Scoring:** `scripts/score_div.py`.

## Questions

1. Is P2g only good for some kinds of skill?
2. Does an **indexing library** that the model looks up improve P2g? This is a lookup, not a
   memory. Each skill gets a table of facts about the tools it names, drawn from past execution
   evidence, and the table grows as new executions are labelled.

## Test set: 170 skill–runtime pairs, all executed blindly

| stratum | pairs | source |
|---|---|---|
| real non-developer skills | 100 | 21 domains. Repositories: `anthropics/knowledge-work-plugins`, `anthropics/financial-services-plugins`, `alirezarezvani/claude-skills`, `K-Dense-AI/claude-scientific-skills`, `coreyhaines31/marketingskills` (Apache-2.0 / MIT) |
| real skills re-run in a new runtime | 50 | skills already executed in the developer sandbox |
| created skills | 20 | written to probe unfamiliar tools, accounts and devices (CC0) |

The pairs are spread over three runtimes:

| runtime | what it allows | pairs |
|---|---|---|
| `developer-sandbox` | full developer sandbox | 64 |
| `offline-workstation` | shell with preinstalled software; no network, no installs | 54 |
| `office-assistant` | text files and web reading; no code execution, no binary output | 52 |

**Labels (L2):**
- 117 achieved;
- 47 confirmed impossible: 31 missing tool, 10 account or credential, 5 network (offline
  runtime), 1 safety rule;
- 6 inconclusive.

**Strict adjudication.** A separate agent read each of the 117 achieved reports. It judged 19
of them "simulated": most rewrote a missing bundled script themselves, and a few used mock
connectors or shims.

## Q1: does P2g generalise? Yes (pre-registered criterion met)

| slice | recall | false rejections | decided accuracy |
|---|---|---|---|
| **all** | 38/47 | 14/117 | **141/164 = 0.86** [0.80, 0.90] |
| real non-developer (criterion ≥ 0.80) | 10/15 | 10/82 | **0.85** |
| real re-run | 19/23 | 4/25 | 0.83 |
| created | 9/9 | 0/10 | 1.00 |
| developer-sandbox (criterion ≥ 0.75) | 11/13 | 5/47 | 0.88 |
| office-assistant | 16/18 | 5/33 | 0.86 |
| offline-workstation | 11/16 | 4/37 | 0.83 |

**Recall by blocker:**

| blocker | recall |
|---|---|
| missing tool | 24/31 (0.77) |
| account or credential | 9/10 |

On the earlier ext test, missing-tool recall was 12/17.

**Sensitivity analyses:**
- strict adjudication: decided accuracy 125/145 = 0.86;
- excluding the protocol violations listed in `protocol_violations.txt`: 0.87.

## Q2: does the policy index improve P2g?

**Index contents.** 2,097 labelled mentions of 1,297 terms, from 440 execution reports.

**Prequential growth.** The index grows from 1,009 terms (before div batch 1) to 1,272 terms
(before div batch 17).

**Coverage.**
- 157 of the 170 skills had at least one indexed term.
- 67 skills had terms the index had never seen.
- 251 of those unseen terms were probed on PyPI and npm.

| method | recall | false rejections | decided accuracy | missing-tool recall |
|---|---|---|---|---|
| P2g | 38/47 | 14/117 | 141/164 = 0.86 | 24/31 |
| **P2g + index** | **40/47** | **8/117** | **149/164 = 0.91** [0.85, 0.94] | **26/31** |

**Paired comparison** (exact McNemar test on the decided cases):

| labels | index better | index worse | p |
|---|---|---|---|
| L2 | 12 | 4 | 0.077 |
| strict | 10 | 2 | 0.039 |

**Pre-registered criteria:**

| criterion | result |
|---|---|
| (1) recall +10 points, or missing-tool recall +15 points | **not met**: recall +4.3 points, missing-tool recall +6.5 points |
| (2) false rejections rise by at most 2 | **met**: they *fell* by 6 |
| (3) decided accuracy at least P2g's | **met**: +4.9 points |

**Verdict: Q2 fails its pre-registered criterion 1**, so the plan's success condition is not
met. The index did not add the correct rejections it was designed to add. Its benefit is
fewer false rejections: 9 of the 12 improved cases are skills that execution showed to be
achievable.

**Where the index helped.** It gave evidence that a named tool works locally or is optional,
for example:
- `wrangler`, `terraform`, `python3`;
- sibling-skill cross-references shown as "not a tool".

With that evidence, P2g stopped treating those tools as hard requirements.

**Where it hurt.** There were 4 worse cases:
- `phone`;
- `aso` and `expo-animation`, both adjudicated as simulated;
- `skill-installer`, where the index's GitHub facts suggested that GitHub was reachable.

**Prequential curve.** Decided accuracy on batches 1–8 compared with batches 9–17:

| method | batches 1–8 | batches 9–17 |
|---|---|---|
| P2g | 0.91 | 0.82 |
| P2g + index | 0.92 | 0.90 |

So the gap widened as the index grew. This is descriptive only; the batches are small.

**Cost.** The index made the prompts longer. Round-1 replies that failed to parse rose from 14
(P2g) to 29 (index). After the retry, both methods had comparable validity.

## Small-model arms (steps 3 and 5)

**Dataset.** `runs/20260928_div/slm/`: 2,097 rows (term, context line, class, core, blocked),
from `scripts/slm_dataset.py`.

**Splits.**
- leave one organisation out: 17 folds;
- unseen terms: 5 folds.

**Arms** (`scripts/slm_arms.py`):
- retrieval-in-context;
- LoRA;
- neologism: one new trained embedding per term, with the base model frozen.

They share one likelihood-scoring prompt. That design (`slm_arms.py`) needs large models
from huggingface.co, which is blocked. The arms were therefore run in a CPU variant with
classification heads (`slm_train.py`); see "Model arms" below.

**Baselines that did run:**

| method | unseen terms, macro-F1 | held-out organisations, macro-F1 | core accuracy (unseen / held-out) |
|---|---|---|---|
| majority class | 0.06 | 0.10 | 0.52 / 0.53 |
| index lookup (majority label of the same term) | 0.06 (cannot help by construction) | 0.20 | 0.52 / 0.57 |
| character n-gram TF-IDF + logistic regression | **0.41** | **0.26** | **0.69 / 0.63** |

Three points follow:
- A pure lookup cannot generalise to unseen terms.
- Even a lexical model recovers much of the requirement class from the term and its context.
- Held-out *organisations* are harder than unseen terms.

The model arms must beat the lexical baseline to justify a 1–3B model.

**Model arms, trained on CPU in this sandbox** (`scripts/slm_train.py`, plan amendment B).

**Weights.** GPT-2 medium (355M) and RoBERTa-base (125M), from the legacy Hugging Face S3
bucket; it is the only reachable model host.

**Readout.** Two linear heads (cls, core) on the mean-pooled hidden state.

**Splits** (5 folds each):
- unseen terms;
- org5: organisations hashed into 5 groups.

**Baselines on the same splits** (`results_baselines.json`):
- lexical: macro-F1 0.40 (unseen) and 0.20 (org5);
- majority class: 0.06 on both.

| arm | macro-F1, unseen / org5 | class accuracy, unseen / org5 | core accuracy, unseen / org5 |
|---|---|---|---|
| lexical TF-IDF + logistic regression (class-balanced) | **0.40 / 0.20** | **0.62** / 0.52 | **0.69 / 0.63** |
| retrieval (k-NN over frozen embeddings), RoBERTa | 0.27 / 0.13 | 0.59 / 0.50 | 0.68 / 0.60 |
| retrieval, GPT-2 medium | 0.18 / 0.11 | 0.53 / 0.45 | 0.64 / 0.55 |
| LoRA r=8, 3 epochs, RoBERTa | 0.18 / 0.16 | 0.61 / **0.59** | 0.61 / 0.61 |
| neologism (new `<t:term>` embeddings + heads), RoBERTa | 0.12 / 0.11 | 0.57 / 0.55 | 0.60 / 0.60 |
| LoRA, GPT-2 medium | running | | |
| neologism, GPT-2 medium | running | | |

**Reading.**
- No model arm so far beats the lexical baseline on macro-F1. The fine-tuned arms mostly
  predict the frequent classes: LoRA has the best class *accuracy* on held-out organisations
  (0.59 against 0.52), but a lower macro-F1.
- **The comparison is not fully like for like.**
  - The baseline uses class-balanced weights; the model arms use plain cross-entropy, as
    frozen in amendment B.
  - The dataset is small: 2,097 rows, 11 classes, several with fewer than 50 rows.
- **The neologism arm cannot help on the unseen-terms split by construction.** A test term has
  no trained embedding. It is also no better on org5, where most test terms were seen in
  training.
- **On this evidence**, a small model does not yet earn a place next to the lookup index plus
  a lexical classifier.
  - More labelled rows, and class-balanced training, would be needed before trying a
    1–3B model.
  - A class-weighted rerun would be a new, post-hoc arm and has not been run.

**Distillation (step 5).** The dataset of checker-valid compactions with execution labels is
defined, but not trained, for the same reason.

## Caveats

- **Blindness.** Executors were told to reply only "done", but many returned their outcomes.
  The analyst therefore saw outcomes during the run. The methods and criteria were fixed
  before any index prompt existed, and the index is built mechanically.
- **Runtime fidelity.**
  - PyPI and GitHub are reachable in this sandbox, so some "offline" executors used the
    network. These runs are listed and excluded in a sensitivity analysis.
  - Web fetch is mostly blocked for office executors. Those tasks became inconclusive rather
    than confirmed impossible.
- **Labels.** The term labels come from one model labeller with no inter-rater check.
  Labelled terms include some noise, such as `workflow` and `api`.
- **Single model.** One model compacted, labelled, executed and adjudicated.
- **Statistical power.** Only 47 confirmed impossibles; the intervals are wide.

## Recommendation

1. **Keep P2g as the decision procedure.** It generalises across domains and runtimes.
2. **The index is a candidate, not a proven default.** It lowered false rejections and raised
   accuracy, but missed its pre-registered recall criterion. A confirmatory run on fresh
   skills should test "false rejections and decided accuracy" as the primary outcome.
3. **The small-model arms have been run on CPU.** None beats the lexical baseline on
   macro-F1 (see "Model arms").
   - More labelled data and class-balanced training should come before trying a larger
     model.
4. **P2g-grounded,** an attempted improvement of P2g, failed its fresh pre-registered test;
   see [`P2G_GROUNDED_TEST.md`](P2G_GROUNDED_TEST.md).

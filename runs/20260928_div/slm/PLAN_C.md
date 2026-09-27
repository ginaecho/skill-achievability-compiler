# Plan amendment C: more data and a literature-based recipe for the small-model arms

Written on 2026-09-27, before any model was trained on the new data. At that time, labelling
of the new data was in progress and no silver label had been inspected.

## Why

The CPU arms (amendment B) all scored below the lexical baseline on macro-F1:
- retrieval: 0.27 on unseen terms and 0.13 on org5;
- LoRA: 0.18 and 0.16;
- neologism: 0.12 and 0.11.

A literature survey (docs/DIVERSITY_TEST.md, "Model arms") gives the reasons:
- **Frozen mean-pooled embeddings are weak.** kNN should run over *contrastively fine-tuned*
  embeddings (SetFit, arXiv 2209.11055; KNN-BERT, arXiv 2110.02523).
- **Imbalance needs class-balanced heads and logit adjustment** (arXiv 1901.05555,
  arXiv 2007.07314).
- **Initialisation of new tokens.** They should start from the mean of their own subword
  embeddings, not at random (arXiv 2407.05841 and later work).
- **An LLM silver labeller distilled into a small model** is the most effective source of
  extra data (arXiv 2108.13487, arXiv 2308.03279). Two conditions:
  - evaluation stays on clean labels;
  - a "clean data only" control is required (arXiv 2305.17442).

## Data

**Gold.** Report-grounded labels (`labels/out`, LABELLER_PROMPT.md):
- the earlier prior and div reports;
- the 120 gr reports, newly labelled with the same prompt.

Gold rows are the only evaluation data.

**Silver** (`slm/silver/out`, `slm/silver/LABELLER_PROMPT.md`):
- **Source.** 1,747 licensed SKILL.md documents from 10 public repositories, never labelled
  before. They were de-duplicated (exact matches and Jaccard ≥ 0.8) against every benchmark
  skill and against each other (`scripts/slm_silver_corpus.py`).
- **Labels.** Requirement class and core/optional only, from the document alone.
- **Use.** Silver is used for training only.

**Splits** (same hashing as before, over gold rows):
- unseen terms: `sha256("term:" + term) % 5`;
- org5: `sha256("org:" + org) % 5`.

**Leakage control.** In each fold:
- the training data is the gold rows outside the test fold, plus silver rows whose term (for
  unseen terms) or organisation (for org5) is not in the test fold;
- no test term or test organisation reaches training through silver.

## Arms

All arms use distilroberta-base (82M), the only small encoder reachable, on CPU.

| arm | description |
|---|---|
| **A0** | lexical TF-IDF + LR (class-balanced), gold only (the baseline, recomputed on the enlarged gold set) |
| **A1** | A0 + silver |
| **B1g** | SetFit-style: supervised contrastive fine-tuning on gold only, then class-balanced LR heads (cls, core) with post-hoc logit adjustment (τ = 1) |
| **B1** | B1g trained on gold + silver |
| **B2** | B1 + neologism: one new token `<t:term>` per training term, initialised to the mean of the term's subword embeddings and trained jointly |

**B1g fine-tuning** uses the SupCon loss (temperature 0.1), batches of 32 drawn with
square-root class-balanced sampling, 200 steps, AdamW with learning rate 3e-5, and max
length 64.

**B2 details.** Test terms seen in training use their token; unseen test terms keep their
spelling.

**Also reported** for B1 and B2:
- kNN (k = 16) over the tuned embeddings;
- an ensemble that averages the probabilities of the embedding LR and of A1.

## Metrics and criteria

**Metrics.**
- **Primary:** macro-F1 over the 11 classes on gold test rows, pooled over folds, for both
  splits.
- **Secondary:**
  - macro-F1 over the classes with at least 20 gold rows;
  - core accuracy.

**Questions.**
1. **Does silver data help?** Compare A1 with A0, and B1 with B1g. "Helps" means +0.03
   macro-F1 on both splits.
2. **Does the literature recipe beat the lexical baseline?** Compare the better of B1 and
   its ensemble with A1. "Beats" means +0.03 macro-F1 on both splits.
3. **Does the neologism help on top of it?** Compare B2 with B1: +0.02 on org5, and no worse
   than −0.01 on unseen terms. On unseen terms it can only help through better
   training-term representations.

**Stopped arms.** The amendment-B GPT-2 medium LoRA and neologism arms were stopped after 1
of 10 folds to free the CPU. They are not reported.

## Correction (before any full run)

A smoke test on partial data (2 training steps, 250 silver rows) showed the cls head
collapsing onto rare classes: accuracy 0.006. The cause was that "class-balanced LR + post-hoc
logit adjustment" corrects for the class prior twice.

Following Menon et al. (2021), the cls head is now an **unweighted** LR with post-hoc logit
adjustment (τ = 1). The core head stays class-balanced. No full-data result existed when this
was changed.

## Results (2026-09-28; gold evaluation rows: 2,676; silver training rows: 8,206)

Macro-F1 over 11 classes, pooled over 5 folds (`results2_*.json`):

| arm | unseen terms | org5 |
|---|---|---|
| A0 lexical, gold | 0.406 | 0.231 |
| A1 lexical, gold + silver | 0.401 | 0.298 |
| B1g contrastive, gold | 0.388 | 0.274 |
| B1 contrastive, gold + silver | 0.317 | 0.299 |
| B1 + kNN | 0.340 | 0.298 |
| **B1 + ensemble with A1** | **0.438** | **0.345** |
| B2 (B1 + neologism) | 0.291 | 0.266 |
| B2 + ensemble | 0.420 | 0.322 |

Answers to the three questions:

1. **Does silver help?** Not by the criterion.
   - For the lexical model: +0.067 on org5, −0.005 on unseen terms.
   - For the contrastive model: +0.025 on org5, −0.071 on unseen terms.
2. **Does the recipe beat the lexical baseline?** **Yes, but only as the ensemble with the
   lexical model:** +0.037 on unseen terms and +0.047 on org5.
   - The contrastive encoder alone (B1) does not beat A1 on unseen terms.
3. **Does the neologism help?** **No.** B2 against B1 gives −0.026 on unseen terms and −0.033 on
   org5.

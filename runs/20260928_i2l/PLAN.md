# I2L: benchmarking compaction from intent to logical block

Pre-registered on 2026-09-28, before any new model call for this test and before any
block-level metric was computed on any arm.

## Why

Earlier comparisons scored only the final **verdict**. They compared P2g (natural language →
Controlled English → deterministic parser and runtime binder → pack) with the original JSON
compaction (natural language → pack written directly as JSON).

Compaction is the step **intent → logical block**, where the logical block is the pack:
- Tools with via/needs bindings;
- pre/add/del effects;
- the protocol;
- the Goal.

Two things were therefore never measured:

1. **The quality of the logical block itself.**
   - Does the block contain the requirements that execution showed to be core?
   - Does it make optional work mandatory?
   - Does it carry the blocker that really stopped the executor?
2. **What the logical block is worth.** No arm skipped the block: nothing went directly from
   intent to verdict.

The earlier JSON-against-P2g gap also confounds three things:
- the language (JSON against CE);
- the rules and runtime information in the prompt (JSON's prompt has no runtime binding
  rules);
- the procedure (P2g has retry and a guarded repair; JSON has only a retry).

## Test set

**200 skill–runtime pairs**, all executed blindly before this plan, with L2 outcome labels:

| set | pairs | runtimes | outcome labels | gold requirement labels |
|---|---|---|---|---|
| held-out | 40 | developer-sandbox | `runs/20260926_heldout_execution.json` | 38 |
| fresh | 40 | developer-sandbox | `runs/20260926_tpl/execution.json` | 36 |
| gr | 120 | 3 (hash-assigned) | `runs/20261001_gr` (execution/, adjudication.json) | 101 |

**Gold requirement labels** are `runs/20260928_div/slm/rows.jsonl`, rows with sources
`prior` and `gr`. They are report-grounded: for each pair, a labeller read the execution
report and listed every requirement term with:
- its class;
- `core` (the deliverable needed it);
- `blocked` (the runtime lacked it).

These labels were made before this plan, from execution reports, and never from any
compaction.

## Arms

| arm | intent → | logical block? | language | runtime binding rules | retry | guarded repair | new calls |
|---|---|---|---|---|---|---|---|
| **J** | pack | yes | JSON | no (original prompt) | yes | no | none: existing outputs; held-out and fresh only |
| **JB** | pack + bindings | yes | JSON | **same rules as P2g** | yes | **yes, same guard** | 200 (+ retries, repairs) |
| **P2g** | CE → pack + bindings | yes | CE | yes | yes | yes | none: existing outputs |
| **D** | verdict | **no** | — | same runtime description | no | no | 200 |
| ce_gr | CE → pack + bindings | yes | CE | P2g + software grounding | yes | yes | none: gr only; construct-validity arm |

**JB** is P2g translated into JSON: the same ten rules, the same RUNTIME section, the same
binder (`bind_runtime`), the same checker, the same retry and repair rounds and the same
repair guard. The only difference is the surface language the model writes:
- a JSON pack in which each capability also carries `"via"` and `"needs"`;
- instead of a CE document.

Because the CE parser produces exactly this pack + bindings, the two arms are identical from
the binder onwards. JB is `--method json_rt` in `scripts/benchmark_ce_runtime.py`.

**D** has no logical block. It gets:
- the skill;
- the same RUNTIME section;
- P2g's definition of the core deliverable (rule 10).

It must answer ACHIEVABLE, IMPOSSIBLE or UNKNOWN, naming the missing requirements. It uses one
call.

## Metrics

### A. Block metrics (arms with a block: J, JB, P2g, ce_gr; pairs with gold requirement labels)

**Alignment.**
- For each (arm, pair), a blind judge gets two inputs:
  - the block rendered in one canonical form: `render_ce` of the final pre-binding pack with
    its bindings, so JSON and CE blocks look the same;
  - the pair's gold requirement terms, each with its source context, but without core or
    blocked labels.
- For each term, the judge names the Tool(s) of the block whose work uses or depends on it,
  or NONE.
- The judge sees neither the arm nor the verdict. Batches mix arms in a fixed random order.

**Deterministic quantities.** Everything else is computed deterministically from the block:
- **Necessary Tool.** A Tool invoked in the protocol is necessary when the checker (protocol
  scope, core Goal) refutes the pre-binding pack with that Tool dropped.
  - If the pre-binding pack is already refuted, necessity falls back to syntactic: a Tool
    invoked outside every choice branch.
  - The number of such fallback blocks is reported.
- **Witness Tool.** A Tool that is one of:
  - withdrawn by the binder;
  - blocked by the binder;
  - invoked but undeclared (J's way of expressing a missing capability).

**Pooled rates** over (pair, term) items:

| metric | definition |
|---|---|
| **CR: core recall** (primary) | share of gold core terms mapped to at least one necessary Tool |
| **SC: spurious core** (primary) | share of gold optional terms mapped to a necessary Tool |
| **BC: blocker capture** (primary) | share of gold core-and-blocked terms mapped to a necessary witness Tool |
| REP: representation | share of gold terms mapped to any Tool |
| well-formedness | valid on the first reply; valid after retry |

### B. Verdict metrics (all arms, all 200 pairs)

- L2 labels: recall of confirmed impossibles, false rejections of achieved pairs, and decided
  accuracy, with Wilson intervals.
- Paired exact McNemar tests on decided pairs.
- Scheme per set: held-out and fresh use `compare_heldout.label(…, "L2")`; gr uses
  `score_div.labels("L2")` with base `runs/20261001_gr`.

### C. Tokens

- Per pair: the sum over all rounds of system + user prompt tokens + reply tokens.
- Counted with the local GPT-2 BPE tokenizer, the same proxy as the earlier token analysis.
- Reported split into input and output, with the number of calls.

## Questions and analysis

These are comparisons, not pass/fail gates. Every paired difference is reported with a 95%
paired bootstrap interval over pairs (10,000 resamples, seed 0) for the block rates, and with
McNemar for the verdicts.

| question | comparison |
|---|---|
| **Q1. Language:** holding everything else fixed, does writing CE instead of JSON give a better logical block? | P2g against JB, on CR, SC, BC, well-formedness, verdict and tokens |
| **Q2. Rules + procedure:** how much of the old JSON → P2g gap is not language? | J against JB (held-out and fresh) |
| **Q3. Value of the block:** does intent → logical block → checker beat intent → verdict directly? | P2g (and JB) against D, on the verdict and tokens |
| **Construct validity** | see below |

**Construct validity.** The gr test showed that ce_gr's loss came from optional helper steps
made core. So on gr, **SC(ce_gr) > SC(P2g)** is predicted.

If the block metrics do not show this, they are not measuring what we need, and Q1–Q3's
block conclusions are withdrawn. The verdict and token conclusions still stand.

**Judge reliability.**
- A second, independent judge pass covers a fixed 20% of (arm, pair) items, chosen by
  sha256("i2l-rejudge:" + arm + pair) order.
- Term-level agreement (whether a term maps to a necessary Tool) is reported as Cohen's κ.
- If κ < 0.6, the block metrics are reported as unreliable.

## Execution rules

- **Same model family** for all arms and the judge, as in earlier tests.
- **Compaction subagents** read the frozen prompt files and return the model reply verbatim;
  no tools other than reading the prompt and writing the reply.
- **Prompts are frozen** by `prepare` (sha256 in frozen.json) before any compaction.
- **Retry and repair prompts** are generated by the same deterministic code as for P2g.
- **No arm is tuned** after this plan. A prompt error discovered during the run is reported,
  not fixed, unless it prevents parsing for every case, in which case the fix is documented
  here with a date.

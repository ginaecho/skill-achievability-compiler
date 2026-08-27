# Token-economics A/Y/D/V pilot results

Run: `runs/20260827_113833Z_token_economics_pilot`

Date: 2026-08-27. Model deployment: `gpt-5.4`; resolved model:
`gpt-5.4-2026-03-05`. Inference endpoint:
`https://foundary-tzuc06.openai.azure.com/openai/v1`. The Foundry project
endpoint was not contacted.

This is a **single-trial bounded pilot**, not a statistically powered benchmark.
It measures provider-reported token usage on the repository's 15 labelled corpus
cases. The raw one-row-per-call ledger, complete provider `usage` objects,
request hashes, response classifications, and latency are preserved under the
run directory.

## Definitions used

- **A**: provider-reported input + output tokens for one natural-language-to-pack
  compaction, followed by the deterministic checker. Checker tokens are zero.
- **Y**: the existing corpus ground-truth label:
  `1 = IMPOSSIBLE`, `0 = ACHIEVABLE`.
- **D**: `1` when the checker refuted the generated pack, otherwise `0`.
- **V**: provider-reported tokens for one bounded, one-turn simulated execution
  of a `Y=1` skill. The simulator was instructed to use only declared
  capabilities and stop on achievement or a proved block. The oracle-disposition
  baseline was zero tokens.

`V` is therefore a restricted one-turn cost, not natural uncapped runtime waste.

## Aggregate measurements

| Quantity | Result |
|---|---:|
| Cases | 15 |
| `Y=1` impossible | 9 |
| `Y=0` achievable | 6 |
| Total A input tokens | 16,149 |
| Total A output tokens | 3,915 |
| **Total A tokens** | **20,064** |
| Mean / median A per case | 1,337.6 / 1,341 |
| Mean A for `Y=0` | 1,396.3 |
| Mean A for `Y=1` | 1,298.4 |
| Mean / median client-observed round-trip latency per A call | 3,969 / 4,080 ms |
| Mean / median deterministic checker latency | 9.5 / 4.4 ms |
| `D=1` among `Y=1` | 8/9 (88.9%) |
| `D=1` among `Y=0` | **3/6 (50.0% false-refutation rate)** |
| In-scope structural `Y=1` cases | 7 |
| Refuted among in-scope structural cases | 7/7 |
| Reference/generated reason-code agreement among all refutations | 5/8 |
| Total V tokens across nine impossible cases | 2,241 |
| Mean / median V per impossible case | 249 / 246 |
| V range | 195–322 |
| Prompt-cache hits | 0 tokens |
| Reasoning tokens reported | 0 tokens |

Every provider call completed with `finish_reason=stop`; no retry, truncation,
content filter, missing usage, or HTTP error occurred.

The reported provider latency is the client's full `urlopen` round trip,
including network transfer and JSON parsing. The checker-latency mean includes
first-use Python/Z3 warm-up and must not be interpreted as steady-state CPU
cost.

## Per-case results

| Case | Y | D | Checker verdict | A tokens | V tokens |
|---|---:|---:|---|---:|---:|
| `book_flight_ok` | 0 | 0 | ACHIEVABLE | 1,417 | — |
| `budget_ok` | 0 | 0 | ACHIEVABLE | 1,420 | — |
| `detour_ok` | 0 | 0 | ACHIEVABLE | 1,338 | — |
| `choice_informed_ok` | 0 | 1 | IMPOSSIBLE / `NON_CONFORMANT` | 1,422 | — |
| `hallucinated_email` | 1 | 1 | IMPOSSIBLE / `MISSING_CAPABILITY` | 1,408 | 274 |
| `no_establisher` | 1 | 1 | IMPOSSIBLE / `GOAL_UNSAT` | 1,373 | 267 |
| `over_budget` | 1 | 1 | IMPOSSIBLE / `GOAL_UNSAT` | 1,341 | 237 |
| `blocked_precondition` | 1 | 1 | IMPOSSIBLE / `BLOCKED_GUARD` | 1,188 | 222 |
| `deadlock_unobserved` | 1 | 1 | IMPOSSIBLE / `MISSING_CAPABILITY` | 1,295 | 274 |
| `missing_tool_chain` | 1 | 1 | IMPOSSIBLE / `MISSING_CAPABILITY` | 1,306 | 204 |
| `spurious_payload` | 1 | 0 | ACHIEVABLE | 1,361 | 322 |
| `spurious_intent` | 1 | 1 | IMPOSSIBLE / `MISSING_CAPABILITY` | 1,195 | 246 |
| `recursion_ok` | 0 | 1 | IMPOSSIBLE / `GOAL_UNSAT` | 1,484 | — |
| `two_goals_one_missing` | 1 | 1 | IMPOSSIBLE / `MISSING_CAPABILITY` | 1,219 | 195 |
| `choice_one_branch_ok` | 0 | 1 | IMPOSSIBLE / `MISSING_CAPABILITY` | 1,297 | — |

The three false refutations arose in LLM compaction, not in the labelled
reference packs: the generated packs for `choice_informed_ok`, `recursion_ok`,
and `choice_one_branch_ok` did not faithfully preserve the source semantics.
This is exactly the untrusted-front-end risk the paper separates from
pack-relative checker soundness.

The raw `8/9` detection count is not a population sensitivity estimate. Two
`SPURIOUS` cases deliberately represent payload/intent residues outside the
static checker's scope. `spurious_intent` happened to be refuted because its
generated pack invented a missing `schedule_meeting` act, not because the
checker detected the intended intent-fidelity residue. The seven structural
cases were all refuted, but they are constructed benchmark cases and cannot
estimate detection on naturally occurring failures.

Reason-code agreement between the labelled reference pack and generated pack
was only **5/8 among refutations**. In particular,
`deadlock_unobserved` changed from reference `NON_PROJECTABLE` to generated
`MISSING_CAPABILITY`, and `two_goals_one_missing` changed from reference
`GOAL_UNSAT` to generated `MISSING_CAPABILITY`. Exact reason agreement is not
required for a valid refutation, but these changes show that source-to-pack
fidelity needs separate adjudication.

## Economic calculation and why it does not establish a win

### Primary pre-registered result at one execution

For `K=1`, the conditional means are:

```text
a0 = E[A | Y=0]          = 1,396.33 tokens
a1 = E[A | Y=1]          = 1,298.44 tokens
B  = E[D*V | Y=1]        =   213.22 tokens
pi* = a0/(B-a1+a0)       = 4.49
```

Because `pi* > 1` and `B < a1`, **no finite break-even prevalence exists in
the admissible range at one execution per source version**. Even if every
deployed skill were impossible, the measured one-turn avoidable cost would not
repay its own gate cost.

### Secondary reuse calculation

If all V calls are naively treated as avoidable, only V for raw detected cases
is credited, and the same V repeats unchanged on every execution:

```text
A_total                         = 20,064 tokens
sum(Y * D * V), K=1             =  1,919 tokens
net saving, K=1                 = -18,145 tokens
naive reuse break-even K        = 20,064 / 1,919 = 10.46
```

Under those strong assumptions, the token ledger crosses zero at approximately
**11 executions per source version** for this fixed corpus mixture. This is a
secondary reuse multiplier, not the pre-registered prevalence estimand.

If credit is revoked for both the monolithic-runtime deadlock mismatch and the
out-of-scope `spurious_intent` hit, credited V is **1,399 tokens** and the
secondary reuse crossover is **14.34 executions**. This conservatively keeps
the cost of gating every case while removing benefits that were not faithful
detections of the intended construct.

That number is **not a valid product claim**:

1. The pre-registered quality gate failed: 3/6 achievable cases were falsely
   refuted. Economic savings cannot compensate for blocking achievable work.
2. `deadlock_unobserved` was labelled impossible under the multi-agent
   projection semantics, but the monolithic runtime simulator selected the
   favorable `DELIVER` branch and returned `achieved`. Its generated pack also
   changed the failure from `NON_PROJECTABLE` to `MISSING_CAPABILITY`. Both D
   and V are therefore construct-mismatched.
3. The runtime prompt explicitly stopped once it recognized a block. This
   measures the cost of re-reading an explicit failure disclosure, not an
   operational tool-using execution. It does not represent retrying agents,
   tool calls, multi-turn execution, or uncapped runtime waste.
4. One trial cannot estimate stochastic variance or confidence intervals.
5. The 9/15 impossible prevalence and the raw detection rates are properties of
   this constructed corpus, not deployment-population estimates.
6. A measured one-call A path used an 8,000 completion cap and no schema retry
   or repair. It is an optimistic lower bound for entry points that retry up to
   three provider calls.

## Conclusion

This pilot successfully measured **A, Y, D, and a bounded V**, but it does not
support a positive token-saving conclusion. At `K=1`, the pre-registered
analysis has **no admissible break-even prevalence**. The assumption-laden raw
reuse calculation requires about 11 repetitions, or 14.34 after revoking
construct-mismatched credit, and the compaction quality gate failed.

The next benchmark must first improve or control source-to-pack fidelity, then
use a runtime harness whose execution semantics match each case (especially
multi-agent cases), repeated trials, and pre-registered multi-turn/token caps.

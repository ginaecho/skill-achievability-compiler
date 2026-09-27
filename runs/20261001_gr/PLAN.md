# P2g-grounded: fresh blind test (pre-registered)

**Freeze.**
- The test set, runtimes, inventory snapshot and executor prompts were frozen in commit ac1289c,
  before any execution.
- This plan was committed before any compaction (`prepare`) was run on the `gr` cases.
- About 35 of the 120 executions had finished when it was committed. Executors reply "done",
  but a few returned their outcome anyway. Nothing here depends on those outcomes.
- **Development evidence.** The only evidence behind the design is the div set (a separate
  development run, `runs/20260928_div/dev_ce_gr`) and the P2g error analysis on div and ext.
  Neither contains a `gr` skill.
- **Changes after this commit.** If the div development run exposes an implementation bug, the
  fix and a dated amendment will be committed before `prepare` runs on `gr`. After that, nothing
  about the methods changes.

## Question

Does **P2g-grounded** (`ce_gr`) decide achievability better than **P2g** (`ce_rt`) on skills
neither method has seen?

## Method under test: `ce_gr`

`ce_gr` is P2g plus three generic changes, none tied to a particular skill or tool.

**(R) Grounded refutation.**
- The checker may answer IMPOSSIBLE only when a *witness* exists: a capability that the runtime
  binder withdrew or blocked (tool withdrawn, resource blocked, software unavailable).
- An IMPOSSIBLE with no witness is purely structural (for example, a goal unreachable because of
  how the document was written). It becomes UNKNOWN, with reason `STRUCTURAL:`.
- This is applied when scoring, so it can be switched off as an ablation.

**(S) Software grounding.**
- The model names the specific programs a step depends on, with a `runs` clause (prompt rule 11).
- It also names `via macos_desktop`, `gpu` or `usb_instrument` when a step needs another
  operating system, a GPU or a device.
- The binder resolves each program against the runtime's software policy:

  | runtime | software policy |
  |---|---|
  | `developer-sandbox` | installable |
  | `offline-workstation` | preinstalled |
  | `office-assistant` | none |

- Under the preinstalled policy, programs are checked against the machine inventory in
  `src/skillc/data/runtimes/inventory.json`, snapshotted when the test was frozen.
- An unresolvable program withdraws its capability.

**(F) Documented fallbacks.**
- A fallback the skill itself documents (for example, "if no CRM is connected, ask for an
  export") is written as a branch that uses only runtime tools.
- Inventing a fallback is forbidden.

**Unchanged from P2g:** one retry after a located error, one repair guided by the
counterexample and subject to the guard, and no pruning.

## Test set: `--cases gr`, 120 skill-runtime pairs

**Skills.**

| source | skills |
|---|---|
| fresh skills (`benchmark/ce_sources_gr`), from repositories not sampled before | 50 |
| unused skills from `ce_sources` | 35 |
| unused skills from `ce_sources_ext` | 35 |

**Runtimes.** Each pair gets a runtime by hash:
`RUNTIMES_DIV[sha("gr-rt:" + id) % 3]`, which is one of developer-sandbox, offline-workstation
or office-assistant.

**Execution.** Every pair is executed blindly with the frozen prompt for its runtime
(`executor_prompt_*.txt`). The prompts differ from div as follows:
- no replacing, stubbing or mocking of a missing tool;
- a missing file bundled with the skill is reported as `skill_files_missing`;
- the executor behaves as its runtime allows even where the sandbox is more permissive.

## Labels

**L2 (primary; the same rule as in div):**
- **Achieved:** the executor reports outcome achieved.
- **Confirmed impossible:** blocker `missing_tool_in_runtime`, `needs_credentials_or_account`
  or `forbidden_by_safety_rules`. In `offline-workstation`, `network_or_service_unavailable`
  also counts.
- **Inconclusive:** everything else, including `skill_files_missing` (our corpus holds only
  SKILL.md, so this is an artefact of the test, not of the runtime), `skill_underspecified`
  and `needs_human_or_physical`. Inconclusive pairs are left out of the decided metrics.

**Sensitivity analyses, reported regardless of outcome:**
1. **Strict.** A blind adjudicator judges each achieved report as genuine or simulated.
   Simulated reports become inconclusive.
2. **No violations.** Executors that broke their runtime limits are listed in
   `protocol_violations.txt` and dropped.
3. **L2 + physical.** `needs_human_or_physical` counts as confirmed impossible, since a missing
   device is a missing capability.

## Comparison and criteria (L2, decided pairs)

`ce_gr` **passes** if all three hold:
1. its decided accuracy is at least P2g's;
2. its false rejections (achieved pairs judged IMPOSSIBLE) are no more than P2g's;
3. its recall of confirmed impossibles is at most one case below P2g's.

**Also reported:**
- an exact McNemar test on decided pairs, where p < 0.05 is called a significant improvement;
- Wilson intervals;
- the slices by runtime and by source.

**Ablations** (descriptive; they do not enter the pass/fail decision):
- **(a) `ce_gr` without R:** scored with `--grounded no`, to isolate S + F.
- **(b) P2g with R:** `ce_rt` scored with `--grounded yes`, to isolate R.

The UNKNOWN verdict counts as "not IMPOSSIBLE" for both methods, as in every earlier test.

## Operational details

- Both methods run on the same 120 pairs, in the same batches, with the same compaction model
  and the same batch prompt.
- Executor reports are copied into `execution/` with personal identifiers scrubbed.
- Results go to `runs/20261001_gr/{gr_ce_rt,gr_ce_gr}`.

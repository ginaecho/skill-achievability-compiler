# P2g + tool-policy library (v1 veto): plan and success criteria (pre-registered)

This plan is committed together with:
- the frozen library (`src/skillc/data/toolpolicy/library.json`, v1.0, sha256
  `d164fa0570dabf7fff082a58071159859a8e693025cd887259d88e1e3988ba43`);
- the veto code (`toolpolicy.core_lines`, `unmet`, `veto`);
- the harness option `score --veto none|core|any`;
- the test set definition (`--cases ext`).

All of this is committed before any test-set prompt is answered and before
any test-set skill is executed. After this commit, the library, matcher,
veto rule, binder and prompts are not edited until scoring is done. A bug
fix, if one is forced, is reported with its diff and both sets of results.

## Motivation

TPL v0 put the library into the compaction prompt. The model still decided
whether a requirement was core or optional, and its substitute hints pushed
real requirements onto branches that pruning removed
(`docs/TOOL_POLICY_LIBRARY_20260926.md`). P2g had the best results. The
question now is whether the library adds recall to P2g when it is used only
as **deterministic evidence** and never shown to the model.

Library v1 differs from v0 in these ways, all made after the fresh-set
results and before this test set was drawn:
- `agent_spawn` evidence is tightened (explicit Task tool, dispatching
  subagents, parallel, fresh or isolated agents);
- "Expo Go" is removed from `mobile_device`;
- new entries: `apple_toolchain`, `vscode_joyride`, `codex_image_gen`,
  `azure_mcp`, `huggingface_mcp`.

v1 was tuned on the dev, held-out and fresh sets, so none of them can test
it. This test set is its first independent test.

## Methods (on the same test set)

- **P2g** (`ce_rt`): runtime-bound CE, one located-error retry, one
  counterexample-guided repair with the repair guard, no pruning. This is
  exactly the P2g of the held-out and fresh runs. The prompt contains no
  library content.
- **P2g + core veto** (primary). P2g's verdict, overridden to IMPOSSIBLE
  (reason `LIBRARY_VETO`) when the library matches a requirement that the
  runtime cannot meet in the skill's **core statement**. The core statement
  is the frontmatter plus the title and introduction before the first `## `
  heading. A requirement is unmet when:
  - a resource is not granted;
  - a runtime tool is absent;
  - a program is unavailable or needs another OS;
  - an effect is forbidden by `forbid_effects`.

  The rule is deterministic and independent of the LLM, and it applies even
  when the compaction is invalid.
- **P2g + any veto** (secondary). The same rule, matching anywhere in the
  skill.
- **Library veto alone** (secondary). IMPOSSIBLE iff the core veto fires.

No json baseline is run (budget). The json-vs-P2g question was answered
on 74 pooled held-out skills.

## Test set ("ext", 120 skills)

1. **The 64 remaining skills of the original corpus**
   (`benchmark/ce_sources`). This is every skill in `select_real`'s order
   not used by the A/B, held-out or fresh sets. They come from the same
   repositories that seeded the library, so this part is in-distribution.
2. **56 skills of the new extension corpus** (`benchmark/ce_sources_ext`,
   137 skills from 6 repositories, 3 of them new to this project). They are
   taken round-robin over repositories in `sha256("ext-test:" + id)` order.
   This part is out-of-distribution for the library.

No test skill was compacted, executed or read before this commit. The
collection script parsed each file only for license, size and duplicate
checks.

## Ground truth

- **Every one of the 120 skills is executed blindly.** The executor sees
  only the skill and not any verdict. It uses the strengthened executor
  prompt of the fresh run, unchanged except for the skill path
  (`executor_prompt.txt`, committed here).
- **Labels:** L1 and L2 as before; L2 is primary.
  - Confirmed impossible: `missing_tool_in_runtime`,
    `needs_credentials_or_account`, `forbidden_by_safety_rules`.
  - Achieved: executor outcome `achieved`.
  - Everything else is inconclusive and excluded from decided metrics.

## Success criteria (L2, primary = P2g + core veto, compared with P2g on the same 120)

1. **Recall gain.** Recall of confirmed impossibles rises by at least
   10 percentage points over P2g. If P2g misses fewer than 4 confirmed
   impossibles, this criterion cannot be tested, and that will be stated.
2. **Few added false rejections.**
   - The veto adds at most 2 false rejections: executor-achieved skills
     that P2g did not reject but the veto does.
   - Among the decided skills the veto flips to IMPOSSIBLE, precision is at
     least 0.75.
3. **Net gain.** Decided accuracy of P2g + core veto is at least P2g's.

Reported regardless of outcome:
- precision, recall, false rejections, decided accuracy and Wilson intervals
  for every method;
- exact McNemar test between P2g + core veto and P2g;
- the same metrics split by corpus part (original / extension);
- every veto that fires, with the line and text that triggered it;
- L1 metrics.

## Known limitations, stated in advance

- The library was learned in this same runtime, so generalisation to other
  runtimes is untested.
- The veto can only add IMPOSSIBLE verdicts. It cannot fix P2g's false
  rejections.
- Executor labels are one attempt by one agent. An `achieved` label can be
  wrong where the agent substituted a local stand-in for the real
  deliverable.

## Outcome (recorded after scoring)

- **Criterion 1** (recall gain at least 10 points): not met, and formally
  untestable. P2g misses only 2 confirmed impossibles; the veto gains 0.
- **Criterion 2** (added false rejections): not met. The veto adds 4 false
  rejections; the precision of its flips is 0/4.
- **Criterion 3** (net gain): not met. Decided accuracy falls from 103/115
  (P2g) to 99/115.

No code, library or prompt was changed after this plan was committed. One
malformed executor result file (a trailing comma) was fixed at collection.
See `docs/LIBRARY_VETO_EXT_20260927.md`.

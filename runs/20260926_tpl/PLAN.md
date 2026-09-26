# Tool-policy library (TPL) v0: plan and success criteria (pre-registered)

This plan is committed together with the frozen library
(`src/skillc/data/toolpolicy/library.json`, v0.1) and the code, before any
fresh-set prompt is answered and before any fresh skill is executed. After
this commit, the library, matcher, binder and prompts are not edited until
scoring is done. If a bug forces a change, it is reported with its diff and
both sets of results.

## Motivation

The phase attribution of P1's errors: 0 in CE → logic block; 4 of 5 missed
impossibles in the checking rules; 1 of 5 in NL → CE. P1 trusts the LLM's
`via`/`needs`; when these are omitted or too coarse, nothing is left to
reject. TPL moves accumulated requirement knowledge out of the model into
checked data.

## Method TPL (`--method ce_tpl`)

1. **Matcher (deterministic).** Library entries map evidence patterns in
   SKILL.md to a requirement of one of four kinds:
   - a resource (`needs`);
   - a runtime tool (`via`; includes `agent_spawn` and MCP servers);
   - a program (`runs`);
   - an effect class (`effect`).

   Each match is an obligation, with its line and its known local substitute.
2. **Compaction (LLM).** P1's prompt, plus the `runs`/`effect` clause
   documentation, the runtime's forbidden effects, and the skill's obligation
   list. Every obligation must be carried by some Tool, on a skippable branch
   if that work is optional. There is no waiver statement.
3. **Coverage check (deterministic).** An unmet obligation, like a parse
   error, triggers one located-error retry. The final reply is scored even if
   an obligation is still unmet; unmet obligations are recorded.
4. **Binder with library (deterministic):**
   - `effect` in the runtime's `forbid_effects` (`writes_external`,
     `publishes`) → a `policy:` guard that never holds;
   - `runs` of a program the library marks unavailable, or needing another
     OS → the Tool is withdrawn;
   - `spawn` when the runtime has no `agent_spawn` → an act of the missing
     capability;
   - runtime branch pruning on.
5. **Repair.** One counterexample-guided repair, as P2. The guard rejects any
   repair that changes the Goal, drops a `needs`/`runs`/`effect`, or leaves a
   new obligation uncovered.
6. **Verdict.** The protocol-scope verdict of the final pack.

The library is seeded from the 110 existing execution reports (dev, control,
held-out). Every entry lists its provenance.

## Test set ("fresh")

- The next 40 skills in the A/B's stratified order (`select_real`), skipping
  the 150 A/B skills and the 40 held-out skills. None was compacted,
  executed or read before this commit; only the IDs were listed, to check
  the selection.
- Methods on the same 40 skills:
  - `json` (original);
  - `ce_rt` (P1, then P2g: repair and guard, no pruning, exactly as before);
  - `ce_tpl`.

  Replies are written by subagents answering the frozen prompts, without
  running code.
- **Labelled regression:** `ce_tpl` also runs on the 32 contract scenarios.
- **Ground truth:** every fresh skill is executed blindly with the earlier
  executor prompt, strengthened on two points. Connector and MCP tools must
  not be called even if present. Every command runs with the work directory
  as the current directory, and nothing is written outside it. Labels are
  L1/L2 as before; L2 is primary.

## Success criteria (fresh set, L2, primary verdict)

1. **Recall well above P2g.** TPL's recall of confirmed-impossible skills
   exceeds P2g's on the same set by at least 20 percentage points, *and*
   TPL's recall is at least 0.75.
2. **No more false rejections than P2g.** TPL's false rejections on
   executor-achieved skills are no more than P2g's on the same set.
3. **Labelled.** 16/16 impossible refuted, 0 false refutations.

Reported regardless of outcome:
- precision, decided accuracy, paired McNemar against json and P2g;
- unmet obligations;
- ablations, all deterministic re-scorings of the same TPL replies:
  - binder without the library;
  - no repair round;
  - no pruning.

If the fresh set contains fewer than 5 L2-confirmed impossibles, criterion 1
cannot be meaningfully tested. That will be stated rather than claimed.

## Known limitations, stated in advance

- **Seeding.** The library is seeded from executions in this same
  environment, so its generalisation to other runtimes is untested.
- **Program probe.** In v0 the probe consults the library catalogue plus
  host PATH presence. Absence from PATH is never taken as unavailability.
- **Sample size.** n = 40 again gives wide intervals.

## Amendments log

- After commit c4dee58, before any reply was scored:
  - `--no-library` scoring flag, for the pre-registered "binder without
    library" ablation;
  - each tagged scoring now writes its packs to its own `packs<tag>`
    directory, so ablations cannot overwrite the primary packs.

  Neither change affects the method or the primary scoring.

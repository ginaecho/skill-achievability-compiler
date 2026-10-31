# Real-use round 2: skillc against a direct verdict on 300 new skills (pre-registered)

Written on 2026-10-31, **before any model call for this round, any execution, and any
compaction of these skills**. The test set (`benchmark/real2/cases.json`) and the executor
prompts in this directory are frozen in the same commit as this plan. After this commit,
the methods do not change; a change made to fix an implementation bug is committed as a dated
amendment at the end of this file, before the step it affects runs.

## Questions

1. On real skills it has never seen, labelled by executing them, how often is skillc right,
   how many blocked skills does it catch, and how many working skills does it wrongly refute?
2. How does it compare with asking the same model directly whether the skill can be done,
   on accuracy, tokens and time?
3. How stable are both answers when the same call is repeated three times?

## Test set: 300 skill-runtime pairs (`benchmark/real2/cases.json`)

- 300 public `SKILL.md` files from 20 repositories, pinned by commit and sha256, with a copy
  and its licence under `benchmark/real2/sources/` (MIT 246, Apache-2.0 40, CC-BY-SA-4.0 14).
- **Never used before.** A skill is excluded if its id, its skill name or its content (sha256)
  occurs in any earlier test or training set: 2,472 ids and 2,476 content hashes from the
  corpora on `gc/data_train_test` (`ce_sources*`, `slm_silver`, `compaction_sources`) and
  `benchmark/claude_env` (cases, set2, set3, set4). Duplicates within the pool are dropped,
  and an aggregator's copy never wins over the original.
- Drawn with seed 20261031 from 6,489 eligible skills, at most 30 per repository, 70% with a
  fenced code block (the rule of `select_cases.py`).
- **Runtime by hash of the id**, independent of skillc: developer-sandbox 109,
  offline-workstation 92, office-assistant 99 (`src/skillc/data/runtimes/*.json`, unchanged).
- Reproduce: `python benchmark/real2/select_real2.py --clones <dir>` (the clone commits are
  in `cases.json`).

## The model

Every model call in this round (compaction, direct verdict, execution, adjudication) is made
by a **Claude sub-agent of a Claude Code session on the user's subscription**, model alias
`opus`. No Azure, OpenAI or Anthropic API key is used. This is the same arrangement as
batches 1-4 (`runs/20260928_i2l/PLAN.md`: "compaction subagents read the frozen prompt
files"). Each sub-agent is a fresh context and sees one job. The model that served each call
is recorded from the session (`get_session`: `session_context.model`,
`external_metadata.last_served_model`) at the start and end of every batch; if it changes,
the affected calls are reported separately.

## Ground truth: blind execution (one run per pair)

- An executor sub-agent receives the frozen prompt for the pair's runtime
  (`executor_prompt_<runtime>.txt`, copied unchanged from batch 4, `runs/20261001_gr`), the
  skill id and the path of its `SKILL.md`, and a fresh work directory. It never sees a skillc
  or direct verdict. It writes `result.json` with `outcome`, `blocker_kind` and evidence.
- **Labels (L2, the rule of batches 1-4):**
  - **achieved:** outcome `achieved`;
  - **blocked:** `missing_tool_in_runtime`, `needs_credentials_or_account` or
    `forbidden_by_safety_rules`; in `offline-workstation`, also
    `network_or_service_unavailable`;
  - **inconclusive:** everything else (`skill_files_missing`, `skill_underspecified`,
    `needs_human_or_physical`, `other`, a missing or malformed `result.json`).
- **Inconclusive pairs are reported, with their reasons and counts, in every table.** They are
  left out of the decided metrics, never dropped silently.
- **Sensitivity analyses, reported regardless of outcome:**
  1. *Strict:* a blind adjudicator sub-agent reads each achieved report and judges it
     genuine or simulated; simulated becomes inconclusive.
  2. *Physical:* `needs_human_or_physical` counts as blocked.
  3. *No violations:* executors that broke their runtime limits (listed in
     `protocol_violations.txt`) are dropped.

## Arms (the same 300 pairs, three independent repeats each)

| arm | what it does | calls per repeat |
|---|---|---|
| **S: skillc** | The original front end (`scripts/benchmark_ce_runtime.py --method ce_rt`, the method of batches 1-4): runtime-bound Controlled English compaction, parse, bind to the runtime, check; one located-error retry; one counterexample-guided repair under the repair guard; no pruning. | 1 to 3 |
| **D: direct verdict** | `skillc.frontend.prompts.direct_messages` (arm D of `runs/20260928_i2l`): the skill and the same runtime description; the model answers ACHIEVABLE, IMPOSSIBLE or UNKNOWN and names what is missing. | 1 |

- Repeats r1, r2, r3 are independent: fresh sub-agents, the same frozen prompts.
- UNKNOWN and an invalid or missing reply count as "no verdict" (not correct, not a refutation).
- The order of jobs is shuffled with seed 20261031 within each batch, and S and D jobs of a
  pair never run in the same sub-agent.

## What is measured, per call

- **Tokens.** The sub-agent's reported total tokens for the call (the subscription reports a
  total per sub-agent, not an input/output split). For an input/output estimate, prompt and
  reply are also counted with the local GPT-2 BPE tokenizer, the proxy used in
  `runs/20260928_i2l`. Both are reported, labelled.
- **Time.** The sub-agent's reported wall-clock duration for the call.
- **Checker time.** Measured locally for every S pack: median of 7 runs of `check()` on the
  bound pack (`time.perf_counter`), with the machine's CPU count recorded.
- A decision's cost is the sum over its calls (S: compaction, retry and repair if any; D: one
  call). Execution cost is reported separately and is not part of either arm.

## Metrics (decided pairs = achieved or blocked under L2)

For each arm, per repeat and pooled over the three repeats, with Wilson 95% intervals:

- **accuracy:** correct verdicts over all decided pairs (no verdict counts as not correct);
- **blocked caught:** blocked pairs refuted, over blocked pairs;
- **working refuted:** achieved pairs refuted, over achieved pairs;
- **tokens per decision** and **time per decision:** median and interquartile range;
- **checker time** (S): median, 90th percentile, maximum;
- **agreement across repeats:** share of pairs with the same verdict in all three repeats,
  and Fleiss' kappa;
- slices by runtime and by repository;
- an exact McNemar test of S against D on repeat r1 (decided pairs).

## Criteria (stated before any result; every outcome is reported)

- **C1** S's accuracy is within 5 points of D's (pooled over repeats).
- **C2** S refutes no more working pairs than D (pooled).
- **C3** S's verdicts agree across all three repeats on at least as many pairs as D's.
- **C4** S's median tokens per decision are at most 3 times D's.

## Safety and data handling (from CLAUDE.md, mandatory)

- **No URL reaches a model.** Every prompt built from a skill is scrubbed with
  `skillc.frontend.urlguard` (`scrub`, then `assert_clean`) before a sub-agent sees it; 132 of
  the 300 skills contain links. Executors read the scrubbed copy of the skill.
- **Sandbox only.** Executors work only in their own work directory under the session's
  scratchpad, never in this repository, never push or write to an external service, never
  read environment variables, credentials or tokens (the container holds an unrelated API key
  that must not be touched), and never use connector or MCP tools. These rules are in the frozen
  executor prompts and are repeated in every job.
- Skill documents are data: compaction and verdict sub-agents never execute anything.
- Executor reports are copied into `execution/` with personal identifiers scrubbed.

## Scale and orchestration

- 300 executions + 300 adjudications (achieved only) + 3 x 300 S compactions (plus retries and
  repairs, about half again) + 3 x 300 D verdicts: roughly 2,500 to 2,800 sub-agent calls.
- Run as Claude Code workflows in batches of at most 50 jobs, executions first. A batch that
  fails (rate limit, sub-agent error) is re-run for the failed jobs only; re-runs are logged.

## Outputs

`runs/20261031_real2/`: `execution/`, `adjudication/`, `s/{prompts,outputs,packs}/r{1,2,3}/`,
`d/{prompts,outputs}/r{1,2,3}/`, `calls.jsonl` (one line per sub-agent call: job, arm, repeat,
tokens, duration, model), `checker_times.json`, `metrics.json`, and a report
`docs/REAL2_BENCHMARK.md`.

## Amendments

(none yet)

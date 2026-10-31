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

- 300 public skills from 19 repositories, pinned by commit, each copied as it is installed:
  its whole folder (`SKILL.md` and 1,529 bundled scripts, references and templates in 210
  skills) plus 1,855 support files in 128 skills (its plugin's shared files, and the other
  files and skill folders of its repository that `SKILL.md` refers to), every file with its
  sha256, copied with the licence under `benchmark/real2/sources/` (MIT 255, Apache-2.0 34,
  CC-BY-SA-4.0 11).
- **Never used before.** A skill is excluded if its id, its skill name or its content (sha256)
  occurs in any earlier test or training set: 2,472 ids and 2,476 content hashes from the
  corpora on `gc/data_train_test` (`ce_sources*`, `slm_silver`, `compaction_sources`) and
  `benchmark/claude_env` (cases, set2, set3, set4). Duplicates within the pool are dropped,
  and an aggregator's copy never wins over the original.
- **Not a near-copy.** A skill is also excluded if it shares half or more of its five-word
  phrases (Jaccard of 5-word shingles >= 0.5) with any earlier document, so a renamed or lightly
  edited copy of a used skill is out (72 excluded); drawn skills are below 0.5 with each other
  too. The largest overlap left is 0.21 with an earlier document and 0.42 within the set.
- **Not the same skill in other words.** With each document's own name masked, the TF-IDF
  cosine (words and word pairs; weights over the earlier documents and the eligible pool) is
  below 0.40 against every earlier document and every other drawn skill. This catches a skill
  revised under a new product name and skills generated from one template with the name
  swapped, which the phrase rule misses. The line was set before any run by reading the
  highest-scoring pairs: every pair at 0.44 or above was the same skill or one template; the
  highest pairs left are 0.39 with an earlier document (the same four coding principles
  written as a different skill) and 0.37 within the set (two skills of one vendor pack doing
  different jobs). Applied while drawing.
- **User-facing.** The frontmatter has a name and a description and does not set
  `disable-model-invocation: true` (a repository's own helper command; 101 excluded).
- **A real skill, in scope.** Not a test fixture (a `tests` or `fixtures` folder on its path),
  not a blank authoring template (first heading a placeholder such as "# Skill Name"), and
  not an offensive-security skill (marked `risk: offensive`, or red-team, attack-chain,
  exploit or penetration-testing work in its name, description or category), because
  executors really attempt each skill. Applied while drawing, so a skipped skill only frees
  its slot for the next one in the seeded order. In all 17 were skipped while drawing:
  1 template, 2 fixtures, 4 offensive-security, 4 the same skill as an earlier document and
  6 the same skill as another drawn one (`skipped_while_drawing` in `cases.json`).
- Drawn with seed 20261031 from 6,424 eligible skills, at most 30 per repository, 70% with a
  fenced code block (the rule of `select_cases.py`).
- **Runtime by hash of the id**, independent of skillc: developer-sandbox 110,
  offline-workstation 76, office-assistant 114 (`src/skillc/data/runtimes/*.json`, unchanged).
- Reproduce: `python benchmark/real2/select_real2.py --clones <dir>` (the clone commits are
  in `cases.json`); check: `python benchmark/real2/verify_real2.py <dir>` (every rule above, and
  every copied file against its pinned commit; result on 2026-10-31: no problem found).

## The model

Every model call in this round (compaction, direct verdict, execution, adjudication) is made
by a **Claude sub-agent of a Claude Code session on the user's subscription**. No Azure, OpenAI
or Anthropic API key is used.

- **Arms S and D run on every model a sub-agent can be given on the subscription**: the four
  model options of the Agent and Workflow tools, `opus`, `sonnet`, `haiku` and `fable`
  (`MODELS` in `scripts/real2.py`). Each job names its model and the workflow passes it to the
  sub-agent. **Opus runs first**: the pilot, then both arms with all three repeats on
  `opus`, then `sonnet`, `haiku` and `fable` in that order. Before a model's main run, one
  pilot job checks that the subscription serves it; a model that is not served is dropped by
  a dated amendment and reported as dropped.
- **Executions and adjudications** (the ground truth) run once, on the session's default
  sub-agent model, so every model is judged against the same truth. This is the same arrangement as
batches 1-4 (`runs/20260928_i2l/PLAN.md`: "compaction subagents read the frozen prompt
files"). Each sub-agent is a fresh context and sees one job. The model that served each call
is read from its transcript; `calls.jsonl` stores it as a short hash, and the model's name is
reported in the paper, not in the repository. If the model changes within the round, the
affected calls are reported separately.

## Ground truth: blind execution (one run per pair)

- An executor sub-agent receives the frozen prompt for the pair's runtime
  (`executor_prompt_<runtime>.txt`, copied unchanged from batch 4, `runs/20261001_gr`), the
  case id, the path of its `SKILL.md` in the scrubbed copy of its folder
  (`runs/20261031_real2/skills/<case>/`, which keeps the repository's layout so relative
  paths resolve), and a fresh work directory. It never sees a skillc
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

Each arm runs on each model (4 x 2 x 3 = 24 runs of 300 pairs).

| arm | what it does | calls per repeat and model |
|---|---|---|
| **S: skillc** | The original front end (`scripts/benchmark_ce_runtime.py --method ce_rt`, the method of batches 1-4): runtime-bound Controlled English compaction, parse, bind to the runtime, check; one located-error retry; one counterexample-guided repair under the repair guard; no pruning. | 1 to 3 |
| **D: direct verdict** | `skillc.frontend.prompts.direct_messages` (arm D of `runs/20260928_i2l`): the skill and the same runtime description; the model answers ACHIEVABLE, IMPOSSIBLE or UNKNOWN and names what is missing. | 1 |

- Repeats r1, r2, r3 are independent: fresh sub-agents, the same frozen prompts.
- UNKNOWN and an invalid or missing reply count as "no verdict" (not correct, not a refutation).
- The order of jobs is shuffled with seed 20261031 within each batch, and S and D jobs of a
  pair never run in the same sub-agent.

## What is measured, per call

- **Tokens.** The provider-reported usage in the sub-agent's transcript, summed over its
  turns: input, output, cache-read and cache-creation tokens, kept apart. Prompt and reply
  are also counted with the GPT-2 BPE tokenizer (`tiktoken` 0.14.0, encoding `gpt2`, the same
  vocabulary as the proxy of `runs/20260928_i2l`). Both are reported, labelled.
- **Time.** Wall-clock time of the sub-agent, first to last timestamp of its transcript.
- **Checker time.** Measured locally for every S pack: median of 7 runs of `check()` on the
  bound pack (`time.perf_counter`), with the machine's CPU count recorded.
- A decision's cost is the sum over its calls (S: compaction, retry and repair if any; D: one
  call). Execution cost is reported separately and is not part of either arm.

## Metrics (decided pairs = achieved or blocked under L2)

For each arm and each model, per repeat and pooled over the three repeats, with Wilson 95%
intervals:

- **accuracy:** correct verdicts over all decided pairs (no verdict counts as not correct);
- **blocked caught:** blocked pairs refuted, over blocked pairs;
- **working refuted:** achieved pairs refuted, over achieved pairs;
- **tokens per decision** and **time per decision:** median and interquartile range;
- **checker time** (S): median, 90th percentile, maximum;
- **agreement across repeats:** share of pairs with the same verdict in all three repeats,
  and Fleiss' kappa;
- slices by runtime and by repository;
- an exact McNemar test of S against D on repeat r1 (decided pairs), per model;
- secondary, no criterion: agreement across models on repeat r1 (share of pairs on which every
  model gives the same verdict, and Fleiss' kappa over models), for S and for D. It asks
  whether the checker makes the verdict depend less on which model writes the pack.

## Criteria (stated before any result; every outcome is reported)

Each criterion is judged separately for every model.

- **C1** S's accuracy is within 5 points of D's (pooled over repeats).
- **C2** S refutes no more working pairs than D (pooled).
- **C3** S's verdicts agree across all three repeats on at least as many pairs as D's.
- **C4** S's median tokens per decision are at most 3 times D's.

## Safety and data handling (from CLAUDE.md, mandatory)

- **No URL reaches a model.** Every prompt built from a skill is scrubbed with
  `skillc.frontend.urlguard` (`scrub`, then `assert_clean`) before a sub-agent sees it; 185 of
  the 300 `SKILL.md` files contain a link, an e-mail address or a domain name. Executors read
  the scrubbed copy of the skill folder (amendment 1). `python scripts/real2.py audit`
  re-checks every prompt and every copied file before each batch.
- **Sandbox only.** Executors work only in their own work directory under the session's
  scratchpad, never in this repository, never push or write to an external service, never
  read environment variables, credentials or tokens (the container holds an unrelated API key
  that must not be touched), and never use connector or MCP tools. These rules are in the frozen
  executor prompts and are repeated in every job.
- Skill documents are data: compaction and verdict sub-agents never execute anything.
- Executor reports are copied into `execution/` with personal identifiers scrubbed.

## Scale and orchestration

- 300 executions + up to 300 adjudications (achieved only), then for each of 4 models and 3
  repeats: 300 S compactions (plus retries and repairs, about half again) and 300 D verdicts.
  Roughly 600 + 4 x 3 x 750 = about 9,600 sub-agent calls.
- Run as Claude Code workflows in batches of at most 50 jobs, executions first. A batch that
  fails (rate limit, sub-agent error) is re-run for the failed jobs only; re-runs are logged.

## Outputs

`runs/20261031_real2/`: `skills/` (executor copies) and `skills.json`, `execution/`,
`adjudication/`, `s/<model>/r{1,2,3}/{prompts,outputs,packs}/`,
`d/<model>/r{1,2,3}/{prompts,outputs}/`,
`batches/`, `calls.jsonl` (one line per sub-agent call: job, tokens by kind, seconds, model
hash), `missing.log`, `checker_times.json`, `metrics.json`, and a report
`docs/REAL2_BENCHMARK.md`.

## How to run (`scripts/real2.py`; no model call inside it)

1. `skills`; `prepare --arm s|d --repeat 1|2|3` (every model); `jobs --arm exec --work <scratchpad>/real2_work`;
   `audit`. Done in the commit of amendment 3: 7,200 S and D prompts (300 pairs x 2 arms x 3
   repeats x 4 models; the prompt files of one pair are identical across repeats and models)
   and 300 executor prompts.
2. Executions: one workflow per batch file `batches/exec_*.json`; each sub-agent reads its
   prompt file and writes `result.json` in its work directory. Then `collect-exec --work <dir>`.
3. Adjudication of achieved reports (strict sensitivity): blind, one sub-agent each.
4. For each repeat K (all models; `--model` limits to one): S round 1 and D from
   `jobs --arm s|d --repeat K`; then `retry --repeat K` and S round 2; `repair --repeat K` and
   S round 3. The workflow passes each job's `model` to its sub-agent. A failed job is re-run once; what is still
   missing is recorded with `mark-missing` (no verdict) and listed in `missing.log`.
5. `calls --transcripts <workflow transcript dir>` after each workflow; `score` at the end.

**Pilot.** 10 pairs (the first 10 jobs of `batches/exec_00.json`) go through every step on
repeat r1 with `opus` first, to check the files, the transcripts and the scoring. If the pilot needs no
change of method, its outputs stay in the round. If it does, the change is committed as an
amendment, the pilot outputs are moved to `pilot/` and left out, and the 10 pairs are run again.

## Amendments

**Amendment 1 (2026-10-31, before any model call, execution or compaction in this round).**
The body above is the amended text; this lists what changed from the first commit of this plan
(13cd307c).

1. *Test set redrawn.* Checking the first draw found 10 renamed or near-identical copies of
   skills used before (for example a copy of an earlier artifacts-builder skill, overlap 0.97),
   one internal helper command that is not a user-facing skill, and 208 skills whose bundled
   files had not been copied. `select_real2.py` now excludes near-copies (Jaccard >= 0.5) and
   non-user-facing skills and copies whole folders. The new draw: 19 repositories (was 20),
   6,424 eligible (was 6,489), licences MIT 254 / Apache-2.0 33 / CC-BY-SA-4.0 13 (was
   246/40/14), runtimes 108 / 75 / 117 (was 109/92/99). `verify_real2.py` was added and passes.
2. *Executor copies.* Executors read `runs/20261031_real2/skills/<case>/`, a copy of the skill
   folder with links, e-mail addresses and domain names replaced by placeholders (CLAUDE.md: no
   URL reaches an agent). In source code a member access such as `subprocess.run` or
   `self.live` looks like a domain to the scrubber and would break the script, so code files
   keep a two-part name whose last part is a common member name (list in `scripts/real2.py`);
   every other link or domain is replaced. 40 skills have a code file with a placeholder, and
   one image that carries a link was withheld; outcomes on these skills are also reported
   separately. Batch 4 gave executors the original files.
3. *Executor rules added* (appended to every job; text in `scripts/real2.py`, `EXEC_NOTE`):
   placeholders stand for unreachable resources; no web search or web fetch tools and no
   opening of links; quiet package managers; no URL in `result.json`. Batch 4 allowed web
   tools. Residual: the output of a package manager or a test run can still show a link to
   the executor; this cannot be removed without changing what execution means.
4. *S and D prompts* are built from the scrubbed `SKILL.md` (batches 1-4 were not scrubbed), and
   S retry and repair prompts, which quote the model's own reply, are scrubbed again.
5. *Checker.* The S arm uses the checker of this commit, which includes the MISSING_CAPABILITY
   fix (a missing tool refutes the goal only when no path to the goal avoids it), not the
   checker of batches 1-4.
6. *Measurement.* Tokens and time come from the sub-agent transcripts (input/output split
   available), not from a single reported total; the model is stored as a hash. The pilot
   checks that the transcripts carry usage; if they do not, an amendment says what is used.
7. *Pilot and runner* added (sections "How to run" and the pilot paragraph above).

**Amendment 2 (2026-10-31, before any model call, execution or compaction in this round).**
A second check read every skill for validity and setup, and the user asked for every model.

1. *Not a real skill or out of scope.* One blank authoring template, two test fixtures of a
   plugin's own test suite and four offensive-security skills (red-team and attack playbooks,
   one of them drawn as a replacement) are skipped while drawing (rule in the test-set
   section). 294 skills of the amendment-1 draw stay; six replacements came in the seeded
   order. Licences now MIT 255 / Apache-2.0 34 / CC-BY-SA-4.0 11; runtimes 110 / 75 / 115.
2. *Installed as a unit.* 20 skills of the amendment-1 draw referred to files outside their own
   folder (a plugin's shared scripts and schemas, sibling skills they hand work to), which the
   copy did not hold, so an executor would have failed on a missing file the real install
   has. Each skill now comes with its plugin's shared files and the repository files it refers
   to (1,799 support files in 129 skills), at their repository paths. Every relative reference
   in a `SKILL.md` that exists in its repository at the pinned commit is present in the
   executor copy (checked); references to nothing in the repository are example paths in the
   user's project. Symbolic links and submodules are not copied.
3. *Binary files.* A PNG whose metadata carries a link is copied without its text chunks
   (pixels unchanged). Binary files are checked for real links and e-mail addresses only;
   bare-domain lookalikes occur by chance in compressed bytes.
4. *Every model.* Arms S and D run on each of the four sub-agent model options (`opus`,
   `sonnet`, `haiku`, `fable`), three repeats each; executions and adjudications stay on the
   session's default sub-agent model. Criteria C1-C4 are judged per model; agreement across
   models is added as a secondary measure. About 9,600 sub-agent calls in all.

**Amendment 3 (2026-10-31, before any model call, execution or compaction in this round).**
The user asked that all 300 be validated cases and none a duplicate, and that Opus run first.

1. *Same skill in other words.* A name-masked TF-IDF check (rule in the test-set section)
   found 10 skills the phrase rule had let through: three revised and renamed versions of
   skills used before (a product renamed in name and text), one guide sharing whole sections
   with an earlier skill, three stubs generated from one template with only the name changed
   (one stub of the family stays), two siblings of one register template (one stays) and one
   step of a plugin pipeline that repeats a sibling step. A first line at 0.45 skipped 9;
   reading the pair just under it (0.44, two siblings of the register template) moved the line
   to 0.40, which skipped one more. 290 of the amendment-2 draw and 284 of the amendment-1
   draw remain; 10 replacements came in the seeded order.
   Runtimes now 110 / 76 / 114; licences unchanged.
2. *Opus first.* The pilot and then both arms with all three repeats run on `opus` before the
   other models, in the order `sonnet`, `haiku`, `fable`.
3. `verify_real2.py` also checks the same-skill rule, with the draw's weights: no problem.
   Every relative reference in a `SKILL.md` that exists at the pinned commit is present in the
   executor copy (1,364 references, none missing).

**Amendment 4 (2026-10-31, before the pilot; no execution, compaction or verdict yet).**

1. *The model.* The user chose one Opus model for this round. A probe of the sub-agent model
   option (two one-word calls, no skill text) showed that the plain `opus` option resolves to
   a different model than the one chosen, and that the exact model id is accepted and served,
   as the transcripts record. So every call of this round (executions, adjudications, S and
   D, all three repeats) passes that exact id; the directory label stays `opus`, the id is
   given to the workflow at run time, and transcripts store the serving model as a hash.
   Ground truth therefore also comes from this model (was: the session's default model).
2. *Per-call overhead.* Each sub-agent call carries the same fixed harness context (system
   prompt, tool definitions, project rules; about 60,000 input tokens, mostly written to the
   prompt cache) whatever its job. Token results are reported in total and by kind (input,
   cache write, cache read, output), and also with that fixed per-call part, measured on the
   probe, subtracted, so the arms are compared on what their own prompts and replies cost.
3. *Executor installs.* Executors install packages only inside their work directory (a
   virtual environment for Python, local node_modules for Node), never globally (rule added to
   `EXEC_NOTE`), so the checker's own environment cannot change during the round. The list of
   installed packages is recorded before the round and checked after it.
4. *No leak of the truth.* Executor and adjudicator reports stay in the work directories
   outside the repository until every S and D call has finished; `collect-exec` runs after
   that. S and D sub-agents are told to read only their one prompt file and write only their
   one output file.
5. *Adjudicator prompt* written (`adjudicator_prompt.txt`): blind, read-only, judges an
   achieved report genuine or simulated. Adjudication runs after all executions and before S
   and D.
6. *Concurrency.* The machine has 4 CPUs, so one workflow runs 2 sub-agents at a time; several
   workflows run side by side, each on its own batch file.

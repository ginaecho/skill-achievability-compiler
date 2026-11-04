# Benchmark re-run, November 2026

We re-ran the evaluation of "Affordable Mistakes" (paper/WIP/main.tex, §10, Tables 1-3) with the paper's own scripts, on branch `claude/gallant-sagan-12rwus`, from 2026-11-04. The models were `haiku` and `sonnet` through the Claude Code CLI 2.1.318. The CLI served `claude-haiku-5-5` and `claude-sonnet-5-5`.

## How this re-run differs from the September runs

These differences are deliberate. Each one is a reason a number below may
differ from the paper's.

1. **The prompts are scrubbed of URLs (required by CLAUDE.md, the 2026-10-16 rule).**
   The September scripts put raw SKILL.md text into prompts and copied it into
   the agent's directory. On 2026-10-16 Microsoft Defender for AI flagged a
   benchmark run that had sent third-party links to a model, and since then the
   repository forbids any URL, bare domain or e-mail in a model request. Every
   call in this re-run goes through `src/skillc/benchguard.py`, which uses
   `skillc.frontend.urlguard`:
   - the prompt is `scrub`bed and `assert_clean`ed, so every URL, domain and
     e-mail becomes `[url-n]`, `[host-n]` or `[email-n]`;
   - every file placed in the agent's working directory (SKILL.md, task inputs,
     spec-case tool scripts, generated inputs) is scrubbed with the same
     placeholder table. A binary file with URL-like bytes is refused;
   - the compaction input (`token_economics.py --compact`) goes through
     `providers.claude_cli_complete`, which already sends only `guarded_body`
     output, and `compact_one` refuses a skill that does not scrub clean.
   `tests/test_benchguard.py` checks that a skill containing links produces a
   URL-free prompt and URL-free files for each of the four call sites.
   **Effect on the results:** the agent sees `[url-1]` where the skill had a
   link. None of the 13 usefulness tasks needs a link to do its work. Two task
   inputs had a domain in a JSON value (`contractor.example.com`,
   `apps.example.com`), and their verifiers do not read those values. Among the
   real skills that were run, 4 had links in their text (bulk-rnaseq,
   google-workspace-cli, kubernetes-operator, writing-skills), and pdf had one
   false-positive host, `doc.build`. The judge and the compaction calls see the
   scrubbed skill text. A judge that reasoned from a link (for example a
   download URL) now sees a placeholder.
2. **The agent is isolated from this machine's credentials and services.** The
   September scripts started `claude -p` with the caller's whole environment,
   from the repository directory. This re-run passes the CLI an allow-listed
   environment, with no tokens, keys or cloud credentials. It turns off MCP
   servers, user and project settings, and slash commands and skills
   (`--strict-mcp-config --setting-sources "" --disable-slash-commands`). It
   enables the CLI's sandbox for the agent's shell: the CLI login and other
   credential files cannot be read, reads outside the working directory are
   blocked, and network access is denied. It sets
   `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1`. Every agent works in a fresh
   directory under the session scratchpad's `bench_work/`. A probe run checked
   all of this. To make it work, `bubblewrap` and `socat` were installed in the
   container, because the CLI's sandbox needs them.
   **Effect:** shell agents cannot `pip install` or download anything. The
   sandbox also places empty guard files (`.env`, `package.json`,
   `node_modules/`, ...) in the agent's working directory. `--permission-mode
   acceptEdits` is still passed, but the CLI forces default mode when
   subprocess scrubbing is on. The agent's tools are still exactly the
   runtime's (`--tools` and `--allowedTools`, unchanged).
3. **The LLM judge no longer uses `--bare`.** `--bare` accepts only an
   `ANTHROPIC_API_KEY`, and this container logs the CLI in another way. The
   same isolation flags replace it. The system prompt is still the script's
   own (`--system-prompt`).
4. **The models were sampled again.** `haiku` and `sonnet` are aliases. In
   November the CLI served `claude-haiku-5-5` for `haiku` (see
   `served_models` in each record). September's records do not say which
   model was served (paper §10, reviews R2/R6). Prices differ with the model
   too.
5. **The corpus is 157 skills, not 162.** Five of the 145 third-party entries
   in `PROVENANCE.json` return 404 upstream (`microsoft__skills/azure-cost` and
   four `Security-Phoenix-demo__security-skills-claude-code` skills, among them
   `cti-search-skill`, which raised one of the paper's nine security flags).
   September recorded hashes for only one of the remaining 140 files, so we
   cannot tell whether their text has changed upstream since then.
6. **The realistic-scale tasks were reconstructed.** `usefulness.py` loads
   `scripts/usefulness_tasks_large.json`, but that file was never committed. It
   is not in any commit on any branch. It was rebuilt from what the paper and
   reviews R2 and R7 say about it: the same five skills; sizes of 1000
   transcripts, 1000 rows, 500 users, 150 manifests and 120 files; inputs
   generated from a fixed seed; and a verifier that recomputes the expected
   answer from the same seed. Each task was validated before any model run: a
   reference solution verifies and a corrupted one does not. Every entry
   carries `"reconstructed"`. The September turn and spend caps for these
   rows were not recorded (review R2 W20). Runs reached 127 turns there, so we
   used `--max-turns 150 --budget 1.5`. The small-input rows keep the script
   defaults (`--max-turns 12 --budget 0.6`).
7. **`token_economics.py` now writes its tables to
   `docs/TOKEN_ECONOMICS_CENSUS.md`.** Since 2026-10, `docs/TOKEN_ECONOMICS.md`
   is a hand-written measurement report. The script would have overwritten it,
   and the first stage-1 commit did overwrite it; that commit's change was
   reverted. The script version in the tree also does not compute two fields
   the manifest reads (`free_skills`, `escalated_share_of_measured_run_pct`).
8. **Per-run records now carry `served_models`, `max_turns`, `budget_usd`,
   `stop_reason` and the number of placeholders scrubbed** (usefulness), and
   `served_models` (live agents and judge). These fields were missing from
   September's records (reviews R2 W20 and R6 W4).

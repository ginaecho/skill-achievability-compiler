# Replay log: how this tree was rebuilt, and what is still missing

This branch (`gc/paper-WIP-iserr-writes`) was not produced by the original
session's git history. It was rebuilt by replaying the file writes of one Claude
Code session (2026-09-02 07:04Z to 2026-09-03 02:10Z) on top of `e71f5cf5`
("Fit all figures to the text width"). Builds, test runs, model calls and network
access were not replayed. Commits up to `d2ffb439` are that replay. The commits
after it repair what the replay lost.

## Why the replay lost text

1. **Missing model-backed data.** Several session commands generated paper text
   from results files that came from model runs and are not in the tree:
   `usefulness_runs.jsonl`, `usefulness.json`, `token_economics.json`,
   `grep_baseline.json`, `compaction_runs.jsonl`, `live_agents*.json`. In the
   replay these commands failed. Every later edit whose `assert old in s`
   depended on their output then failed too.
2. **Wrong working directory.** The session's shell kept its directory between
   commands. The replay tracked the directory imperfectly, so some
   `cd paper/WIP && ...` and relative-path commands ran in the wrong place.
3. **Line-number edits.** At 00:19:02Z the session replaced lines 796-806 of
   main.tex by line number. In the shorter replayed file that edit overwrote the
   header of the "Progress under misselection" theorem. This was the first
   build error.
4. **Characters stripped by the transcript export.** Zero-width and bidi
   characters in `scripts/scan_skills.py` and its test reached the transcript
   as empty strings.
5. **One edit missing from the transcript.** The insertion of the
   `%%DIFFRESULT%%` paragraph between 19:33Z and 20:18Z has no command in the
   transcript. Its text was taken from the session's later `sed -n` output
   (20:35:42Z).

## Method used for the repair

The transcript was used as data. For each target file
(`paper/WIP/main.tex`, `paper/WIP/results/CLAIMS.json`, ...), the session's own
main-agent commands that write it were re-executed in order in a scratch copy
of the tree:

- `pdflatex`, `pytest`, `git`, `make`, network tools and Python *scripts* were
  replaced by no-ops. Only inline `python3 -` / `python3 -c` and `sed -i` ran.
- The shell's working directory was tracked, and corrected wherever the
  session's own output showed a relative path resolving from somewhere else.
- `git checkout` of main.tex was emulated from the state at the last commit.
- Data-dependent commands were run with the values the session printed. Where
  no values were printed, the text was taken from a later `sed -n` display.
- After every session display of a line range (`sed -n 'A,Bp' main.tex`, 142 of
  them) and every `grep -n` check, the reconstruction was compared with what
  the session printed. Where they differed, the session's text was spliced in.

Every display from 00:30Z to 02:00Z matches the reconstructed main.tex line for
line. The session's final page check also reproduces: 28 pages, body ending on
page 25 with "...structurally unreachable", References from page 26, 0 errors
and 0 overfull boxes. The CLAIMS.json rebuild reproduces the claim count the
session printed after every step (34, 41, 42, 43, 55, 58, 65, 66, 68, 69, 72,
75, 86, 98, 104).

## What was repaired (commits after d2ffb439)

| Commit subject | File | Evidence |
|---|---|---|
| Restore the "Progress under misselection" theorem | main.tex | grep at 00:18:53Z, heredoc at 00:19:02Z, sed at 00:58:25Z |
| Restore the "Modular composition" theorem | main.tex | sed at 00:39:28Z and 01:00:52Z |
| Front matter, abstract, contributions | main.tex | sed 1-200 (00:57:09Z), 200-335, 360-530 |
| Kernel, differential, benchmark, modularity text | main.tex | sed 1043-1180 (01:02:34Z) and others |
| Live agents, usefulness, Finding 6, security | main.tex | sed 1004-1148 (19:33Z), 1285-1520 (01:02Z) |
| Repairs, related work, conclusion, bibliography | main.tex | sed 1579-1714, 1786-1900; page check at 02:00Z |
| Random-protocol test | tests/test_severity.py | heredoc at 20:18:37Z, test list at 22:29:22Z |
| `total == 162` | tests/test_corpus_security.py | heredoc at 23:25:50Z |
| 104th claim and audited false-refutation formula | results/CLAIMS.json | commands at 23:25:50Z and 02:04:30Z |
| Final differential generator (one recursion per protocol, cumulative record, `--reset`) | scripts/differential_test.py | `cat` at 22:23:13Z plus edit at 23:25:15Z |
| Differential campaign re-run | results/differential*.json | invocation at 23:25:15Z / Makefile |
| Artifact README | paper/WIP/README.md | `sed -n '1,200p'` at 00:24:45Z, then 5 later edits |
| severity.json with real-skill rows | results/severity.json, docs/SEVERITY_RESULTS.md | regenerated with `PYTHONPATH=src` |
| Scanner invisible-character sets (**reconstructed, not verbatim**) | scripts/scan_skills.py, its test | stripped in the transcript |
| main.pdf rebuilt | paper/WIP/main.pdf | |

The differential test now reports 500 generated, 500 compared, 500 agree,
0 disagree and 0 crashes, with 150 protocols at seed 20260902 and 350 at seed
4242 (`--kmax 2`). This is what the session's final paper states. The earlier
campaign compared 499, and the paper reports that too.
`differential_failures.json` keeps the one rejected pack from that earlier
campaign (`rand136`), which the session displayed and CLAIMS.json counts.

## What is still missing or cannot match

- **Model-backed results** (not regenerated, not fabricated):
  `usefulness_runs.jsonl`, `usefulness.json`, `live_agents.json`,
  `live_agents_runs.jsonl`, `token_economics.json`, `compaction_runs.jsonl`,
  `grep_baseline.json`, `llm_judge*.json`. Of the 104 manifest claims, 68
  cannot be evaluated without them: usefulness 27, token economics/census 16,
  live agents 15, grep baseline 8, compaction 2.
- **Third-party corpus**: `real-skills-ext/` and both `PROVENANCE.json` files
  are not in this tree (they are fetched over the network and are gitignored).
  `results/security_scan.json` as replayed scanned 2 files, where the paper
  says 162 files with 9 hits. It needs the corpus to regenerate.
- **Wall-clock timings**: this machine runs about 2-2.5 times slower than the
  session's (benchmark 0.47 s against the paper's 0.21 s; migration n=6 53.7 s
  against 22.4 s). That is outside the manifest's 50% tolerance, so the 7
  timing claims fail here. They are left as measured.
- **`/mnt/skills` has changed since 2026-09-02** (it now has `built-in-browser`,
  and `computer-use` has different text). Two `tests/test_real_skills.py` cases
  fail for that reason. The session's own final run passed them (410 passed,
  5 skipped at 02:08:46Z).

## Remaining test failures (8) and their causes

| Test | Cause |
|---|---|
| test_proof::test_the_numbers_the_paper_states_match_the_shipped_results | model-backed results files missing (stops at `live_agents_runs.jsonl`), plus timings and the security scan |
| test_proof::test_a_cited_phrase_leaving_the_prose_fails_the_numbers_check | needs a clean numbers check first, so fails for the same reasons |
| test_severity::test_grep_baseline_is_weaker_than_the_checker | `grep_baseline.json` missing |
| test_severity::test_real_skills_flip_between_shell_and_no_shell_runtimes | real-skills copy in this tree differs from the session's (`claude-api` is refuted at home) |
| test_corpus_security::test_home_refutation_audit_matches_the_checker | `real-skills-ext/` missing, and the `claude-api` difference above |
| test_corpus_security::test_every_corpus_file_matches_its_recorded_hash | corpus and `PROVENANCE.json` files missing |
| test_real_skills::...[examples/built-in-browser] | `/mnt/skills` changed since the session |
| test_real_skills::...[examples/computer-use-computer_request_access] | `/mnt/skills` changed since the session |

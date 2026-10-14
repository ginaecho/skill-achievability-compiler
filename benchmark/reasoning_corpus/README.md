# Reasoning corpus

Real, naturally occurring agent output from this project's own benchmark runs. Nothing in it is
authored or edited by hand; it is extracted verbatim by `scripts/reasoning_corpus.py build`. Its
purpose is to measure the false-positive rate of the runtime monitor's reasoning scanner
(`Monitor.observe_thinking`) and action scanner (`Monitor.pre_action`) on benign work.

## Files

- `claude_code_sessions.jsonl`: one record per Claude Code session transcript:
  `{source, session_file, units: [{kind, text}], actions: [{tool, key, digest}], n_units, n_chars}`.
- `execution_reports.jsonl`: one record per blind-execution report:
  `{source, skill, runtime, outcome, text, n_chars}`.

## Provenance and counts

| Part | Count |
|---|---|
| Sessions (transcripts with assistant output) | 127 |
| Session units (assistant `thinking`/`text` blocks) | 253 (all `text`; 0 `thinking`) |
| Session characters | 482,899 |
| Session tool actions | 1,073 |
| Execution reports | 560 |
| Report characters | 1,072,263 |

Sessions: JSONL transcripts under `~/.claude/projects/C--Users-tzuchunchen-AppData-Local-Temp-stjp-*`
and `C--Users-TZUCHU-1-AppData-Local-Temp-stjp-*` (headless benchmark runs of this project).
Personal projects (`C--Users-tzuchunchen-Documents-*`) are excluded. The headless transcripts
contain no `thinking` blocks, so session units are visible assistant text only.

Reports: JSON files read from git branch `microsoft/gc/data_train_test` (`git show`, no checkout) in
`runs/20260928_div/execution`, `runs/20261001_gr/execution`, `runs/20260927_ext/execution`,
`runs/20260926_ce_ab/execution`, `runs/20260926_heldout_execution`, `runs/20260926_tpl/execution`.
`skill` and `runtime` come from the report's `skill` field (`<skill>@<runtime>`); 270 reports
(ext, ce_ab, heldout) carry no `@runtime`, so `runtime` is empty. `outcome` is `achieved` or
`not_achieved`.

## Extraction rules

- Sessions: only records with `message.role == "assistant"`; `thinking` and `text` blocks become units,
  in order (the same parsing as `thinking_since`). User turns and tool results are dropped.
  `tool_use` blocks go to `actions` with tool name and a digest (`key` names the input field:
  command, file_path, url, ...; digest is cut at 500 characters).
- Reports: the free-text fields written by the agent (`evidence`, `blocker_detail`, `notes`,
  `note*`, `raw_report`), joined with newlines. The task description (`task_instance`) is not
  included. Reports with no such text are skipped.

## Use

```
python scripts/reasoning_corpus.py build
python scripts/reasoning_corpus.py score --runtime developer-sandbox [--thinking ask|stop] [--src DIR] [--json OUT]
```

`--src` scores the same corpus against another checkout of `src/` for before/after comparisons.
Hits are not labelled: a human classifies the listed sentences as true or false positives.

# Pinned sources for the compaction comparison

These are eight unchanged, publicly licensed skill documents across six
categories. `sources.json` records upstream repository, commit, path, URL,
license and SHA-256 hashes. Each directory retains its same-commit upstream
`LICENSE`. The two Aspire plugin files were symlinks: `UPSTREAM_LINK` retains
their original contents and `SKILL.md` contains the resolved, same-commit
`skills/<name>/SKILL.md` document.

The associated `..\compaction_cases.json` contains separately authored,
bounded task/environment scenarios. They are **not** claims that the original
skills are impossible, actual backend trials, or unchanged production tasks.
Full documents are benchmark input data; none of their instructions is executed.
The Hugging Face trainer candidate is excluded because of an unresolved local
license reference.

The harness freezes inputs and independent reachability labels before any
model call. It sends only these public documents and authored, non-sensitive
contracts to the configured inference service. No real credentials, user data,
dataset rows, PR content or telemetry are part of the cases.

```powershell
python scripts\benchmark_compaction.py --prepare
python scripts\benchmark_compaction.py --run-dir runs\<prepared-directory> --live
```

Omit `--live` for deterministic-only replay. Model calls are opt-in; existing
live compactions can be resumed without repeating completed cases. A resumed
run rejects changed implementation files, inputs, model or endpoint. To replay
after modifying the implementation, prepare a fresh run instead.

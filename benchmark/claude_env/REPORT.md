# `skillc reach --claude` on 100 real SKILL.md / agent.md documents

**The question.** An agent in a Claude Code cloud session is asked to do what a
document is for. Can it, here? `skillc reach DOC.md --claude` answers in three
steps:

1. It reads the document's runtime needs, citing the line each one came from.
2. It probes exactly those needs in the live session, read-only.
3. It returns ACHIEVABLE (possibly under assumptions) or BLOCKED, with a plan
   (installs) and the blockers.

## Protocol

| Step | What was done |
|---|---|
| Development set | `/mnt/skills` (42) and `benchmark/compaction_sources` (10). Only these informed the front-end. |
| Freeze | The front-end was committed (`812f7683`) **before** the test set was drawn. `src/` was not changed afterwards. |
| Test set | `select_cases.py`, seed 20261003. 70 SKILL.md come from the pinned corpora `ce_sources*` on `gc/data_train_test`, with the development set excluded by name and hash. 30 agent.md come from `wshobson/agents@156b7a5e` (15) and `VoltAgent/awesome-claude-code-subagents@82b73821` (15). Within each pool, 70% of the draw is documents with a code block. Provenance (repo, commit, path, license, sha256) is in `cases.json`; the texts are in `cases/`. |
| Ground truth | 10 independent annotators, 10 documents each, followed `RUBRIC.md` **blind**: no skillc, no skillc source. They listed each document's *hard* requirements and checked every one by real, read-only execution in this container: `command -v`, `apt-get -s`, `pip download`, `npm view`, curl egress probes, whether a credential variable is set (never its value), `docker info`, and `gh api user`. Results are in `truth/cNNN.json`, with the command and output for each check. |
| Environment | This session, as it was: Linux x86_64, no GPU, no Docker daemon. Egress goes through an allow-list proxy (pypi, npm, GitHub, Ubuntu, NuGet and the Go proxy are open; huggingface, Microsoft Learn/Azure, Cloudflare, Expo, Neon and NVIDIA are refused). Connectors are GitHub, Notion, Google Drive, Jam, Mem, Bigdata.com, eToro and Claude Docs, plus three that are waiting for sign-in. `session/` holds the tool and connector lists given to both sides. |
| Run | `run_skillc.py` → `results/skillc.json`. Exit codes 0 and 3 count as ACHIEVABLE; exit code 1 counts as BLOCKED. |

One adjudication was made. The annotator of c084 marked it BLOCKED on
`SendMessage`, because that tool was missing from `session/tools.json`. That was
my error in describing the environment: the session has the tool. I corrected
the list before skillc's scored run and set the truth to ACHIEVABLE; the change
is recorded in the file. No other truth was changed.

## Results (frozen front-end; `python benchmark/claude_env/score.py`)

|                    | skillc BLOCKED | skillc ACHIEVABLE |
|--------------------|---------------:|------------------:|
| truth BLOCKED (28) | **20** | 8 (missed) |
| truth ACHIEVABLE (72) | 6 (false refutations) | **66** |

Overall, skillc agreed with the ground truth on **86/100** documents. For a
BLOCKED verdict, precision is **77%** and recall is **71%**. A baseline that
always answers ACHIEVABLE scores 72%, so most of the value is in the 20
correctly blocked cases. In **18 of those 20**, skillc names the true cause or
part of it: no Azure, Neon, Cloudflare, Expo or Hugging Face account; a missing
MCP server (`chrome-devtools`, `azure`, Apollo, `cloudflare-docs`); Windows or
macOS; the Docker daemon; NVIDIA keys. In the other two the verdict is right
but the reason differs:

- **c016:** skillc names the Cloudflare account; the truth names the blocked
  docs host.
- **c041:** skillc says terraform has no install route; the truth says the
  Terraform registry is refused.

### False refutations (6): skillc said BLOCKED, the truth is ACHIEVABLE

| case | skillc's blocker | cause |
|---|---|---|
| c003 | `program:cli_exercise_helper` | The tool-policy library marks this helper unavailable outside the cli/cli checkout. This document *is* that skill's package, so the helper ships with it. |
| c020 | `egress:commons.wikimedia.org` | A sample-file URL in a list is read as a fetch the workflow depends on. |
| c030 | `program:gradio` | `gradio` comes from `pip install gradio`, but the routes file has no entry for it. A route gap. |
| c040, c063 | `egress:aspire.dev`, `platform:windows` | The install table offers alternatives (`curl … \| bash`, PowerShell, `dotnet tool install`, npm). skillc required both the curl route and the Windows one; any one of them suffices. |
| c046 | `program:rev-parse` | Parser bug: command substitution `$(git rev-parse …)` is split so that `rev-parse` looks like a program. |

### Missed blocks (8): skillc said ACHIEVABLE, the truth is BLOCKED

In every one of these, the requirement is stated **in prose**, not in a command,
an import, a credential variable or an `mcp__` reference. The deterministic
reader does not see it:

- c006 and c057: a Common Room MCP, and an Azure MCP plus Azure account.
- c026: browser automation of NotebookLM.
- c029: "use the microsoft-docs MCP".
- c037: Adobe Illustrator.
- c045: an Expo account and the EAS API.
- c070: the Joyride VS Code tool.
- c077: a DGX Spark GPU.

## What this says

* When skillc blocks, it is usually right and usually for the right reason.
  The six wrong blocks have concrete, fixable causes:
  - alternatives read as conjunctions;
  - a command-substitution parsing bug;
  - two data gaps (an install route, and a helper the skill ships with);
  - one URL that was only an example.
* Its weakness is recall on needs that are written only in prose ("requires
  Illustrator", "use the X MCP"). These need either a vocabulary of named
  products and connectors, or a model-based reader whose output is checked the
  same way.
* Neither side can see some judgement calls. Examples: whether consulting
  current docs is a *hard* step (c016, c029), and whether writing scripts for a
  tool you cannot run counts (c037). The annotators recorded these in `notes`.

These numbers are for the frozen front-end. Fixing the causes above would use
the test set as development data. Any later improvement must therefore be
measured on a newly drawn test set: run `select_cases.py` with a different seed
and exclude the cases already used.

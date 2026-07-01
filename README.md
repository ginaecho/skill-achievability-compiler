# skill-achievability-compiler

**`skillc`** — a static compiler that decides whether the *goal* of an agent
skill (a `SKILL.md`, agent markdown, or a formal achievability pack) is
achievable in a given capability context.  It is **sound for refutation**:
an `IMPOSSIBLE` verdict is a proof (relative to the declared capabilities and
frame assumption) that no run of the skill can reach its goal.  It is
deliberately **incomplete for achievement**: `ACHIEVABLE` means "structurally
admissible", not "guaranteed".

The soundness core is mechanized in Coq ([`proof/SkillAchievability.v`](proof/SkillAchievability.v),
zero axioms, audited by [`proof/check_assumptions.v`](proof/check_assumptions.v));
the checker decides capability-guarded may-reachability with z3, in
milliseconds, with no LLM in the trusted path.

```
 natural-language skill ──► [ front-end compaction ] ──► pack ──► [ checker ] ──► verdict
      (SKILL.md)              UNTRUSTED                           TRUSTED
                              deterministic or LLM                sound for refutation
```

## Install

```bash
pip install -e ".[dev]"        # installs the `skillc` CLI
```

## Quick start

Check a real skill against the runtime that will execute it:

```console
$ skillc check call-to-book/SKILL.md --profile claude-ai
call-to-book: ACHIEVABLE

$ skillc check call-to-book/SKILL.md --profile claude-code
call-to-book: IMPOSSIBLE [MISSING_CAPABILITY]
  protocol invokes undeclared capabilities: ['ask_user_input_v0']
  missing: ask_user_input_v0 (line 7)
```

The same skill, two verdicts: achievability is always judged **relative to a
capability context Γ** (an environment *profile* plus the skill's own
`allowed-tools`/`tools` frontmatter).  A consumer-app skill that asks
questions via `ask_user_input_v0` is provably not executable as written under
Claude Code, which has no such tool.

Batch-scan a skill tree, compile a pack, or run the evaluation corpus:

```console
$ skillc scan /mnt/skills --profile claude-ai      # 32/32 achievable
$ skillc compile SKILL.md -o pack.json             # inspect the formal object
$ skillc check pack.json --json                    # machine-readable verdict
$ skillc eval                                      # corpus + soundness audit
$ skillc profiles                                  # claude-ai, claude-code, none
```

Exit codes: `0` achievable, `1` impossible, `2` error — so `skillc check` can
gate CI for skill repositories.

## What the checker decides

A **pack** declares capabilities (STRIPS pre/effects, numeric assignments,
constrained non-determinism), a goal-marked global protocol (`act` / `msg` /
`choice`), a goal formula, and the initial state.  The checker refutes with
one of:

| reason | failure mode it catches |
|---|---|
| `MISSING_CAPABILITY` | hallucinated planning — the protocol invokes a tool that is not granted |
| `GOAL_UNSAT` | no establisher for a goal conjunct, or a numeric refinement (e.g. *under $500*) unsatisfiable on every run |
| `BLOCKED_GUARD` | a mandatory action's precondition can never be satisfied (the retry-forever cause) |
| `NON_PROJECTABLE` | a role must act inside a branch it is never told about (unobserved choice → deadlock/handoff freeze) |

Tolerance comes from may-reachability (detours allowed), interface slack, and
goal-relevant abstraction — extra status messages or beneficial branches never
cause a refutation (Coq T2), and *adding* capabilities never flips
`ACHIEVABLE` to `IMPOSSIBLE` (Coq T3, `cap_monotone`).

## Front-ends

1. **Deterministic markdown front-end** (default, no LLM).  Parses
   frontmatter (`allowed-tools` / `tools`), prose tool declarations
   (`Tools: a, b, c`), and extracts tool invocations from the prose
   ("ask via `ask_user_input_v0`", "use `str_replace`", …).  Unix commands
   and code symbols route through the profile's shell capability; fenced code
   blocks are not scanned.  Every extraction is reported with line-number
   provenance (`skillc compile` prints it to stderr) so the pack is
   inspectable at one checkpoint.
2. **Embedded pack**: a fenced block tagged ```` ```skillc-pack ```` inside
   the SKILL.md is validated and used verbatim — full checker power (guards,
   budgets, roles, choice) for authors who want precise semantics.
3. **LLM compaction** (`skillc compile --llm`, needs `ANTHROPIC_API_KEY`):
   semantic NL→pack distillation.  Untrusted by design — its output passes
   the same deterministic schema gate and trusted checker, so a hallucinated
   compaction can only produce a false `ACHIEVABLE` (caught by later layers),
   never a false `IMPOSSIBLE` about the pack it actually emitted.

## Results on real, public skills

Validated against Anthropic's public skills corpus
([anthropics/skills](https://github.com/anthropics/skills), 32 `SKILL.md`
files mounted at `/mnt/skills`, or fetched with
`python3 scripts/fetch_skills.py`):

* **32/32 achievable under the `claude-ai` profile** — their home runtime.
  Zero false refutations on deployed skills (the empirical face of T1).
* **16/32 refuted under the `claude-code` profile**, each with the exact
  missing tool named (`ask_user_input_v0`, `read_page`, `upload_file`,
  `create_file`, `str_replace`, `show_widget`, `search_mcp_registry`, …) and
  the source line.  Granting the named tools flips every one of them back to
  achievable (T3 on real data).

Full table: [`docs/REAL_SKILLS_REPORT.md`](docs/REAL_SKILLS_REPORT.md).

On the 15-spec ground-truth corpus (`skillc eval`): **FN = 0** (no achievable
goal ever refuted — T1) and the only false `ACHIEVABLE`s are the two planted
`SPURIOUS` cases (payload faithfulness / intent fidelity), i.e. exactly the
residues the compiler openly defers to runtime monitoring and human review —
never a structural failure it should have caught.

## Tests

```bash
python3 -m pytest                          # 159 tests
SKILLC_SKILLS_DIR=./real-skills pytest tests/test_real_skills.py   # real corpus
SKILLC_LIVE_LLM=1 pytest tests/test_llm_frontend.py               # live LLM (opt-in)
coqc proof/SkillAchievability.v && coqc proof/check_assumptions.v  # the proof
```

The suite covers the formula language, the schema gate, every refutation
reason, projectability, the corpus confusion matrix (reproduced exactly:
TP=6 FN=0 FP=2 TN=7), the markdown front-end (extraction, classification,
profiles, embedded packs), the CLI, and — when a corpus is present — every
real public skill under multiple profiles, including the monotone-widening
property.

## Layout

```
src/skillc/            the compiler package
  checker.py             trusted core: tolerant may-reachability (z3)
  pack.py                pack model + deterministic schema gate
  formula.py             guard/goal mini-language
  profiles.py            capability contexts (claude-ai, claude-code, none)
  frontend/markdown.py   deterministic SKILL.md -> pack compaction
  frontend/llm.py        optional LLM compaction (untrusted, env-gated)
  evaluate.py            corpus evaluation + soundness/incompleteness audit
  cli.py                 skillc compile | check | scan | eval | profiles
  data/                  built-in profiles + evaluation corpus
proof/                 mechanized soundness (Coq 8.18, zero axioms)
corpus/build_corpus.py 15 ground-truth specs across the failure taxonomy
docs/                  compaction prompt + real-skill scan report
scripts/               fetch_skills.py, make_report.py
tests/                 the test suite (pytest)
```

## Honest limitations

Everything is proved about the *declared* capabilities and protocol; if the
prose lies, the checker verifies a fiction (honest declaration is a runtime
obligation).  The deterministic front-end is a conservative heuristic — its
extraction is inspectable and a misextraction only makes the checker judge a
different pack, but it does not understand semantics (use the embedded-pack
escape hatch or `--llm` for that).  The projectability check targets the
unobserved-choice family, not full MPST projection.  Dynamic subagent
spawning is outside the decidable fragment.

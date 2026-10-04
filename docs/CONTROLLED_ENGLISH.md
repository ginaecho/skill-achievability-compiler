# SkillC Controlled English (CE)

> **Data:** the experiment data this document cites (`runs/`, `benchmark/`) is kept on the
> branch [`gc/data_train_test`](https://github.com/ginaecho/skill-achievability-compiler/tree/gc/data_train_test),
> not on `main`. Check out that branch to reproduce the numbers or run the experiment scripts.

CE is a small formal language that reads as English. Each sentence form
denotes exactly one pack construct, so parsing CE into a pack is deterministic
and exactly invertible. Parse errors give the line and column.

```text
Skill `book-flight`.
Tool `book_flight` (owner `agent`) via `bash` needs `airline_account`:
  requires `flight_selected`; adds `booked`.
Goal: `booked` and `confirmation_sent`.
Protocol:
  - `agent` uses `book_flight`.
  - `agent` uses `send_email`.
```

- **Grammar and renderer:** `src/skillc/frontend/ce.py` (grammar 1.2).
- **Worked example:** `examples/controlled-english/`.
- **CLI.** `skillc check skill.ce` checks a CE file. `skillc ce pack.json`
  renders a pack as CE. `skillc check SKILL.md --llm --via-ce` makes the
  model write CE instead of JSON.
- **Tool clauses** (they bind a Tool to a runtime, see
  [P2G_RUNTIME_BINDING.md](P2G_RUNTIME_BINDING.md)):
  - `via <runtime tool>`;
  - `needs <resource>`;
  - `runs <program>`;
  - `effect local | reads_external | writes_external | publishes`.
- **Live goal.** An optional `Live goal:` line states the deployed outcome
  separately from the core deliverable.

## Guarantees (tested in `tests/test_ce.py`)

- **Round trip.** `parse_ce(render_ce(p)) == canonical_pack(p)`, and
  `render_ce(parse_ce(t)) == t` for canonical documents.
- **Real packs.** Every pack in the repository round-trips with an identical
  checker verdict, and so does every mutant of those packs.
- **Generated packs.** Hypothesis generates packs with adversarial
  identifiers, and they round-trip too.
- **Errors.** Located errors cover 24 malformed forms.

## A/B against JSON compaction (150 real skills, 32 labelled scenarios)

**Set-up:**
- The model received the same skills and the same modelling rules.
- The only difference between the two arms was the output format: CE or JSON.
- Each arm got one located-error retry.
- The corpus is `benchmark/ce_sources`: 294 licensed skills from 15 public
  repositories, byte-identical to upstream.
- Data are in `runs/20260926_ce_ab/`.

**Results:**

| | JSON | CE |
|---|---|---|
| Valid after one retry | 150/150 | 150/150 |
| Valid on first attempt | 141/150 | 115/150 (grammar 1.0) |
| Labelled scenarios (impossible refuted / false refutations) | 16/16, 0 | 16/16, 0 |
| Median output length | 1,212 characters | 797 characters (−35%) |
| Verdict stable across 3 samples | 11/20 | 15/20 (p = 0.22) |

- **First-attempt gap.** It came almost entirely from one gap in the grammar:
  grammar 1.0 rejected `Initially true: none.` Grammar 1.1 fixed this.
  Re-parsing the same replies post hoc then gives 219/222 valid on the first
  attempt.
- **Accuracy.** The output format did not change accuracy.
- **Real limit on real skills: which tools the model declares.** An executor
  that could not see the verdicts accomplished 29 of the 46 skills rejected
  by either arm. Most of these false rejections were `MISSING_CAPABILITY`:
  an ordinary developer action that the compactor left undeclared. That
  finding motivated binding compaction to a runtime manifest (P2g).

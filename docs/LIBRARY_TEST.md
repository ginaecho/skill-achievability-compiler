# Testing a tool-policy library with P2g

**Idea.** P2g relies on the model to state each skill's requirements with
`via` and `needs` (see [P2G_RUNTIME_BINDING.md](P2G_RUNTIME_BINDING.md)).
The alternative tested here keeps accumulated requirement knowledge as
checked data: the tool-policy library. Each entry maps an evidence pattern in
the skill text to a requirement: a resource, a runtime tool, a program or an
effect class. For example:

- "EAS Build" → `needs expo_account`;
- `mcp__notion__` → `via notion_mcp`;
- "Xcode" → `via macos_os`.

The library was seeded from execution reports of this sandbox.

- **Code:** `src/skillc/frontend/toolpolicy.py`.
- **Data:** `src/skillc/data/toolpolicy/library.json` (v1.0).

Two designs were tested, each against a plan committed before any test skill
was compacted or executed.

## Test 1: library in the prompt (TPL v0)

- **Pre-registration:** commit c4dee58.
- **Data:** `runs/20260926_tpl/`.
- **Test set:** 40 new skills, all executed blindly.

**How it works:**
- The skill's library matches become obligations listed in the prompt.
- Every obligation must appear on some Tool; a deterministic coverage check
  retries otherwise.
- The binder also applies the library:
  - forbidden effects are blocked;
  - unavailable programs are withdrawn;
  - `spawn` requires `agent_spawn`.

| method | recall | false rejections | decided accuracy |
|---|---|---|---|
| P2g | **12/14** | **2/24** | **34/38** |
| TPL v0 | 10/14 | 3/24 | 31/38 |

**Result: it failed 2 of its 3 criteria.** It lost 2 correct rejections to
P2g and added 1 false rejection.

The model covered every obligation, but made real requirements *optional*,
nudged by the library's hints about local alternatives. Pruning then removed
those optional branches.

## Test 2: library as a deterministic veto on P2g (v1)

- **Pre-registration:** commit f237fd2.
- **Data:** `runs/20260927_ext/`.

**How it works:**
- The library is never shown to the model.
- P2g's verdict is overridden to IMPOSSIBLE when the library finds, in the
  skill's **core statement**, a requirement the runtime cannot meet. The core
  statement is the frontmatter plus the intro before the first `## `
  heading.

**Test set:** 120 new skills, all executed blindly:
- 64 unused skills from the original corpus;
- 56 skills from a new corpus of 137 licensed skills
  (`benchmark/ce_sources_ext`), drawn from 6 repositories.

**Labels:** 80 achieved, 35 impossible, 5 inconclusive.

| method | recall | false rejections | decided accuracy | vs P2g (better / worse) |
|---|---|---|---|---|
| **P2g** | **33/35** | **10/80** | **103/115** | — |
| P2g + core veto (primary) | 33/35 | 14/80 | 99/115 | 0 / 4 |
| P2g + veto matching anywhere in the text | 35/35 | 31/80 | 84/115 | 2 / 21 |
| veto alone | 8/35 | 4/80 | 84/115 | 10 / 29 |

**Result: the veto failed all three criteria.**
1. It added no correct rejection.
2. It added 4 false rejections.
3. Decided accuracy fell from 103/115 to 99/115.

**Why:**
- **8 correct vetoes, all redundant.** Every one fell on a skill that P2g
  had already rejected: the model had written the same `needs`/`via` itself.
  These were Azure, AWS, Expo and GitHub accounts, and an MCP server.
- **4 false vetoes, all mentions rather than requirements:**
  - "LLM-as-judge" in agentic-eval and advanced-evaluation: the executor
    acted as the judge itself;
  - "boto3" in a local environment-setup skill;
  - an MCP prefix in openai-docs: the skill's documented web-search fallback
    worked.

  A text pattern cannot tell a mention from a requirement.

## Conclusion

The library's knowledge is mostly correct, but it does not improve P2g.

- **Shown to the model:** it pushed real requirements into optional
  branches.
- **Used as a veto:** it only repeats P2g's rejections or adds false ones.

It is still useful as an explanation of *why* a skill is impossible, but it
should not decide the verdict. **Use P2g alone.**

**Incidents:**
- One executor wrote a small folder of synthetic sample files into the
  repository root. It was moved out and never committed.
- Some executors installed system packages or toolchains, or started Docker.
- No executor wrote to an external service.

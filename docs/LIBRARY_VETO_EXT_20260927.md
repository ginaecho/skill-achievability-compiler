# P2g + tool-policy library (v1 veto): pre-registered test on 120 new skills

This test answers the question "why not P2g + library?". It was run on a
larger set of new cases.

- **Plan and criteria:** `runs/20260927_ext/PLAN.md`. It was committed
  (f237fd2) together with the frozen library v1.0, the veto code and the
  test-set definition, before any test skill was compacted or executed.
- **Data:** `runs/20260927_ext/`:
  - `comparison.json`: every metric and every case;
  - `execution/`: 120 blind execution reports;
  - `ext_ce_rt/`: prompts, replies and scorings.
- **Reproduction:** see the header of `scripts/compare_ext.py`.

## Result

**The library veto fails its pre-registered test.**
- On 120 new skills, P2g alone already catches 33 of the 35 confirmed
  impossibles.
- The core veto adds no correct rejection. Every correct veto duplicates a
  rejection P2g had already made.
- It adds 4 false rejections.
- **Recommendation: keep P2g without the veto.**

### Set

- **120 skills:**
  - 64 remaining skills of the original corpus, from the same repositories
    that seeded the library;
  - 56 skills from a new corpus of 137 licensed skills
    (`benchmark/ce_sources_ext`), drawn from 6 repositories, 3 of them new
    to the project.
- **Ground truth:** all 120 were executed blindly.
- **L2 labels:**

  | label | skills |
  |---|---|
  | achieved | 80 |
  | confirmed impossible | 35 |
  | inconclusive | 5 |

  Under L1 (missing tool only), 7 are confirmed impossible.

### Results (L2, 115 decided skills)

| method | IMPOSSIBLE | precision | recall | false rejections | decided accuracy | vs P2g (better / worse, McNemar p) |
|---|---|---|---|---|---|---|
| P1 (no repair) | 52 | 34/51 | 34/35 | 17/80 | 97/115 | 1 / 7, p = 0.07 |
| **P2g** | 44 | **33/43** | **33/35** (Wilson 95%: 0.81–0.98) | **10/80** | **103/115** (0.83–0.94) | — |
| P2g + core veto (primary) | 48 | 33/47 | 33/35 | 14/80 | 99/115 | 0 / 4, p = 0.125 |
| P2g + any veto | 70 | 35/66 | 35/35 | 31/80 | 84/115 | 2 / 21, p < 0.001 |
| core veto alone | 12 | 8/12 | 8/35 | 4/80 | 84/115 | 10 / 29, p = 0.003 |

Precision here counts decided rejections only, so it leaves out the 1
inconclusive skill that P2g rejected.

**P2g split by corpus part (decided accuracy):**
- original corpus: 54/61;
- new extension corpus: 49/54.

P2g held up on repositories it had never seen.

**L1 (missing tool only):** every CE method catches 7/7.

### Pre-registered criteria

1. **Recall gain of at least 10 points: not met.**
   - The gain is 0.0 points: both methods catch 33/35.
   - The criterion is also formally untestable, because P2g misses only 2
     confirmed impossibles, fewer than the pre-registered minimum of 4.
2. **Added false rejections: not met.**
   - The veto flips 4 skills to IMPOSSIBLE.
   - All 4 were achieved by the executor, so the precision of the flips
     is 0/4.
3. **Net gain: not met.** Decided accuracy falls from 103/115 to 99/115.

## Why the veto adds nothing here (case level)

The core veto fired on 12 skills.

- **8 correct fires:** eas-simulator, expo-dev-client,
  hf-cloud-aws-context-discovery, customize, microsoft-foundry,
  podcast-generation, gh-address-comments and chrome-mcp-troubleshooting.
  P2g had already rejected all 8, because the model had written the matching
  `needs`/`via` itself. The failure that motivated the library, requirements
  omitted by the compactor, did not occur on this set. P2g's
  runtime-manifest prompt, together with the counterexample-guided repair,
  already surfaces these requirements.
- **4 false fires.** The requirement is mentioned in the core statement but
  is not needed for the core deliverable:

  | skill | library match | what the executor did |
  |---|---|---|
  | agentic-eval | "LLM-as-judge" matched `llm_api_key` | acted as the judge itself |
  | advanced-evaluation | "LLM-as-judge" matched `llm_api_key` | acted as the judge itself |
  | hf-cloud-python-env-setup | "boto3" matched `aws_account` | the deliverable is a local environment setup |
  | openai-docs | `mcp__openaiDeveloperDocs__` matched an MCP server | fell back to the web search the skill itself documents |

  These are exactly the error class noted in the TPL report: a match marks a
  mention, not a requirement. The core-statement filter does not change
  that.
- **Any-scope veto:** it catches P2g's 2 misses (deploy and github-triage)
  and 3 inconclusive skills, at the cost of 21 extra false rejections.

## What P2g still gets wrong

- **Misses (2):**
  - microsoft `deploy`: P2g returned UNKNOWN, but the skill needs Azure
    credentials.
  - trailofbits `github-triage`: the skill needs an authenticated `gh`.
- **False rejections (10).** This is P2g's dominant error on this set:
  - Six rejected skills were scored achieved because the executor verified
    the local part of the deliverable and treated publishing as optional:
    - pr-writer, shipping-and-launch, make-repo-contribution: drafted the
      PR, launch plan or contribution without publishing it;
    - m365-agents-py: ran against local stubs instead of Azure Bot Service;
    - azure-messaging-webpubsub-java: generated a token offline;
    - ai-ready: produced local files only.
  - The other four were achieved with local tooling: define-goal,
    ruff-recursive-fix, web-design-reviewer and firebase-apk-scanner.

  Whether the six above are real false rejections depends on the reading of
  "core deliverable". The executors were told to pick the core deliverable.
  They sometimes judged the external step to be outside the core, where
  P2g's compactor judged it inside. This is the same core-versus-live-goal
  ambiguity identified in the P3 report. It is the largest remaining source
  of error, and neither the library nor the checker can settle it from the
  text alone.

## Secondary: P2g across three independent test sets (post hoc pooling)

P2g was frozen before all three sets were drawn: held-out 40, fresh 40,
ext 120. The labelled scenarios are not part of this pool.

| set | recall (L2) | false rejections | decided accuracy |
|---|---|---|---|
| held-out | 8/14 | 1/22 | 29/36 |
| fresh | 12/14 | 2/24 | 34/38 |
| ext | 33/35 | 10/80 | 103/115 |
| **pooled** | **53/63** (Wilson 95%: 0.73–0.91) | **13/126** (0.06–0.17) | **166/189** (0.82–0.92) |

## Conclusions

1. **Answer to "why not P2g + library":** it has now been tested as a
   deterministic veto kept out of the prompt, which was the design the TPL
   post-mortem proposed. It is not better than P2g. On the held-out set its
   gain was circular, because the library was seeded from that set. On two
   sets it did not see (fresh, ext) it adds false rejections and no correct
   ones.
2. **The library's knowledge is not wrong. It is redundant.**
   - When a requirement really is core, P2g's model already states it
     (8 of 8 correct vetoes duplicated P2g).
   - When it is only mentioned, the pattern cannot tell (4 of 4 new vetoes
     were false).
   - The useful residue is diagnostic. The library can explain *why* a skill
     is impossible, but it should not decide the verdict.
3. **Next error to attack:** core-versus-optional judgement of external
   steps (publish, deploy, submit). Both P2g's false rejections and its
   misses come from there. That calls for a better specification of the
   deliverable, for example a user-stated goal level, rather than more
   pattern knowledge.

## Incidents during execution (reported, not hidden)

- **Stray directory in the repository.**
  - The automate-this executor wrote an 8 KB `sample_data/Downloads/`
    directory (synthetic files) into the repository root, breaking its
    work-directory rule.
  - It was moved to the scratchpad and never committed.
  - Its label (achieved) is unaffected.
- **Host changes.** Several executors changed the host outside their work
  directories:
  - screenshot and aflpp installed system packages (apt);
  - cargo-fuzz and mutation-testing installed toolchains or tools under
    the home directory;
  - aspire started the Docker daemon;
  - jupyter-notebook created a user kernelspec, then removed it.

  None wrote to external services.
- **Malformed result file.** One result file (brand-guidelines) had a
  trailing comma. It was fixed at collection and marked `_note`; the content
  is unchanged.
- **Late launch.** One executor (accelerated-computing-cudf) was mistakenly
  launched late: it was marked as launched without being launched. Its
  prompt was identical.
- **Delegated executor prompts.** Executor prompts were delivered as files
  (`runs/20260927_ext/exec_prompts/`), each with the frozen template
  text. The subagent was told to read and follow its file.
- **Disk space.** Dependency caches filled the disk. They were cleared
  twice from finished work directories only.
- **Connectors.** No executor used a connector or MCP tool. Several used
  web search or fetch, which is permitted.

# Real-skill demo sources (research note)

Research-only survey, produced 2026-08-26, of five publicly available, first-party agent-skill /
agent-task artifacts suitable for demonstrating `skillc` on `ACHIEVABLE` and `IMPOSSIBLE` outcomes
across document generation, GitHub workflow, web research, deployment, and data analysis. Every
source below is an official vendor repository or official vendor documentation page, fetched
directly (GitHub Contents API / direct HTTP fetch) on 2026-08-26; no search-engine summary is used
as evidence without a primary-source fetch to back it. **No compiler code, corpus, paper, or test
was changed to produce this note** — the mapping into `skillc`'s declared-pack format
(`name`/`roles`/`capabilities`/`protocol`/`goal`, see [`README.md`](../README.md#what-the-checker-decides)
and the embedded-pack examples in [`examples/`](../examples)) below is a *proposal for a future
compaction*, not an applied change.

Method note: two of the five real skills already appear (compacted) in
[`docs/REAL_SKILLS_REPORT.md`](REAL_SKILLS_REPORT.md) — `docx` and `xlsx` under `anthropics/skills`.
They are included again here, with fresh primary-source citations against the repository's current
layout (it was restructured from `public/`+`examples/` into a single `skills/` tree since that
report was generated), because they remain the clearest first-party "document generation" and
"data analysis" artifacts and the report's own scan already gives an empirical achievable/impossible
contrast to build on (`docs/REAL_SKILLS_REPORT.md:3-4`, `:32-35`).

---

## 1. Document generation — Anthropic's `docx` skill

**Source:** <https://github.com/anthropics/skills/blob/main/skills/docx/SKILL.md>
(repo: `anthropics/skills`, path `skills/docx/SKILL.md`, fetched at commit
`3b3fad9`, blob SHA `fb954a460a1ea2294e9595e87fecce8df043eeba`).

**Provenance:** the repository README states the four document skills (`docx`, `pdf`, `pptx`,
`xlsx`) are "the document creation & editing skills that power Claude's document capabilities... under
the hood," and that they are **"source-available, not open source"** — distinct from the Apache-2.0
example skills in the same repo (`anthropics/skills:README.md`, "About This Repository" section).
The `SKILL.md` frontmatter itself repeats this: `license: Proprietary. LICENSE.txt has complete
terms`. Quoted here minimally for provenance; redistribute only the frontmatter/metadata, not the
full skill body, if reusing outside this note.

**Intended workflow (as written):** the skill is triggered whenever a `.docx`/`.dotx` file is the
deliverable. It prescribes three approaches keyed to the task — *create* with the `docx` npm
package, *edit* an existing file via `unzip → edit word/document.xml → zip`, or *read* via
`pandoc -t markdown` — then mandates a verification step ("After writing a `.docx`, render it and
look at it": `soffice.py --headless --convert-to pdf`, `pdftoppm`, then *read the images*).

**Required tools/capabilities (concrete, as named in the file):** a shell capable of running
`npm`/`node` (the `docx` package, preinstalled), `unzip`/`zip`, `pandoc`, LibreOffice (`soffice`),
`pdftoppm` (Poppler), plus the bundled helper scripts `scripts/office/soffice.py`,
`scripts/merge_runs.py`, `scripts/office/validate.py`, `scripts/accept_changes.py`,
`scripts/comment.py`.

**Adaptation into a `skillc` pack:**
- capabilities: `write_docx` (shell/`node`, `add: ["draft_written"]`), `render_preview` (`pre:
  "draft_written"`, `add: ["rendered"]` — the `soffice`→`pdftoppm` chain), `read_rendered_pages`
  (`pre: "rendered"`, `add: ["verified"]`), optionally `validate_xml` for the edit path.
- goal: `{"and": ["draft_written", "verified"]}` (the file's own two-step contract: write, then
  *look at what you wrote* before calling it done).
- **ACHIEVABLE demo:** grant all of the above under a shell-capable profile (analogous to this
  repo's `claude-code`/`claude-ai` profiles in `src/skillc/data`) — mirrors the existing
  `public/docx` → `ACHIEVABLE`/`ACHIEVABLE` row in `docs/REAL_SKILLS_REPORT.md:29`.
- **IMPOSSIBLE demo:** drop `render_preview` (no LibreOffice/`pdftoppm` in the profile) while
  keeping the goal's `verified` conjunct — a direct `MISSING_CAPABILITY`/`GOAL_UNSAT` case, and a
  realistic one: a restricted sandbox profile without an image-rendering capability cannot honor
  the skill's own mandatory verification step, exactly the asymmetry this compiler is built to
  name.

---

## 2. GitHub workflow — Copilot cloud agent + `github-mcp-server` pull-request tools

**Sources:**
- <https://docs.github.com/en/copilot/concepts/agents/cloud-agent/about-cloud-agent> (GitHub Docs,
  "About GitHub Copilot cloud agent," fetched 2026-08-26).
- <https://github.com/github/github-mcp-server> (repo `github/github-mcp-server`, `README.md`,
  MIT-licensed, blob SHA `d8d8695d2a51e0d9edb55130d9884b0da1de4312`), specifically its
  `pull_requests` toolset section and `Actions` toolset section.
- <https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments>
  ("Managing environments for deployment," GitHub Docs).

**Intended workflow (as documented):** "Copilot cloud agent can: Research a repository... Fix
bugs... [and] make code changes on a branch," after which a human "review[s] the diff, iterate[s],
and creates a pull request when [they're] ready" — or the agent opens the PR directly. The docs
explicitly frame this as agent-automated *up to* the PR: "Copilot automates branch creation, commit
message writing, and pushing... [the developer] chooses to create a pull request when ready"
(docs.github.com, "About GitHub Copilot cloud agent," "Benefits over traditional AI workflows").

**Required tools/capabilities (concrete, from the `github-mcp-server` tool catalog):**
`get_file_contents`, `issue_read`, a commit/push path, `create_pull_request` ("Open new pull
request" — `owner`, `repo`, `title`, `head`, `base`, `reviewers`), `request_copilot_review`
("Request Copilot review"), `pull_request_read` (`get_diff`, `get_status`, `get_files`), and
`merge_pull_request` ("Merge pull request"). The tool list is generated straight from the server's
own toolset table (`github-mcp-server:README.md`, "Pull Requests" and "Actions" `<details>`
sections).

**The natural impossibility:** GitHub's own environment-protection docs describe **required
reviewers** as an out-of-band, human-only gate: "specify people or teams that must approve workflow
jobs that use this environment... Only one of the required reviewers needs to approve the job for
it to proceed... to prevent users from approving workflow runs that they triggered, select Prevent
self-review" (docs.github.com, "Managing environments for deployment," step 6). Searching the full
`github-mcp-server` tool catalog for an approval-granting tool call (`grep -i "approve"` over the
fetched README) returns **no matching tool** — `merge_pull_request` exists, but nothing in the
declared catalog lets the *agent itself* satisfy a required-reviewer/no-self-review gate; that
approval is a GitHub-UI action taken by a distinct human.

**Adaptation into a `skillc` pack:**
- capabilities: `read_issue`, `push_branch`, `create_pull_request` (`add: ["pr_opened"]`),
  `request_copilot_review` (`pre: "pr_opened"`, `add: ["review_requested"]`), `merge_pull_request`
  (`pre: {"and": ["pr_opened", "reviewer_approved"]}`, `add: ["merged"]`).
- goal (achievable variant): `{"and": ["pr_opened", "review_requested"]}` — matches what the docs
  say the agent alone can guarantee.
- goal (impossible variant): `merged` with the same guard — since no capability in the declared
  catalog ever establishes `reviewer_approved` (it is a human UI action outside the tool surface),
  this is a clean `BLOCKED_GUARD`/`GOAL_UNSAT` case with a real-world justification, not a
  synthetic one: "self-review prevention" is a documented GitHub policy, not an authoring mistake.

---

## 3. Web research — MCP reference `fetch` server + Anthropic's orchestrator-workers pattern

**Sources:**
- <https://github.com/modelcontextprotocol/servers/blob/main/src/fetch/README.md> (repo
  `modelcontextprotocol/servers`, path `src/fetch/README.md`, MIT-licensed, blob SHA
  `7e2869983facdaec288b780afa30ae8b126c1c43`).
- <https://www.anthropic.com/engineering/building-effective-agents> (Anthropic engineering blog,
  "Building effective agents," fetched 2026-08-26; note the page's own header caveat that some
  tooling details postdate the article, which does not affect the workflow-pattern description
  used here).

**Intended workflow (as documented):** the MCP `fetch` server "enables LLMs to retrieve and process
content from web pages, converting HTML to markdown," with pagination via `start_index` for
reading long pages in chunks. It exposes exactly **one** tool, `fetch(url, max_length, start_index,
raw)` — there is no query/search endpoint (`modelcontextprotocol/servers:src/fetch/README.md`,
"Available Tools"). Anthropic's own workflow taxonomy describes the matching orchestration pattern
for open-ended research: "In the orchestrator-workers workflow, a central LLM dynamically breaks
down tasks, delegates them to worker LLMs, and synthesizes their results," citing as a fit "Search
tasks that involve gathering and analyzing information from multiple sources for possible relevant
information" (anthropic.com/engineering/building-effective-agents, "Workflow: Orchestrator-workers").

**Required tools/capabilities (concrete):** `fetch` (single known URL → markdown text, from the MCP
server) plus, per the orchestrator-workers description, an orchestrating LLM call that "breaks down
tasks" and "synthesizes results" from parallel worker calls — but the *source of URLs to fetch* is
never specified by either primary source: the `fetch` tool takes a URL as input, it does not
discover one.

**Adaptation into a `skillc` pack:**
- capabilities: `fetch_url` (`owner: "worker"`, `pre: "url_known"`, `add: ["page_fetched"]`),
  `synthesize` (`owner: "orchestrator"`, `pre: "page_fetched"`, `add: ["report_delivered"]`).
- **ACHIEVABLE demo:** a task that supplies the URLs up front (e.g., "summarize these three
  documentation pages") — `url_known` is established by the initial state, so `fetch_url` →
  `synthesize` is a straight achievable chain, a good "tolerance"/fan-out case (parallel `fetch`
  calls, `may`-reachability) similar to `corpus/build_corpus.py`'s `detour_ok`/`choice_one_branch_ok`
  shape.
  ​
- **IMPOSSIBLE demo:** a task phrased as "search the web for X and report back" with only the
  `fetch` server declared and no search tool granted — `url_known` has no establisher (nothing in
  the declared capability set turns a topic into a URL), which is a direct, real-world
  `MISSING_CAPABILITY`/`GOAL_UNSAT` instance: `fetch` is a *retrieval* primitive, not a *search*
  primitive, and the two are easy to conflate when hand-writing a `SKILL.md`.

---

## 4. Deployment — GitHub Actions environments + `required reviewers` protection rule

**Sources:**
- <https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments>
  ("Managing environments for deployment," GitHub Docs, fetched 2026-08-26).
- <https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments>
  (referenced by the above for the `required-reviewers`/`wait-timer`/`prevent-self-review` field
  definitions).
- <https://github.com/github/github-mcp-server> `README.md`, `Actions` toolset (`actions_get`,
  `actions_list`, `actions_run_trigger` — "Trigger GitHub Actions workflow actions").

**Intended workflow (as documented):** a repository defines a named **environment** (e.g.
`production`) with protection rules — required reviewers (up to six people/teams, only one
approval needed), an optional wait timer, and a deployment-branch restriction. "A job that
references an environment must follow any protection rules for the environment before running or
accessing the environment's secrets" (docs.github.com, "Managing environments for deployment,"
lede). An agent's realistic deployment task is: trigger the workflow (`actions_run_trigger` →
`run_workflow`), poll its status (`actions_get` → `get_workflow_run`), and the job itself performs
the deploy once the environment's gate clears.

**Required tools/capabilities (concrete):** `actions_run_trigger` (method `run_workflow`, `owner`,
`repo`, `ref`, `inputs`), `actions_get` (method `get_workflow_run`) — both from
`github-mcp-server`. Approving a pending environment deployment is a GitHub-UI/API action
(reviewing the deployment request) taken by one of the environment's named reviewers; it is not
exposed as a callable tool in the `github-mcp-server` catalog (the same `grep -i "approve"` sweep
used in §2 found no such tool).

**Adaptation into a `skillc` pack:**
- capabilities: `trigger_workflow` (`add: ["run_started"]`), `poll_run` (`pre: "run_started"`,
  `add: ["run_status_known"]`), `deploy_job` (`pre: {"and": ["run_status_known", "env_approved"]}`,
  `add: ["deployed"]`).
- **ACHIEVABLE demo:** an environment with *no* required reviewers configured (the default) —
  `env_approved` can be modeled as trivially true / absent from the guard, so `deployed` is
  reachable; this matches ordinary CI/CD deploys with no protection rule.
- **IMPOSSIBLE demo:** an environment with required reviewers **and** "Prevent self-review" enabled,
  where the triggering identity is the same agent — the declared capability set has no tool that
  establishes `env_approved` (approval is a distinct human's UI action, and self-approval is
  explicitly disallowed by the platform: docs.github.com, step 6.3, "prevent users from approving
  workflow runs that they triggered"). This is a `BLOCKED_GUARD` case grounded directly in a
  documented GitHub platform policy rather than an invented restriction.

---

## 5. Data analysis — Anthropic's `xlsx` skill

**Source:** <https://github.com/anthropics/skills/blob/main/skills/xlsx/SKILL.md> (repo
`anthropics/skills`, path `skills/xlsx/SKILL.md`, fetched at commit `3b3fad9`, blob SHA
`9da54804cc8c938586f89363c8da3b3a6e2a563d`; same "source-available, not open source" provenance as
§1 — frontmatter: `license: Proprietary. LICENSE.txt has complete terms`).

**Intended workflow (as written):** triggered whenever a spreadsheet file (`.xlsx`/`.xlsm`/`.csv`/
`.tsv`) is the primary input or output. It prescribes `openpyxl` for creating/editing formulas and
formatting, `pandas` for bulk data in/out, and `markitdown` for a quick read — then makes
recalculation **mandatory**: "openpyxl writes formulas as strings with no cached values... Until
you recalculate, every formula cell reads back as `None`," so every write must be followed by
`python scripts/recalc.py output.xlsx`, whose JSON `status` must read `success`, not `errors_found`,
before the file may ship ("Never ship while `recalc.py` reports `errors_found`").

**Required tools/capabilities (concrete):** a Python runtime with `openpyxl`, `pandas`, and
`markitdown` preinstalled, plus the bundled `scripts/recalc.py` (shells out to LibreOffice,
`soffice`) and `scripts/office/soffice.py`.

**Adaptation into a `skillc` pack:**
- capabilities: `write_formulas` (`add: ["draft_written"]`), `recalc` (`pre: "draft_written"`,
  `add: ["recalculated"]`, with a `nondet` on a `status` field modeling `success`/`errors_found`),
  `check_status` (`pre: "recalculated"`, guard `{"cmp": ["status", "==", "success"]}`, `add:
  ["verified"]`).
- goal: `{"and": ["draft_written", "verified"]}` — mirrors the skill's own hard requirement, and is
  a numeric/enum-refinement case in the same family as `corpus/build_corpus.py`'s `budget_ok`/
  `over_budget` pair.
- **ACHIEVABLE demo:** grant `write_formulas`, `recalc` (with LibreOffice present), and
  `check_status` — the skill's documented happy path.
- **IMPOSSIBLE demo:** drop `recalc` (no LibreOffice/`soffice` in the profile — a plausible
  restricted-sandbox profile) while keeping the `verified` goal conjunct: no capability can ever
  produce a `status == success` observation, so the goal is unsatisfiable on every run —
  `GOAL_UNSAT`, and a faithful one, since the skill text itself treats an un-recalculated file as
  categorically undeliverable, not merely unverified.

---

## License / provenance summary

| # | Repo / page | License (as stated by the source) |
|---|---|---|
| 1, 5 | `anthropics/skills` (`skills/docx`, `skills/xlsx`) | Repo overall: mixed (example skills Apache-2.0). The four document skills (`docx`, `pdf`, `pptx`, `xlsx`) are explicitly called out as **"source-available, not open source"** with a `Proprietary` license field pointing to a `LICENSE.txt` (`anthropics/skills:README.md`, "About This Repository"). Quoted minimally here (frontmatter + short excerpts); do not redistribute the full skill body without checking that `LICENSE.txt`. |
| 2, 4 | `github/github-mcp-server`, `docs.github.com` | `github-mcp-server` is MIT-licensed (`github/github-mcp-server:LICENSE`). `docs.github.com` pages are GitHub's official product documentation; excerpts here are short, attributed quotations for research/citation purposes. |
| 3 | `modelcontextprotocol/servers` (`src/fetch`) | Apache-2.0 for code/spec, CC-BY-4.0 for documentation, with some pre-relicensing contributions remaining MIT (`modelcontextprotocol/servers:LICENSE`). The `fetch` server's own `README.md` states it "is licensed under the MIT License." |
| 3 | `anthropic.com/engineering/building-effective-agents` | Anthropic's official engineering blog; short quotations only, for citation/attribution. |

All quotations above are kept short and attributed; none of the five sources' full text is
reproduced. The original note proposed pack-shaped mappings. The current end-to-end demo
instead downloads five Apache-2.0 natural-language skills from the pinned
`anthropics/skills` commit, compacts them live, schema-gates the generated packs,
and checks them. See `demo/real-skill-cases/results.json`; none of the proposed
manual mappings in this note is used as a demo input.

## Gaps and uncertainties

- The `github-mcp-server` and GitHub Docs "no approval tool" claim (§2, §4) is based on a
  case-insensitive grep for `approve` over the fetched `README.md` at blob SHA
  `d8d8695d2a51e0d9edb55130d9884b0da1de4312`; the server is under active development; a future
  toolset could add a deployment-review tool, which would flip that specific pack from `IMPOSSIBLE`
  to `ACHIEVABLE` under `cap_monotone` (Coq T3) once granted.
- `anthropics/skills` was restructured (from `public/`+`examples/` to a single `skills/` tree)
  since `docs/REAL_SKILLS_REPORT.md` was generated against an older layout/mount
  (`/mnt/skills`, `public/docx` etc.); path citations above use the current tree at commit `3b3fad9`.
- The five end-to-end demo cases differ from the proposed mappings above: they
  use the full upstream natural-language sources and preserve the actual Azure
  OpenAI outputs under `demo/real-skill-cases/generated-packs/`.

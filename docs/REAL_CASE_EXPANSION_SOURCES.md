# REAL Case Expansion — Sourced SKILL.md / Task Workflow Artifacts

Research note for the skill-achievability-compiler benchmark. Goal: identify 8-10
**additional** real, first-party SKILL.md/task-workflow artifacts (distinct from the
existing five Anthropics Apache-2.0 skills already in the benchmark: `webapp-testing`,
`mcp-builder`, `frontend-design`, `slack-gif-creator`, `algorithmic-art`), spanning at
least six task categories, with pinned commit SHAs, verified licenses, and a
positive/negative capability profile for each. All artifacts below were fetched and
verified directly via the GitHub API (`gh api`) on 2026-09-21; no search-engine
synthesis was trusted without a follow-up primary-source fetch.

**Benchmark selection:** eight of these nine candidates are selected.
`huggingface-llm-trainer` is excluded because its local license reference
is unresolved; the repository license is not used to override that ambiguity.
The other eight still cover six categories. Candidate restrictions below
are proposals, not ground-truth labels: the benchmark uses separately
specified tasks and contracts. In particular, lack of Go execution does
not make a static code review impossible, and lack of cloud write access
does not make writing a deployment plan impossible.

**Source-resolution correction:** the two Aspire plugin paths below are Git
symlinks, not full documents. The benchmark follows each link to
`skills/aspire-orchestration/SKILL.md` or `skills/aspire-deployment/SKILL.md`
at the same pinned commit and retains the original link bytes. See
`benchmark/compaction_sources/sources.json` for resolved URLs and hashes.
Licenses were fetched again at each source's exact commit.

**Scope discipline (per task instructions):** This note only *identifies and
characterizes* candidate artifacts. It does not download artifacts into the repo,
execute any tooling, provision infrastructure, or claim pass/fail outcomes. The parent
session is responsible for downloading selected artifacts and independently reviewing
scenario semantics, harness design, and the deterministic-vs-LLM compaction /
precision-recall evaluation.

---

## Methodology

1. Confirmed the user-supplied starting candidate (`google/langextract`) via
   `gh api repos/google/langextract/contents/...` and `gh api repos/.../commits?path=...`
   to pin the exact commit that introduced/last-touched the file.
2. Confirmed existence, license, and topic focus of candidate first-party repos
   (`microsoft/skills`, `microsoft/aspire-skills`, `huggingface/skills`, `cli/cli`)
   via `gh api repos/<owner>/<repo>` (checks `license.spdx_id` from GitHub's own
   license detector) and via `gh api repos/<owner>/<repo>/git/trees/<branch>?recursive=1`
   to enumerate real `SKILL.md` paths (not inferred).
3. Rejected candidates that failed verification:
   - `docker/claude-plugins` — repo exists but **`license: null`** (no LICENSE file,
     no GitHub-detected SPDX id). Excluded per the "prefer MIT/Apache-2.0/BSD,
     verify license" constraint.
   - `anthropics/skills` — `gh api repos/anthropics/skills/license` returned
     **404 Not Found** (no machine-detected license / ambiguous licensing for at
     least some contents). Excluded to avoid the proprietary/source-available
     document-skill trap the task warned about, and also to avoid re-covering the
     same org as the five existing benchmark skills.
   - `github/awesome-copilot` — repo-level license is MIT, and it does contain
     `skills/*/SKILL.md` paths, but many of its skills are personal-productivity/
     novelty prompts (e.g. `brag-sheet`, `daily-prep`, `namecheap`) rather than
     first-party product-team workflow artifacts, so it was not selected in favor
     of `cli/cli`'s `.github/skills/code-review/SKILL.md`, which is an official,
     actively used maintainer-review workflow for the `gh` CLI itself.
4. For every selected artifact, fetched the raw file content
   (`gh api repos/<owner>/<repo>/contents/<path> --jq .content` base64-decoded) to
   read the actual instructions, front-matter, and any **skill-local license
   override** in the YAML front matter (`license:` key), then cross-checked that
   override against the repo-level license file's own commit history.
5. Recorded the exact commit SHA that last touched each `SKILL.md` file (via
   `gh api repos/<owner>/<repo>/commits?path=<path>`, first result = most recent),
   and the exact commit SHA that last touched the repo's `LICENSE` file, so raw URLs
   are fully pinned and reproducible.

---

## License-override finding (important caveat)

Two of the nine artifacts declare a `license:` field **inside the SKILL.md YAML front
matter itself**, which is worth flagging because it can diverge from the repository's
top-level license:

- `microsoft/skills` and `microsoft/aspire-skills` skills consistently declare
  `license: MIT` in front matter, which **matches** the repo-level MIT license
  detected by GitHub (`gh api repos/microsoft/skills/license` → `MIT`;
  `gh api repos/microsoft/aspire-skills/license` → `MIT`). No conflict.
- `huggingface/skills`' `huggingface-llm-trainer/SKILL.md` declares
  `license: Complete terms in LICENSE.txt` — a vague, **non-SPDX, seemingly
  boilerplate placeholder**. The repo root contains no `LICENSE.txt` (only
  `LICENSE`, Apache-2.0, confirmed via `gh api repos/huggingface/skills/contents`
  and `gh api repos/huggingface/skills/license`). This front-matter string does not
  point to any resolvable file in the repo at the pinned commit. **Recommendation:**
  exclude this artifact from redistribution and the benchmark until the
  override is resolved. Do not infer permission from the repository-level
  license alone. Other `huggingface/skills` files
  (e.g. `huggingface-datasets/SKILL.md`, `hf-cli/SKILL.md`) carry **no** `license:`
  key at all, so no override risk there.
- `google/langextract`'s `skills/langextract-usage/SKILL.md` and `cli/cli`'s
  `.github/skills/code-review/SKILL.md` carry no front-matter license field; repo-level
  license governs (Apache-2.0 and MIT respectively).

---

## Selected artifacts (9 total, 6 categories)

### 1. Data extraction / analysis
**`google/langextract` — `skills/langextract-usage/SKILL.md`**
- Commit: `d0f086c947be3808c664901e1891fa57f6905fc8`
- Source: https://github.com/google/langextract/blob/d0f086c947be3808c664901e1891fa57f6905fc8/skills/langextract-usage/SKILL.md
- Raw: https://raw.githubusercontent.com/google/langextract/d0f086c947be3808c664901e1891fa57f6905fc8/skills/langextract-usage/SKILL.md
- License: Apache-2.0 (repo-level, no front-matter override)
  - License path: `LICENSE` @ commit `04b72333a09de4fe25c73dae35faa2f820914b9f`
  - License raw: https://raw.githubusercontent.com/google/langextract/04b72333a09de4fe25c73dae35faa2f820914b9f/LICENSE
- **Task description:** Guides an agent through `lx.extract()` structured-information
  extraction from unstructured text using few-shot examples, char-interval grounding,
  alignment-warning triage, and JSONL/visualization output.
- **Essential capabilities:** (a) install/import the `langextract` Python package,
  (b) construct `lx.data.ExampleData`/`lx.data.Extraction` few-shot examples with
  verbatim `extraction_text`, (c) call `lx.extract()` with a model id and API key
  env var, (d) filter results by `char_interval` grounding.
- **Incidental capabilities:** JSONL saving/visualization (`lx.io`, `lx.visualize`),
  Ollama/OpenAI provider switching, multi-document batching, prompt-validation
  strictness tuning — all optional refinements on top of the core extract call.
- **Realistic positive capability profile:** file write, outbound HTTPS to an LLM
  API (Gemini/OpenAI/local Ollama), Python execution.
- **Restricted negative (removes something essential):** revoke outbound network
  access to the LLM provider (no API key / no HTTPS egress) — `lx.extract()` cannot
  complete because every extraction call is itself an LLM request; there is no local
  fallback path in this skill's core workflow.
- **Alternative legal method still satisfying goal:** Yes, partially — a user could
  swap providers to a **local** Ollama server (`model_url`, no API key, no external
  egress) as documented in `references/providers.md`, so "no outbound API-key auth"
  is a *softer* negative than "no network at all." For the strict negative above
  (no network path whatsoever, including localhost), no alternative satisfies the
  goal — this is a case where the essential capability truly has no legal workaround.

### 2. Databases (relational)
**`microsoft/skills` — `.github/plugins/azure-sdk-dotnet/skills/azure-resource-manager-postgresql-dotnet/SKILL.md`**
- Commit: `073741f2fc5628b22e8a5f8b56fb3878c418ecb6`
- Source: https://github.com/microsoft/skills/blob/073741f2fc5628b22e8a5f8b56fb3878c418ecb6/.github/plugins/azure-sdk-dotnet/skills/azure-resource-manager-postgresql-dotnet/SKILL.md
- Raw: https://raw.githubusercontent.com/microsoft/skills/073741f2fc5628b22e8a5f8b56fb3878c418ecb6/.github/plugins/azure-sdk-dotnet/skills/azure-resource-manager-postgresql-dotnet/SKILL.md
- License: MIT (front-matter `license: MIT` **matches** repo-level MIT)
  - License path: `LICENSE` @ commit `d08b0c611440a5f78f15e677f9cbfe68303f9391`
  - License raw: https://raw.githubusercontent.com/microsoft/skills/d08b0c611440a5f78f15e677f9cbfe68303f9391/LICENSE
- **Task description:** Azure.ResourceManager.PostgreSql .NET SDK workflow — create
  a PostgreSQL Flexible Server, databases, firewall rules, HA config, backups, Entra
  ID admins, read replicas; includes auth via `DefaultAzureCredential`.
- **Essential capabilities:** Azure subscription/resource-group context,
  `ArmClient` auth (credential/token), outbound HTTPS to Azure Resource Manager API,
  ability to provision **billable cloud infrastructure** (this is a live
  create/update/delete workflow, not a simulation).
- **Incidental capabilities:** point-in-time restore, read-replica creation, server
  stop/start for cost saving, Entra ID administrator wiring — advanced/optional
  operations layered on the core create-server-and-database flow.
- **Realistic positive capability profile:** valid Azure credentials + ARM API
  network egress + permission to create resources in a resource group.
- **Restricted negative:** remove ARM **write** permission (read-only/Reader RBAC
  role) — the skill's core workflow (`CreateOrUpdateAsync`) fails at every step
  because server/database/firewall-rule creation requires Contributor-level write
  access; there is no read-only path to "create a PostgreSQL server."
- **Alternative legal method still satisfying goal:** No — provisioning requires
  write RBAC by definition; a read-only credential can only *list/describe* existing
  servers (`GetPostgreSqlFlexibleServers()`), which does not satisfy a "create a
  server" task. (Note: for the benchmark's safety constraints, this artifact's
  scenario should be scoped to **plan/describe-only** sub-tasks — never actually
  executed — since real execution would provision billable cloud infrastructure.)

### 3. Databases (NoSQL / management-plane)
**`microsoft/skills` — `.github/plugins/azure-sdk-dotnet/skills/azure-resource-manager-cosmosdb-dotnet/SKILL.md`**
- Commit: `073741f2fc5628b22e8a5f8b56fb3878c418ecb6`
- Source: https://github.com/microsoft/skills/blob/073741f2fc5628b22e8a5f8b56fb3878c418ecb6/.github/plugins/azure-sdk-dotnet/skills/azure-resource-manager-cosmosdb-dotnet/SKILL.md
- Raw: https://raw.githubusercontent.com/microsoft/skills/073741f2fc5628b22e8a5f8b56fb3878c418ecb6/.github/plugins/azure-sdk-dotnet/skills/azure-resource-manager-cosmosdb-dotnet/SKILL.md
- License: MIT (front-matter matches repo-level; same LICENSE ref as artifact #2)
- **Task description:** Azure.ResourceManager.CosmosDB .NET SDK — explicitly scoped
  to **management-plane only** (accounts/databases/containers/throughput/RBAC), with
  the SKILL.md itself warning "NOT for data plane operations... use
  Microsoft.Azure.Cosmos for that."
- **Essential capabilities:** ARM auth (`DefaultAzureCredential`/`ArmClient`),
  subscription/resource-group access, write permission to create Cosmos accounts,
  outbound HTTPS to ARM.
- **Incidental capabilities:** autoscale-vs-manual throughput switching, key/
  connection-string retrieval, Cassandra/Gremlin/MongoDB/Table API sub-resources —
  optional beyond the core account+database+container creation path.
- **Realistic positive capability profile:** same as artifact #2 (valid Azure
  Contributor-level credential + ARM network egress).
- **Restricted negative:** remove ARM write RBAC (Reader-only) — account/database/
  container creation (`CreateOrUpdateAsync`) fails identically to artifact #2.
- **Alternative legal method still satisfying goal:** No, for the same reason as
  #2 — this is a genuinely separate essential-capability removal, distinguishing
  "management plane create" (needs write) from "data plane read" (a different,
  unrelated SDK/skill entirely, per the skill's own explicit disclaimer). Also
  worth noting as a paired example for the benchmark: #2 and #3 let you test
  whether the harness generalizes "needs cloud write RBAC" as an essential
  capability across two structurally similar but domain-distinct skills.

### 4. Containers / infrastructure (orchestration)
**`microsoft/aspire-skills` — `.github/plugins/aspire-skills/skills/aspire-orchestration/SKILL.md`**
(same content mirrored at `skills/aspire-orchestration/SKILL.md` in the same repo)
- Commit: `e40f7958497f255e48c1efe90c926f19fc496787`
- Source: https://github.com/microsoft/aspire-skills/blob/e40f7958497f255e48c1efe90c926f19fc496787/.github/plugins/aspire-skills/skills/aspire-orchestration/SKILL.md
- Raw: https://raw.githubusercontent.com/microsoft/aspire-skills/e40f7958497f255e48c1efe90c926f19fc496787/.github/plugins/aspire-skills/skills/aspire-orchestration/SKILL.md
- License: MIT (front-matter `license: MIT` matches repo-level)
  - License path: `LICENSE` @ commit `5987dd316a92cd32252db03c8c8a28e7a42156c5`
  - License raw: https://raw.githubusercontent.com/microsoft/aspire-skills/5987dd316a92cd32252db03c8c8a28e7a42156c5/LICENSE
- **Task description:** Manage the lifecycle (start/stop/wait/restart) of a local
  .NET Aspire distributed-application AppHost (which itself orchestrates containers/
  services), via VS Code lifecycle tools or the `aspire` CLI, with strict rules
  around file locks, worktree isolation, and "do not use for deploy" boundaries.
- **Essential capabilities:** local shell/process execution (`aspire` CLI or an
  editor's lifecycle tool), a pre-existing AppHost project on disk, ability to
  start/stop local processes and inspect local ports.
- **Incidental capabilities:** git-worktree isolation flags (`--isolated`), self-
  update commands (`aspire update --self`), hidden-resource `describe` diagnostics —
  refinements on top of core start/stop.
- **Realistic positive capability profile:** local process spawn/kill permission,
  filesystem read of the AppHost project, no cloud credentials required (purely
  local orchestration).
- **Restricted negative:** remove local process-spawn permission (e.g. a sandboxed
  agent with no ability to launch child processes/no port-bind permission) — the
  entire skill collapses because every core action (`aspire run`, `aspire stop`,
  `aspire wait`) requires spawning and supervising a local process tree.
- **Alternative legal method still satisfying goal:** No — there is no remote/API
  equivalent for "start my local AppHost" in this skill; it is inherently a local
  process-lifecycle capability. (This artifact and #5 below are a clean matched pair
  for testing the harness's ability to distinguish "local process control" essential
  capabilities from "cloud provisioning" essential capabilities.)

### 5. Containers / infrastructure (deployment)
**`microsoft/aspire-skills` — `.github/plugins/aspire-skills/skills/aspire-deployment/SKILL.md`**
- Commit: `e40f7958497f255e48c1efe90c926f19fc496787`
- Source: https://github.com/microsoft/aspire-skills/blob/e40f7958497f255e48c1efe90c926f19fc496787/.github/plugins/aspire-skills/skills/aspire-deployment/SKILL.md
- Raw: https://raw.githubusercontent.com/microsoft/aspire-skills/e40f7958497f255e48c1efe90c926f19fc496787/.github/plugins/aspire-skills/skills/aspire-deployment/SKILL.md
- License: MIT (front-matter matches repo-level; same LICENSE ref as artifact #4)
- **Task description:** Deploy an Aspire AppHost model to Docker Compose,
  Kubernetes/AKS, Azure Container Apps/App Service, or AWS, via `aspire publish`/
  `aspire deploy`/`aspire destroy`, with an explicit target-selection decision tree
  and a "confirm before provisioning billable resources" safety rule baked into the
  skill text itself.
- **Essential capabilities:** local `aspire` CLI execution, a valid AppHost with a
  configured deployment-environment resource, and (depending on target) either local
  Docker/kubectl/Helm tooling **or** cloud credentials (Azure/AWS) with provisioning
  rights.
- **Incidental capabilities:** CI/CD non-interactive flag wiring
  (`--non-interactive`), JavaScript/Vite/Next.js app-resource nuances, Radius
  preview-target support — all optional beyond "pick one target and deploy."
- **Realistic positive capability profile:** local CLI execution + target-specific
  credential (kubeconfig for Kubernetes, cloud credential for Azure/AWS, or just a
  local Docker daemon for Compose).
- **Restricted negative:** remove the ability to reach/authenticate to *any* deploy
  target (no Docker daemon, no kubeconfig, no cloud credential) — `aspire deploy`
  cannot complete for any target because every target branch in the decision tree
  requires at least one of these; the skill has no fully-local, credential-free
  deploy path.
- **Alternative legal method still satisfying goal:** Partially — if the *only*
  missing capability is cloud credentials but a local Docker daemon is present, the
  agent can legally satisfy "deploy this app" by choosing the Docker Compose target
  instead of Azure/AWS/Kubernetes (the skill's own decision tree explicitly supports
  this substitution). This makes artifact #5 a good "capability substitution is
  possible" case, contrasting with #4's "no substitution possible" case — useful
  for testing whether the harness's achievability compiler can reason about
  target-selection flexibility rather than treating the skill as monolithic.
  **Safety note:** any benchmark scenario using this artifact must stay at the
  plan/dry-run level (`--list-steps`, no real `aspire deploy`/`destroy` execution),
  per the "do not execute infrastructure" constraint.

### 6. Cloud / observability
**`microsoft/skills` — `.github/plugins/azure-sdk-java/skills/azure-monitor-opentelemetry-exporter-java/SKILL.md`**
- Commit: `67ae723a23ba880e3e5c8a3e5e2320092024476e`
- Source: https://github.com/microsoft/skills/blob/67ae723a23ba880e3e5c8a3e5e2320092024476e/.github/plugins/azure-sdk-java/skills/azure-monitor-opentelemetry-exporter-java/SKILL.md
- Raw: https://raw.githubusercontent.com/microsoft/skills/67ae723a23ba880e3e5c8a3e5e2320092024476e/.github/plugins/azure-sdk-java/skills/azure-monitor-opentelemetry-exporter-java/SKILL.md
- License: MIT (front-matter matches repo-level; same LICENSE ref as artifact #2)
- **Task description:** Export OpenTelemetry traces/metrics/logs from a Java
  application to Azure Monitor/Application Insights; covers span creation,
  attributes, custom span processors, exception recording, and metrics (counters/
  histograms). The SKILL.md itself flags this exact package as **deprecated** in
  favor of `azure-monitor-opentelemetry-autoconfigure`, and documents the migration
  path — a realistic "skill describing a semi-obsolete but still-functional API"
  case.
- **Essential capabilities:** a valid Application Insights connection string
  (`APPLICATIONINSIGHTS_CONNECTION_STRING`), outbound HTTPS egress from the
  instrumented process to Azure Monitor's ingestion endpoint, JVM/Java runtime.
- **Incidental capabilities:** custom `SpanProcessor` registration, nested-span
  parent/child linking, histogram/counter metric definitions — refinements on the
  core "instrument and export" workflow.
- **Realistic positive capability profile:** outbound HTTPS from the app process to
  `*.in.applicationinsights.azure.com`, valid connection string, Java 8+ runtime.
- **Restricted negative:** revoke outbound network egress from the instrumented
  process (e.g., an isolated/air-gapped sandbox) — telemetry export cannot occur
  because the exporter's entire job is shipping spans/metrics to a remote Azure
  ingestion endpoint; there is no local sink in this skill's core workflow.
- **Alternative legal method still satisfying goal:** No full substitute inside
  *this* skill, but note for the harness: OpenTelemetry itself supports a local
  `ConsoleSpanExporter`/OTLP-to-local-collector fallback that is **outside this
  skill's scope** — a good test of whether the achievability compiler correctly
  scopes "essential capability" to what the skill's own instructions actually cover,
  rather than what the underlying library could theoretically do.

### 7. ML / model / dataset work (data-plane, read-only)
**`huggingface/skills` — `skills/huggingface-datasets/SKILL.md`**
- Commit: `b3df145a3a5a3e64ac075d781c625896d9d2bfcd`
- Source: https://github.com/huggingface/skills/blob/b3df145a3a5a3e64ac075d781c625896d9d2bfcd/skills/huggingface-datasets/SKILL.md
- Raw: https://raw.githubusercontent.com/huggingface/skills/b3df145a3a5a3e64ac075d781c625896d9d2bfcd/skills/huggingface-datasets/SKILL.md
- License: Apache-2.0 (repo-level, no front-matter override on this file)
  - License path: `LICENSE` @ commit `2a30f92beb97bd8815c9e516e1e7995d5fb9bd45`
  - License raw: https://raw.githubusercontent.com/huggingface/skills/2a30f92beb97bd8815c9e516e1e7995d5fb9bd45/LICENSE
- **Task description:** Use the Hugging Face **Dataset Viewer API**
  (`https://datasets-server.huggingface.co`) to validate, list splits, preview,
  paginate, search/filter, and pull parquet/statistics for a dataset; also covers
  dataset creation/upload flows (Hub UI or `@huggingface/hub` CLI) and a distinct
  "agent trace upload" sub-workflow with explicit privacy defaults (private-by-
  default because traces may contain secrets/PII).
- **Essential capabilities:** outbound HTTPS to `datasets-server.huggingface.co`
  (read path is fully unauthenticated for public datasets); for gated/private
  datasets, a valid `Authorization` bearer token is required.
- **Incidental capabilities:** dataset upload via `npx @huggingface/hub` or `hf`
  CLI, Croissant metadata retrieval, agent-trace-specific upload conventions — all
  additive beyond the core read/paginate/search workflow.
- **Realistic positive capability profile:** outbound HTTPS egress, no credential
  needed for the *public-dataset read* scenario.
- **Restricted negative:** revoke outbound HTTPS egress entirely — every endpoint
  in the core workflow (`/is-valid`, `/splits`, `/first-rows`, `/rows`, `/search`,
  `/parquet`) fails because the skill is a thin wrapper around remote HTTP GETs;
  there is no offline/local dataset-server equivalent documented in this skill.
- **Alternative legal method still satisfying goal:** Partially — if the dataset is
  already cached locally (e.g., via the separate `datasets` Python library's local
  cache) a workaround *outside this skill's documented scope* could inspect rows
  without the Viewer API, but that requires a different tool/skill entirely, so
  within the bounds of *this* skill, network egress is a hard essential dependency.

### 8. ML / model / dataset work (cloud-GPU training)
**`huggingface/skills` — `skills/huggingface-llm-trainer/SKILL.md`**
- Commit: `d0d3f4301358fc1351d408a58596d5644b5a8114`
- Source: https://github.com/huggingface/skills/blob/d0d3f4301358fc1351d408a58596d5644b5a8114/skills/huggingface-llm-trainer/SKILL.md
- Raw: https://raw.githubusercontent.com/huggingface/skills/d0d3f4301358fc1351d408a58596d5644b5a8114/skills/huggingface-llm-trainer/SKILL.md
- License: **Front-matter override flagged, not trusted at face value** — declares
  `license: Complete terms in LICENSE.txt`, but no `LICENSE.txt` exists anywhere in
  the repo root at this commit (`gh api repos/huggingface/skills/contents` lists
  only `LICENSE`). This candidate is **excluded** from the benchmark pending
  resolution of the local license reference. Repository license evidence alone
  is not treated as permission for this file. Repository license path: `LICENSE` @ commit
  `2a30f92beb97bd8815c9e516e1e7995d5fb9bd45` (same as artifact #7).
  License raw: https://raw.githubusercontent.com/huggingface/skills/2a30f92beb97bd8815c9e516e1e7995d5fb9bd45/LICENSE
- **Task description:** Fine-tune/train LLMs or VLMs using TRL (SFT/DPO/GRPO/reward
  modeling) or Unsloth on **Hugging Face Jobs** (managed cloud GPUs), submitted via
  an `hf_jobs()` MCP tool call rather than local execution; includes GGUF conversion,
  Trackio monitoring, and Hub-auth requirements.
- **Essential capabilities:** access to the `hf_jobs()` MCP tool (implies a
  configured Hugging Face Jobs account/billing), a valid Hub authentication token,
  outbound network access from the orchestrating agent to the HF Jobs submission
  API.
- **Incidental capabilities:** Unsloth-specific VRAM-saving code paths, GGUF
  conversion for local (Ollama/LM Studio) deployment, Trackio dashboard wiring —
  optional beyond "submit a training job."
  Note this artifact's own instructions are unusually **prescriptive/mandatory**
  ("You MUST create the training script AND submit the job immediately"), which is
  itself a useful stress case for an achievability compiler: it tests whether the
  harness can recognize an essential capability (paid cloud-GPU job submission) that
  the skill's own text treats as non-optional even when a user might prefer a dry
  run.
- **Realistic positive capability profile:** working `hf_jobs()` tool/MCP
  connection, valid `HF_TOKEN`, outbound HTTPS.
- **Restricted negative:** remove access to the `hf_jobs()` tool/HF Jobs account
  (e.g., no billing enabled, tool not registered) — the skill's mandatory directive
  ("ALWAYS use `hf_jobs()` MCP tool... NOT bash `trl-jobs` commands") explicitly
  forbids the CLI fallback, so job submission cannot proceed through this skill's
  sanctioned path.
- **Alternative legal method still satisfying goal:** Only outside this skill's
  rules — the underlying `trl-jobs` CLI or fully local GPU training could
  technically achieve "train a model," but the skill text explicitly instructs the
  agent **not** to use the bash/CLI path, making that alternative a policy
  violation of the skill's own instructions rather than a legal in-skill substitute.
  This is a strong example of an "essential capability with no *sanctioned*
  workaround," useful for testing negative cases where a technical workaround
  exists but is explicitly disallowed by the skill author.

### 9. Documentation / collaboration / source control
**`cli/cli` — `.github/skills/code-review/SKILL.md`**
- Commit: `d6cbbe9f1c27018a67d1039f1c625471a359def5`
- Source: https://github.com/cli/cli/blob/d6cbbe9f1c27018a67d1039f1c625471a359def5/.github/skills/code-review/SKILL.md
- Raw: https://raw.githubusercontent.com/cli/cli/d6cbbe9f1c27018a67d1039f1c625471a359def5/.github/skills/code-review/SKILL.md
- License: MIT (repo-level, no front-matter override; `cli/cli` uses default branch
  `trunk`, confirmed via `gh api repos/cli/cli/license`)
  - License path: `LICENSE` @ commit `7f3bc25e3ae3833518cbc0efa6ff61aba709e8a4`
  - License raw: https://raw.githubusercontent.com/cli/cli/7f3bc25e3ae3833518cbc0efa6ff61aba709e8a4/LICENSE
- **Task description:** An official reviewer-persona workflow for reviewing GitHub
  CLI (`gh`) pull requests: establish intent from linked issues/PR history, apply
  the repo's `AGENTS.md` root contract and task-specific guides (command
  development, testing, API/hosts), classify findings by severity
  (🛑 Requirement / 💭 Commentary / 💅 Nit), and follow a strict reporting template
  distinguishing breaking vs. non-breaking (interactive vs. non-interactive contract)
  changes.
- **Essential capabilities:** read access to the PR diff, its linked issue/comments,
  and repo history (git log/blame or GitHub API for related issues/PRs/commits);
  read access to `AGENTS.md` and the referenced docs (`docs/command-development.md`,
  `docs/testing.md`, `docs/api-and-hosts.md`); ability to run `go test ./...` and
  `make lint`/`golangci-lint` to verify claims before reporting them (the skill
  explicitly says "verify a claim against the code before raising it").
- **Incidental capabilities:** running `golangci-lint fmt --diff` for style nits,
  searching for prior maintainer decisions across issues/PRs/commits — thorough but
  not strictly required to produce *a* review; the mandatory minimum is reading the
  diff + root contract + relevant guide.
- **Realistic positive capability profile:** local git repo checkout, GitHub API/CLI
  read access (issues, PRs, commit history), local Go toolchain to run tests/lint.
- **Restricted negative:** remove the ability to run `go test ./...`/`golangci-lint`
  locally (e.g., no Go toolchain, no build environment) — the skill explicitly
  requires verifying claims "against the code" and flagging "a failing `go test
  ./...` or `make lint`" as a blocking 🛑 Requirement finding; without local
  execution, the reviewer cannot distinguish "observed failures from checks that
  were not run," which the skill explicitly calls out as a distinction that must be
  preserved (i.e., removing this capability doesn't just degrade quality — it
  removes a rule the skill explicitly instructs the agent to honor).
- **Alternative legal method still satisfying goal:** Partially — a reviewer without
  local test execution could still produce a **valid, narrower** review scoped to
  static/logical issues, prior-decision contradictions, and scope/reviewability
  commentary, explicitly labeling untested claims as "not run" rather than
  "failing," which the skill's own template supports (the severity/labeling system
  doesn't strictly require local execution for every finding type — only for the
  specific "failing test/lint" 🛑 finding). This makes it a good "partial
  degradation, not total failure" negative case, contrasting with the harder
  negatives in artifacts #1, #4, #6, and #8.

---

## Machine-readable summary

```json
[
  {
    "id": "langextract-usage",
    "category": "data-extraction-analysis",
    "owner": "google",
    "repo": "langextract",
    "commit": "d0f086c947be3808c664901e1891fa57f6905fc8",
    "path": "skills/langextract-usage/SKILL.md",
    "source_url": "https://github.com/google/langextract/blob/d0f086c947be3808c664901e1891fa57f6905fc8/skills/langextract-usage/SKILL.md",
    "raw_url": "https://raw.githubusercontent.com/google/langextract/d0f086c947be3808c664901e1891fa57f6905fc8/skills/langextract-usage/SKILL.md",
    "license": "Apache-2.0",
    "license_path": "LICENSE",
    "license_raw_url": "https://raw.githubusercontent.com/google/langextract/04b72333a09de4fe25c73dae35faa2f820914b9f/LICENSE",
    "scenario": "Extract structured entities/attributes from unstructured text via lx.extract() with few-shot examples and char-interval grounding.",
    "essential_capability": "Outbound HTTPS access to an LLM provider (Gemini/OpenAI) or a local Ollama server; valid API key for hosted providers.",
    "negative_restriction": "No network egress of any kind (including localhost) removes the ability to call any provider, hosted or local."
  },
  {
    "id": "azure-arm-postgresql-dotnet",
    "category": "databases",
    "owner": "microsoft",
    "repo": "skills",
    "commit": "073741f2fc5628b22e8a5f8b56fb3878c418ecb6",
    "path": ".github/plugins/azure-sdk-dotnet/skills/azure-resource-manager-postgresql-dotnet/SKILL.md",
    "source_url": "https://github.com/microsoft/skills/blob/073741f2fc5628b22e8a5f8b56fb3878c418ecb6/.github/plugins/azure-sdk-dotnet/skills/azure-resource-manager-postgresql-dotnet/SKILL.md",
    "raw_url": "https://raw.githubusercontent.com/microsoft/skills/073741f2fc5628b22e8a5f8b56fb3878c418ecb6/.github/plugins/azure-sdk-dotnet/skills/azure-resource-manager-postgresql-dotnet/SKILL.md",
    "license": "MIT",
    "license_path": "LICENSE",
    "license_raw_url": "https://raw.githubusercontent.com/microsoft/skills/d08b0c611440a5f78f15e677f9cbfe68303f9391/LICENSE",
    "scenario": "Provision/manage an Azure PostgreSQL Flexible Server, database, firewall rules, HA, and backups via the .NET ARM SDK.",
    "essential_capability": "Azure ARM write (Contributor-level) RBAC credential plus outbound HTTPS to management.azure.com.",
    "negative_restriction": "Reader-only RBAC removes all create/update/delete capability; only list/describe remains possible."
  },
  {
    "id": "azure-arm-cosmosdb-dotnet",
    "category": "databases",
    "owner": "microsoft",
    "repo": "skills",
    "commit": "073741f2fc5628b22e8a5f8b56fb3878c418ecb6",
    "path": ".github/plugins/azure-sdk-dotnet/skills/azure-resource-manager-cosmosdb-dotnet/SKILL.md",
    "source_url": "https://github.com/microsoft/skills/blob/073741f2fc5628b22e8a5f8b56fb3878c418ecb6/.github/plugins/azure-sdk-dotnet/skills/azure-resource-manager-cosmosdb-dotnet/SKILL.md",
    "raw_url": "https://raw.githubusercontent.com/microsoft/skills/073741f2fc5628b22e8a5f8b56fb3878c418ecb6/.github/plugins/azure-sdk-dotnet/skills/azure-resource-manager-cosmosdb-dotnet/SKILL.md",
    "license": "MIT",
    "license_path": "LICENSE",
    "license_raw_url": "https://raw.githubusercontent.com/microsoft/skills/d08b0c611440a5f78f15e677f9cbfe68303f9391/LICENSE",
    "scenario": "Provision/manage an Azure Cosmos DB account, SQL database, container, and throughput settings via the .NET ARM management-plane SDK.",
    "essential_capability": "Azure ARM write (Contributor-level) RBAC credential plus outbound HTTPS to management.azure.com.",
    "negative_restriction": "Reader-only RBAC removes all create/update/delete capability; data-plane CRUD is explicitly out of scope for this skill."
  },
  {
    "id": "aspire-orchestration",
    "category": "containers-infrastructure",
    "owner": "microsoft",
    "repo": "aspire-skills",
    "commit": "e40f7958497f255e48c1efe90c926f19fc496787",
    "path": ".github/plugins/aspire-skills/skills/aspire-orchestration/SKILL.md",
    "source_url": "https://github.com/microsoft/aspire-skills/blob/e40f7958497f255e48c1efe90c926f19fc496787/.github/plugins/aspire-skills/skills/aspire-orchestration/SKILL.md",
    "raw_url": "https://raw.githubusercontent.com/microsoft/aspire-skills/e40f7958497f255e48c1efe90c926f19fc496787/.github/plugins/aspire-skills/skills/aspire-orchestration/SKILL.md",
    "license": "MIT",
    "license_path": "LICENSE",
    "license_raw_url": "https://raw.githubusercontent.com/microsoft/aspire-skills/5987dd316a92cd32252db03c8c8a28e7a42156c5/LICENSE",
    "scenario": "Start/stop/wait/restart a local .NET Aspire AppHost (local distributed-application/container orchestration) via CLI or editor lifecycle tools.",
    "essential_capability": "Local process spawn/supervise permission and filesystem read of the AppHost project; no cloud credential required.",
    "negative_restriction": "No local process-spawn/port-bind permission (fully sandboxed agent) removes every core start/stop/wait action."
  },
  {
    "id": "aspire-deployment",
    "category": "containers-infrastructure",
    "owner": "microsoft",
    "repo": "aspire-skills",
    "commit": "e40f7958497f255e48c1efe90c926f19fc496787",
    "path": ".github/plugins/aspire-skills/skills/aspire-deployment/SKILL.md",
    "source_url": "https://github.com/microsoft/aspire-skills/blob/e40f7958497f255e48c1efe90c926f19fc496787/.github/plugins/aspire-skills/skills/aspire-deployment/SKILL.md",
    "raw_url": "https://raw.githubusercontent.com/microsoft/aspire-skills/e40f7958497f255e48c1efe90c926f19fc496787/.github/plugins/aspire-skills/skills/aspire-deployment/SKILL.md",
    "license": "MIT",
    "license_path": "LICENSE",
    "license_raw_url": "https://raw.githubusercontent.com/microsoft/aspire-skills/5987dd316a92cd32252db03c8c8a28e7a42156c5/LICENSE",
    "scenario": "Deploy an Aspire AppHost model to Docker Compose, Kubernetes/AKS, Azure, or AWS via aspire publish/deploy/destroy (plan/dry-run only for benchmark safety).",
    "essential_capability": "Local aspire CLI plus at least one reachable deploy-target credential/daemon (Docker daemon, kubeconfig, or cloud credential).",
    "negative_restriction": "No reachable target at all (no Docker daemon, no kubeconfig, no cloud credential) removes every deploy branch in the decision tree."
  },
  {
    "id": "azure-monitor-opentelemetry-exporter-java",
    "category": "cloud-observability",
    "owner": "microsoft",
    "repo": "skills",
    "commit": "67ae723a23ba880e3e5c8a3e5e2320092024476e",
    "path": ".github/plugins/azure-sdk-java/skills/azure-monitor-opentelemetry-exporter-java/SKILL.md",
    "source_url": "https://github.com/microsoft/skills/blob/67ae723a23ba880e3e5c8a3e5e2320092024476e/.github/plugins/azure-sdk-java/skills/azure-monitor-opentelemetry-exporter-java/SKILL.md",
    "raw_url": "https://raw.githubusercontent.com/microsoft/skills/67ae723a23ba880e3e5c8a3e5e2320092024476e/.github/plugins/azure-sdk-java/skills/azure-monitor-opentelemetry-exporter-java/SKILL.md",
    "license": "MIT",
    "license_path": "LICENSE",
    "license_raw_url": "https://raw.githubusercontent.com/microsoft/skills/d08b0c611440a5f78f15e677f9cbfe68303f9391/LICENSE",
    "scenario": "Instrument a Java app with OpenTelemetry spans/metrics and export them to Azure Monitor/Application Insights (skill flags this exact package as deprecated in favor of the autoconfigure package).",
    "essential_capability": "Outbound HTTPS egress from the instrumented process to the Application Insights ingestion endpoint plus a valid connection string.",
    "negative_restriction": "No outbound network egress from the instrumented process (air-gapped sandbox) removes all telemetry export; no local sink is documented in this skill."
  },
  {
    "id": "huggingface-datasets",
    "category": "ml-model-dataset",
    "owner": "huggingface",
    "repo": "skills",
    "commit": "b3df145a3a5a3e64ac075d781c625896d9d2bfcd",
    "path": "skills/huggingface-datasets/SKILL.md",
    "source_url": "https://github.com/huggingface/skills/blob/b3df145a3a5a3e64ac075d781c625896d9d2bfcd/skills/huggingface-datasets/SKILL.md",
    "raw_url": "https://raw.githubusercontent.com/huggingface/skills/b3df145a3a5a3e64ac075d781c625896d9d2bfcd/skills/huggingface-datasets/SKILL.md",
    "license": "Apache-2.0",
    "license_path": "LICENSE",
    "license_raw_url": "https://raw.githubusercontent.com/huggingface/skills/2a30f92beb97bd8815c9e516e1e7995d5fb9bd45/LICENSE",
    "scenario": "Explore/query a Hugging Face dataset (splits, rows, search, filter, parquet, stats) via the public Dataset Viewer API.",
    "essential_capability": "Outbound HTTPS egress to datasets-server.huggingface.co; no credential needed for public datasets.",
    "negative_restriction": "No outbound network egress removes all Viewer API calls; the skill has no offline/local-cache equivalent documented."
  },
  {
    "id": "huggingface-llm-trainer",
    "category": "ml-model-dataset",
    "owner": "huggingface",
    "repo": "skills",
    "commit": "d0d3f4301358fc1351d408a58596d5644b5a8114",
    "path": "skills/huggingface-llm-trainer/SKILL.md",
    "source_url": "https://github.com/huggingface/skills/blob/d0d3f4301358fc1351d408a58596d5644b5a8114/skills/huggingface-llm-trainer/SKILL.md",
    "raw_url": "https://raw.githubusercontent.com/huggingface/skills/d0d3f4301358fc1351d408a58596d5644b5a8114/skills/huggingface-llm-trainer/SKILL.md",
    "license": "Apache-2.0 (repo-level; NOTE: SKILL.md front matter declares a non-resolvable 'license: Complete terms in LICENSE.txt' override that points to a file that does not exist in the repo -- flagged, not trusted)",
    "license_path": "LICENSE",
    "license_raw_url": "https://raw.githubusercontent.com/huggingface/skills/2a30f92beb97bd8815c9e516e1e7995d5fb9bd45/LICENSE",
    "scenario": "Submit an SFT/DPO/GRPO fine-tuning job for an LLM/VLM to Hugging Face Jobs (managed cloud GPUs) via the hf_jobs() MCP tool.",
    "essential_capability": "Working hf_jobs() MCP tool connection with a valid, billing-enabled Hugging Face account/token; the skill explicitly forbids the bash trl-jobs CLI fallback.",
    "negative_restriction": "No access to the hf_jobs() tool/account (no billing, tool unregistered) removes the only sanctioned submission path per this skill's own mandatory rules."
  },
  {
    "id": "gh-cli-code-review",
    "category": "documentation-collaboration-source-control",
    "owner": "cli",
    "repo": "cli",
    "commit": "d6cbbe9f1c27018a67d1039f1c625471a359def5",
    "path": ".github/skills/code-review/SKILL.md",
    "source_url": "https://github.com/cli/cli/blob/d6cbbe9f1c27018a67d1039f1c625471a359def5/.github/skills/code-review/SKILL.md",
    "raw_url": "https://raw.githubusercontent.com/cli/cli/d6cbbe9f1c27018a67d1039f1c625471a359def5/.github/skills/code-review/SKILL.md",
    "license": "MIT",
    "license_path": "LICENSE",
    "license_raw_url": "https://raw.githubusercontent.com/cli/cli/7f3bc25e3ae3833518cbc0efa6ff61aba709e8a4/LICENSE",
    "scenario": "Review a GitHub CLI (gh) pull request against the repo's AGENTS.md contract and task guides, classifying findings by severity and verifying claims by running tests/lint before reporting them.",
    "essential_capability": "Local Go toolchain to run 'go test ./...' and 'golangci-lint' to verify claims, plus read access to the PR diff, linked issue, and AGENTS.md/docs guides.",
    "negative_restriction": "No local Go build/test execution removes the ability to verify or report the skill's explicitly mandatory 'failing test/lint' 🛑 Requirement finding category, though a narrower static-only review remains possible."
  }
]
```

---

## Coverage summary

| Category | Artifacts |
|---|---|
| Data extraction/analysis | #1 langextract-usage |
| Databases | #2 azure-arm-postgresql-dotnet, #3 azure-arm-cosmosdb-dotnet |
| Containers/infrastructure | #4 aspire-orchestration, #5 aspire-deployment |
| Cloud/observability | #6 azure-monitor-opentelemetry-exporter-java |
| ML/model/dataset | #7 huggingface-datasets, #8 huggingface-llm-trainer |
| Documentation/collaboration/source control | #9 gh-cli-code-review |

9 candidates, of which 8 are admitted, covering 6 categories. No overlap with
the existing benchmark's five Anthropic skills
(different orgs, different repos, different licenses in several cases).

## Licensing/ground-truth caveats for the parent session

1. **`huggingface-llm-trainer`'s front-matter license override does not resolve to
   a real file** — the benchmark excludes this candidate rather than assuming
   the repository-level license resolves the artifact-level ambiguity.
2. **`docker/claude-plugins` and `anthropics/skills` were excluded** for license-
   verification failures (null/undetectable license), not for lack of relevant
   content — if the parent session has an independent legal basis to use them
   (e.g., explicit written permission), they could be reconsidered, but as
   default-search-derived candidates they did not clear the bar this task set.
3. **Artifacts #2, #3, and #5 describe skills whose *real* execution provisions
   billable cloud infrastructure or deploys workloads.** Per the task's "no
   executing infrastructure" constraint, any benchmark scenario built from these
   should be scoped to planning/description/dry-run sub-tasks (e.g., "describe the
   steps and required permissions," "run `--list-steps`"), never actual
   `CreateOrUpdateAsync`/`aspire deploy` execution against a live subscription.
4. All commit SHAs above were the **most recent commit that touched that exact
   path** at the time of research (2026-09-21), obtained via
   `gh api repos/<owner>/<repo>/commits?path=<path>`; they are not necessarily the
   repos' current HEAD, which is intentional for pinning reproducibility.
5. This note does not adjudicate the deterministic-vs-LLM compaction /
   precision-recall evaluation methodology itself — that harness and evaluation are
   explicitly the parent session's responsibility per the task's division of labor.

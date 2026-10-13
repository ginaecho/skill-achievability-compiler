# Microsoft Agent 365 Integration Research

Research date: **2026-10-13**

Scope: Understand what Microsoft Agent 365 is, how it relates to Microsoft 365 Agents SDK,
Microsoft Agent Framework, Microsoft Foundry, and Copilot Studio; its developer onboarding,
identity/authorization model, SDK languages, MCP tooling, and observability; and its actual
documented extension/interception points — in order to propose, not implement, candidate
integrations for SkillC (a Python, untrusted-intent-compaction → formal capability/protocol
pack → trusted Z3 static-admissibility-check pipeline). This document is **research and
proposal only**. No Agent 365 code, SDK, or tenant integration exists in this repository.
External claims cite Microsoft sources; the source list distinguishes directly retrieved
pages from links surfaced but not independently verified. Availability and licensing
statements should be checked for the target tenant before implementation.

---

## 1. Verified facts (Microsoft primary sources)

### 1.1 What Microsoft Agent 365 *is*

- Microsoft Agent 365 is described by Microsoft Learn as a product that provides the ability
  to **observe, govern, and secure** the growing number of agents within an organization,
  across three pillars (Observe / Govern / Secure), via a centralized Agent 365 registry in
  the Microsoft 365 admin center, Microsoft Entra, Microsoft Purview, and Microsoft Defender.
  Source: https://learn.microsoft.com/en-us/microsoft-agent-365/overview (ms.date
  2026-08-19, retrieved 2026-10-13).
- Per that same page: **"As of May 1, 2026, Microsoft Agent 365 is generally available for
  the Commercial segment on a per user basis."** It requires Microsoft E5 as a prerequisite,
  and at least one user must hold a qualifying Microsoft Agent 365 license.
  Source: https://learn.microsoft.com/en-us/microsoft-agent-365/overview, citing
  https://www.microsoft.com/security/blog/2026/05/01/microsoft-agent-365-now-generally-available-expands-capabilities-and-integrations/
- Agent 365 is **not** itself an agent-building framework. The SDK overview page states
  explicitly: *"The Microsoft Agent 365 SDK runs alongside these layers. It doesn't build,
  host, deploy, orchestrate, or execute the agent."* The three layers an adopter still owns
  are Model, Framework/runtime (LangChain, Microsoft Agent Framework, Semantic Kernel, OpenAI
  Agents SDK, Claude Agent SDK, or custom code), and Host.
  Source: https://learn.microsoft.com/en-us/microsoft-agent-365/developer/agent-365-sdk
  (ms.date 2026-10-09, retrieved 2026-10-13).

### 1.2 Agent 365 vs. Microsoft 365 Agents SDK vs. Agent Framework vs. Copilot Studio vs. Foundry

Microsoft Learn draws this distinction directly (same `agent-365-sdk` page, "Compare
Microsoft Agent 365 SDK and Microsoft 365 Agents SDK" section):

| Product | Official Microsoft description | Source |
|---|---|---|
| **Microsoft Agent 365 SDK** | "Doesn't build agents. Extends an agent that already exists to add identity, tooling, and notifications. Use Microsoft OpenTelemetry to add observability." | `agent-365-sdk` page above |
| **Microsoft 365 Agents SDK** | "A framework for building conversational agents. Handles message delivery across channels such as Teams and Microsoft Copilot, and manages conversation state." Linked as a distinct product at https://learn.microsoft.com/en-us/microsoft-365/agents-sdk/ | same page |
| **Microsoft Agent Framework** | Named in Agent 365 docs only as one of several *framework/runtime* options an agent may already be built with (alongside LangChain, Semantic Kernel, OpenAI Agents SDK, Claude Agent SDK). Agent 365 does not replace or subsume it. | `agent-365-sdk` and `choose-integration-option` pages |
| **Copilot Studio / Azure AI Foundry** | Listed as platforms with potential **built-in** Agent 365 integration (no SDK needed for some scenarios): *"Built-in integration ... Microsoft platforms and agents, such as Agent Builder, Copilot Studio, Azure AI Foundry, Copilot Cowork, and Researcher ... No SDK or custom-code integration. Administrative enablement might still be required."* Learn also notes: *"Copilot Studio and Azure AI Foundry can provide built-in Agent 365 integration for some scenarios ... Owning or deploying code alone doesn't determine the choice; compare the capabilities and authentication model for the specific scenario."* For Foundry-hosted agents it points to a separate Foundry Agent Service doc set. | https://learn.microsoft.com/en-us/microsoft-agent-365/developer/choose-integration-option (ms.date 2026-09-30) |

**Explicit conclusion from Microsoft, not inferred by this research**: *"The SDK isn't an
alternative to your agent framework, so 'build an agent' isn't one of these mechanisms.
Build the agent with your framework first, then use one of the preceding mechanisms[.]"*
(`choose-integration-option` page). This directly supports the constraint given by the
integration analysis: **Agent 365 must not be conflated with Agent Framework** — they are explicitly
differentiated as "control plane / governance layer" vs. "agent-building framework" by
Microsoft's own docs.

Three integration mechanisms are enumerated by Microsoft (`choose-integration-option` page),
none of which is "rewrite the agent":
1. **Built-in integration** — no SDK, for Microsoft-native or already-integrated platforms.
2. **Registry sync (preview)** — for external platforms (Google Vertex AI, AWS Bedrock);
   import-only, for visibility/governance, not code-level capability.
3. **Agent 365 SDK** — for agents built with an SDK/framework (Microsoft 365 Agents SDK,
   Microsoft Agent Framework, OpenAI Agents SDK, LangChain, CrewAI, LlamaIndex); added
   in the agent's own code for identity, tooling, notifications. Observability is handled by
   a *separate* package (Microsoft OpenTelemetry Distro), not the Agent 365 SDK itself.

### 1.3 Developer onboarding flow (documented)

The quickstart (https://learn.microsoft.com/en-us/microsoft-agent-365/developer/get-started,
ms.date 2026-09-17) documents:

- Prerequisites: an existing agent on **Python, Node.js, or .NET**; a Microsoft tenant with
  Agent 365 enabled, signed in as Global Administrator or "Agent ID Developer" (with a Global
  Administrator available for OAuth consent grants); an Azure subscription; a supported coding
  assistant (Claude Code, GitHub Copilot CLI, or VS Code agent mode); the `gh` CLI.
- Skills are installed via `gh skill add microsoft/agent365-skills`, then invoked by natural-
  language intent inside the coding assistant (e.g., "set up this project for Agent 365",
  "register this agent with Agent 365", "add observability to this agent") — not as literal
  CLI subcommands the developer memorizes.
- Stage flow: `a365-setup` (detect stack, route to **standard agent** vs **AI teammate**
  path) → `make-a365-agent` (register blueprint + agent identity + permissions) OR
  `make-ai-teammate` (adds hosting + message routing, **Frontier preview program only**) →
  `instrument-observability` (choose auth mode: OBO, Agentic-User, or S2S).
- **Licensing gate explicitly documented per capability**:
  - Identity: no additional license beyond tenant Agent 365 enablement.
  - Observability: requires at least one tenant user with **Microsoft 365 E7 or Microsoft
    Agent 365** license; otherwise *"telemetry is dropped silently"* and spans may be
    queryable only via Defender advanced hunting if the root `invoke_agent` span is missing.
  - Tooling (Work IQ): requires a **Microsoft 365 Copilot license**; Work IQ MCP itself is
    explicitly labeled **in preview**.
  - Notifications (agent's own user/mailbox/Teams presence): **Frontier preview program
    only**.

### 1.4 Identity, authorization, and tool-access model

- **Microsoft Entra Agent ID** is the identity substrate. An *agent identity* is "a special
  service principal in Microsoft Entra ID... It doesn't have credentials on its own." The
  **agent identity blueprint** is the reusable template holding credentials (federated
  identity credentials), from which agent identities are instantiated; agent identities only
  *authenticate* via FIC issued by the blueprint.
  Source: https://learn.microsoft.com/en-us/entra/agent-id/agent-identities (ms.date
  2026-03-30).
- Components of an agent identity: object `id`, display name, an optional human **sponsor**
  (accountable owner, used e.g. for incident contact), the blueprint, and an optional
  **agent's user account** (second, user-type Entra object, 1:1 with the agent identity, used
  when a system strictly requires a user-type principal — e.g., mailbox/Teams presence).
  Same source.
- Supported protocols at the identity-platform level: **OAuth 2.0, Model Context Protocol
  (MCP), and agent-to-agent (A2A)**.
  Source: https://learn.microsoft.com/en-us/entra/agent-id/what-is-microsoft-entra-agent-id
  (ms.date 2026-04-14).
- Governance surfaces explicitly listed: Conditional Access for agents, Identity Protection
  ("risky agents"), Identity governance (`agent-id-governance-overview`), network-level
  controls (Secure AI Gateway), and sign-in/audit logs for agents. Same source.
- Third-party agents (e.g., AWS Bedrock, n8n) can be given a governed Entra identity via the
  **Microsoft Entra ID Auth SDK (sidecar)** or **workload identity federation**, independent
  of Agent 365 licensing. Same source.
- **Agent 365 licensing is required specifically to extend Entra *security* features (not
  base identity) to agents**: *"Extending Microsoft Entra security features to agents
  requires Microsoft Agent 365. Agent 365 is included with Microsoft 365 E7 and is available
  as an add-on to Microsoft E5/A5/Business Premium..."* Same source.
- Tool access ("Tooling" capability) is delivered as **governed Work IQ MCP servers**,
  reaching Microsoft 365 workloads (Mail, Calendar, Word, SharePoint, Teams) "under admin
  control." Microsoft is explicit that **the Agent 365 SDK registers the MCP servers, but
  "your runtime still executes the tool calls"** — i.e., invocation/execution authority stays
  with the agent's own framework/runtime, not with Agent 365.
  Source: `agent-365-sdk` page, "What it is and what it isn't" section.
- The Work IQ overview and reference repository were surfaced during research but were not
  independently fetched. Exact tools, permission mappings, and reference-implementation
  compatibility remain unverified; do not use an assumed tool catalog as a capability grant.
  Follow-up sources: https://learn.microsoft.com/en-us/microsoft-agent-365/tooling-servers-overview
  and https://github.com/microsoft/work-iq.

### 1.5 SDK languages and packaging

- **Microsoft Agent 365 SDK**: delivered as **language-specific packages for Python,
  JavaScript, and .NET**. Install only the package(s) for the capabilities needed (identity,
  tooling, notifications); observability is a *separate* install.
  Source: `agent-365-sdk` page.
- **Microsoft OpenTelemetry Distro** (the observability package, distinct from the Agent 365
  SDK and from the now-**deprecated** "Agent 365 Observability SDK"): supports **.NET,
  Node.js, and Python**. Install via `pip install microsoft-opentelemetry` (Python ≥3.10),
  `npm install @microsoft/opentelemetry` (Node ≥18, ESM needs ≥20.6.0 with an `--import`
  loader flag), or the `Microsoft.OpenTelemetry` NuGet package (.NET). It is a single
  OpenTelemetry-standards-based distro that can export simultaneously to Azure Monitor, any
  OTLP-compatible backend (Datadog, Grafana, New Relic, etc.), and Microsoft Agent 365; it
  explicitly also supports Microsoft Foundry telemetry.
  Source: https://learn.microsoft.com/en-us/microsoft-agent-365/developer/microsoft-opentelemetry
  (ms.date 2026-10-01). Microsoft explicitly instructs: *"Don't use the deprecated Agent 365
  Observability SDK for new observability integrations. Use the Microsoft OpenTelemetry
  Distro."*
- The exporter "discovers its endpoint automatically based on tenant" and needs "a token
  resolver that returns an access token for a given agent ID and tenant ID," using one of
  three auth modes mirrored from the identity model: **OBO** (on-behalf-of a signed-in user),
  **Agentic-User** (agent's own user account — Frontier preview only), or **S2S**
  (service-to-service). Same source + `get-started` page.

### 1.6 Observability — what is and isn't proven

- Documented telemetry semantics: spans represent *"audited, traceable interactions,
  inference events, and tool usage"* and feed Microsoft Defender, Microsoft Purview, and the
  Microsoft 365 admin center *"after a test run."* A valid root `invoke_agent` span is
  required for spans to surface in those three UI surfaces even though the export call itself
  can return HTTP 200 without one. Source: `get-started` + `microsoft-opentelemetry` pages.
- Microsoft's own docs flag a silent-failure mode: **licensing gaps cause telemetry to be
  dropped without an API-visible error** — a caveat directly relevant to any claim that
  "exporting OTel spans" by itself proves ingestion into an Agent 365 tenant surface.

### 1.7 Extension/interception points actually documented

The retrieved documentation describes the following integration surfaces for an
externally-built agent; this is not an exhaustive assertion about all Microsoft APIs:

1. **Identity** — acquire/present an Entra agent-identity token (via blueprint-issued FIC),
   gating access to downstream resources at the IdP/authorization layer (Entra, Conditional
   Access, Purview DLP), **outside** the agent's own process.
2. **Tooling** — call governed Work IQ MCP servers (admin-scoped, preview) as one more set of
   MCP tool endpoints the agent's own runtime chooses to invoke; the agent's runtime remains
   the thing that decides *whether* and *how* to call a tool.
3. **Notifications** — inbound message/event delivery to an agent's own user account
   (Frontier preview only). This is not required for a first SkillC pilot.
4. **Observability** — emit OpenTelemetry spans from inside the agent process at points the
   adopter instruments (e.g., around an `invoke_agent` root span, tool calls, inference calls).
   This is an *emission* point, not an interception/blocking point: nothing in the cited docs
   describes Agent 365 or the OpenTelemetry Distro blocking, denying, or altering an agent's
   action before it executes. Enforcement/authorization is described as happening at the
   Entra/Conditional-Access/Purview layer against tokens and resources, not as a callback into
   agent logic before a tool call.

No Microsoft Learn page retrieved in this research describes a documented "pre-execution
policy callback," "admissibility check," or third-party static-validation hook point inside
the Agent 365 SDK itself. The closest analog — governed MCP tool scoping and admin policy —
is enforced by the MCP server/Entra/Purview stack server-side, not by a pluggable client-side
gate that a tool like SkillC could register into.

---

## 2. Verified SkillC implementation and integration gaps

*(Citations below are from the parent session's direct local inspection; this research agent
did not read SkillC source and relays them as given, for architectural framing only.)*

- SkillC's own relative-refutation framing (`README.md:3-19`, `CONTEXT.md:33-57`) already
  matches the posture Agent 365 itself requires for any checker that wants to make claims
  about agent behavior: IMPOSSIBLE is relative to declared contracts/frame assumptions,
  ACHIEVABLE means structural admissibility only, and UNKNOWN abstains. This is compatible
  with, but orthogonal to, Agent 365/Entra's own authorization semantics — Entra decides
  *whether a token is issued*; SkillC decides *whether a declared plan is structurally
  admissible against a declared capability/protocol pack*. Neither subsumes the other.
- `src/skillc/checker.py:724-772` — `check(pack, semantics='may', scope='protocol'|'goal')`:
  the default protocol scope judges the declared protocol. With `scope='goal'`, a
  protocol-only refutation degrades to `UNKNOWN`/`PROTOCOL_ONLY` unless a
  capability-context refutation establishes that alternative plans are also ruled out.
  Both modes consume the same pack schema, not a different or "fuller" pack.
  An adapter must report the decision scope and use reviewed grant/approval/effect
  contracts before interpreting a refutation as a business goal being unreachable.
- `src/skillc/frontend/grants.py:20-39` (`bind_grants`) filters environment grants by name
  only, independently of protocol; it has no concept of per-resource or delegated
  authorization (e.g., Entra scopes like `Mail.Send` scoped to a specific mailbox, or
  Conditional Access policy outcomes). An Agent 365/Entra adapter would need a richer grant
  model than today's name-only filter to faithfully represent Entra agent-identity scopes.
- `src/skillc/env/model.py:1-40,85-105` already has a provider-neutral principal/scope/role/
  deny/policy/MCP representation plus an explicit "unknown evidence" marker — structurally
  the right place to add an Entra-agent-identity-shaped principal, but no such mapping exists
  today.
- `src/skillc/env/mcp.py:1-19,130-148` observes MCP tool **names and descriptions** only,
  with a reusable `list_http_tools` helper; the generic probe lists **stdio tools only**
  today. Discovering that a Work IQ MCP server exposes a `send_mail` tool is not evidence
  that the current agent identity holds the Entra scope/admin policy to invoke it
  successfully, nor evidence of the tool's actual side effects. This is a hard structural gap
  for any claim of the form "SkillC verified this agent cannot send mail": discovery ≠ proof
  of effective permission, and MCP tool metadata is not a substitute for Entra scope/policy
  evaluation.
- `src/skillc/integrations/agent_framework.py:66-126,148-197,252-282` — the existing
  Agent Framework preflight/tool middleware can prevent a host-loop call by skipping
  `call_next` and returning a reason, but `fail_open=True` is the default and
  `SKILLC_MONITOR=off` can bypass it entirely; this middleware sits inside the **Agent
  Framework runtime** (one of the "framework/runtime" layers Agent 365 explicitly says it
  does not build or execute), and is architecturally a different integration point than
  anything Agent 365 documents. If this middleware is proposed as an "enforcement" boundary
  for any future Agent 365-adjacent pilot, it needs an explicit fail-closed policy decision,
  not a default.
- `:311-327` — the existing `telemetry_span` helper emits SkillC OpenTelemetry spans. Per
  §1.6 above, Microsoft's own docs warn that a successful exporter call (HTTP 200) does not
  by itself prove ingestion into any Agent 365 portal surface (Defender/Purview/admin
  center) — licensing gaps silently drop telemetry, and a missing root `invoke_agent` span
  silently limits visibility to Defender advanced hunting only. Reusing this span helper for
  an Agent 365 adapter is plausible in shape (both are OTel) but requires validating against
  the `microsoft-opentelemetry` package's specific span/attribute conventions, which have not
  been inspected in this research pass and are not confirmed compatible as-is.
- `src/skillc/monitor.py:552-635` — `gate` checks owner/precondition/tools; `post_action`
  applies *modeled* effects based on heuristic nonfailure, not structured evidence that a
  business outcome actually occurred. `:665` onward — runtime formulas don't track numeric
  variables, so numeric conditions resolve to unknown and **never deny**. This matters
  directly for any Agent 365-adjacent pilot scenario involving approval thresholds, spend
  limits, or other numeric gates: today's monitor cannot turn "amount > $10,000 requires a
  second approver" into a numeric-condition-based denial. Runtime formula unknown is not
  the same as a checker `UNKNOWN` verdict: the monitor currently does not deny on it.
- `src/skillc/monitor_mcp.py:1-29,90-116,200` onward — an advisory FastMCP stdio monitor
  with a root/current-session design; it is **not** documented or verified as a
  tenant-isolated, concurrent-request-safe shared service by default, which is a prerequisite
  for anything that would sit behind a multi-tenant Agent 365 control plane.
- **No Agent 365 adapter exists** in this repository (confirmed by the parent's search of
  `src/`, `tests/`, `examples/`). This research agent did not independently re-search the
  repository (per instructions) and relies on that search result.

**Net implication for scope**: Microsoft's own documented extension points for Agent 365 are
identity (Entra), governed MCP tool access (Work IQ, preview), notifications (Frontier
preview only), and OpenTelemetry emission — none of which is a "submit a plan for
pre-execution static admissibility checking" hook. Any SkillC↔Agent 365 integration is
therefore necessarily an **adapter that sits beside** Agent 365's documented surfaces (e.g.,
consuming Entra agent-identity/scope metadata as SkillC environment-model input, or emitting
SkillC verdicts as OpenTelemetry span attributes/events for Purview/Defender visibility), not
a plug-in to an Agent 365-provided enforcement callback, because no such callback is
documented.

---

## 3. Proposed applications (labeled PROPOSAL — not implemented, not endorsed as sufficient)

These are candidate directions only. None has been designed in code, none is claimed to work,
and none guarantees a business or security outcome.

**PROPOSAL A — Entra agent-identity-aware environment model.**
Extend `src/skillc/env/model.py`'s provider-neutral principal/scope representation with an
optional Entra-agent-identity-shaped view (blueprint, sponsor, scopes, agent's-user-account
flag) populated from data a human operator exports from the Microsoft Entra admin
center/Graph (per https://learn.microsoft.com/en-us/entra/agent-id/agent-identities), so that
a SkillC capability/protocol pack can declare "this agent identity holds scope X" as a frame
assumption, explicitly distinguishing a verified Entra scope grant from SkillC's current
name-only `bind_grants`. This would still only ever produce "structurally inadmissible given
the declared scope set," not a live, tenant-verified guarantee — SkillC would need to treat
the imported scope data as an input assumption, not ground truth it re-derives.

**PROPOSAL B — OpenTelemetry span bridge.**
Investigate whether SkillC's existing `telemetry_span` (per the parent's local citation) can
be adapted to also emit spans the Microsoft OpenTelemetry Distro / Agent 365 convention
recognizes (e.g., attributes consistent with an `invoke_agent` root span), so that a SkillC
verdict (ACHIEVABLE/IMPOSSIBLE/UNKNOWN plus the refuted contract) becomes visible as an event
or attribute on spans that eventually reach Defender/Purview/the admin center for a
Agent-365-registered agent. This is purely an observability/visibility proposal — it does not
make SkillC's check a gate on execution, and per §1.6, span delivery into those UI surfaces
has documented silent-failure modes (licensing, missing root span) that would need to be
independently verified in an actual tenant before any claim of successful ingestion.

**PROPOSAL C — Documented-gap-aware pilot scenario, not an enforcement claim.**
For a proposed pilot ("read SharePoint financial docs → finance analysis →
independent approval → send report via Outlook/Teams"), a SkillC capability/protocol pack
would need, at minimum: (a) a `send`-capable grant model that distinguishes "Mail.Send scope
granted" from "approved to send to this specific external recipient" (not present in
`bind_grants` today); (b) an explicit approval/role branch in the protocol pack so that
"independent approval occurred" is a precondition token the checker can see, rather than an
implicit assumption; and (c) a numeric-condition-capable runtime formula layer if any
approval threshold (e.g., dollar amount) is part of the contract, since `monitor.py`'s
current runtime formulas do not track numeric variables and would resolve such a condition to
unknown rather than deny. Approval predicates and role ownership already exist in the
finance protocol (`examples/hosted-agent-finance-group/protocol/quarterly_finance_report.ce`).
The new work is mapping them to authenticated approval evidence and Microsoft 365 tools,
not inventing approval semantics. This is a design gap list, not a roadmap commitment.

**PROPOSAL D — MCP tool-name discovery vs. Entra-scope-backed admissibility.**
Because `src/skillc/env/mcp.py` observes tool names/descriptions only (and currently only
over stdio for the generic probe), any Agent 365-adjacent pack should explicitly model the
difference between "a Work IQ MCP server advertises a `send_mail` tool" (discovery) and "the
current agent identity's Entra scopes and any admin/Conditional Access policy would actually
authorize invoking it" (authorization). Collapsing these two would make an IMPOSSIBLE/
ACHIEVABLE verdict unsound relative to the stated relative-refutation contract. This proposal
is to add a frame-assumption flag that forces such packs to declare which of the two they are
modeling, not to build an Entra policy evaluator.

---

## 4. Phased recommendation (PROPOSAL, non-binding)

1. **Phase 0 (current)** — No code change. Confirm the four facts above (Agent 365 ≠ Agent
   Framework; SDK languages; MCP preview status; OTel silent-failure modes) are understood by
   anyone designing an adapter, to avoid building against assumed/future capabilities that are
   not yet documented as GA (e.g., notifications/AI-teammate features remain Frontier-preview
   gated as of this research date).
2. **Phase 1 (design only)** — Specify an adapter boundary (not a checker rewrite) that
   converts an externally supplied, human-curated snapshot of Entra agent-identity scopes
   into SkillC's existing provider-neutral `env/model.py` shape, explicitly marked as an
   input assumption with an "unknown evidence" default where data is missing.
3. **Phase 2 (proposed implementation)** — Build a bounded Python Agent Framework pilot,
   registered with Agent 365, using a reviewed contract for reading financial documents,
   independent approval, and report delivery. Run static validation before execution and
   attach the existing middleware to every relevant client-side tool call. Define explicit
   failure policy and isolate state by tenant, identity, and conversation; do not treat the
   current shared-root MCP monitor as a production service.
4. **Phase 3 (runtime verification)** — Demonstrate that a denied tool is never invoked,
   a missing send grant is explained, approval cannot be fabricated by the writer, and
   `UNKNOWN` is not mislabeled `IMPOSSIBLE`. Use authenticated tool-result evidence before
   advancing approval/delivery predicates. Export correlated SkillC decision spans through
   the supported Microsoft observability path and verify visibility in the target tenant.
   Numeric thresholds and server-side tools remain out of scope until their enforcement
   paths are explicitly implemented and exercised.

This phasing is a suggestion for discussion, not a commitment, and is explicitly scoped to
avoid any deployment, account creation, secret handling, or model download, per the request's
constraints.

---

## 5. Uncertainties and open questions

- **GA date plausibility**: The Learn overview page states Agent 365 reached general
  availability "As of May 1, 2026," with a `ms.date` of 2026-08-19 on the retrieved page and a
  linked security-blog post dated 2026-05-01. Relative to this research's stated date
  (2026-10-13), these dates are in the past, which is internally consistent, but this
  research agent cannot independently corroborate the blog post content (it was not fetched
  directly in this pass) — treat the GA claim as sourced to Learn's own citation rather than
  independently re-verified against the blog.
- **Work IQ MCP preview scope**: Confirmed as "(preview)" by Learn page titles
  (`Work IQ MCP overview (preview)`), but the exact enterprise policy/permission model (how
  admin-set scopes map to individual MCP tool invocations) was not fully fetched in this pass
  (only summarized via search-tool synthesis, not a direct page fetch) — treat tool-count and
  category details as **secondary-sourced** (search synthesis), not independently confirmed
  against the primary Learn page text in this research pass.
- **Microsoft OpenTelemetry Distro ↔ SkillC span compatibility**: Not evaluated. This
  research did not fetch the full `microsoft-opentelemetry` page content past 6000 characters
  nor the GitHub reference repos; attribute-level compatibility with SkillC's existing
  `telemetry_span` is unknown and would require a dedicated follow-up read of both.
  Secondary: https://github.com/microsoft/opentelemetry-distro-dotnet (named in the Learn
  page, not independently fetched).
  Secondary: https://github.com/microsoft/work-iq (named by search synthesis, not
  independently fetched).
- **No search was run for**: Microsoft Foundry Agent Service's own Agent 365 data-collection
  configuration pages (`/en-us/azure/foundry/agents/how-to/configure-agent-365-data-collection`
  and `grant-agent-365-permissions`) beyond the one-line description surfaced via the
  `choose-integration-option` page; these were not fetched directly and their content is
  unverified beyond that single reference.
- **Licensing/pricing details** (exact SKUs, cost) were not independently verified beyond the
  Learn page's own cross-references to `https://www.microsoft.com/microsoft-agent-365#plans-and-pricing`
  and `https://www.microsoft.com/licensing/terms/productoffering/Agent365/EAEAS#clause-2755-h3-1`
  — neither URL was fetched directly in this research pass.
- **No claim is made that Agent 365, Entra Agent ID, or any linked product currently
  integrates with SkillC.** All integration language in §3–4 is explicitly a proposal.

---

## 6. Source list (all fetched or search-surfaced in this research pass, 2026-10-13)

Primary (Microsoft Learn, fetched directly):
- https://learn.microsoft.com/en-us/microsoft-agent-365/overview
- https://learn.microsoft.com/en-us/microsoft-agent-365/developer/agent-365-sdk
- https://learn.microsoft.com/en-us/microsoft-agent-365/developer/get-started
- https://learn.microsoft.com/en-us/microsoft-agent-365/developer/choose-integration-option
- https://learn.microsoft.com/en-us/microsoft-agent-365/developer/microsoft-opentelemetry
- https://learn.microsoft.com/en-us/entra/agent-id/what-is-microsoft-entra-agent-id
- https://learn.microsoft.com/en-us/entra/agent-id/agent-identities

Primary (named by the above pages but not independently fetched in this pass — secondary
confidence only):
- https://learn.microsoft.com/en-us/microsoft-365/agents-sdk/
- https://learn.microsoft.com/en-us/azure/foundry/agents/overview
- https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/configure-agent-365-data-collection
- https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/grant-agent-365-permissions
- https://learn.microsoft.com/en-us/azure/foundry/quickstarts/get-started-code
- https://learn.microsoft.com/en-us/entra/id-governance/agent-id-governance-overview
- https://learn.microsoft.com/en-us/entra/identity/conditional-access/agent-id
- https://learn.microsoft.com/en-us/entra/id-protection/concept-risky-agents
- https://learn.microsoft.com/en-us/entra/global-secure-access/concept-secure-web-ai-gateway-agents
- https://learn.microsoft.com/en-us/microsoft-agent-365/tooling-servers-overview ("Work IQ MCP overview (preview)")
- https://www.microsoft.com/security/blog/2026/05/01/microsoft-agent-365-now-generally-available-expands-capabilities-and-integrations/
- https://github.com/microsoft/opentelemetry-distro-dotnet
- https://github.com/microsoft/work-iq

Secondary (search-tool synthesis, not independently fetched — lowest confidence, used only
for orientation, not for load-bearing claims above):
- Bing/web-search synthesis results covering "Microsoft Agent Framework vs Microsoft 365
  Agents SDK vs Copilot Studio vs Azure AI Foundry" and "Work IQ MCP servers preview
  documentation" queries, run 2026-10-13.

Local (parent-session direct code citations, relayed without independent re-inspection by
this research agent, per the delegated research scope):
- README.md:3-19, CONTEXT.md:33-57, src/skillc/checker.py:724-772,
  src/skillc/frontend/grants.py:20-39, src/skillc/env/model.py:1-40,85-105,
  src/skillc/env/mcp.py:1-19,130-148, src/skillc/integrations/agent_framework.py:66-126,
  148-197,252-282,311-327, src/skillc/monitor.py:552-635,665+, src/skillc/monitor_mcp.py:
  1-29,90-116,200+.

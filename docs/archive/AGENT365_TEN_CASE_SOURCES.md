# Source Research and Final Selection for Ten Agent 365 Cases

Research date / retrieval date for all sources below: **2026-10-13**.

## Final selection correction

The final runnable corpus is
[`examples/agent365-cases`](../../examples/agent365-cases/README.md).
It contains ten **published, source-backed workflows**, not ten independently
verified production deployments. KPMG is an adoption announcement; partner
documentation and official worked scenarios form the remaining cases. Adobe,
Celonis and Egnyte are explicitly marked **coming soon** by the source.

Two original candidates below were excluded: Integra's quote does not specify a
concrete workflow, and the cited Cowork page does not directly establish its Agent
365 relationship. They were replaced after a successful direct fetch of
[Microsoft's partner documentation](https://learn.microsoft.com/en-us/microsoft-agent-365/third-party-agents):

- [Genspark](https://learn.microsoft.com/en-us/microsoft-agent-365/third-party-agents#genspark):
  research/task execution in Teams, Word collaboration, and human approval or
  rejection before actions. AI teammate availability requires Frontier access.
- [Adobe](https://learn.microsoft.com/en-us/microsoft-agent-365/third-party-agents#adobe):
  a marketing director queries page views, orders and audience trends, then
  analyzes campaign fallout and conflicts for a leadership review. Integration
  is marked coming soon.

Both replacement sections were fetched and read directly on 2026-10-13. The final
catalog models source-described operations only: it does not invent Integra purchase
orders, Rox discount changes, Gloat job applications or Kasisto bank transactions.
The original research candidates and proposed extensions below are retained as
research history, **not** as the final case selection or evidence of deployment.

## Purpose and method

The original research below identified ten public customer/product candidates
suitable as inputs to SkillC's local case folders (untrusted-intent → formal
capability/protocol pack → Z3 admissibility check). Every case below was located via web
search and then **independently fetched and read** at the cited URL on 2026-10-13 — no case
is sourced from a search-engine snippet alone. Each entry records:

- HTTP/fetch result and page title as observed.
- Source category (first-party Microsoft customer-story press release, first-party Microsoft
  Learn partner-integration doc, first-party Microsoft Learn product doc).
- Source-backed facts, paraphrased, plus one optional exact quotation ≤25 words.
- **Direct vs. proposed Agent 365 relationship** — stated explicitly for every case; nothing
  is silently assumed to be "Agent 365" when the source does not say so.
- Workflow operations, actors, and capabilities as described in the source (not invented).
- A realistic missing-capability / approval / evidence gate we can model locally, clearly
  marked **LOCAL TEST ASSUMPTION** wherever SkillC would need a rule the source does not
  itself specify.
- A suggested case-folder slug and a bounded modeled goal/protocol scope for the parent
  repository's case-folder generator/runner (not implemented here).

**Limitations (apply to all ten cases):** these are public marketing/documentation/press
sources, not production telemetry or tenant access. No case below reflects this researcher
observing a live Agent 365 tenant, admin center, or audit log. Figures, feature availability
("coming soon", "Frontier preview", GA) are as stated on the page at retrieval time and may
change. Where a partner integration page says a capability is "coming soon," that is recorded
as a limitation, not elided.

**Diversity coverage:** professional-services governance, supply chain/regulatory
(procurement-adjacent), customer service, sales, HR, finance/banking, legal/content
governance, IT-ops/insurance-claims process intelligence, IT-ops/security, and
scheduling/approval-gated task automation.

---

## 1. KPMG — global Agent 365 + Copilot deployment (professional services governance)

- **URL**: https://news.microsoft.com/source/2026/06/09/kpmg-and-microsoft-scale-trusted-enterprise-ai-agents-globally-through-deployment-of-agent-365-and-copilot/
- **Fetch status**: HTTP 200, successfully retrieved and read in full (one page, no pagination
  truncation needed for the cited section). Page title: "KPMG and Microsoft scale trusted,
  enterprise AI agents globally through deployment of Agent 365 and Copilot" (news.microsoft.com,
  dated June 9, 2026).
- **Source category**: First-party Microsoft customer-story press release (news.microsoft.com).
- **Facts**: KPMG (276,000+ professionals, 138 countries) announced it will adopt Microsoft
  Agent 365 to manage how AI agents are deployed, managed, monitored, and updated across its
  global organization, embedding it into KPMG's own "Trusted AI" framework and "Workbench"
  multi-agent platform; KPMG member firms separately expand Microsoft 365 Copilot access
  to the full global workforce. Quoted customer: Lisa Heneghan, Global Chief Digital Officer,
  KPMG.
- **Exact quotation (21 words)**: "KPMG will adopt Microsoft Agent 365 to manage how AI
  agents are deployed, managed, monitored and updated across its global organization."
- **Agent 365 relationship**: **Direct.** The press release explicitly names Microsoft Agent
  365 as the adopted product and describes governance/monitoring/lifecycle-management use.
- **Workflow operations / actors / capabilities**: Actor = KPMG IT/governance team (admin
  role) plus individual KPMG professionals across audit, tax, advisory lines of business.
  Operations described: register and inventory agents org-wide; monitor agent activity;
  enforce governance/compliance/security controls at scale; help KPMG's own clients replicate
  the same agent governance model. No specific per-ticket workflow steps, tool call sequences,
  or approval gates are enumerated in the source (this is an executive-level partnership
  announcement, not a technical workflow spec).
- **Missing-capability / approval / evidence gate to model locally**: The source states "with
  governance, security and controls in place" but does not enumerate a specific policy
  engine, approval chain, or evidence artifact. **LOCAL TEST ASSUMPTION**: model a two-tier
  approval — (a) an agent-registration admissibility check (must present a registered Entra
  Agent ID + declared scope before being allowed to touch audit/tax/advisory client data),
  and (b) a human-sponsor sign-off gate before any agent is granted cross-engagement data
  access. Neither sub-rule is stated verbatim in the source; both are reasonable local stand-
  ins consistent with the source's "governance, risk and compliance frameworks, including
  clear ownership" language, not verbatim facts.
- **Case folder slug**: `kpmg-agent365-governance`
- **Bounded modeled goal/protocol**: Admit/deny an agent-task request of the form "AI agent X
  (registered, scope = audit-workpaper-summarization) requests read access to client
  workpaper repository Y" against a capability pack requiring (i) active registry entry,
  (ii) scope match, (iii) sponsor-approval evidence token. Z3 goal: prove admissibility only
  when all three literals hold; otherwise produce the specific missing literal.

---

## 2. Integra LifeSciences — excluded candidate (insufficient concrete workflow detail)

- **URL**: same page as Case 1 — https://news.microsoft.com/source/2026/06/09/kpmg-and-microsoft-scale-trusted-enterprise-ai-agents-globally-through-deployment-of-agent-365-and-copilot/
- **Fetch status**: HTTP 200, same successful fetch as above (quotation appears further down
  the same press release, in a pull-quote block from Integra LifeSciences' CIO).
- **Source category**: First-party Microsoft customer-story press release (quoted customer,
  embedded in a different company's Agent 365 announcement).
- **Facts**: Dimitri Kvares, Corporate VP & CIO of Integra LifeSciences (a medical device /
  neurosurgery and tissue-reconstruction company), is quoted describing a phased roadmap
  embedding "Microsoft Copilot" into Global Supply Chain, Regulatory Affairs, and Medical
  Affairs functions, with an "enterprise AI operating model and a dedicated team" to keep
  deployments "responsible, secure, and compliant," and ROI/adoption tracking.
- **Exact quotation (21 words)**: "we are embedding AI capabilities, such as Microsoft
  Copilot, into core functions, including Global Supply Chain, Regulatory Affairs, and
  Medical Affairs."
- **Agent 365 relationship**: **Proposed / gap, not direct.** The quote names **Microsoft
  Copilot**, not Microsoft Agent 365, and appears as a supporting customer quote inside a
  KPMG/Agent 365 press release, not as a statement that Integra LifeSciences itself has
  deployed Agent 365. Treat this as a real, named, documented enterprise Copilot deployment
  in supply-chain/regulatory/medical-affairs functions, with an **inferred, not evidenced**,
  potential Agent 365 governance layer (plausible because it is adjacent to the KPMG/A365
  announcement, but not stated).
- **Workflow operations / actors / capabilities**: Actors = supply chain, regulatory affairs,
  and medical affairs staff at a regulated medical-device manufacturer. Operations described
  only at the level of "embedding AI capabilities... into core functions" and "scaling
  high-impact use cases" — no concrete task list (e.g., no named PO approval or regulatory
  submission step) is given in the source.
- **Missing-capability / approval / evidence gate to model locally**: **LOCAL TEST
  ASSUMPTION** (entirely invented for modeling, since the source gives no workflow detail):
  a procurement-adjacent case where a supply-chain copilot drafts a purchase requisition and
  must hold evidence of (a) budget-owner approval and (b) regulatory-affairs sign-off before
  it is permitted to submit the requisition to an ERP system — modeling the general
  "responsible, secure, and compliant" deployment principle the CIO quote states, without
  claiming the specific gate is documented.
- **Case folder slug**: `integra-lifesciences-supplychain-copilot` (label clearly as
  **Copilot deployment with proposed/未evidenced Agent 365 layer**, not an Agent 365 case, in
  any derived case-folder README).
- **Bounded modeled goal/protocol**: Admit/deny "draft requisition R for supplier S, amount A"
  only when both an approval-evidence token (budget owner) and a compliance-evidence token
  (regulatory affairs) are present in the fact base; otherwise report the missing evidence
  token(s).

---

## 3. Zendesk AI teammate — Agent 365 integration for customer support (service)

- **URL**: https://learn.microsoft.com/en-us/microsoft-agent-365/third-party-agents
- **Fetch status**: HTTP 200, fetched and read across three paginated reads (start_index 0,
  10000, 20000) to reach the Zendesk entry near the end of the document. Page title:
  "Ecosystem partner agents available in Agent 365 | Microsoft Learn" (ms.date 2026-10-01,
  Learn page `agent365-docs/third-party-agents.md`).
- **Source category**: First-party Microsoft Learn partner-integration documentation.
- **Facts**: Zendesk is listed as an "AI teammate" (Frontier-program-only category) under
  "Customer support," marked Registered ✓, Observable ✓, Work IQ not yet (−). The page states
  service engineers can identify and manage all tickets related to a customer directly from
  Microsoft Teams, and communicate with customers and internal teams without switching apps,
  with Agent 365 observability ensuring activity stays within enterprise trust boundaries.
- **Exact quotation (21 words)**: "The Agent 365 integration enables service engineers to
  identify and manage all tickets related to a customer directly from Microsoft Teams."
- **Agent 365 relationship**: **Direct.** This is a named, launch-time Agent 365 ecosystem
  partner integration on Microsoft's own partner list, not an inferred association.
- **Workflow operations / actors / capabilities**: Actor = customer-service engineer, acting
  inside Microsoft Teams. Operations: view/manage all Zendesk tickets for a given customer in
  context; message customers and internal teams; all actions logged to the Microsoft 365
  admin center observability dashboard. "AI teammate" status (per the page's footnote) means
  it is available only to Frontier-preview-program participants, a stated gating condition.
- **Missing-capability / approval / evidence gate to model locally**: The source states
  observability occurs but does not define a specific approval chain for, e.g., ticket
  escalation or refund authorization. **LOCAL TEST ASSUMPTION**: an escalation action (e.g.,
  "issue customer credit > $X") requires an evidence token from a supervisor role before the
  agent may execute it; a plain "view/reply" action requires only the Frontier-program
  entitlement flag and an active Agent 365 registration — both modeled as required facts.
- **Case folder slug**: `zendesk-support-ticket-triage`
- **Bounded modeled goal/protocol**: Admit "reply to ticket T for customer C" when
  (registered ∧ frontier-entitled); admit "issue credit of amount A on ticket T" only when
  additionally (supervisor-approval-evidence present ∧ A ≤ policy-limit) — else surface the
  unmet literal.

---

## 4. Rox — Agent 365 integration for sales revenue intelligence (sales)

- **URL**: https://learn.microsoft.com/en-us/microsoft-agent-365/third-party-agents
  (same page/fetch as Case 3; Rox entry appears in the start_index 20000 pagination read)
- **Fetch status**: HTTP 200, same successful multi-page fetch. Page title as in Case 3.
- **Source category**: First-party Microsoft Learn partner-integration documentation.
- **Facts**: Rox is listed under "Sales & revenue intelligence," Registered ✓, Observable ✓.
  Description: Rox helps sales teams track deal health, forecast accurately, and act on
  pipeline insights; the Agent 365 integration brings Rox's revenue data into Microsoft
  Teams so sales teams can monitor deals and act on revenue insights without leaving
  Microsoft 365. All Rox agent activity is tracked through the admin center observability
  dashboard.
- **Exact quotation (24 words)**: "The Agent 365 integration brings Rox's revenue data into
  Microsoft Teams, enabling sales teams to monitor deals and take action on revenue
  insights."
- **Agent 365 relationship**: **Direct.** Named launch-time ecosystem partner on Microsoft's
  own list.
- **Workflow operations / actors / capabilities**: Actor = sales rep / sales manager, in
  Teams. Operations: read deal-health/pipeline/forecast data; act on recommendations (source
  does not specify which concrete write-actions, e.g., updating a CRM field, are permitted
  vs. merely advisory).
- **Missing-capability / approval / evidence gate to model locally**: **LOCAL TEST
  ASSUMPTION**: distinguish a read-only "view forecast" capability (no approval needed beyond
  registration) from a write-action "apply a discount recommendation to an active deal,"
  which we assume requires a sales-manager approval evidence token before the agent may
  write back to the CRM — the source does not specify any write-back gating, so this is
  entirely a local test construct, not a documented Rox/Agent 365 rule.
- **Case folder slug**: `rox-sales-pipeline-insight`
- **Bounded modeled goal/protocol**: Admit "surface pipeline insight for deal D" under
  registration alone; admit "apply discount recommendation to deal D" only with manager
  approval evidence; else report missing approval.

---

## 5. Gloat — Agent 365 integration for internal talent mobility (HR)

- **URL**: https://learn.microsoft.com/en-us/microsoft-agent-365/third-party-agents
  (Gloat entry, start_index 15000 pagination read)
- **Fetch status**: HTTP 200, same page/fetch session as Cases 3–4.
- **Source category**: First-party Microsoft Learn partner-integration documentation.
- **Facts**: Gloat, listed under "HR & talent management," Registered ✓, Observable ✓, is
  described as a talent marketplace platform connecting employees with internal
  opportunities, projects, and career paths; the Agent 365 integration surfaces talent and
  opportunity recommendations directly in Teams, making internal mobility part of everyday
  work, with all Gloat agent activity tracked via the admin center observability dashboard.
- **Exact quotation (20 words)**: "The Gloat Agent 365 integration surfaces talent and
  opportunity recommendations directly in Teams, making internal mobility part of everyday
  work."
- **Agent 365 relationship**: **Direct.** Named launch-time ecosystem partner.
- **Workflow operations / actors / capabilities**: Actor = employee (opportunity seeker) and,
  implicitly, hiring manager (opportunity poster), inside Teams. Operations: receive
  personalized career/project recommendations; explore internal opportunities. The source
  does not describe an apply/select/hire action chain, only recommendation surfacing.
- **Missing-capability / approval / evidence gate to model locally**: **LOCAL TEST
  ASSUMPTION**: model a two-stage flow — (1) recommend opportunity to employee (no approval
  needed, data-visibility scope = employee's own profile), (2) employee applies to internal
  role, which requires evidence that the employee's current manager has been notified (a
  plausible real HR-governance pattern, not stated by Gloat/Microsoft in the source).
- **Case folder slug**: `gloat-internal-mobility-recommendation`
- **Bounded modeled goal/protocol**: Admit "surface recommendation R to employee E" under
  registration + own-profile-scope; admit "submit internal application for E to role R" only
  with manager-notification evidence present; else report the gap.

---

## 6. Kasisto (KAI platform) — Agent 365 agent factory for regulated banking/financial-services workflows (finance)

- **URL**: https://learn.microsoft.com/en-us/microsoft-agent-365/third-party-agents
  (Kasisto entry, start_index 15000 pagination read)
- **Fetch status**: HTTP 200, same page/fetch session.
- **Source category**: First-party Microsoft Learn partner-integration documentation
  (secondary link to Kasisto's own docs noted but not independently fetched in this pass).
- **Facts**: Kasisto's KAI platform is described as "an agent factory purpose-built for
  building line-of-business AI agents for banking and financial services, handling regulated
  workflows for banks and credit unions." Agents built on KAI are currently deployed as "AI
  teammates" in Agent 365; each gets an automatic Microsoft Entra Agent ID; KAI agents
  participate in Teams 1:1 and group conversations "with Agent 365 governance and
  observability providing the compliance controls financial institutions require."
- **Exact quotation (22 words)**: "KAI agents participate in Teams 1:1 and group
  conversations, with Agent 365 governance and observability providing the compliance
  controls financial institutions require."
- **Agent 365 relationship**: **Direct.** Named launch-time "agent factory" category partner,
  explicitly described as producing governed Agent 365 agents by construction (automatic
  Entra Agent ID on creation).
- **Workflow operations / actors / capabilities**: Actor = bank/credit-union employee
  (relationship manager, support rep) using Teams; agent factory = Kasisto KAI; the
  regulated-workflow content itself (e.g., loan servicing, account inquiries) is referenced
  only generically as "regulated workflows for banks and credit unions" — no specific named
  financial transaction type is enumerated in the source.
- **Missing-capability / approval / evidence gate to model locally**: **LOCAL TEST
  ASSUMPTION**: because the source emphasizes "compliance controls financial institutions
  require" without naming them, model a representative regulated-finance gate: any agent
  action that discloses a customer's account balance or performs a funds-related action
  requires (a) verified customer-identity evidence and (b) an active Entra Agent ID
  registration; absent either, deny.
- **Case folder slug**: `kasisto-banking-regulated-agent`
- **Bounded modeled goal/protocol**: Admit "disclose account summary for customer C to agent
  A" only when (A.registered ∧ identity-verification-evidence(C) present); else report the
  missing literal (commonly identity-verification).

---

## 7. Egnyte — Agent 365 integration for content governance (legal / compliance)

- **URL**: https://learn.microsoft.com/en-us/microsoft-agent-365/third-party-agents
  (Egnyte entry, start_index 10000 pagination read)
- **Fetch status**: HTTP 200, same page/fetch session.
- **Source category**: First-party Microsoft Learn partner-integration documentation.
- **Facts**: Egnyte is described as "a secure content cloud and data governance platform for
  enterprises." The Agent 365 integration brings AI-driven insights from Egnyte into
  Microsoft Teams: "the agent scans files in the customer's Egnyte storage to summarize
  content, generate new content, and support collaboration in 1:1 and group conversations,"
  while "Egnyte logs observability data to Agent 365, giving admins full governance
  visibility over AI activity across enterprise content." The page explicitly states: "Egnyte
  integration with Agent 365 is coming soon" (not yet GA at the time of the page).
- **Exact quotation (23 words)**: "The agent scans files in the customer's Egnyte storage to
  summarize content, generate new content, and support collaboration in 1:1 and group
  conversations."
- **Agent 365 relationship**: **Direct** (documented, launch-partner integration), but with an
  explicit **"coming soon"** availability caveat recorded in the source — this is a real,
  named, planned integration, not yet confirmed generally available at retrieval time.
- **Workflow operations / actors / capabilities**: Actor = any employee in a Teams
  conversation referencing enterprise content stored in Egnyte; capability = scan/summarize/
  generate content from files the requesting user is entitled to see; admin oversight via
  the Agent 365 observability dashboard.
- **Missing-capability / approval / evidence gate to model locally**: The source implies
  "governance visibility" but not a pre-execution gate. **LOCAL TEST ASSUMPTION**: a
  content-governance check requiring the requesting user to hold at least "viewer" permission
  on the underlying Egnyte folder (an access-control fact, modeled locally, not asserted by
  the source) before the agent may summarize or generate content from it — a reasonable
  stand-in for "data governance platform" behavior, explicitly not verbatim from Egnyte docs.
- **Case folder slug**: `egnyte-content-governance-summarize`
- **Bounded modeled goal/protocol**: Admit "summarize file F for user U in Teams" only when
  (U has viewer-or-higher permission on F ∧ Agent 365 observability logging active); else
  deny and name the missing permission/logging literal.

---

## 8. Celonis — Agent 365 process intelligence in an insurance claims operation (IT ops / claims)

- **URL**: https://learn.microsoft.com/en-us/microsoft-agent-365/third-party-agents
  (Celonis entry, start_index 10000 pagination read)
- **Fetch status**: HTTP 200, same page/fetch session.
- **Source category**: First-party Microsoft Learn partner-integration documentation
  (includes a worked **example scenario**, not just a capability summary).
- **Facts**: Celonis is described as "a process intelligence platform that gives Agent 365 a
  real-time view of how AI agents perform across your business operations," creating a
  "digital twin" of operations from Agent 365 activity data. The page gives a concrete,
  named example: "Consider a process owner managing AI agents across claim triage, fraud
  detection, and customer service. Agent 365 governs who the agents are, what they're
  authorized to do, and enforces security and compliance policies." Two worked examples are
  given: "A Triage Agent shows a security block where a malicious file uploaded by a customer
  was stopped by Agent 365 via Microsoft Defender," and "A Fraud Agent is blocked from
  connecting to an unencrypted database because of compliance rules configured in Agent
  365." The page states "Celonis integration with Agent 365 is coming soon" (planned, not yet
  GA at retrieval time) and links to a Celonis blog post
  (https://www.celonis.com/blog/scaling-the-agentic-enterprise-with-microsoft-agent-365-and-celonis)
  that was **not independently fetched** in this pass (noted as a gap below).
- **Exact quotation (20 words)**: "A Fraud Agent is blocked from connecting to an unencrypted
  database because of compliance rules configured in Agent 365."
- **Agent 365 relationship**: **Direct**, and unusually concrete — this is the single
  richest *worked example* of an actual admit/deny security-policy decision found across all
  ten sources (a malicious-file block and an unencrypted-database connection block), making
  it an excellent template for a SkillC protocol-pack test case. Still labeled "coming soon"
  for the Celonis-specific telemetry linkage, so the Celonis half of the integration is
  **planned**, while the underlying Agent 365 Defender/compliance blocking behavior it
  describes is presented as already operative.
- **Workflow operations / actors / capabilities**: Actors = process owner (admin), Triage
  Agent, Fraud Agent, Customer Service Agent, all operating under Agent 365 identity/
  governance. Capabilities: claim triage, fraud detection, customer-service handling;
  Agent 365 enforces (a) a file/malware security policy via Microsoft Defender and (b) a
  data-connection compliance policy (no unencrypted-database connections).
- **Missing-capability / approval / evidence gate to model locally**: This case is unusual
  in that the **deny conditions are directly source-backed**, not purely a local assumption:
  (1) deny file-touching action if the file fails a Defender malware scan; (2) deny a
  database-connection action if the target endpoint is not encrypted. A **LOCAL TEST
  ASSUMPTION** is still needed to formalize "fails a Defender scan" and "endpoint not
  encrypted" as boolean literals the Z3 pack can consume, since the source describes the
  policy outcome, not the literal schema.
- **Case folder slug**: `celonis-insurance-claims-agent-policy`
- **Bounded modeled goal/protocol**: Admit "Triage Agent processes uploaded file F for claim
  C" only when (F passed-defender-scan); admit "Fraud Agent connects to database D" only
  when (D.encrypted = true); otherwise emit the specific violated literal, mirroring the two
  worked examples in the source almost directly.

---

## 9. Sophos — Agent 365 integration for security alert triage (IT ops / security)

- **URL**: https://learn.microsoft.com/en-us/microsoft-agent-365/third-party-agents
  (Sophos entry, start_index 20000 pagination read)
- **Fetch status**: HTTP 200, same page/fetch session.
- **Source category**: First-party Microsoft Learn partner-integration documentation.
- **Facts**: Sophos is described as "a cybersecurity platform that protects organizations
  from threats across endpoints, networks, and cloud environments." The Sophos Agent 365
  integration "brings security alerts and response actions into Microsoft 365, letting
  security teams act on threats directly from Teams without switching to a separate
  console." Listed capabilities: receive Sophos alerts/threat notifications in Teams; triage
  and respond to incidents directly from Microsoft 365; all Sophos agent activity tracked via
  the admin center observability dashboard.
- **Exact quotation (22 words)**: "The Sophos Agent 365 integration brings security alerts
  and response actions into Microsoft 365, letting security teams act on threats directly
  from Teams."
- **Agent 365 relationship**: **Direct.** Named launch-time ecosystem partner, "Registered ✓,
  Observable ✓" per the integration table.
- **Workflow operations / actors / capabilities**: Actor = security analyst/incident
  responder, in Teams. Operations: receive alert; triage; respond (source does not specify
  the exact set of allowed "response actions," e.g., isolate endpoint vs. close ticket, nor
  any authorization tiering among them).
- **Missing-capability / approval / evidence gate to model locally**: **LOCAL TEST
  ASSUMPTION**: distinguish a low-risk response action ("acknowledge alert," no approval
  needed beyond registration) from a high-risk response action ("isolate endpoint from
  network"), which we assume requires a second analyst's or security-lead's approval
  evidence before execution — a common SOC "four-eyes" control pattern, not stated in the
  Sophos/Agent 365 doc itself.
- **Case folder slug**: `sophos-security-incident-response`
- **Bounded modeled goal/protocol**: Admit "acknowledge alert A" under registration alone;
  admit "isolate endpoint E for alert A" only with second-approver evidence present; else
  report the missing approval.

---

## 10. Microsoft Copilot Cowork — excluded candidate (replaced with directly linked Adobe case)

- **URL**: https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/
- **Fetch status**: HTTP 200, fetched and read (first ~5000 characters; page continues beyond
  what was read, but the cited approval-gating language and capability list were captured in
  full). Page title: "Copilot Cowork overview | Microsoft Learn" (ms.date 2026-09-29).
- **Source category**: First-party Microsoft Learn **product** documentation for a
  first-party Microsoft 365 Copilot feature — **not** a third-party Agent 365 ecosystem
  partner and **not** a named customer case study. Labeled per instructions as **"official
  sample/product doc, not a customer deployment."**
- **Facts**: "Microsoft Copilot Cowork can carry out tasks on your behalf. You describe what
  you need, and Cowork sends emails, schedules meetings, creates documents, posts in Teams,
  and manages your calendar. You approve each action before it happens." Listed capabilities
  include sending emails, scheduling meetings, creating Word/Excel/PowerPoint/PDF documents,
  posting in Teams, searching organizational resources, managing OneDrive/SharePoint files,
  conducting research, preparing briefings/summaries, drafting communications, and running
  scheduled/recurring prompts. Cowork for work/school accounts is stated as **generally
  available**; Cowork for personal accounts is **in preview**.
- **Exact quotation (7 words)**: "You approve each action before it happens."
- **Agent 365 relationship**: **Not directly evidenced on this page.** This page does not
  mention Microsoft Agent 365 by name. It is included here as a **real, first-party,
  currently documented Microsoft 365 Copilot feature** with an explicit, source-stated,
  per-action human-approval gate — directly useful as a SkillC approval-protocol template —
  and is cross-referenced elsewhere in Microsoft's own integration docs (per the companion
  research doc `docs/archive/MICROSOFT_AGENT_365_INTEGRATION_RESEARCH.md`, §1.2) as a
  Microsoft-native surface that Agent 365 can observe/govern once an agent uses it. That
  governance linkage is a **proposed application**, not asserted on the Cowork page itself.
- **Workflow operations / actors / capabilities**: Actor = any Microsoft 365 work/school (or
  preview personal) user; capability set as listed above (email, meeting scheduling, document
  creation, Teams posting, file management, research, scheduled prompts). The source's own
  approval model is explicit and generic: *every* action is held for user approval before
  execution — this is the one case in this dossier where the approval gate itself, not just
  the workflow, is directly source-backed.
- **Missing-capability / approval / evidence gate to model locally**: Directly source-backed
  core rule: no externally visible action (send email, post to Teams, schedule a meeting)
  executes without prior user approval. **LOCAL TEST ASSUMPTION** layered on top: treat
  "recurring scheduled prompts" as a standing pre-approval (approved once at schedule-creation
  time) versus one-off actions needing fresh per-instance approval — this distinction is
  plausible from the feature list but not explicitly stated as a rule on the page.
- **Case folder slug**: `copilot-cowork-approval-gated-automation`
- **Bounded modeled goal/protocol**: Admit "Cowork sends email draft D to recipient R" or
  "Cowork posts message M to Teams channel C" only when a fresh per-action approval-evidence
  token is present; admit a recurring scheduled prompt's instance execution when a
  schedule-level approval token exists (per the LOCAL TEST ASSUMPTION above); otherwise deny
  and name the missing approval token.

---

## Original candidate mapping (superseded by the final selection above)

| # | Case | Entity (real) | Category | Source URL | A365 relationship |
|---|------|----------------|----------|------------|--------------------|
| 1 | `kpmg-agent365-governance` | KPMG | Professional services / cross-functional governance | news.microsoft.com KPMG press release | Direct |
| 2 | `integra-lifesciences-supplychain-copilot` | Integra LifeSciences | Supply chain / regulatory / procurement-adjacent | same press release (quoted customer) | Proposed only (Copilot named, not A365) |
| 3 | `zendesk-support-ticket-triage` | Zendesk (Agent 365 partner) | Customer service | learn.microsoft.com/.../third-party-agents | Direct |
| 4 | `rox-sales-pipeline-insight` | Rox (Agent 365 partner) | Sales | same Learn page | Direct |
| 5 | `gloat-internal-mobility-recommendation` | Gloat (Agent 365 partner) | HR | same Learn page | Direct |
| 6 | `kasisto-banking-regulated-agent` | Kasisto / KAI (Agent 365 partner) | Finance / banking | same Learn page | Direct |
| 7 | `egnyte-content-governance-summarize` | Egnyte (Agent 365 partner) | Legal / content compliance | same Learn page | Direct (integration "coming soon") |
| 8 | `celonis-insurance-claims-agent-policy` | Celonis (Agent 365 partner) | IT ops / insurance claims | same Learn page | Direct (integration "coming soon"; worked policy example) |
| 9 | `sophos-security-incident-response` | Sophos (Agent 365 partner) | IT ops / security | same Learn page | Direct |
| 10 | `copilot-cowork-approval-gated-automation` | Microsoft Copilot Cowork | Scheduling / cross-functional task automation | learn.microsoft.com/.../copilot/cowork/ | Not direct (official Microsoft product sample, A365 link proposed) |

The original candidate sources were fetched on 2026-10-13. They support a mixture
of announcements, partner capabilities and worked examples, not ten confirmed
customer deployments. Candidates 2 and 10 did not meet the final corpus's
concrete-workflow/direct-Agent-365 selection criterion and were replaced as noted above.

## Gaps and follow-up

- No additional named-customer Agent 365 deployments beyond KPMG were found via web search in
  this pass (`site:news.microsoft.com` / `site:customers.microsoft.com` query returned no
  results); Microsoft's customer-story catalogue (https://www.microsoft.com/en/customers/)
  was not separately crawled in this pass and may contain further named A365 deployments —
  suggested follow-up search: `site:microsoft.com/en/customers "Agent 365"`.
- The Celonis and Egnyte integrations are both explicitly marked "coming soon" on the Learn
  page at retrieval time (2026-10-13); their *workflow descriptions* are real and documented,
  but GA status should be re-checked before being cited as a currently-operating deployment.
- The Celonis blog post linked from the Learn page
  (https://www.celonis.com/blog/scaling-the-agentic-enterprise-with-microsoft-agent-365-and-celonis)
  was referenced but **not independently fetched**; treat any additional detail from it as
  unverified until fetched directly.
- No production telemetry, tenant admin-center screenshots, or live Agent 365 registry data
  were accessed; all facts are drawn from public marketing/documentation pages as of the
  stated retrieval date.

# Hosts end to end: compacted packs instead of authored ones

Experiment H of `runs/20261015_review_response/PLAN.md`. Before this run, every host result
(Agent 365, the Agent Framework finance agent, Scout) was computed on packs we wrote by hand.
Here gpt-5.4 (Azure AI Foundry `foundary-tzuc06`, deployment `gpt-5.4`) writes the packs from
the natural-language inputs. The method is P2g: `ce_runtime_messages` bound to a runtime
manifest, one located-error retry (`CE_RETRY_PROMPT`), and for Agent Framework and Scout one
counterexample-guided repair (`CE_REPAIR_PROMPT`) guarded by `repair_violations`. The
compacted packs then go through the same offline checks as the authored ones. All prompts
and replies are under `runs/20261015_hosts/<part>/`, with sha256s in `frozen.json`. We read
two raw replies per part before the full run, and no prompt changed after that.

## Summary

| host | input | runtime | result |
|---|---|---|---|
| Agent 365 | 10 `intent.md`, 3 samples per arm | one manifest per case, from its grants | named states: 189/195 (separation of duty 0/6); blind: 0/195, all unaligned |
| Agent Framework | 6 role skills + coordinator instructions, 3 samples | `foundry-hosted` | 0/3 samples match the authored gate labels; **6 false IMPOSSIBLE** on correct configurations |
| Scout | 70 SKILL.md of set2, 1 sample | `scout-desktop` | 67/70 valid; 48 ACHIEVABLE, 19 IMPOSSIBLE, 0 UNKNOWN; no truth labels |

## Agent 365

**Input and runtime.** For each of the ten cases, the input is `intent.md`. The manifest
`agent365-<case>` has the case's grants as its only tools (grants `enterprise_runtime`, lacks
"any operation not listed", software `none`). P2g runs with one retry and no repair. Two arms:

- **named** (`a365/`): each tool description is the `case.json` action text plus "Establishes
  `<state>`", and the runtime description lists the environment's state names.
- **blind** (`a365_blind/`, Addendum A): only the action text; no state is named anywhere.

**Checks.** A Tool bound `via G` (G a grant) is renamed G; others keep their names (no
`vocabulary_merge` occurred). Each static check in `checks.json` runs through
`run_cases.static_check`, and verdict and reason are compared with `expected`. Addendum A adds
one check kind, `role_separation`, which passes iff the two actions exist and have different
owners. Genspark checks `approve_document_action` against `create_word_document`. Celonis
checks `connect_fraud_database` against `triage_claim_file`: that pair is the handoff, because
the claim moves from Triage to Fraud's first action. The authored packs pass all 65 static
checks. The 60 runtime checks do not read the pack and are out of scope.

| check | named arm | blind arm |
|---|---|---|
| six standard checks (each) | 30/30 | 0/30 |
| three case-specific verdict checks (each) | 3/3 | 0/3 |
| `approval_separation_of_duty` (Genspark) | **0/3** | 0/3 |
| `triage_fraud_handoff_separation` (Celonis) | **0/3** | 0/3 |
| **all static checks** | **189/195** | **0/195** |
| valid first / final | 30/30 / 30/30 | 29/30 / 30/30 |
| packs with `unaligned` goal/initial names; with preconditions outside the vocabulary | 0; 0 | 30; 30 |
| packs with the authored step set | 30 | 30 |
| disagreements by cause | compaction_error 6 (roles collapsed) | vocabulary 189, compaction_error 6 |

**What 189/189 measured.** The figure before Addendum A measured three things. Did the model
pick the right step for each grant? Did it use the state names the manifest handed it? Does
the environment's contract substitution then decide everything else? It did not measure
fidelity. Every compacted pack, in both arms, has one role (`agent`, sometimes also `user`),
so the agent approves its own Word document and does its own fraud handoff. The two
separation checks make that visible: 0/6 in each arm, against 2/2 for the authored packs.

**Blind arm.** With no state names, the model chose its own, for example `topic_researched`
and `activity_monitored`. Only 20 of 107 goal atoms are in the environment vocabulary, and
only 4 of 30 packs contain the authored goal atom. `bind_environment` then reports the pack
unaligned, and `static_check` refuses to decide rather than refute. So the blind arm yields
no verdict at all, not a wrong one (no false IMPOSSIBLE). The steps were right in all 30
(28 renamed via `via`): `via` aligns tool names, not state names, so the named arm's agreement
rests on the manifest publishing the state vocabulary.

## Microsoft Agent Framework (finance hosted agent)

**Input.** The coordinator constant `COORDINATOR_INSTRUCTIONS` from
`examples/hosted-agent-finance/src/finance-agent/main.py` (the default, full text), then the
six files `skills/<Role>.md` in full, each under a heading `# Role: <Role>` (order: Fetcher,
ExpenseAnalyst, RevenueAnalyst, TaxSpecialist, TaxVerifier, Writer). The frozen text is
`runs/20261015_hosts/maf/inputs/finance.md`. The runtime is `foundry-hosted`. The prompt adds
one user-level note: several roles exchange messages; declare one Role per agent, the
messages as `tells`, and the approval ordering, with the deliverable as the Goal.

**Gate.** For each sample, the project is copied to `maf/project_s<k>/` without logs,
`.azure`, or the vendored `skillc` copy. The compacted CE replaces
`protocol/quarterly_finance_report.ce` and `protocol-variants/` is deleted. Then
`gate(project, declared)` runs for the three configurations. The reference is the unchanged
authored pack, gated the same way in `maf/project_authored/`.

| sample | rounds | azure.yaml | azure.search.yaml | azure.isolated.yaml |
|---|---|---|---|---|
| authored reference | | ACHIEVABLE | ACHIEVABLE | ACHIEVABLE |
| s0 | 1 | **IMPOSSIBLE** MISSING_CAPABILITY | **IMPOSSIBLE** | **IMPOSSIBLE** |
| s1 | 1, repair (invalid, kept refuted pack) | **IMPOSSIBLE** pure GOAL_UNSAT | **IMPOSSIBLE** | **IMPOSSIBLE** |
| s2 | 1, retry (still invalid) | gate error: no parsable pack | gate error | gate error |

**False IMPOSSIBLE on correct configurations: 6 of 9** (s0 and s1 on all three
configurations). The third sample produced no parsable pack. No sample meets the
`tests/test_gate.py` expectations (pack ACHIEVABLE via `code_interpreter, write` on
`azure.yaml`; gate ACHIEVABLE on search and isolated).

Causes:

- **s0, vocabulary (runtime binding).** The skills name Agent Framework function tools
  (`analyze_expenses`, `classify_revenue`, ...). The manifest has no entry for "the agent's
  own registered functions", so the model bound them `via mcp`, and `lookup_tax_rules` `via
  search`, because the TaxSpecialist skill says "in the tax-rules search index". Under the
  full `foundry-hosted` manifest the pack is ACHIEVABLE, so P2g saw no refutation and did not
  repair. The gate's effective runtime withdraws `mcp` (and `search`, except in the search
  configuration), so every configuration refutes the pack. The authored pack binds these
  tools `via code_interpreter` by authorial choice.
- **s1, compaction error (goal).** The Goal contains `high_branch or standard_branch`, but no
  Tool adds those atoms: the branch is a choice label, not an effect. The pure check refutes
  the pack before any binding. The repair reply did not parse ('adds' twice on one Tool), so
  P2g kept the refuted pack.
- **s2, schema.** The first reply joins `requires` conditions with commas, and the retry
  joins `adds` predicates with `and`. Both break the CE grammar.

**Structure versus the authored pack** (valid packs only):

| | authored | s0 | s1 |
|---|---|---|---|
| roles | 6 | 7 (adds `coordinator`, snake_case names) | 7 |
| tools | 10 | 10, same names | 11 (adds `report_result`) |
| messages (`tells`) | 17 | 15 | 15 |
| approval gates `write_revenue_analysis` | yes (`approved`) | yes (`approval_exists`, added only by TaxVerifier tools) | yes |
| owner of approving tools | TaxVerifier | tax_verifier | tax_verifier |

**Email variant.** Reference: the authored
`protocol-variants/quarterly_finance_report.email.ce` flipped into `protocol/`, as
`test_gate.py` does. The gate's verdict is IMPOSSIBLE, naming `email_account` and
`email_report`. Compacted: the same input with "Final step: email the report to the CFO."
appended to the Writer skill (`maf/inputs/finance_email.md`), 3 samples, gated under
`azure.yaml`.

| sample | rounds | gate | email step in the final pack | names the missing connection |
|---|---|---|---|---|
| s0 | 1, retry (invalid) | gate error | dropped in the retry | no |
| s1 | 1, retry, repair (invalid) | IMPOSSIBLE, pure GOAL_UNSAT on `high_path`/`standard_path` | yes: `email_report_to_cfo` via `openapi`, needs `cfo_email_service` | no (refuted for the goal error first) |
| s2 | 1, retry, repair (invalid) | IMPOSSIBLE, pure GOAL_UNSAT | dropped | no |

Two of three email packs get the reference label IMPOSSIBLE, but for the wrong reason. None
is refuted for the missing email connection.

### Under P2g+ and the effective runtime

Criterion B4 of the plan (Addendum B, fixes F-a to F-f). The packs are compacted by
`skillc.gate.compact_project`, which is the code path of `skillc gate --compact`, called
through the API on project copies so that `examples/` is not written to. The prompt is
P2g+ (`ce_runtime_messages(..., version="p2g+")`) over `project_text` (the
`COORDINATOR_INSTRUCTIONS` constant and the six skills, each under `# Role: <name>`) plus
`MULTI_ROLE_NOTE`. The runtime in the prompt is the **effective** runtime: `foundry-hosted`
reduced by the declared azure.yaml. The loop has two located-error retries and one guarded
repair. Then `gate(project, cfg, packs=[compacted])` gates each pack, and the same report
gives the authored `protocol/*.ce` label as the reference. The model is gpt-5.4 with 3
samples per job. The driver is `runs/20261015_hosts/maf_v2/run_b4.py`. Prompts, replies,
per-call usage and sha256s are in `maf_v2/` and `maf_group_v2/` (`frozen.json`,
`results.json`, `summary.json`). One smoke sample was read before the run
(`maf_v2/project_finance_azure_smoke/`, not scored). No prompt changed.

`compact_project` needs the declared file to build the effective runtime, so each
configuration has its own compaction (3 samples each). The prompts for `azure.yaml` and
`azure.isolated.yaml` are byte-identical: isolation only turns `web_fetch` into an assumption
and leaves the tool list the same. `azure.search.yaml` adds `search`. Sample *k* of one
configuration is independent of sample *k* of another.

| sample | azure.yaml | azure.search.yaml | azure.isolated.yaml |
|---|---|---|---|
| authored reference | ACHIEVABLE | ACHIEVABLE | ACHIEVABLE |
| s0 | ACHIEVABLE (2 retries) | ACHIEVABLE (1 retry) | REJECTED NON_PROJECTABLE |
| s1 | ACHIEVABLE (repair kept) | ACHIEVABLE | ACHIEVABLE |
| s2 | ACHIEVABLE | ACHIEVABLE | UNKNOWN (`web_fetch` under isolation) |

No pack withdrew or blocked a tool on its own configuration.

| | first run (P2g, full manifest) | P2g+, effective runtime |
|---|---|---|
| false IMPOSSIBLE on the three correct configurations | **6 of 9** | **0 of 9** |
| gate errors (no parsable pack) | 3 of 9 | 0 of 9 |
| label equal to the authored pack's | 0 of 9 | 7 of 9 |
| sample indices with zero false IMPOSSIBLE | 1 of 3 (s2, which had no pack) | 3 of 3 |

As a supplement, the three `azure.yaml` packs were also gated under the other two files.
Of the 9 results, 8 are ACHIEVABLE and 1 is UNKNOWN (s1 under isolation, `lookup_tax_rules`
via `web_fetch`). None is IMPOSSIBLE.

Per-sample causes of the remaining disagreements and of the extra rounds:

- **isolated s0, REJECTED (not a refutation).** The model wrote a hub-and-spoke protocol: the
  coordinator relays every message. `revenue_analyst` makes the branch choice, but the
  coordinator then sends the branch messages without first receiving one from
  `revenue_analyst`. Projection fails (NON_PROJECTABLE). The goal is reachable along the
  witness, and the gate says that this is not a goal-impossibility claim.
- **isolated s2, UNKNOWN.** `lookup_tax_rules` is bound `via web_fetch`, which under
  `AllowOnlyApprovedOutbound` is kept only as an assumption. This verdict is correct for the
  pack as written. The authored pack binds the tool `via code_interpreter`.
- **Binding of `lookup_tax_rules`.** Under `azure.search.yaml` all three samples bind it
  `via search`. Under `azure.yaml` and `azure.isolated.yaml` it is bound `via web_search` (4)
  or `via web_fetch` (2), never `via mcp`, because `mcp` and `search` are no longer in the
  prompt. This is F-d's effect on defect D5. The role functions are bound `via reply`,
  `read` and `write`, not `code_interpreter` as in the authored pack.
- **azure s1, repair.** The first reply had `fetch_financials` require `quarter_selected`,
  which no Tool adds (D1 again: a fact the user decides, written as a `requires`). The
  checker refuted it (BLOCKED_GUARD), and the guarded repair was kept.
- **Retries (D6).** azure s0 needed two retries (an `and` inside a parenthesis, then a stray
  word as a step). search s0 and isolated s2 each needed one (a comma between Tool clauses).

**Structure versus the authored pack.** The authored pack has 6 roles, 10 tools and 17
messages, `approved` gates `write_revenue_analysis`, and only `TaxVerifier` owns approving
tools.

| | roles | tools | messages | approval gates the revenue analysis | approving tools owned by | another role owns an approving tool (rule 14) |
|---|---|---|---|---|---|---|
| authored | 6 | 10 | 17 | yes (`approved`) | TaxVerifier | no |
| azure s0/s1/s2 | 7/7/7 | 12/11/11 | 19/14/15 | yes in all three | tax_verifier | no |
| search s0/s1/s2 | 7/7/7 | 11/11/11 | 15/17/15 | yes | tax_verifier | no |
| isolated s0/s1/s2 | 7/7/7 | 11/11/11 | 14/14/15 | yes | tax_verifier | no |

Every sample adds a `coordinator` role, whose tool reports the result to the user, and
uses snake_case role names. The approval atom is renamed in every sample (`approval_ready`,
`approval_exists`, `approval_obtained`), but each is added only by the two `tax_verifier`
tools and required by `write_revenue_analysis`. The Goal is the coordinator's report to the
user (for example `user_reported`), not `report_delivered and approved`. In azure s0 the Goal
is a disjunction that also covers the rejected path. Rule 14 is computed strictly: a tool
counts as approving if it is named `approv*` or adds an `approv*` atom that the revenue
analysis requires. `hosts_e2e.structure`'s looser `approving_tool_owners`, also stored in
`summary.json`, counts the coordinator's `user_reported_branch_approval_and_path` as
approving, which is a false positive of the name match.

**Email variant.** The same text with "Final step: email the report to the CFO." appended to
the Writer skill (`hosts_e2e.EMAIL_STEP`) in a project copy, gated under `azure.yaml`. The
reference is the authored `quarterly_finance_report.email.ce` flipped into `protocol/`. Its
label is IMPOSSIBLE MISSING_CAPABILITY: `email_report` needs `email_account`, and `mcp` is
not declared.

| sample | rounds | gate | email step in the pack | names the missing connection |
|---|---|---|---|---|
| s0 | 1 | REJECTED NON_PROJECTABLE (coordinator relays, as in isolated s0) | dropped | no |
| s1 | 1 | **ACHIEVABLE** | dropped | no |
| s2 | 1 retry | REJECTED NON_CONFORMANT (the Writer behaviour does not refine its projection) | dropped | no |

All three samples drop the email sentence. The Writer ends with `deliver_report` via
`write`, and the Goal is the coordinator's report to the user. No email Tool and no
`needs` remain, so nothing can be refuted, and s1 is a false ACHIEVABLE. In the first run
one sample in three kept the step (`email_report_to_cfo` via `openapi`). A likely cause, not
tested here: the P2g+ rule "the Goal names only the deliverable", together with the
coordinator's "Finish by reporting ... to the user", makes the coordinator's report the
deliverable, and the Writer's last sentence then reads as optional.

**Second multi-role case: `examples/hosted-agent-finance-group`.** These are six hosted
agents talking over A2A, and the case was not used to develop the fixes. The project has no
`COORDINATOR_INSTRUCTIONS`, so the input is the six skills only, and the effective runtime
keeps `a2a`. Results under `azure.yaml`:

| sample | rounds | pack | gate | authored |
|---|---|---|---|---|
| s0 | 1 | REJECTED NON_PROJECTABLE (`tax_verifier` acts in `revenue_analyst`'s branch without a distinguishing message) | REJECTED | ACHIEVABLE |
| s1 | 2 retries | REJECTED NON_PROJECTABLE (`fetcher` acts in `writer`'s rejected/generated choice) | REJECTED | ACHIEVABLE |
| s2 | 2 retries | REJECTED NON_PROJECTABLE (`fetcher` acts in `tax_verifier`'s choice) | REJECTED | ACHIEVABLE |

False IMPOSSIBLE: **0 of 3**. All three are protocol-typing rejections, not refutations:
the goal is reachable in each. s1 and s2 model every rejection as an external choice whose
branch the `fetcher` must act in without being told. Structure: s0 has 6 roles, 11 tools and
14 messages. s1 has 6 roles, 12 tools and 19 messages. s2 has 7 roles (adds `user`), 11 tools
and 21 messages. The authored pack has 6, 10 and 17. In all three the approval atom gates
`write_revenue_analysis`, and only `tax_verifier` owns approving tools (no rule-14
violation). The roles bind the A2A edges `via a2a`.

The group's topology check gives UNKNOWN on most edges: "role `expense_analyst` maps to no
declared agent". `_Topology.agent_for` compares the role name with the agent name and the
skill file stem in lower case, but does not remove `_` or `-`. So `revenue_analyst` does not
match `RevenueAnalyst.md`, while the one-word roles `fetcher` and `writer` do match (for
example `finance-writer -> finance-fetcher over connection writer-to-fetcher`). This is a
gate limitation, reported here and not fixed: with snake_case role names, which P2g+ writes
every time, a multi-agent topology cannot be confirmed.

**B4.** It has two parts:

- (a) Zero false IMPOSSIBLE on the three correct configurations in at least two of three
  samples: **met** (0 of 9, against 6 of 9 before).
- (b) The email variant refuted, naming the missing connection: **not met** (0 of 3; every
  sample drops the email step).

**B4 is not met.**

**What this shows.** On this case, F-d and F-f remove the false refutations. With the
effective runtime the model no longer binds the role functions to `mcp`. Branch assumptions
(F-a) and `reply` (F-b) remove the goal errors of the first run (`high_branch or
standard_branch` with no establisher). Separation of duty survives compaction in 12 of 12
finance packs and 3 of 3 group packs: the approval is a separate atom, owned only by the
verifier. **What it does not show.** The gate becomes more permissive, but not more
discriminating on this case. The one variant that should be refuted is not refuted,
because the requirement disappears during compaction, not because the check fails. The typing
rejections (isolated s0, email s0 and s2, group s0 to s2) do not occur with the authored packs. They are not false IMPOSSIBLE, but they do
fail a deploy gate (exit 4). The samples are few (3 per job, one model), the email and group
results come from one input each, and the role-name mismatch hides the group's topology
check.

**Cost.** 27 model calls in all. The scored jobs used 25: finance and email 18 (43,301
uncached input tokens, 43,648 cached, 20,220 output), group 7 (17,171 / 22,784 / 8,200). The
unscored smoke sample used 2 (5,605 / 4,224 / 1,988).

## Microsoft Scout

**Input.** The 70 `kind: skill` entries of `benchmark/claude_env/set2/cases.json`, each file
`set2/cases/<case>.md` in full. The runtime is `scout-desktop`, and the method is P2g with 1
sample, one retry and one guarded repair. There is no truth for this runtime, so no accuracy
is claimed.

| measure | count |
|---|---|
| valid first reply / valid final | 47/70 / 67/70 (3 still fail the grammar or have a Tool without `via`) |
| repaired (accepted by the guard) / repair invalid / repair rejected by the guard | 26 / 3 / 0 |
| ACHIEVABLE | 48 (23 with the protocol well typed, 25 with it rejected as NON_CONFORMANT) |
| IMPOSSIBLE | 19 (12 GOAL_UNSAT, 7 BLOCKED_GUARD) |
| UNKNOWN | 0 |
| IMPOSSIBLE witnessed by a missing runtime resource | 3 (c003 `figma_access`, c047 `llm_api_access`/`tinker_account`, c066 `azure_account`) |
| Tools withdrawn (via a tool Scout lacks) | 0 |

Sixteen of the 19 refutations have no missing-resource witness: a Goal atom or guard nothing
establishes (UNKNOWN under the P2g-grounded rule). 25 of the 48 ACHIEVABLE are not admissible.

**Fidelity judge.** 20 items (sha256("scout-judge:"+case) order) in `scout/judge/items/`,
with rubric F1 to F5, no verdicts, and `judge/README.md`. Not yet scored.

## Cost

| part | calls recorded | input (uncached) | input (cached) | output |
|---|---|---|---|---|
| a365 (named) | 30 | 15,794 | 43,264 | 6,726 |
| a365 (blind) | 31 | 18,298 | 40,320 | 7,382 |
| maf | 13 | 36,293 | 29,312 | 18,503 |
| scout | 122 | 327,439 | 238,336 | 73,786 |
| total | 196 | 397,824 | 351,232 | 106,397 |

Up to three Scout calls, in flight when a Windows file lock stopped the run, were redone.

## What this shows and what it does not

- **Shows:** on Agent 365, compaction finds the right steps (30/30 in both arms). The verdict
  checks agree only when the manifest publishes the state names; without them nothing is
  decided. Roles collapse in every pack (separation of duty 0/12).
- **Shows:** on the multi-role finance agent, the authored-pack result does not carry over.
  The packs compacted from the same skills are refuted on every correct configuration, or do
  not parse. The "we wrote the pack" threat (HOSTED_AGENT_EVALUATION.md section 7) is real
  for this host: the gate's ACHIEVABLE depends on our binding choice (`code_interpreter` for
  the role functions) and on a goal written without branch atoms.
- **Does not show:** live Agent 365 behaviour.
- **Does not show:** live deployment (the gate runs offline; the live arms of
  `HOSTED_AGENT_EVALUATION.md` remain future work), or accuracy on Scout (no truth labels
  for `scout-desktop`; judge items prepared, not scored).
- Samples are few (3, one model family); nothing was tuned on these inputs.

## Reproduction

```bash
# run needs AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/openai/v1 and an az login
for s in prepare run score; do for p in a365 maf scout; do python scripts/hosts_e2e.py $p $s; done; done
for s in prepare run score; do python scripts/hosts_e2e.py a365 $s --blind-vocab; done   # Addendum A
```

`score` checks every prompt and reply against `frozen.json` and writes `summary.json`,
`results.json` and, per part, `disagreements.json`, the gated project copies, or `judge/`.

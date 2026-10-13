# SkillC finance security: static validation and runtime verification

This is an offline, synthetic application of SkillC to:
SharePoint documents -> analysis -> independent approval -> Outlook/Teams delivery.
It does not connect to Microsoft 365, implement Entra authentication, or claim a
production Agent 365 integration.

## Threat model and findings

An attacker can influence document text, agent instructions, proposed tool arguments,
or peer-agent reply text. The trusted host, authenticated reviewer, policy configuration,
transport implementation and approval database are outside the attacker's control.
If the agent can modify those, these controls are not an isolation mechanism.

| Scenario | Previous behavior | Added protection |
|---|---|---|
| No capability can send the report | Static validation already refutes the declared protocol | No checker change; the offline demo exercises independent grant binding |
| A document instructs the agent to bypass review or add an external recipient | A tool name or `approved` predicate does not constrain delivery arguments | Exact operation/destination allowlists, plus approval bound to the complete delivery |
| A peer writes `[Approval]` or fabricated analysis labels | The group receive bridge promoted labels to facts | Labels alone never establish facts; the host must verify producer, success, payload and workflow |
| Approve document A, then fetch document B | Global Boolean approval survived | Strict mode invalidates dependent approvals and derived artifacts when recomputing upstream predicates |
| Reuse approval for another version, report, amount, channel or destination | No artifact-specific authorization | `ApprovalGate` checks the complete delivery fingerprint |
| Writer fabricates or replays an approval reference | Textual approval checks and Boolean facts were insufficient | Opaque authority-issued references; independent reviewer; expiry, revocation and durable single use |
| An optional forbidden branch is pruned during static validation but called anyway | Execution used the original unbound capability | Every capability invocation rechecks current runtime bindings and restrictions |
| Invoke a raw tool alias to bypass a named capability's prerequisites | Default runtime-name matching could allow it | Opt-in strict middleware requires named capabilities and known role ownership |
| Supply NaN/Infinity or an ambiguous fractional amount to avoid an audit | Float comparisons could issue standard approval | Finite nonnegative monetary validation; cents-based approval threshold |
| Unknown numeric prerequisite or monitor failure | Default monitor can allow these | Strict mode denies unknown prerequisites and requires fail-closed error handling |

`IMPOSSIBLE` remains a static refutation relative to the declared model. Runtime
authorization returns a refusal or raises `AuthorizationError`; it does **not** label
a denied delivery an impossible business goal. `ACHIEVABLE` is still structural
admissibility, not a security certificate or proof of business success.

## New reusable module: `skillc.security`

`ApprovalGate` exposes `approve`, `deliver`, and `revoke`. It uses standard-library
SQLite with parameterized queries; there is no model in the authorization path.

A `Delivery` binds:

- tenant and workflow IDs from the host;
- source item ID, authoritative version and SHA-256 source digest;
- authenticated report author;
- the exact report contents, operation and complete destination set;
- the source amount in integer minor units (cents in this example).

The host calls `approve` only after an authenticated independent reviewer approves
that exact delivery. `audited=True` is trusted audit evidence supplied by that
handler, **not** an agent argument, a report phrase, or evidence that SkillC performs
an audit. Reviewers must be in the host allowlist and cannot be the report author.
The delivery principal must be an allowed sender and different from the approver.

Before delivery, the gate rechecks policy, fingerprint, reviewer authorization,
audit threshold and expiry. It commits consumption before calling the transport.
Concurrent or restarted callers cannot reuse the same reference. If delivery times
out, the exception propagates and the reference stays consumed: reconcile the
outcome and obtain new approval, rather than automatically retrying. This is
at-most-once invocation, not guaranteed or exactly-once delivery.

SQLite and issuer methods are trusted-host state. Do not expose them through agent
filesystem tools or mount their directory in an agent-writable sandbox. Approval
references are bearer authorizations for the bound operation; avoid logging them.
The database stores their hashes, not plaintext references. A protected database
backup/rollback, multi-host authority, review UI, and issuer authentication remain
deployment responsibilities.

### Attach at the actual delivery tool

The protected tool should construct the delivery from the *current* authoritative
document version and the exact bytes it will send. Model arguments must not determine
the tenant, actor, author, source version, source amount or policy.

```python
# Trusted host code, not an agent-exposed approval tool.
reference = gate.approve(reviewed_delivery, approver=authenticated_reviewer)

# Inside the actual delivery tool, immediately before the effect:
result = gate.deliver(
    reference,
    current_delivery,
    sender=authenticated_sender,
    send=send_exact_delivery,
)
```

`send_exact_delivery` consumes the immutable `Delivery` passed to it. It must not
append Cc/Bcc, attachments, alternate channels or unreviewed content. All recipients
must be represented by canonical tenant-scoped IDs from a trusted resolver; allowlist
membership is exact, not a permissive email-domain suffix check. An adapter must
resolve aliases and distribution-list membership according to its policy.

Reading a fresh source version and revoking references on source changes are host
obligations: passing an old `Delivery` object cannot let SkillC detect an unseen
SharePoint update. For mutable sources, use version-specific reads and conditional
operations/host coordination to address changes between validation and delivery.
The supplied Microsoft client still enforces effective permissions and resource
policy. A local allowlist is not a replacement for Entra, Purview/DLP or Conditional Access.

## Strict Agent Framework middleware

```python
monitor = skillc_monitor(
    runtime="foundry-hosted",
    root=trusted_state_root,
    session_id=trusted_isolated_session_id,
    plan_path=reviewed_plan_path,
    strict=True,
    fail_open=False,
)
agent = Agent(
    client=client,
    tools=protected_tools,
    middleware=monitor.middleware_for("Writer"),
)
```

Strict mode requires a host-supplied plan and disallows the agent's plan-writing tool.
It refuses raw aliases, absent role/owner information and unknown preconditions.
It cannot be combined with `fail_open=True` or disabled through the middleware's
`SKILLC_MONITOR=off` switch. Existing non-strict callers retain their fail-open default.
Dependent-fact invalidation is an additional strict runtime policy; non-strict mode
retains the declared pack's ordinary STRIPS frame semantics. Both finance examples
now select strict mode when the monitor is enabled.
The group example explicitly permits `SKILLC_MONITOR=off` *before construction*
for bare-agent comparisons; that is an unprotected deployment, not strict enforcement.

All sensitive tools must pass through the middleware and, for delivery, the approval
gate. Server-side tool execution and unwrapped tools are not intercepted. Host code
must isolate monitors by tenant, authenticated principal and workflow; a process-global
default session is not suitable for concurrent tenant requests. Numeric conditions
are conservatively denied in strict monitor formulas, not generally evaluated there.
The new approval gate evaluates its own typed integer monetary threshold separately.

## Group receive bridge: intentional compatibility change

The old group demo converted text labels into trusted protocol state. That is unsafe,
even when the caller can authenticate to the endpoint: it does not prove who originally
produced a relayed result or whether an approval operation succeeded.

`receive_bridge` now accepts a **host-injected** `verify_received` function and trusted
tenant/workflow IDs. The verifier returns `MessageEvidence` only after checking
authenticated original issuer, execution success, freshness, workflow membership and
the SHA-256 digest of the complete received payload. The bridge independently matches
issuer, receiver, label and route against the protocol mapping.

`MessageEvidence` is a typed attestation interface, **not** a signature verifier.
Never deserialize untrusted JSON straight into it or accept model-provided
`verified=true`. The verifier must also bind downstream tool arguments to the
verified artifact, not merely attest that a fact was once true.

No authenticated transport verifier is wired into the existing group's `build()`.
Therefore the monitored distributed example now **blocks remote-dependent actions**
instead of trusting text. This is an intentional fail-closed mitigation, not a claim
that the cloud workflow has been completed. The verifier seam supports a trusted host
integration; production receipt issuance, key management and replay checks still need
implementation for the chosen transport. Verifier/storage failures propagate rather
than allowing execution.

## Reproduce without accounts, models or network

From the repository root, with SkillC installed:

```powershell
python examples\agent365-finance\security_demo.py --state-dir runs\agent365-security-offline
python -m pytest tests\test_security.py tests\test_finance_security.py tests\test_monitor.py tests\test_monitor_mcp.py tests\test_agent_framework_adapter.py -q
```

The demo uses a synthetic SharePoint item and synthetic mailbox/channel IDs. Its
transport only appends to an in-memory list. It asserts exactly one legitimate
transport invocation; the forged, altered and replayed deliveries never invoke it.
It keeps the authority database in the supplied local state directory. The tests
also exercise concurrency, persistence, monetary boundaries, real finance example
functions, strict middleware failures and the group's evidence-receiving interface.
Finance/Agent Framework tests require the existing `.[agent-framework]` extra.

Limits: this does not detect all prompt injection, assess whether financial analysis
is truthful, prove the reviewer is human, infer effective tenant permissions, or
prevent exfiltration through any unwrapped tool. It provides deterministic runtime
controls at declared, host-enforced seams alongside the unchanged static checker.

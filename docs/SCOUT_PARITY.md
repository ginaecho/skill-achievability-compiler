# SkillC in Microsoft Scout: parity with the Agent 365 adapter

Date: **2026-10-13**. The Scout integration (`skillc monitor mcp`, served as MCP tools)
now offers the runtime capabilities added for Agent 365 workflows
([A365 security](AGENT365_SECURITY.md)). Both share the same monitor core and the
same `skillc.security.ApprovalGate`; only the adapter differs.

## Summary

**The same checks are available in Scout, but they are not enforced as strongly as in
A365.**

**Same as A365**

- Strict mode can load a plan supplied by the user or host that the agent cannot replace.
- In strict mode, raw host-tool names, unknown prerequisites and stale downstream facts
  are denied.
- Runtime restrictions are checked again before each action.
- Protected actions can require the user's approval of the exact content, destinations,
  source and amount. Approvals are single-use, expire, and cannot be forged or reused.

**Weaker in Scout**

1. **Checks are voluntary.** Scout gives SkillC no hook before tools run, so the agent
   can skip or ignore SkillC.
2. **SkillC does not send the message.** It approves the exact message, but cannot prove
   Scout's later send used the same content.
3. **The approval prompt is unconfirmed in Scout.** It worked with a test MCP client; if
   Scout cannot show it, protected actions are denied.
4. **The agent shares the user's account and PowerShell.** It could edit SkillC's files
   or settings; the installed skill forbids this but cannot prevent it.
5. **There is no fail-closed mode.** If the SkillC server stops, Scout continues.

### Why Scout is weaker than A365

The decision logic is identical; the difference is **where SkillC sits relative to the
action**.

- In **A365**, SkillC runs as Agent Framework middleware inside the host's own tool-call
  path. Every tool call passes through it, a denial means `call_next()` is never called,
  and the tool cannot run. The host, not the model, owns the plan, the approval store
  and the reviewer identity, and strict mode refuses to run if SkillC fails.
- In **Scout**, SkillC is an MCP server beside the agent, not in front of its tools.
  Scout exposes no pre-tool hook to plugins, so SkillC only sees what the agent chooses
  to report and cannot stop a tool call it was not asked about. The agent runs with the
  user's identity on the same machine as SkillC's state, so host-owned state is only
  protected by instruction, not isolation. Scout's actual send tools are separate from
  SkillC, so an approval constrains the check, not the transport.

In short: A365 is **enforcement** (the tool cannot run without passing SkillC); Scout is
**cooperative checking** (the same verdicts, which a compliant agent follows). Closing
the gap requires Scout to offer a host-enforced pre-tool hook, or to route protected
operations through a SkillC-owned tool that performs the send itself.

Installation backed up and updated only SkillC's MCP entry and the `skillc-check` skill.
Restart Scout to load the new tools. Scout stays in advisory mode by default: strict
mode needs a supplied plan, and approval checks need an approval policy listing
protected tools and allowed destinations.

Validation: 31 Scout parity and MCP tests passed with both the repository Python and
Scout's Python, and 168 related tests passed. The installed server command was started
and exposes all eight tools.

## Capability matrix

| Capability | A365 (Agent Framework middleware) | Scout (MCP tools) |
|---|---|---|
| Static validation of the plan (checker, runtime binding) | ✓ | ✓ (same core) |
| Runtime restrictions rechecked per action, incl. branches pruned at plan time | ✓ | ✓ |
| Strict mode: host-owned plan, no replacement from the conversation | ✓ `strict=True` | ✓ `--strict --host-plan` |
| Strict: named capabilities only, raw host-tool aliases denied | ✓ | ✓ |
| Strict: unknown (e.g. numeric) preconditions denied | ✓ | ✓ |
| Strict: re-reading a source invalidates downstream approvals/artifacts | ✓ | ✓ |
| Approval bound to exact content, destinations, source, amount | ✓ `ApprovalGate` | ✓ `--approval-policy` |
| Single use, expiry, revocation, cross-session isolation | ✓ | ✓ |
| Forged approval text is not approval | ✓ | ✓ |
| Finite two-decimal monetary validation; audit above threshold | ✓ | ✓ |
| Independent approver | Host-authenticated reviewer | The **user**, via MCP elicitation |
| Authenticated cross-agent message evidence | Seam (`MessageEvidence`) | Not applicable: `scout-desktop` lacks sub-agents |
| Fail-closed on monitor errors | ✓ strict requires `fail_open=False` | Not enforceable; see below |

Evidence: `tests/test_scout_parity.py` exercises each row through the MCP interface,
including a live stdio server with and without an elicitation-capable client (31 tests,
also passing under Scout's own interpreter, Python 3.13 with `mcp` 1.25).

## Enforcement differences (important)

1. **Scout calls skillc voluntarily.** Agent Framework middleware sits in the tool-call
   path: a denied tool is never invoked. Scout offers no pre-tool hook to plugins, so the
   agent must call `skillc_check_action` and then perform the checked action unchanged.
   An agent that skips or ignores skillc is not stopped; `calls.jsonl` records only
   what it chose to report. Identical decisions, weaker guarantee.
2. **The approval binds the check, not the transport.** The approved reference is
   consumed when `skillc_check_action` authorizes the exact content and destinations.
   skillc does not send the Teams message itself, so it cannot prove the subsequent
   `m_send_teams_message` call used that content.
3. **Approval comes from the user through the host.** skillc asks via MCP elicitation,
   which Scout must display to the user. A host without elicitation gets a refusal
   (`no user-approval channel`), never a model-issued approval. Whether the current
   Scout build renders elicitation is **not yet verified live**.
4. **Same identity, same machine.** The agent runs PowerShell as the user. It could, in
   principle, edit `~/.skillc-mcp`, the policy file or Scout's MCP configuration. The
   skill forbids this, but nothing prevents it; A365 keeps the gate in host-owned state.
5. **Roles and sources are self-reported.** In strict mode Scout's single plan role is
   used by default; source versions and texts are what the agent reports.
6. **No fail-closed mode.** If the skillc server is down, Scout continues without it.

To close gaps 1, 2 and 6, Scout would need a host-enforced pre-tool hook (as the
Copilot hooks adapter uses) or would route protected operations through a skillc-owned
tool that performs the send itself.

## Install and configure

```powershell
skillc monitor scout-install                                     # default: advisory
skillc monitor scout-install --strict --host-plan plan.ce        # host-owned plan
skillc monitor scout-install --approval-policy policy.json       # protected operations
```

The installer rewrites only the `skillc` entry of `~/.scout/m-mcp-servers.json` and the
`skillc-check` skill, keeping `.bak-skillc-<time>` copies. Restart Scout afterwards.
Instead of `--approval-policy`, a policy at `~/.skillc-mcp/.skillc/approval-policy.json`
is picked up automatically:

```json
{"protected_tools": ["teams_message"],
 "destinations": ["teams:<chat-or-channel-id>"],
 "ttl_seconds": 900, "audit_above": "50000.00"}
```

Defaults are unchanged: without a policy or `--strict`, the Scout monitor behaves as
before. On this machine the updated server and skill were installed on 2026-10-13 in
the default (advisory) configuration; strict mode and a policy are opt-in.

# Pre-session hook integration

`skillc hook pre-session` lets an agent host audit and check proposed skills
before it creates a model session. The host supplies the tools available to
that specific session, receives a structured admission result, and excludes or
blocks skills according to policy. No LLM runs in this hook.

## User flow

1. Run `apm install`, then `apm run setup` in the target workspace.
2. Select the existing agent files that should receive preflight. The installer
  does not download or replace agents.
3. Setup installs uv when needed, an isolated Python runtime, PyYAML, Z3, and
  `skillc`; it then writes the shared adapters and scoped hooks.
4. Setup runs `skillc doctor --workspace . --configured`, including a real
  preflight for each selected agent. Installation succeeds only if doctor
  passes.
5. Start an agent session normally. The selected agent's `SessionStart` hook
  runs `skillc hook agent-session` before the model begins work.
6. Grant a missing capability or edit a blocked agent, then reload the session.

The low-level `pre-session` protocol below remains available to hosts that need
to submit multiple optional skills and choose custom admission policies.

For a user, there is no required command in the normal flow. The commands below
define the interface an agent host invokes.

## Host invocation

For a selected custom agent, the generated cross-platform adapter invokes the
single-agent host interface directly:

```powershell
skillc hook agent-session --agent .github/agents/my-agent.md
```

It prints host hook JSON such as `{"continue":true}` and exits `2` with a
`stopReason` when the required agent is impossible. It has no separate
`python3`, `jq`, or PowerShell JSON-module dependency.

For a host-managed set of skills, write a request to a file:

```json
{
  "schema": "skillc.hook.pre-session/1",
  "runtime": {
    "profile": "current-session",
    "capabilities": ["read_file", "run_in_terminal"],
    "shell": true
  },
  "skills": [
    {
      "id": "release-service",
      "path": ".agents/skills/release-service/SKILL.md"
    }
  ],
  "policy": {
    "impossible": "exclude",
    "unknown": "warn",
    "auditError": "exclude"
  },
  "semantics": "may"
}
```

Invoke the hook:

```powershell
skillc hook pre-session --request pre-session.json
```

Hosts can use stdin/stdout instead:

```powershell
Get-Content pre-session.json -Raw | skillc hook pre-session --stdio
```

Standard output contains exactly one JSON response. Diagnostics and admission
actions are structured; a host must not parse human-readable checker messages.
The command exits `1` only when the response decision is `block-session`.
Filtering an optional skill is a successful hook execution and exits `0`.

## Response

An abridged response looks like this:

```json
{
  "schema": "skillc.hook.pre-session-result/1",
  "decision": "allow-with-filtering",
  "profile": "current-session",
  "admittedSkills": [],
  "excludedSkills": [
    {
      "skillId": "release-service",
      "status": "refuted",
      "verdict": "IMPOSSIBLE",
      "reason": "MISSING_CAPABILITY",
      "frontier": ["deploy_service"],
      "action": "exclude",
      "diagnostics": [
        {
          "code": "SKILLC001",
          "severity": "error",
          "message": "Capability 'deploy_service' is unavailable",
          "path": ".agents/skills/release-service/SKILL.md",
          "line": 12,
          "capability": "deploy_service"
        }
      ]
    }
  ],
  "warnings": []
}
```

`results` contains the complete result for every proposed skill. The admitted,
excluded, and warning collections are convenience views for host policy.

## Runtime capability context

When `runtime.capabilities` is present, it is authoritative for that session.
This supports workspaces that enable different MCP servers or tool grants. If
it is omitted, `runtime.profile` names a built-in or JSON profile accepted by
`skillc check --profile`.

Frontmatter and prose declarations remain distinct skill-side grants and are
combined by the existing markdown frontend. The host must not claim tools that
will be unavailable after session creation.

## Admission policies

| Field | Values | Default |
|---|---|---|
| `impossible` | `exclude`, `block-session`, `allow` | `exclude` |
| `unknown` | `warn`, `exclude`, `block-session`, `allow` | `warn` |
| `auditError` | `exclude`, `block-session`, `allow` | `exclude` |

Use `block-session` when a skill is mandatory for the selected agent. Prefer
`exclude` for optional skills so one broken skill does not prevent unrelated
work. `UNKNOWN` is an abstention and should not be presented as a refutation.

## Python embedding

Hosts embedding Python can avoid subprocess transport:

```python
from skillc.hooks import run_pre_session_hook

response = run_pre_session_hook(request)
```

For one skill, use `skillc.preflight_skill` directly. It composes bundle audit,
deterministic compilation, schema validation, and checking into one structured
result.

## Integration timing

Run full preflight when a skill is installed or changed, then cache the result.
At pre-session time, invalidate results when the skill, runtime capabilities,
semantics, or `skillc` version changes. The current protocol provides pack
digests for host caches; a shared persistent cache is not yet implemented by
the CLI.

MCP exposure can complement this hook for agents that author and repair skills,
but it should not be the only enforcement point: MCP tools are commonly loaded
as part of the session that this hook is intended to protect.
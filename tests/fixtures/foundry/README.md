# Foundry fixtures

Recorded exports of `skillc env probe --foundry` (`src/skillc/env/foundry.py`,
`tests/test_env_foundry.py`), replayed offline by the tests with
`foundry.replay(DIR)`. No test needs Azure.

## `firstProject-finance-report-agent/`

One live, read-only run on 2026-10-08 against the project
`https://foundary-tzuc06.services.ai.azure.com/api/projects/firstProject`
for the hosted agent `finance-report-agent` (version 8, the current one),
the deployment of `examples/hosted-agent-finance/azure.yaml`:

| file | what it is |
|---|---|
| `manifest.json` | the probe's arguments and capture time |
| `get_agents_*` | the agent and its version 8 (REST data plane, `api-version=v1`) |
| `get_toolboxes_*` | the toolbox listing and the `finance-tools` version 1 definition |
| `mcp_tools_list_*` | the toolbox's live `tools/list` over streamable HTTP MCP |
| `get_connections_*` | the project's connections |
| `az_role_assignment_list_*` | `az role assignment list` for the agent's instance identity (none) |

The files are **sanitised** before they are written (`foundry.sanitise`):
every key named like token, secret, key, authorization, password or
credential is dropped (a connection's `credentials` keeps only its `type`),
environment variable values are replaced by `<redacted>` (the names stay),
and e-mail addresses are replaced. What remains are identifiers (Azure
resource ids, the agent identity's object id, a content hash) and public
descriptions; no credential of any kind.

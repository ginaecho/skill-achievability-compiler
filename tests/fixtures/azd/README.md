# azd fixtures

Sample `azure.yaml` files for `skillc env from-azd` (`src/skillc/env/azd.py`,
`tests/test_env_azd.py`).

## From `microsoft-foundry/foundry-samples`

`01-basic/azure.yaml` and `04-foundry-toolbox/azure.yaml` are verbatim copies
of these files from https://github.com/microsoft-foundry/foundry-samples
(branch `main`, fetched 2026-10-07 from `raw.githubusercontent.com`):

* `samples/python/hosted-agents/agent-framework/responses/01-basic/azure.yaml`
* `samples/python/hosted-agents/agent-framework/responses/04-foundry-toolbox/azure.yaml`

That repository is Copyright (c) Microsoft Corporation and licensed under the
MIT License (https://github.com/microsoft-foundry/foundry-samples/blob/main/LICENSE).
The files are reproduced here unchanged, as test data, under that licence.

## Authored for these tests

`isolated-search/` is written for skillc and is not from the samples. It
exercises every branch of the adapter: a `$ref` include (`agents/researcher.yaml`),
a remote `$ref` and a cyclic `$ref` (both recorded as unknown), a connection
with `${SECRET}` credentials and a literal value that must never reach the
graph, a `network` block with `AllowOnlyApprovedOutbound`, a toolbox that
declares `azure_ai_search`, an `azure.ai.skill`, a prompt agent whose
`instructions` is a file, two `rai_policy` entries and an unsupported host.

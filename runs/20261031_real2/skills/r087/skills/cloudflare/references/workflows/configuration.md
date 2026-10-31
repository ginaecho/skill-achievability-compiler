# Workflow Configuration

Use the current guides for configuration fields and setup commands; check the project's installed Wrangler version and generated binding types before adapting an existing project.

| Task | Documentation |
| --- | --- |
| Scaffold and deploy a Workflow class with its binding | [Build your first Workflow]([url-1]) |
| Configure one or more Workflows, including a binding to a Workflow in another Worker | [Wrangler Workflows configuration]([url-2]) |
| Configure storage, AI, and other resources used by steps | [Workers bindings]([url-3]) |
| Choose step retry, backoff, timeout, and sleep behavior | [Sleeping and retrying]([url-4]) |
| Schedule instances or trigger them from another Worker | [Trigger Workflows]([url-5]) |
| Trigger a Workflow from Pages Functions | [Call Workflows from Pages]([url-6]) |
| Develop and inspect instances locally | [Local development]([url-7]) |
| Set resource budgets and inspect execution | [Limits]([url-8]) and [metrics and analytics]([url-9]) |

Distinguish the Worker that defines the Workflow from callers that trigger it. For Pages, follow the documented intermediary Worker/service-binding approach. A step's elapsed-time timeout and the Worker's active CPU budget address different failure modes; configure them based on the actual failure.

See [api.md](./api.md), [patterns.md](./patterns.md), and [gotchas.md](./gotchas.md).

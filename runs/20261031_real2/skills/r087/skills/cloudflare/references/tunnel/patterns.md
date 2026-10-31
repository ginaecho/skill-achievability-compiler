# Tunnel Deployment Decisions

Choose deployment ownership and availability requirements before adapting an example.

| Task | Documentation |
| --- | --- |
| Install a remotely-managed tunnel on a host or in Docker | [Setup]([url-1]) |
| Deploy cloudflared inside a cluster | [Kubernetes]([url-2]) |
| Manage tunnel infrastructure declaratively | [Terraform]([url-3]) |
| Deploy replicas and check current capacity | [Replicas and high availability]([url-4]) |
| Choose redundancy or explicit traffic steering | [Routing]([url-5]) |
| Plan upgrades for the existing installation method | [Update cloudflared]([url-6]) |
| Add authentication or private connectivity | [Integrations]([url-7]) |

Establish which service each replica can reach and how configuration and credentials reach each host. Decide whether simple redundancy meets the requirement or whether health-based routing needs a load balancer. Verify replacement replicas before retiring existing ones, and include application-level checks in the rollout. See [api.md](./api.md) for programmatic operations.

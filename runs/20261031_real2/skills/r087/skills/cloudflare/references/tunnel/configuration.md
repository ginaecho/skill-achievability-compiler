# Tunnel Configuration

Read the documentation for the existing management mode before changing routes or credentials.

| Task | Documentation |
| --- | --- |
| Configure remotely-managed tunnels | [Setup]([url-1]) |
| Edit local ingress rules, service mappings, and validate matching | [Configuration file]([url-2]) |
| Configure origin TLS, HTTP, and connection behavior | [Origin parameters]([url-3]) |
| Configure runtime flags and service arguments | [Run parameters]([url-4]) |
| Manage remote tunnel tokens and rotation | [Tunnel tokens]([url-5]) |
| Choose service protocols and DNS routing | [Routing]([url-6]) |

Confirm which configuration source the running process uses, then review the routes affected by the change. Match origin settings to the actual service and certificate rather than copying settings from a different deployment. See [networking.md](./networking.md) for connectivity and [patterns.md](./patterns.md) for rollout decisions.

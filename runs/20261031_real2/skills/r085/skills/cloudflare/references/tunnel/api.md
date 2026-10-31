# Tunnel APIs and Commands

Fetch current operation schemas, permissions, and examples before automating tunnel changes.

| Task | Documentation |
| --- | --- |
| Create a tunnel, configure ingress, and create application DNS through the API | [Setup]([url-1]) |
| List existing tunnels and inspect response fields | [List Cloudflare Tunnels API]([url-2]) |
| Retrieve and rotate tunnel tokens | [Tunnel tokens]([url-3]) |
| Manage local tunnels using the CLI | [Useful commands]([url-4]) |
| Configure public DNS and routing behavior | [Routing]([url-5]) |
| Select private-network integration and its setup guide | [Integrations]([url-6]) |

Identify the account, tunnel ID, and management mode before a write. Review existing routes before replacing configuration; distinguish tunnel lifecycle operations from DNS changes. Use [patterns.md](./patterns.md) when infrastructure as code owns these resources.

# Tunnel Troubleshooting

Capture the tunnel status, failing route, management mode, and cloudflared logs before changing settings.

| Task | Documentation |
| --- | --- |
| Tunnel fails to connect or reports an error | [Troubleshooting]([url-1]) |
| Tunnel is healthy but an HTTPS application fails or redirects | [HTTPS origins]([url-2]) |
| Inspect connection health and application diagnostics | [Monitoring]([url-3]) |
| Check local configuration and rule matching | [Configuration file]([url-4]) |
| Connections behave unexpectedly after token rotation | [Tunnel tokens]([url-5]) |
| Check replica capacity or firewall requirements | [Configuration]([url-6]) |
| Update an existing installation | [Update cloudflared]([url-7]) |

Separate tunnel health from origin availability. Check the service address, protocol, and certificate before relaxing verification. Scope operational changes to the intended tunnel and replicas; follow the documented rotation and upgrade sequence instead of stopping every cloudflared process on a host. See [networking.md](./networking.md) for connectivity checks.

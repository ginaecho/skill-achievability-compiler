# Tunnel Networking

Investigate the connection from cloudflared to Cloudflare separately from the connection to the origin and the client access path.

| Task | Documentation |
| --- | --- |
| Determine required egress ports and destinations | [Firewall rules]([url-1]) |
| Diagnose DNS, QUIC, or TCP connectivity | [Connection errors]([url-2]) |
| Configure transport and runtime options | [Run parameters]([url-3]) |
| Check service protocols and client requirements | [Routing]([url-4]) |
| Set up private-network access with Cloudflare One | [Connect private networks with cloudflared]([url-5]) |
| Inspect tunnel health, logs, and metrics | [Monitoring]([url-6]) |

Test from the machine or container running cloudflared. Compare the actual firewall policy with the current documented destinations; do not infer transport ports from the origin protocol. For private access, follow the linked Cloudflare One setup for routes and device-client configuration instead of reusing public-hostname instructions. See [gotchas.md](./gotchas.md) for origin failures.

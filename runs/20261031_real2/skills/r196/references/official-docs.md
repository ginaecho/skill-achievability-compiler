# Official Procore sources

Consulted: 2026-09-13

## Scope

These first-party sources ground **Procore Read-Only Connection Proof**. Re-check the selected endpoint reference before executing a smoke test.

## Sources

- [Making your first API call]([url-1])
- [Client Credentials grant and test call]([url-2])
- [Multiple Procore Regions headers]([url-3])
- [Pagination]([url-4])

## Provider boundaries

- A valid token does not prove correct company or project scope.
- `Procore-Company-Id` is part of the routing boundary where documented.
- Collection results must follow endpoint-specific pagination.
- This proof remains read-only and treats excess access as a failure.
- Source snapshot: `procore/documentation@fd31bc4b6c3d46b72b2b570c920ae5ccb2aa4318`.

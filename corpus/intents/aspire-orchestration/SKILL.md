---
name: aspire-apphost-status-capture
description: Start a local Aspire AppHost, capture resource status, and stop the AppHost cleanly.
allowed-tools: [aspire_start, aspire_wait, aspire_describe, aspire_stop]
---

# Aspire AppHost Status Capture

Use this procedure for a known valid local AppHost that should run long enough to reach readiness and report status.

Tools: `aspire_start`, `aspire_wait`, `aspire_describe`, `aspire_stop`.

## Workflow

1. Use `aspire_start` to start the AppHost in non-interactive mode.
2. Use `aspire_wait` for the target resource so readiness is established through Aspire.
3. Use `aspire_describe` to record the resource status.
4. Use `aspire_stop` before finishing so the local AppHost lifecycle is closed.

You are finished when the resource status is **recorded** and the AppHost is **stopped**.

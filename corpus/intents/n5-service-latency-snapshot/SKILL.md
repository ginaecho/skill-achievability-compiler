---
name: service-latency-snapshot
description: Service latency snapshot procedure.
allowed-tools: [query_service_metrics, compute_latency_snapshot, publish_latency_snapshot]
---
# Service latency snapshot

Use this procedure for analytics on service latency.

Tools: `query_service_metrics`, `compute_latency_snapshot`, `publish_latency_snapshot`.

## Workflow
1. Run `query_service_metrics` for the service data.
2. Run `compute_latency_snapshot` with a freshness target of 15 minutes or less.
3. Run `publish_latency_snapshot`.

You are finished when the latency snapshot is **published** and refresh minutes are **15 or less**.

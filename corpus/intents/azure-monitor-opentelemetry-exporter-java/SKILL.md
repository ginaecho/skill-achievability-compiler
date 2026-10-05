---
name: java-azure-monitor-span-delivery
description: Configure Java OpenTelemetry and deliver a span to Azure Monitor ingestion.
allowed-tools: [configure_exporter, record_span, export_span]
---

# Java Azure Monitor Span Delivery

Use this procedure for a Java compatibility scenario that still targets the Azure Monitor OpenTelemetry exporter package.

Tools: `configure_exporter`, `record_span`, `export_span`.

## Workflow

1. Use `configure_exporter` to set up Azure Monitor exporting for the Java OpenTelemetry SDK.
2. Use `record_span` to create and end a representative span from the configured tracer.
3. Use `export_span` to deliver the span to Azure Monitor ingestion.
4. Report the telemetry delivery result with the package path used.

You are finished when the Java span is **recorded** and telemetry is **delivered** to Azure Monitor.

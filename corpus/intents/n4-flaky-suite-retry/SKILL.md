---
name: suite-retry-report
description: Repeat a test suite until ready and publish the report.
allowed-tools: [run_suite, publish_test_report]
---

# Suite retry report

Use this procedure when a suite may need another pass before a report is published.

Tools: `run_suite`, `publish_test_report`.

## Workflow
1. Use `run_suite` for the suite pass.
2. Choose `again` to repeat the suite pass, or choose `ready` to exit the retry loop.
3. After the ready branch, use `publish_test_report` to publish the report.

You are finished when the test report is **shared**.

---
name: card-dispute-triage
description: Coordinate card dispute triage between analyst and case worker.
allowed-tools: [credit_cardholder, request_merchant_evidence]
---

# Card dispute triage

Two participants take part: a **dispute analyst** and a **case worker**.

Tools: credit_cardholder, request_merchant_evidence.

## Workflow
1. The dispute analyst chooses either cardholder credit or merchant evidence.
2. For cardholder credit, the dispute analyst sends the case worker the `cardholder_credit` label, then the case worker uses `credit_cardholder`.
3. For merchant evidence, the dispute analyst sends the case worker the `merchant_evidence` label, then the case worker uses `request_merchant_evidence`.

You are finished when the dispute is **advanced**.

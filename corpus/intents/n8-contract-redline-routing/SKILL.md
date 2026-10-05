---
name: contract-redline-routing
description: Route a contract redline to the right editing track.
allowed-tools: [scan_terms, revise_privacy, revise_payment]
---

# Contract redline routing

Two participants take part: a **reviewer** and an **editor**.

Tools: `scan_terms`, `revise_privacy`, `revise_payment`.

## Workflow
1. The reviewer uses `scan_terms` to examine the contract terms.
2. The reviewer chooses the privacy track or the payment track.
3. On the privacy track, the reviewer sends `privacy_track` to the editor, then the editor uses `revise_privacy`.
4. On the payment track, the reviewer sends `payment_track` to the editor, then the editor uses `revise_payment`.

You are finished when the contract redline is **ready**.

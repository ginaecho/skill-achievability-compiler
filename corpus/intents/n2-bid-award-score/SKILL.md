---
name: bid-award-score
description: Award a supplier after bid scoring reaches the target.
allowed-tools: [collect_supplier_bids, score_bid_responses, award_supplier]
---

# Bid award score

Use this procedure for a sourcing manager awarding a supplier from bid responses.

Tools: collect_supplier_bids, score_bid_responses, award_supplier.

## Workflow
1. Use `collect_supplier_bids` to collect bid responses.
2. Use `score_bid_responses` to score the responses.
3. Use `award_supplier` to award the selected supplier.

You are finished when the supplier is **awarded** with a score of at least 80.

---
name: hardware-ticket-retry
description: Hardware ticket stock retry procedure.
allowed-tools: [check_laptop_stock, assign_laptop_asset]
---
# Hardware ticket stock retry

Tools: `check_laptop_stock`, `assign_laptop_asset`.

## Workflow
1. Begin the `stock_cycle` loop.
2. Run `check_laptop_stock` in the loop.
3. Choose `try_again` to continue `stock_cycle` or `ready` to exit.
4. After exiting, run `assign_laptop_asset`.

You are finished when the requested hardware ticket stock retry task is **complete**.

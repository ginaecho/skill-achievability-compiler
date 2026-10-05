---
name: return-label-detail-loop
description: Review a return request and create a return label after detail collection.
allowed-tools: [inspect_return_request, request_return_detail, create_return_label]
---

# Return label detail loop

Use this procedure when a return request may need extra detail before a label is created.

Tools: `inspect_return_request`, `request_return_detail`, `create_return_label`.

## Workflow
1. Use `inspect_return_request` to review the return request.
2. Choose either the needs-detail path or the ready path.
3. On the needs-detail path, use `request_return_detail` and repeat the workflow.
4. On the ready path, use `create_return_label`.

You are finished when the return label is **created**.

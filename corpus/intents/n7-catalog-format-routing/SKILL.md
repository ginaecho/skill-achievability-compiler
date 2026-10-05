---
name: catalog-format-routing
description: Route a new title by catalog format.
allowed-tools: [catalog_ebook_record, catalog_print_record]
---

# Catalog format routing

Use this procedure when acquisitions selects the cataloging path for a new library title.

Tools: `catalog_ebook_record`, `catalog_print_record`.

Two participants take part: an **acquisitions_lead** and a **cataloger**.

## Workflow
1. The acquisitions lead chooses the ebook branch or the print branch.
2. On the ebook branch, the cataloger runs `catalog_ebook_record`.
3. On the print branch, the cataloger runs `catalog_print_record`.

You are finished when the catalog record is **catalog_ready**.

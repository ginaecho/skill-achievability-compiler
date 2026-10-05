---
name: editorial-package-routing
description: Build an editorial package from the selected route.
allowed-tools: [check_rights, build_rights_package, build_standard_package]
---

# Editorial package routing

Two participants take part: an **editor** and a **producer**.

Tools: `check_rights`, `build_rights_package`, `build_standard_package`.

## Workflow
1. The editor chooses the rights route or the standard route.
2. On the rights route, the producer uses `check_rights`, then `build_rights_package`.
3. On the standard route, the producer uses `build_standard_package`.

You are finished when the editorial package is **ready**.

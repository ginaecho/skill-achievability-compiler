---
name: dependency-patch-advisory
description: Inspect dependencies, patch the manifest, and publish an advisory.
allowed-tools: [inspect_deps, patch_manifest, publish_advisory]
---

# Dependency patch advisory

Use this procedure when dependency maintenance needs a patched manifest and an advisory.

Tools: `inspect_deps`, `patch_manifest`, `publish_advisory`.

## Workflow
1. Use `inspect_deps` to inspect dependency files.
2. Use `patch_manifest` after inspection.
3. Use `publish_advisory` after the manifest patch.

You are finished when the manifest is **patched** and the advisory is **published**.

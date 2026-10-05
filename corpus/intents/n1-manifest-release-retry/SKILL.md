---
name: manifest-release-retry
description: Scan a manifest until ready, then release a container.
allowed-tools: [scan_manifest, release_container]
---
# Retry manifest scan before release

Use this procedure when a yard agent prepares a container for release.

Tools: `scan_manifest`, `release_container`.

## Workflow
1. Run `scan_manifest`.
2. The yard_agent chooses `scan_again` to repeat the scan, or `ready` to leave the scan loop.
3. After the loop, run `release_container`.

You are finished when the container is **released**.

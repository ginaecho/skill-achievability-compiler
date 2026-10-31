<!-- SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Repository routes

These are routing targets, not guarantees of public availability or compatibility.
Read the entrypoint at the selected revision before relying on it. If a candidate
path is absent, inspect the repository's skill index and report the gap.

For each actual handoff, capture the expert's declared version separately from
its Git revision and the component/API versions being discussed. Use the version
rules in the router. The [release record](releases.md) records inspected revisions
and version metadata; these routes do not establish runtime compatibility.

| Need | Public source | Expert or documented entrypoint |
| --- | --- | --- |
| Access existing storage, configure client authentication, integrate USD resolution | [ovstorage]([url-1]) | [ovstorage expert]([url-2]) |
| Implement content service contracts or adapters; local-process or cluster services | [usd-content-workspace]([url-3]) | [workspace expert on release/v0.1.0]([url-4]) |
| Publish and consume exact package versions and dependencies | [ovpackage]([url-5]) | Verified task-skill fallback: [CLI]([url-6]) or [API]([url-7]); no dedicated expert found at this revision |
| Concurrent USD edits, session integration and recovery | [ovlive]([url-8]) | Documentation fallback: [client]([url-9]), [support boundary]([url-10]), [service]([url-11]). No SKILL.md or AGENTS.md found at this revision; do not invent an expert handoff. |
| Local/shared source-content or derived-data caching | [usd-caches]([url-12]) | [cache expert]([url-13]) |

Use `release/v0.1.0` for usd-content-workspace, including local checkout selection.
Resolve and record the branch's current commit for each handoff; branch links can
advance. Keep this branch selection when refreshing the release record.

For prebuilt deployments, follow [NGC artifacts and owning documentation](prebuilt-artifacts.md).
The workspace expert owns service deployment and release-inventory interpretation;
the cache expert owns Hub, OVCC and OVDC placement and integration. The ovlive
client and its separately versioned Live Edit Service require compatible hosts;
a source tag alone does not demonstrate a runnable integration.

Handoff example: “We have one developer on Linux, existing filesystem content,
and want a plain local service process. Preserve the filesystem as authority.
Using this source revision, identify the smallest runnable option, actual APIs,
prerequisites, limitations and a disposable save/readback check. Cite source files;
do not deploy anything.”

A multi-region case should additionally give worker locations, source location,
read reuse, derived-data generation and allowed retention. Request a topology and
its evidence; do not guess cache counts, bucket replication or automatic failover.

<!-- SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# NGC prebuilds and documentation

Checked **2026-10-20**. Use these links to find supported distribution artifacts
and owning documentation. Read the [release record](releases.md) before selecting
versions; source repositories, libraries, charts, images and API specifications
have separate release identities. Fetch and deployment instructions belong to the
[workspace and cache experts](repositories.md), not this router.

## Services

Start with the [NGC service collection]([url-1])
and [Developer Guide]([url-2]).
The collection retains the catalog label “Omniverse Storage APIs.” It distributes
service artifacts; the broad workflow expert here is Omniverse Content Services.
The `ovstorage` client library is a separate component, not the Storage Service image.

| Capability | Prebuilt entrypoints | Owning documentation |
| --- | --- | --- |
| Storage access through service adapters | [Storage image]([url-3]), [chart]([url-4]) | [Storage configuration]([url-5]); follow its service reference for configuration authority |
| Service discovery | [Legacy Discovery chart]([url-6]); locate Auto Discovery in the service collection | [Discovery guide]([url-7]); ask the workspace expert to distinguish the static catalog from the operator |
| Notifications and subscriptions | [Aggregation image]([url-8]), [chart]([url-9]); [Consumer image]([url-10]), [chart]([url-11]) | [Notifications guide]([url-12]), including broker dependencies |
| Permission policies | [Permission image]([url-13]), [chart]([url-14]) | [Permissions guide]([url-15]) |
| Identity and User Info | Service collection: `microsoft-graph-userinfo-service` and authentication dependencies; verify exact coordinates using the workspace inventory | [User Info guide]([url-16]) |
| Live USD sessions | [Live Edit image]([url-17]), [chart]([url-18]) | [Live Edit deployment]([url-19]) and [ovlive client integration]([url-20]) |
| Thumbnail generation and retrieval | [Thumbnail image]([url-21]), [chart]([url-22]) | Developer Guide's Thumbnail Service sections; verify the worker image as well as the service |

Navigator, permission UI, API specification resources and supporting test artifacts
are also in the workspace inventory. Load that inventory for those tasks instead
of treating every artifact as a mandatory service. An API resource is not a
running service. Custom adapters still require implementation and conformance
checks; a prebuilt service does not prove support for an arbitrary backend.

## Caches

| Cache and purpose | Prebuilt distribution | Owning documentation |
| --- | --- | --- |
| Hub Workstation Cache: local reuse of content and derived data through supported clients | [Resource packages]([url-23]), [container]([url-24]) | [Hub guide]([url-25]) |
| Omniverse Content Cache (OVCC): shared source-content caching | [Image `usd-content-cache`]([url-26]), [chart `ovcontentcache`]([url-27]) | [OVCC guide]([url-28]) |
| Omniverse Derived Cache (OVDC): shared reuse of computed/derived data | [Image]([url-29]), [chart]([url-30]) | [OVDC guide]([url-31]) |

Ask the cache expert to select placement and compatible client integrations from
the user's locality, reuse and retention constraints. These caches do not turn
an arbitrary SMB/NFS client into a cache-aware application. Establish permission
for managed local caching before recommending workstation persistence.

## Artifact selection and access

Catalog visibility, entitlement, download access and runtime behavior are separate
checks. Some NGC entries require sign-in or subscription access. Container images
and Helm charts use different registries and authentication; an NGC acquisition
key is not a runtime service identity. Use the workspace expert's
[artifact-access reference on release/v0.1.0]([url-32])
and the [NGC catalog guide]([url-33])
for the actual retrieval procedure. Never put credentials in a report.

For a concrete deployment handoff, identify the selected chart version and every
required image tag (including workers and test images), the relevant API/client
versions and host support, then have the owning expert verify the rendered
configuration and a representative workflow. Record immutable digests when
available. If a source or catalog listing disagrees with a release inventory,
report the discrepancy and verify the exact artifact instead of silently choosing
a substitute. Documentation review alone does not verify a download or deployment.

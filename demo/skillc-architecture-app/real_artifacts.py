"""Load real, externally published SKILL.md, agent.md, and prompt artifacts.

Every artifact is read from the pinned `gc/data_train_test` corpus, keeps its
upstream provenance, and is verified against its recorded SHA-256; artifacts
whose bytes differ from their manifest are excluded and reported. Authored
benchmark fixtures (`ce_sources_created`) are deliberately excluded.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

SKILL_POOLS = (
    "ce_sources",
    "ce_sources_ext",
    "ce_sources_div",
    "ce_sources_gr",
    "compaction_sources",
)
COPILOT_POOL = "copilot_sources"
HOME_RUNTIME = {
    "skill": "claude-code",
    "agent": "vscode-copilot",
    "prompt": "vscode-copilot",
}


def load_real_artifacts(data_root: Path) -> tuple[list[dict], list[dict]]:
    """Return verified unique artifacts and those excluded by integrity checks."""
    benchmark = data_root / "benchmark"
    artifacts = [
        *(
            artifact
            for pool in SKILL_POOLS
            for artifact in _skill_pool(benchmark / pool, pool)
        ),
        *_copilot_pool(benchmark / COPILOT_POOL),
    ]
    verified, excluded, seen = [], [], set()
    for artifact in artifacts:
        if artifact.pop("integrity_error", None):
            excluded.append({key: artifact[key] for key in ("id", "kind", "pool", "sha256")}
                            | {"actual_sha256": artifact["actual_sha256"]})
            continue
        if artifact["sha256"] in seen:
            continue
        seen.add(artifact["sha256"])
        verified.append(artifact)
    return sorted(verified, key=lambda item: (item["kind"], item["id"])), excluded


def balanced_subset(artifacts: list[dict]) -> list[dict]:
    """Equal-size, content-neutral sample per kind (lowest SHA-256 first)."""
    by_kind: dict[str, list[dict]] = {}
    for artifact in artifacts:
        by_kind.setdefault(artifact["kind"], []).append(artifact)
    size = min(len(items) for items in by_kind.values())
    return [
        artifact
        for kind in sorted(by_kind)
        for artifact in sorted(by_kind[kind], key=lambda item: item["sha256"])[:size]
    ]


def _skill_pool(pool_dir: Path, pool: str) -> list[dict]:
    records = json.loads((pool_dir / "sources.json").read_text(encoding="utf-8"))
    return [
        _artifact(
            kind="skill",
            pool=pool,
            identifier=record["id"],
            path=pool_dir / record["id"] / "SKILL.md",
            sha256=record.get("sha256") or record["skill_md_sha256"],
            repo_url=record.get("repo_url") or record.get("source_url", ""),
            commit=record.get("commit", ""),
            path_in_repo=record.get("path_in_repo") or record.get("path", ""),
            license_spdx=record.get("license_spdx") or record.get("license", ""),
            root=pool_dir,
        )
        for record in records
    ]


def _copilot_pool(pool_dir: Path) -> list[dict]:
    manifest = pool_dir / "sources.json"
    if not manifest.is_file():
        return []
    records = json.loads(manifest.read_text(encoding="utf-8"))
    return [
        _artifact(
            kind=record["kind"],
            pool=COPILOT_POOL,
            identifier=record["id"],
            path=pool_dir / record["path"],
            sha256=record["sha256"],
            repo_url=record["repo_url"],
            commit=record["commit"],
            path_in_repo=record["path_in_repo"],
            license_spdx=record["license_spdx"],
            root=pool_dir,
        )
        for record in records
    ]


def _artifact(*, kind: str, pool: str, identifier: str, path: Path, sha256: str,
              repo_url: str, commit: str, path_in_repo: str,
              license_spdx: str, root: Path) -> dict:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        # A manifest path that escapes its pool is never read (it could be any local file).
        data, actual = b"", "path-outside-pool"
    else:
        data = resolved.read_bytes()
        actual = hashlib.sha256(data).hexdigest()
    return {
        "id": identifier,
        "kind": kind,
        "pool": pool,
        "home_runtime": HOME_RUNTIME[kind],
        "repo_url": repo_url,
        "commit": commit,
        "path_in_repo": path_in_repo,
        "license_spdx": license_spdx,
        "sha256": sha256,
        "actual_sha256": actual,
        "integrity_error": actual != sha256,
        "content": data.decode("utf-8", errors="replace"),
    }

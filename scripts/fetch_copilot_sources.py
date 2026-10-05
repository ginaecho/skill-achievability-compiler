#!/usr/bin/env python3
"""Pin real Copilot agent and prompt files from github/awesome-copilot.

The repository migrated its prompt files into skills on 2026-02-24, so the
corpus is pinned to the last commit that still ships both `agents/*.agent.md`
and `prompts/*.prompt.md`. Files are stored byte-identical to upstream with
the repository's MIT license and a `sources.json` provenance manifest.

Usage:  python scripts/fetch_copilot_sources.py DEST
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import tarfile
import urllib.request
from pathlib import Path

REPO = "github/awesome-copilot"
COMMIT = "e13e02bea62b7ac6200ac94131a87a8096d4c992"
TARBALL = f"https://codeload.github.com/{REPO}/tar.gz/{COMMIT}"
KINDS = {
    "agent": re.compile(r"^agents/[^/]+\.agent\.md$"),
    "prompt": re.compile(r"^prompts/[^/]+\.prompt\.md$"),
}
MIN_BYTES, MAX_BYTES = 300, 60_000


def _case_id(path: str) -> str:
    stem = Path(path).name.split(".")[0]
    slug = re.sub(r"[^a-z0-9_-]+", "-", stem.lower()).strip("-")
    return f"github__awesome-copilot__{slug}"


def select_sources(files: dict[str, bytes]) -> list[dict]:
    """Choose redistributable agent/prompt files and describe their provenance."""
    records, seen = [], set()
    for path in sorted(files):
        kind = next((name for name, rule in KINDS.items() if rule.match(path)), None)
        data = files[path]
        digest = hashlib.sha256(data).hexdigest()
        if kind is None or not MIN_BYTES <= len(data) <= MAX_BYTES or digest in seen:
            continue
        seen.add(digest)
        records.append({
            "id": _case_id(path),
            "kind": kind,
            "repo_url": f"https://github.com/{REPO}",
            "commit": COMMIT,
            "path_in_repo": path,
            "license_spdx": "MIT",
            "license_file": "LICENSE",
            "sha256": digest,
            "bytes": len(data),
        })
    return records


def download() -> dict[str, bytes]:
    with urllib.request.urlopen(TARBALL, timeout=180) as response:
        payload = response.read()
    files = {}
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        for member in archive.getmembers():
            if member.isfile():
                relative = member.name.split("/", 1)[1]
                if relative == "LICENSE" or any(r.match(relative) for r in KINDS.values()):
                    files[relative] = archive.extractfile(member).read()
    return files


def write_corpus(dest: Path, files: dict[str, bytes]) -> list[dict]:
    records = select_sources(files)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "LICENSE").write_bytes(files["LICENSE"])
    for record in records:
        target = dest / f"{record['kind']}s" / Path(record["path_in_repo"]).name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(files[record["path_in_repo"]])
        record["path"] = target.relative_to(dest).as_posix()
    (dest / "sources.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    return records


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    records = write_corpus(Path(sys.argv[1]), download())
    counts = {kind: sum(r["kind"] == kind for r in records) for kind in KINDS}
    print(f"pinned {REPO}@{COMMIT[:8]}: {counts}")
    return 0 if records else 1


if __name__ == "__main__":
    sys.exit(main())

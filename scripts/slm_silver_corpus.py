"""Silver training corpus for the small-model arms: every licensed SKILL.md in the clones
that is not already labelled, not a near-duplicate of a labelled or benchmark skill, and
not a mirrored copy.

Labels come from the skill document only (runs/20260928_div/slm/silver/LABELLER_PROMPT.md):
requirement class and core/optional are properties of the text, so no execution report
is needed. "blocked" cannot be labelled without a report and is left out. Silver rows are
used only for training; the models are still evaluated on the report-grounded (gold) rows.

  python scripts/slm_silver_corpus.py CLONES_DIR [--batch 12]

Writes benchmark/slm_silver/<id>/SKILL.md (+ sources.json with licence per skill) and
runs/20260928_div/slm/silver/{items/<id>.json, batch_NNN.json}.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
from scripts.collect_ce_sources_ext import (find_license, ident, inside_repo,  # noqa: E402
                                            jaccard, sha, shingles, spdx)
from skillc.frontend.policyindex import extract_terms  # noqa: E402

OUT = ROOT / "benchmark" / "slm_silver"
K = 16  # bottom-k sketch size for near-duplicate candidate search


class NearDup:
    """Near-duplicate index: documents sharing any of their K smallest shingle hashes are
    compared exactly (Jaccard >= 0.8 counts as a duplicate)."""

    def __init__(self):
        self.docs, self.inv = [], {}

    @staticmethod
    def _sketch(sh: set) -> list[int]:
        return sorted(int(sha(x)[:12], 16) for x in sh)[:K]

    def seen(self, sh: set) -> bool:
        cand = {i for h in self._sketch(sh) for i in self.inv.get(h, ())}
        return any(jaccard(sh, self.docs[i]) >= 0.8 for i in cand)

    def add(self, sh: set) -> None:
        self.docs.append(sh)
        for h in self._sketch(sh):
            self.inv.setdefault(h, []).append(len(self.docs) - 1)
SILVER = ROOT / "runs" / "20260928_div" / "slm" / "silver"
LABELS = ROOT / "runs" / "20260928_div" / "labels" / "out"
SKIP = {"template", "templates", "test", "tests", "fixtures", "evals", "node_modules", ".git",
        "dist", "build"}  # mirrored copies (.claude, .codex, ...) are removed as duplicates


def prune_stale(silver: Path, current: dict[str, str]) -> None:
    """Make the generated silver artifacts match the corpus being written.

    `current` maps each kept skill id to its SKILL.md sha256. Items and label outputs of
    skills no longer kept, or whose document changed, are removed (labels of an unchanged
    skill are kept, so they need not be paid for again); batches are always rebuilt."""
    for item in sorted((silver / "items").glob("*.json")):
        try:
            data = json.loads(item.read_text(encoding="utf-8"))
            recorded = data.get("sha256") or _document_sha(data.get("skill_path"))
        except (OSError, ValueError, AttributeError):
            recorded = None
        if current.get(item.stem) != recorded:
            item.unlink()
    for label in sorted((silver / "out").glob("*.json")):
        if not (silver / "items" / label.name).exists():
            label.unlink()
    for batch in silver.glob("batch_*.json"):
        batch.unlink()


def _document_sha(path) -> str | None:
    """sha256 of an earlier item's document (items written before `sha256` was recorded)."""
    if not path or not Path(path).is_file():
        return None
    return sha(Path(path).read_text(encoding="utf-8", errors="replace").encode())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("clones", type=Path)
    ap.add_argument("--batch", type=int, default=12)
    a = ap.parse_args()

    labelled = {json.loads(f.read_text())["skill"].split("@")[0] for f in LABELS.glob("*.json")}
    seen_sha, corpus = set(), NearDup()
    for p in (ROOT / "benchmark").glob("*/*/SKILL.md"):   # every benchmark skill (incl. test sets)
        if p.parent.parent.name == "slm_silver":
            continue
        t = p.read_bytes()
        seen_sha.add(sha(t))
        corpus.add(shingles(t.decode("utf-8", "replace")))

    kept, skipped = [], {"no_licence": 0, "dup": 0, "labelled": 0, "mirror": 0, "short": 0,
                     "outside": 0}
    for repo in sorted(d for d in a.clones.iterdir() if d.is_dir()):
        org_repo = repo.name.replace("_", "/", 1)
        for p in sorted(repo.rglob("SKILL.md")):
            rel = p.relative_to(repo)
            if SKIP & {x.lower() for x in rel.parts[:-1]}:
                skipped["mirror"] += 1
                continue
            sid = ident(org_repo, p.parent)
            if inside_repo(p, repo) is None:
                skipped["outside"] += 1
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            if len(text) < 400:
                skipped["short"] += 1
                continue
            if sid in labelled:
                skipped["labelled"] += 1
                continue
            lic = find_license(repo, p.parent)
            lic_id = spdx(lic.read_text(errors="replace")) if lic else None
            if not lic_id:
                skipped["no_licence"] += 1
                continue
            h, sh = sha(text.encode()), shingles(text)
            if h in seen_sha or corpus.seen(sh):
                skipped["dup"] += 1
                continue
            if any(k["id"] == sid for k in kept):
                sid = f"{sid}-{h[:6]}"
            seen_sha.add(h)
            corpus.add(sh)
            kept.append({"id": sid, "repo": org_repo, "path": str(rel), "licence": lic_id,
                         "sha256": h, "text": text})

    (SILVER / "items").mkdir(parents=True, exist_ok=True)
    prune_stale(SILVER, {k["id"]: k["sha256"] for k in kept})
    if OUT.exists():
        shutil.rmtree(OUT)
    for k in kept:
        d = OUT / k["id"]
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(k.pop("text"), encoding="utf-8")
        cands = [c["term"] for c in extract_terms((d / "SKILL.md").read_text(encoding="utf-8"),
                                                  limit=30)]
        (SILVER / "items" / f"{k['id']}.json").write_text(json.dumps(
            {"skill": k["id"], "skill_path": str(d / "SKILL.md"), "sha256": k["sha256"],
             "candidates": cands}, indent=1))
    (OUT / "sources.json").write_text(json.dumps(kept, indent=1) + "\n")
    ids = sorted(k["id"] for k in kept)
    for i in range(0, len(ids), a.batch):
        (SILVER / f"batch_{i // a.batch:03d}.json").write_text(json.dumps(ids[i:i + a.batch]))
    by_repo = {}
    for k in kept:
        by_repo[k["repo"]] = by_repo.get(k["repo"], 0) + 1
    print(json.dumps({"kept": len(kept), "skipped": skipped, "batches": -(-len(ids) // a.batch),
                      "by_repo": by_repo}, indent=1))


if __name__ == "__main__":
    main()

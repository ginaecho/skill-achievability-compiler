"""Collect the extension corpus benchmark/ce_sources_ext (more real SKILL.md cases).

Same selection rules as benchmark/ce_sources (see its README), applied to:
  * the three capped collections, beyond their first 30 skills
    (microsoft/skills, github/awesome-copilot, trailofbits/skills);
  * three repositories not in ce_sources
    (NVIDIA/skills, addyosmani/agent-skills,
     muratcankoylan/Agent-Skills-for-Context-Engineering).
Candidates are de-duplicated against ce_sources and compaction_sources
(exact and near duplicates), and against each other.

  python scripts/collect_ce_sources_ext.py CLONES_DIR
CLONES_DIR holds `git clone --depth 1` checkouts named <org>_<repo>.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "benchmark" / "ce_sources"
OUT = ROOT / "benchmark" / "ce_sources_ext"
COMPACTION = ROOT / "benchmark" / "compaction_sources"
REPOS = [  # (org/repo, cap on NEW skills)
    ("microsoft/skills", 20), ("github/awesome-copilot", 20), ("trailofbits/skills", 20),
    ("nvidia/skills", 30), ("addyosmani/agent-skills", 30),
    ("muratcankoylan/Agent-Skills-for-Context-Engineering", 30),
]
LICENSES = {"MIT": ["mit license", "permission is hereby granted, free of charge"],
            "Apache-2.0": ["apache license", "version 2.0"],
            "MPL-2.0": ["mozilla public license"],
            "CC-BY-4.0": ["creative commons attribution 4.0", "cc by 4.0",
                          "attribution 4.0 international"],
            "CC-BY-SA-4.0": ["attribution-sharealike 4.0"]}
SKIP_DIRS = {"template", "templates", "test", "tests", "fixtures", "evals", "node_modules", ".git"}


def sha(b: bytes | str) -> str:
    if isinstance(b, str):
        b = b.encode()
    return hashlib.sha256(b).hexdigest()


def shingles(text: str) -> set:
    w = re.findall(r"[a-z0-9]+", text.lower())
    return {" ".join(w[i:i + 5]) for i in range(max(0, len(w) - 4))}


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def spdx(text: str) -> str | None:
    t = text.lower()
    for k in ("CC-BY-SA-4.0", "CC-BY-4.0", "MPL-2.0", "Apache-2.0", "MIT"):
        if all(s in t for s in LICENSES[k][:1]) or any(s in t for s in LICENSES[k]):
            if k == "Apache-2.0" and "apache license" not in t:
                continue
            return k
    return None


def find_license(repo: Path, skill_dir: Path) -> Path | None:
    d = skill_dir
    while True:
        for name in ("LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING", "LICENSE-CC-BY-4.0"):
            if (d / name).is_file():
                return d / name
        if d == repo:
            return None
        d = d.parent


def ident(org_repo: str, skill_dir: Path) -> str:
    org, repo = org_repo.lower().split("/")
    return re.sub(r"[^a-z0-9_-]", "", f"{org}__{repo}__{skill_dir.name.lower()}")


def main(clones: Path) -> None:
    base = json.loads((BASE / "sources.json").read_text())
    seen_sha = {s["sha256"] for s in base}
    seen_ids = {s["id"] for s in base}
    corpus = [(s["id"].split("__")[-1], shingles((BASE / s["id"] / "SKILL.md").read_text(
        encoding="utf-8", errors="replace"))) for s in base]
    for p in COMPACTION.rglob("*.md"):
        seen_sha.add(sha(p.read_bytes()))
        corpus.append((p.parent.name.lower(), shingles(p.read_text(errors="replace"))))
    out = []
    for org_repo, cap in REPOS:
        repo = clones / org_repo.replace("/", "_")
        commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                                capture_output=True, text=True).stdout.strip()
        cands = []
        for f in sorted(repo.rglob("SKILL.md")):
            rel = f.relative_to(repo)
            if SKIP_DIRS & {p.lower() for p in rel.parts[:-1]}:
                continue
            real = f.resolve()
            data = real.read_bytes()
            if not 300 <= len(data) <= 60_000 or sha(data) in seen_sha:
                continue
            lic = find_license(repo, f.parent)
            if lic is None:
                continue
            kind = spdx(lic.read_text(errors="replace"))
            if kind is None:
                continue
            sid = ident(org_repo, f.parent)
            if sid in seen_ids:
                continue
            cands.append((sid, rel, data, lic, kind))
        # fixed order: group by the first hyphen token, round-robin, sha order within groups
        groups: dict[str, list] = {}
        for c in sorted(cands, key=lambda c: sha("ext:" + c[0])):
            groups.setdefault(c[1].parent.name.split("-")[0].lower(), []).append(c)
        order = []
        while any(groups.values()):
            for g in sorted(groups):
                if groups[g]:
                    order.append(groups[g].pop(0))
        taken = 0
        for sid, rel, data, lic, kind in order:
            if taken >= cap:
                break
            text = data.decode("utf-8", errors="replace")
            sh = shingles(text)
            name = rel.parent.name.lower()
            if any(jaccard(sh, o) > 0.6 or (n == name and jaccard(sh, o) > 0.25)
                   for n, o in corpus):
                continue
            d = OUT / sid
            d.mkdir(parents=True, exist_ok=True)
            (d / "SKILL.md").write_bytes(data)
            shutil.copyfile(lic, d / "LICENSE")
            out.append({"id": sid, "repo_url": f"https://github.com/{org_repo}", "commit": commit,
                        "path_in_repo": str(rel), "license_spdx": kind,
                        "license_file": str(lic.relative_to(repo)), "sha256": sha(data),
                        "bytes": len(data)})
            corpus.append((name, sh))
            seen_sha.add(sha(data))
            seen_ids.add(sid)
            taken += 1
        print(f"{org_repo}: {len(cands)} candidates, {taken} taken")
    out.sort(key=lambda s: s["id"])
    (OUT / "sources.json").write_text(json.dumps(out, indent=2) + "\n")
    print(f"{len(out)} skills -> {OUT}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))

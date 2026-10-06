"""Collect benchmark/ce_sources_gr: fresh non-developer SKILL.md cases for the P2g-grounded test
(same sources and procedure as collect_ce_sources_div.py, excluding every earlier corpus).

Sources (licensed; `git clone --depth 1` checkouts named <org>_<repo> in CLONES_DIR):
  anthropics/knowledge-work-plugins, anthropics/financial-services-plugins (Apache-2.0),
  K-Dense-AI/claude-scientific-skills, coreyhaines31/marketingskills,
  alirezarezvani/claude-skills (MIT).
Engineering folders and mirrored copies (.gemini, .codex, ...) are skipped. Each skill gets a
domain label from its folder. Candidates are de-duplicated (exact and near) against
ce_sources, ce_sources_ext and compaction_sources, and N = 50 are taken round-robin over
domains in a fixed sha256 order.

  python scripts/collect_ce_sources_gr.py CLONES_DIR
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.collect_ce_sources_ext import (COMPACTION, find_license, jaccard,  # noqa: E402
                                            head_commit, inside_repo, sha,
                                            shingles, spdx)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "benchmark" / "ce_sources_gr"
N = 50
SKIP = {"engineering", "engineering-team", ".gemini", ".codex", ".cursor", ".claude",
        "node_modules", ".git", "templates", "template", "tests", "evals"}


def domain(org_repo: str, rel: Path) -> str | None:
    parts = [p.lower() for p in rel.parts[:-1]]
    if SKIP & set(parts):
        return None
    top = parts[0] if parts else ""
    if org_repo == "anthropics/knowledge-work-plugins":
        return {"partner-built": "business-integrations", "small-business": "small-business",
                "sales": "sales", "data": "data-analytics", "operations": "operations",
                "legal": "legal", "human-resources": "human-resources",
                "product-management": "product", "marketing": "marketing",
                "finance": "finance", "design": "design", "bio-research": "life-science",
                "enterprise-search": "knowledge-search"}.get(top, "business-other")
    if org_repo == "anthropics/financial-services-plugins":
        return "financial-services"
    if org_repo == "K-Dense-AI/claude-scientific-skills":
        return "science"
    if org_repo == "coreyhaines31/marketingskills":
        return "marketing"
    if org_repo == "alirezarezvani/claude-skills":
        return {"marketing-skill": "marketing", "marketing": "marketing",
                "c-level-advisor": "executive", "c-level-agents": "executive",
                "ra-qm-team": "regulatory-quality", "compliance-os": "regulatory-quality",
                "product-team": "product", "productivity": "productivity",
                "research": "research", "project-management": "project-management",
                "commercial": "sales"}.get(top)
    return None


REPOS = ["anthropics/knowledge-work-plugins", "anthropics/financial-services-plugins",
         "K-Dense-AI/claude-scientific-skills", "coreyhaines31/marketingskills",
         "alirezarezvani/claude-skills"]


def main(clones: Path) -> None:
    corpus, seen = [], set()
    for base in ("ce_sources", "ce_sources_ext", "ce_sources_div", "ce_sources_created"):
        for p in (ROOT / "benchmark" / base).glob("*/SKILL.md"):
            b = p.read_bytes()
            seen.add(sha(b))
            corpus.append(shingles(b.decode("utf-8", "replace")))
    for p in COMPACTION.rglob("*.md"):
        seen.add(sha(p.read_bytes()))
        corpus.append(shingles(p.read_text(errors="replace")))
    cands = []
    for org_repo in REPOS:
        repo = clones / org_repo.replace("/", "_")
        commit = head_commit(repo)
        for f in sorted(repo.rglob("SKILL.md")):
            rel = f.relative_to(repo)
            dom = domain(org_repo, rel)
            if dom is None:
                continue
            real = inside_repo(f, repo)
            if real is None:
                continue
            data = real.read_bytes()
            if not 300 <= len(data) <= 60_000 or sha(data) in seen:
                continue
            lic = find_license(repo, f.parent)
            kind = spdx(lic.read_text(errors="replace")) if lic else None
            if kind is None:
                continue
            org, name = org_repo.lower().split("/")
            sid = f"{org}__{name}__{f.parent.name.lower()}".replace(" ", "-")
            cands.append(dict(sid=sid, rel=rel, data=data, lic=lic, kind=kind, repo=repo,
                              org_repo=org_repo, commit=commit, domain=dom))
    groups: dict[str, list] = {}
    for c in sorted(cands, key=lambda c: sha("gr:" + c["sid"])):
        groups.setdefault(c["domain"], []).append(c)
    out, ids = [], set()
    while len(out) < N and any(groups.values()):
        for g in sorted(groups):
            while groups[g] and len(out) < N:
                c = groups[g].pop(0)
                sh = shingles(c["data"].decode("utf-8", "replace"))
                if c["sid"] in ids or any(jaccard(sh, o) > 0.6 for o in corpus):
                    continue
                d = OUT / c["sid"]
                d.mkdir(parents=True, exist_ok=True)
                (d / "SKILL.md").write_bytes(c["data"])
                shutil.copyfile(c["lic"], d / "LICENSE")
                out.append({"id": c["sid"], "repo_url": f"https://github.com/{c['org_repo']}",
                            "commit": c["commit"], "path_in_repo": str(c["rel"]),
                            "license_spdx": c["kind"],
                            "license_file": str(c["lic"].relative_to(c["repo"])),
                            "sha256": sha(c["data"]), "bytes": len(c["data"]),
                            "domain": c["domain"]})
                corpus.append(sh)
                ids.add(c["sid"])
                break
    out.sort(key=lambda s: s["id"])
    (OUT / "sources.json").write_text(json.dumps(out, indent=2) + "\n")
    print(f"{len(cands)} candidates, {len(out)} skills -> {OUT}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))

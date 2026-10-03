"""Draw the 100 test cases for `skillc reach --claude`, reproducibly.

Sources (all real, natural-language documents written by people, pinned):

  skills  benchmark/ce_sources{,_div,_ext,_gr}/*/SKILL.md on branch
          gc/data_train_test (provenance in each sources.json), excluding any
          document whose name or content is in the development set
          (/mnt/skills and benchmark/compaction_sources)
  agents  plugins/*/agents/*.md of github.com/wshobson/agents and
          categories/*/*.md of github.com/VoltAgent/awesome-claude-code-subagents
          at the commits below

70 skills + 30 agents (15 per repository).  Within each pool, 70% of the draw
comes from documents that contain a fenced code block and 30% from those that
do not -- a criterion that does not depend on skillc -- so the set exercises
runtime requirements while keeping prose-only documents represented.

    python benchmark/claude_env/select_cases.py --agents-root /path/to/clones
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import shutil
import subprocess
from pathlib import Path

SEED = 20261003
BRANCH = "origin/gc/data_train_test"
CORPORA = ("ce_sources", "ce_sources_div", "ce_sources_ext", "ce_sources_gr")
AGENT_REPOS = {
    "wshobson/agents": ("156b7a5e7a8b93642628a339ee4039c925b34c7f", "plugins/*/agents/*.md"),
    "VoltAgent/awesome-claude-code-subagents": ("82b73821baa7a911d5b14cfb6da238b7f0db6b42",
                                                "categories/*/*.md"),
}
DEV_NAMES = {p.parent.name for p in Path("/mnt/skills").glob("*/*/SKILL.md")} | {
    p.parent.name for p in Path("benchmark/compaction_sources").glob("*/SKILL.md")}
FENCE = re.compile(r"^[ \t]*```", re.M)
HERE = Path(__file__).parent


def git_show(path: str) -> str:
    return subprocess.run(["git", "show", f"{BRANCH}:{path}"], capture_output=True, text=True,
                          check=True).stdout


def stratified(pool: list[dict], n: int, rng: random.Random) -> list[dict]:
    fenced = [d for d in pool if d["fenced"]]
    plain = [d for d in pool if not d["fenced"]]
    k = round(n * 0.7)
    return rng.sample(fenced, min(k, len(fenced))) + rng.sample(plain, n - min(k, len(fenced)))


def skills() -> list[dict]:
    dev_hashes = {hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in [*Path("/mnt/skills").glob("*/*/SKILL.md"),
                            *Path("benchmark/compaction_sources").glob("*/SKILL.md")]}
    out, seen = [], set()
    for corpus in CORPORA:
        for src in json.loads(git_show(f"benchmark/{corpus}/sources.json")):
            name = src["id"].split("__")[-1]
            if src["sha256"] in seen or src["sha256"] in dev_hashes or name in DEV_NAMES:
                continue
            seen.add(src["sha256"])
            text = git_show(f"benchmark/{corpus}/{src['id']}/SKILL.md")
            out.append({"id": src["id"], "kind": "skill", "corpus": corpus,
                        "repo_url": src["repo_url"], "commit": src["commit"],
                        "path_in_repo": src["path_in_repo"], "license": src["license_spdx"],
                        "sha256": hashlib.sha256(text.encode()).hexdigest(),
                        "fenced": bool(FENCE.search(text)), "text": text})
    return out


def agents(root: Path) -> dict[str, list[dict]]:
    out = {}
    for repo, (commit, pattern) in AGENT_REPOS.items():
        clone = root / repo.lower()
        head = subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
        if head != commit:
            raise SystemExit(f"{repo} is at {head}, expected {commit}")
        docs = []
        for p in sorted(clone.glob(pattern)):
            if p.name.lower() == "readme.md":
                continue
            text = p.read_text(encoding="utf-8")
            rel = str(p.relative_to(clone))
            docs.append({"id": f"{repo.replace('/', '__')}__{p.stem}", "kind": "agent",
                         "corpus": repo, "repo_url": f"https://github.com/{repo}",
                         "commit": commit, "path_in_repo": rel, "license": "MIT",
                         "sha256": hashlib.sha256(text.encode()).hexdigest(),
                         "fenced": bool(FENCE.search(text)), "text": text})
        out[repo] = docs
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agents-root", type=Path, default=Path("/home/user"))
    args = ap.parse_args()
    rng = random.Random(SEED)
    chosen = stratified(skills(), 70, rng)
    for docs in agents(args.agents_root).values():
        unique = list({d["sha256"]: d for d in docs}.values())
        chosen += stratified(unique, 15, rng)
    docs_dir = HERE / "cases"
    shutil.rmtree(docs_dir, ignore_errors=True)
    docs_dir.mkdir()
    cases = []
    for i, d in enumerate(chosen, 1):
        case_id = f"c{i:03d}"
        (docs_dir / f"{case_id}.md").write_text(d.pop("text"), encoding="utf-8")
        cases.append({"case": case_id, **d})
    (HERE / "cases.json").write_text(json.dumps({"seed": SEED, "cases": cases}, indent=1) + "\n",
                                     encoding="utf-8")
    print(f"{len(cases)} cases: {sum(c['kind'] == 'skill' for c in cases)} skills, "
          f"{sum(c['kind'] == 'agent' for c in cases)} agents, "
          f"{sum(c['fenced'] for c in cases)} with code blocks")


if __name__ == "__main__":
    main()

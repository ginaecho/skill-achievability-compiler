"""Draw the round-2 real-use test set: public SKILL.md files never used before.

Every document is a real, unchanged SKILL.md from a public repository, pinned
by commit and sha256.  A document is eligible only if

  * its licence is permissive (MIT, Apache-2.0, BSD, MPL-2.0, CC-BY-4.0,
    CC-BY-SA-4.0), read from the skill folder or else the repository root;
  * neither its id (owner__repo__skill), its skill name, nor its content
    (sha256) occurs in any earlier test or training set: the benchmark/ corpora
    on branch gc/data_train_test (ce_sources*, slm_silver, compaction_sources)
    and benchmark/claude_env (cases, set2, set3, set4);
  * it shares less than half of its five-word phrases (Jaccard of 5-gram
    shingles) with every earlier document and with every other drawn document,
    so a renamed or lightly edited copy of a used skill is excluded;
  * it is a user-facing skill: frontmatter with a name and a description, and
    not marked `disable-model-invocation: true` (a repository's own helper
    command);
  * it is not a duplicate of another eligible document (same sha256 or name);
  * it is a real skill: not a test fixture (a folder named tests or fixtures on its
    path) and not a blank authoring template (its first heading is a placeholder
    such as "# Skill Name"); and it is not an offensive-security skill (marked
    `risk: offensive`, or red-team, attack-chain, exploit or penetration-testing
    work in its name, description or category), because executors really attempt
    each skill.  This rule is applied while drawing, so a skipped
    document only frees its slot for the next one in the seeded order.

From the eligible pool, N documents are drawn with a fixed seed, at most CAP per
repository, 70% from documents with a fenced code block and 30% without (the
rule select_cases.py uses).  Each document is assigned one of three runtimes by
a hash of its id, so the assignment does not depend on skillc.

    python benchmark/real2/select_real2.py --clones /path/to/clones

writes benchmark/real2/cases.json and a copy of each skill's whole folder at the
pinned commit (SKILL.md, bundled scripts, references and templates; files over
2 MB are listed but not copied) plus its licence, under
benchmark/real2/sources/<id>/.  A skill is copied as it is installed: with its
folder come (a) the shared files of the plugin it belongs to (the plugin
directory without its skill folders) and (b) every other file or skill folder
of its repository that SKILL.md refers to by a relative path, resolved from the
skill folder or else from the repository root.  These support files keep their
repository paths under sources/<id>/_support/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
from pathlib import Path

SEED = 20261031
N = 300
CAP = 30
BRANCH = "origin/gc/data_train_test"
RUNTIMES = ("developer-sandbox", "offline-workstation", "office-assistant")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FENCE = re.compile(r"^[ \t]*```", re.M)
NEAR = 0.5                       # Jaccard of 5-word shingles that counts as a copy
MAX_FILE = 2_000_000             # bundled files larger than this are listed, not copied
FRONT = re.compile(r"^\s*---\s*\n(.*?)\n---", re.S)


def shingles(text: str) -> frozenset[str]:
    w = re.findall(r"[a-z0-9]+", text.lower())
    return frozenset(" ".join(w[k:k + 5]) for k in range(max(0, len(w) - 4)))


class NearIndex:
    """Inverted index of shingle sets; `near(s)` is the best Jaccard against it."""

    def __init__(self) -> None:
        self.sets: list[frozenset[str]] = []
        self.inv: dict[str, list[int]] = {}

    def add(self, s: frozenset[str]) -> None:
        j = len(self.sets)
        self.sets.append(s)
        for g in s:
            self.inv.setdefault(g, []).append(j)

    def near(self, s: frozenset[str]) -> float:
        if not s:
            return 0.0
        hits: dict[int, int] = {}
        for g in s:
            for j in self.inv.get(g, ()):
                hits[j] = hits.get(j, 0) + 1
        return max((v / len(s | self.sets[j]) for j, v in hits.items()), default=0.0)


def user_facing(text: str) -> bool:
    m = FRONT.match(text)
    if not m:
        return False
    fm = m.group(1)
    return (bool(re.search(r"^name:", fm, re.M)) and bool(re.search(r"^description:", fm, re.M))
            and not re.search(r"^disable-model-invocation:\s*true", fm, re.M))

PLACEHOLDER_H1 = re.compile(
    r"#\s*[\[<{(]*\s*(?:\{\{\s*)?(?:skill[ _-]?name|your[ _-]skill[ _-]name)"
    r"(?:\s*\}\})?\s*[\]>})]*\s*$", re.I)


# Offensive-security skills are left out: executors really attempt a skill, and
# CLAUDE.md allows nothing done for testing to harm an outside service.
OFFENSIVE = re.compile(r"red[- ]?team|attack[- ]chain|-attack\b|\battack\b.*\btechniques?\b|"
                       r"penetration|pentest|exploit|offensive|\bc2\b|malware|phishing", re.I)


def not_a_skill(path_in_repo: str, text: str) -> str | None:
    """Why a document is not in scope: a test fixture, a blank template or an
    offensive-security skill; None if it is in scope."""
    if {"tests", "test", "fixtures", "__fixtures__"} & {p.lower() for p in Path(path_in_repo).parts}:
        return "test_fixture"
    m = FRONT.match(text)
    front = m.group(1) if m else ""
    if (re.search(r"^risk:\s*['\"]?offensive", front, re.M | re.I)
            or OFFENSIVE.search(Path(path_in_repo).parent.name)
            or OFFENSIVE.search(" ".join(re.findall(r"^(?:name|description|category):.*$",
                                                    front, re.M | re.I)))):
        return "offensive_security"
    first = next((ln for ln in text.splitlines() if ln.startswith("# ")), "")
    if PLACEHOLDER_H1.fullmatch(first.strip()):
        return "blank_template"
    return None


REFS = [re.compile(r"\]\((?!https?:|#|mailto:)([^)\s]+)\)"),
        re.compile(r"(?<![\w/.:-])((?:\.{1,2}/)*[\w-]+(?:/[\w.\[\]-]+)+)")]


def support_files(rdir: Path, commit: str, skill_dir: str, text: str) -> list[str]:
    """Repository files outside the skill folder that the installed skill uses."""
    listing = subprocess.run(["git", "ls-tree", "-r", commit], cwd=rdir,
                             capture_output=True, text=True, check=True).stdout.split("\n")
    tree = [ln.split("\t", 1)[1] for ln in listing      # files only, no submodules
            if "\t" in ln and ln.split()[1] == "blob" and ln.split()[0] != "120000"]
    files = set(tree)
    skill_dirs = {str(Path(t).parent) for t in tree if Path(t).name == "SKILL.md"}

    def inside(path: str, d: str) -> bool:
        return path == d or path.startswith(d + "/")

    def own_skill(path: str) -> bool:
        return inside(path, skill_dir)

    out: set[str] = set()
    parts = Path(skill_dir).parts               # (a) the plugin's shared files
    root = None
    for i in range(len(parts) - 1, 0, -1):
        if str(Path(*parts[:i]) / ".claude-plugin" / "plugin.json") in files:
            root = str(Path(*parts[:i]))
            break
    if root is None and "plugins" in parts[:-1]:
        k = parts.index("plugins")
        if len(parts) > k + 2:
            root = str(Path(*parts[:k + 2]))
    if root is not None:
        for t in tree:
            if inside(t, root) and not own_skill(t) and not any(
                    inside(t, d) for d in skill_dirs if d != root and inside(d, root)):
                out.add(t)
    for rx in REFS:                             # (b) files the skill refers to
        for ref in rx.findall(text):
            ref = ref.split("#")[0].rstrip(".,;:)`'\"")
            if not ref or ref.startswith("/"):
                continue
            for cand in (os.path.normpath(os.path.join(skill_dir, ref)),
                         os.path.normpath(ref.lstrip("./") if ref.startswith("./") else ref)):
                if cand.startswith("..") or own_skill(cand):
                    continue
                if cand in files:
                    folder = str(Path(cand).parent)
                    if Path(cand).name == "SKILL.md" and folder in skill_dirs:
                        out |= {t for t in tree if inside(t, folder)}
                    else:
                        out.add(cand)
                    break
                if any(t.startswith(cand + "/") for t in tree) and cand in skill_dirs:
                    out |= {t for t in tree if inside(t, cand)}
                    break
    return sorted(t for t in out if not own_skill(t))


# repository -> clone directory name; the licence is read from the clone
REPOS = [
    "anthropics/skills", "openai/skills", "microsoft/skills", "cloudflare/skills",
    "supabase/agent-skills", "hashicorp/agent-skills", "getsentry/skills", "expo/skills",
    "huggingface/skills", "obra/superpowers", "trailofbits/skills", "addyosmani/agent-skills",
    "vercel-labs/agent-skills", "wshobson/agents", "ComposioHQ/awesome-claude-skills",
    "glebis/claude-skills", "AgentCTO/claude-skills", "vtmocanu/skills",
    "meetrais/claude-agent-skills", "CaliLuke/skills", "NVIDIA/skills",
    "anthropics/knowledge-work-plugins", "anthropics/financial-services-plugins",
    "K-Dense-AI/claude-scientific-skills", "coreyhaines31/marketingskills",
    "alirezarezvani/claude-skills", "github/awesome-copilot",
    "muratcankoylan/Agent-Skills-for-Context-Engineering", "neondatabase/agent-skills",
    "microsoft/aspire-skills", "davila7/claude-code-templates",
    # aggregators last: an original copy elsewhere always takes precedence
    "sickn33/agentic-awesome-skills", "jeremylongshore/claude-code-plugins-plus-skills",
]

LICENCES = [  # (spdx, pattern), first match wins
    ("Apache-2.0", re.compile(r"Apache License\s*,?\s*Version 2\.0|Apache-2\.0", re.I)),
    ("MIT", re.compile(r"\bMIT License\b|Permission is hereby granted, free of charge", re.I)),
    ("MPL-2.0", re.compile(r"Mozilla Public License,? Version 2\.0", re.I)),
    ("BSD", re.compile(r"Redistribution and use in source and binary forms", re.I)),
    ("CC-BY-SA-4.0", re.compile(r"Attribution-ShareAlike 4\.0", re.I)),
    ("CC-BY-4.0", re.compile(r"Attribution 4\.0 International|CC-BY-4\.0", re.I)),
]
LICENCE_FILE = re.compile(r"^(licen[cs]e|copying)([-._].*)?$", re.I)


def classify(text: str) -> str | None:
    for spdx, pat in LICENCES:
        if pat.search(text):
            return spdx
    return None


def licence_for(skill_dir: Path, repo_dir: Path) -> tuple[str | None, Path | None]:
    for d in (skill_dir, repo_dir):
        files = sorted(p for p in d.iterdir() if p.is_file() and LICENCE_FILE.match(p.name))
        for f in files:
            spdx = classify(f.read_text(errors="replace"))
            if spdx:
                return spdx, f
        if files:          # a licence file exists here but is not permissive
            return None, files[0]
    return None, None


def used_sets() -> tuple[set[str], set[str], set[str], NearIndex]:
    """Ids, skill names and content hashes of every earlier test or training document."""
    names = subprocess.run(["git", "ls-tree", "-r", "--name-only", BRANCH, "--", "benchmark/"],
                           cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    paths = [p for p in names if p.lower().endswith("skill.md")]
    ids = {p.split("/")[2] for p in paths}
    batch = subprocess.run(["git", "cat-file", "--batch"], cwd=ROOT, check=True,
                           input="".join(f"{BRANCH}:{p}\n" for p in paths).encode(),
                           capture_output=True).stdout
    hashes, i, index = set(), 0, NearIndex()
    while i < len(batch):
        nl = batch.index(b"\n", i)
        size = int(batch[i:nl].split()[2])
        body = batch[nl + 1:nl + 1 + size]
        hashes.add(hashlib.sha256(body).hexdigest())
        index.add(shingles(body.decode(errors="replace")))
        i = nl + 1 + size + 1
    for f in ["benchmark/claude_env/cases.json"] + [
            f"benchmark/claude_env/{s}/cases.json" for s in ("set2", "set3", "set4")]:
        p = ROOT / f
        if p.exists():
            for c in json.loads(p.read_text())["cases"]:
                ids.add(c["id"])
                if c.get("sha256"):
                    hashes.add(c["sha256"])
    skill_names = {i.split("__")[-1].lower() for i in ids}
    return ids, skill_names, hashes, index


def pool(clones: Path, used_ids, used_names, used_hashes,
         used_index: NearIndex) -> tuple[list[dict], dict]:
    out, seen_hash, seen_name = [], set(), set()
    why = {"licence": 0, "not_user_facing": 0, "used_id": 0, "used_name": 0,
           "used_content": 0, "near_copy_of_used": 0, "duplicate": 0}
    lowered = {u.lower() for u in used_ids}
    for repo in REPOS:
        rdir = clones / repo.replace("/", "_")
        if not rdir.exists():
            continue
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=rdir, capture_output=True,
                                text=True, check=True).stdout.strip()
        owner, name = repo.split("/")
        for md in sorted(rdir.rglob("SKILL.md")):
            if any(part.startswith(".git") for part in md.parts):
                continue
            skill = md.parent.name
            sid = f"{owner}__{name}__{skill}"
            body = md.read_bytes()
            sha = hashlib.sha256(body).hexdigest()
            spdx, lic = licence_for(md.parent, rdir)
            if spdx is None:
                why["licence"] += 1
                continue
            text = body.decode(errors="replace")
            if not user_facing(text):
                why["not_user_facing"] += 1
                continue
            if sid in used_ids or sid.lower() in lowered:
                why["used_id"] += 1
                continue
            if skill.lower() in used_names:
                why["used_name"] += 1
                continue
            if sha in used_hashes:
                why["used_content"] += 1
                continue
            sh = shingles(text)
            if used_index.near(sh) >= NEAR:
                why["near_copy_of_used"] += 1
                continue
            if sha in seen_hash or skill.lower() in seen_name:
                why["duplicate"] += 1
                continue
            seen_hash.add(sha)
            seen_name.add(skill.lower())
            out.append({
                "id": sid, "kind": "skill", "repo_url": f"github.com/{repo}",
                "commit": commit, "path_in_repo": str(md.relative_to(rdir)),
                "license": spdx, "license_file": str(lic.relative_to(rdir)) if lic else None,
                "sha256": sha, "bytes": len(body),
                "fenced": bool(FENCE.search(text)),
                "_src": str(md), "_lic": str(lic) if lic else None, "_sh": sh,
            })
    return out, why


def draw(cands: list[dict], n: int, cap: int, rng: random.Random) -> list[dict]:
    by_repo: dict[str, list[dict]] = {}
    for c in cands:
        by_repo.setdefault(c["repo_url"], []).append(c)
    capped = []
    for repo in sorted(by_repo):
        items = sorted(by_repo[repo], key=lambda d: d["id"])
        rng.shuffle(items)
        capped += items[:cap]
    fenced = [d for d in capped if d["fenced"]]
    plain = [d for d in capped if not d["fenced"]]
    rng.shuffle(fenced)
    rng.shuffle(plain)
    index = NearIndex()
    skipped: dict[str, str] = {}
    draw.skipped = skipped

    def take(items: list[dict], want: int, into: list[dict]) -> list[dict]:
        left = []
        for d in items:
            if d["id"] in skipped:
                continue
            if len(into) < want and (why := not_a_skill(d["path_in_repo"],
                                                       Path(d["_src"]).read_text(errors="replace"))):
                skipped[d["id"]] = why
                continue
            if len(into) < want and index.near(d["_sh"]) < NEAR:
                into.append(d)
                index.add(d["_sh"])
            else:
                left.append(d)
        return left

    picked: list[dict] = []
    fenced_left = take(fenced, min(round(n * 0.7), len(fenced)), picked)
    plain_left = take(plain, n, picked)
    if len(picked) < n:                     # top up from whichever pool has more left
        take(fenced_left + plain_left, n, picked)
    return sorted(picked, key=lambda d: d["id"])


def runtime_for(sid: str) -> str:
    h = int(hashlib.sha256(sid.encode()).hexdigest(), 16)
    return RUNTIMES[h % len(RUNTIMES)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clones", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=HERE)
    args = ap.parse_args()
    used_ids, used_names, used_hashes, used_index = used_sets()
    cands, why = pool(args.clones, used_ids, used_names, used_hashes, used_index)
    picked = draw(cands, N, CAP, random.Random(SEED))
    src = args.out / "sources"
    if src.exists():
        shutil.rmtree(src)
    cases = []
    for i, d in enumerate(picked, 1):
        dst = src / d["id"]
        dst.mkdir(parents=True)
        skill_dir = Path(d["_src"]).parent
        files, skipped = [], []
        for f in sorted(p for p in skill_dir.rglob("*") if p.is_file()):
            if ".git" in f.relative_to(skill_dir).parts:
                continue
            rel = f.relative_to(skill_dir)
            if f.stat().st_size > MAX_FILE:
                skipped.append(str(rel))
                continue
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f, dst / rel)
            files.append({"path": str(rel),
                          "sha256": hashlib.sha256(f.read_bytes()).hexdigest()})
        rdir = Path(d["_src"]).parents[len(Path(d["path_in_repo"]).parts) - 1]
        support, support_skipped = [], []
        for rel in support_files(rdir, d["commit"], str(Path(d["path_in_repo"]).parent),
                                 Path(d["_src"]).read_text(errors="replace")):
            f = rdir / rel
            if f.is_symlink() or not f.is_file() or f.stat().st_size > MAX_FILE:
                support_skipped.append(rel)
                continue
            (dst / "_support" / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f, dst / "_support" / rel)
            support.append({"path": rel, "sha256": hashlib.sha256(f.read_bytes()).hexdigest()})
        if d["_lic"] and not (dst / "LICENSE").exists():
            shutil.copyfile(d["_lic"], dst / "LICENSE")
        case = {k: v for k, v in d.items() if not k.startswith("_")}
        case["files"] = files
        case["files_not_copied"] = skipped
        case["support_files"] = support
        case["support_files_not_copied"] = support_skipped
        case["case"] = f"r{i:03d}"
        case["runtime"] = runtime_for(d["id"])
        cases.append(case)
    summary = {
        "seed": SEED, "n": len(cases), "cap_per_repo": CAP,
        "used_documents_excluded": {"ids": len(used_ids), "content_hashes": len(used_hashes)},
        "eligible_pool": len(cands), "rejected": why,
        "per_repo": {r: sum(c["repo_url"] == r for c in cases)
                     for r in sorted({c["repo_url"] for c in cases})},
        "per_runtime": {r: sum(c["runtime"] == r for c in cases) for r in RUNTIMES},
        "fenced": sum(c["fenced"] for c in cases),
        "with_bundled_files": sum(len(c["files"]) > 1 for c in cases),
        "with_support_files": sum(bool(c["support_files"]) for c in cases),
        "skipped_while_drawing": draw.skipped,
    }
    (args.out / "cases.json").write_text(json.dumps({**summary, "cases": cases}, indent=1) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()

"""Independent check of benchmark/real2/cases.json (runs/20261031_real2/PLAN.md, amendment 1).

    python benchmark/real2/verify_real2.py /path/to/clones

Checks: 300 unique ids, names and hashes; every copied file matches the pinned commit;
every file of the skill folder is copied or listed; every skill is user-facing; no id,
name or hash of an earlier test or training document; Jaccard of 5-word shingles below
0.5 against every earlier document (the gc/data_train_test corpora and the
benchmark/claude_env case texts) and within the set.
"""
import hashlib, json, re, subprocess, sys, collections
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
CL = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "benchmark/real2"))
import select_real2 as S
d = json.loads((ROOT / "benchmark/real2/cases.json").read_text())
cases = d["cases"]
prob = collections.defaultdict(list)
print("n", len(cases), "unique ids", len({c["id"] for c in cases}),
      "unique case ids", len({c["case"] for c in cases}),
      "unique sha", len({c["sha256"] for c in cases}),
      "unique names", len({c["id"].split("__")[-1].lower() for c in cases}))
# 1 files: hash in sources == recorded == pinned commit
nfiles = 0
for c in cases:
    owner, repo = c["repo_url"].split("/")[1:3]
    cdir = CL / f"{owner}_{repo}"
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cdir, capture_output=True, text=True).stdout.strip()
    if head != c["commit"]: prob["commit_mismatch"].append(c["case"])
    base = c["path_in_repo"].rsplit("/", 1)[0]
    src = ROOT / "benchmark/real2/sources" / c["id"]
    for f in c["files"]:
        nfiles += 1
        local = (src / f["path"]).read_bytes()
        pinned = subprocess.run(["git", "show", f'{c["commit"]}:{base}/{f["path"]}'], cwd=cdir, capture_output=True).stdout
        h = hashlib.sha256(local).hexdigest()
        if h != f["sha256"] or hashlib.sha256(pinned).hexdigest() != h:
            prob["file_hash"].append((c["case"], f["path"]))
    if not any(f["path"] == "SKILL.md" and f["sha256"] == c["sha256"] for f in c["files"]):
        prob["skill_hash"].append(c["case"])
    # every file in the pinned folder is either copied or listed
    tree = subprocess.run(["git", "ls-tree", "-r", "--name-only", c["commit"], "--", base + "/"], cwd=cdir,
                          capture_output=True, text=True).stdout.split()
    rel = {t[len(base) + 1:] for t in tree}
    have = {f["path"] for f in c["files"]} | {f["path"] if isinstance(f, dict) else f for f in c["files_not_copied"]}
    if rel - have: prob["folder_incomplete"].append((c["case"], sorted(rel - have)[:3]))
    if not (src / c["license_file"].split("/")[-1]).exists() and not any(src.glob("LICEN*")):
        prob["licence_copy"].append(c["case"])
    text = (src / "SKILL.md").read_text(errors="replace")
    if not S.user_facing(text): prob["not_user_facing"].append(c["case"])
print("files checked", nfiles)
# 2 near copies vs used (train/test branch + claude_env case texts) and within set
ids, names, hashes, index = S.used_sets()
for p in sorted((ROOT / "benchmark/claude_env").glob("**/cases/*.md")):
    index.add(S.shingles(p.read_text(errors="replace")))
sh = {c["case"]: S.shingles((ROOT / "benchmark/real2/sources" / c["id"] / "SKILL.md").read_text(errors="replace")) for c in cases}
worst = []
for c in cases:
    if c["id"] in ids: prob["used_id"].append(c["case"])
    if c["id"].split("__")[-1].lower() in names: prob["used_name"].append(c["case"])
    if c["sha256"] in hashes: prob["used_hash"].append(c["case"])
    j = index.near(sh[c["case"]]); worst.append(j)
    if j >= S.NEAR: prob["near_used"].append((c["case"], round(j, 2)))
def jac(a, b): return len(a & b) / max(1, len(a | b))
ks = list(sh); wmax = 0
for i in range(len(ks)):
    for k in ks[i + 1:]:
        j = jac(sh[ks[i]], sh[k]); wmax = max(wmax, j)
        if j >= S.NEAR: prob["near_within"].append((ks[i], k, round(j, 2)))
print("max Jaccard vs used", round(max(worst), 3), "max within set", round(wmax, 3))
print("licences", collections.Counter(c["license"] for c in cases))
print("runtimes", collections.Counter(c["runtime"] for c in cases))
print("repos", len({c["repo_url"] for c in cases}), "max per repo", max(collections.Counter(c["repo_url"] for c in cases).values()))
print("fenced", sum(c["fenced"] for c in cases), "bundled", sum(len(c["files"]) > 1 for c in cases),
      "not_copied", sum(bool(c["files_not_copied"]) for c in cases))
print("runtime rule ok", all(c["runtime"] == S.runtime_for(c["id"]) for c in cases))
urls = sum(bool(re.search(r"https?://|www\.", (ROOT / "benchmark/real2/sources" / c["id"] / "SKILL.md").read_text(errors="replace"))) for c in cases)
print("skills with links", urls)
print("PROBLEMS", {k: (len(v), v[:5]) for k, v in prob.items()} or "none")

"""Runner for real-use round 2 (runs/20261031_real2/PLAN.md).

This script never calls a model. It writes frozen prompt files that sub-agents
read, and scores the files they write back.

  skills                  executor copies of the 300 skill folders, URL-scrubbed
  prepare --arm s|d --repeat K
                          freeze the S (skillc) or D (direct verdict) prompts
  retry --repeat K        S: one located-error retry per invalid reply
  repair --repeat K       S: one counterexample-guided repair per refuted pack
  jobs --arm exec|s|d [--repeat K] [--round N] [--only CASES]
                          shuffled job batches of at most 50 for the workflows
  collect-exec --work DIR copy executor result.json files into execution/
  calls --transcripts DIR one line per sub-agent call into calls.jsonl
  mark-missing --arm s|d --repeat K
                          record replies still missing after one re-run (no verdict)
  audit                   every prompt and every executor copy is URL-free
  score                   labels, verdicts, checker time, tokens, metrics.json

Every prompt is scrubbed with skillc.frontend.urlguard (scrub, then
assert_clean) before it is written; `audit` re-checks all of them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import shutil
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import scripts.benchmark_ce_runtime as bcr  # noqa: E402
from scripts.benchmark_ce import mcnemar_exact, sha, wilson, write_json  # noqa: E402
from skillc import check  # noqa: E402
from skillc.frontend.prompts import ce_runtime_messages, direct_messages  # noqa: E402
from skillc.frontend.providers import extract_json_object  # noqa: E402
from skillc.frontend.runtime import load_runtime  # noqa: E402
from skillc.frontend.urlguard import HOST_RE, assert_clean, find_urls, scrub  # noqa: E402

RUN = ROOT / "runs" / "20261031_real2"
SRC = ROOT / "benchmark" / "real2" / "sources"
SEED = 20261031
BATCH = 50
REPEATS = (1, 2, 3)
L2_BLOCKED = {"missing_tool_in_runtime", "needs_credentials_or_account",
              "forbidden_by_safety_rules"}
VERDICTS = ("ACHIEVABLE", "IMPOSSIBLE")


def cases() -> list[dict]:
    return json.loads((ROOT / "benchmark/real2/cases.json").read_text())["cases"]


# ------------------------------------------------------------- executor copies
CODE_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".sh", ".bash", ".rb",
            ".go", ".rs", ".java", ".kt", ".swift", ".ps1", ".r", ".lua", ".php", ".cs"}
MEMBER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*")
# Words that are both a top-level domain in urlguard's list and a common member name.
MEMBER_NAMES = {"run", "id", "info", "app", "live", "store", "network", "host", "top",
                "click", "page", "tools", "at", "to", "work", "email", "link", "pt",
                "build", "is", "in"}


def is_member(tok: str) -> bool:
    """`subprocess.run`, `self.live`: a code member access, not a domain name.
    Two identifier labels, the first starting lower-case, the last a member name
    (so `youtu.be`, `zoom.us` or `meet.google` are still scrubbed)."""
    return (MEMBER.fullmatch(tok) is not None and (tok[0].islower() or tok[0] == "_")
            and tok.rsplit(".", 1)[1].lower() in MEMBER_NAMES)


def scrub_code(text: str) -> tuple[str, dict, list[str]]:
    """Scrub a source file without breaking member accesses."""
    kept: list[str] = []

    def protect(m: re.Match) -> str:
        if is_member(m.group(0)):
            kept.append(m.group(0))
            return f"\x00K{len(kept) - 1}\x00"
        return m.group(0)

    guarded = HOST_RE.sub(protect, text)
    out, table = scrub(guarded)
    out = re.sub(r"\x00K(\d+)\x00", lambda m: kept[int(m.group(1))], out)
    return out, table, kept


def code_clean(text: str) -> list[str]:
    return [h for h in find_urls(text) if not is_member(h)]


def build_skills() -> None:
    """runs/20261031_real2/skills/<case>/: what an executor may read."""
    dest_root = RUN / "skills"
    if dest_root.exists():
        shutil.rmtree(dest_root)
    manifest = {}
    for c in cases():
        src, dest = SRC / c["id"], dest_root / c["case"]
        rec = {"id": c["id"], "files": 0, "placeholders": 0, "code_files_scrubbed": [],
               "members_kept": 0, "withheld": []}
        for f in c["files"]:
            raw = (src / f["path"]).read_bytes()
            target = dest / f["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                if find_urls(raw.decode("latin-1")):
                    rec["withheld"].append(f["path"])     # binary with a link inside
                    continue
                target.write_bytes(raw)
                rec["files"] += 1
                continue
            if Path(f["path"]).suffix.lower() in CODE_EXT:
                out, table, kept = scrub_code(text)
                rec["members_kept"] += len(kept)
                if table:
                    rec["code_files_scrubbed"].append(f["path"])
                left = code_clean(out)
            else:
                out, table = scrub(text)
                left = find_urls(out)
            if left:
                raise SystemExit(f"{c['case']}/{f['path']}: URL-like text left: {left[:3]}")
            rec["placeholders"] += len(table)
            target.write_text(out, encoding="utf-8")
            rec["files"] += 1
        manifest[c["case"]] = rec
    write_json(RUN / "skills.json", manifest)
    n = sum(r["placeholders"] for r in manifest.values())
    print(f"{len(manifest)} skill copies, {n} placeholders, "
          f"{sum(bool(r['code_files_scrubbed']) for r in manifest.values())} with a scrubbed "
          f"code file, {sum(len(r['withheld']) for r in manifest.values())} binary files withheld")


# ------------------------------------------------------------------ S and D
def _clean_prompt(system: str, user: str) -> dict:
    table: dict = {}
    system, _ = scrub(system, table)
    user, _ = scrub(user, table)
    assert_clean(system)
    assert_clean(user)
    return {"system": system, "user": user}


def arm_dir(arm: str, k: int) -> Path:
    return RUN / arm / f"r{k}"


def prepare(arm: str, k: int) -> None:
    out = arm_dir(arm, k)
    if (out / "frozen.json").exists():
        raise SystemExit(f"{out} is already frozen")
    method = "ce_rt" if arm == "s" else "direct"
    rts: dict = {}
    frozen_cases, jobs = [], []
    for c in cases():
        rt = rts.setdefault(c["runtime"], load_runtime(c["runtime"]))
        text, _ = scrub((SRC / c["id"] / "SKILL.md").read_text(encoding="utf-8"))
        system, user = (ce_runtime_messages(text, rt) if arm == "s"
                        else direct_messages(text, rt))
        rel = f"prompts/{method}/{c['case']}__s0.json"
        write_json(out / rel, _clean_prompt(system, user))
        frozen_cases.append({"id": c["case"], "skill": c["id"], "set": "real2",
                             "corpus": "real2/sources", "runtime": c["runtime"]})
        jobs.append({"case": c["case"], "arm": method, "sample": 0, "round": 1,
                     "prompt": rel, "output": f"outputs/{method}/{c['case']}__s0.txt",
                     "prompt_sha256": sha((out / rel).read_bytes())})
    impl = {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in
            [ROOT / "src/skillc/frontend/ce.py", ROOT / "src/skillc/frontend/prompts.py",
             ROOT / "src/skillc/frontend/runtime.py", ROOT / "src/skillc/checker.py",
             ROOT / "src/skillc/frontend/urlguard.py",
             *sorted((ROOT / "src/skillc/data/runtimes").glob("*.json")),
             ROOT / "scripts/benchmark_ce_runtime.py", Path(__file__)]}
    write_json(out / "frozen.json", {
        "created_utc": datetime.now(timezone.utc).isoformat(), "method": method,
        "repeat": k, "runtime": bcr.RUNTIME, "case_set": "real2", "prune": False,
        "cases": frozen_cases, "jobs": jobs, "implementation_sha256": impl})
    print(f"{len(jobs)} {arm} prompts in {out}")


def _reclean(out: Path) -> None:
    """A retry or repair prompt quotes the model's own reply: scrub it again."""
    frozen = json.loads((out / "frozen.json").read_text())
    for job in frozen["jobs"]:
        if job["round"] == 1:
            continue
        p = json.loads((out / job["prompt"]).read_text())
        write_json(out / job["prompt"], _clean_prompt(p["system"], p["user"]))
        job["prompt_sha256"] = sha((out / job["prompt"]).read_bytes())
    write_json(out / "frozen.json", frozen)


def retry(k: int) -> None:
    bcr.retry(arm_dir("s", k))
    _reclean(arm_dir("s", k))


def repair(k: int) -> None:
    bcr.repair(arm_dir("s", k))
    _reclean(arm_dir("s", k))


# ------------------------------------------------------------------- jobs
EXEC_NOTE = """
Rules added for this round (runs/20261031_real2/PLAN.md, amendment 1):
- The skill folder is a copy in which links, e-mail addresses and domain names were replaced
  by placeholders such as [url-1], [host-1] or [email-1]. A placeholder stands for something
  you cannot reach. Do not guess or look up the original.
- Do not use web search or web fetch tools, and do not open links. If the runtime grants
  package installation, run package managers in quiet mode (for example pip -q, npm --silent).
- Never print or write a URL, a domain name or an e-mail address into result.json; describe
  the resource in words instead.
"""


def exec_prompt(c: dict, work_root: Path) -> str:
    tpl = (RUN / f"executor_prompt_{c['runtime']}.txt").read_text(encoding="utf-8")
    text = (tpl.replace("{ID}", c["case"])
            .replace("{PATH}", str(RUN / "skills" / c["case"] / "SKILL.md"))
            .replace("{WORK}", str(work_root / c["case"])))
    return text.rstrip() + "\n" + EXEC_NOTE


def make_jobs(arm: str, k: int, rnd: int, only: list[str] | None,
              work_root: Path) -> None:
    rng = random.Random(f"{SEED}:{arm}:{k}:{rnd}")
    if arm == "exec":
        items = []
        for c in cases():
            if only and c["case"] not in only:
                continue
            rel = f"execution/prompts/{c['case']}.txt"
            (RUN / rel).parent.mkdir(parents=True, exist_ok=True)
            text = exec_prompt(c, work_root)
            assert_clean(text)
            (RUN / rel).write_text(text, encoding="utf-8")
            items.append({"job": f"exec:{c['case']}", "case": c["case"],
                          "prompt": str(RUN / rel),
                          "output": str(work_root / c["case"] / "result.json")})
        tag = "exec"
    else:
        out = arm_dir(arm, k)
        frozen = json.loads((out / "frozen.json").read_text())
        items = [{"job": f"{arm}{k}:{j['case']}:n{j['round']}", "case": j["case"],
                  "prompt": str(out / j["prompt"]), "output": str(out / j["output"])}
                 for j in frozen["jobs"] if j["round"] == rnd
                 and (not only or j["case"] in only)
                 and not (out / j["output"]).exists()]
        tag = f"{arm}_r{k}_n{rnd}"
    rng.shuffle(items)
    bdir = RUN / "batches"
    bdir.mkdir(parents=True, exist_ok=True)
    for i in range(0, len(items), BATCH):
        write_json(bdir / f"{tag}_{i // BATCH:02d}.json", items[i:i + BATCH])
    print(f"{len(items)} {tag} jobs in {math.ceil(len(items) / BATCH)} batches")


# ------------------------------------------------------------ execution truth
PERSONAL = [(re.compile(r"/home/[^/\s\"']+"), "/home/<user>"),
            (re.compile(r"/root\b"), "/<root>")]


def collect_exec(work_root: Path) -> None:
    out = RUN / "execution"
    out.mkdir(parents=True, exist_ok=True)
    got = 0
    for c in cases():
        p = work_root / c["case"] / "result.json"
        if not p.exists():
            continue
        text, _ = scrub(p.read_text(encoding="utf-8", errors="replace"))
        for rx, rep in PERSONAL:
            text = rx.sub(rep, text)
        (out / f"{c['case']}.json").write_text(text, encoding="utf-8")
        got += 1
    print(f"collected {got} executor reports")


def label(case: str, sensitivity: str = "main") -> tuple[str, str]:
    """(achieved | blocked | inconclusive, reason) under L2 and a sensitivity rule."""
    c = next(x for x in cases() if x["case"] == case)
    p = RUN / "execution" / f"{case}.json"
    try:
        r = extract_json_object(p.read_text(encoding="utf-8"))
        outcome, kind = r.get("outcome"), r.get("blocker_kind")
    except (OSError, ValueError, TypeError):
        return "inconclusive", "missing_or_malformed_result"
    if sensitivity == "no_violations":
        viol = RUN / "protocol_violations.txt"
        if viol.exists() and case in viol.read_text().split():
            return "inconclusive", "protocol_violation"
    if outcome == "achieved":
        if sensitivity == "strict":
            adj = RUN / "adjudication" / f"{case}.json"
            try:
                if extract_json_object(adj.read_text()).get("genuine") is False:
                    return "inconclusive", "simulated_success"
            except (OSError, ValueError, TypeError):
                return "inconclusive", "not_adjudicated"
        return "achieved", "achieved"
    blocked = set(L2_BLOCKED)
    if c["runtime"] == "offline-workstation":
        blocked.add("network_or_service_unavailable")
    if sensitivity == "physical":
        blocked.add("needs_human_or_physical")
    if outcome == "not_achieved" and kind in blocked:
        return "blocked", kind
    return "inconclusive", str(kind)


# ------------------------------------------------------------------ verdicts
def missing_outputs(arm: str, k: int) -> list[str]:
    out = arm_dir(arm, k)
    return [j["output"] for j in json.loads((out / "frozen.json").read_text())["jobs"]
            if not (out / j["output"]).exists()]


def mark_missing(arm: str, k: int) -> None:
    """After a failed job's one re-run: record the reply as missing (no verdict)."""
    out = arm_dir(arm, k)
    gone = missing_outputs(arm, k)
    for rel in gone:
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_text("(no reply: the sub-agent failed twice)\n", encoding="utf-8")
    with open(RUN / "missing.log", "a", encoding="utf-8") as f:
        for rel in gone:
            f.write(f"{datetime.now(timezone.utc).isoformat()} {arm}{k} {rel}\n")
    print(f"{len(gone)} missing replies recorded")


def s_verdicts(k: int) -> dict:
    out = arm_dir("s", k)
    bcr.score_all(out)                      # writes results.json and packs/
    return {r["case"]: (r.get("verdict") if r.get("verdict") in VERDICTS else "NONE")
            for r in json.loads((out / "results.json").read_text())}


def d_verdicts(k: int) -> dict:
    out = arm_dir("d", k)
    res = {}
    for job in json.loads((out / "frozen.json").read_text())["jobs"]:
        try:
            v = extract_json_object((out / job["output"]).read_text(encoding="utf-8"))["verdict"]
        except (OSError, ValueError, KeyError, TypeError):
            v = None
        res[job["case"]] = v if v in VERDICTS else "NONE"
    return res


def checker_times(k: int) -> dict:
    times = {}
    for p in sorted((arm_dir("s", k) / "packs" / "ce_rt").glob("*.json")):
        pack = json.loads(p.read_text())
        runs = []
        for _ in range(7):
            t0 = time.perf_counter()
            check(pack)
            runs.append(time.perf_counter() - t0)
        times[p.stem] = statistics.median(runs)
    return times


# ------------------------------------------------------------------ calls
def log_calls(transcripts: Path) -> None:
    """One line per sub-agent transcript: the job it ran (found by its prompt path),
    provider-reported usage summed over its turns, wall time, and the model."""
    jobs = {}
    for b in sorted((RUN / "batches").glob("*.json")):
        for j in json.loads(b.read_text()):
            jobs[j["prompt"]] = j
    seen = set()
    if (RUN / "calls.jsonl").exists():
        seen = {json.loads(line)["transcript"]
                for line in (RUN / "calls.jsonl").read_text().splitlines() if line}
    new = []
    for t in sorted(transcripts.rglob("agent-*.jsonl")):
        if str(t) in seen:
            continue
        rows = [json.loads(line) for line in t.read_text().splitlines() if line.strip()]
        first_user = next((json.dumps(r.get("message", {})) for r in rows
                           if r.get("type") == "user"), "")
        job = next((j for p, j in jobs.items() if p in first_user), None)
        if job is None:
            continue
        use = Counter()
        models = Counter()
        for r in rows:
            m = r.get("message") or {}
            if r.get("type") == "assistant" and isinstance(m.get("usage"), dict):
                for f in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                          "cache_creation_input_tokens"):
                    use[f] += int(m["usage"].get(f) or 0)
                models[m.get("model")] += 1
        stamps = [datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
                  for r in rows if r.get("timestamp")]
        new.append({"transcript": str(t), "job": job["job"], "case": job["case"],
                    **dict(use), "seconds": (max(stamps) - min(stamps)).total_seconds()
                    if stamps else None,
                    # which model served the call, as a short hash (no model names in the repo)
                    "model_sha8": sorted(hashlib.sha256(str(k).encode()).hexdigest()[:8]
                                         for k in models)})
    with open(RUN / "calls.jsonl", "a", encoding="utf-8") as f:
        for row in new:
            f.write(json.dumps(row) + "\n")
    print(f"{len(new)} calls logged")


_ENC = None


def bpe(text: str) -> int:
    """GPT-2 BPE token count, the proxy of runs/20260928_i2l."""
    global _ENC
    if _ENC is None:
        import tiktoken
        _ENC = tiktoken.get_encoding("gpt2")
    return len(_ENC.encode(text, disallowed_special=()))


# ------------------------------------------------------------------ audit
def audit() -> None:
    bad = []
    for p in sorted(RUN.rglob("prompts/**/*.json")):
        d = json.loads(p.read_text())
        if find_urls(d["system"]) or find_urls(d["user"]):
            bad.append(str(p))
    for p in sorted((RUN / "execution" / "prompts").glob("*.txt")):
        if find_urls(p.read_text()):
            bad.append(str(p))
    for p in sorted((RUN / "skills").rglob("*")):
        if p.is_file():
            try:
                text = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = p.read_bytes().decode("latin-1")
            hits = code_clean(text) if p.suffix.lower() in CODE_EXT else find_urls(text)
            if hits:
                bad.append(str(p))
    print("audit:", "clean" if not bad else f"{len(bad)} files with URL-like text: {bad[:5]}")
    if bad:
        raise SystemExit(1)


# ------------------------------------------------------------------ metrics
def rate(k: int, n: int) -> dict:
    return {"k": k, "n": n, "rate": round(k / n, 4) if n else None, "ci95": wilson(k, n)}


def arm_metrics(v: dict, lab: dict) -> dict:
    dec = [c for c in v if lab[c] in ("achieved", "blocked")]
    blk = [c for c in dec if lab[c] == "blocked"]
    ach = [c for c in dec if lab[c] == "achieved"]
    good = sum((v[c] == "IMPOSSIBLE") == (lab[c] == "blocked") and v[c] != "NONE" for c in dec)
    return {"accuracy": rate(good, len(dec)),
            "blocked_caught": rate(sum(v[c] == "IMPOSSIBLE" for c in blk), len(blk)),
            "working_refuted": rate(sum(v[c] == "IMPOSSIBLE" for c in ach), len(ach)),
            "no_verdict": rate(sum(v[c] == "NONE" for c in dec), len(dec))}


def fleiss(rows: list[list[str]], cats=("ACHIEVABLE", "IMPOSSIBLE", "NONE")) -> float | None:
    if not rows:
        return None
    n = len(rows[0])
    pj = Counter()
    pi = []
    for r in rows:
        cnt = Counter(r)
        pj.update(cnt)
        pi.append((sum(x * x for x in cnt.values()) - n) / (n * (n - 1)))
    pbar = sum(pi) / len(pi)
    pe = sum((pj[c] / (len(rows) * n)) ** 2 for c in cats)
    return round((pbar - pe) / (1 - pe), 4) if pe < 1 else None


def quart(xs: list[float]) -> dict:
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return {"n": 0}
    q = statistics.quantiles(xs, n=4) if len(xs) > 1 else [xs[0]] * 3
    return {"n": len(xs), "median": round(q[1], 4), "iqr": [round(q[0], 4), round(q[2], 4)]}


def score() -> None:
    ids = [c["case"] for c in cases()]
    labels = {s: {c: label(c, s) for c in ids}
              for s in ("main", "strict", "physical", "no_violations")}
    lab = {c: labels["main"][c][0] for c in ids}
    for arm in ("s", "d"):
        for k in REPEATS:
            if (arm_dir(arm, k) / "frozen.json").exists() and missing_outputs(arm, k):
                raise SystemExit(f"{arm}{k}: {len(missing_outputs(arm, k))} replies missing; "
                                 "re-run them once, then `mark-missing`")
    v = {arm: {k: (s_verdicts(k) if arm == "s" else d_verdicts(k)) for k in REPEATS
               if (arm_dir(arm, k) / "frozen.json").exists()} for arm in ("s", "d")}
    calls = [json.loads(x) for x in (RUN / "calls.jsonl").read_text().splitlines()
             if x] if (RUN / "calls.jsonl").exists() else []
    m: dict = {"labels": dict(Counter(lab.values())),
               "inconclusive_reasons": dict(Counter(r for c, (l_, r) in labels["main"].items()
                                                    if l_ == "inconclusive")),
               "sensitivity_labels": {s: dict(Counter(x[0] for x in labels[s].values()))
                                      for s in labels}}
    for arm, reps in v.items():
        am: dict = {}
        for k, vk in reps.items():
            am[f"r{k}"] = arm_metrics(vk, lab)
            am[f"r{k}"]["by_runtime"] = {
                rt: arm_metrics({c: vk[c] for c in vk if next(
                    x for x in cases() if x["case"] == c)["runtime"] == rt}, lab)
                for rt in ("developer-sandbox", "offline-workstation", "office-assistant")}
            am[f"r{k}"]["sensitivity"] = {
                s: arm_metrics(vk, {c: labels[s][c][0] for c in ids})
                for s in ("strict", "physical", "no_violations")}
        if reps:
            pooled = {f"{c}#{k}": vk[c] for k, vk in reps.items() for c in vk}
            am["pooled"] = arm_metrics(pooled, {f"{c}#{k}": lab[c] for k in reps for c in ids})
        if len(reps) == 3:
            rows = [[reps[k][c] for k in REPEATS] for c in ids]
            am["agreement"] = {"all_three_same": rate(sum(len(set(r)) == 1 for r in rows),
                                                      len(rows)),
                               "fleiss_kappa": fleiss(rows)}
        tok = {}
        for c in calls:
            if c["job"].startswith(arm):
                key = c["job"].split(":")[0] + ":" + c["case"]
                t = tok.setdefault(key, {"tokens": 0, "seconds": 0.0})
                t["tokens"] += sum(c.get(f, 0) for f in (
                    "input_tokens", "output_tokens", "cache_read_input_tokens",
                    "cache_creation_input_tokens"))
                t["seconds"] += c.get("seconds") or 0.0
        am["tokens_per_decision"] = quart([t["tokens"] for t in tok.values()])
        am["seconds_per_decision"] = quart([t["seconds"] for t in tok.values()])
        bp = []
        for k in reps:
            out = arm_dir(arm, k)
            per: Counter = Counter()
            for j in json.loads((out / "frozen.json").read_text())["jobs"]:
                if (out / j["output"]).exists():
                    p = json.loads((out / j["prompt"]).read_text())
                    per[j["case"]] += (bpe(p["system"]) + bpe(p["user"])
                                       + bpe((out / j["output"]).read_text(encoding="utf-8")))
            bp += list(per.values())
        am["bpe_tokens_per_decision"] = quart(bp)
        m[arm] = am
    if v["s"]:
        ct = {}
        for k in v["s"]:
            ct.update({f"{c}#{k}": t for c, t in checker_times(k).items()})
        xs = sorted(ct.values())
        m["checker_seconds"] = {"n": len(xs), "median": statistics.median(xs) if xs else None,
                                "p90": xs[int(0.9 * (len(xs) - 1))] if xs else None,
                                "max": xs[-1] if xs else None,
                                "cpus": __import__("os").cpu_count()}
        write_json(RUN / "checker_times.json", ct)
    if 1 in v["s"] and 1 in v["d"]:
        dec = [c for c in ids if lab[c] in ("achieved", "blocked")]
        ok = lambda vv, c: vv[c] != "NONE" and (vv[c] == "IMPOSSIBLE") == (lab[c] == "blocked")
        b = sum(ok(v["s"][1], c) and not ok(v["d"][1], c) for c in dec)
        w = sum(not ok(v["s"][1], c) and ok(v["d"][1], c) for c in dec)
        m["mcnemar_r1"] = {"s_only_correct": b, "d_only_correct": w, "p": mcnemar_exact(b, w)}
    if "pooled" in m.get("s", {}) and "pooled" in m.get("d", {}):
        s, d = m["s"], m["d"]
        acc = lambda a: a["pooled"]["accuracy"]["rate"] or 0
        m["criteria"] = {
            "C1_accuracy_within_5_points": acc(s) >= acc(d) - 0.05,
            "C2_no_more_working_refuted": s["pooled"]["working_refuted"]["k"]
            <= d["pooled"]["working_refuted"]["k"],
            "C3_agreement_at_least_D": (s.get("agreement", {}).get("all_three_same", {})
                                        .get("k", -1)
                                        >= d.get("agreement", {}).get("all_three_same", {})
                                        .get("k", 10**9)),
            "C4_median_tokens_at_most_3x": (s["tokens_per_decision"].get("median") or 0)
            <= 3 * (d["tokens_per_decision"].get("median") or 0)
            if d["tokens_per_decision"].get("n") else None}
    write_json(RUN / "metrics.json", m)
    print(json.dumps({k: m[k] for k in ("labels", "criteria") if k in m}, indent=1))


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("skills")
    p = sub.add_parser("prepare")
    p.add_argument("--arm", choices=("s", "d"), required=True)
    p.add_argument("--repeat", type=int, choices=REPEATS, required=True)
    for name in ("retry", "repair"):
        sub.add_parser(name).add_argument("--repeat", type=int, choices=REPEATS, required=True)
    j = sub.add_parser("jobs")
    j.add_argument("--arm", choices=("exec", "s", "d"), required=True)
    j.add_argument("--repeat", type=int, default=1)
    j.add_argument("--round", type=int, default=1)
    j.add_argument("--only", nargs="*")
    j.add_argument("--work", type=Path, default=Path("/tmp/real2_work"))
    sub.add_parser("collect-exec").add_argument("--work", type=Path, required=True)
    sub.add_parser("calls").add_argument("--transcripts", type=Path, required=True)
    mm = sub.add_parser("mark-missing")
    mm.add_argument("--arm", choices=("s", "d"), required=True)
    mm.add_argument("--repeat", type=int, choices=REPEATS, required=True)
    sub.add_parser("audit")
    sub.add_parser("score")
    a = ap.parse_args()
    if a.cmd == "skills":
        build_skills()
    elif a.cmd == "prepare":
        prepare(a.arm, a.repeat)
    elif a.cmd == "retry":
        retry(a.repeat)
    elif a.cmd == "repair":
        repair(a.repeat)
    elif a.cmd == "jobs":
        make_jobs(a.arm, a.repeat, a.round, a.only, a.work)
    elif a.cmd == "collect-exec":
        collect_exec(a.work)
    elif a.cmd == "calls":
        log_calls(a.transcripts)
    elif a.cmd == "mark-missing":
        mark_missing(a.arm, a.repeat)
    elif a.cmd == "audit":
        audit()
    else:
        score()


if __name__ == "__main__":
    main()

"""Screen the 719-source real-skill cohort on the three hosts of this PC, with no model.

    python scripts/demo_screen_real_skills.py [--cache DIR] [--output DIR] [--limit N]
                                              [--ids a,b] [--data-ref REF] [--quiet]

For every cohort skill whose text is on this PC (verified by sha256), and for each host of
`scripts/demo_hosts.py` (GitHub Copilot CLI, Microsoft Scout, Microsoft 365 Copilot), the
three no-model readings of `demo_hosts.nomodel` are computed: the bound checker, the
host-profile checker and the requirement reader.  Sequential, one skill at a time, no model
call, no server, no network.

Output (one folder per run, resumable with --output):
  screen.jsonl   one JSON line per skill: ids, hashes, verdicts, witness strings (requirement
                 names, bases and line numbers, never skill text), checks of each witness
                 against this PC, keyword categories, earlier truth, timings
  locate.json    where each cohort text was found, or why not
  summary.json   distributions, contradictions, weak cases, the ranking
  SHORTLIST.md   the ranked candidates

Skill texts are data: read, hashed and passed to skillc's deterministic readers; never
executed, installed or followed.  No skill text is written to the output.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import demo_hosts as dh  # noqa: E402
from skillc.env import scout as scout_env  # noqa: E402
from skillc.env.nl import intent_from_text  # noqa: E402

COHORT = ROOT / "runs" / "20261106_real_skills" / "cohort.json"
DEFAULT_CACHE = Path.home() / "skillc-data" / "real-skills-20261106"
DATA_REF = "origin/gc/data_train_test"
HOSTS = dh.HOSTS
SHORT = {"copilot-cli": "Copilot CLI", "scout": "Scout", "m365-copilot": "M365 Copilot"}

# ----------------------------------------------------------------------------- keywords
# Counted on the skill text; only the category names and counts are stored.
BUSINESS = {
    "m365_mail_calendar": r"\b(outlook|e-?mails?|inbox|calendar|meetings?|invites?|teams "
                          r"(chat|channel|message))\b",
    "m365_documents": r"(\.docx|\.xlsx|\.pptx|\b(sharepoint|onedrive|excel|powerpoint|word "
                      r"document|spreadsheets?|slide decks?)\b)",
    "github": r"\b(github|pull requests?|gh (pr|issue|repo|release|api)|git push)\b",
    "azure": r"\b(azure|az (login|account|group|webapp|deployment|storage)|bicep|entra)\b",
    "sales_crm": r"\b(salesforce|hubspot|crm|sales|prospects?|leads?|deals?|opportunit(y|ies))\b",
    "tickets": r"\b(jira|tickets?|zendesk|servicenow|linear issues?|support cases?)\b",
    "cloud_deploy": r"\b(deploy(s|ing|ment)?|vercel|netlify|cloudflare|aws|gcp|kubernetes|"
                    r"kubectl|terraform)\b",
}
MICROSOFT_GITHUB_AZURE = ("m365_mail_calendar", "m365_documents", "github", "azure")
OUTWARD = (r"\b(send(s|ing)?|post(s|ing)? (to|a|the|on|in)|publish(es|ing)?|delete(s|d)?|"
           r"deploy(s|ing)?|pay(s|ment|ments)?|git push|push(es)? to|merge(s|d)? (the|a|into)|"
           r"upload(s|ing)?|tweet|submit(s|ting)?|charge(s)?|refund(s)?)\b")

# ----------------------------------------------------------------------------- locate


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _git_show(ref: str) -> bytes | None:
    try:
        return subprocess.run(["git", "show", ref], cwd=ROOT, capture_output=True,
                              check=True).stdout
    except (subprocess.CalledProcessError, OSError):
        return None


def locate(case: dict, cache: Path, data_ref: str) -> tuple[bytes | None, dict]:
    """(raw bytes or None, how): the cohort text from the content-addressed cache, then
    the real2 copy in this clone, then the data branch; each candidate is sha256-checked."""
    tried = []
    bundle = cache / "bundles" / f"{case['id']}.json"
    if bundle.is_file():
        try:
            b = json.loads(bundle.read_text(encoding="utf-8"))
            entry = next((f for f in b["files"] if f["path"] == case["path_in_repo"]), None)
        except (OSError, ValueError, KeyError):
            entry = None
        if entry:
            obj = cache / "objects" / entry["git_blob"]
            if obj.is_file():
                raw = obj.read_bytes()
                if _sha(raw) == case["sha256"]:
                    return raw, {"where": "cache", "object": entry["git_blob"]}
                tried.append("cache: sha256 mismatch")
            else:
                tried.append("cache: object missing")
        else:
            tried.append("cache: no file entry in bundle")
    else:
        tried.append("cache: no bundle")
    local = ROOT / "benchmark" / "real2" / "sources" / case["id"] / "SKILL.md"
    if local.is_file():
        raw = local.read_bytes()
        if _sha(raw) == case["sha256"]:
            return raw, {"where": "benchmark/real2/sources"}
        tried.append("real2: sha256 mismatch")
    origin = case.get("origin", "")
    if ":" in origin and re.fullmatch(r"[0-9a-f]{40}", origin.split(":", 1)[0]):
        raw = _git_show(origin)
        if raw is not None and _sha(raw) == case["sha256"]:
            return raw, {"where": "git", "ref": origin.split(":", 1)[0][:12]}
        tried.append("git origin: missing or mismatch")
    corpus = origin if origin.startswith("ce_sources") else None
    if corpus:
        raw = _git_show(f"{data_ref}:benchmark/{corpus}/{case['id']}/SKILL.md")
        if raw is not None and _sha(raw) == case["sha256"]:
            return raw, {"where": "git", "ref": data_ref}
        tried.append("data branch: missing or mismatch")
    return None, {"where": None, "tried": tried}

# ----------------------------------------------------------------------------- earlier truth


def _verdict_of(label: str | None) -> str | None:
    return {"achieved": "ACHIEVABLE", "blocked": "IMPOSSIBLE", "not_achieved": "IMPOSSIBLE",
            "ACHIEVABLE": "ACHIEVABLE",
            "BLOCKED": "IMPOSSIBLE", "IMPOSSIBLE": "IMPOSSIBLE"}.get(label or "")


def _agree(truth: str | None, verdict: str | None) -> bool | None:
    t, v = _verdict_of(truth), verdict
    if t is None or v not in ("ACHIEVABLE", "IMPOSSIBLE"):
        return None
    return t == v


def _git_json(ref: str):
    raw = _git_show(ref)
    return json.loads(raw) if raw else None


def earlier_truth(data_ref: str, cohort: list[dict]) -> dict[str, list[dict]]:
    """skill id -> earlier measured outcomes with skillc's verdict on the same pair.
    Runtimes here are the benchmark runtimes, not the three hosts of this PC."""
    out: dict[str, list[dict]] = {}
    by_sha = {c["sha256"]: c["id"] for c in cohort}

    def add(sid, rec):
        out.setdefault(sid, []).append(rec)

    # real2 (300 pairs, three skillc repeats)
    p = ROOT / "runs" / "20261031_real2" / "case_outcomes.json"
    if p.is_file():
        for c in json.loads(p.read_text(encoding="utf-8")):
            vs = [v for v in (c.get("s") or {}).values() if v]
            maj = Counter(vs).most_common(1)[0][0] if vs else None
            lab = c["labels"]["main"]
            add(c["skill"], {"study": "real2", "runtime": c["runtime"], "truth": lab["label"],
                             "truth_reason": lab.get("reason"), "skillc": maj,
                             "skillc_repeats": vs, "agree": _agree(lab["label"], maj)})
    # claude_env (Claude Code cloud session; annotated truth), joined by sha256
    ce = ROOT / "benchmark" / "claude_env"
    if (ce / "cases.json").is_file():
        res = {r["case"]: r for r in json.loads((ce / "results" / "skillc.json").read_text(
            encoding="utf-8"))}
        for c in json.loads((ce / "cases.json").read_text(encoding="utf-8"))["cases"]:
            sid = by_sha.get(c["sha256"])
            tp = ce / "truth" / f"{c['case']}.json"
            if not sid or not tp.is_file():
                continue
            t = json.loads(tp.read_text(encoding="utf-8"))["verdict"]
            v = res.get(c["case"], {}).get("verdict")
            v = "IMPOSSIBLE" if v == "BLOCKED" else v
            add(sid, {"study": "claude_env", "runtime": "claude-code-cloud", "truth": t,
                      "skillc": v, "agree": _agree(t, v)})
    # historical studies on the data branch (execution outcomes and skillc verdicts)
    def outcomes(prefix: str) -> dict[str, dict]:
        try:
            names = subprocess.run(["git", "ls-tree", "--name-only", f"{data_ref}", prefix + "/"],
                                   cwd=ROOT, capture_output=True, text=True,
                                   check=True).stdout.split()
        except (subprocess.CalledProcessError, OSError):
            return {}
        got = {}
        for n in names:
            d = _git_json(f"{data_ref}:{n}")
            if d:
                got[Path(n).stem] = d
        return got

    for study, base, results_file in (("div", "runs/20260928_div", "div_ce_rt/results.json"),
                                      ("gr", "runs/20261001_gr", "gr_ce_rt/results.json")):
        ex = outcomes(f"{base}/execution")
        adj = _git_json(f"{data_ref}:{base}/adjudication.json") or {}
        verdicts = {r["case"]: r.get("verdict")
                    for r in _git_json(f"{data_ref}:{base}/{results_file}") or []}
        for case, e in ex.items():
            sid, _, rt = case.partition("@")
            v = verdicts.get(case)
            add(sid, {"study": study, "runtime": rt, "truth": e.get("outcome"),
                      "truth_reason": e.get("blocker_kind"),
                      "adjudication": (adj.get(case) or {}).get("verdict"),
                      "skillc": v, "agree": _agree(e.get("outcome"), v)})
    comp = _git_json(f"{data_ref}:runs/20260927_ext/comparison.json") or {}
    for sid, c in (comp.get("per_case") or {}).items():
        add(sid, {"study": "ext", "runtime": "developer-sandbox", "truth": c.get("label"),
                  "truth_reason": c.get("blocker_kind"), "skillc": c.get("P2g"),
                  "agree": _agree(c.get("label"), c.get("P2g"))})
    jb = {r["case"]: r.get("verdict")
          for r in _git_json(f"{data_ref}:runs/20260928_i2l/jb/results.json") or []}
    for study, f in (("i2l-heldout", "runs/20260926_heldout_execution.json"),
                     ("i2l-fresh", "runs/20260926_tpl/execution.json")):
        for sid, e in (_git_json(f"{data_ref}:{f}") or {}).items():
            v = jb.get(sid)
            add(sid, {"study": study, "runtime": "developer-sandbox", "truth": e.get("outcome"),
                      "truth_reason": e.get("blocker_kind"), "skillc": v,
                      "agree": _agree(e.get("outcome"), v)})
    return out

# ----------------------------------------------------------------------------- PC checks


def _parse_witness(line: str) -> dict:
    """`kind:name: basis; evidence line 3, line 9` -> parts (the private witness form)."""
    head, _, ev = line.partition("; evidence ")
    req, _, basis = head.partition(": ")
    return {"requirement": req, "basis": basis,
            "lines": [int(n) for n in re.findall(r"line (\d+)", ev)]}


def pc_check(req: str, host: dict) -> dict:
    """Whether a reader witness is true for this PC, as far as can be checked without a
    model or the network.  Credential variables are checked by name only (never read)."""
    kind, _, name = req.partition(":")
    tools = {t["name"].lower() for t in host["agent_tools"]}
    shell = bool(host["shell_tools"])
    if kind == "program":
        prog = name.split()[0] if name else name
        if not shell:
            return {"check": "true", "how": "the host has no shell tool to run any program"}
        on_path = shutil.which(prog) is not None
        return ({"check": "false", "how": f"{prog} is on PATH of this PC"} if on_path else
                {"check": "true", "how": f"{prog} is not on PATH of this PC"})
    if kind == "credential":
        present = name in os.environ
        return ({"check": "false", "how": "the variable is set in this environment"} if present
                else {"check": "true", "how": "the variable is not set in this environment"})
    if kind == "tool":
        names = [w.lower() for w in re.split(r"[\s,]+", name) if w]
        miss = [w for w in names if w not in tools]
        return ({"check": "true", "how": "not among the host's tool names: " + ", ".join(miss)}
                if miss else {"check": "false", "how": "the host has these tool names"})
    if kind == "platform":
        n = name.lower()
        if any(w in n for w in ("mac", "darwin", "ios", "xcode", "linux")):
            return {"check": "true", "how": f"this PC runs {sys.platform}"}
        return {"check": "not checked", "how": "platform name not judged"}
    if kind == "mcp":
        hit = [t for t in tools if name.lower().replace(" ", "_") in t]
        return ({"check": "false", "how": "a host tool matches the name"} if hit else
                {"check": "true", "how": "no host tool or server matches the name"})
    if kind == "account" and "github" in name.lower():
        signed = bool(host["observed"].get("signed_in", {}).get("gh"))
        return ({"check": "false", "how": "the GitHub CLI is signed in on this PC"} if signed
                else {"check": "plausible", "how": "no GitHub CLI sign-in seen for this host"})
    if kind == "account":
        return {"check": "plausible", "how": "no account of this kind is configured for the "
                                             "host (not verifiable without signing in)"}
    if kind == "egress":
        return {"check": "not checked", "how": "network reachability is not tested"}
    return {"check": "not checked", "how": f"no check for kind {kind}"}

# ----------------------------------------------------------------------------- one skill


def host_verdict(nm: dict) -> str:
    """IMP: the reader or the host-profile checker refutes with a named missing item;
    ACH: both agree it is achievable; WEAK otherwise."""
    rd, hp = nm["reader"], nm["checker_host_profile"]
    if rd["verdict"] == "IMPOSSIBLE" or (hp.get("verdict") == "IMPOSSIBLE" and hp.get("missing")):
        return "IMP"
    if rd["verdict"] == "ACHIEVABLE" and hp.get("verdict") == "ACHIEVABLE":
        return "ACH"
    return "WEAK"


def screen_one(case: dict, text: str, hosts: dict, earlier: list[dict]) -> dict:
    t0 = time.perf_counter()
    intent = intent_from_text(text)
    reqs = list(intent.get("goal") or []) + list(intent.get("optional") or [])
    rec = {"id": case["id"], "sha256": case["sha256"], "repository": case["repository"],
           "path_in_repo": case["path_in_repo"], "lines": len(text.splitlines()),
           "bytes": len(text.encode("utf-8")),
           "reader_requirements": {"hard": len(intent.get("goal") or []),
                                   "optional": len(intent.get("optional") or []),
                                   "kinds": dict(Counter(r.split(":", 1)[0] for r in reqs))},
           "keywords": {k: len(re.findall(rx, text, re.I)) for k, rx in BUSINESS.items()},
           "outward_hits": len(re.findall(OUTWARD, text, re.I)),
           "earlier": earlier, "hosts": {}}
    rec["keywords"] = {k: v for k, v in rec["keywords"].items() if v}
    with tempfile.TemporaryDirectory(prefix="skillc-screen-") as tmp:
        tmp = Path(tmp)
        compiled = dh.compile_skill(text, tmp)
        rec["compile_ms"] = compiled["ms"]
        for hid, h in hosts.items():
            nm = dh.nomodel(compiled, text, h, tmp, private=True)
            ch, hp, rd = nm["checker"], nm["checker_host_profile"], nm["reader"]
            wit = []
            for line in rd["witness"]:
                w = _parse_witness(line)
                w.update(pc_check(w["requirement"], h))
                wit.append(w)
            rec["hosts"][hid] = {
                "verdict": host_verdict(nm),
                "bound": {"verdict": ch.get("verdict"), "reason": ch.get("reason"),
                          "missing": ch.get("missing", []), "undeclared": ch.get("undeclared", []),
                          "ms": ch.get("ms"), "error": (ch.get("error") or None) and
                          str(ch["error"])[:160]},
                "profile": {"verdict": hp.get("verdict"), "reason": hp.get("reason"),
                            "missing": hp.get("missing", []), "ms": hp.get("ms"),
                            "error": (hp.get("error") or None) and str(hp["error"])[:160]},
                "reader": {"verdict": rd["verdict"], "witness": rd["witness"],
                           "witness_checked": wit, "unknown": rd["unknown"], "ms": rd["ms"]},
            }
    rec["ms"] = dh._ms(t0)
    return rec

# ----------------------------------------------------------------------------- ranking


def _truth_note(earlier: list[dict]) -> dict:
    decided = [e for e in earlier if e["agree"] is not None]
    return {"pairs": len(earlier), "decided": len(decided),
            "agree": sum(e["agree"] for e in decided),
            "disagree": sum(not e["agree"] for e in decided)}


# Tool names from a skill's frontmatter tool list (Claude Code's own tool names): on a host
# without them the witness is true but generic ("no file or shell tools").
AGENT_TOOL_NAMES = {"read", "write", "edit", "multiedit", "grep", "glob", "bash", "task",
                    "todowrite", "webfetch", "websearch", "agent", "askuserquestion", "ls",
                    "notebookedit", "skill"}
# Names of other agent products a checker took for tools: a misread, not a requirement.
PRODUCT_NAMES = {"claude", "claude-code", "cursor", "codex", "codex-cli", "gemini", "gemini-cli",
                 "antigravity", "copilot", "windsurf", "opencode", "env", "aider"}
# Strength of one witness: 3 a named service, account, credential, connector or platform;
# 2 a named program absent from PATH on a host with a shell; 1 generic (no shell, no file
# tools, a software route); 0 a misread.
STRENGTH_WORD = {3: "named", 2: "program", 1: "generic", 0: "misread"}


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def witness_strength(w: dict, host: dict | None = None) -> int:
    kind, _, name = w["requirement"].partition(":")
    if w["check"] == "false":
        return 0
    if kind in ("credential", "account", "mcp", "platform"):
        return 3
    if kind == "program":
        return 1 if w["how"].startswith("the host has no shell") else 2
    if kind == "tool":
        words = [_norm(x) for x in re.split(r"[\s,]+", name) if x]
        return 0 if words and all(x in {_norm(p) for p in PRODUCT_NAMES} for x in words) else 1
    return 1


def checker_witness(h: str, miss: list[str], host_tools: set[str]) -> tuple[int, dict]:
    """Strength and description of the host-profile checker's missing tool names."""
    names = [m.lower() for m in miss]
    product = [m for m in names if m in PRODUCT_NAMES]
    renamed = [m for m in names if _norm(m) in host_tools]     # web_fetch vs webfetch
    generic = [m for m in names if m in AGENT_TOOL_NAMES or m in dh.SHELL_NAMES
               or " " in m]
    specific = [m for m in names if m not in product + renamed + generic]
    if specific:
        s, check, how = 3, "true", "not among the host's tool names"
    elif generic and not renamed:
        s, check, how = 1, "generic", "only file, shell or agent tool names are missing"
    else:
        s, check, how = 0, "false", ("a host tool has this name in another spelling"
                                     if renamed else "names of other agent products, not tools")
    return s, {"requirement": "tool:" + ", ".join((specific or generic or names)[:3]),
               "basis": "host-profile checker", "lines": [], "check": check, "how": how}


def score(rec: dict, host_tools: dict[str, set[str]]) -> dict:
    hv = {h: rec["hosts"][h]["verdict"] for h in HOSTS}
    # the best witness on each IMP host
    best_by_host: dict[str, tuple[int, dict]] = {}
    for h in HOSTS:
        if hv[h] != "IMP":
            continue
        cands = [(witness_strength(w), w) for w in rec["hosts"][h]["reader"]["witness_checked"]]
        miss = rec["hosts"][h]["profile"]["missing"]
        if miss:
            cands.append(checker_witness(h, miss, host_tools[h]))
        if cands:
            best_by_host[h] = max(cands, key=lambda c: c[0])
    strength = max((s for s, _ in best_by_host.values()), default=-1)
    best_h = next((h for h in HOSTS if h in best_by_host and best_by_host[h][0] == strength),
                  None)
    ach = [h for h in HOSTS if hv[h] == "ACH"]
    real_imp = [h for h, (s, _) in best_by_host.items() if s >= 1]
    diverge = 3 if ach and real_imp else 1 if real_imp and len(set(hv.values())) > 1 else 0
    kw = rec["keywords"]
    biz = sum(1 for k in kw if k in BUSINESS) + 2 * sum(1 for k in kw
                                                       if k in MICROSOFT_GITHUB_AZURE)
    tn = _truth_note(rec["earlier"])
    truth_pts = 0 if not tn["decided"] else (1 if tn["disagree"] == 0 else -1)
    outward = rec["outward_hits"] > 0
    total = (60 * diverge + 40 * max(strength, 0) + 3 * min(biz, 8) + 6 * truth_pts
             + (5 if outward else 0))
    w = best_by_host[best_h][1] if best_h else None
    return {"host_verdicts": hv, "diverge": diverge,
            "witness_strength": STRENGTH_WORD.get(strength, "none"),
            "witness": w and {"host": best_h, **{k: w[k] for k in
                                                ("requirement", "basis", "lines", "check", "how")}},
            "imp_witness_strength": {h: STRENGTH_WORD[s] for h, (s, _) in best_by_host.items()},
            "business": biz, "keywords": sorted(kw), "truth": tn, "outward": outward,
            "score": total}


def summarize(records: list[dict], locate_info: dict, seconds: float,
              host_tools: dict[str, set[str]]) -> dict:
    dist = {h: {r: Counter() for r in ("bound", "profile", "reader", "combined")}
            for h in HOSTS}
    weak_all, contradictions, ranked = [], [], []
    for rec in records:
        for h in HOSTS:
            c = rec["hosts"][h]
            dist[h]["bound"][str(c["bound"]["verdict"])] += 1
            dist[h]["profile"][str(c["profile"]["verdict"])] += 1
            dist[h]["reader"][str(c["reader"]["verdict"])] += 1
            dist[h]["combined"][c["verdict"]] += 1
            rd, hp = c["reader"]["verdict"], c["profile"]["verdict"]
            if (rd == "IMPOSSIBLE" and hp == "ACHIEVABLE") or (
                    rd == "ACHIEVABLE" and hp == "IMPOSSIBLE" and c["profile"]["missing"]):
                contradictions.append({"id": rec["id"], "host": h, "reader": rd, "profile": hp,
                                       "profile_missing": c["profile"]["missing"][:4],
                                       "reader_witness": c["reader"]["witness"][:2]})
        if all(rec["hosts"][h]["verdict"] == "WEAK" for h in HOSTS):
            weak_all.append(rec["id"])
        ranked.append({"id": rec["id"], **score(rec, host_tools)})
    ranked.sort(key=lambda r: (-r["score"], r["id"]))
    combos = Counter("/".join(r["host_verdicts"][h] for h in HOSTS) for r in ranked)
    return {
        "schema": "skillc.hosts-screen/1", "created": dh._now(), "seconds": round(seconds, 1),
        "coverage": {"cohort": len(locate_info), "found": sum(1 for v in locate_info.values()
                                                             if v.get("where")),
                     "not_found": sorted(k for k, v in locate_info.items() if not v.get("where")),
                     "by_place": dict(Counter(v.get("where") for v in locate_info.values())),
                     "screened": len(records)},
        "distribution": {h: {r: dict(c) for r, c in v.items()} for h, v in dist.items()},
        "combined_patterns_copilot_scout_m365": dict(combos.most_common()),
        "weak_all_hosts": {"count": len(weak_all), "rule": "WEAK on every host: no refutation "
                           "with a named item, and the checkers did not confirm ACHIEVABLE "
                           "(UNKNOWN or error)", "ids": weak_all},
        "reader_only_deliverable": sum(
            1 for r in records if set(r["reader_requirements"]["kinds"]) <= {"deliverable"}),
        "witness_strength_on_imp_hosts": {h: dict(Counter(
            r["imp_witness_strength"].get(h) for r in ranked if h in r["imp_witness_strength"]))
            for h in HOSTS},
        "contradictions": {"count": len(contradictions), "items": contradictions},
        "diverging": sum(1 for r in ranked if r["diverge"] == 3),
        "diverging_named_witness": sum(1 for r in ranked if r["diverge"] == 3
                                       and r["witness_strength"] in ("named", "program")),
        "ranked": ranked,
    }


def shortlist_md(summary: dict, records: dict, top: int = 25) -> str:
    lines = [f"# Real-skill screen on three hosts ({summary['created']})", "",
             f"No model. {summary['coverage']['screened']} skills screened of "
             f"{summary['coverage']['cohort']} cohort ids "
             f"({len(summary['coverage']['not_found'])} texts not found). "
             f"Screen time {summary['seconds']} s.", "",
             "Combined host verdict: IMP when the reader or the host-profile checker names a "
             "missing item; ACH when both say achievable; WEAK otherwise.", "",
             "| # | cohort id | Copilot CLI | Scout | M365 Copilot | witness (host: requirement; "
             "lines; PC check) | strength | earlier truth (agree/decided) | outward | score |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(summary["ranked"][:top], 1):
        w = r["witness"]
        wt = (f"{SHORT[w['host']]}: {w['requirement']}; lines {','.join(map(str, w['lines'][:4]))}"
              f"; {w['check']}" if w else "")
        tn = r["truth"]
        lines.append(f"| {i} | {r['id']} | {r['host_verdicts']['copilot-cli']} | "
                     f"{r['host_verdicts']['scout']} | {r['host_verdicts']['m365-copilot']} | "
                     f"{wt} | {r['witness_strength']} | {tn['agree']}/{tn['decided']} | "
                     f"{'yes' if r['outward'] else 'no'} | {r['score']} |")
    lines += ["", f"Weak on all hosts: {summary['weak_all_hosts']['count']}. "
              f"Reader/checker contradictions (host cells): {summary['contradictions']['count']}.",
              "", "Earlier truth comes from benchmark runtimes (developer-sandbox, "
              "office-assistant, offline-workstation, Claude Code cloud), not from these hosts.",
              ""]
    return "\n".join(lines)

# ----------------------------------------------------------------------------- main


def build_hosts() -> dict:
    from skillc.env.copilot import copilot_home as default_copilot_home
    copilot_home = default_copilot_home()
    return {"copilot-cli": dh.copilot_host(copilot_home, None),
            "scout": dh.scout_host(scout_env.scout_home(), copilot_home, None),
            "m365-copilot": dh.m365_host(None)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    ap.add_argument("--output", type=Path)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--ids", help="comma-separated cohort ids")
    ap.add_argument("--data-ref", default=DATA_REF)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    say = (lambda *a: None) if args.quiet else (lambda *a: print(*a, flush=True))

    started = time.perf_counter()
    cohort = json.loads(COHORT.read_text(encoding="utf-8"))["cases"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    out = args.output or ROOT / "runs" / f"{stamp}_hosts_screen"
    out.mkdir(parents=True, exist_ok=True)
    say(f"screen -> {out}")

    hosts = build_hosts()
    for hid, h in hosts.items():
        dh._write_json(out / "env" / f"{hid}.manifest.json", h["manifest"])
        say(dh.host_line(h))

    loc_file = out / "locate.json"
    if loc_file.is_file():
        locate_info = json.loads(loc_file.read_text(encoding="utf-8"))
    else:
        locate_info = {c["id"]: locate(c, args.cache, args.data_ref)[1] for c in cohort}
        dh._write_json(loc_file, locate_info)
    say(f"located {sum(1 for v in locate_info.values() if v.get('where'))} of {len(cohort)}")

    tr_file = out / "earlier_truth.json"
    if tr_file.is_file():
        truth = json.loads(tr_file.read_text(encoding="utf-8"))
    else:
        truth = earlier_truth(args.data_ref, cohort)
        dh._write_json(tr_file, truth)
    say(f"earlier truth for {sum(1 for c in cohort if c['id'] in truth)} cohort ids")

    jl = out / "screen.jsonl"
    done: dict[str, dict] = {}
    if jl.is_file():
        for line in jl.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
                done[r["id"]] = r
            except (ValueError, KeyError):
                continue          # a line cut by an interruption is screened again
    wanted = cohort
    if args.ids:
        keep = {s.strip() for s in args.ids.split(",")}
        wanted = [c for c in cohort if c["id"] in keep]
    if args.limit:
        wanted = wanted[:args.limit]
    prior_s = float((json.loads((out / "summary.json").read_text(encoding="utf-8"))
                     .get("seconds_screen", 0)) if (out / "summary.json").is_file() else 0)
    screen_s = 0.0
    with jl.open("a", encoding="utf-8") as fh:
        for n, case in enumerate(wanted, 1):
            if case["id"] in done or not locate_info.get(case["id"], {}).get("where"):
                continue
            raw, _how = locate(case, args.cache, args.data_ref)
            if raw is None:
                continue
            text = raw.decode("utf-8", errors="replace")
            t0 = time.perf_counter()
            try:
                rec = screen_one(case, text, hosts, truth.get(case["id"], []))
            except Exception as e:  # noqa: BLE001 - one bad text must not stop the screen
                rec = {"id": case["id"], "sha256": case["sha256"],
                       "error": f"{type(e).__name__}: {str(e)[:200]}"}
            screen_s += time.perf_counter() - t0
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            done[case["id"]] = rec
            del text, raw
            if n % 25 == 0:
                gc.collect()
            if "hosts" in rec:
                say(f"{n:4d} {case['id'][:60]:60s} "
                    + " ".join(f"{SHORT[h]}={rec['hosts'][h]['verdict']}" for h in HOSTS)
                    + f" {rec['ms'] / 1000:.1f}s")
            else:
                say(f"{n:4d} {case['id'][:60]:60s} error {rec['error'][:80]}")

    records = [r for r in done.values() if "hosts" in r]
    host_tools = {hid: {_norm(t["name"]) for t in h["agent_tools"]}
                  | {_norm(t) for t in h["manifest"]["tools"]} for hid, h in hosts.items()}
    summary = summarize(records, locate_info, prior_s + screen_s, host_tools)
    summary["seconds_screen"] = round(prior_s + screen_s, 1)
    summary["seconds_wall_this_invocation"] = round(time.perf_counter() - started, 1)
    summary["errors"] = sorted(r["id"] for r in done.values() if "error" in r)
    dh._write_json(out / "summary.json", summary)
    (out / "SHORTLIST.md").write_text(shortlist_md(summary, done), encoding="utf-8")
    say(f"wrote {jl}, summary.json, SHORTLIST.md; screen {summary['seconds_screen']} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

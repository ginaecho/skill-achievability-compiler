#!/usr/bin/env python3
"""Static security scan of a skill corpus.  READS ONLY -- nothing is executed.

Skill documents are instructions an agent will follow with real tools, so a
corpus of third-party skills is an untrusted input to any experiment that
loads them.  This scanner reports, per file, evidence in five families:

  injection      text that impersonates the harness or tries to redirect the
                 agent (fake system/assistant turns, "ignore previous
                 instructions", instructions about commit attribution)
  exfiltration   sending local secrets or files off the machine
  destructive    irreversible local damage (rm -rf, force push, history
                 rewrite, disk writes)
  remote_code    fetching code and running it in one step (curl | sh, eval of
                 downloaded text, pip/npm install from a URL)
  obfuscation    content that hides its meaning from a reader (long base64
                 blobs, zero-width or bidi control characters, HTML comments
                 carrying instructions)

Every hit is reported with file, line and the matched text so a human can
judge it.  Severity is a triage aid, not a verdict.
"""
from __future__ import annotations
import argparse, json, re, sys, unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RULES = [
    # (family, severity, name, regex)
    ("injection", "high", "fake-harness-turn", r"<\s*/?\s*(system-reminder|system_reminder|antml:|function_results|human>|assistant>)"),
    ("injection", "high", "ignore-previous", r"\bignore\s+(all\s+)?(previous|prior|earlier|above)\s+(instructions|prompts|rules|context)"),
    ("injection", "high", "override-attribution", r"(co-authored-by|commit\s+message|attribution)[^\n]{0,80}(must|always|instead|replace|end\s+with)"),
    ("injection", "medium", "role-reassignment", r"^\s*(system|assistant)\s*:\s*you\s+(are|must)\b"),
    ("injection", "medium", "disclose-secrets", r"\b(print|reveal|show|output|repeat)\b[^\n]{0,40}\b(system\s+prompt|your\s+instructions|api[_\s-]?key|secret)"),
    ("injection", "medium", "hidden-html-instruction", r"<!--[^>]{0,400}?\b(ignore|instead|you must|do not tell|secretly)\b"),
    ("exfiltration", "high", "post-env-secret", r"curl[^\n]{0,200}(-d|--data|-F)[^\n]{0,200}\$\{?(ANTHROPIC_API_KEY|OPENAI_API_KEY|AWS_SECRET|GITHUB_TOKEN|GH_TOKEN|API_KEY|SECRET|PASSWORD)"),
    ("exfiltration", "high", "read-credentials", r"(cat|cp|tar|zip|base64)\s+[^\n]{0,80}(\.ssh/id_|\.aws/credentials|\.netrc|\.env\b|id_rsa|credentials\.json)"),
    ("exfiltration", "medium", "env-dump-to-network", r"(env|printenv)\s*\|[^\n]{0,80}(curl|wget|nc\b|ncat)"),
    ("destructive", "high", "rm-rf-root", r"rm\s+-[rfRF]{1,3}\s+(/|~|\$HOME|/\*|\.\s*$)"),
    ("destructive", "medium", "rm-rf", r"\brm\s+-[rfRF]{2,3}\b"),
    ("destructive", "high", "force-push", r"git\s+push[^\n]{0,60}(--force\b|-f\b)"),
    ("destructive", "medium", "history-rewrite", r"git\s+(reset\s+--hard|filter-branch|rebase\s+-i|clean\s+-[xfd]{2,})"),
    ("destructive", "high", "disk-write", r"\b(mkfs|dd\s+if=[^\n]{0,40}of=/dev/|shred\s+-)"),
    ("destructive", "medium", "chmod-777", r"chmod\s+(-R\s+)?777\b"),
    ("remote_code", "high", "curl-pipe-shell", r"(curl|wget)[^\n|]{0,200}\|\s*(sudo\s+)?(ba)?sh\b"),
    ("remote_code", "high", "eval-download", r"eval\s*\(?\s*[\"$`]?\s*(curl|wget|requests\.get|urlopen)"),
    ("remote_code", "medium", "pip-install-url", r"pip\s+install[^\n]{0,120}(https?://|git\+)"),
    ("remote_code", "medium", "npm-install-url", r"npm\s+(i|install)[^\n]{0,120}(https?://|github:)"),
    ("obfuscation", "medium", "long-base64", r"[A-Za-z0-9+/]{200,}={0,2}"),
    # the agent's own configuration: a skill that edits the harness changes
    # what every later skill is allowed to do
    ("self_config", "high", "edit-agent-config", r"(~|\$HOME)?/?\.(claude|cursor|codex|aider)/(settings|config|hooks)[^\n]{0,40}(write|edit|append|add|modify|>>|>)"),
    ("self_config", "high", "install-hook", r"\b(hooks?)\b[^\n]{0,60}\b(PreToolUse|PostToolUse|SessionStart|Stop)\b"),
    ("self_config", "medium", "widen-permissions", r"(allowedTools|permissions|dangerously-skip-permissions|bypassPermissions|--yes\b|--force\b)[^\n]{0,60}(add|set|append|always)"),
    ("self_config", "high", "write-outside-workdir", r"(>|>>|tee|cp|mv)\s+(~|\$HOME|/etc/|/usr/|/root/)"),
]
COMPILED = [(f, s, n, re.compile(p, re.I | re.M)) for f, s, n, p in RULES]
ZERO_WIDTH = {"​", "‌", "‍", "⁠", "﻿"}
BIDI = {"‪", "‫", "‬", "‭", "‮", "⁦", "⁧", "⁨", "⁩"}
TAGS = range(0xE0000, 0xE0080)          # unicode tag block: invisible text


def scan_text(text: str) -> list[dict]:
    hits = []
    for family, sev, name, rx in COMPILED:
        for m in rx.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            frag = m.group(0)
            hits.append({"family": family, "severity": sev, "rule": name, "line": line,
                         "match": (frag[:160] + "...") if len(frag) > 160 else frag})
    # invisible characters
    for i, ch in enumerate(text):
        o = ord(ch)
        if ch in ZERO_WIDTH or ch in BIDI or o in TAGS:
            line = text.count("\n", 0, i) + 1
            hits.append({"family": "obfuscation", "severity": "high" if (ch in BIDI or o in TAGS) else "medium",
                         "rule": "invisible-character", "line": line,
                         "match": f"U+{o:04X} {unicodedata.name(ch, 'unknown')}"})
            break                                    # one report per file is enough
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", default=["real-skills", "real-skills-ext"])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    files = []
    for p in args.paths:
        root = ROOT / p
        files += sorted(root.rglob("SKILL.md")) if root.is_dir() else [root]
    report, counts = [], Counter()
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except Exception as e:                                        # noqa: BLE001
            report.append({"path": str(f.relative_to(ROOT)), "error": str(e)}); continue
        hits = scan_text(text)
        if hits:
            report.append({"path": str(f.relative_to(ROOT)), "hits": hits})
            for h in hits:
                counts[(h["family"], h["severity"], h["rule"])] += 1
    out = {"files_scanned": len(files), "files_with_hits": len(report),
           "by_rule": {f"{k[0]}/{k[1]}/{k[2]}": v for k, v in sorted(counts.items(), key=lambda x: -x[1])},
           "findings": report}
    if args.out:
        (ROOT / args.out).write_text(json.dumps(out, indent=1))
    if args.json:
        print(json.dumps(out, indent=1))
    else:
        print(f"scanned {len(files)} files; {len(report)} with at least one hit")
        for k, v in out["by_rule"].items():
            print(f"  {v:4d}  {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

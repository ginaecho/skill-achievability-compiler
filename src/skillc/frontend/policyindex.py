"""Policy index: a lookup table from tool/service/program names to what they require.

Unlike the tool-policy library (`toolpolicy.py`), which pattern-matches skill text and
turns matches into obligations, the index is only *looked up*: for every term the
deterministic extractor finds in a skill, it returns what past execution evidence says
the term requires (a requirement class, how often it was core, how often it blocked),
and flags terms it has never seen. The model reads these as reference facts; nothing in
the index decides a verdict.

Requirement classes (intrinsic to the term, independent of any runtime):
  none                      ordinary text or a capability every runtime has
  local_program             a program/library that runs locally (installable or bundled)
  network_access            needs the public internet (web pages, public APIs, registries)
  code_execution            needs to run code or shell commands
  binary_output             produces binary files (xlsx, docx, pdf, images, audio, video)
  account_or_credential     needs an account, login, API key or paid subscription
  os_or_hardware            needs a specific OS, GUI toolchain, GPU or physical device
  agent_spawn               needs to launch sub-agents or parallel agent sessions
  external_write            writes to or publishes on an external service
  human_or_physical         needs a human decision or physical action
  unavailable_program       a program that is not publicly obtainable (internal, unpublished)

The index grows by adding labelled mentions (`add`); it is a plain JSON file.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["CLASSES", "extract_terms", "norm", "PolicyIndex", "Mention"]

CLASSES = ("none", "local_program", "network_access", "code_execution", "binary_output",
           "account_or_credential", "os_or_hardware", "agent_spawn", "external_write",
           "human_or_physical", "unavailable_program")

_SHELL_LANGS = {"", "bash", "sh", "shell", "console", "zsh", "powershell", "ps1", "cmd"}
_STOP = {"the", "a", "an", "and", "or", "if", "then", "cd", "echo", "export", "set", "for",
         "do", "done", "true", "false", "null", "none", "yes", "no", "sudo", "cat", "ls",
         "mkdir", "cp", "mv", "rm", "grep", "sed", "awk", "head", "tail", "sort", "cut",
         "wc", "tee", "xargs", "find", "chmod", "touch", "source", "env", "which", "test"}
_PRODUCT = re.compile(r"\b([A-Z][A-Za-z0-9.+-]*(?:\s[A-Z][A-Za-z0-9.+-]*){0,2})\s"
                      r"(API|CLI|SDK|account|app|App|Studio|Cloud|MCP|server|workspace|"
                      r"portal|console|subscription|token|key)\b")
_MCP = re.compile(r"\bmcp__([A-Za-z0-9-]+)__")
_FENCE = re.compile(r"^```\s*([A-Za-z0-9_+-]*)\s*$")
_IDENT = re.compile(r"^[A-Za-z][A-Za-z0-9_.+-]{1,40}$")


def norm(term: str) -> str:
    t = term.strip().strip("`'\".,:;()[]").lower()
    t = re.sub(r"\s+", " ", t)
    return t


def _cmd_head(s: str) -> str | None:
    s = s.strip().lstrip("$>").strip()
    if not s or s.startswith("#"):
        return None
    tok = s.split()[0]
    if tok in ("npx", "uvx", "bunx", "pipx") and len(s.split()) > 1:
        tok = s.split()[1]
        tok = tok.split("@")[0] if not tok.startswith("@") else tok
    if tok in ("python", "python3", "node", "bash", "sh") and len(s.split()) > 1:
        nxt = s.split()[1]
        if nxt == "-m" and len(s.split()) > 2:
            return s.split()[2]
        return None
    if tok in ("pip", "pip3", "npm", "yarn", "pnpm", "apt", "apt-get", "brew", "cargo",
               "go", "gem", "conda", "uv") and len(s.split()) > 2 and s.split()[1] in (
               "install", "add", "i", "get"):
        return s.split()[2]
    return tok if _IDENT.match(tok) and tok.lower() not in _STOP else None


def extract_terms(text: str, known: set[str] | None = None, limit: int = 30) -> list[dict]:
    """Candidate tool/service/program mentions, in order of first appearance.

    Each candidate is {"term", "line", "source"}: backticked command heads and
    identifiers, command heads in shell code blocks, MCP server prefixes, product
    phrases ("X API", "X account", ...), and any already-indexed term found verbatim.
    """
    out: dict[str, dict] = {}

    def add(term: str, line: int, source: str) -> None:
        k = norm(term)
        if not k or k in _STOP or len(k) < 2 or k.isdigit():
            return
        if k not in out:
            out[k] = {"term": k, "line": line, "source": source}

    lang, in_fence = "", False
    for no, line in enumerate(text.splitlines(), 1):
        m = _FENCE.match(line.strip())
        if m:
            in_fence, lang = (not in_fence), m.group(1).lower()
            continue
        if in_fence:
            if lang in _SHELL_LANGS:
                h = _cmd_head(line)
                if h:
                    add(h, no, "code")
            continue
        for mm in _MCP.finditer(line):
            add(f"mcp__{mm.group(1)}", no, "mcp")
        for mm in re.finditer(r"`([^`]{1,80})`", line):
            span = mm.group(1).strip()
            if " " in span or span.startswith(("$", ">")):
                h = _cmd_head(span)
                if h:
                    add(h, no, "backtick")
            elif _IDENT.match(span) and not span.endswith((".md", ".json", ".csv", ".txt",
                                                            ".py", ".yaml", ".yml")):
                add(span, no, "backtick")
        for mm in _PRODUCT.finditer(line):
            add(f"{mm.group(1)} {mm.group(2)}", no, "product")
        if known:
            low = line.lower()
            for k in known:
                if len(k) >= 3 and k in low and re.search(rf"(?<![a-z0-9]){re.escape(k)}"
                                                          rf"(?![a-z0-9])", low):
                    add(k, no, "index")
    return sorted(out.values(), key=lambda d: d["line"])[:limit]


@dataclass
class Mention:
    term: str
    cls: str                 # one of CLASSES
    core: bool
    skill: str
    runtime: str = "developer-sandbox"
    blocked: bool = False    # the execution was blocked by this term
    note: str = ""


@dataclass
class PolicyIndex:
    entries: dict = field(default_factory=dict)   # term -> {"mentions": [...]} summary

    @staticmethod
    def load(path: str | Path) -> "PolicyIndex":
        p = Path(path)
        return PolicyIndex(json.loads(p.read_text())) if p.exists() else PolicyIndex()

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.entries, indent=1, sort_keys=True) + "\n")

    def add(self, m: Mention) -> None:
        e = self.entries.setdefault(norm(m.term), {"mentions": []})
        e["mentions"].append({"cls": m.cls, "core": m.core, "skill": m.skill,
                              "runtime": m.runtime, "blocked": m.blocked,
                              "note": m.note[:160]})

    def summary(self, term: str) -> dict | None:
        e = self.entries.get(norm(term))
        if not e:
            return None
        ms = e["mentions"]
        cls = Counter(x["cls"] for x in ms)
        return {"term": norm(term), "n": len(ms), "class": cls.most_common(1)[0][0],
                "classes": dict(cls), "core": sum(x["core"] for x in ms),
                "blocked": sum(x["blocked"] for x in ms),
                "notes": [x["note"] for x in ms if x["note"]][:2]}

    def lookup(self, text: str, limit: int = 30) -> dict:
        """{"known": [summary...], "unknown": [term...]} for the skill text."""
        known, unknown = [], []
        for c in extract_terms(text, set(self.entries), limit=limit):
            s = self.summary(c["term"])
            if s:
                known.append(dict(s, line=c["line"]))
            else:
                unknown.append(c["term"])
        return {"known": known, "unknown": unknown}

    def stats(self) -> dict:
        by = defaultdict(int)
        for t in self.entries:
            by[self.summary(t)["class"]] += 1
        return {"terms": len(self.entries), "by_class": dict(by)}

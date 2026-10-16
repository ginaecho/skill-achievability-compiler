#!/usr/bin/env python3
"""Experiment C (runs/20261015_review_response/PLAN.md): measured cost.

Real model calls, simulated tool results grounded in the annotators' verified
observations.

  python scripts/measure_cost.py prepare runs/20261015_cost/v1
  python scripts/measure_cost.py run     runs/20261015_cost/v1 [--only c001,c004] [--arm ungated|gated]
  python scripts/measure_cost.py score   runs/20261015_cost/v1

Set: the 31 BLOCKED documents of benchmark/claude_env/set2 and 31 ACHIEVABLE ones
taken in sha256("cost:"+case) order.

Arm (a) ungated: gpt-5.4 is asked to carry out the document's task in the
claude-code-cloud runtime, one JSON action per turn, at most 12 turns.  Tool
results come from a deterministic stub (`Stub`) that answers from the
document's truth file (requirements with kind/name/status) and from the
runtime's stated facts (Linux, no GPU, no Docker daemon, egress allow-list).
A program with no truth entry is treated as present, so the stub never invents
a blocker the annotators did not verify.

Arm (b) gated: one P2g compaction (ce_runtime_messages, one CE_RETRY on a parse
or gate error), bind_runtime(prune=False), check().  The checker spends zero
tokens by construction: no model is in its decision path, so there is nothing
to meter.

Every model call goes through providers.azure_openai_complete inside
`with metered() as usage:`, so tokens are the API's own usage block.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import shlex
import statistics
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from skillc import check  # noqa: E402
from skillc.frontend import providers  # noqa: E402
from skillc.frontend.ce import CEError, extract_ce, parse_ce_detailed  # noqa: E402
from skillc.frontend.prompts import CE_RETRY_PROMPT, ce_runtime_messages  # noqa: E402
from skillc.frontend.providers import extract_json_object, metered  # noqa: E402
from skillc.frontend.runtime import bind_runtime, load_runtime  # noqa: E402
from skillc.pack import PackError  # noqa: E402
from skillc.tokens import FAILURE_PROFILES, economics  # noqa: E402

SET2 = ROOT / "benchmark" / "claude_env" / "set2"
RUNTIME_NAME = "claude-code-cloud"
MODEL = "gpt-5.4"
MAX_TURNS = 12
WORKERS = 4
TIMEOUT = 600
LABEL = ("real model calls, simulated tool results grounded in the annotators' "
         "verified observations")
ASK_USER_ANSWER = "Use your best judgement; I have nothing to add."

# --------------------------------------------------------------------------
# Prompts (frozen into frozen.json by `prepare`)
# --------------------------------------------------------------------------

UNGATED_SYSTEM = """You are an autonomous agent working in the runtime described below.
Your job is to carry out what the document below is for, for one representative
request that a user of this document would typically make. Choose that request
yourself and state it in your first "why". There is no live user to supply inputs:
if the request needs inputs a user would normally give (a project to work on, a file,
a description, a design, a dataset), invent a small plausible one yourself and create
it with the tools if it must exist on disk. Never invent credentials, accounts, tool
results or service responses. The working directory starts empty apart from this
document and the files it names as bundled with it; if your request needs a project,
create a small one yourself.

You can act only through the runtime's tools. You know only what the tool results
show you: do not assume a command worked, a file exists, a service answered or a
credential is set unless a tool result says so.

Each turn, output exactly ONE JSON object and nothing else, in one of two shapes:
  {{"tool": "<tool name>", "args": {{...}}, "why": "<one sentence>"}}
  {{"status": "achieved" | "blocked" | "impossible", "reason": "<one or two sentences>"}}

Report "achieved" only when the tool results show that the document's deliverable
for your request is done. Report "blocked" when something the task needs is missing
in this runtime and you cannot obtain it. Report "impossible" when the task cannot be
done in this runtime at all. Stop as soon as one of the three is true.

Arguments: bash {{"command": "..."}}; read {{"path": "..."}}; write {{"path": "...",
"content": "..."}}; edit {{"path": "...", "old": "...", "new": "..."}}; web_fetch
{{"url": "..."}}; web_search {{"query": "..."}}; ask_user {{"question": "..."}};
a connector (github, notion, ...) {{"operation": "<one of its operations>",
"params": {{...}}}}; any other tool {{"action": "...", ...}}.

RUNTIME `{name}`: {description}
Its tools:
{tools}
"""

UNGATED_USER_HEAD = """Document ({kind_phrase}, `{path}` from {repo}):
```
{text}
```
"""
UNGATED_USER_TAIL = "\nYour next JSON object:"


def ungated_system(runtime) -> str:
    tools = "\n".join(f"  - `{t}`: {d}" for t, d in runtime.tools.items())
    return UNGATED_SYSTEM.format(name=runtime.name, description=runtime.description,
                                 tools=tools)


def ungated_head(meta: dict, text: str) -> str:
    kind_phrase = "an agent skill (SKILL.md)" if meta["kind"] == "skill" \
        else "an agent definition (agent.md)"
    return UNGATED_USER_HEAD.format(kind_phrase=kind_phrase, path=meta["path_in_repo"],
                                    repo=meta["repo_url"], text=text)


def transcript_user(head: str, turns: list[dict]) -> str:
    parts = [head]
    if turns:
        parts.append("\nTranscript so far:")
        for t in turns:
            parts.append(f"\nTurn {t['turn']} (you): {t['reply_text']}")
            parts.append(f"Turn {t['turn']} (result): {t['result']}")
    return "\n".join(parts) + UNGATED_USER_TAIL


# --------------------------------------------------------------------------
# The stub: tool results from the truth file
# --------------------------------------------------------------------------

ALLOW_SUFFIXES = (
    "pypi.org", "pythonhosted.org", "npmjs.org", "npmjs.com", "github.com",
    "githubusercontent.com", "githubassets.com", "ubuntu.com", "nuget.org",
    "golang.org", "go.dev", "pkg.go.dev",
)
COMMON_VARS = {"HOME", "PATH", "USER", "PWD", "SHELL", "LANG", "TERM", "HOSTNAME",
               "TMPDIR", "OLDPWD", "LC_ALL", "PYTHONPATH", "VIRTUAL_ENV", "CI",
               "NODE_ENV", "EDITOR", "UID", "GITHUB_TOKEN_UNUSED"}
OFFLINE_SUBCMDS = {"fmt", "format", "--version", "-v", "-V", "version", "help", "--help",
                   "-h", "lint", "test", "build", "check", "validate-local", "compile"}
# libraries that reach a host by themselves (used only if truth lists the host unavailable)
LIB_HOSTS = {"from_pretrained": "huggingface.co", "hf_hub_download": "huggingface.co",
             "snapshot_download": "huggingface.co", "pipeline(": "huggingface.co",
             "load_dataset(": "huggingface.co"}
# the vendor a CLI talks to, and the CLI a package installs
VENDOR = {"hf": "huggingface", "huggingface-cli": "huggingface", "az": "azure",
          "neonctl": "neon", "wrangler": "cloudflare", "eas": "expo", "atk": "m365"}
PKG_BINS = {"azure-cli": "az", "huggingface-hub": "hf", "neonctl": "neon",
            "@microsoft/m365agentstoolkit-cli": "atk", "wrangler": "wrangler",
            "eas-cli": "eas"}
CRED_VAR = re.compile(r"KEY|TOKEN|SECRET|PASSW|AUTH|CRED|ENDPOINT|CLIENT|TENANT|"
                      r"SUBSCRIPTION|ACCOUNT|_ID$|CONNECTION|DEPLOYMENT|_URL$|DSN|PROJECT|"
                      r"_USER$|LOGIN")
GENERIC_TOKENS = {"com", "org", "net", "io", "dev", "api", "www", "app", "cli", "the",
                  "and", "for", "with", "sdk", "local", "tool", "tools", "account",
                  "accounts", "access", "login", "signed", "user", "package", "npm",
                  "python", "python3", "pip", "module", "server", "service", "cloud",
                  "host", "direct", "from", "container", "endpoint", "endpoints", "key",
                  "keys", "token", "tcp", "build", "docs", "learn", "microsoft",
                  "project", "region", "mcp", "agent", "agents", "open", "registry"}


def _norm(name: str) -> str:
    n = name.strip().lower()
    n = re.split(r"[=<>~!\[;]", n)[0].strip()
    if "@" in n[1:]:                       # npm name@version (keep a leading @scope)
        n = n[0] + n[1:].split("@")[0]
    return n.replace("_", "-")


def aliases(name: str) -> set:
    """Names a truth requirement may be invoked by."""
    out = set()
    main = name.split(" (")[0]
    for part in re.split(r"\s*(?:/|\+|,| or )\s*", main):
        part = part.strip()
        if part and " " not in part:
            out.add(_norm(part))
        elif part:
            out.add(_norm(part.split()[0]))
    if name.strip().startswith("@"):
        out.add(_norm(name.split(" (")[0]))
    for inner in re.findall(r"\(([^)]*)\)", name):
        for tok in re.split(r"[\s,]+", inner):
            tok = tok.strip()
            if tok and tok.lower() not in {"or", "cli", "npm", "package", "with", "logged",
                                           "in", "local", "install", "at"} \
                    and re.match(r"^[@A-Za-z][\w.@/-]*$", tok) and len(tok) > 2:
                out.add(_norm(tok))
    out |= {a.replace(".", "-") for a in out}
    return {a for a in out if a}


def name_tokens(name: str) -> set:
    toks = {t for t in re.split(r"[^a-z0-9]+", name.lower()) if len(t) >= 3}
    return toks - GENERIC_TOKENS


def host_pattern(name: str):
    """A regex for an egress requirement's host, or None if it names no host."""
    for tok in re.split(r"[\s(),/]+", name):
        if "." in tok and re.match(r"^[\w<>*.-]+$", tok) and not tok.endswith("."):
            pat = re.escape(tok.lower())
            pat = re.sub(r"\\?<[^>]*\\?>", r"[^/]+", pat).replace(r"\*", r"[^/]*")
            return re.compile(rf"^(?:[^/]*\.)?{pat}$")
    return None


class Stub:
    """Deterministic tool results for one document, grounded in its truth file."""

    def __init__(self, truth: dict, runtime, doc_path: str, doc_text: str):
        self.runtime = runtime
        self.doc_path = doc_path
        self.doc_text = doc_text
        self.entries = []
        for r in truth["requirements"]:
            self._add(r)
        self.installed: set = set()
        self.files: dict = {}
        self.heredocs = ""
        self.produced: set = set()
        # relative paths the document names (scripts/x.py, references/y.md, ...)
        self.bundled = sorted({
            m.group(1).lstrip("./") for m in re.finditer(
                r"(?<![\w:.@-])((?:\./)?(?:[\w-]+/)+[\w.-]+\.[A-Za-z]\w{0,4})\b", doc_text)
            if not re.match(r"^(?:[\w-]+\.)+(?:com|org|io|dev|net|ai|app)/", m.group(1))})

    def is_bundled(self, path: str) -> bool:
        path = path.strip().strip("'\"")
        return path not in self.files and any(path.endswith(b) for b in self.bundled)

    def bundled_blocker(self) -> str | None:
        """A bundled script's network need: the truth's first hard unavailable egress."""
        for e in self.entries:
            if e["kind"] == "egress" and e["status"] == "unavailable" and e["hard"]:
                host = e["name"].split()[0] if e["host"] else e["name"]
                return f"curl: (56) CONNECT tunnel failed, response 403 ({host})"
        return None

    def _add(self, r: dict, hard: bool | None = None) -> None:
        e = {"kind": r["kind"], "name": r["name"], "status": r["status"],
             "hard": bool(r.get("hard")) if hard is None else hard,
             "aliases": aliases(r["name"]), "tokens": name_tokens(r["name"]),
             "host": host_pattern(r["name"]) if r["kind"] == "egress" else None,
             "vars": set(re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", r["name"]))}
        self.entries.append(e)
        for sub in r.get("any_of") or []:
            self._add({"any_of": None, **sub},
                      hard=bool(r.get("hard")) and r["status"] == "unavailable")

    # ---- lookups --------------------------------------------------------
    def _match(self, name: str, kinds: tuple) -> list:
        n = _norm(name)
        if not n:
            return []
        variants = {n, n.replace("-", "_"), n.split("/")[-1], n.replace(".", "-")}
        return [e for e in self.entries if e["kind"] in kinds
                and (variants & e["aliases"])]

    def program_state(self, prog: str) -> str:
        """present | installable | unavailable"""
        hits = self._match(prog, ("program", "pymodule", "skill-source", "mcp"))
        if not hits:
            return "present"
        if any(e["status"] == "available" for e in hits):
            return "present"
        if any(_norm(prog) in self.installed or (e["aliases"] & self.installed)
               for e in hits):
            return "present"
        if any(e["status"] == "installable" for e in hits):
            return "installable"
        return "unavailable"

    def host_state(self, host: str, url: str = "") -> str:
        """available | refused"""
        host = host.lower().split(":")[0]
        verdicts = [e["status"] for e in self.entries
                    if e["kind"] == "egress" and e["host"] and e["host"].match(host)]
        if verdicts:
            return "available" if "available" in verdicts else "refused"
        # a vendor download of a program the annotators verified installable
        low = url.lower()
        for e in self.entries:
            if e["kind"] in ("program", "pymodule") and e["status"] == "installable" \
                    and any(len(a) > 2 and a in low for a in e["aliases"]):
                return "available"
        if any(host == s or host.endswith("." + s) for s in ALLOW_SUFFIXES):
            return "available"
        return "refused"

    def var_set(self, var: str) -> bool:
        if var in COMMON_VARS or not CRED_VAR.search(var):
            return True
        for e in self.entries:
            if e["kind"] in ("credential", "account") and e["status"] == "available":
                if var in e["vars"]:
                    return True
                if var.startswith("AWS_") and "aws" in e["name"].lower():
                    return True
        return False

    def coupled_blocker(self, prog: str, args: list, text: str) -> str | None:
        """An unavailable account/egress the annotators tied to this program."""
        words = [a for a in args if not a.startswith("-")]
        if words and words[0] in OFFLINE_SUBCMDS:
            return None
        if not words and any(a in OFFLINE_SUBCMDS for a in args):
            return None
        ptoks = name_tokens(prog) | {_norm(prog)}
        if _norm(prog) in VENDOR:
            ptoks.add(VENDOR[_norm(prog)])
        for e in self.entries:
            if e["status"] != "unavailable":
                continue
            if e["kind"] in ("account", "credential") and ptoks & e["tokens"]:
                return (f"Error: not authenticated. No {e['name']} credentials or login "
                        f"found in this environment.")
        for e in self.entries:
            if e["status"] != "unavailable" or e["kind"] != "egress" or not words:
                continue
            if ptoks & e["tokens"]:
                host = e["name"].split()[0]
                return (f"Error: request to https://{host}/ failed: "
                        f"CONNECT tunnel failed, response 403")
        return None

    def text_blockers(self, text: str) -> str | None:
        """Hosts named in a command or a script it runs."""
        for url in re.findall(r"https?://[^\s'\"`)<>]+", text):
            host = urlparse(url).hostname or ""
            if host and self.host_state(host, url) == "refused":
                return f"curl: (56) CONNECT tunnel failed, response 403 ({host})"
        for lib, host in LIB_HOSTS.items():
            if lib in text:
                for e in self.entries:
                    if e["kind"] == "egress" and e["status"] == "unavailable" \
                            and e["host"] and e["host"].match(host):
                        return (f"OSError: We couldn't connect to 'https://{host}': "
                                f"ProxyError('Unable to connect to proxy', "
                                f"'Tunnel connection failed: 403 Forbidden')")
        for var in re.findall(r"\$\{?([A-Z][A-Z0-9_]{2,})\}?|environ(?:\.get)?\(?\[?['\"]"
                              r"([A-Z][A-Z0-9_]{2,})", text):
            v = var[0] or var[1]
            if v and not self.var_set(v):
                return f"Error: environment variable {v} is not set"
        return None

    # ---- tools ----------------------------------------------------------
    def call(self, tool: str, args: dict) -> str:
        tool = (tool or "").strip().lower().replace("-", "_")
        args = args if isinstance(args, dict) else {}
        if tool == "bash":
            return self.bash(str(args.get("command", "")))
        if tool == "read":
            return self.read(str(args.get("path", args.get("pattern", ""))))
        if tool in ("write", "edit"):
            path = str(args.get("path", ""))
            if tool == "write":
                self.files[path] = str(args.get("content", ""))
                return f"Wrote {len(self.files[path])} bytes to {path}."
            cur = self.files.get(path, "")
            self.files[path] = cur.replace(str(args.get("old", "")), str(args.get("new", "")))
            return f"Edited {path}."
        if tool == "web_fetch":
            url = str(args.get("url", ""))
            host = urlparse(url).hostname or ""
            if not host:
                return "Error: invalid URL"
            if self.host_state(host, url) == "refused":
                return f"Error: fetching {url} failed: CONNECT tunnel failed, response 403"
            return f"HTTP 200 from {host}. The page loaded; its content matches what the document says about it."
        if tool == "web_search":
            return ("Search results: 5 snippets, consistent with the document; "
                    "no new information beyond it.")
        if tool == "ask_user":
            return ASK_USER_ANSWER
        if tool == "agent":
            return ("The sub-agent ran in the same runtime with the same tools and "
                    "returned no information beyond what your own tool results show.")
        if tool == "skill":
            return "Loaded: the document above is the installed skill."
        if tool == "mcp_resources":
            conns = [t for t in self.runtime.tools if t in CONNECTORS]
            return "Connected MCP servers: " + ", ".join(conns) + "."
        if tool in CONNECTORS:
            op = args.get("operation") or args.get("action") or "call"
            return f"{tool}.{op}: OK. The call succeeded and returned the requested data."
        if tool in self.runtime.tools:
            return f"{tool}: OK."
        return (f"Error: unknown tool `{tool}`. Available tools: "
                + ", ".join(self.runtime.tools) + ".")

    def read(self, path: str) -> str:
        if path in self.files:
            return self.files[path][:4000]
        base = path.rsplit("/", 1)[-1]
        if base.lower() in (self.doc_path.rsplit("/", 1)[-1].lower(), "skill.md"):
            return self.doc_text[:4000]
        if self.is_bundled(path):
            return (f"{path}: a file bundled with the document; it contains what the document "
                    f"says it contains (the simulation summarizes files you did not write "
                    f"instead of showing them).")
        if path in self.produced:
            return (f"{path}: produced by an earlier command; it contains what that command "
                    f"is documented to produce (summarized by the simulation).")
        return f"{path}: No such file or directory"

    # ---- bash -----------------------------------------------------------
    def bash(self, command: str) -> str:
        for m in re.finditer(r"(?:cat|tee)\s*>{1,2}?\s*(\S+)\s*<<-?\s*['\"]?(\w+)['\"]?[^\n]*"
                             r"\n(.*?)\n\s*\2\b", command, flags=re.S):
            self.files[m.group(1)] = m.group(3)
        self.heredocs = "\n".join(m.group(2) for m in re.finditer(
            r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n(.*?)\n\s*\1\b", command, flags=re.S))
        command = re.sub(r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n.*?\n\s*\1\b", "<<HEREDOC",
                         command, flags=re.S)
        outputs: list = []
        ok = True
        pipe_out = None          # output of the first segment of a running pipeline
        for op, seg in split_segments(command):
            if op == "&&" and not ok or op == "||" and ok:
                continue
            out, ok = self.segment(seg)
            first = seg.split()[0].rsplit("/", 1)[-1] if seg.split() else ""
            if op == "|":
                if not ok:
                    outputs.append(out)
                elif first in FILTERS and pipe_out is not None:
                    pass         # the filter's input is already shown
                elif out:
                    outputs.append(out)
            else:
                pipe_out = out
                if out:
                    outputs.append(out)
        outputs.append(f"(exit code {0 if ok else 1})")
        return "\n".join(outputs)[:2000]

    def segment(self, seg: str) -> tuple[str, bool]:
        try:
            toks = shlex.split(seg, posix=True)
        except ValueError:
            toks = seg.split()
        toks = [t for t in (x.strip("()") for x in toks) if t]
        if toks and toks[0].rsplit("/", 1)[-1] != "cat":
            kept, skip = [], False
            for t in toks:
                if skip:
                    skip = False
                    continue
                if re.fullmatch(r"\d?>>?|&>|<", t):
                    skip = True
                    continue
                if re.match(r"^(\d?>>?|&>|<<?)\S", t):
                    continue
                kept.append(t)
            toks = kept
        while toks and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", toks[0])
                        or toks[0] in ("sudo", "env", "time", "exec", "nohup", "then",
                                       "do", "else", "{", "(")):
            toks = toks[1:]
        if not toks:
            return "", True
        prog = toks[0].rsplit("/", 1)[-1]
        args = toks[1:]
        if prog in ("cd", "export", "set", "true", "source", ".", "mkdir", "touch", "fi",
                    "done", "}", ")", "if", "for", "while", "echo", "printf", "cat", "ls",
                    "pwd", "test", "[", "[[", "rm", "cp", "mv", "chmod", "grep", "head",
                    "tail", "sed", "awk", "wc", "sort", "find", "tee", "xargs", "tar",
                    "unzip", "printenv", "which", "command", "type", "uname", "nvidia-smi",
                    "docker", "curl", "wget", "git", "gh", "apt", "apt-get", "pip", "pip3",
                    "npm", "npx", "pnpm", "yarn", "uv", "pipx", "python", "python3",
                    "go", "cargo", "dotnet", "gem", "brew", "nproc", "free", "df"):
            return self.builtin(prog, args, seg)
        return self.run_program(prog, args, seg)

    def run_program(self, prog: str, args: list, seg: str) -> tuple[str, bool]:
        st = self.program_state(prog)
        if st != "present":
            return f"bash: {prog}: command not found", False
        if args and args[0] in ("--version", "-v", "-V", "version"):
            return f"{prog} 1.0.0", True
        blk = self.coupled_blocker(prog, args, seg) or self.text_blockers(
            seg + "\n" + self.heredocs)
        if not blk and any(self.is_bundled(a) for a in [prog] + args):
            blk = self.bundled_blocker()
        if blk:
            return blk, False
        self._produce(args)
        return RAN, True

    def _produce(self, args: list) -> None:
        for a in args:
            a = a.split("=", 1)[-1]
            if re.fullmatch(r"[\w./-]+\.[A-Za-z]\w{0,4}", a) and a not in self.files \
                    and not self.is_bundled(a):
                self.produced.add(a)

    def builtin(self, prog: str, args: list, seg: str) -> tuple[str, bool]:
        a = [x for x in args if not x.startswith("-")]
        if prog in ("echo", "printf"):
            m = re.findall(r"\$\{?([A-Z][A-Z0-9_]{2,})\}?", seg)
            unset = [v for v in m if not self.var_set(v)]
            if unset:
                return "(empty: " + ", ".join(unset) + " not set)", True
            return " ".join(args)[:200], True
        if prog == "printenv":
            if a and not self.var_set(a[0]):
                return "", False
            return "(variables printed)", True
        if prog in ("test", "[", "[["):
            m = re.findall(r"\$\{?([A-Z][A-Z0-9_]{2,})\}?", seg)
            if m and not all(self.var_set(v) for v in m):
                return "", False
            for flag in ("-f", "-e", "-d", "-x", "-s"):
                if flag in args and args.index(flag) + 1 < len(args):
                    path = args[args.index(flag) + 1].strip("'\"").removeprefix("./")
                    known = set(self.files) | self.produced | set(self.bundled)
                    hit = path in known or self.is_bundled(path) or (
                        flag == "-d" and any(k.startswith(path.rstrip("/") + "/")
                                             for k in known))
                    return "", hit
            return "", True
        if prog in ("which", "command", "type"):
            names = [x for x in a if x not in ("-v",)]
            missing = [n for n in names if self.program_state(n) != "present"
                       or n in ("nvidia-smi", "osascript")]
            if missing:
                return "", False
            return "\n".join(f"/usr/bin/{n}" for n in names), True
        if prog == "uname":
            return "Linux x86_64", True
        if prog == "nvidia-smi":
            return "bash: nvidia-smi: command not found", False
        if prog in ("nproc",):
            return "4", True
        if prog == "free":
            return "Mem: total 15Gi", True
        if prog == "docker":
            if args and args[0] in ("--version", "version") and len(args) == 1:
                return "Docker version 27.5.1 (client only)", True
            return ("failed to connect to the docker API at unix:///var/run/docker.sock; "
                    "is the docker daemon running?"), False
        if prog == "cat" and (">" in args or ">>" in args):
            target = args[(args.index(">") if ">" in args else args.index(">>")) + 1:][:1]
            if target and target[0] not in self.files:
                self.files[target[0]] = " ".join(x for x in args if x not in (">", ">>"))
            return "", True
        if prog in ("cat", "head", "tail") and a:
            if a[0] in self.files:
                return self.files[a[0]][:1500], True
            out = self.read(a[0])[:600]
            return out, not out.endswith("No such file or directory")
        if prog in ("ls", "find"):
            listed = ", ".join(sorted(self.files)) or "no files written yet"
            bundled = ", ".join(self.bundled) or "none"
            return (f"{self.doc_path.rsplit('/', 1)[-1]}; bundled with it: {bundled}; "
                    f"files written this session: {listed}"), True
        if prog in ("curl", "wget"):
            urls = [x for x in args if re.match(r"^https?://", x)] or \
                   [x for x in args if "." in x and "/" in x]
            if not urls:
                return "", True
            url = urls[0] if "://" in urls[0] else "https://" + urls[0]
            host = urlparse(url).hostname or ""
            if self.host_state(host, url) == "refused":
                return "curl: (56) CONNECT tunnel failed, response 403", False
            self._mark_installed_from_text(url)
            blk = self.text_blockers(seg)
            if blk:
                return blk, False
            return f"HTTP 200 from {host}", True
        if prog == "git":
            if a and a[0] in ("clone", "fetch", "pull", "push", "ls-remote"):
                for x in args:
                    if "://" in x or x.startswith("git@"):
                        host = (urlparse(x).hostname if "://" in x
                                else x.split("@", 1)[1].split(":")[0])
                        if self.host_state(host or "", x) == "refused":
                            return ("fatal: unable to access: CONNECT tunnel failed, "
                                    "response 403"), False
            return "", True
        if prog == "gh":
            return "", True
        if prog in ("apt", "apt-get") and a[:1] == ["install"]:
            return self.install(a[1:], "apt")
        if prog in ("pip", "pip3") and a[:1] == ["install"]:
            return self.install(a[1:], "pip")
        if prog in ("python", "python3"):
            if args[:2] == ["-m", "pip"] and "install" in args:
                rest = [x for x in args[args.index("install") + 1:] if not x.startswith("-")]
                return self.install(rest, "pip")
            if args[:1] == ["-c"] and len(args) > 1:
                for mod in re.findall(r"(?:^|[;\n]\s*)(?:import|from)\s+([\w.]+)", args[1]):
                    st = self.program_state(mod.split(".")[0]) if not \
                        self._match(mod, ("pymodule",)) else self.program_state(mod)
                    if st != "present":
                        return f"ModuleNotFoundError: No module named '{mod}'", False
                blk = self.text_blockers(args[1])
                return (blk, False) if blk else (RAN, True)
            if args[:1] == ["-m"] and len(args) > 1:
                if self.program_state(args[1]) != "present":
                    return f"No module named {args[1]}", False
                blk = self.coupled_blocker(args[1], args[2:], seg) or self.text_blockers(seg)
                return (blk, False) if blk else (RAN, True)
            if args and args[0] in ("--version", "-V"):
                return "Python 3.11.15", True
            script = next((x for x in args if x.endswith(".py")), None)
            text = seg + "\n" + self.files.get(script or "", "") + "\n" + self.heredocs
            for mod in re.findall(r"(?m)^\s*(?:import|from)\s+([\w.]+)", text):
                if self._match(mod, ("pymodule",)) and self.program_state(mod) != "present":
                    return f"ModuleNotFoundError: No module named '{mod}'", False
            blk = self.text_blockers(text)
            if not blk and script and self.is_bundled(script):
                blk = self.bundled_blocker()
            if not blk:
                self._produce([x for x in args if x != script])
            return (blk, False) if blk else (RAN, True)
        if prog in ("uv", "pipx") and "install" in a:
            rest = [x for x in a[a.index("install") + 1:] if x not in ("pip", "tool")]
            return self.install(rest, "pip")
        if prog in ("npm", "pnpm", "yarn") and a[:1] and a[0] in ("install", "i", "add"):
            return self.install(a[1:], "npm")
        if prog == "npx":
            pkgs = [x for x in a if x not in ("--yes", "-y")]
            if pkgs:
                name = _norm(pkgs[0])
                if self.program_state(name) != "present":
                    out, ok = self.install([name], "npm")   # npx fetches the package
                    if not ok:
                        return out, ok
                rest = args[args.index(pkgs[0]) + 1:]
                return self.run_program(name, rest, seg)
            return "", True
        if prog in ("go", "cargo", "dotnet", "gem", "brew") and "install" in a:
            rest = [x for x in a[a.index("install") + 1:] if x not in ("tool",)]
            return self.install([x.rsplit("/", 1)[-1].split("@")[0] for x in rest], prog)
        if prog in ("brew",):
            return "bash: brew: command not found", False
        if prog in ("go", "cargo", "dotnet", "gem", "npm", "pnpm", "yarn", "uv", "pipx",
                    "pip", "pip3", "apt", "apt-get"):
            return self.run_program(prog, args, seg)
        blk = self.text_blockers(seg)
        return (blk, False) if blk else ("", True)

    def _mark_installed_from_text(self, text: str) -> None:
        low = text.lower()
        for e in self.entries:
            if e["status"] == "installable" and any(len(x) > 2 and x in low for x in e["aliases"]):
                self.installed |= e["aliases"]

    def install(self, pkgs: list, how: str) -> tuple[str, bool]:
        pkgs = [p for p in pkgs if p and not p.startswith("-")]
        if not pkgs:
            return "Requirements installed.", True
        done = []
        for p in pkgs:
            name = _norm(p.split("@")[0] if not p.startswith("@") else "@" + p[1:].split("@")[0])
            hits = self._match(name, ("program", "pymodule", "skill-source", "mcp"))
            if hits and all(e["status"] == "unavailable" for e in hits):
                msg = {"apt": f"E: Unable to locate package {p}",
                       "pip": (f"ERROR: Could not find a version that satisfies the "
                               f"requirement {p}\nERROR: No matching distribution found for {p}"),
                       "npm": f"npm error 404 Not Found - GET https://registry.npmjs.org/{p}"
                       }.get(how, f"error: package {p} not found")
                return msg, False
            for e in hits:
                self.installed |= e["aliases"]
            self.installed.add(name)
            if name in PKG_BINS:
                self.installed.add(PKG_BINS[name])
            done.append(p)
        return {"apt": "Setting up " + ", ".join(done) + " ... done",
                "pip": "Successfully installed " + " ".join(done),
                "npm": f"added {len(done) * 12} packages"}.get(how, "installed " + " ".join(done)), True


CONNECTORS = {"github", "notion", "google_drive", "jam", "mem", "bigdata_com", "etoro",
              "claude_docs"}


def split_segments(cmd: str) -> list:
    """Split a shell command on unquoted |, ||, &&, ;, & and newlines into
    (operator before the segment, segment) pairs; the first operator is ';'."""
    segs, cur, q, i, op = [], [], None, 0, ";"
    while i < len(cmd):
        c = cmd[i]
        if q:
            cur.append(c)
            if c == q:
                q = None
            elif c == "\\" and q == '"' and i + 1 < len(cmd):
                cur.append(cmd[i + 1])
                i += 1
        elif c in ("'", '"'):
            q = c
            cur.append(c)
        elif c == "&" and ((i and cmd[i - 1] == ">") or cmd[i + 1:i + 2] == ">"):
            cur.append(c)
        elif c in "|;&\n":
            nxt = cmd[i + 1] if i + 1 < len(cmd) else ""
            segs.append((op, "".join(cur)))
            cur = []
            if c in "|&" and nxt == c:
                op = c + c
                i += 1
            else:
                op = {"|": "|", "&": ";", ";": ";", "\n": ";"}[c]
        else:
            cur.append(c)
        i += 1
    segs.append((op, "".join(cur)))
    return [(o, s.strip()) for o, s in segs if s.strip()]


RAN = ("(exit 0: the command did what it is documented to do; the simulation summarizes "
       "program output instead of reproducing it)")
FILTERS = {"grep", "head", "tail", "sort", "wc", "sed", "awk", "tee", "xargs", "cut", "tr",
           "jq", "less", "cat", "uniq"}


# --------------------------------------------------------------------------
# Model calls
# --------------------------------------------------------------------------

_TOKEN = {"value": None, "at": 0.0}
_TOKEN_LOCK = threading.Lock()
_orig_token = providers.azure_cli_token


def _cached_token() -> str:
    with _TOKEN_LOCK:
        if not _TOKEN["value"] or time.time() - _TOKEN["at"] > 1800:
            _TOKEN["value"] = _orig_token()
            _TOKEN["at"] = time.time()
        return _TOKEN["value"]


providers.azure_cli_token = _cached_token


def call_model(system: str, user: str, json_mode: bool) -> tuple[str, dict, int]:
    """(text, usage {input, output, cached}, attempts) via azure_openai_complete."""
    delay = 10
    for attempt in range(1, 8):
        try:
            with metered() as usage:
                text = providers.azure_openai_complete(system, user, MODEL, TIMEOUT,
                                                       json_mode=json_mode)
            u = usage[-1] if usage else {}
            return text, {"input": int(u.get("input_tokens", 0))
                          + int(u.get("cache_read_input_tokens", 0)),
                          "output": int(u.get("output_tokens", 0)),
                          "cached_input": int(u.get("cache_read_input_tokens", 0)),
                          "usage_reported": bool(usage)}, attempt
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            transient = ("HTTP 429" in msg or re.search(r"HTTP 5\d\d", msg)
                         or "timed out" in msg.lower() or "URLError" in type(e).__name__
                         or isinstance(e, (TimeoutError, ConnectionError, OSError)))
            if attempt == 7 or not transient:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 120)
    raise AssertionError("unreachable")


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------

def sha(s: str | bytes) -> str:
    return hashlib.sha256(s.encode() if isinstance(s, str) else s).hexdigest()


def load_set() -> list[dict]:
    cases = {c["case"]: c for c in json.loads((SET2 / "cases.json").read_text(
        encoding="utf-8"))["cases"]}
    truths = {}
    for f in sorted((SET2 / "truth").glob("c*.json")):
        t = json.loads(f.read_text(encoding="utf-8"))
        truths[t["case"]] = t
    blocked = sorted(c for c, t in truths.items() if t["verdict"] == "BLOCKED")
    achievable = sorted((c for c, t in truths.items() if t["verdict"] == "ACHIEVABLE"),
                        key=lambda c: sha("cost:" + c))[:len(blocked)]
    out = []
    for c in blocked + sorted(achievable):
        text = (SET2 / "cases" / f"{c}.md").read_text(encoding="utf-8")
        out.append({"case": c, "meta": cases[c], "truth": truths[c], "text": text})
    return out


def runtime_obj():
    return load_runtime(RUNTIME_NAME)


# --------------------------------------------------------------------------
# prepare
# --------------------------------------------------------------------------

def cmd_prepare(out: Path) -> int:
    out.mkdir(parents=True, exist_ok=False)
    (out / "prompts").mkdir()
    rt = runtime_obj()
    rt_path = ROOT / "src" / "skillc" / "data" / "runtimes" / f"{RUNTIME_NAME}.json"
    usys = ungated_system(rt)
    docs = []
    gsys_all = set()
    for d in load_set():
        c = d["case"]
        head = ungated_head(d["meta"], d["text"])
        first_user = transcript_user(head, [])
        gsys, guser = ce_runtime_messages(d["text"], rt)
        gsys_all.add(gsys)
        (out / "prompts" / f"{c}.ungated.user0.txt").write_text(first_user, encoding="utf-8")
        (out / "prompts" / f"{c}.gated.user.txt").write_text(guser, encoding="utf-8")
        docs.append({
            "case": c, "truth_verdict": d["truth"]["verdict"],
            "truth_blocking": d["truth"]["blocking"], "kind": d["meta"]["kind"],
            "id": d["meta"]["id"], "text_sha256": sha(d["text"]),
            "source_sha256_cases_json": d["meta"]["sha256"],
            "truth_sha256": sha((SET2 / "truth" / f"{c}.json").read_bytes()),
            "ungated_user0_sha256": sha(first_user), "gated_user_sha256": sha(guser),
        })
    assert len(gsys_all) == 1
    gsys = gsys_all.pop()
    (out / "prompts" / "ungated.system.txt").write_text(usys, encoding="utf-8")
    (out / "prompts" / "gated.system.txt").write_text(gsys, encoding="utf-8")
    frozen = {
        "experiment": "C: measured cost (runs/20261015_review_response/PLAN.md)",
        "label": LABEL,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": MODEL, "endpoint": "https://foundary-tzuc06.openai.azure.com/openai/v1",
        "runtime": RUNTIME_NAME, "runtime_sha256": sha(rt_path.read_bytes()),
        "max_turns": MAX_TURNS, "ask_user_answer": ASK_USER_ANSWER,
        "selection": "31 BLOCKED (all) + 31 ACHIEVABLE by ascending sha256('cost:'+case)",
        "script_sha256": sha(Path(__file__).read_bytes()),
        "ungated_system_sha256": sha(usys), "ungated_system": usys,
        "ungated_user_template": UNGATED_USER_HEAD + "\n[Transcript so far: ...]"
                                 + UNGATED_USER_TAIL,
        "gated_system_sha256": sha(gsys),
        "gated_retry_template": CE_RETRY_PROMPT,
        "n_blocked": sum(x["truth_verdict"] == "BLOCKED" for x in docs),
        "n_achievable": sum(x["truth_verdict"] == "ACHIEVABLE" for x in docs),
        "documents": docs,
    }
    (out / "frozen.json").write_text(json.dumps(frozen, indent=1) + "\n", encoding="utf-8")
    print(f"prepared {len(docs)} documents in {out} "
          f"({frozen['n_blocked']} BLOCKED, {frozen['n_achievable']} ACHIEVABLE)")
    return 0


def verify_frozen(out: Path) -> dict:
    frozen = json.loads((out / "frozen.json").read_text(encoding="utf-8"))
    rt = runtime_obj()
    if sha(ungated_system(rt)) != frozen["ungated_system_sha256"]:
        raise SystemExit("ungated system prompt changed since prepare")
    if sha(Path(__file__).read_bytes()) != frozen["script_sha256"]:
        raise SystemExit("measure_cost.py changed since prepare: re-prepare into a fresh "
                         "directory")
    by = {d["case"]: d for d in load_set()}
    for doc in frozen["documents"]:
        d = by[doc["case"]]
        if sha(d["text"]) != doc["text_sha256"]:
            raise SystemExit(f"{doc['case']}: text changed")
        gsys, guser = ce_runtime_messages(d["text"], rt)
        if sha(gsys) != frozen["gated_system_sha256"] or sha(guser) != doc["gated_user_sha256"]:
            raise SystemExit(f"{doc['case']}: gated prompt changed")
    return frozen


# --------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------

def run_ungated(d: dict, rt) -> dict:
    usys = ungated_system(rt)
    head = ungated_head(d["meta"], d["text"])
    stub = Stub(d["truth"], rt, d["meta"]["path_in_repo"], d["text"])
    turns: list[dict] = []
    status, reason = "timeout", f"no status after {MAX_TURNS} turns"
    for n in range(1, MAX_TURNS + 1):
        user = transcript_user(head, turns)
        text, usage, attempts = call_model(usys, user, json_mode=True)
        row = {"turn": n, "prompt_sha256": sha(user), "usage": usage, "attempts": attempts,
               "reply_text": " ".join(text.split())[:4000]}
        try:
            obj = extract_json_object(text)
        except (ValueError, json.JSONDecodeError):
            obj = None
        if isinstance(obj, dict) and obj.get("status") in ("achieved", "blocked", "impossible"):
            status, reason = obj["status"], str(obj.get("reason", ""))
            row.update(kind="status", status=status, reason=reason, result="")
            turns.append(row)
            break
        if isinstance(obj, dict) and isinstance(obj.get("tool"), str):
            result = stub.call(obj["tool"], obj.get("args") or {})
            row.update(kind="tool", tool=obj["tool"], args=obj.get("args"),
                       why=obj.get("why"), result=result)
        else:
            row.update(kind="invalid", result=("Error: your reply was not one JSON object "
                                               "of the two allowed shapes."))
        turns.append(row)
    return {"case": d["case"], "arm": "ungated", "truth": d["truth"]["verdict"],
            "status": status, "reason": reason, "turns": len(turns),
            "input_tokens": sum(t["usage"]["input"] for t in turns),
            "output_tokens": sum(t["usage"]["output"] for t in turns),
            "cached_input_tokens": sum(t["usage"]["cached_input"] for t in turns),
            "usage_reported_all": all(t["usage"]["usage_reported"] for t in turns),
            "transcript": turns}


def run_gated(d: dict, rt) -> dict:
    gsys, guser = ce_runtime_messages(d["text"], rt)
    calls, prompt = [], guser
    verdict, error, ce_text = None, None, None
    for attempt in range(2):
        text, usage, attempts = call_model(gsys, prompt, json_mode=False)
        calls.append({"attempt": attempt, "usage": usage, "http_attempts": attempts,
                      "prompt_sha256": sha(prompt), "reply_text": text})
        try:
            ce_text = extract_ce(text)
            parsed = parse_ce_detailed(ce_text)
            b = bind_runtime(parsed.pack, parsed.bindings, rt, prune=False)
            v = check(b.pack)
            verdict = {"label": v.label, "reason": v.reason, "refuted": v.refuted,
                       "unknown": v.unknown,
                       "protocol": getattr(v, "protocol", ""),
                       "protocol_reason": getattr(v, "protocol_reason", ""),
                       "withdrawn": b.withdrawn, "blocked": b.blocked}
            error = None
            break
        except (CEError, PackError) as e:
            error = f"{type(e).__name__}: {e}"
            prompt = guser + CE_RETRY_PROMPT.format(error=e, text=text.strip())
    return {"case": d["case"], "arm": "gated", "truth": d["truth"]["verdict"],
            "verdict": verdict, "error": error, "calls": len(calls),
            "input_tokens": sum(c["usage"]["input"] for c in calls),
            "output_tokens": sum(c["usage"]["output"] for c in calls),
            "cached_input_tokens": sum(c["usage"]["cached_input"] for c in calls),
            "checker_tokens": 0,
            "checker_tokens_note": "zero by construction: no model in the checker",
            "ce_text": ce_text, "transcript": calls}


def cmd_run(out: Path, only: list | None, arms: list) -> int:
    verify_frozen(out)
    rt = runtime_obj()
    docs = [d for d in load_set() if not only or d["case"] in only]
    jobs = []
    for arm in arms:
        (out / arm).mkdir(exist_ok=True)
        for d in docs:
            if not (out / arm / f"{d['case']}.json").exists():
                jobs.append((arm, d))
    print(f"{len(jobs)} job(s)", flush=True)
    fails = 0

    def work(arm, d):
        res = run_ungated(d, rt) if arm == "ungated" else run_gated(d, rt)
        (out / arm / f"{d['case']}.json").write_text(json.dumps(res, indent=1) + "\n",
                                                    encoding="utf-8")
        return res

    with ThreadPoolExecutor(WORKERS) as ex:
        futs = {ex.submit(work, a, d): (a, d["case"]) for a, d in jobs}
        for f in as_completed(futs):
            a, c = futs[f]
            try:
                r = f.result()
                tag = r.get("status") or (r["verdict"] or {}).get("label") or r.get("error")
                print(f"{a:8} {c} {r['truth']:10} -> {tag}  in={r['input_tokens']:,} "
                      f"out={r['output_tokens']:,}", flush=True)
            except Exception:  # noqa: BLE001
                fails += 1
                print(f"{a:8} {c} FAILED\n{traceback.format_exc()}", flush=True)
    return 1 if fails else 0


# --------------------------------------------------------------------------
# score
# --------------------------------------------------------------------------

def median(xs):
    return statistics.median(xs) if xs else None


def boot(xs: list, stat=median, n=2000, seed=20261015):
    if not xs:
        return [None, None]
    rng = random.Random(seed)
    vals = sorted(stat([rng.choice(xs) for _ in xs]) for _ in range(n))
    return [vals[int(0.025 * n)], vals[int(0.975 * n) - 1]]


def boot_pairs(pairs: list, stat, n=2000, seed=20261015):
    rng = random.Random(seed)
    vals = sorted(stat([rng.choice(pairs) for _ in pairs]) for _ in range(n))
    return [vals[int(0.025 * n)], vals[int(0.975 * n) - 1]]


def rate(k, n):
    return {"k": k, "n": n, "rate": round(k / n, 4) if n else None}


def cmd_score(out: Path) -> int:
    frozen = json.loads((out / "frozen.json").read_text(encoding="utf-8"))
    by = {d["case"]: d for d in load_set()}
    rows = []
    missing = []
    for doc in frozen["documents"]:
        c = doc["case"]
        try:
            a = json.loads((out / "ungated" / f"{c}.json").read_text(encoding="utf-8"))
            b = json.loads((out / "gated" / f"{c}.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            missing.append(c)
            continue
        v = b["verdict"] or {}
        reason = v.get("reason") if v.get("refuted") else \
            (v.get("protocol_reason") if v.get("protocol") == "REJECTED" else "")
        model_reason = reason if reason in FAILURE_PROFILES else "MISSING_CAPABILITY"
        econ = economics(by[c]["text"], model_reason, llm=True)
        truth = doc["truth_verdict"]
        st = a["status"]
        rows.append({
            "case": c, "truth": truth, "kind": doc["kind"],
            "a_status": st, "a_turns": a["turns"], "a_input": a["input_tokens"],
            "a_output": a["output_tokens"], "a_total": a["input_tokens"] + a["output_tokens"],
            "a_cached_input": a["cached_input_tokens"],
            "a_honest_stop": truth == "BLOCKED" and st in ("blocked", "impossible"),
            "a_hallucinated_completion": truth == "BLOCKED" and st == "achieved",
            "a_agrees_with_truth": (st in ("blocked", "impossible")) if truth == "BLOCKED"
                                   else st == "achieved",
            "b_label": v.get("label"), "b_reason": v.get("reason"), "b_error": b["error"],
            "b_calls": b["calls"], "b_input": b["input_tokens"], "b_output": b["output_tokens"],
            "b_total": b["input_tokens"] + b["output_tokens"], "checker_tokens": 0,
            "model_reason": model_reason, "model_reason_from_checker": reason in FAILURE_PROFILES,
            "modelled_waste_typical": econ.waste_typical.total_tokens,
            "modelled_waste_band": [econ.waste_low.total_tokens, econ.waste_high.total_tokens],
            "modelled_successful_run": econ.successful_run.total_tokens,
            "modelled_verification": econ.verification.total_tokens,
            "modelled_turns_typical": econ.profile.turns[1],
        })

    def arm_stats(rs, key):
        xs = [r[key] for r in rs]
        return {"n": len(xs), "median": median(xs), "ci95": boot(xs),
                "sum": sum(xs), "mean": round(sum(xs) / len(xs), 1) if xs else None}

    metrics = {"label": LABEL, "model": MODEL, "runtime": RUNTIME_NAME,
               "n_scored": len(rows), "missing": missing,
               "checker_tokens": "0 by construction (no model in the decision path; "
                                 "not measured because there is nothing to meter)",
               "per_class": {}}
    for cls in ("BLOCKED", "ACHIEVABLE", "ALL"):
        rs = [r for r in rows if cls == "ALL" or r["truth"] == cls]
        if not rs:
            continue
        m = {k: arm_stats(rs, k) for k in ("a_input", "a_output", "a_total", "a_turns",
                                           "b_input", "b_output", "b_total")}
        m["a_status_counts"] = {s: sum(r["a_status"] == s for r in rs)
                                for s in ("achieved", "blocked", "impossible", "timeout")}
        m["a_agrees_with_truth"] = rate(sum(r["a_agrees_with_truth"] for r in rs), len(rs))
        m["b_label_counts"] = {lab: sum(r["b_label"] == lab for r in rs)
                               for lab in ("IMPOSSIBLE", "ACHIEVABLE", "UNKNOWN", None)}
        m["modelled"] = {
            "waste_typical": arm_stats(rs, "modelled_waste_typical"),
            "successful_run": arm_stats(rs, "modelled_successful_run"),
            "verification": arm_stats(rs, "modelled_verification")}
        metrics["per_class"][cls] = {k: (v if not isinstance(v, dict) or "None" not in v
                                         else v) for k, v in m.items()}
        if None in m["b_label_counts"]:
            m["b_label_counts"]["parse_failure"] = m["b_label_counts"].pop(None)

    bl = [r for r in rows if r["truth"] == "BLOCKED"]
    ac = [r for r in rows if r["truth"] == "ACHIEVABLE"]
    if bl:
        pairs = [(r["a_total"], r["b_total"]) for r in bl if r["b_total"]]
        metrics["blocked"] = {
            "honest_stop": rate(sum(r["a_honest_stop"] for r in bl), len(bl)),
            "hallucinated_completion": rate(sum(r["a_hallucinated_completion"] for r in bl),
                                            len(bl)),
            "timeout": rate(sum(r["a_status"] == "timeout" for r in bl), len(bl)),
            "ratio_a_over_b_median_of_per_doc": median([a / b for a, b in pairs]),
            "ratio_a_over_b_median_of_per_doc_ci95": boot([a / b for a, b in pairs]),
            "ratio_a_over_b_ratio_of_medians": median([a for a, _ in pairs])
            / median([b for _, b in pairs]),
            "ratio_a_over_b_ratio_of_medians_ci95": boot_pairs(
                pairs, lambda ps: median([a for a, _ in ps]) / median([b for _, b in ps])),
            "gated_refuted": rate(sum(r["b_label"] == "IMPOSSIBLE" for r in bl), len(bl)),
            "modelled_leverage_median_of_per_doc": median(
                [r["modelled_waste_typical"] / r["modelled_verification"] for r in bl]),
            "modelled_waste_over_measured_a_ratio_of_medians":
                median([r["modelled_waste_typical"] for r in bl])
                / median([r["a_total"] for r in bl]),
            "modelled_verification_over_measured_b_ratio_of_medians":
                median([r["modelled_verification"] for r in bl])
                / median([r["b_total"] for r in bl]),
            "modelled_turns_typical_median": median([r["modelled_turns_typical"] for r in bl]),
            "measured_turns_median": median([r["a_turns"] for r in bl]),
        }
    if ac:
        pairs = [(r["a_total"], r["b_total"]) for r in ac if r["a_total"]]
        metrics["achievable"] = {
            "achieved": rate(sum(r["a_status"] == "achieved" for r in ac), len(ac)),
            "false_stop": rate(sum(r["a_status"] in ("blocked", "impossible") for r in ac),
                               len(ac)),
            "timeout": rate(sum(r["a_status"] == "timeout" for r in ac), len(ac)),
            "overhead_b_over_a_median_of_per_doc": median([b / a for a, b in pairs]),
            "overhead_b_over_a_median_of_per_doc_ci95": boot([b / a for a, b in pairs]),
            "overhead_b_over_a_ratio_of_medians": median([b for _, b in pairs])
            / median([a for a, _ in pairs]),
            "overhead_b_over_a_ratio_of_medians_ci95": boot_pairs(
                pairs, lambda ps: median([b for _, b in ps]) / median([a for a, _ in ps])),
            "gated_false_refutations": rate(sum(r["b_label"] == "IMPOSSIBLE" for r in ac),
                                            len(ac)),
            "modelled_successful_run_over_measured_a_ratio_of_medians":
                median([r["modelled_successful_run"] for r in ac])
                / median([r["a_total"] for r in ac]),
            "modelled_verification_over_measured_b_ratio_of_medians":
                median([r["modelled_verification"] for r in ac])
                / median([r["b_total"] for r in ac]),
            "modelled_successful_run_turns": 10,
            "measured_turns_median": median([r["a_turns"] for r in ac]),
        }
    spent_in = sum(r["a_input"] + r["b_input"] for r in rows)
    spent_out = sum(r["a_output"] + r["b_output"] for r in rows)
    metrics["experiment_tokens_spent"] = {"input": spent_in, "output": spent_out,
                                          "total": spent_in + spent_out,
                                          "note": "scored runs only; excludes trial runs"}
    (out / "results.json").write_text(json.dumps({"label": LABEL, "rows": rows}, indent=1)
                                      + "\n", encoding="utf-8")
    (out / "metrics.json").write_text(json.dumps(metrics, indent=1, default=str) + "\n",
                                      encoding="utf-8")
    print(json.dumps(metrics, indent=1, default=str))
    return 0 if not missing else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("prepare", "run", "score"))
    ap.add_argument("out", type=Path)
    ap.add_argument("--only", default="")
    ap.add_argument("--arm", choices=("ungated", "gated", "both"), default="both")
    a = ap.parse_args()
    out = a.out if a.out.is_absolute() else ROOT / a.out
    if a.cmd == "prepare":
        return cmd_prepare(out)
    if a.cmd == "run":
        arms = ["ungated", "gated"] if a.arm == "both" else [a.arm]
        return cmd_run(out, [x for x in a.only.split(",") if x] or None, arms)
    return cmd_score(out)


if __name__ == "__main__":
    raise SystemExit(main())

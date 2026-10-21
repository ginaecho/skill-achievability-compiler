"""Evaluate a document's requirements against a runtime manifest (Rdet).

    intent_from_text(doc)  +  data/runtimes/<name>.json  ->  Evaluation

The deterministic arm Rdet of Addendum C (fix F-g).  It reads no model
output and probes nothing: every requirement the natural-language reader
(`env.nl`) extracted is given one status from the manifest alone,

    available | installable | unavailable | unknown

with a `basis` naming the manifest field (and entry) that decided it.  A
hard requirement (one in the intent's `goal`) that is unavailable is a
refutation, reason REQUIREMENT_UNAVAILABLE, and its evidence lines are the
witness.  A field the manifest does not have decides nothing: hosts and
programs are then unknown, never unavailable, so the additive fields
(`egress_allow`, `egress_deny`, `available_programs`, `unavailable_programs`)
can only add refutations where a manifest is explicit.

Pure and deterministic: no network, no subprocess, no environment reads.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from .nl import intent_from_text, routes

REASON = "REQUIREMENT_UNAVAILABLE"
STATUSES = ("available", "installable", "unavailable", "unknown")
INSTALL_MODES = ("installable", "session-installable")

# Tokens too generic to name a service in a `lacks` sentence or a tool name.
GENERIC = frozenset("""account accounts api key keys token tokens secret secrets server mcp os
    cli id client auth access password connection string the a an and or of for to hub
    cloud service services plugin claude ai com io dev app sdk tool tools""".split())
# Runtime tools that are not connectors: an MCP server never matches one of these.
NOT_CONNECTORS = frozenset("""bash read write edit web_fetch web_search ask_user agent skill
    tasks artifact send_user_file push_notification mcp_resources browser code_interpreter
    mcp openapi a2a search windows_os reply""".split())
# Claude Code tool names (frontmatter `allowed-tools`) -> manifest tool keys.
CLAUDE_TOOLS = {"read": "read", "glob": "read", "grep": "read", "ls": "read",
                "write": "write", "edit": "edit", "multiedit": "edit", "notebookedit": "edit",
                "bash": "bash", "webfetch": "web_fetch", "websearch": "web_search",
                "task": "agent", "agent": "agent", "askuserquestion": "ask_user",
                "skill": "skill", "sendmessage": "agent", "taskcreate": "tasks",
                "tasklist": "tasks", "taskget": "tasks", "taskupdate": "tasks",
                "taskstop": "tasks", "monitor": "tasks", "croncreate": "tasks"}
# A lacks sentence that closes a class: no credentials for external services,
# no connectors beyond the listed tools.
CREDENTIALS_CLOSED = re.compile(r"\b(api keys?|credentials|logins?|accounts)\b.*"
                                r"\bexternal services?\b", re.I)
CONNECTORS_CLOSED = re.compile(r"\bconnectors?\b.*\bother than the tools listed\b", re.I)
# What a lacks entry has to be about before a name in it decides a requirement:
# "Azure endpoints" in a network sentence does not say there is no Azure account.
ABOUT_CREDENTIALS = re.compile(r"\b(credentials?|accounts?|api keys?|logins?|secrets?)\b", re.I)
ABOUT_CONNECTORS = re.compile(r"\b(connectors?|integrations?|mcp)\b", re.I)
CREDENTIAL_SUFFIX = re.compile(r"_(API_KEY|API_TOKEN|ACCESS_TOKEN|AUTH_TOKEN|TOKEN|SECRET_KEY|"
                               r"SECRET|ACCESS_KEY_ID|SECRET_ACCESS_KEY|CLIENT_SECRET|"
                               r"CLIENT_ID|PASSWORD|CONNECTION_STRING|PROFILE)$")


@dataclass(frozen=True)
class ManifestFacts:
    name: str
    description: str = ""
    tools: dict = field(default_factory=dict)
    grants: tuple = ()
    lacks: tuple = ()
    software: str = "installable"
    egress_allow: tuple | None = None        # None: the manifest does not say
    egress_deny: tuple | None = None
    available_programs: tuple | None = None
    unavailable_programs: tuple | None = None

    @staticmethod
    def from_dict(d: dict) -> ManifestFacts:
        def opt(key):
            v = d.get(key)
            return None if v is None else tuple(str(x) for x in v)
        return ManifestFacts(str(d.get("name", "")), str(d.get("description", "")),
                             dict(d.get("tools") or {}), tuple(d.get("grants") or ()),
                             tuple(d.get("lacks") or ()), str(d.get("software", "installable")),
                             opt("egress_allow"), opt("egress_deny"),
                             opt("available_programs"), opt("unavailable_programs"))


def load_manifest_facts(name_or_path) -> ManifestFacts:
    """The raw manifest JSON, by name from data/runtimes or by path."""
    if isinstance(name_or_path, ManifestFacts):
        return name_or_path
    if isinstance(name_or_path, dict):
        return ManifestFacts.from_dict(name_or_path)
    p = Path(str(name_or_path))
    if p.suffix == ".json" and p.exists():
        return ManifestFacts.from_dict(json.loads(p.read_text(encoding="utf-8")))
    ref = resources.files("skillc").joinpath(f"data/runtimes/{name_or_path}.json")
    try:
        return ManifestFacts.from_dict(json.loads(ref.read_text(encoding="utf-8")))
    except FileNotFoundError:
        raise KeyError(f"unknown runtime {name_or_path!r}") from None


@dataclass
class Status:
    cond: str
    hard: bool
    status: str
    basis: str
    evidence: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"requirement": self.cond, "hard": self.hard, "status": self.status,
                "basis": self.basis, "evidence": list(self.evidence)}


@dataclass
class Evaluation:
    runtime: str
    statuses: list
    blocking: list
    unknown: list
    verdict: str
    reason: str | None
    witness: list

    def to_dict(self) -> dict:
        return {"schema": "skillc.requirement_eval/1", "runtime": self.runtime,
                "verdict": self.verdict, "reason": self.reason, "blocking": list(self.blocking),
                "unknown": list(self.unknown), "witness": list(self.witness),
                "requirements": [s.to_dict() for s in self.statuses]}


# --------------------------------------------------------------------------
# Matching
# --------------------------------------------------------------------------

def _host_rule(host: str, patterns) -> str | None:
    """The pattern that matches `host`: exact, `*.suffix` (subdomains only) or `*`."""
    host = host.lower().rstrip(".")
    for p in patterns or ():
        q = p.lower()
        if q == host:
            return p
    best = None
    for p in patterns or ():
        q = p.lower()
        if q == "*" or (q.startswith("*.") and host.endswith(q[1:])):
            if best is None or len(q) > len(best):
                best = p
    return best


def egress_status(host: str, facts: ManifestFacts) -> tuple[str, str]:
    exact_allow = host.lower() in {h.lower() for h in facts.egress_allow or ()}
    exact_deny = host.lower() in {h.lower() for h in facts.egress_deny or ()}
    if exact_deny:
        return "unavailable", f"egress_deny: {host}"
    if exact_allow:
        return "available", f"egress_allow: {host}"
    allow, deny = _host_rule(host, facts.egress_allow), _host_rule(host, facts.egress_deny)
    if allow and (not deny or len(allow) >= len(deny)):
        return "available", f"egress_allow: {allow}"
    if deny:
        return "unavailable", f"egress_deny: {deny}"
    return "unknown", "no egress_allow or egress_deny entry matches"


def _program_listed(name: str, listed) -> str | None:
    for p in listed or ():
        if p == "*" or p.lower() == name.lower():
            return p
    return None


def _tokens(name: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", name.lower()) if t and t not in GENERIC]


def _lacks_naming(tokens: list[str], facts: ManifestFacts, about=None) -> str | None:
    """The first lacks entry (about the right subject, if `about` is given) that
    names one of `tokens` as a word."""
    for entry in facts.lacks:
        if about and not about.search(entry):
            continue
        for t in tokens:
            if len(t) >= 3 and re.search(rf"\b{re.escape(t)}s?\b", entry, re.I):
                return entry
    return None


def _grant_or_tool(tokens: list[str], facts: ManifestFacts, connectors_only=False) -> str | None:
    if not tokens:
        return None
    joined = "_".join(tokens)
    if connectors_only:
        hit = _tool_match(tokens, joined, facts)
        if hit:
            return hit
    for g in facts.grants:
        gl = g.lower()
        if gl in (joined, f"{joined}_account") or (
                gl.endswith("_account") and set(_tokens(gl[:-8])) and
                set(_tokens(gl[:-8])) <= set(tokens)):
            return f"grants: {g}"
    return _tool_match(tokens, joined, facts)


def _tool_match(tokens: list[str], joined: str, facts: ManifestFacts) -> str | None:
    """A connector tool of the manifest whose name tokens the requirement names."""
    for t in facts.tools:
        if t.lower() in NOT_CONNECTORS:
            continue
        key = t.lower().removesuffix("_mcp")
        mine = set(_tokens(key))
        if key == joined or (mine and mine <= set(tokens)):
            return f"tools: {t}"
    return None


def _credential_account(name: str) -> str | None:
    for account, groups in routes()["accounts"].items():
        if any(name in group for group in groups):
            return account
    return None


# --------------------------------------------------------------------------
# One requirement
# --------------------------------------------------------------------------

def _routes_status(cond: str, intent: dict, facts: ManifestFacts) -> tuple[str, str]:
    """Installability of a program or module through the install routes the
    intent carries (claude_routes.json and the document's own commands)."""
    ops = [op for op in intent.get("operations") or [] if cond in (op.get("adds") or [])]
    if not ops and cond.startswith("program:"):
        route = routes()["programs"].get(cond.split(":", 1)[1])
        if route:
            ops = [{"id": f"route_{route[0]}", "needs": routes()["installers"][route[0]]}]
    if not ops:
        return "unknown", f"software: {facts.software}; no known install route"
    denied = []
    for op in ops:
        blocked = None
        for need in op.get("needs") or []:
            if "egress" in need:
                st, basis = egress_status(need["egress"], facts)
                if st == "unavailable":
                    blocked = basis
            elif "program" in need:
                hit = _program_listed(need["program"], facts.unavailable_programs)
                if hit and not _program_listed(need["program"], facts.available_programs):
                    blocked = f"unavailable_programs: {hit}"
            if blocked:
                break
        if not blocked:
            return "installable", f"software: {facts.software}; route {op.get('id')}"
        denied.append(f"{op.get('id')} ({blocked})")
    return "unavailable", f"software: {facts.software}; every install route refused: " \
                          + "; ".join(denied)


def _program_status(cond: str, name: str, intent: dict, facts: ManifestFacts):
    if _program_listed(name, facts.available_programs):
        return "available", f"available_programs: {name}"
    hit = _program_listed(name, facts.unavailable_programs)
    if hit:
        return "unavailable", f"unavailable_programs: {hit}"
    if facts.software == "none":
        return "unavailable", "software: none"
    if facts.software in INSTALL_MODES:
        return _routes_status(cond, intent, facts)
    return "unknown", f"software: {facts.software}"


def _named_status(name: str, facts: ManifestFacts, closed=None, about=None,
                  connectors_only=False):
    tokens = _tokens(name)
    hit = _grant_or_tool(tokens, facts, connectors_only)
    if hit:
        return "available", hit
    entry = _lacks_naming(tokens, facts, about)
    if entry:
        return "unavailable", f"lacks: {entry}"
    if closed:
        for entry in facts.lacks:
            if closed.search(entry):
                return "unavailable", f"lacks: {entry}"
    return "unknown", "no tool, grant or lacks entry names it"


def requirement_status(cond: str, intent: dict, facts: ManifestFacts) -> tuple[str, str]:
    kind, _, name = cond.partition(":")
    if kind == "deliverable":
        return "available", "work the agent does by itself"
    if kind == "egress":
        return egress_status(name, facts)
    if kind == "program":
        return _program_status(cond, name, intent, facts)
    if kind == "pymodule":
        if facts.software == "none":
            return "unavailable", "software: none"
        if _program_listed("python", facts.unavailable_programs) == "*":
            return "unavailable", "unavailable_programs: *"
        if facts.software in INSTALL_MODES:
            return _routes_status(cond, intent, facts)
        return "unknown", f"software: {facts.software}"
    if kind == "installer":
        needs = routes()["installers"].get(name, [])
        results = []
        for need in needs:
            if "egress" in need:
                results.append(egress_status(need["egress"], facts))
            elif "program" in need:
                results.append(_program_status(f"program:{need['program']}",
                                               need["program"], intent, facts))
        if facts.software == "none":
            return "unavailable", "software: none"
        for st, basis in results:
            if st == "unavailable":
                return st, basis
        if results and all(st == "available" for st, _ in results):
            return "available", "; ".join(b for _, b in results)
        return "unknown", "; ".join(b for _, b in results) or "no installer route"
    if kind == "daemon":
        if name.lower() in {g.lower() for g in facts.grants}:
            return "available", f"grants: {name}"
        hit = _program_listed(name, facts.unavailable_programs)
        if hit:
            return "unavailable", f"unavailable_programs: {hit}"
        entry = _lacks_naming(_tokens(name), facts)
        return ("unavailable", f"lacks: {entry}") if entry else \
            ("unknown", "no grant, unavailable_programs or lacks entry names it")
    if kind == "credential":
        account = _credential_account(name)
        if account and account in facts.grants:
            return "available", f"grants: {account}"
        service = CREDENTIAL_SUFFIX.sub("", name)
        return _named_status(service, facts, CREDENTIALS_CLOSED, ABOUT_CREDENTIALS)
    if kind == "account":
        return _named_status(name, facts, CREDENTIALS_CLOSED, ABOUT_CREDENTIALS)
    if kind == "platform":
        if name.lower() in {g.lower() for g in facts.grants}:
            return "available", f"grants: {name}"
        entry = _lacks_naming(_tokens(name), facts)
        return ("unavailable", f"lacks: {entry}") if entry else \
            ("unknown", "no grant or lacks entry names it")
    if kind == "mcp":
        return _named_status(name, facts, CONNECTORS_CLOSED, ABOUT_CONNECTORS,
                             connectors_only=True)
    if kind == "tool":
        return _tool_status(name, facts)
    return "unknown", f"no rule for requirement kind {kind!r}"


def _tool_status(name: str, facts: ManifestFacts) -> tuple[str, str]:
    """A frontmatter tool; "Bash Read" (a space-separated list) is each of its words."""
    parts = name.split() or [name]
    found = []
    for part in parts:
        key = CLAUDE_TOOLS.get(part.lower(), part.lower())
        if key in facts.tools or part in facts.tools:
            found.append(f"tools: {key if key in facts.tools else part}")
        elif key == "bash" and _program_listed("bash", facts.unavailable_programs) == "*":
            return "unavailable", "unavailable_programs: *"
        else:
            return "unknown", f"no manifest tool matches {part}"
    return "available", "; ".join(found)


# --------------------------------------------------------------------------
# The evaluation
# --------------------------------------------------------------------------

def evaluate(intent: dict, facts) -> Evaluation:
    facts = load_manifest_facts(facts)
    evidence = intent.get("evidence") or {}
    statuses = []
    for hard, conds in ((True, intent.get("goal") or []), (False, intent.get("optional") or [])):
        for cond in conds:
            st, basis = requirement_status(cond, intent, facts)
            statuses.append(Status(cond, hard, st, basis, list(evidence.get(cond, []))))
    blocking = [s.cond for s in statuses if s.hard and s.status == "unavailable"]
    unknown = [s.cond for s in statuses if s.status == "unknown"]
    witness = [{"requirement": s.cond, "status": s.status, "basis": s.basis,
                "evidence": list(s.evidence)}
               for s in statuses if s.hard and s.status == "unavailable"]
    return Evaluation(facts.name, statuses, blocking, unknown,
                      "IMPOSSIBLE" if blocking else "ACHIEVABLE",
                      REASON if blocking else None, witness)


def refute_text(text: str, manifest, name: str | None = None) -> Evaluation:
    """Read `text` with `intent_from_text`, then evaluate it against `manifest`."""
    return evaluate(intent_from_text(text, name=name), manifest)


def manifest_facts(runtime) -> ManifestFacts | None:
    """The manifest Rdet reads for `runtime`, or None when there is none.

    `runtime` is a manifest name or path, a dict, a ManifestFacts, or a
    `frontend.runtime.Runtime`.  A Runtime equal to the built-in manifest of
    its name reads that manifest's file (with its additive fields); any other
    Runtime gives only its own fields (tools, grants, lacks, software), so
    the additive fields are unknown and decide nothing."""
    if runtime is None:
        return None
    from ..frontend.runtime import Runtime, load_runtime
    if isinstance(runtime, Runtime):
        try:
            if load_runtime(runtime.name) == runtime:
                return load_manifest_facts(runtime.name)
        except (KeyError, ValueError, OSError):
            pass
        return ManifestFacts(runtime.name, runtime.description, dict(runtime.tools),
                             tuple(runtime.grants), tuple(runtime.lacks), runtime.software)
    return load_manifest_facts(runtime)


def witness_lines(ev) -> list[str]:
    """One line per blocking requirement: `kind:name: basis; evidence`.
    `ev` is an Evaluation or a list of its witness entries."""
    out = []
    for w in (ev.witness if isinstance(ev, Evaluation) else ev):
        line = f"{w['requirement']}: {w['basis']}"
        if w.get("evidence"):
            line += "; evidence " + " | ".join(w["evidence"])
        out.append(line)
    return out



# --------------------------------------------------------------------------
# A typed free-name requirement (Rllm, Addendum E-b)
# --------------------------------------------------------------------------
# Rllm's requirements are `kind` + a free `name` written by a model ("AWS
# account credentials / SSO session", "docker daemon", "api.openai.com").
# typed_requirement_status decides one from the manifest alone, with the
# same rule as above: a field or sentence the manifest does not have decides
# nothing, so anything not decided is `unknown`, never `unavailable`.

TYPED_KINDS = ("program", "egress", "credential", "account", "connector", "tool",
               "platform", "hardware")
# What a lacks entry is about.  Programs, platforms and hardware are decided
# only by entries about none of network, credentials or connectors: "Azure
# endpoints" in the network sentence says nothing about the Azure CLI.
ABOUT_NETWORK = re.compile(r"\b(network|egress|hosts?|proxy|internet)\b", re.I)
HOST_RE = re.compile(r"(?<![\w.-])(\*\.|<[^<>\s]+>\.)?((?:[a-z0-9-]+\.)+[a-z]{2,})(?![\w-])",
                     re.I)
ENV_VAR_RE = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")
# Host labels too generic to name a service ("docs.x.com" names x, not docs).
HOST_LABEL_STOP = frozenset("""www api docs doc com org net io dev app co uk cloud
    registry files objects raw codeload proxy sum archive security console""".split())
# Claude Code built-in tools the CLAUDE_TOOLS map does not name: they exist in
# every Claude Code session; a requirement naming one is never unavailable.
CLAUDE_BUILTIN_EXTRA = {"todowrite": "tasks", "todoread": "tasks", "notebookread": "read",
                        "bashoutput": "bash", "killshell": "bash", "killbash": "bash",
                        "slashcommand": "skill", "exitplanmode": None,
                        "enterplanmode": None, "listmcpresourcestool": "mcp_resources",
                        "readmcpresourcetool": "mcp_resources", "toolsearch": None}
MCP_TOOL_RE = re.compile(r"^mcp__([A-Za-z0-9_-]+?)__")
# A tool name is one identifier (js_repl, image_gen, codex.emitImage).
TOOL_NAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]*")
FILE_NAME_RE = re.compile(r"\.(py|md|sh|js|ts|json|ya?ml|txt|toml|ps1|rb|go)$", re.I)


def _lacks_entries(facts: ManifestFacts, subject: str) -> list[str]:
    """Lacks entries about `subject`: `network`, `credentials`, `connectors`, or
    `other` (about none of the three: hardware, daemons, operating systems)."""
    out = []
    for e in facts.lacks:
        net = bool(ABOUT_NETWORK.search(e))
        cred = bool(ABOUT_CREDENTIALS.search(e))
        conn = bool(ABOUT_CONNECTORS.search(e)) or bool(CONNECTORS_CLOSED.search(e))
        if (subject == "network" and net) or (subject == "credentials" and cred) or \
                (subject == "connectors" and conn) or \
                (subject == "other" and not (net or cred or conn)):
            out.append(e)
    return out


# Words of a free name too weak to tie it to a lacks entry on their own
# ("Visual Studio Code" is not "Visual Studio"; "Android Studio" neither).
NAME_WEAK = frozenset("""visual studio code desktop toolkit toolchain toolchains build builds
    command line runtime engine framework library package packages version pro professional
    community edition host machine local system driver drivers support gui other physical
    devices hardware and with the for""".split())


def _entry_naming(tokens: list[str], entries: list[str]) -> str | None:
    tokens = [t for t in tokens if t not in NAME_WEAK]
    for entry in entries:
        for t in tokens:
            if len(t) >= 3 and re.search(rf"\b{re.escape(t)}s?\b", entry, re.I):
                return entry
    return None


def _hosts_in(name: str) -> list[str]:
    """Host names written in `name`; `*.x.y` and `<project>.x.y` become `sub.x.y`
    (a subdomain, which the manifest's `*.` patterns match)."""
    out = []
    for m in HOST_RE.finditer(name.replace("https://", " ").replace("http://", " ")):
        host = m.group(2).lower().rstrip(".")
        out.append(("sub." + host) if m.group(1) else host)
    return out


def _host_labels(pattern: str) -> set[str]:
    labels = [x for x in pattern.lower().lstrip("*.").split(".") if x]
    return {x for x in labels[:-1] if x not in HOST_LABEL_STOP and len(x) >= 3}


def _typed_egress(name: str, facts: ManifestFacts) -> tuple[str, str]:
    hosts = _hosts_in(name)
    if hosts:
        res = [egress_status(h, facts) for h in hosts]
        for st, basis in res:
            if st == "available":
                return st, basis
        bad = [(st, b) for st, b in res if st == "unavailable"]
        if bad and len(bad) == len(res):
            return bad[0]
        return "unknown", "; ".join(b for _, b in res)
    # No host written: the service the requirement names, against the host
    # labels of the egress lists ("Hugging Face Hub" -> huggingface.co).
    toks = set(_tokens(name)) | {"".join(_tokens(name))}
    allow = [p for p in facts.egress_allow or () if _host_labels(p) & toks]
    deny = [p for p in facts.egress_deny or () if _host_labels(p) & toks]
    if allow and not deny:
        return "available", f"egress_allow: {allow[0]}"
    if deny and not allow:
        return "unavailable", f"egress_deny: {deny[0]}"
    return "unknown", "no host in the requirement, and no egress entry names its service"


def _typed_program(name: str, facts: ManifestFacts) -> tuple[str, str]:
    toks = set(re.findall(r"[a-z0-9]+", name.lower()))
    for listed, field_ in ((facts.available_programs, "available_programs"),
                           (facts.unavailable_programs, "unavailable_programs")):
        for p in listed or ():
            ptoks = set(re.findall(r"[a-z0-9]+", p.lower()))
            if p == "*" or (ptoks and ptoks <= toks):
                st = "available" if field_ == "available_programs" else "unavailable"
                return st, f"{field_}: {p}"
    if facts.software == "none":
        return "unavailable", "software: none"
    entry = _entry_naming(_tokens(name), _lacks_entries(facts, "other"))
    if entry:
        return "unavailable", f"lacks: {entry}"
    progs = routes()["programs"]
    for w in re.findall(r"[a-z0-9][a-z0-9_.+-]*", name.lower()):
        if w in progs:
            return requirement_status(f"program:{w}", {}, facts)
    if facts.software in INSTALL_MODES:
        return "unknown", f"software: {facts.software}; no known install route"
    return "unknown", f"software: {facts.software}"


def _typed_account(name: str, facts: ManifestFacts) -> tuple[str, str]:
    tokens = _tokens(name)
    if not tokens:
        return "unknown", "the requirement names no service"
    hit = _grant_or_tool(tokens, facts)
    if hit:
        return "available", hit
    entry = _entry_naming(tokens, _lacks_entries(facts, "credentials"))
    if entry:
        return "unavailable", f"lacks: {entry}"
    for entry in facts.lacks:
        if CREDENTIALS_CLOSED.search(entry):
            return "unavailable", f"lacks: {entry}"
    return "unknown", "no tool, grant or lacks entry names it"


def _typed_credential(name: str, facts: ManifestFacts) -> tuple[str, str]:
    bare = name.strip().strip("$`")
    if ENV_VAR_RE.fullmatch(bare) and not CREDENTIAL_SUFFIX.search(bare):
        # BURP_JAR, DATABASE_URL: a setting, not a secret of a named service
        return "unknown", f"{bare} is not a credential-shaped variable"
    for var in ENV_VAR_RE.findall(name):
        st, basis = requirement_status(f"credential:{var}", {}, facts)
        if st == "available":
            return st, basis
    return _typed_account(name, facts)


def _typed_connector(name: str, facts: ManifestFacts) -> tuple[str, str]:
    m = MCP_TOOL_RE.match(name.strip())
    if m:
        name = m.group(1)
    tokens = _tokens(name)
    if not tokens:
        return "unknown", "the requirement names no service"
    hit = _tool_match(tokens, "_".join(tokens), facts)
    if hit:
        return "available", hit
    for g in facts.grants:
        gt = set(_tokens(g[:-8])) if g.lower().endswith("_account") else set()
        if gt and gt <= set(tokens):
            return "available", f"grants: {g}"
    for entry in facts.lacks:
        if CONNECTORS_CLOSED.search(entry):
            return "unavailable", f"lacks: {entry}"
    entry = _entry_naming(tokens, _lacks_entries(facts, "connectors"))
    if entry:
        return "unavailable", f"lacks: {entry}"
    return "unknown", "no tool or lacks entry names it"


def _typed_tool(name: str, facts: ManifestFacts) -> tuple[str, str]:
    raw = name.strip()
    if MCP_TOOL_RE.match(raw):
        return _typed_connector(raw, facts)
    key = re.sub(r"[^a-z0-9_]", "", raw.split("(")[0].strip().lower().replace(" ", "_"))
    flat = key.replace("_", "")
    for k in (flat, key):
        if k in CLAUDE_TOOLS and CLAUDE_TOOLS[k] in facts.tools:
            return "available", f"tools: {CLAUDE_TOOLS[k]}"
        if k in facts.tools:
            return "available", f"tools: {k}"
    if flat in CLAUDE_BUILTIN_EXTRA:
        t = CLAUDE_BUILTIN_EXTRA[flat]
        if t and t in facts.tools:
            return "available", f"tools: {t}"
        return "unknown", f"Claude Code built-in tool {raw}"
    if flat == "bash" and _program_listed("bash", facts.unavailable_programs) == "*":
        return "unavailable", "unavailable_programs: *"
    if not TOOL_NAME_RE.fullmatch(raw) or FILE_NAME_RE.search(raw):
        # "git diff", "scripts/run.py", "guide.md": a command or a file, not a tool
        return "unknown", f"{raw!r} is not a tool name"
    return _typed_connector(raw, facts)


def _typed_platform(name: str, facts: ManifestFacts) -> tuple[str, str]:
    low = name.lower()
    for g in facts.grants:
        if re.search(rf"\b{re.escape(g.lower())}\b", low):
            return "available", f"grants: {g}"
    entry = _entry_naming(_tokens(name), _lacks_entries(facts, "other"))
    if entry:
        return "unavailable", f"lacks: {entry}"
    return "unknown", "no grant or lacks entry names it"


def typed_requirement_status(kind: str, name: str, facts) -> tuple[str, str]:
    """Status and basis of one typed free-name requirement against `facts`.

    egress     the hosts written in the name, by egress_status; with no host
               written, the service the name names against the host labels of
               egress_allow / egress_deny
    program    available/unavailable_programs, software mode, the lacks
               entries about neither network, credentials nor connectors, then
               the known install routes
    credential an environment variable in the name that a grant covers,
               otherwise as an account
    account    grants and connector tools, the lacks entry about credentials
               that names it, then the lacks sentence closing external services
    connector  the manifest's connector tools and account grants, then the
               lacks sentence closing other integrations
    tool       Claude Code tool names against the manifest tools; any other
               name as a connector
    platform,  grants, then the lacks entries about neither network,
    hardware   credentials nor connectors
    Anything else, and anything these do not decide, is `unknown`."""
    facts = load_manifest_facts(facts)
    kind = (kind or "").strip().lower()
    name = str(name or "").strip()
    if not name:
        return "unknown", "empty name"
    if kind == "egress":
        return _typed_egress(name, facts)
    if kind == "program":
        return _typed_program(name, facts)
    if kind == "credential":
        return _typed_credential(name, facts)
    if kind == "account":
        return _typed_account(name, facts)
    if kind == "connector":
        return _typed_connector(name, facts)
    if kind == "tool":
        return _typed_tool(name, facts)
    if kind in ("platform", "hardware"):
        return _typed_platform(name, facts)
    return "unknown", f"no rule for requirement kind {kind!r}"

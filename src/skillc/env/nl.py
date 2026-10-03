"""Natural-language front-end: what a SKILL.md / agent.md needs from its runtime.

    skill text  ->  skillc.intent/1 for the Claude catalogue

Deterministic and evidence-carrying: every requirement names the line it came
from.  It reads what the document *does*, not what it mentions:

    shell blocks      the programs a command runs; packages it installs (pip,
                      npm, apt: the installer and its registry); hosts a
                      command fetches from (curl, wget, git clone, docker pull)
    python blocks     imported modules outside the standard library
    credentials       variables like OPENAI_API_KEY that the text sets or reads
    accounts, platforms, MCP servers
                      the tool-policy library's evidence (frontend.toolpolicy)
                      and `mcp__server__tool` references
    frontmatter       allowed-tools / tools: the Claude tools it uses

A missing program, module or package counts as reachable when an installer
can install it here (`data/env/claude_routes.json`); the installer's own
needs are checked like any other.  A requirement whose evidence sits in an
optional passage ("optional", "alternatively", "if you have ...") is kept in
`optional` and does not decide the overall verdict.
"""
from __future__ import annotations

import json
import re
import shlex
import sys
from dataclasses import dataclass, field
from importlib import resources
from urllib.parse import urlparse

from ..frontend.markdown import parse_frontmatter
from ..frontend.toolpolicy import load_library, match

SHELL_LANGS = {"", "bash", "sh", "shell", "console", "zsh", "terminal", "shell-session"}
PY_LANGS = {"python", "py", "python3"}
FENCE_RE = re.compile(r"^[ \t]*(```+|~~~+)[ \t]*([\w+-]*)[^\n]*\n(.*?)^[ \t]*\1[ \t]*$",
                      re.S | re.M)
BUILTINS = frozenset("""cd echo export set unset source . if then else elif fi for do done
    while until case esac true false test [ [[ read exit return eval exec alias printf
    local declare function trap wait shift time nohup env sudo xargs type command""".split())
COMMON = frozenset("""ls cat cp mv rm mkdir rmdir touch chmod chown ln find grep sed awk head
    tail sort uniq wc cut tr tee diff file stat du df date sleep kill ps which basename
    dirname pwd realpath mktemp tar gzip gunzip zip unzip bash sh zsh""".split())
# Words that open a line of code in another language: an untagged or mislabelled
# block holding JavaScript or Python is not a command line.
KEYWORDS = frozenset("""const let var await async function return import from export def
    class break continue try catch except raise with yield lambda print new this self
    public private static void int string package interface type enum struct fn use""".split())
# Programs recognised in untagged blocks and in inline code (a tagged shell
# block may run any program).
KNOWN = frozenset("""git curl wget gh docker kubectl helm terraform ansible node npm npx
    yarn pnpm bun bunx deno python python3 pip pip3 uv pipx poetry conda go cargo rustc
    rustup java javac mvn gradle dotnet ruby gem bundle php composer swift xcodebuild
    flutter dart psql mysql sqlite3 redis-cli mongosh jq yq ffmpeg ffprobe convert magick
    pdftoppm pdfinfo pdftotext pdfimages pdffonts qpdf pdftk tesseract pandoc pdflatex
    latexmk soffice libreoffice aws az gcloud gsutil bq firebase vercel netlify wrangler
    supabase make cmake gcc clang tsc eslint prettier pytest ruff black mypy jupyter
    markitdown mmdc dot hf huggingface-cli yt-dlp playwright brew apt apt-get choco winget
    code claude rg fd openssl ssh scp rsync unzip""".split())
# Commands that install a tool: (program, words that must follow it)
INSTALL_VERBS = {"npm": ("install", "i", "add"), "pnpm": ("add", "install", "i"),
                 "yarn": ("global",), "pipx": ("install",), "cargo": ("install",),
                 "go": ("install",), "dotnet": ("tool",), "brew": ("install",),
                 "winget": ("install",), "choco": ("install",), "scoop": ("install",),
                 "uv": ("tool",), "gem": ("install",)}
# Where an installer downloads from (pip, npm and apt are in claude_routes.json)
REGISTRIES = {"cargo": ("index.crates.io", "static.crates.io"), "go": ("proxy.golang.org",),
              "dotnet": ("api.nuget.org",), "gem": ("rubygems.org",),
              "pipx": ("pypi.org", "files.pythonhosted.org"), "uv": ("pypi.org",),
              "npm": ("registry.npmjs.org",), "pnpm": ("registry.npmjs.org",),
              "yarn": ("registry.npmjs.org",), "brew": ("formulae.brew.sh",)}
SCRIPT_SHELLS = {"bash", "sh", "zsh", "iex", "pwsh", "powershell"}
# A download of one of these is sample input data, which any other file can replace
DATA_EXT = re.compile(r"\.(ogg|mp3|mp4|wav|webm|png|jpe?g|gif|svg|csv|tsv|json|txt|pdf|"
                      r"parquet|xml|html?)$", re.I)
INSTALLER_NAMES = {"winget", "choco", "chocolatey", "scoop", "brew", "homebrew"}
LOCAL_MODULES = frozenset("scripts src lib utils util core helpers app tests config".split())
CREDENTIAL_RE = re.compile(
    r"\b([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*_(?:API_KEY|API_TOKEN|ACCESS_TOKEN|AUTH_TOKEN|TOKEN|"
    r"SECRET_KEY|SECRET|ACCESS_KEY_ID|SECRET_ACCESS_KEY|CLIENT_SECRET|PASSWORD|"
    r"CONNECTION_STRING))\b")
PLACEHOLDER = re.compile(r"^(YOUR|MY|EXAMPLE|SAMPLE|DUMMY|FAKE)_")
OPTIONAL_RE = re.compile(
    r"\b(optional(ly)?|alternatively|alternative|if (you|the user|your team) (have|has|use|"
    r"want|prefer|need)|if available|if installed|when available|for example|e\.g\.|"
    r"such as|instead of|troubleshoot\w*|advanced|faq)\b", re.I)
HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$")
MCP_RE = re.compile(r"\bmcp__([A-Za-z0-9_-]+?)__")
INLINE_RE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
NPM_RE = re.compile(r"\b(npm|yarn|pnpm|node)\b", re.I)
PIP_LINE_RE = re.compile(r"\bpip\b|\bpython (packages?|librar(y|ies)|modules?)\b", re.I)
IMPORT_RE = re.compile(r"\s*(?:from\s+([A-Za-z_]\w*)[\w.]*\s+import|import\s+([A-Za-z_]\w*))")
PIP_NAMES = {"cv2": "opencv-python", "PIL": "pillow", "sklearn": "scikit-learn",
             "yaml": "pyyaml", "bs4": "beautifulsoup4", "docx": "python-docx",
             "pptx": "python-pptx", "fitz": "pymupdf", "dotenv": "python-dotenv",
             "dateutil": "python-dateutil", "jwt": "pyjwt", "Crypto": "pycryptodome"}
_MODULE_OF = {v: k for k, v in PIP_NAMES.items()}


@dataclass
class Requirement:
    cond: str
    title: str
    needs: list[dict]
    fix: str
    installs: list[dict] = field(default_factory=list)   # {"id","title","needs","how"}
    evidence: list[str] = field(default_factory=list)
    core: bool = False


@dataclass
class _DocRoute:
    """An install command in the document: a way to get a tool, not a need.

    `provides` holds the package names and URL it installs from; it becomes an
    alternative way to satisfy the program it names, carrying its own needs."""
    line: int
    text: str
    tokens: list[str]
    provides: list[str]
    needs: list[dict]


def routes() -> dict:
    raw = resources.files("skillc").joinpath("data/env/claude_routes.json")
    return json.loads(raw.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Reading the document
# --------------------------------------------------------------------------

def _optional_lines(lines: list[str]) -> set[int]:
    """1-based lines in an optional passage (the line itself, or its section)."""
    out, section_optional = set(), False
    for no, line in enumerate(lines, 1):
        heading = HEADING_RE.match(line)
        if heading:
            section_optional = bool(OPTIONAL_RE.search(heading.group(1)))
        if section_optional or OPTIONAL_RE.search(line):
            out.add(no)
    return out


def _blocks(text: str) -> list[tuple[str, int, str]]:
    """(language, first line number, body) of every fenced block."""
    out = []
    for m in FENCE_RE.finditer(text):
        out.append((m.group(2).lower(), text.count("\n", 0, m.start(3)) + 1, m.group(3)))
    return out


def _commands(lang: str, start: int, body: str):
    """(line number, command) pairs of a shell block; a line ending in a
    backslash continues on the next."""
    pending, first = "", 0
    for i, raw in enumerate(body.splitlines()):
        if raw.rstrip().endswith("\\"):
            first = first if pending else i
            pending += raw.rstrip()[:-1] + " "
            continue
        if pending:
            raw, i, pending = pending + raw.strip(), first, ""
        line = raw.strip()
        prompted = line.startswith(("$ ", "> "))
        line = line[2:].strip() if prompted else line
        if not line or line.startswith("#"):
            continue
        if not lang and not prompted and (line.endswith((".", ":", "?"))
                                          or len(line.split()) > 12):
            continue                       # untagged blocks often hold output or prose
        yield start + i, line


def _substitutions(command: str) -> tuple[str, list[str]]:
    """`$( ... )` command substitutions taken out of a command line: the line
    with each replaced by a placeholder word, and the inner commands."""
    inner, out, i = [], [], 0
    while i < len(command):
        if command.startswith("$(", i):
            depth, j = 1, i + 2
            while j < len(command) and depth:
                depth += {"(": 1, ")": -1}.get(command[j], 0)
                j += 1
            inner.append(command[i + 2:j - 1])
            out.append("SUBST")
            i = j
        else:
            out.append(command[i])
            i += 1
    return "".join(out), inner


def _segments(command: str) -> list[list[str]]:
    """The simple commands of a command line, split at `&&`, `||`, `;` and `|`
    outside quotes, each without leading assignments and wrappers; the
    commands inside `$( ... )` come out as commands of their own."""
    command, inner = _substitutions(command)
    nested = [seg for c in inner for seg in _segments(c)]
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    try:
        words = list(lexer)
    except ValueError:
        words = command.split()
    out, tokens = [], []
    for word in [*words, ";"]:
        if word and set(word) <= set(";&|"):
            while tokens and (re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[0])
                              or tokens[0] in ("sudo", "env", "time", "nohup", "exec")):
                tokens = tokens[1:]
            if tokens:
                out.append(tokens)
            tokens = []
        else:
            tokens.append(word)
    return out + nested


def _hosts(tokens: list[str]) -> list[str]:
    hosts = []
    for t in tokens:
        for url in re.findall(r"https?://[^\s'\"<>)]+", t):
            host = urlparse(url).hostname
            if host and "." in host and not re.search(r"[{}<>$]", url) \
                    and host not in ("localhost", "example.com") and not host.endswith(".local"):
                hosts.append(host)
    return hosts


# --------------------------------------------------------------------------
# Requirements
# --------------------------------------------------------------------------

class _Collector:
    def __init__(self, optional: set[int]):
        self.reqs: dict[str, Requirement] = {}
        self.optional = optional
        self.routes = routes()
        self.doc_routes: list[_DocRoute] = []

    def add(self, req: Requirement, line: int, text: str, optional: bool = False) -> None:
        have = self.reqs.setdefault(req.cond, req)
        have.evidence.append(f"line {line}: {text.strip()[:160]}")
        have.core = have.core or not (optional or line in self.optional)

    def program(self, name: str, line: int, text: str) -> None:
        if name in COMMON:
            return
        route = self.routes["programs"].get(name)
        installs = [self.route(name, *route)] if route else []
        self.add(Requirement(f"program:{name}", f"the program {name}", [{"program": name}],
                             f"install {name}", installs), line, text)

    def route(self, name: str, installer: str, package: str) -> dict:
        """Installing `name` with a known installer (pip, npm, apt)."""
        return {"id": f"install_{name}_{installer}",
                "title": f"Install {name} ({installer} {package})",
                "needs": self.routes["installers"][installer],
                "how": {"pip": f"pip install {package}", "npm": f"npm install -g {package}",
                        "apt": f"apt-get install -y {package}"}[installer]}

    def installer(self, name: str, line: int, text: str) -> None:
        self.add(Requirement(f"installer:{name}", f"{name} can install packages here",
                             self.routes["installers"][name],
                             f"give the runtime {name} and access to its registry"), line, text)

    def egress(self, host: str, line: int, text: str) -> None:
        self.add(Requirement(f"egress:{host}", f"network access to {host}", [{"egress": host}],
                             f"ask for {host} to be allowed by the network policy"), line, text)

    def mcp(self, server: str, line: int, text: str) -> None:
        server = server.replace("_", "-")
        self.add(Requirement(f"mcp:{server}", f"the MCP server {server}",
                             [{"mcp_server": server}], f"connect the {server} MCP server"),
                 line, text)

    def module(self, name: str, line: int, text: str) -> None:
        if name in LOCAL_MODULES:
            return
        package = PIP_NAMES.get(name, name.replace("_", "-"))
        install = {"id": f"install_{name}", "title": f"Install the Python package {package}",
                   "needs": self.routes["installers"]["pip"], "how": f"pip install {package}"}
        self.add(Requirement(f"pymodule:{name}", f"the Python module {name}",
                             [{"pymodule": name}], "", [install]), line, text)

    def credential(self, name: str, line: int, text: str) -> None:
        self.add(Requirement(f"credential:{name}", f"the credential {name}",
                             [{"credential": name}], f"set {name} in the environment"),
                 line, text)


def requirements(text: str) -> list[Requirement]:
    meta, body = parse_frontmatter(text)
    offset = text.count("\n", 0, len(text) - len(body))
    lines = text.splitlines()
    col = _Collector(_optional_lines(lines))
    for lang, start, block in _blocks(body):
        start += offset
        if lang in SHELL_LANGS:
            for no, command in _commands(lang, start, block):
                _read_command(col, no, command, known_only=not lang)
        elif lang in PY_LANGS:
            for i, line in enumerate(block.splitlines()):
                m = IMPORT_RE.match(line)
                if m:
                    mod = m.group(1) or m.group(2)
                    if mod not in sys.stdlib_module_names and mod != "__future__":
                        col.module(mod, start + i, line)
    for no, line in enumerate(lines, 1):
        for name in CREDENTIAL_RE.findall(line):
            if not PLACEHOLDER.match(name) and ("`" in line or "$" in line or "=" in line
                                                or re.search(r"\b(set|export|env)", line, re.I)):
                col.credential(name, no, line)
        for server in MCP_RE.findall(line):
            col.mcp(server, no, line)
    fenced = {i for _, start, block in _blocks(body)
              for i in range(start + offset - 1, start + offset + block.count("\n") + 1)}
    _inline(col, lines, fenced)
    _library(col, text)
    _frontmatter_tools(col, meta, lines)
    _attach_routes(col)
    _fold_credentials(col)
    return list(col.reqs.values())


def _inline(col: _Collector, lines: list[str], in_blocks: set[int]) -> None:
    """Inline code in prose: a command or a known program (`npx foo`, `soffice`),
    or a package on a line about pip (`openpyxl`, `pandas` ... (pip))."""
    for no, line in enumerate(lines, 1):
        if no in in_blocks:
            continue
        for clause in re.split(r"[·;]|(?<!\\)\|", line):
            pip_clause = PIP_LINE_RE.search(clause) and not NPM_RE.search(clause)
            for span in INLINE_RE.findall(clause):
                span = span.replace("\\|", "|")
                words = span.split()
                if words and words[0] in KNOWN and (len(words) > 1 or words[0] not in COMMON):
                    _read_command(col, no, span, known_only=True)
                elif pip_clause and len(words) == 1 and re.fullmatch(r"[A-Za-z][\w-]*", span) \
                        and span not in KNOWN and span.lower() not in ("pip", "install"):
                    col.module(_MODULE_OF.get(span.lower(), span.replace("-", "_")), no, line)


def _fold_credentials(col: _Collector) -> None:
    """A credential that is one alternative of a required account is not
    required by itself: OPENAI_API_KEY *or* GEMINI_API_KEY satisfies an LLM key."""
    accounts = col.routes["accounts"]
    for cond in [c for c in col.reqs if c.startswith("account:")]:
        names = {n for group in accounts[cond.split(":", 1)[1]] for n in group}
        for name in names:
            folded = col.reqs.pop(f"credential:{name}", None)
            if folded:
                col.reqs[cond].evidence += folded.evidence
                col.reqs[cond].core = col.reqs[cond].core or folded.core


def _install_command(tokens: list[str], piped_to: str | None) -> list[str] | None:
    """What an install command provides (package names, script URL), or None."""
    head, args = tokens[0], [t for t in tokens[1:] if not t.startswith("-")]
    if head in ("curl", "wget", "iwr", "irm", "invoke-webrequest") and piped_to in SCRIPT_SHELLS:
        return [t for t in tokens if re.match(r"https?://", t)]
    verbs = INSTALL_VERBS.get(head)
    if verbs and args[:1] and args[0] in verbs:
        global_npm = head not in ("npm", "pnpm") or {"-g", "--global"} & set(tokens)
        packages = [a for a in args[1:] if a not in ("install", "add")]
        return packages if global_npm and packages else None
    if head in ("pip", "pip3") and "install" in args and "-r" not in tokens:
        return [a for a in args if a != "install"]
    return None


def _provides(route: _DocRoute, program: str) -> bool:
    """Whether an install command installs `program`: its package or script URL
    names it (aspire <- @microsoft/aspire-cli, Aspire.Cli, aspire.dev/install.sh)."""
    return _installs_what(route) == program.lower()


def _read_command(col: _Collector, no: int, command: str, known_only: bool = False) -> None:
    segments = _segments(command)
    for k, tokens in enumerate(segments):
        head = tokens[0]
        if head in KEYWORDS or (known_only and head not in KNOWN):
            continue
        args = [t for t in tokens[1:] if not t.startswith("-")]
        piped_to = segments[k + 1][0] if k + 1 < len(segments) else None
        provides = _install_command(tokens, piped_to)
        if provides is not None and not (head in ("pip", "pip3") and provides):
            sub = _Collector(set())
            sub.routes = col.routes
            _needs_of(sub, no, tokens, command)
            needs = [n for r in sub.reqs.values() for n in r.needs] + [
                {"egress": h} for h in REGISTRIES.get(head, ())]
            needs = [json.loads(n) for n in dict.fromkeys(json.dumps(n) for n in needs)]
            col.doc_routes.append(_DocRoute(no, command, tokens, provides, needs))
            if piped_to in SCRIPT_SHELLS:
                segments[k + 1] = ["true"]          # the shell runs the script, not a need
            continue
        if head in ("curl", "wget"):
            out = next((tokens[i + 1] for i, t in enumerate(tokens[:-1]) if t in ("-o", "-O")),
                       None) or (args[-1] if head == "wget" and args else None)
            sample = bool(out and DATA_EXT.search(out.split("?")[0]))
            for host in _hosts(tokens):
                col.add(Requirement(f"egress:{host}", f"network access to {host}",
                                    [{"egress": host}],
                                    f"ask for {host} to be allowed by the network policy"),
                        no, command, optional=sample)
            col.program(head, no, command)
            continue
        _needs_of(col, no, tokens, command)


def _needs_of(col: _Collector, no: int, tokens: list[str], command: str) -> None:
    """The needs of one simple command."""
    head = tokens[0]
    args = [t for t in tokens[1:] if not t.startswith("-")]
    for host in _hosts(tokens):
        col.egress(host, no, command)
    if head in BUILTINS or "/" in head or not re.fullmatch(r"[a-z][a-z0-9._+-]*", head):
        return
    if head in ("python", "python3") and "-m" in tokens:
        after = tokens[tokens.index("-m") + 1:]
        mod = after[0].split(".")[0] if after else ""
        if mod == "pip":
            head, args = "pip", tokens[tokens.index("-m") + 2:]
        elif mod and mod not in sys.stdlib_module_names:
            col.module(mod, no, command)
    if head in ("pip", "pip3", "uv") and "install" in args:
        col.installer("pip", no, command)
        return
    if head in ("npm", "yarn", "pnpm", "bun") and args[:1] \
            and args[0] in ("install", "i", "add", "ci"):
        col.installer("npm", no, command)
    if head in ("npx", "bunx"):
        col.installer("npm", no, command)
    if head in ("apt", "apt-get") and "install" in args:
        col.installer("apt", no, command)
        return
    if head == "docker" and args[:1] and args[0] in ("pull", "run") and len(args) > 1:
        image = args[1]
        first = image.split("/")[0]
        col.egress(first if "." in first else "registry-1.docker.io", no, command)
        col.add(Requirement("daemon:docker", "a running Docker daemon",
                            [{"daemon": "docker"}], "start a Docker daemon the agent can use"),
                no, command)
    col.program(head, no, command)


def _attach_routes(col: _Collector) -> None:
    """Install commands of the document become alternative ways to get the
    programs they name; one that names no program the document runs is kept
    as a need of its own (the document wants that thing installed)."""
    used = set()
    for cond, req in col.reqs.items():
        if not cond.startswith("program:"):
            continue
        program = cond.split(":", 1)[1]
        for i, route in enumerate(col.doc_routes):
            if _provides(route, program):
                used.add(i)
                req.installs.append({"id": f"doc_install_{program}_{i}",
                                     "title": f"Install {program} as the document says "
                                              f"(line {route.line})",
                                     "needs": route.needs, "how": route.text})
        module = col.reqs.get(f"pymodule:{program}")
        if module and not req.installs:          # a program that comes with a pip package
            req.installs.append(col.route(program, "pip",
                                          PIP_NAMES.get(program, program.replace("_", "-"))))
    unused: dict[str, list[_DocRoute]] = {}
    for i, route in enumerate(col.doc_routes):
        if i not in used:
            unused.setdefault(_installs_what(route), []).append(route)
    for name, group in unused.items():
        if not name:
            for route in group:
                _needs_of(col, route.line, route.tokens, route.text)
            continue
        # Several commands that install the same thing are alternatives
        for route in group:
            col.program(name, route.line, route.text)
        col.reqs[f"program:{name}"].installs += [
            {"id": f"doc_install_{name}_{k}", "title": f"Install {name} as the document says "
             f"(line {r.line})", "needs": r.needs, "how": r.text} for k, r in enumerate(group)]


GENERIC_HOSTS = {"raw.githubusercontent.com", "github.com", "gist.githubusercontent.com",
                 "objects.githubusercontent.com", "get.pnpm.io"}


def _installs_what(route: _DocRoute) -> str:
    """The name of the tool an install command installs: `@microsoft/aspire-cli`,
    `Aspire.Cli` and `https://aspire.dev/install.sh` all name `aspire`."""
    item = route.provides[0] if route.provides else ""
    if re.match(r"https?://", item):
        url = urlparse(item)
        parts = [p for p in url.path.split("/") if p]
        item = (parts[1] if len(parts) > 1 else "") if url.hostname in GENERIC_HOSTS \
            else (url.hostname or "").removeprefix("get.").removeprefix("www.").split(".")[0]
    item = re.sub(r"^@[^/]+/", "", item.split("@")[0] if not item.startswith("@")
                  else "@" + item[1:].split("@")[0]).lower()
    item = re.sub(r"[.-](cli|tools?)$", "", item.split("/")[-1])
    return item if re.fullmatch(r"[a-z][a-z0-9_-]{2,}", item) else ""


def _library(col: _Collector, text: str) -> None:
    accounts, platforms = col.routes["accounts"], col.routes["platforms"]
    library = load_library()
    for o in match(text, library):
        if o.kind == "program" and library.programs.get(o.value, {}).get("status") \
                == "unavailable":
            continue          # unpublished: it ships with the skill's own package
        if o.kind == "runtime_tool" and o.text.strip().lower() in INSTALLER_NAMES:
            continue          # an installer named as one way to install something
        if o.kind == "resource" and o.value in accounts:
            alternatives = [{"all": [{"credential": v} for v in group]}
                            for group in accounts[o.value]]
            label = o.value.replace("_", " ")
            col.add(Requirement(f"account:{o.value}", f"an authenticated {label}",
                                [{"any": alternatives}],
                                f"provide credentials for {label} "
                                f"({' or '.join('+'.join(g) for g in accounts[o.value])})"),
                    o.line, o.text)
        elif o.kind == "runtime_tool" and o.value in platforms:
            col.add(Requirement(f"platform:{platforms[o.value]}", f"a {platforms[o.value]} machine",
                                [{"platform": platforms[o.value]}],
                                f"run on a {platforms[o.value]} machine"), o.line, o.text)
        elif o.kind == "runtime_tool" and o.value.endswith("_mcp"):
            col.mcp(o.value[:-4], o.line, o.text)
        elif o.kind == "program":
            col.program(o.value, o.line, o.text)


def _frontmatter_tools(col: _Collector, meta: dict, lines: list[str]) -> None:
    raw = meta.get("allowed-tools") or meta.get("allowed_tools") or meta.get("tools")
    names = raw.split(",") if isinstance(raw, str) else raw if isinstance(raw, list) else []
    line = next((i for i, t in enumerate(lines, 1)
                 if re.match(r"(allowed[-_])?tools\s*:", t.strip())), 1)
    for item in names:
        item = str(item).strip()
        name = re.sub(r"\(.*\)$", "", item).strip()
        if not name:
            continue
        server = MCP_RE.match(name + "__") if name.startswith("mcp__") else None
        if server:
            col.mcp(server.group(1), line, item)
        else:
            col.add(Requirement(f"tool:{name}", f"the {name} tool", [{"tool": name}],
                                f"give the agent the {name} tool"), line, item)


# --------------------------------------------------------------------------
# The intent
# --------------------------------------------------------------------------

def intent_from_text(text: str, name: str | None = None, source: str = "") -> dict:
    meta, _ = parse_frontmatter(text)
    reqs = requirements(text)
    core = [r.cond for r in reqs if r.core]
    caps = [{"pred": r.cond, "title": r.title, "needs": r.needs, "fix": r.fix} for r in reqs]
    ops = [{**op, "adds": [r.cond]} for r in reqs for op in r.installs]
    if not core:
        caps.append({"pred": "deliverable", "title": "work the agent does by itself",
                     "needs": [], "fix": ""})
        core = ["deliverable"]
    return {
        "schema": "skillc.intent/1",
        "name": name or str(meta.get("name") or "skill"),
        "description": " ".join(str(meta.get("description") or "").split()),
        "source": source,
        "catalog": "claude",
        "target": {"scope": "/"},
        "capabilities": caps,
        "operations": ops,
        "goal": core,
        "optional": [r.cond for r in reqs if not r.core],
        "evidence": {r.cond: r.evidence for r in reqs},
    }

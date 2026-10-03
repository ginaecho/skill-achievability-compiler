"""Deterministic front-end: SKILL.md / agent markdown  ->  achievability pack.

This is the *untrusted* half of the compiler pipeline (the checker is the
trusted half).  It compacts a natural-language skill into a formal pack in a
purely deterministic, inspectable way -- no LLM required:

  1. **Declared capabilities Γ** come from the environment profile plus the
     skill's own frontmatter (`allowed-tools` for Claude Code skills, `tools`
     for agent markdown), plus prose declarations of the corpus style
     ("Tools: a, b, c" / "Tools available: ...").
  2. **Invoked actions** are extracted from the prose: backticked identifiers
     governed by an invocation verb ("via `ask_user_input_v0`",
     "use `str_replace`", "call `save_skill`", ...).  Fenced code blocks are
     not scanned (their contents run through the shell capability).
  3. Identifiers are classified: declared tools and snake_case names act via
     their own capability; unix-ish commands, scripts, and undeclared
     CamelCase code symbols (`pdftotext`, `thumbnail.py`, `PositionalTab`)
     act via the profile's shell (`bash`) capability.
  4. **Semantic compaction** (`prose.py` + `semantic.py`).  When the document
     says what "finished" means -- "Your job is finished when the flight is
     **booked** and a **confirmation email has been sent**" -- and lists
     workflow steps, the pack is built from what the document actually
     claims: goal conditions (with numeric budgets), participants, guards and
     bounds stated in the Tools section, choices/messages/spawns read from the
     workflow, and any declared per-role behaviour.  That pack can be refuted
     for reasons the weak reading cannot see: a goal condition with no
     establisher, a guard nothing satisfies, a budget no tool can meet, an
     unannounced choice that strands a role, a declared behaviour that does
     not cover its contract.
  5. Otherwise the pack falls back to the weak reading: one capability per
     granted tool establishing `used_<tool>`; the protocol is the ordered
     sequence of invoked acts; the goal is the conjunction of `used_<t>` over
     all invoked tools -- i.e. *the skill, as written, can actually be carried
     out in this environment*.  A document that never says when it is finished
     gives the front-end nothing stronger to check.

An author can bypass the heuristics entirely by embedding a precise pack in a
fenced block tagged `skillc-pack`; that JSON is validated and used verbatim
(this unlocks the full checker: guards, budgets, roles, choice/projection).

Soundness note (mirrors the paper's trust boundary): a misextraction here can
only make the checker judge *a different pack*; the verdict remains sound for
the pack actually produced, and the provenance report makes the pack
inspectable at one checkpoint.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import yaml

from ..pack import PackError, validate_pack
from ..profiles import Profile, normalize_tool
from . import semantic
from .prose import INVOKE_RE, negated_before

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.S)
FENCE_RE = re.compile(r"^(```+|~~~+)([^\n]*)\n(.*?)^\1\s*$\n?", re.S | re.M)
TOOLS_LINE_RE = re.compile(
    r"^\s*(?:\*\*)?tools(?:\s+available)?(?:\*\*)?\s*:\s*(.+)$", re.I | re.M)

AGENT_TOOL_RE = re.compile(r"\A(?:[a-z][a-z0-9]*(?:_[a-z0-9]+)+|[A-Z][A-Za-z0-9]*)\Z")
SHELL_TOKEN_RE = re.compile(r"\A[a-z][a-z0-9+.-]*\Z")

SHELL_CAP = "bash"
PACK_FENCE_TAG = "skillc-pack"


@dataclass
class Invocation:
    """One extracted tool use, with provenance for the inspection report."""
    raw: str            # identifier as written
    tool: str           # normalized capability it acts through
    kind: str           # "agent-tool" | "shell"
    line: int           # 1-based line in the source markdown


@dataclass
class CompileResult:
    pack: dict
    name: str
    profile: str
    declared: dict[str, str] = field(default_factory=dict)  # tool -> source
    invocations: list[Invocation] = field(default_factory=list)
    embedded: bool = False           # pack came from a ```skillc-pack block
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)   # semantic readings
    goal_source: str = "tool_usage_only"


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split YAML frontmatter from the body.  Tolerates malformed YAML."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    body = text[m.end():]
    try:
        meta = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return {}, body
    return (meta if isinstance(meta, dict) else {}), body


def _tool_list(value) -> list[str]:
    """Frontmatter tools value: comma-separated string or YAML list."""
    if value is None:
        return []
    if isinstance(value, str):
        return [t.strip() for t in value.split(",") if t.strip()]
    if isinstance(value, list):
        return [str(t).strip() for t in value if str(t).strip()]
    return []


def _strip_fences(body: str) -> tuple[str, dict | None]:
    """Blank out fenced code blocks (preserving line numbers) and pull out an
    embedded ``skillc-pack`` JSON block if present."""
    embedded: dict | None = None

    def repl(m: re.Match) -> str:
        nonlocal embedded
        info = m.group(2).strip().lower()
        if PACK_FENCE_TAG in info.split() and embedded is None:
            try:
                embedded = json.loads(m.group(3))
            except json.JSONDecodeError as e:
                raise PackError(f"embedded skillc-pack block is not valid JSON: {e}") from e
        return "\n" * m.group(0).count("\n")

    return FENCE_RE.sub(repl, body), embedded


def _classify(raw: str) -> str | None:
    """Classify an extracted identifier: 'agent-tool', 'shell', or None."""
    if ":" in raw:
        return None                      # XML-ish / namespaced code refs
    if "." in raw:
        # scripts and dotted method refs execute through a shell if at all
        return "shell"
    if AGENT_TOOL_RE.match(raw):
        return "agent-tool"
    if SHELL_TOKEN_RE.match(raw):
        return "shell"                   # unix-ish command: jq, pdftotext, ...
    return None


def extract(body: str, declared: set[str]) -> list[Invocation]:
    """Extract ordered tool invocations from prose (code fences pre-stripped)."""
    out: list[Invocation] = []
    for m in INVOKE_RE.finditer(body):
        # Skip negated invocations: "do NOT use `X`", "never call `X`", etc.
        if negated_before(body, m.start(), window=20):
            continue
        raw = m.group(1)
        norm = normalize_tool(raw)
        line = body.count("\n", 0, m.start(1)) + 1
        if norm in declared:
            out.append(Invocation(raw, norm, "agent-tool", line))
            continue
        kind = _classify(raw)
        if kind == "agent-tool" and raw[0].isupper():
            # Unknown CamelCase is a code symbol (library class/API), not an
            # agent tool: it executes through the shell, if at all.  Declared
            # CamelCase tools (e.g. `WebFetch` under claude-code) were matched
            # against Γ above.
            kind = "shell"
        if kind == "agent-tool":
            out.append(Invocation(raw, norm, "agent-tool", line))
        elif kind == "shell":
            out.append(Invocation(raw, SHELL_CAP, "shell", line))
    return out


def compile_markdown(text: str, profile: Profile,
                     name: str | None = None) -> CompileResult:
    """Compact a SKILL.md / agent markdown into an achievability pack."""
    meta, body = parse_frontmatter(text)
    skill_name = str(name or meta.get("name") or "skill")
    prose, embedded = _strip_fences(body)

    if embedded is not None:
        validate_pack(embedded)
        return CompileResult(pack=embedded, name=skill_name,
                             profile=profile.name, embedded=True,
                             goal_source="embedded")

    declared = _capability_context(meta, prose, profile)
    invocations = extract(prose, set(declared))

    # If the document states what "finished" means and lists workflow steps,
    # compile what it actually claims (goal conditions, guards, budgets,
    # participants, choices) instead of the weaker used_<tool> reading.
    sem = semantic.build(skill_name, prose, declared)
    if sem is not None:
        validate_pack(sem.pack)
        return CompileResult(pack=sem.pack, name=skill_name,
                             profile=profile.name, declared=declared,
                             invocations=invocations, notes=sem.notes,
                             goal_source="semantic")

    warnings: list[str] = []
    if not invocations:
        warnings.append("no tool invocations extracted; the fallback goal is "
                        "trivially achievable, but the skill's actual goal "
                        "and tool requirements have not been established")
    pack = _usage_pack(skill_name, declared, invocations)
    validate_pack(pack)
    return CompileResult(pack=pack, name=skill_name, profile=profile.name,
                         declared=declared, invocations=invocations,
                         warnings=warnings)


def _capability_context(meta: dict, prose: str, profile: Profile) -> dict[str, str]:
    """Γ: declared tool -> where it was declared (profile, frontmatter, prose)."""
    declared = {t: f"profile:{profile.name}" for t in sorted(profile.tools)}
    for key in ("allowed-tools", "allowed_tools", "tools"):
        for t in _tool_list(meta.get(key)):
            declared[normalize_tool(t)] = f"frontmatter:{key}"
    for m in TOOLS_LINE_RE.finditer(prose):
        for t in m.group(1).rstrip(".").split(","):
            t = t.strip().strip("`")
            if t and re.match(r"\A[A-Za-z][A-Za-z0-9_-]*\Z", t):
                declared[normalize_tool(t)] = "prose:tools-line"
    if profile.shell and SHELL_CAP not in declared:
        declared[SHELL_CAP] = f"profile:{profile.name}(shell)"
    return declared


def _usage_pack(name: str, declared: dict[str, str],
                invocations: list[Invocation]) -> dict:
    """The legacy reading: each tool establishes `used_<tool>`, and the goal is
    that every invoked tool has been used."""
    def pred(tool: str) -> str:
        return "used_" + re.sub(r"[^a-z0-9_]", "_", tool)

    used = list(dict.fromkeys(inv.tool for inv in invocations))
    return {
        "name": name,
        "roles": ["agent"],
        "capabilities": {t: {"owner": "agent", "add": [pred(t)]}
                         for t in sorted(declared)},
        "protocol": [{"act": {"cap": inv.tool, "by": "agent"}}
                     for inv in invocations],
        "goal": {"and": [pred(t) for t in used]} if used else True,
        "init_true": [],
    }


def compile_file(path, profile: Profile, name: str | None = None) -> CompileResult:
    with open(path, encoding="utf-8") as fh:
        return compile_markdown(fh.read(), profile, name=name)

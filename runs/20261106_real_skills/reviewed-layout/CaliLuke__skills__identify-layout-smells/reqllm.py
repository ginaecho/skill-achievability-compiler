"""Rllm: requirements extracted by a model, availability decided by the manifest.

PLAN.md (runs/20261015_review_response), Addendum E-b.

    document --(model, document only)--> JSON requirements
             --(deterministic guards)--> checked requirements
             --(env.manifest.typed_requirement_status)--> verdict

The model reads the document and nothing else: no runtime manifest, no tool
list, no runtime name.  One extraction therefore serves every runtime.  It
returns the document's primary task and its requirements, each with a
`kind`, a free `name`, `alternatives`, `hard`, a `hard_basis` and a verbatim
`quote`.  Everything after the reply is deterministic:

  * quote guard   a requirement whose quote is not in the document (after
                  whitespace and markdown-emphasis normalisation) is dropped;
  * hard guard    `hard` is cleared when `hard_basis` is `none` or the quote
                  starts on a line of an optional passage (env.nl's reader);
  * status        each name, and each alternative, by the manifest evaluator;
                  a requirement with alternatives is unavailable only if the
                  name and every alternative are;
  * verdict       IMPOSSIBLE (REQUIREMENT_UNAVAILABLE) if a hard requirement
                  is unavailable, the witness being its quote and the manifest
                  sentence that decided it; ACHIEVABLE otherwise.

The model can add a refutation only through a requirement it quotes from the
document and the manifest decides; it cannot decide availability.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable

from ..env.manifest import REASON, load_manifest_facts, typed_requirement_status
from ..env.nl import _optional_lines
from .providers import extract_json_object

SCHEMA = "skillc.reqllm_eval/1"
KINDS = ("program", "egress", "credential", "account", "connector", "tool", "platform",
         "hardware")
HARD_BASES = ("must", "numbered_step", "only_method", "frontmatter", "none")

SYSTEM = """You read one instruction document for an AI agent (a skill or an agent definition) and list what the agent needs from outside itself to do the document's primary task. You do not decide whether anything is available; you only extract what the document says.

Reply with one JSON object and nothing else:
{
  "primary_task": "<one sentence: the core deliverable of the document for one representative request>",
  "requirements": [
    {"kind": "<kind>", "name": "<name>", "alternatives": ["<name>", ...],
     "hard": true|false, "hard_basis": "<basis>", "quote": "<verbatim text>"}
  ]
}

kind is one of:
- program: an executable, CLI, SDK, application or daemon that has to be installed or running (for example docker, ffmpeg, a browser binary, Xcode).
- egress: a network host or online service endpoint the agent has to reach. Write the host name when the document gives one (api.example.com); otherwise the service's name.
- credential: an API key, token, secret or login for an external service (not a key or value read from a local file). Write the environment variable when the document gives one (EXAMPLE_API_KEY). A variable that holds a path or a setting is not a credential.
- account: an account, subscription, tenant, workspace or paid plan with an external service.
- connector: an MCP server or third-party app integration that the document names and the agent calls as tools. A component described only in prose ("the context manager", "the memory store") is not a connector unless the document says it is an MCP server or integration.
- tool: a named tool of an AI agent (a built-in tool such as an image generator, a code REPL or a comment-posting tool) that the document tells the agent to call. Write the tool name exactly as the document writes it. Scripts, files, shell commands, documents, linked skills, sub-agents and agent types are not tools.
- platform: an operating system or execution environment (for example macOS, Windows, a browser with a display).
- hardware: a physical device or hardware resource (for example a GPU, a phone, a board, a camera, a minimum amount of memory).

name: the shortest standard name of the thing (product, host, environment variable or tool name), not a description.
alternatives: names the document itself offers instead of this one ("use X or Y", "X, or alternatively Y"); an empty list when the document offers none. Do not add alternatives the document does not name.
hard: true only when the primary task cannot be done without this requirement according to the document. Judge it against what the agent itself must do: when the deliverable is files, configuration or instructions that the user later uses with a service, that service's account is not hard. false when the document makes it optional, conditional ("if you use X"), one of several options, a troubleshooting or follow-up step, an example, a comparison, or background.
hard_basis, the reason for hard (use "none" when hard is false):
- must: the document says it is required ("must", "required", "requires", "needs", "only works with", "cannot ... without").
- numbered_step: a mandatory step of the main workflow (a numbered or ordered step that is not optional) uses it.
- only_method: the document gives exactly one way to do the primary task and that way uses it.
- frontmatter: the document's frontmatter declares it (tools, allowed-tools, mcp servers, requirements).
- none: none of these.
quote: one passage copied character for character from the document that shows the requirement (at most about 200 characters, within one paragraph, list item or code line). Do not paraphrase, shorten with "...", translate, or fix typos.

Rules:
1. List each distinct requirement once. Put the strongest quote on it.
2. Leave out the agent's own work (reading, writing and editing files in the working directory, reasoning, writing the answer, asking the user), the inputs the user provides, and basic shell utilities (cd, ls, cat, grep, sed).
3. Things the document mentions only as examples, comparisons, related links or background are not requirements; leave them out.
4. When the document installs something itself (a pip, npm, apt or similar command), list the program and, if the install reaches a host the document names, that host.
5. When a mandatory step runs an external service's CLI command or calls its API (a cloud provider, a SaaS product), also list the account or credential that call needs, quoting that step, even if the document does not name the credential.
6. An empty requirements list is a valid answer.
"""

USER = "Document:\n```\n{text}\n```\nJSON:"

RETRY_PROMPT = ("\n\nYour previous reply was rejected:\n  {error}\n\nPrevious reply:\n{reply}\n\n"
                "Reply with the corrected JSON object only.")


def reqllm_messages(text: str) -> tuple[str, str]:
    """(system, user) for one extraction.  Neither names a runtime."""
    return SYSTEM, USER.format(text=text)


def retry_messages(text: str, reply: str, error: str) -> tuple[str, str]:
    """The single located-error retry: the same prompt, the reply, the error."""
    return SYSTEM, USER.format(text=text) + RETRY_PROMPT.format(error=error,
                                                                reply=reply.strip())


# ------------------------------------------------------------------ parsing

class ExtractionError(ValueError):
    """A reply that is not the JSON object the prompt asks for; the message
    locates the first defect (JSON position or field path)."""


def _locate_json_error(reply: str) -> str:
    start = reply.find("{")
    if start < 0:
        return "no JSON object in the reply"
    try:
        json.loads(reply[start:reply.rfind("}") + 1] or reply[start:])
    except json.JSONDecodeError as e:
        return f"invalid JSON: {e.msg} at line {e.lineno}, column {e.colno}"
    return "invalid JSON"


def _check_item(i: int, q) -> dict:
    p = f"requirements[{i}]"
    if not isinstance(q, dict):
        raise ExtractionError(f"{p}: must be an object")
    for k in ("kind", "name", "hard", "hard_basis", "quote"):
        if k not in q:
            raise ExtractionError(f"{p}: missing field {k!r}")
    kind = str(q["kind"]).strip().lower()
    if kind not in KINDS:
        raise ExtractionError(f"{p}.kind: {q['kind']!r} is not one of {', '.join(KINDS)}")
    if not isinstance(q["name"], str) or not q["name"].strip():
        raise ExtractionError(f"{p}.name: must be a non-empty string")
    alts = q.get("alternatives", [])
    if alts is None:
        alts = []
    if not isinstance(alts, list) or not all(isinstance(a, str) for a in alts):
        raise ExtractionError(f"{p}.alternatives: must be a list of strings")
    if not isinstance(q["hard"], bool):
        raise ExtractionError(f"{p}.hard: must be true or false")
    basis = str(q["hard_basis"]).strip().lower()
    if basis not in HARD_BASES:
        raise ExtractionError(f"{p}.hard_basis: {q['hard_basis']!r} is not one of "
                              f"{', '.join(HARD_BASES)}")
    if not isinstance(q["quote"], str):
        raise ExtractionError(f"{p}.quote: must be a string")
    return {"kind": kind, "name": q["name"].strip(),
            "alternatives": [a.strip() for a in alts if a.strip()],
            "hard": q["hard"], "hard_basis": basis, "quote": q["quote"]}


def parse_extraction(reply: str, strict: bool = True) -> dict:
    """The extraction in `reply`, schema-checked.  strict=False (after the
    retry) keeps the valid requirements and lists the invalid ones under
    `invalid` instead of raising."""
    try:
        obj = extract_json_object(reply)
    except ValueError:
        raise ExtractionError(_locate_json_error(reply)) from None
    if not isinstance(obj, dict):
        raise ExtractionError("the reply must be a JSON object")
    reqs = obj.get("requirements")
    if not isinstance(reqs, list):
        raise ExtractionError("field 'requirements': missing or not a list")
    task = obj.get("primary_task")
    if not isinstance(task, str):
        if strict:
            raise ExtractionError("field 'primary_task': missing or not a string")
        task = ""
    items, invalid = [], []
    for i, q in enumerate(reqs):
        try:
            items.append(_check_item(i, q))
        except ExtractionError as e:
            if strict:
                raise
            invalid.append(str(e))
    return {"primary_task": task, "requirements": items, "invalid": invalid}


# ------------------------------------------------------------------ guards

_EMPH = re.compile(r"[*_`~]")
_TRANS = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"',
                        "–": "-", "—": "-", " ": " ", "…": "..."})


def normalize(s: str) -> str:
    """Whitespace and markdown-emphasis normalisation: typographic quotes and
    dashes to ASCII, `* _ ` ~` removed, whitespace runs to one space."""
    return re.sub(r"\s+", " ", _EMPH.sub("", s.translate(_TRANS))).strip()


def _normalized_with_lines(text: str) -> tuple[str, list[int]]:
    """normalize(text), and for each of its characters the 1-based line of
    the document it comes from."""
    out, where, line, space = [], [], 1, False
    for ch in text.translate(_TRANS):
        if ch == "\n":
            line += 1
        if _EMPH.match(ch):
            continue
        if ch.isspace():
            space = bool(out)
            continue
        if space:
            out.append(" ")
            where.append(line)
            space = False
        out.append(ch)
        where.append(line)
    return "".join(out), where


def locate_quote(quote: str, text: str, _cache: dict | None = None) -> int | None:
    """The 1-based line where `quote` starts in `text` after normalisation, or
    None when it is not there.  A quote written as segments joined by "..."
    is located when every segment occurs, in order (each segment verbatim)."""
    norm, where = (_cache or {}).get("doc") or _normalized_with_lines(text)
    if _cache is not None:
        _cache["doc"] = (norm, where)
    q = normalize(quote)
    if not q:
        return None
    segs = [s.strip() for s in q.split("...") if s.strip()]
    if not segs:
        return None
    pos, first = 0, None
    for s in segs:
        k = norm.find(s, pos)
        if k < 0:
            return None
        if first is None:
            first = k
        pos = k + len(s)
    return where[first] if where else None


# ------------------------------------------------------------------ evaluation

def _status_with_alternatives(req: dict, facts) -> dict:
    names = [req["name"]] + list(req["alternatives"])
    res = [(n, *typed_requirement_status(req["kind"], n, facts)) for n in names]
    sts = [st for _, st, _ in res]
    if all(st == "unavailable" for st in sts):
        status, basis = "unavailable", res[0][2]
        if len(res) > 1:
            basis = "; ".join(f"{n}: {b}" for n, _, b in res)
    elif any(st == "available" for st in sts):
        n, st, b = next(r for r in res if r[1] == "available")
        status, basis = "available", b if n == req["name"] else f"{n}: {b}"
    elif any(st == "installable" for st in sts):
        n, st, b = next(r for r in res if r[1] == "installable")
        status, basis = "installable", b if n == req["name"] else f"{n}: {b}"
    else:
        status = "unknown"
        basis = "; ".join(f"{n}: {st} ({b})" for n, st, b in res) if len(res) > 1 else res[0][2]
    return {"status": status, "basis": basis,
            "per_name": [{"name": n, "status": st, "basis": b} for n, st, b in res]}


def evaluate_extraction(extraction: dict, text: str, manifest) -> dict:
    """Guards, statuses and verdict for one extraction against one manifest."""
    facts = load_manifest_facts(manifest)
    optional = _optional_lines(text.splitlines())
    cache: dict = {}
    reqs, dropped = [], []
    for q in extraction.get("requirements") or []:
        line = locate_quote(q["quote"], text, cache)
        if line is None:
            dropped.append({**q, "dropped": "quote not in the document"})
            continue
        hard = bool(q["hard"])
        cleared = None
        if hard and q["hard_basis"] == "none":
            hard, cleared = False, "hard_basis none"
        elif hard and line in optional:
            hard, cleared = False, f"line {line} is in an optional passage"
        st = _status_with_alternatives(q, facts)
        reqs.append({"requirement": f"{q['kind']}:{q['name']}", "kind": q["kind"],
                     "name": q["name"], "alternatives": list(q["alternatives"]),
                     "hard_model": bool(q["hard"]), "hard_basis": q["hard_basis"],
                     "hard": hard, "hard_cleared": cleared, "quote": q["quote"],
                     "line": line, **st})
    blocking = [r for r in reqs if r["hard"] and r["status"] == "unavailable"]
    n_all = len(reqs) + len(dropped)
    return {"schema": SCHEMA, "runtime": facts.name,
            "primary_task": extraction.get("primary_task", ""),
            "verdict": "IMPOSSIBLE" if blocking else "ACHIEVABLE",
            "reason": REASON if blocking else None,
            "blocking": [r["requirement"] for r in blocking],
            "witness": [{"requirement": r["requirement"], "status": r["status"],
                         "basis": r["basis"], "quote": r["quote"], "line": r["line"],
                         "evidence": [f"{r['line']}: {r['quote']}"]} for r in blocking],
            "unknown": [r["requirement"] for r in reqs if r["status"] == "unknown"],
            "requirements": reqs, "dropped": dropped,
            "invalid_items": list(extraction.get("invalid") or []),
            "quotes": {"total": n_all, "verbatim": len(reqs),
                       "verbatim_rate": round(len(reqs) / n_all, 4) if n_all else None}}


def invalid_evaluation(manifest, error: str) -> dict:
    """The evaluation of a reply that gave no extraction: decides nothing."""
    facts = load_manifest_facts(manifest)
    return {"schema": SCHEMA, "runtime": facts.name, "primary_task": "",
            "verdict": "UNKNOWN", "reason": "INVALID_EXTRACTION", "error": error,
            "blocking": [], "witness": [], "unknown": [], "requirements": [],
            "dropped": [], "invalid_items": [],
            "quotes": {"total": 0, "verbatim": 0, "verbatim_rate": None}}


def extraction_from_replies(replies: list[str]) -> tuple[dict | None, str | None]:
    """The extraction from a chain of replies (first, then the retry): the
    first reply that passes the strict schema; otherwise the last one read
    leniently; (None, error) when no reply has a JSON object at all."""
    err = None
    for reply in replies:
        try:
            return parse_extraction(reply, strict=True), None
        except ExtractionError as e:
            err = str(e)
    if replies:
        try:
            return parse_extraction(replies[-1], strict=False), None
        except ExtractionError as e:
            err = str(e)
    return None, err


def run_rllm(text: str, manifest, complete: Callable[[str, str], str]) -> dict:
    """Extract with `complete(system, user) -> reply` (one located-error retry
    when the first reply is not valid), then evaluate against `manifest`.
    The result carries the replies under `replies`."""
    system, user = reqllm_messages(text)
    replies = [complete(system, user)]
    try:
        parse_extraction(replies[0], strict=True)
    except ExtractionError as e:
        replies.append(complete(*retry_messages(text, replies[0], str(e))))
    ext, err = extraction_from_replies(replies)
    ev = invalid_evaluation(manifest, err) if ext is None else \
        evaluate_extraction(ext, text, manifest)
    ev["replies"] = replies
    return ev

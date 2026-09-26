"""SkillC Controlled English (CE): a readable, formal surface for packs.

Compaction via CE splits the untrusted step in two:

    natural language --(LLM paraphrase, untrusted)--> CE --(this module)--> pack

The second arrow is deterministic.  CE is a small formal language that reads
as English; every sentence form denotes exactly one pack construct, so
`parse_ce(render_ce(p)) == canonical_pack(p)` for every valid pack `p`, and a
parse error names the line and column the author (human or model) must fix.
Nothing is inferred here: there is no stemming, synonym matching or guessing,
which is what makes the arrow trustworthy.  Whether the CE says what the prose
meant remains the untrusted part, exactly as for JSON compaction.

A CE document, by example::

    Skill `book-flight`.
    Roles: `agent`, `user`.
    Tool `search_flights` (owner `agent`).
    Tool `book_flight` (owner `agent`): requires `flight_selected`; adds `booked`.
    Tool `pay` (owner `agent`): picks `price` with `price` < 500; sets `spent` to `spent` + `price`.
    Initially true: `logged_in`.
    Initially: `spent` == 0.
    Goal: `booked` and `spent` <= 500.
    Protocol:
      - `agent` uses `search_flights`.
      - `user` chooses one of (observed):
        - branch `accept`:
          - `agent` uses `book_flight`.
        - branch `decline`: none.
    Behaviour of `user`:
      - select one of:
        - branch `accept`: none.
        - branch `decline`: none.

Sentence forms (one statement per line; nested steps are ``- `` bullets
indented two spaces per level; ``#`` starts a comment outside backticks)::

    Skill `NAME`.
    Roles: `R`, ... .            | Roles: none.
    Tool `C` [(owner `R`)] [: CLAUSE; CLAUSE; ...].
        CLAUSE := requires F | adds `P`, ... | removes `P`, ...
                | sets `V` to E | picks `V` with F
    Initially true: `P`, ... .
    Initially: F.                (one line per initial constraint)
    Goal: F.
    Protocol:                    | Protocol: none.
    Behaviour of `R`:            | Behaviour of `R`: none.

    protocol step               behaviour (local) step
    - `R` uses `C`.             - use `C`.
    - `A` tells `B` `L`.        - send `L` to `B`.   - receive `L` from `A`.
    - `R` chooses one of [(external, observed)]:
                                - select one of:     - branch on `A` one of:
        - branch `L`:               - branch `L`:
        - branch `L`: none.
    - loop `X`:  | - loop `X`: none.      (both)
    - repeat `X`.                          (both)
    - checkpoint: F.                       (both)
    - spawn `R`.

Formulas and linear expressions::

    F := F or F | F and F | not F | ( F ) | true | false
       | all of (F, ...) | any of (F, ...) | E OP E | `P`
    E := `V` | INT | -INT | ( E ) | E + E | E - E | E * E    (one operator
         per level; nest with parentheses)
    OP := < | <= | == | > | >= | !=

Identifiers are always backticked, so a predicate named ``and`` cannot be
confused with the connective, and ``true`` (the constant) differs from
```true``` (a predicate).
"""
from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from ..pack import validate_pack

CE_VERSION = "1"
INDENT = "  "
CMP_OPS = ("<=", ">=", "==", "!=", "<", ">")
ARITH_OPS = ("+", "-", "*")
CHOICE_FLAGS = ("external", "observed")
CAP_FIELDS = ("owner", "pre", "add", "del", "assigns", "nondet")


class CEError(ValueError):
    """A CE document is malformed, or a pack cannot be rendered as CE."""

    def __init__(self, message: str, line: int | None = None,
                 col: int | None = None):
        self.line, self.col, self.message = line, col, message
        where = ""
        if line is not None:
            where = f"line {line}" + (f", column {col}" if col is not None else "")
            where += ": "
        super().__init__(where + message)


class _Committed(CEError):
    """A diagnosis that backtracking must not hide (the input is wrong under
    every reading, and this message says why)."""


# --------------------------------------------------------------------------
# Canonical form
# --------------------------------------------------------------------------

def canonical_pack(pack: dict) -> dict:
    """The normal form CE round-trips to.

    Defaults are made explicit (`pre: true`, empty effect lists and maps,
    empty roles and initial state), `false` choice flags are dropped (absent
    and false mean the same to the checker), and an empty `skills` map is
    dropped.  Formulas, names and every ordered list are kept exactly.
    """
    out: dict[str, Any] = {
        "name": pack["name"],
        "roles": list(pack.get("roles", [])),
        "capabilities": {},
        "protocol": _canon_steps(pack["protocol"]),
        "goal": deepcopy(pack["goal"]),
        "init_true": list(pack.get("init_true", [])),
        "init_constraints": deepcopy(pack.get("init_constraints", [])),
    }
    for name, cap in pack["capabilities"].items():
        c: dict[str, Any] = {}
        if "owner" in cap:
            c["owner"] = cap["owner"]
        c["pre"] = deepcopy(cap.get("pre", True))
        c["add"] = list(cap.get("add", []))
        c["del"] = list(cap.get("del", []))
        c["assigns"] = deepcopy(cap.get("assigns", {}))
        c["nondet"] = deepcopy(cap.get("nondet", {}))
        out["capabilities"][name] = c
    skills = pack.get("skills") or {}
    if skills:
        out["skills"] = {r: _canon_steps(s) for r, s in skills.items()}
    return out


def _canon_steps(steps: list) -> list:
    out = []
    for s in steps:
        (kind, body), = s.items()
        if kind in ("choice", "select", "branch"):
            b = {k: v for k, v in body.items()
                 if k != "branches" and not (k in CHOICE_FLAGS and v is False)}
            b["branches"] = {l: _canon_steps(br)
                             for l, br in body["branches"].items()}
            out.append({kind: b})
        elif kind == "rec":
            out.append({"rec": {"name": body["name"],
                                "body": _canon_steps(body["body"])}})
        else:
            out.append(deepcopy(s))
    return out


# --------------------------------------------------------------------------
# Rendering: pack -> CE
# --------------------------------------------------------------------------

# Everything str.splitlines() treats as a line boundary, plus the backtick.
_UNWRITABLE = frozenset("`\n\r\x0b\x0c\x1c\x1d\x1e\x85  ")


def _name(n: Any) -> str:
    if not isinstance(n, str) or not n:
        raise CEError(f"identifier must be a non-empty string, got {n!r}")
    if _UNWRITABLE.intersection(n):
        raise CEError(f"identifier {n!r} contains a backtick or line break "
                      "and cannot be written in CE")
    return f"`{n}`"


def _names(ns: list) -> str:
    return ", ".join(_name(n) for n in ns)


def render_expr(e: Any) -> str:
    if isinstance(e, bool):
        raise CEError(f"booleans are not expressions: {e!r}")
    if isinstance(e, int):
        return str(e)
    if isinstance(e, str):
        return _name(e)
    if isinstance(e, dict) and len(e) == 1:
        (op, args), = e.items()
        if op in ARITH_OPS and isinstance(args, list) and len(args) == 2:
            return f"{_expr_operand(args[0])} {op} {_expr_operand(args[1])}"
    raise CEError(f"not a CE-expressible expression: {e!r}")


def _expr_operand(e: Any) -> str:
    text = render_expr(e)
    return f"({text})" if isinstance(e, dict) else text


def render_formula(f: Any) -> str:
    if f is True:
        return "true"
    if f is False:
        return "false"
    if isinstance(f, str):
        return _name(f)
    if isinstance(f, dict) and len(f) == 1:
        (op, arg), = f.items()
        if op in ("and", "or") and isinstance(arg, list):
            if len(arg) < 2:
                word = "all" if op == "and" else "any"
                return f"{word} of (" + ", ".join(render_formula(x) for x in arg) + ")"
            return f" {op} ".join(_formula_operand(x) for x in arg)
        if op == "not":
            return "not " + _formula_operand(arg)
        if op == "cmp" and isinstance(arg, list) and len(arg) == 3:
            left, cmp, right = arg
            if cmp not in CMP_OPS:
                raise CEError(f"unknown comparison {cmp!r}")
            return f"{render_expr(left)} {cmp} {render_expr(right)}"
    raise CEError(f"not a CE-expressible formula: {f!r}")


def _formula_operand(f: Any) -> str:
    text = render_formula(f)
    infix = (isinstance(f, dict) and len(f) == 1
             and next(iter(f)) in ("and", "or")
             and isinstance(f[next(iter(f))], list)
             and len(f[next(iter(f))]) >= 2)
    return f"({text})" if infix else text


def _render_cap(name: str, cap: dict) -> str:
    unknown = set(cap) - set(CAP_FIELDS)
    if unknown:
        raise CEError(f"capability {name!r} has fields CE cannot express: "
                      f"{sorted(unknown)}")
    head = f"Tool {_name(name)}"
    if "owner" in cap:
        head += f" (owner {_name(cap['owner'])})"
    clauses = []
    pre = cap.get("pre", True)
    if pre is not True:
        clauses.append("requires " + render_formula(pre))
    if cap.get("add"):
        clauses.append("adds " + _names(cap["add"]))
    if cap.get("del"):
        clauses.append("removes " + _names(cap["del"]))
    for var, expr in (cap.get("assigns") or {}).items():
        clauses.append(f"sets {_name(var)} to {render_expr(expr)}")
    for var, constr in (cap.get("nondet") or {}).items():
        clauses.append(f"picks {_name(var)} with {render_formula(constr)}")
    return head + (": " + "; ".join(clauses) if clauses else "") + "."


def _render_steps(steps: list, depth: int, local: bool, out: list) -> None:
    ind = INDENT * depth
    for s in steps:
        if not (isinstance(s, dict) and len(s) == 1):
            raise CEError(f"step must be a single-key dict: {s!r}")
        (kind, b), = s.items()
        if kind == "act":
            out.append(f"{ind}- use {_name(b['cap'])}." if local else
                       f"{ind}- {_name(b['by'])} uses {_name(b['cap'])}.")
        elif kind == "msg" and not local:
            out.append(f"{ind}- {_name(b['from'])} tells {_name(b['to'])} "
                       f"{_name(b['label'])}.")
        elif kind == "send" and local:
            out.append(f"{ind}- send {_name(b['label'])} to {_name(b['to'])}.")
        elif kind == "recv" and local:
            out.append(f"{ind}- receive {_name(b['label'])} from {_name(b['from'])}.")
        elif kind in ("choice", "select", "branch") and \
                (kind == "choice") != local:
            if kind == "choice":
                flags = [f for f in CHOICE_FLAGS if b.get(f) is True]
                extra = set(b) - {"by", "branches", *CHOICE_FLAGS}
                if extra:
                    raise CEError(f"choice has fields CE cannot express: {sorted(extra)}")
                head = f"{_name(b['by'])} chooses one of"
                if flags:
                    head += " (" + ", ".join(flags) + ")"
            elif kind == "select":
                head = "select one of"
            else:
                head = f"branch on {_name(b['from'])} one of"
            out.append(f"{ind}- {head}:")
            for label, branch in b["branches"].items():
                if branch:
                    out.append(f"{ind}{INDENT}- branch {_name(label)}:")
                    _render_steps(branch, depth + 2, local, out)
                else:
                    out.append(f"{ind}{INDENT}- branch {_name(label)}: none.")
        elif kind == "goal":
            out.append(f"{ind}- checkpoint: {render_formula(b)}.")
        elif kind == "rec":
            if b["body"]:
                out.append(f"{ind}- loop {_name(b['name'])}:")
                _render_steps(b["body"], depth + 1, local, out)
            else:
                out.append(f"{ind}- loop {_name(b['name'])}: none.")
        elif kind == "continue":
            out.append(f"{ind}- repeat {_name(b)}.")
        elif kind == "spawn" and not local:
            out.append(f"{ind}- spawn {_name(b['role'])}.")
        else:
            where = "behaviour" if local else "protocol"
            raise CEError(f"step kind {kind!r} cannot appear in a {where}")


def render_ce(pack: dict) -> str:
    """Render a pack as a CE document (one statement per line)."""
    known = {"name", "roles", "capabilities", "protocol", "goal",
             "init_true", "init_constraints", "skills"}
    extra = set(pack) - known
    if extra:
        raise CEError(f"pack has top-level fields CE cannot express: {sorted(extra)}")
    lines = [f"Skill {_name(pack['name'])}."]
    roles = pack.get("roles", [])
    lines.append("Roles: " + (_names(roles) if roles else "none") + ".")
    for name, cap in pack["capabilities"].items():
        lines.append(_render_cap(name, cap))
    if pack.get("init_true"):
        lines.append("Initially true: " + _names(pack["init_true"]) + ".")
    for c in pack.get("init_constraints", []):
        lines.append("Initially: " + render_formula(c) + ".")
    lines.append("Goal: " + render_formula(pack["goal"]) + ".")
    if pack["protocol"]:
        lines.append("Protocol:")
        _render_steps(pack["protocol"], 1, False, lines)
    else:
        lines.append("Protocol: none.")
    for role, behaviour in (pack.get("skills") or {}).items():
        if behaviour:
            lines.append(f"Behaviour of {_name(role)}:")
            _render_steps(behaviour, 1, True, lines)
        else:
            lines.append(f"Behaviour of {_name(role)}: none.")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# Tokens
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Tok:
    kind: str       # NAME | INT | WORD | SYM
    value: str
    col: int        # 1-based


_SYMS = ("<=", ">=", "==", "!=", "<", ">", "+", "-", "*",
         "(", ")", ",", ";", ":", ".")
_WORD_RE = re.compile(r"[A-Za-z]+")
_INT_RE = re.compile(r"\d+")


def tokenize(text: str, line: int, col0: int = 1) -> tuple[list[Tok], str]:
    """Tokens of one line, plus the trailing ``#`` comment (or "")."""
    toks: list[Tok] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        col = col0 + i
        if ch in " \t":
            if ch == "\t":
                raise CEError("tabs are not allowed; indent with spaces", line, col)
            i += 1
        elif ch == "#":
            return toks, text[i + 1:].strip()
        elif ch == "`":
            j = text.find("`", i + 1)
            if j < 0:
                raise CEError("unterminated backtick identifier", line, col)
            if j == i + 1:
                raise CEError("empty identifier ``", line, col)
            toks.append(Tok("NAME", text[i + 1:j], col))
            i = j + 1
        elif ch.isdigit():
            m = _INT_RE.match(text, i)
            toks.append(Tok("INT", m.group(), col))
            i = m.end()
        elif ch.isalpha():
            m = _WORD_RE.match(text, i)
            toks.append(Tok("WORD", m.group(), col))
            i = m.end()
        else:
            for sym in _SYMS:
                if text.startswith(sym, i):
                    toks.append(Tok("SYM", sym, col))
                    i += len(sym)
                    break
            else:
                raise CEError(f"unexpected character {ch!r}", line, col)
    return toks, ""


# --------------------------------------------------------------------------
# Token-stream parser (one statement)
# --------------------------------------------------------------------------

class _Stream:
    def __init__(self, toks: list[Tok], line: int, end_col: int):
        self.toks, self.i, self.line, self.end_col = toks, 0, line, end_col

    def peek(self, k: int = 0) -> Tok | None:
        j = self.i + k
        return self.toks[j] if j < len(self.toks) else None

    def col(self) -> int:
        t = self.peek()
        return t.col if t else self.end_col

    def fail(self, expected: str) -> CEError:
        t = self.peek()
        got = f"{t.kind.lower()} {t.value!r}" if t else "end of line"
        return CEError(f"expected {expected}, got {got}", self.line, self.col())

    def is_word(self, *words: str, k: int = 0) -> bool:
        t = self.peek(k)
        return t is not None and t.kind == "WORD" and t.value in words

    def is_sym(self, *syms: str, k: int = 0) -> bool:
        t = self.peek(k)
        return t is not None and t.kind == "SYM" and t.value in syms

    def word(self, w: str) -> None:
        if not self.is_word(w):
            raise self.fail(f"'{w}'")
        self.i += 1

    def words(self, phrase: str) -> None:
        for w in phrase.split():
            self.word(w)

    def sym(self, s: str) -> None:
        if not self.is_sym(s):
            raise self.fail(f"'{s}'")
        self.i += 1

    def name(self, what: str = "a backticked identifier") -> str:
        t = self.peek()
        if t is None or t.kind != "NAME":
            raise self.fail(what)
        self.i += 1
        return t.value

    def names(self) -> list[str]:
        out = [self.name()]
        while self.is_sym(","):
            self.i += 1
            out.append(self.name())
        return out

    def end(self) -> None:
        if self.peek() is not None:
            raise self.fail("end of statement")

    # -- formulas ----------------------------------------------------------
    def formula(self) -> Any:
        parts = [self._conj()]
        while self.is_word("or"):
            self.i += 1
            parts.append(self._conj())
        return parts[0] if len(parts) == 1 else {"or": parts}

    def _conj(self) -> Any:
        parts = [self._unary()]
        while self.is_word("and"):
            self.i += 1
            parts.append(self._unary())
        return parts[0] if len(parts) == 1 else {"and": parts}

    def _unary(self) -> Any:
        if self.is_word("not"):
            self.i += 1
            return {"not": self._unary()}
        return self._atom()

    def _atom(self) -> Any:
        if self.is_word("true"):
            self.i += 1
            return True
        if self.is_word("false"):
            self.i += 1
            return False
        if self.is_word("all", "any") and self.is_word("of", k=1):
            op = "and" if self.peek().value == "all" else "or"
            self.i += 2
            self.sym("(")
            items = []
            if not self.is_sym(")"):
                items.append(self.formula())
                while self.is_sym(","):
                    self.i += 1
                    items.append(self.formula())
            self.sym(")")
            return {op: items}
        start = self.i
        cmp = self._try_cmp()
        if cmp is not None:
            return cmp
        self.i = start
        if self.is_sym("("):
            self.i += 1
            f = self.formula()
            self.sym(")")
            return f
        t = self.peek()
        if t is not None and t.kind == "NAME":
            self.i += 1
            return t.value
        raise self.fail("a formula (a backticked predicate, true, false, "
                        "not, all of, any of, a comparison or '(')")

    def _try_cmp(self) -> Any:
        start = self.i
        try:
            left = self.expr()
        except _Committed:
            raise
        except CEError:
            self.i = start
            return None
        t = self.peek()
        if t is None or t.kind != "SYM" or t.value not in CMP_OPS:
            self.i = start
            return None
        self.i += 1
        right = self.expr()
        return {"cmp": [left, t.value, right]}

    # -- linear expressions ------------------------------------------------
    def expr(self) -> Any:
        left = self._operand()
        t = self.peek()
        if t is not None and t.kind == "SYM" and t.value in ARITH_OPS:
            self.i += 1
            right = self._operand()
            if self.is_sym(*ARITH_OPS):
                raise _Committed("one arithmetic operator per level: add "
                                 "parentheses", self.line, self.col())
            return {t.value: [left, right]}
        return left

    def _operand(self) -> Any:
        t = self.peek()
        if t is None:
            raise self.fail("an expression")
        if t.kind == "NAME":
            self.i += 1
            return t.value
        if t.kind == "INT":
            self.i += 1
            return int(t.value)
        if t.kind == "SYM" and t.value == "-":
            nxt = self.peek(1)
            if nxt is not None and nxt.kind == "INT":
                self.i += 2
                return -int(nxt.value)
        if t.kind == "SYM" and t.value == "(":
            self.i += 1
            e = self.expr()
            self.sym(")")
            return e
        raise self.fail("an expression (a backticked variable, an integer "
                        "or '(')")


# --------------------------------------------------------------------------
# Document parser
# --------------------------------------------------------------------------

@dataclass
class _Line:
    no: int
    depth: int
    toks: list[Tok]
    end_col: int
    comment: str

    def stream(self) -> _Stream:
        return _Stream(self.toks, self.no, self.end_col)


@dataclass
class ParseResult:
    pack: dict
    comments: dict[int, str] = field(default_factory=dict)   # line -> text


def _lines(text: str) -> list[_Line]:
    out = []
    for no, raw in enumerate(text.splitlines(), 1):
        stripped = raw.rstrip()
        if not stripped.strip():
            continue
        body = stripped.lstrip(" ")
        lead = len(stripped) - len(body)
        if body.startswith("\t") or "\t" in stripped[:lead + 1]:
            raise CEError("tabs are not allowed; indent with spaces", no, 1)
        if body.startswith("#"):
            continue
        if lead % len(INDENT):
            raise CEError(f"indentation must be a multiple of {len(INDENT)} "
                          "spaces", no, 1)
        toks, comment = tokenize(body, no, lead + 1)
        if not toks:
            continue
        out.append(_Line(no, lead // len(INDENT), toks, len(stripped) + 1,
                         comment))
    return out


def parse_ce_detailed(text: str) -> ParseResult:
    lines = _lines(text)
    if not lines:
        raise CEError("empty CE document")
    comments = {ln.no: ln.comment for ln in lines if ln.comment}
    pack: dict[str, Any] = {}
    roles = None
    caps: dict[str, dict] = {}
    init_true = None
    init_constraints: list = []
    goal_line = None
    protocol = None
    skills: dict[str, list] = {}

    first = lines[0]
    st = first.stream()
    if first.depth:
        raise CEError("the document must start with 'Skill `NAME`.' at the "
                      "left margin", first.no, 1)
    st.word("Skill")
    pack["name"] = st.name("the skill name in backticks")
    st.sym(".")
    st.end()

    pos = 1
    while pos < len(lines):
        ln = lines[pos]
        st = ln.stream()
        if ln.depth:
            raise CEError("unexpected indented line: steps belong under "
                          "'Protocol:' or 'Behaviour of `R`:'", ln.no, 1)
        pos += 1
        if st.is_word("Roles"):
            if roles is not None:
                raise CEError("duplicate 'Roles:' statement", ln.no, 1)
            st.word("Roles")
            st.sym(":")
            if st.is_word("none"):
                st.word("none")
                roles = []
            else:
                roles = st.names()
            st.sym(".")
            st.end()
        elif st.is_word("Tool"):
            st.word("Tool")
            name_col = st.col()
            name = st.name("the tool name in backticks")
            if name in caps:
                raise CEError(f"duplicate tool {name!r}", ln.no, name_col)
            caps[name] = _parse_cap(st)
        elif st.is_word("Initially") and st.is_word("true", k=1):
            if init_true is not None:
                raise CEError("duplicate 'Initially true:' statement", ln.no, 1)
            st.words("Initially true")
            st.sym(":")
            init_true = st.names()
            st.sym(".")
            st.end()
        elif st.is_word("Initially"):
            st.word("Initially")
            st.sym(":")
            init_constraints.append(st.formula())
            st.sym(".")
            st.end()
        elif st.is_word("Goal"):
            if goal_line is not None:
                raise CEError(f"duplicate 'Goal:' statement (first on line "
                              f"{goal_line})", ln.no, 1)
            goal_line = ln.no
            st.word("Goal")
            st.sym(":")
            pack["goal"] = st.formula()
            st.sym(".")
            st.end()
        elif st.is_word("Protocol"):
            if protocol is not None:
                raise CEError("duplicate 'Protocol:' statement", ln.no, 1)
            st.word("Protocol")
            protocol, pos = _parse_block_head(st, lines, pos, 1, False)
        elif st.is_word("Behaviour", "Behavior"):
            st.i += 1
            st.word("of")
            role_col = st.col()
            role = st.name("the role name in backticks")
            if role in skills:
                raise CEError(f"duplicate behaviour for role {role!r}",
                              ln.no, role_col)
            skills[role], pos = _parse_block_head(st, lines, pos, 1, True)
        else:
            raise st.fail("a statement: Roles, Tool, Initially, Goal, "
                          "Protocol or Behaviour of")

    if goal_line is None:
        raise CEError("missing 'Goal:' statement")
    if protocol is None:
        raise CEError("missing 'Protocol:' statement (write 'Protocol: none.' "
                      "for an empty protocol)")
    out = {
        "name": pack["name"],
        "roles": roles if roles is not None else [],
        "capabilities": caps,
        "protocol": protocol,
        "goal": pack["goal"],
        "init_true": init_true if init_true is not None else [],
        "init_constraints": init_constraints,
    }
    if skills:
        out["skills"] = skills
    return ParseResult(out, comments)


def _parse_cap(st: _Stream) -> dict:
    cap: dict[str, Any] = {}
    if st.is_sym("("):
        st.sym("(")
        st.word("owner")
        cap["owner"] = st.name("the owner role in backticks")
        st.sym(")")
    cap.update({"pre": True, "add": [], "del": [], "assigns": {}, "nondet": {}})
    if st.is_sym("."):
        st.sym(".")
        st.end()
        return cap
    st.sym(":")
    seen = set()
    while True:
        col = st.col()
        if st.is_word("requires"):
            st.i += 1
            if "requires" in seen:
                raise CEError("'requires' may appear once per tool; combine "
                              "conditions with 'and'", st.line, col)
            cap["pre"] = st.formula()
            seen.add("requires")
        elif st.is_word("adds", "removes"):
            key = "add" if st.peek().value == "adds" else "del"
            st.i += 1
            if key in seen:
                raise CEError(f"'{'adds' if key == 'add' else 'removes'}' may "
                              "appear once per tool; list every predicate in "
                              "one clause", st.line, col)
            cap[key] = st.names()
            seen.add(key)
        elif st.is_word("sets"):
            st.i += 1
            var = st.name("the variable in backticks")
            if var in cap["assigns"]:
                raise CEError(f"variable {var!r} is set twice", st.line, col)
            st.word("to")
            cap["assigns"][var] = st.expr()
        elif st.is_word("picks"):
            st.i += 1
            var = st.name("the variable in backticks")
            if var in cap["nondet"]:
                raise CEError(f"variable {var!r} is picked twice", st.line, col)
            st.word("with")
            cap["nondet"][var] = st.formula()
        else:
            raise st.fail("a tool clause: requires, adds, removes, sets or picks")
        if st.is_sym(";"):
            st.sym(";")
            continue
        st.sym(".")
        st.end()
        return cap


def _parse_block_head(st: _Stream, lines: list[_Line], pos: int, depth: int,
                      local: bool) -> tuple[list, int]:
    """After a block header's keyword(s): ': none.' or ':' + nested steps."""
    st.sym(":")
    if st.is_word("none"):
        st.word("none")
        st.sym(".")
        st.end()
        return [], pos
    st.end()
    return _parse_steps(lines, pos, depth, local, st.line)


def _parse_steps(lines: list[_Line], pos: int, depth: int, local: bool,
                 header_line: int) -> tuple[list, int]:
    steps: list = []
    while pos < len(lines) and lines[pos].depth >= depth:
        ln = lines[pos]
        if ln.depth > depth:
            raise CEError(f"over-indented: expected {depth * len(INDENT)} "
                          f"spaces", ln.no, 1)
        pos += 1
        st = ln.stream()
        st.sym("-")
        step, pos = _parse_step(st, lines, pos, depth, local)
        steps.append(step)
    if not steps:
        raise CEError("a block header ending in ':' needs indented '- ' steps "
                      "(or write ': none.')", header_line)
    return steps, pos


def _parse_step(st: _Stream, lines: list[_Line], pos: int, depth: int,
                local: bool) -> tuple[dict, int]:
    if st.is_word("checkpoint"):
        st.word("checkpoint")
        st.sym(":")
        f = st.formula()
        st.sym(".")
        st.end()
        return {"goal": f}, pos
    if st.is_word("loop"):
        st.word("loop")
        name = st.name("the loop name in backticks")
        body, pos = _parse_block_head(st, lines, pos, depth + 1, local)
        return {"rec": {"name": name, "body": body}}, pos
    if st.is_word("repeat"):
        st.word("repeat")
        name = st.name("the loop name in backticks")
        st.sym(".")
        st.end()
        return {"continue": name}, pos
    if local:
        return _parse_local_step(st, lines, pos, depth)
    if st.is_word("spawn"):
        st.word("spawn")
        role = st.name("the spawned role in backticks")
        st.sym(".")
        st.end()
        return {"spawn": {"role": role}}, pos
    actor = st.name("a step: `ROLE` uses/tells/chooses, checkpoint, loop, "
                    "repeat or spawn")
    if st.is_word("uses"):
        st.word("uses")
        cap = st.name("the tool name in backticks")
        st.sym(".")
        st.end()
        return {"act": {"cap": cap, "by": actor}}, pos
    if st.is_word("tells"):
        st.word("tells")
        to = st.name("the receiving role in backticks")
        label = st.name("the message label in backticks")
        st.sym(".")
        st.end()
        return {"msg": {"from": actor, "to": to, "label": label}}, pos
    if st.is_word("chooses"):
        st.words("chooses one of")
        body: dict[str, Any] = {"by": actor}
        if st.is_sym("("):
            st.sym("(")
            flags = []
            while True:
                t = st.peek()
                if t is None or t.kind != "WORD" or t.value not in CHOICE_FLAGS:
                    raise st.fail("a choice flag: external or observed")
                if t.value in flags:
                    raise CEError(f"duplicate choice flag {t.value!r}",
                                  st.line, t.col)
                flags.append(t.value)
                st.i += 1
                if st.is_sym(","):
                    st.i += 1
                    continue
                st.sym(")")
                break
            for flag in CHOICE_FLAGS:
                if flag in flags:
                    body[flag] = True
        body["branches"], pos = _parse_branches(st, lines, pos, depth, False)
        return {"choice": body}, pos
    raise st.fail("'uses', 'tells' or 'chooses' after the role")


def _parse_local_step(st: _Stream, lines: list[_Line], pos: int,
                      depth: int) -> tuple[dict, int]:
    if st.is_word("use"):
        st.word("use")
        cap = st.name("the tool name in backticks")
        st.sym(".")
        st.end()
        return {"act": {"cap": cap}}, pos
    if st.is_word("send"):
        st.word("send")
        label = st.name("the message label in backticks")
        st.word("to")
        to = st.name("the receiving role in backticks")
        st.sym(".")
        st.end()
        return {"send": {"to": to, "label": label}}, pos
    if st.is_word("receive"):
        st.word("receive")
        label = st.name("the message label in backticks")
        st.word("from")
        frm = st.name("the sending role in backticks")
        st.sym(".")
        st.end()
        return {"recv": {"from": frm, "label": label}}, pos
    if st.is_word("select"):
        st.words("select one of")
        branches, pos = _parse_branches(st, lines, pos, depth, True)
        return {"select": {"branches": branches}}, pos
    if st.is_word("branch") and st.is_word("on", k=1):
        st.words("branch on")
        frm = st.name("the deciding role in backticks")
        st.words("one of")
        branches, pos = _parse_branches(st, lines, pos, depth, True)
        return {"branch": {"from": frm, "branches": branches}}, pos
    raise st.fail("a behaviour step: use, send, receive, select, branch on, "
                  "checkpoint, loop or repeat")


def _parse_branches(st: _Stream, lines: list[_Line], pos: int, depth: int,
                    local: bool) -> tuple[dict, int]:
    st.sym(":")
    st.end()
    header = st.line
    branches: dict[str, list] = {}
    while pos < len(lines) and lines[pos].depth >= depth + 1:
        ln = lines[pos]
        if ln.depth > depth + 1:
            raise CEError(f"over-indented: expected "
                          f"{(depth + 1) * len(INDENT)} spaces", ln.no, 1)
        pos += 1
        bst = ln.stream()
        bst.sym("-")
        bst.word("branch")
        col = bst.col()
        label = bst.name("the branch label in backticks")
        if label in branches:
            raise CEError(f"duplicate branch label {label!r}", ln.no, col)
        branches[label], pos = _parse_block_head(bst, lines, pos, depth + 2,
                                                 local)
    if not branches:
        raise CEError("a choice needs at least one indented "
                      "'- branch `L`:' line", header)
    return branches, pos


def parse_ce(text: str) -> dict:
    """Parse a CE document into a pack in canonical form (not yet validated)."""
    return parse_ce_detailed(text).pack


def compile_ce(text: str) -> dict:
    """Parse, then run the same deterministic schema gate as every front-end."""
    pack = parse_ce(text)
    validate_pack(pack)
    return pack


# --------------------------------------------------------------------------
# Extracting CE from model output
# --------------------------------------------------------------------------

_FENCE_RE = re.compile(r"```[ \t]*([A-Za-z0-9_-]*)[ \t]*\n(.*?)\n[ \t]*```",
                       re.S)


def extract_ce(text: str) -> str:
    """The CE document in a model response.

    Prefers a fenced block tagged ``ce``; otherwise the first fenced block
    that starts with ``Skill``; otherwise everything from the first line that
    starts with ``Skill `` to the end.  No repair is attempted: a malformed
    document fails in `parse_ce` with a line/column message.
    """
    blocks = _FENCE_RE.findall(text)
    for tag, body in blocks:
        if tag.lower() == "ce":
            return body.strip("\n") + "\n"
    for _, body in blocks:
        if body.lstrip().startswith("Skill "):
            return body.strip("\n") + "\n"
    m = re.search(r"(?m)^Skill `", text)
    if m:
        return text[m.start():].strip("\n") + "\n"
    raise CEError("no CE document found (expected a line starting with "
                  "'Skill `NAME`.')")

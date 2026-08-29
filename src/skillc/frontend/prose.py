"""Deterministic prose analysis for the markdown front-end.

`markdown.py` originally compacted a skill into the weakest pack that says
anything at all: one capability per granted tool, an effect `used_<tool>`, and
a goal that is the conjunction of those.  Such a pack can only ever be refuted
for a *missing tool* -- the goal is true by construction as soon as the tools
exist.

This module reads the parts of an ordinary skill document that actually carry
meaning, so the pack can say what the skill is really claiming:

  * **Completion condition.**  "Your job is finished when the flight is
    **booked** and a **confirmation email has been sent**."  Each bold clause
    becomes a goal conjunct, named after its head participle (`booked`,
    `sent`).  A numeric clause inside a conjunct ("booked at a price below
    500") becomes an arithmetic comparison.
  * **Participants.**  "Two participants take part: a **router** and a
    **handler**." / "A single **worker** carries out this skill."  A skill
    that never says otherwise has the single role `agent`.
  * **Workflow steps.**  Numbered steps in the Workflow/Contract section.  A
    step invokes a declared tool when it names it -- in backticks, or in plain
    English that stems to the tool's own name ("Book the chosen flight" ->
    `book_flight`).  A step whose head announces a choice and whose body is a
    bullet list becomes a protocol `choice`, one branch per bullet;
    "the router tells the handler `go_simple`" inside a branch becomes a
    `msg`; "spawn a helper subagent" becomes a `spawn`.
  * **Effects.**  A step that mentions a goal condition establishes it: the
    act nearest the mention gets it in its `add` list.  A goal condition no
    step ever mentions therefore has *no establisher* -- which is exactly the
    failure the checker refutes.
  * **Tool notes.**  Sentences in the Tools section that name a tool:
    "`publish` requires the report to be **approved**" becomes a guard;
    "`filter` ... marks the shortlist **filtered**" becomes an effect;
    "`book_premium` ... costs 800 or more" becomes a nondeterministic bound on
    the document's numeric quantity.
  * **Loops.**  A workflow that writes "Loop:" above its steps repeats them;
    a step that says the work goes back round ("go back to the start of the
    loop") is where it repeats, and the prose saying it is past the loop
    ("Once the loop has been left:") is where it stops.
  * **Declared role behaviour.**  A "Declared handler behaviour" section
    becomes `skills[handler]`, so the checker can test it against the
    handler's projected contract.

Everything here is heuristic and untrusted, exactly like the rest of the
front-end: a misreading only means the checker decides a different pack, and
the compiled pack is printed for inspection.  Nothing in this module knows
about any particular skill: it keys on ordinary English conventions
(completion sentences, numbered steps, bullet lists, backticked tool names).

Deliberate limits, stated rather than hidden:
  * at most ONE numeric quantity per document (a skill that budgets two
    different numbers is compacted as if they were the same one);
  * a loop is only read where the document draws one ("Loop:"); a retry
    described in passing is compacted as the straight-line path through it,
    which is the path the author says reaches the goal.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# --------------------------------------------------------------------------
# Morphology: crude but deterministic stemming, enough to tell "Book the
# flight" from "the booking is confirmed".
# --------------------------------------------------------------------------

IRREGULAR = {
    "sent": "send", "paid": "pay", "made": "make", "built": "build",
    "found": "find", "given": "give", "written": "write", "wrote": "write",
    "done": "do", "taken": "take", "took": "take", "gone": "go",
    "sold": "sell", "told": "tell", "kept": "keep", "held": "hold",
    "met": "meet", "drawn": "draw", "shown": "show", "known": "know",
    "seen": "see", "chosen": "choose", "chose": "choose", "spent": "spend",
    "left": "leave", "lost": "lose", "got": "get", "gotten": "get",
    "bought": "buy", "brought": "bring", "caught": "catch",
    "taught": "teach", "thought": "think", "sought": "seek", "dealt": "deal",
    "felt": "feel", "sat": "sit", "began": "begin", "begun": "begin",
    "ran": "run", "sang": "sing", "read": "read", "put": "put", "set": "set",
    "cut": "cut", "hit": "hit", "let": "let", "split": "split",
    "shut": "shut", "cost": "cost", "hurt": "hurt", "spread": "spread",
}

# Words that carry no discriminating meaning: they must never make a tool
# match a step or a step establish a goal condition.
STOPWORDS = frozenset("""
a an the this that these those it its it's their they them there here
and or but so then than if when while once until after before
is are was were be been being am do does did done doing
have has had having will would shall should can could may might must
of in on at to for from with without by into onto over under about as
not no nor never any all each every some both either neither
i you he she we us our your my his her one two three
what which who whom whose how why where
""".split())


def stem(word: str) -> str:
    """A conservative stem: enough to relate 'booked'/'booking'/'book'."""
    w = word.lower().strip("_")
    if w in IRREGULAR:
        return IRREGULAR[w]
    for suf, keep in (("ingly", 5), ("edly", 4), ("ing", 5), ("ies", 4),
                      ("ied", 4), ("ed", 4), ("es", 4), ("ly", 4), ("s", 3)):
        if w.endswith(suf) and len(w) >= keep:
            w = w[: -len(suf)]
            if suf in ("ies", "ied"):
                w += "y"
            break
    if len(w) > 3 and w.endswith("e"):
        w = w[:-1]
    if len(w) > 3 and w[-1] == w[-2] and w[-1] not in "aeiou":
        w = w[:-1]          # stopped -> stopp -> stop
    return w


WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*")


def stem_index(text: str) -> dict[str, int]:
    """stem -> offset of its first occurrence in `text`.

    Indexes each word, each underscore-separated part of an identifier (so
    `send_email` also answers for "send" and "email"), and each pair of
    adjacent words joined up (so "look up" answers for `lookup`).
    """
    idx: dict[str, int] = {}
    toks = [(m.group(0), m.start()) for m in WORD_RE.finditer(text)]

    def put(key: str, pos: int) -> None:
        if key and key not in idx:
            idx[key] = pos

    for i, (w, pos) in enumerate(toks):
        put(stem(w), pos)
        if "_" in w:
            for part in w.split("_"):
                put(stem(part), pos)
        if i + 1 < len(toks):
            put(stem(w + toks[i + 1][0]), pos)
    return idx


def content_stems(text: str) -> list[str]:
    return [stem(w) for w in WORD_RE.findall(text)
            if w.lower() not in STOPWORDS]


# --------------------------------------------------------------------------
# Numeric clauses
# --------------------------------------------------------------------------

_OPS_BEFORE = {
    "below": "<", "under": "<", "less than": "<", "cheaper than": "<",
    "lower than": "<", "at most": "<=", "no more than": "<=",
    "not more than": "<=", "at or below": "<=", "up to": "<=",
    "above": ">", "over": ">", "more than": ">", "higher than": ">",
    "greater than": ">", "at least": ">=", "at or above": ">=",
    "no less than": ">=", "starting at": ">=",
}
_OPS_AFTER = {
    "or more": ">=", "or above": ">=", "or greater": ">=", "or higher": ">=",
    "or less": "<=", "or below": "<=", "or under": "<=", "or lower": "<=",
}

_NUM_BEFORE_RE = re.compile(
    r"\b(" + "|".join(sorted(_OPS_BEFORE, key=len, reverse=True))
    + r")\s+\$?\s*([0-9][0-9,]*)", re.I)
_NUM_AFTER_RE = re.compile(
    r"\$?\s*\b([0-9][0-9,]*)\s+(" + "|".join(sorted(_OPS_AFTER, key=len,
                                                    reverse=True)) + r")\b",
    re.I)

# The nouns a skill uses for the money-ish quantity it budgets.  The whole
# document is modelled as having a single numeric dimension (see module
# docstring), so these are all the same variable.
QUANTITY_NOUNS = ("price", "prices", "cost", "costs", "fare", "fares",
                  "amount", "total", "budget", "ceiling", "spend", "charge",
                  "fee", "fees", "rate")


@dataclass(frozen=True)
class NumClause:
    op: str
    value: int
    start: int
    end: int
    noun: Optional[str] = None


def find_num_clause(text: str) -> Optional[NumClause]:
    """The first numeric comparison stated in `text`, if any."""
    cands: list[NumClause] = []
    for m in _NUM_BEFORE_RE.finditer(text):
        cands.append(NumClause(_OPS_BEFORE[m.group(1).lower()],
                               int(m.group(2).replace(",", "")),
                               m.start(), m.end()))
    for m in _NUM_AFTER_RE.finditer(text):
        cands.append(NumClause(_OPS_AFTER[m.group(2).lower()],
                               int(m.group(1).replace(",", "")),
                               m.start(), m.end()))
    if not cands:
        return None
    c = min(cands, key=lambda c: c.start)
    noun = None
    for m in re.finditer(r"\b(" + "|".join(QUANTITY_NOUNS) + r")\b",
                         text, re.I):
        noun = m.group(1).lower()
        if m.start() < c.start:
            break
    return NumClause(c.op, c.value, c.start, c.end, noun)


def quantity_var(noun: Optional[str]) -> str:
    """Canonical name of the document's single numeric quantity."""
    if not noun:
        return "amount"
    s = stem(noun)
    # The money-ish nouns a skill mixes freely ("a price below 500", "fares
    # under 500", "costs 800 or more") all name the one quantity it budgets.
    if s in ("pric", "fare", "cost", "charg", "fee", "ceil", "spend",
             "budget", "rate"):
        return "price"
    return {"amount": "amount", "total": "total"}.get(s, s or "amount")


# --------------------------------------------------------------------------
# Goal conditions
# --------------------------------------------------------------------------

DONE_RE = re.compile(
    r"(?:your\s+job\s+is\s+finished\s+when"
    r"|you(?:'re|\s+are)\s+done\s+when"
    r"|(?:the\s+)?(?:job|task|skill|work)\s+is\s+"
    r"(?:finished|complete|completed|done)\s+when"
    r"|this\s+is\s+done\s+when"
    r"|success\s+means"
    r"|definition\s+of\s+done\s*:)"
    r"(.{0,400}?)(?<!\d)\.(?:\s|$)", re.I | re.S)

BOLD_RE = re.compile(r"\*\*([^*]+?)\*\*")

# Head of a goal condition: the last participle-looking word in the clause.
_PARTICIPLE_RE = re.compile(r"\b([A-Za-z]{3,})\b")


def _is_participle(word: str) -> bool:
    w = word.lower()
    if w in STOPWORDS or w in QUANTITY_NOUNS:
        # "cost" is a participle in English but never the state a goal
        # describes -- in "ordered at a cost below 200" it names the
        # quantity, and the state is "ordered".
        return False
    return w.endswith("ed") or w in IRREGULAR


def condition_predicate(phrase: str) -> Optional[str]:
    """Name the state a goal condition describes: its head participle.

    "booked flight" -> booked; "a confirmation email has been sent" -> sent;
    "the ticket is resolved" -> resolved.  Returns None when the phrase names
    no state (nothing that reads as a past participle).

    A clause whose whole content is *one noun and that participle* names a
    state **of that noun**, and keeps the noun: "the ledger has been updated"
    -> ledger_updated, "a confirmation has been sent" -> confirmation_sent,
    "the order found" -> order_found.  Anything longer is read as before --
    the extra words are scene-setting ("a confirmation email has been sent"),
    not part of the state's name -- so the author picks which reading they
    want by how tightly they bold the clause.
    """
    words = [m.group(1) for m in _PARTICIPLE_RE.finditer(phrase)
             if m.group(1).lower() not in STOPWORDS]
    heads = [w for w in words if _is_participle(w)]
    if not heads:
        return None
    head = heads[-1].lower()
    if (len(words) == 2 and words[1].lower() == head
            and not _is_participle(words[0])
            and words[0].lower() not in QUANTITY_NOUNS):
        return words[0].lower() + "_" + head
    return head


@dataclass
class Condition:
    """One conjunct of the skill's stated completion condition.

    `context` is the run of the completion sentence this conjunct closes --
    the unbolded words around it ("and the asset register has been
    **updated**"), which is where the nouns live when the author bolds only
    the participle.
    """
    text: str
    predicate: Optional[str] = None
    num: Optional[NumClause] = None
    context: str = ""


def goal_clause(prose: str) -> Optional[str]:
    """The raw text of the document's completion sentence, if it has one."""
    m = DONE_RE.search(prose)
    return m.group(1) if m else None


def parse_goal(prose: str) -> tuple[list[Condition], Optional[str]]:
    """Conditions the document says must hold when the skill is finished,
    plus the name of the numeric quantity it budgets (if any)."""
    m = DONE_RE.search(prose)
    if not m:
        return [], None
    clause = m.group(1)
    parts = list(BOLD_RE.finditer(clause))
    if not parts:
        return [], None
    conds: list[Condition] = []
    var: Optional[str] = None
    prev = 0
    for b in parts:
        text = " ".join(b.group(1).split())
        context = " ".join(clause[prev:b.end(1)].replace("*", " ").split())
        prev = b.end()
        num = find_num_clause(text)
        rest = text
        if num is not None:
            rest = (text[:num.start] + " " + text[num.end:]).strip()
            if var is None:
                var = quantity_var(num.noun)
        conds.append(Condition(text, condition_predicate(rest), num, context))
    return conds, var


# --------------------------------------------------------------------------
# Participants
# --------------------------------------------------------------------------

ROLE_CUE_RE = re.compile(
    r"(?:participants?\s+take\s+part"
    r"|participants?\s*:"
    r"|carr(?:y|ies)\s+out\s+this\s+skill"
    r"|take\s+part\s+in\s+this\s+skill"
    r"|roles?\s*:)", re.I)

_ROLE_NAME_RE = re.compile(
    r"\*\*([A-Za-z][A-Za-z0-9 _-]{0,24}?)\*\*(?:\s*\(`([A-Za-z][\w-]*)`\))?")


@dataclass
class Role:
    name: str                       # role id used in the pack
    aliases: frozenset              # words in the prose that refer to it


def parse_roles(prose: str) -> list[Role]:
    """Participants the document introduces, in the order it introduces them."""
    roles: list[Role] = []
    seen: set[str] = set()
    for cue in ROLE_CUE_RE.finditer(prose):
        # the sentence the cue sits in
        start = prose.rfind("\n\n", 0, cue.start()) + 1
        end = prose.find("\n\n", cue.end())
        sentence = prose[start: end if end != -1 else len(prose)]
        for m in _ROLE_NAME_RE.finditer(sentence):
            display = " ".join(m.group(1).split()).lower()
            if not re.fullmatch(r"[a-z][a-z0-9 _-]*", display):
                continue
            rid = (m.group(2) or display).lower().replace(" ", "_")
            if rid in seen:
                continue
            seen.add(rid)
            roles.append(Role(rid, frozenset({rid, display,
                                              display.replace(" ", "_")})))
    return roles


# --------------------------------------------------------------------------
# Document structure: sections, numbered steps, bullets
# --------------------------------------------------------------------------

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.M)
STEP_RE = re.compile(r"^ {0,3}(\d+)[.)]\s+")
BULLET_RE = re.compile(r"^(\s*)[-*+]\s+")


@dataclass
class Section:
    title: str
    body: str


def split_sections(prose: str) -> list[Section]:
    """The document's headed sections (plus a leading untitled one)."""
    out: list[Section] = []
    marks = list(HEADING_RE.finditer(prose))
    if not marks or marks[0].start() > 0:
        out.append(Section("", prose[: marks[0].start() if marks else len(prose)]))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(prose)
        out.append(Section(m.group(2).strip(), prose[m.end(): end]))
    return out


def find_section(sections: list[Section], pattern: str) -> Optional[Section]:
    rx = re.compile(pattern, re.I)
    for s in sections:
        if rx.search(s.title):
            return s
    return None


def numbered_steps(body: str) -> list[str]:
    """Top-level numbered steps, each with its indented continuation lines."""
    lines = body.split("\n")
    steps: list[list[str]] = []
    cur: Optional[list[str]] = None
    pending: list[str] = []
    for line in lines:
        if STEP_RE.match(line):
            if cur is not None:
                steps.append(cur)
            cur = [line]
            pending = []
        elif cur is not None:
            if not line.strip():
                pending.append(line)
            elif line[:1].isspace():
                cur.extend(pending)
                pending = []
                cur.append(line)
            else:
                steps.append(cur)
                cur = None
                pending = []
    if cur is not None:
        steps.append(cur)
    return ["\n".join(s) for s in steps]


# A workflow that goes round: a line that is nothing but "Loop:" (or
# "Repeat:") opens a repeated block, and the first later line that talks about
# being past the loop ("Once the loop has been left:") closes it again.
LOOP_OPEN_RE = re.compile(r"\A\s*(?:loop|repeat)\s*:\s*\Z", re.I)
_LEAVE_RE = re.compile(
    r"\b(?:after|once|outside|exits?|exited|leaves?|leaving|left|ends?|ended"
    r"|finished|done\s+with)\b", re.I)


def _closes_loop(line: str) -> bool:
    return (bool(re.search(r"\bloop\b", line, re.I))
            and bool(_LEAVE_RE.search(line))
            and not STEP_RE.match(line) and not BULLET_RE.match(line)
            and not line[:1].isspace())


def split_loop_segments(body: str) -> list[tuple[str, str]]:
    """Segment a workflow body into ("seq" | "loop", text) runs.

    A document that writes "Loop:" above its steps is saying those steps go
    round again; the block ends where the prose says it is past the loop, or
    at the end of the section.
    """
    segs: list[tuple[str, str]] = []
    kind = "seq"
    cur: list[str] = []
    for line in body.split("\n"):
        if kind == "seq" and LOOP_OPEN_RE.match(line):
            segs.append((kind, "\n".join(cur)))
            cur, kind = [], "loop"
            continue
        if kind == "loop" and _closes_loop(line):
            segs.append((kind, "\n".join(cur)))
            cur, kind = [], "seq"
            continue
        cur.append(line)
    segs.append((kind, "\n".join(cur)))
    return [s for s in segs if s[1].strip()]


# "go back to step 1", "start over", "round again": the step says the block
# repeats rather than carrying on.
CONTINUE_RE = re.compile(
    r"\b(?:go(?:es)?\s+back\s+to|going\s+back\s+to|start\s+(?:again|over)"
    r"|starts\s+(?:again|over)|round\s+again|again\s+from\s+the\s+(?:top|start)"
    r"|repeat(?:s)?\s+(?:the\s+loop|from\s+the\s+(?:top|start)))\b", re.I)


def split_bullets(text: str) -> tuple[str, list[str]]:
    """(head text before the first bullet, one string per bullet).

    A bullet keeps its indented continuation lines; an unindented paragraph
    after the list closes it (that paragraph is commentary, not an item).
    """
    lines = text.split("\n")
    head: list[str] = []
    bullets: list[list[str]] = []
    indent: Optional[int] = None
    pending: list[str] = []
    closed = False
    for line in lines:
        m = BULLET_RE.match(line)
        if m and not closed and (indent is None or len(m.group(1)) <= indent):
            indent = len(m.group(1))
            bullets.append([line])
            pending = []
        elif bullets and not closed:
            if not line.strip():
                pending.append(line)
            elif line[:1].isspace():
                bullets[-1].extend(pending)
                pending = []
                bullets[-1].append(line)
            else:
                closed = True
        elif not bullets:
            head.append(line)
    return "\n".join(head), ["\n".join(b) for b in bullets]


def sentences(text: str) -> list[str]:
    """Rough sentence split; good enough for one-clause tool notes."""
    flat = " ".join(text.split())
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", flat) if s.strip()]


# --------------------------------------------------------------------------
# Invocation verbs (shared with the legacy used_<tool> extraction)
# --------------------------------------------------------------------------

INVOKE_RE = re.compile(
    r"\b(?:via|use[sd]?|using|call(?:s|ed|ing)?|invoke[sd]?|invoking"
    r"|run(?:s|ning)?|through)"
    r"\s+(?:the\s+)?`([A-Za-z][A-Za-z0-9_.:-]*)`",
    re.I,
)

# A negation word in the ~20 characters before an invocation verb, used to
# skip "do NOT use `X`" false positives.
NEGATION_RE = re.compile(r"\b(?:not|never|without|instead\s+of)\b", re.I)


def negated_before(text: str, pos: int, window: int = 24) -> bool:
    return bool(NEGATION_RE.search(text[max(0, pos - window):pos]))

"""Stance of reasoning text: what the agent commits to, as opposed to what it mentions.

The runtime monitor reads an agent's reasoning (thinking summaries, progress notes,
visible text).  A sentence that names a requirement is not yet an intention: the agent
may be weighing an option, repeating what a README or a web page says, or stating a
fact.  Only a *committed* sentence predicts the next tool call.  This module splits
reasoning text into units and gives each one a stance, deterministically:

  commit      first-person intent ("I'll", "let me", "now I run"), a step label
              ("Next: ..."), an imperative or gerund of an action verb at the start
              ("Delete the old table", "Running `rm -rf` ..."), or a drafted shell
              command (a unit that is one backticked command, a line in a shell fence)
  deliberate  a question, or a hedge ("maybe", "could", "whether") without a commit
              marker, or a hedge right before one ("maybe I'll ...")
  report      what someone or something else says: "the README mentions", "the issue
              asks", "according to", a quotation, a `>` quote line
  narration   a retrospective account of what was already done: a past-tense action verb
              at the start ("Ran `which go`", "Created sample-app/"), a first-person past
              ("I ran", "we tested") or a report label ("Work dir:", "Commands run:",
              "Result:"); a command quoted right after a narration is evidence, not a draft
              (`classify_all`)
  mention     everything else: a declarative statement ("X is set in .env")

Decisive labels commit ("Quickest fix: ...", "The simplest way is to ...", "Plan: ..."), and
so does acknowledging a consequence of one's own act ("the local edits will go away").

An *anaphoric* commit ("I'll do that", "I'll do as the issue asks", "OK, doing it now")
has no content of its own: it adopts the unit before it.  When that unit is a report,
the agent is about to act on someone else's words; `interaction.scan` uses this to
recognise compliance with instructions found in tool output.

Negation is clause-scoped (`negated`): "I won't push to prod; I'll push to staging"
negates only the first clause.

Everything here is a heuristic over ordinary English conventions; nothing calls a
model and nothing depends on a particular agent.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["Unit", "split_units", "classify", "classify_all", "negated", "clauses",
           "is_anaphoric", "refers_back", "commit_part", "report_source", "anaphoric_tail",
           "presence_check", "COMMIT", "DELIBERATE", "REPORT", "MENTION", "NARRATION"]

COMMIT, DELIBERATE, REPORT, MENTION = "commit", "deliberate", "report", "mention"
NARRATION = "narration"


@dataclass(frozen=True)
class Unit:
    text: str                 # the unit, without bullet markers or the `>` of a quote
    line: int                 # 1-based line of the reasoning text it starts on
    in_code: bool = False     # inside a fenced code block
    quote: bool = False       # a `>` quote line
    lang: str = ""            # the info string of the fence it is in


# ---------------------------------------------------------------------- splitting

FENCE = re.compile(r"^\s*(```|~~~)\s*([\w+-]*)")
BULLET = re.compile(r"^\s*(?:[-*+•]|\d+[.)])\s+")
SHELL_LANGS = frozenset({"", "bash", "sh", "shell", "zsh", "console", "terminal", "powershell",
                         "pwsh", "ps1", "ps", "cmd", "bat", "fish", "sql", "psql"})
# a sentence ends at . ! ? (and closing quotes or brackets) followed by space
SENTENCE_END = re.compile(r"[.!?]+[\"')\]”]*\s+")
ABBREVIATIONS = ("e.g.", "i.e.", "etc.", "vs.", "cf.", "approx.", "no.")


def _norm(text: str) -> str:
    return text.replace("’", "'").replace("‘", "'")


def _in_backticks(text: str, pos: int) -> bool:
    return text.count("`", 0, pos) % 2 == 1


def _sentences(text: str) -> list[str]:
    """Sentence split that never cuts inside a backticked span or after an abbreviation."""
    out, start = [], 0
    for m in SENTENCE_END.finditer(text):
        if _in_backticks(text, m.start()):
            continue
        head = text[start:m.end()].rstrip()
        if head.lower().endswith(ABBREVIATIONS):
            continue
        out.append(text[start:m.end()].strip())
        start = m.end()
    rest = text[start:].strip()
    if rest:
        out.append(rest)
    return [s for s in out if s]


def split_units(text: str) -> list[Unit]:
    """Units of reasoning text: one per sentence, bullet, quote line or code line."""
    units: list[Unit] = []
    fence: str | None = None          # the fence's language while inside one
    for no, raw in enumerate(_norm(text).splitlines(), 1):
        m = FENCE.match(raw)
        if m:
            fence = None if fence is not None else m.group(2).lower()
            continue
        if fence is not None:
            if raw.strip():
                units.append(Unit(raw.strip(), no, in_code=True, lang=fence))
            continue
        line = raw.strip()
        if not line:
            continue
        if line.startswith(">"):
            body = line.lstrip("> ").strip()
            if body:
                units.append(Unit(body, no, quote=True))
            continue
        line = BULLET.sub("", line)
        for s in _sentences(line):
            units.append(Unit(s, no))
    return units


# ---------------------------------------------------------------------- clauses, negation

CLAUSE_BREAK = re.compile(r";|,\s*(?:but|so|instead)\b|\s+but\s+|\s(?=instead of\b)|"
                          r"\s(?=rather than\b)", re.IGNORECASE)
NEGATION = re.compile(r"(?:\b(?:no|not|without|cannot|never|avoid(?:ing)?|lacks?|lacking|"
                      r"unavailable|refuse|skip(?:ping)?|instead of|rather than)\b|n't\b"
                      # deferral: "leave any purchase to the user" is not doing it
                      r"|\bleav(?:e|ing)\b(?=[^;\n]{0,60}\bto (?:the user|the human|you)\b))",
                      re.IGNORECASE)
# "instead of X, Y" / "rather than X, Y": the negation ends at the comma
COMMA_SCOPED = ("instead of", "rather than")
# a comma splice opens a new independent clause with its own subject and verb ("it is not
# an address, it is an instruction to ..."): a negation before it does not reach past it
COMMA_SPLICE = re.compile(r",\s*(?:it|this|that|they|he|she|I|we|there)\s*(?:is|are|was|were|"
                          r"'s|'re|'ll|will|has|have|had)\b", re.IGNORECASE)


def clauses(text: str) -> list[tuple[int, int]]:
    """(start, end) offsets of the clauses of `text`: split at `;`, `, but`, `, so`,
    `, instead`, ` instead of` and ` rather than` (the last two stay at the start of the
    clause they open, where they negate what follows)."""
    spans, start = [], 0
    for m in CLAUSE_BREAK.finditer(text):
        if _in_backticks(text, m.start()):
            continue
        spans.append((start, m.start()))
        start = m.end()
    spans.append((start, len(text)))
    return [(a, b) for a, b in spans if text[a:b].strip()] or [(0, len(text))]


# checking that a value is set, present or valid, without showing it, does not use it
PRESENCE = re.compile(r"\s-[zn]\s|\bis (?:not )?set\b|\bunset\b|\bnot set\b|\bexists?\b|"
                      r"\bpresent\b|\bdefined\b|\bconfigured\b|\bmissing\b|\bwhether\b|"
                      r"\bwithout (?:printing|showing|revealing|exposing)|\binvalid\b|"
                      r"\bexpired\b", re.IGNORECASE)


def presence_check(unit_text: str, match_start: int) -> bool:
    """Whether the clause around `match_start` only checks that something is set, present
    or valid ("I'll echo whether OPENAI_API_KEY is set without printing it")."""
    text = _norm(unit_text)
    a, b = next(((a, b) for a, b in clauses(text) if a <= match_start <= b), (0, len(text)))
    return bool(PRESENCE.search(text, a, b))


def negated(unit_text: str, match_start: int) -> bool:
    """Whether a match at `match_start` is negated: a negation word occurs before it in
    the same clause."""
    text = _norm(unit_text)
    a, b = next(((a, b) for a, b in clauses(text) if a <= match_start <= b), (0, len(text)))
    for m in NEGATION.finditer(text[:b], a):
        if m.start() >= match_start:
            break
        if m.group(0).lower() in COMMA_SCOPED and "," in text[m.end():match_start]:
            continue
        if COMMA_SPLICE.search(text, m.end(), match_start):
            continue
        return True
    return False


# ---------------------------------------------------------------------- stance markers

ACTION_VERBS = (
    "run", "execute", "send", "delete", "push", "publish", "deploy", "remove", "drop", "wipe",
    "transfer", "pay", "install", "call", "use", "apply", "move", "overwrite", "force",
    "email", "mail", "post", "upload", "share", "forward", "reply", "create", "write", "edit",
    "update", "truncate", "purge", "destroy", "erase", "format", "reset", "grant", "disable",
    "enable", "chmod", "chown", "print", "echo", "cat", "dump", "show", "display", "paste",
    "buy", "order", "purchase", "submit", "migrate", "rename", "copy", "download", "fetch",
    "kill", "restart", "commit", "merge", "rebase", "invite", "notify", "book", "cancel",
    "charge", "refund", "approve", "add", "set", "change", "modify", "clean", "clear",
    "empty", "rm", "drop", "launch", "start", "stop", "trigger", "build", "release", "ship",
    "open", "close", "archive", "revoke", "rotate", "export", "import", "sync", "invoke",
)
DOUBLED = {"run", "drop", "stop", "ship", "set", "commit", "submit", "chat", "cut", "put"}


def _verb_forms() -> str:
    forms = set()
    for v in ACTION_VERBS:
        forms.add(v)
        if v in DOUBLED:
            forms.add(v + v[-1] + "ing")
        elif v.endswith("e") and not v.endswith("ee"):
            forms.add(v[:-1] + "ing")
        else:
            forms.add(v + "ing")
    return "|".join(sorted(forms, key=len, reverse=True))


VERBS = _verb_forms()
COMMIT_MARKERS = [re.compile(p, re.IGNORECASE) for p in (
    r"\b(?:I|we)(?:'ll| will| am going to|'m going to| are going to|'re going to| need to"
    r"| have to| must| plan to| intend to| can now| should now| shall)\b",
    r"\b(?:let me|let's|lets)\b",
    rf"\b(?:now|next|then)\s+(?:I\s+)?(?:will\s+|'ll\s+)?(?:{VERBS})\b",
    r"\b(?:going to|about to|proceed(?:ing)? (?:to|with)|time to|ready to|start(?:ing)? by)\b",
    # "I can go ahead and call it", "I can just send it", "I might as well wipe it",
    # "Go ahead and delete it": a decision taken, phrased as a permission to oneself
    r"\b(?:I|we) can (?:now |then |safely |simply |just )?(?:go ahead|just)\b",
    r"\b(?:I|we) (?:might|may) as well\b",
    r"^\s*(?:so |ok,? |okay,? |then,? )?go ahead and\b",
)]
LABEL = re.compile(r"^\s*(?:now|next|then|finally|first|second|third|step \d+|todo|action|"
                   r"plan|afterwards|fix|approach|solution|decision)\b\s*(?P<sep>[:,])?\s*(?P<rest>.*)$", re.IGNORECASE)
LEADING_VERB = re.compile(rf"^(?:`|(?:{VERBS})\b(?!\s+(?:is|are|was|were|has|have|had|will|"
                          r"would|can|could|should|of|for|time)\b))", re.IGNORECASE)
WHOLE_COMMAND = re.compile(r"^\$?\s*`[^`]+`[.:;!]?$")
HEDGE = re.compile(r"\b(?:could|might|maybe|perhaps|possibly|options?|optional(?:ly)?|"
                   r"alternatively|consider(?:ing)?|whether|would be|one way|another way|"
                   r"if (?:I|we) (?:wanted|were))\b", re.IGNORECASE)
ATTRIBUTION = re.compile(
    # "the README mentions", "a comment in the code says", "one email instructs me",
    # "the lead's description tells me", "the page text instructs"
    r"\b(?:the|this|that|a|an|one|its|their|some)\s+(?:[\w'-]+\s+){0,2}?"
    r"(?P<who>user|readme|docs?|documentation|issue|comment|pr|pull request|page|web ?page|"
    r"site|website|e-?mails?|messages?|file|output|error|result|response|tool result|"
    r"tool output|instructions?|prompt|system prompt|note|ticket|invites?|calendar event|"
    r"article|post|repo(?:sitory)?|changelog|log|description|text|document|attachment|"
    r"config(?:uration)?|code|record|review|reply|banner|snippet|header|title|metadata|"
    # the counterparty of a customer-facing deployment, not the agent's principal
    r"customer|caller|client|visitor|requester|buyer|guest|member|driver|patient|person)"
    r"(?:\s+(?:in|on|from|of)\s+(?:the|my|this|that|a|an|its|their)\s+[\w'-]+)?\s+"
    r"(?:has |have |had |now |just |also |keeps? |kept )?"
    r"(?:says?|said|mentions?|mentioned|asks?|asked|wants?|wanted|requests?|requested|"
    r"suggests?|suggested|instructs?|instructed|tells?|told|contains?|contained|includes?|"
    r"included|states?|stated|reads?|recommends?|recommended|directs?|directed|demands?|"
    r"demanded|insists?|insisted|saying)\b",
    re.IGNORECASE)
# a pronoun or an unnamed person as the source, only with a verb that addresses the agent
# ("He now wants me to ...", "They keep saying ...", "someone told me ...")
PERSON_ATTRIBUTION = re.compile(
    r"(?:^|[.;,:!-]\s*|\b(?:and|but|so|then)\s+)(?P<who>he|she|they|someone|somebody)\s+"
    r"(?:\w+\s+)?(?:wants? me to|wanted me to|told me|tells me|asked me to|asks me to|"
    r"demands?|demanded|insists?|insisted|keeps? saying|kept saying|keeps? asking|"
    r"kept asking)\b", re.IGNORECASE)
ACCORDING = re.compile(r"\baccording to\b", re.IGNORECASE)
# a request addressed to the agent, whatever the grammar of its source: a gerund or
# participle ("an instruction telling me to ..."), a plural or partitive subject ("one of
# the tickets asks me to ..."), a relative clause in between ("a note tucked into the
# comment asking me to ..."), "addressed to me and asks ..."; the source is the last
# noun before the verb in the same comma-free stretch
REQUEST_VERB = re.compile(
    r"\b(?:telling|asking|instructing|directing|ordering|urging|requesting|demanding|"
    r"tells|asks|instructs|directs|orders|urges|requests|demands|wants|wanted|told|asked|"
    r"instructed|directed)\s+(?:me|us|the (?:agent|assistant|model|ai|bot))\b"
    r"|\baddressed to (?:me|us|the (?:agent|assistant|model|ai|bot))\b", re.IGNORECASE)
REQUEST_SOURCE = re.compile(
    r"\b(?P<who>user|instructions?|requests?|notes?|messages?|comments?|texts?|commands?|"
    r"prompts?|notices?|tickets?|e-?mails?|pages?|issues?|files?|documents?|readme|docs?|"
    r"descriptions?|posts?|repl(?:y|ies)|reviews?|banners?|snippets?|outputs?|strings?|"
    r"payloads?|tools?|servers?|results?|responses?|participants?|customers?|callers?|"
    r"clients?|visitors?|senders?|attackers?|someone|somebody|websites?|sites?|"
    r"attachments?|scripts?|packages?|dependency|dependencies|errors?|pr|pull requests?|"
    r"threads?|lines?|fields?|cells?|rows?)\b(?!')", re.IGNORECASE)


class _Span:
    """A match-like (start, end) of an attribution found in two steps."""

    def __init__(self, start: int, end: int, who: str) -> None:
        self._s, self._e, self.who = start, end, who

    def start(self) -> int:
        return self._s

    def end(self) -> int:
        return self._e

    def group(self, name: str = "who") -> str:
        return self.who


def _requests(text: str) -> list[_Span]:
    """The requests addressed to the agent in `text`, each with its source."""
    out = []
    for v in REQUEST_VERB.finditer(text):
        head = text[max(0, v.start() - 120):v.start()]
        head = head[max(head.rfind(c) for c in ".;?!") + 1:]
        # the nearest comma-free stretch first; past a comma (a relative clause set off by
        # commas: "a note, buried below the trace, asking me to ...") only when it has none
        nouns = list(REQUEST_SOURCE.finditer(head[head.rfind(",") + 1:]))             or list(REQUEST_SOURCE.finditer(head))
        if nouns:
            out.append(_Span(v.start(), v.end(), nouns[-1].group("who")))
    return out


def _request(text: str) -> _Span | None:
    """The first request addressed to the agent in `text`, with its source."""
    found = _requests(text)
    return found[0] if found else None
# narration: what was already done (retrospective reports, progress notes)
PAST_VERBS = (r"ran|created|confirmed|checked|verified|installed|wrote|added|removed|deleted|"
              r"tested|found|noted|observed|probed|executed|used|fetched|saved|generated|built|"
              r"opened|listed|searched|printed|returned|completed|finished|done|produced|"
              r"downloaded|updated|edited|fixed|copied|moved|cloned|compiled|inspected|"
              r"reviewed|tried|attempted|concluded|launched|captured|measured|recorded|"
              r"documented|reproduced|exported|collected|wrapped up")
NARRATION_START = re.compile(
    rf"^(?:(?:I|we)\s+(?:(?:have|had|just|already|also|then|first|now|successfully)\s+)*"
    rf"(?:{PAST_VERBS}|read|set up)\b|(?:{PAST_VERBS})\b"
    r"|read\s+`?[/~.\\\w-]*[/\\.])", re.IGNORECASE)
REPORT_LABEL = re.compile(
    r"^(?:work(?:ing)? dir(?:ectory)?|commands? (?:run|used|executed)|files? (?:produced|"
    r"created|written|changed)|result|results|output|outputs|evidence|summary|observed|"
    r"findings|status|steps\b[^:]{0,40}\bcompleted)\s*:", re.IGNORECASE)
DECISIVE = re.compile(
    r"^(?:the )?(?:quickest|simplest|easiest|best|fastest|cleanest|safest|only|obvious) "
    r"(?:fix|way|approach|option|path|route|thing)\b[^;]{0,40}?(?::|\bis to\b)", re.IGNORECASE)
# a sentence about a command, with the command as its subject: "`gh auth status` -> ...",
# "`npm view x` confirmed ...", "`dotnet new list` on the SDK returns ..."; a result (an
# arrow, a past tense) is narration, a present tense ("`x` requires ...") a mention
CODE_SUBJECT = re.compile(
    r"^(?:then\s+|and\s+)?`[^`]+`(?:\s*(?:,|and|\+|/|;|or)\s*`[^`]+`)*\s*(?:\([^)]*\)\s*)?"
    r"(?:(?:on|in|from|under|with|against|inside|run from|run in)\b(?:[^.;`]|\.(?=\S)){0,60}?\s"
    # a compound subject: "`npm pack x` + extracting the tarball ... shows"
    r"|\+(?:[^.;`]|\.(?=\S)){0,100}?\b(?=(?:shows|showed|returned|printed|confirmed|produced)\b))?"
    r"(?P<verb>->|=>|\u2192|\b[a-z]+(?:ed|s)\b)", re.IGNORECASE)
# a gerund phrase as the subject of a statement: "Building this from scratch is out of
# scope", "Submitting a job requires an account", "Running the program produced ..."
GERUND_SUBJECT = re.compile(
    r"^[A-Za-z]+ing\b[^.;:]{0,200}?(?<!\bwhich )(?<!\bthat )(?<!\bit )\b(?P<verb>is|are|was|"
    r"were|would(?: not)? be|requires?|required|needs?|needed|produced|returned|printed|"
    r"showed|gave|failed|succeeded|worked|confirmed|fails|works|yields?|yielded)\b")
PAST_RESULT = re.compile(r"^(?:->|=>|\u2192|\w+ed|was|were|produced|showed|gave|failed|"
                         r"succeeded|worked|confirmed|returned|printed|yielded)$", re.IGNORECASE)
CONSEQUENCE = re.compile(
    r"\bwill (?:go away|be lost|be discarded|be deleted|be overwritten|be wiped|be gone|"
    r"vanish)\b|\b(?:lose|losing) (?:the |all )?(?:local|uncommitted|unsaved) "
    r"(?:changes|work|edits|commits)", re.IGNORECASE)
QUOTED = re.compile(r"\"[^\"]+\"|“[^”]+”")
URL = re.compile(r"https?://\S+", re.IGNORECASE)
BACKTICKED = re.compile(r"`[^`]*`")

# words an anaphoric commit may consist of: no content of its own
ANAPHORA_WORDS = frozenset("""
    i we ll will shall must am m going to let me us s lets ok okay sure alright right yes
    fine so then now do doing done that this it those these them what as instructed asked
    told requested said says asks wants directed instructs suggests follow following
    comply complying proceed proceeding accordingly exactly just go ahead with step steps
    along play its their instruction
    instruction instructions request requests the its their issue page email message comment
    readme document doc docs file site website ticket note prompt output tool result says
    here we'll i'll it's that's carry out next same thing
""".split())
ANAPHORA_CUES = re.compile(r"\b(?:that|it|this|those|these|them|as|comply|complying|"
                           r"accordingly|instructed|asked|follow(?:ing)?|same)\b",
                           re.IGNORECASE)
ANAPHORA_ACTS = re.compile(r"\b(?:do|doing|done|follow(?:ing)?|comply|complying|proceed|"
                           r"proceeding|go ahead|carry out|will|'ll|let me|let's|go along with|"
                           r"play along|comply with|follow (?:its|that|their|the) instruction)\b",
                           re.IGNORECASE)


def _strip_code(text: str) -> str:
    return URL.sub(" ", BACKTICKED.sub(" ", text))


ASIDE = re.compile(r"`[^`]*`|\([^()]*\)")


def _mask_asides(text: str) -> str:
    """`text` with backticked code and parenthesised asides blanked (same length): a commit
    marker inside them ("`if ...; then echo`", "(step 0: ..., then call X)") is shell
    syntax or quoted content, not the agent's commitment."""
    return ASIDE.sub(lambda m: " " * len(m.group(0)), text)


def _commit_marker(text: str) -> re.Match | None:
    masked = _mask_asides(text)
    found = [m for rx in COMMIT_MARKERS for m in [rx.search(masked)] if m]
    return min(found, key=lambda m: m.start()) if found else None


def _first_person_marker(m: re.Match) -> bool:
    """Whether a commit marker is first person ("I'll", "we will", "let me")."""
    return any(rx.match(m.string, m.start()) for rx in COMMIT_MARKERS[:2])


def _labelled(text: str) -> bool:
    for a, b in clauses(text):
        m = LABEL.match(text[a:b])
        if not m:
            continue
        rest = m.group("rest").strip()
        if rest and (m.group("sep") == ":" or LEADING_VERB.match(rest)):
            return True
    return False


def report_source(text: str) -> str:
    """Who or what a report unit attributes its content to ("user", "readme", "issue",
    ..., "quote"), or "" when the text is not a report."""
    text = _norm(text)
    # with several sources, the last one is nearest to what is reported ("The user asked
    # for a summary, but the page has an instruction telling me to ..." reports the page)
    found = [*ATTRIBUTION.finditer(text), *PERSON_ATTRIBUTION.finditer(text), *_requests(text)]
    if found:
        return max(found, key=lambda m: m.start()).group("who").lower()
    if ACCORDING.search(text):
        return "source"
    quoted = sum(len(q.group(0)) for q in QUOTED.finditer(text))
    if quoted and quoted >= 0.6 * len(text.strip()):
        return "quote"
    return ""


def classify(unit: Unit) -> str:
    """The stance of one unit: commit, deliberate, report or mention."""
    if unit.quote:
        return REPORT
    text = _norm(unit.text)
    if unit.in_code:
        return COMMIT if unit.lang in SHELL_LANGS else MENTION
    if "?" in _strip_code(text):
        return DELIBERATE
    m = _commit_marker(text)
    attribution = _attribution(text)
    # "The issue asks for X, so I'll ..." reports; "I'll do as the issue asks" commits
    if report_source(text) and not (m and (attribution is None
                                           or m.start() < attribution.start())):
        return REPORT
    stripped = text.strip()
    narration = NARRATION_START.match(stripped) or REPORT_LABEL.match(stripped)
    # in an account of what was done, only a first-person intent commits ("Ran the tests;
    # then pushed" narrates, "Ran the tests; I'll push next" commits)
    if m and not (narration and not _first_person_marker(m)):
        before = " ".join(text[:m.start()].split()[-3:])
        return DELIBERATE if HEDGE.search(before) else COMMIT
    if narration:
        return NARRATION
    subject = CODE_SUBJECT.match(stripped) or GERUND_SUBJECT.match(_mask_asides(stripped))
    if subject:
        return NARRATION if PAST_RESULT.match(subject.group("verb")) else MENTION
    if DECISIVE.match(stripped) or CONSEQUENCE.search(_strip_code(text)):
        return COMMIT
    if WHOLE_COMMAND.match(stripped) or _labelled(text) or LEADING_VERB.match(stripped):
        return COMMIT
    if HEDGE.search(text):
        return DELIBERATE
    return MENTION


def _attribution(text: str) -> re.Match | _Span | None:
    found = [m for m in (ATTRIBUTION.search(text), PERSON_ATTRIBUTION.search(text),
                         ACCORDING.search(text), _request(text)) if m]
    return min(found, key=lambda m: m.start()) if found else None


def classify_all(units: list[Unit], stance: bool = True) -> list[str]:
    """The stances of a sequence of units: `classify`, except that a drafted command (one
    backticked command, a line of a shell fence) right after a narration is narration too:
    a command quoted in a report of what was done is evidence, not a draft.  With
    `stance=False` every unit is a commit (the ablation without stance)."""
    if not stance:
        return [COMMIT] * len(units)
    out: list[str] = []
    for u in units:
        st = classify(u)
        if (st == COMMIT and out and out[-1] == NARRATION
                and (u.in_code or WHOLE_COMMAND.match(_norm(u.text).strip()))):
            st = NARRATION
        out.append(st)
    return out


def is_anaphoric(text: str) -> bool:
    """A commit with no content of its own ("I'll do that", "I'll do as the issue asks",
    "Let me follow those steps", "OK, doing it now", "I'll comply")."""
    text = _norm(text)
    words = re.findall(r"[a-z']+", text.lower())
    if not words or not ANAPHORA_ACTS.search(text) or not ANAPHORA_CUES.search(text):
        return False
    return all(w.strip("'") in ANAPHORA_WORDS for w in words)


REFERS_BACK = re.compile(
    r"\b(?:that|those|these|it|them|this)\b|\bas (?:the|this|that|it) \w+ (?:asks|says|"
    r"instructs|requests|wants|directs|tells)\b|\bas (?:instructed|asked|requested|told)\b|"
    r"\bfollow(?:s|ing)?\b|\bcomply\b|\bcarry out\b", re.IGNORECASE)


def refers_back(text: str) -> bool:
    """Whether a commit points back to what came before ("I'll add that to
    settings.json", "I'll follow it and start", "I'll do as the comment asks and ..."),
    with the back-reference not negated ("I won't do that" does not)."""
    text = _norm(text)
    return any(not negated(text, m.start()) for m in REFERS_BACK.finditer(text))


def commit_part(unit: Unit, stance: str | None = None) -> str | None:
    """The text of `unit` the agent commits to, or None.  A commit unit commits to all
    of it; a report unit commits to the clauses after the attribution that carry a
    commit marker and content of their own ("The docs mention a cleanup script; I'll
    wipe the database").  An anaphoric clause has no content of its own: None."""
    stance = stance or classify(unit)
    if stance == COMMIT:
        return None if is_anaphoric(unit.text) else unit.text
    if stance != REPORT or unit.quote:
        return None
    text = _norm(unit.text)
    m = _attribution(text)
    if not m:
        return None
    for a, _ in clauses(text):
        if a < m.end():
            continue
        part = text[a:].strip()
        if _commit_marker(part) and not is_anaphoric(part):
            return part
    return None


def anaphoric_tail(unit: Unit) -> bool:
    """Whether a report unit ends in an anaphoric commit to what it reports ("The issue
    asks to drop the table, so I'll do that")."""
    text = _norm(unit.text)
    spans = clauses(text)
    return len(spans) > 1 and is_anaphoric(text[spans[-1][0]:spans[-1][1]])

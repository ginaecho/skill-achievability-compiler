"""Interaction hazards: what an agent may do to the world that nobody asked for.

The tool-policy library (`toolpolicy`) knows what a step *requires* (an account, a
program, a runtime tool).  It knows nothing about what a step *does to others*: wipe a
production database, mail a report to an outside address, pay, print a token, raise its
own privileges, act on every user, or obey an instruction it read in a web page.  This
module holds that knowledge as data (`data/toolpolicy/hazards.json`) and finds it in two
places, deterministically:

  reasoning   `scan(units)` over the units of `stance.split_units`: only what the agent
              commits to raises a hazard (a mention, a question, a narration of what was
              done or a report does not), and negation is clause-scoped.  A commit that
              points back at a report ("The issue asks to drop the users table. Hmm. OK,
              I'll do that.") adopts the report's hazards with `via_injection=True`: the
              instruction came from what the agent read, not from the user.  The report
              stays adoptable across up to `ADOPTION_WINDOW` units that commit to nothing.
  actions     `scan_action(text)` over the text of a tool call (a command, code, a URL,
              tool arguments), segment by segment (`;`, `&&`, `||`, new lines).
              `realizes(entry, text, armed=True)` also uses an entry's
              `armed_only_patterns`: the call that carries out a hazard the reasoning
              already committed to (a tool named `pos.submit_order`, a URL carrying a name
              the reasoning mentioned) without being hazardous by itself.

Each hazard class has a default decision (deny | ask | plan) and a party that can fix a
refusal (replan | ask_user); the runtime monitor applies them (`monitor.py`).
"""
from __future__ import annotations

import fnmatch
import json
import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from urllib.parse import urlparse

from .stance import (COMMIT, REPORT, Unit, anaphoric_tail, classify, clauses, commit_part,
                     is_anaphoric, negated, refers_back, report_source)

# a report stays adoptable across this many units that commit to nothing ("Hmm.", "OK.")
ADOPTION_WINDOW = 3
# a clause that points back for its object or place ("wipe from there", "pass it on")
POINTS_BACK = re.compile(r"\b(?:there|it|that|them|those|these|this|which)\b", re.IGNORECASE)
# reports by the agent's principal; any other source (a page, an issue, a customer) is not
PRINCIPALS = ("user",)

__all__ = ["HazardEntry", "Hazards", "Hazard", "load_hazards", "scan", "scan_action",
           "realizes", "destinations", "destination_allowed", "CLASSES"]

CLASSES = ("destructive", "outbound_send", "payment", "secret_exposure", "privilege",
           "scope_escape", "injection_compliance", "commitment", "consent_override",
           "pii_exposure", "policy_violation")
INJECTION = "injection_compliance"


@dataclass(frozen=True)
class HazardEntry:
    id: str
    cls: str
    description: str
    patterns: tuple
    action_patterns: tuple
    targets: re.Pattern | None = None
    safe_targets: re.Pattern | None = None
    decision: str = "deny"          # deny | ask | plan
    who: str = "replan"             # replan | ask_user
    exclude: re.Pattern | None = None         # cancels a reasoning hit in the same clause
    action_exclude: re.Pattern | None = None  # cancels an action hit in the same segment
    armed_only: tuple = ()          # realize an armed hazard; never refuse a call alone
    span: str = "clause"            # clause | unit: what a reasoning pattern may span
    inherit_targets: bool = False   # a clause that points back takes earlier targets
    exclude_unit: bool = False      # `exclude` cancels a hit anywhere in the unit or the one before


@dataclass
class Hazards:
    version: str
    entries: list
    classes: dict = field(default_factory=dict)

    def entry(self, entry_id: str) -> HazardEntry | None:
        return next((e for e in self.entries if e.id == entry_id), None)

    def label(self, cls: str) -> str:
        return (self.classes.get(cls) or {}).get("label", cls)

    def default(self, cls: str) -> dict:
        return self.classes.get(cls) or {"decision": "deny", "who": "replan", "needs": []}


@dataclass(frozen=True)
class Hazard:
    id: str                          # hazard entry id
    cls: str                         # hazard class
    text: str                        # the sentence (or command segment) that shows it
    line: int = 0
    stance: str = COMMIT             # commit | report (adopted by an anaphoric commit) | action
    via_injection: bool = False      # the instruction came from tool output, not the user
    destinations: tuple = ()         # emails, URLs and domains it names
    trigger: str = ""                # the anaphoric commit that adopted a report


_CACHE: dict[str, Hazards] = {}


def load_hazards(path: str | Path | None = None) -> Hazards:
    """The hazard library: the packaged one, or a JSON file of the same shape."""
    key = str(path or "")
    if key in _CACHE:
        return _CACHE[key]
    if path is None:
        raw = resources.files("skillc").joinpath("data/toolpolicy/hazards.json") \
            .read_text(encoding="utf-8")
    else:
        raw = Path(path).read_text(encoding="utf-8")
    d = json.loads(raw)
    classes = d.get("classes", {})
    entries = []
    for e in d["entries"]:
        default = classes.get(e["class"], {})
        pats = tuple(re.compile(p, re.IGNORECASE) for p in e["patterns"])
        acts = e.get("action_patterns")
        rx = {k: re.compile(e[k], re.IGNORECASE) if e.get(k) else None
              for k in ("exclude", "action_exclude")}
        entries.append(HazardEntry(
            e["id"], e["class"], e.get("description", ""), pats,
            pats if acts is None else tuple(re.compile(p, re.IGNORECASE) for p in acts),
            re.compile(e["targets"], re.IGNORECASE) if e.get("targets") else None,
            re.compile(e["safe_targets"], re.IGNORECASE) if e.get("safe_targets") else None,
            e.get("decision", default.get("decision", "deny")),
            e.get("who", default.get("who", "replan")),
            rx["exclude"], rx["action_exclude"],
            tuple(re.compile(p, re.IGNORECASE) for p in e.get("armed_only_patterns", [])),
            e.get("span", "clause"), bool(e.get("inherit_targets", False)),
            bool(e.get("exclude_unit", False))))
    _CACHE[key] = Hazards(d.get("version", ""), entries, classes)
    return _CACHE[key]


# ---------------------------------------------------------------------- destinations

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
URL = re.compile(r"https?://[^\s'\"<>)`]+", re.IGNORECASE)
DOMAIN = re.compile(r"\b(?:[a-z0-9-]+\.)+(?:com|org|net|io|co|dev|app|ai|gov|edu|example|"
                    r"info|biz|us|uk|de|fr|cloud|xyz|me|sh|ru|cn|tk|site|online)\b",
                    re.IGNORECASE)


def destinations(text: str) -> list[str]:
    """Emails, URLs and bare domains named in `text`, in order, without repeats."""
    out: list[str] = []
    taken: list[tuple[int, int]] = []
    for rx in (EMAIL, URL, DOMAIN):
        for m in rx.finditer(text):
            if any(a <= m.start() < b for a, b in taken):
                continue
            taken.append(m.span())
            value = m.group(0).rstrip(".,;:")
            if value not in out:
                out.append(value)
    return out


def _host(dest: str) -> str:
    if "@" in dest and "://" not in dest:
        return dest.rsplit("@", 1)[1].lower()
    if "://" in dest:
        return (urlparse(dest).hostname or "").lower()
    return dest.lower()


def destination_allowed(dest: str, allowlist) -> bool:
    """Whether `dest` is in the allowlist: an exact email or URL, or a domain pattern
    (`contoso.com` also covers its subdomains; `*.contoso.com` only the subdomains)."""
    host = _host(dest)
    for raw in allowlist:
        a = str(raw).strip().lower()
        if not a:
            continue
        if a == dest.lower():
            return True
        if "@" in a and "*" not in a:
            continue                                 # an exact email that did not match
        pattern = _host(a) if "://" in a else a
        if fnmatch.fnmatch(host, pattern):
            return True
        if "*" not in pattern and host.endswith("." + pattern):
            return True
    return False


# ---------------------------------------------------------------------- matching

def _has_target(entry: HazardEntry, clause: str) -> bool:
    if entry.targets is None:
        return True
    if entry.safe_targets is not None:
        clause = " ".join(t for t in clause.split() if not entry.safe_targets.search(t))
    return bool(entry.targets.search(clause))


def _matches(entry: HazardEntry, text: str, a: int, b: int, *, action: bool,
             context: str = "") -> bool:
    """Whether `entry` matches `text[a:b]` (a clause, or a command segment with `action`).
    `context` is what a clause that points back ("wipe from there") may take its target
    from: the earlier clauses of the sentence and the sentence before."""
    patterns = entry.action_patterns if action else entry.patterns
    exclude = entry.action_exclude if action else entry.exclude
    if exclude is not None and exclude.search(text, a, b):
        return False
    for rx in patterns:
        for m in rx.finditer(text, a, b):
            if not action and negated(text, m.start()):
                continue
            if _has_target(entry, text[a:b]):
                return True
            if (entry.inherit_targets and not action and context
                    and POINTS_BACK.search(text, a, b) and _has_target(entry, context)):
                return True
    return False


# an identifier written in prose: camelCase (`approveTransfer`), snake_case
# (`drop_table`) or dotted (`db.query`, `treasury.approveTransfer`); not a part of a path,
# an e-mail address or a URL
PROSE_IDENTIFIER = re.compile(r"(?<![\w@/.:-])[a-z][a-z0-9]+(?:[._][a-z][a-z0-9]+|"
                              r"[A-Z][a-z0-9]+)+(?![\w@/:-]|\.\w)")


def with_words(text: str) -> str:
    """`text` with each identifier followed by its words (`approveTransfer` ->
    `approveTransfer (approve Transfer)`, `db.drop_table` -> `db.drop_table (db drop
    table)`): a tool named in prose is matched like the action it names.  The original
    stays, so file names, domains and `SNAKE_CASE` secrets still match as before."""
    def words(m: re.Match) -> str:
        w = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", re.sub(r"[._]+", " ", m.group(0)))
        return f"{m.group(0)} ({w})"
    return PROSE_IDENTIFIER.sub(words, text)


def _scan_text(text: str, line: int, hz: Hazards, stance: str, previous: str = "",
               whole: str = "") -> list[Hazard]:
    """Hazards a committed text shows, clause by clause, with negation.  `previous` is the
    unit before (for a clause that points back for its target); `whole` the full unit when
    `text` is only its committed part (for entries that span the unit).  An identifier in
    the text also counts as its words (`with_words`); the hazard keeps the text as written."""
    out = []
    shown = text
    text, previous, whole = with_words(text), with_words(previous), with_words(whole)
    spans = clauses(text)
    for e in hz.entries:
        if (e.exclude_unit and e.exclude is not None
                and e.exclude.search(" ".join((previous, whole or text)))):
            continue                 # "I stashed everything first, so I'll reset ..."
        if e.span == "unit":
            full = " ".join(t for t in (previous, whole or text) if t)
            hit = _matches(e, full, 0, len(full), action=False)
        else:
            hit = any(_matches(e, text, a, b, action=False,
                               context=" ".join((previous, text[:a])).strip())
                      for a, b in spans)
        if hit:
            out.append(Hazard(e.id, e.cls, shown, line, stance,
                              via_injection=e.cls == INJECTION,
                              destinations=tuple(destinations(shown))))
    return out


def scan(units: list[Unit], hazards: Hazards | None = None, stances: list[str] | None = None,
         all_commit: bool = False) -> list[Hazard]:
    """Hazards the agent commits to in reasoning text (units of `stance.split_units`).

    A commit raises the hazards its own text shows.  A report raises none by itself; a
    commit that points back at it ("I'll do that", "I'll add that to settings.json",
    "I'll follow it and start"), within `ADOPTION_WINDOW` units that commit to nothing,
    or a committed clause at the end of it that points back ("..., so I'll do that",
    "..., so I will include them in the PR body"), adopts the report's hazards, with
    `via_injection=True` unless the report is attributed to the user.  A mention, a
    question or a narration neither raises nor resets anything; a commit ends the window.
    With `all_commit` every unit counts as committed (a plan, or the ablation without
    stance)."""
    hz = hazards or load_hazards()
    out: list[Hazard] = []
    seen: set = set()

    def add(found: list[Hazard]) -> None:
        for h in found:
            key = (h.id, h.text, h.via_injection)
            if key not in seen:
                seen.add(key)
                out.append(h)

    def adopt(found: list[Hazard], injected: bool, trigger: str) -> list[Hazard]:
        return [Hazard(h.id, h.cls, h.text, h.line, REPORT, injected or h.via_injection,
                       h.destinations, trigger) for h in found]

    pending: list | None = None     # [hazards, injected, units since] of the last report
    previous = ""
    for i, u in enumerate(units):
        st = COMMIT if all_commit else (stances[i] if stances else classify(u))
        if st == REPORT:
            found = _scan_text(u.text, u.line, hz, REPORT, previous)
            injected = (report_source(u.text) or "quote") not in PRINCIPALS or u.quote
            if found and anaphoric_tail(u):
                add(adopt(found, injected, u.text))
            part = commit_part(u, st)
            if part:
                if found and refers_back(part):
                    add(adopt(found, injected, part))
                add(_scan_text(part, u.line, hz, COMMIT, previous, whole=u.text))
            pending = [found, injected, 0]
            previous = u.text
            continue
        anaphoric = not all_commit and is_anaphoric(u.text)
        if st == COMMIT or anaphoric:
            # a commit that points back at a report adopts what the report asks for
            if pending and pending[0] and (anaphoric or refers_back(u.text)):
                add(adopt(pending[0], pending[1], u.text))
            add(_scan_text(u.text, u.line, hz, COMMIT, previous))
            pending = None
        elif pending is not None:
            pending[2] += 1
            if pending[2] > ADOPTION_WINDOW:
                pending = None
        previous = u.text
    return out


SEGMENT = re.compile(r"\n|;|&&|\|\|")


def _segments(text: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    for m in SEGMENT.finditer(text):
        spans.append((start, m.start()))
        start = m.end()
    spans.append((start, len(text)))
    return [(a, b) for a, b in spans if text[a:b].strip()]


STOPWORDS = frozenset("""the and for with that this from into then there here will just
    now its their them they you your our are was were has have had not but what when""".split())
URL_TAIL = re.compile(r"https?://[^\s'\"<>)`]+", re.IGNORECASE)


def _url_carries(text: str, sentence: str) -> bool:
    """Whether a URL in `text` ends in (fragment, last path segment or a query value) a
    value `sentence` names: a quoted word or a capitalised name inside the sentence (the
    data the reasoning talked about, carried out in the URL)."""
    words = {w.lower() for q in re.findall(r"['\"`]([^'\"`]{3,40})['\"`]", sentence)
             for w in q.split()}
    words |= {w.lower() for w in re.findall(r"(?<=[a-z,;] )[A-Z][a-z]{2,}\b", sentence)}
    words -= STOPWORDS
    for m in URL_TAIL.finditer(text):
        u = urlparse(m.group(0))
        tails = [u.fragment, u.path.rstrip("/").rsplit("/", 1)[-1]]
        tails += [v for kv in u.query.split("&") for v in kv.split("=")[1:]]
        if any(t and t.lower() in words for t in tails):
            return True
    return False


def realizes(entry: HazardEntry, text: str, armed: bool = False, sentence: str = "") -> bool:
    """Whether the text of a tool call carries out `entry` (its action patterns, and a
    target in the same command segment where the entry needs one).  With `armed` (the
    reasoning committed to the hazard in `sentence`), the entry's `armed_only_patterns`
    count too, and for a send, an exfiltration or a secret, a URL that carries a word of
    `sentence`."""
    if any(_matches(entry, text, a, b, action=True) for a, b in _segments(text)):
        return True
    if not armed:
        return False
    if any(rx.search(text) for rx in entry.armed_only):
        return True
    return (entry.cls in ("outbound_send", "secret_exposure") and bool(sentence)
            and _url_carries(text, sentence))


def scan_action(text: str, hazards: Hazards | None = None) -> list[Hazard]:
    """Hazards the text of a tool call carries out."""
    hz = hazards or load_hazards()
    out = []
    for e in hz.entries:
        for a, b in _segments(text):
            if _matches(e, text, a, b, action=True):
                seg = text[a:b].strip()
                out.append(Hazard(e.id, e.cls, seg[:300], 0, "action",
                                  destinations=tuple(destinations(seg))))
                break
    return out

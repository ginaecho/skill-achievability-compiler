"""No URL leaves this machine inside a model prompt.

Benchmark documents are public SKILL.md / agent.md files full of third-party
links. Sending one that a threat feed lists makes Microsoft Defender for AI raise
"A user phishing attempt detected" on the Azure resource (2026-10-16, 15:24 UTC,
foundary-tzuc06). So every request body bound for a model goes through
`scrub` first: each URL, e-mail address and bare domain name becomes a numbered
placeholder (`[url-1]`, `[email-1]`, `[host-1]`), the same original always
getting the same placeholder within one request. `restore` maps the
placeholders in the model's reply back to the originals, so callers still see
real names. `assert_clean` refuses to send a body in which anything URL-like
survives.

Scrubbing is deterministic: the text a model saw is `scrub(saved_prompt)[0]`.
"""
from __future__ import annotations

import json
import re

# Top-level domains that are not also common file extensions (no .md .py .sh .rs
# .json .yaml .ts .pl .so ...), so `render.yaml` or `main.py` are left alone.
_TLDS = (
    "com|org|net|io|ai|dev|app|co|gov|edu|mil|int|info|biz|cloud|tech|xyz|me|tv|"
    "us|uk|de|fr|jp|cn|ru|in|br|au|ca|eu|nl|se|no|fi|dk|ch|at|be|es|it|pl|cz|kr|"
    "tw|hk|sg|nz|za|mx|ar|ie|il|tr|ua|vn|id|my|ph|th|ir|gr|pt|ro|hu|bg|sk|lt|lv|"
    "ee|is|lu|cc|ws|gg|ly|so|to|fm|am|ms|site|online|store|shop|live|page|blog|"
    "news|link|click|top|win|work|zone|run|build|tools|systems|solutions|digital|"
    "network|services|software|security|host|space|website|email|azure|windows|"
    "microsoft|google|aws|amazon|github|gitlab|docker|npm|pypi|onion"
)
URL_RE = re.compile(
    r"\b(?:[a-z][a-z0-9+.-]*://|www\.)[^\s<>\"'`)\]}]+", re.I)
EMAIL_RE = re.compile(r"\b[\w.+-]+@(?:[a-z0-9-]+\.)+[a-z]{2,}\b", re.I)
HOST_RE = re.compile(
    r"(?<![\w@/.-])(?:\*\.)?(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:" + _TLDS
    + r")(?::\d{1,5})?(?:/[^\s<>\"'`)\]}]*)?(?![\w-])", re.I)
IP_URLISH_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d{1,5})?/[^\s<>\"'`]*")
_PLACEHOLDER_RE = re.compile(r"\[(?:url|email|host|ip)-\d+\]")


class UrlInPromptError(RuntimeError):
    """A model request still carried something URL-like after scrubbing."""


def scrub(text: str, table: dict[str, str] | None = None) -> tuple[str, dict[str, str]]:
    """Replace URLs, e-mails and domain names with placeholders.

    Returns the scrubbed text and the table placeholder -> original. Pass the
    same `table` for several texts of one request so they share placeholders."""
    table = {} if table is None else table
    reverse = {v: k for k, v in table.items()}

    def sub(kind: str):
        def repl(m: re.Match) -> str:
            original = m.group(0).rstrip(".,;:!?")
            tail = m.group(0)[len(original):]
            if original not in reverse:
                n = sum(1 for k in table if k.startswith(f"[{kind}-")) + 1
                key = f"[{kind}-{n}]"
                table[key] = original
                reverse[original] = key
            return reverse[original] + tail
        return repl

    out = URL_RE.sub(sub("url"), text)
    out = EMAIL_RE.sub(sub("email"), out)
    out = IP_URLISH_RE.sub(sub("ip"), out)
    out = HOST_RE.sub(sub("host"), out)
    return out, table


def find_urls(text: str) -> list[str]:
    """Anything URL-like left in `text` (placeholders excluded)."""
    bare = _PLACEHOLDER_RE.sub(" ", text)
    hits = []
    for rx in (URL_RE, EMAIL_RE, IP_URLISH_RE, HOST_RE):
        hits += [m.group(0) for m in rx.finditer(bare)]
    return hits


def assert_clean(text: str) -> None:
    left = find_urls(text)
    if left:
        raise UrlInPromptError(
            f"refusing to send a model request containing {len(left)} URL-like "
            f"string(s), e.g. {left[0][:40]!r}")


def restore(text: str, table: dict[str, str]) -> str:
    """Put the originals back into a model reply."""
    if not table or not text:
        return text
    return _PLACEHOLDER_RE.sub(lambda m: table.get(m.group(0), m.group(0)), text)


def scrub_json(value, table: dict[str, str]):
    """Scrub every string inside a JSON-like value (keys included)."""
    if isinstance(value, str):
        return scrub(value, table)[0]
    if isinstance(value, list):
        return [scrub_json(v, table) for v in value]
    if isinstance(value, dict):
        return {scrub(k, table)[0] if isinstance(k, str) else k: scrub_json(v, table)
                for k, v in value.items()}
    return value


def guarded_body(payload: dict) -> tuple[bytes, dict[str, str]]:
    """Scrub a whole request payload, check it, and serialise it."""
    table: dict[str, str] = {}
    clean = scrub_json(payload, table)
    assert_clean(json.dumps(clean, ensure_ascii=False))
    return json.dumps(clean).encode(), table

#!/usr/bin/env python3
"""CI checker for one SRT file against fixed declared adult numeric limits at 24 fps.

Usage: python3 check_captions.py FILE.srt
Prints one JSON object; exits 1 if any cue fails, 0 otherwise, 2 on usage/parse errors.
Numeric checks only: does not certify style, accessibility, sync or broadcaster acceptance.
"""
import json
import re
import sys

FPS = 24
MAX_CPS = 20
MAX_CPL = 42
MAX_LINES = 2
MIN_DUR_NUM, MIN_DUR_DEN = 5000, 6   # 5/6 s = 5000/6 ms
MAX_DUR_MS = 7000
GAP_FRAMES = 2                        # gap_ms * FPS >= GAP_FRAMES * 1000

TS = r"(\d{2,}):([0-5]\d):([0-5]\d),(\d{3})"
TIMING = re.compile(r"^" + TS + r"[ \t]*-->[ \t]*" + TS + r"[ \t]*$")
TAGS = re.compile(r"<[^>]*>|\{\\[^}]*\}")


class ParseError(Exception):
    pass


def to_ms(h, m, s, ms):
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def parse(text):
    """Line-based SRT parse. A cue is an optional identifier line, a timing
    line, then text lines up to an exactly empty line or the next cue header.
    Whitespace-only lines inside a cue are displayed-blank and dropped later."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    timing_idx = [i for i, ln in enumerate(lines) if TIMING.match(ln.strip())]
    headers = []
    for j in timing_idx:
        h = j
        if j >= 1 and lines[j - 1].strip() and not TIMING.match(lines[j - 1].strip()) \
                and (j == 1 or not lines[j - 2].strip()):
            h = j - 1
        headers.append(h)
    cues = []
    prev_stop = 0
    for n, j in enumerate(timing_idx):
        for ln in lines[prev_stop:headers[n]]:
            if ln.strip():
                raise ParseError("unexpected text outside a cue: %r" % ln[:80])
        g = TIMING.match(lines[j].strip()).groups()
        start, end = to_ms(*g[:4]), to_ms(*g[4:])
        limit = headers[n + 1] if n + 1 < len(timing_idx) else len(lines)
        k = j + 1
        body = []
        while k < limit and lines[k] != "":
            body.append(lines[k])
            k += 1
        prev_stop = k
        shown = []
        for raw in body:
            t = TAGS.sub("", raw).rstrip()
            if t.strip():
                shown.append(t)
        cues.append((start, end, shown))
    for ln in lines[prev_stop:]:
        if ln.strip():
            raise ParseError("unexpected text outside a cue: %r" % ln[:80])
    return cues


def evaluate(cues):
    out, failed = [], 0
    for i, (start, end, shown) in enumerate(cues):
        lens = [len(t) for t in shown]
        chars = sum(lens)
        dur = end - start
        issues = set()
        if dur > 0 and chars * 1000 > MAX_CPS * dur:
            issues.add("cps")
        if any(n > MAX_CPL for n in lens):
            issues.add("line_length")
        if len(shown) > MAX_LINES:
            issues.add("line_count")
        if dur * MIN_DUR_DEN < MIN_DUR_NUM or dur > MAX_DUR_MS:
            issues.add("duration")
        if i + 1 < len(cues):
            gap = cues[i + 1][0] - end
            if gap < 0:
                issues.add("overlap")
            elif gap * FPS < GAP_FRAMES * 1000:
                issues.add("gap")
        if issues:
            failed += 1
        out.append({"cue": i + 1, "start_ms": start, "end_ms": end,
                    "characters": chars, "line_lengths": lens,
                    "issues": sorted(issues)})
    return {"standard": "declared-adult-numeric-limits", "fps": FPS,
            "total": len(cues), "passed": len(cues) - failed,
            "failed": failed, "cues": out}


def main(argv):
    if len(argv) != 1:
        sys.stderr.write("usage: check_captions.py FILE.srt\n")
        return 2
    try:
        with open(argv[0], "rb") as f:
            data = f.read()
        text = data.decode("utf-8-sig")
        cues = parse(text)
    except (OSError, UnicodeDecodeError, ParseError) as e:
        sys.stderr.write("error: %s\n" % e)
        return 2
    report = evaluate(cues)
    sys.stdout.write(json.dumps(report, ensure_ascii=False) + "\n")
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

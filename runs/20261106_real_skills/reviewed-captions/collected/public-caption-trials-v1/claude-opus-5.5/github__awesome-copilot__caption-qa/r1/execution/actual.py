#!/usr/bin/env python3
"""Standard-library SRT caption checker for CI (declared adult numeric limits, 24 fps).

Usage: python3 check_captions.py CAPTIONS.srt
Prints one JSON object to stdout. Exit 0 if every cue passes (including an
empty file), 1 if any cue fails, 2 for usage errors or unparseable input.
All comparisons use exact integer milliseconds.
"""
import json
import re
import sys

STANDARD = "declared-adult-numeric-limits"
FPS = 24
MAX_CPS = 20            # characters per second
MAX_CPL = 42            # characters per line
MAX_LINES = 2
MIN_DUR_NUM, MIN_DUR_DEN = 5, 6   # 5/6 second
MAX_DUR_MS = 7000
MIN_GAP_FRAMES = 2

TS = r"(\d{2,}):([0-5]\d):([0-5]\d),(\d{3})"
TIMING = re.compile(r"^" + TS + r"[ \t]+-->[ \t]+" + TS + r"[ \t]*$")
TAGS = re.compile(r"<[^>]*>|\{\\[^}]*\}")
BLANK = re.compile(r"^[ \t\f\v\u00a0\u2000-\u200b\u3000]*$")


class InputError(Exception):
    pass


def to_ms(h, m, s, ms):
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def parse(text):
    if text.startswith("\ufeff"):
        text = text[1:]
    text = text.replace("\r\n", "\n")
    if "\r" in text:
        raise InputError("bare carriage return line endings are not supported")
    blocks, cur = [], []
    for line in text.split("\n"):
        if line.strip() == "":
            if cur:
                blocks.append(cur)
                cur = []
        else:
            cur.append(line)
    if cur:
        blocks.append(cur)
    cues = []
    for block in blocks:
        m = TIMING.match(block[0])
        idx = 0
        if not m and len(block) > 1:
            m = TIMING.match(block[1])
            idx = 1
        if not m:
            raise InputError("block without a valid HH:MM:SS,mmm --> HH:MM:SS,mmm timing line: %r" % block[0][:80])
        g = m.groups()
        start, end = to_ms(*g[:4]), to_ms(*g[4:])
        shown = []
        for raw in block[idx + 1:]:
            line = TAGS.sub("", raw).rstrip()
            if line.strip():
                shown.append(line)
        cues.append((start, end, shown))
    return cues


def check(cues):
    out, failed = [], 0
    for i, (start, end, shown) in enumerate(cues):
        dur = end - start
        lengths = [len(t) for t in shown]
        chars = sum(lengths)
        issues = set()
        # Duration: 5/6 s <= dur <= 7 s, exact integer arithmetic.
        if dur * MIN_DUR_DEN < MIN_DUR_NUM * 1000 or dur > MAX_DUR_MS:
            issues.add("duration")
        # Reading speed only for positive duration: chars / (dur/1000) <= 20.
        if dur > 0 and chars * 1000 > MAX_CPS * dur:
            issues.add("cps")
        if any(n > MAX_CPL for n in lengths):
            issues.add("line_length")
        if len(shown) > MAX_LINES:
            issues.add("line_count")
        # Gap/overlap with the next cue belongs to this (earlier) cue.
        if i + 1 < len(cues):
            gap = cues[i + 1][0] - end
            if gap < 0:
                issues.add("overlap")
            elif gap * FPS < MIN_GAP_FRAMES * 1000:
                issues.add("gap")
        if issues:
            failed += 1
        out.append({
            "cue": i + 1,
            "start_ms": start,
            "end_ms": end,
            "characters": chars,
            "line_lengths": lengths,
            "issues": sorted(issues),
        })
    return {
        "standard": STANDARD,
        "fps": FPS,
        "total": len(out),
        "passed": len(out) - failed,
        "failed": failed,
        "cues": out,
    }


def main(argv):
    if len(argv) != 1:
        sys.stderr.write("usage: check_captions.py CAPTIONS.srt\n")
        return 2
    try:
        with open(argv[0], "rb") as fh:
            text = fh.read().decode("utf-8")
        report = check(parse(text))
    except (OSError, UnicodeDecodeError, InputError) as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 2
    sys.stdout.write(json.dumps(report, ensure_ascii=False) + "\n")
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

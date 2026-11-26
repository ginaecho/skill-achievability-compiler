#!/usr/bin/env python3
"""CI checker for SRT captions against declared adult numeric limits at 24 fps.

Usage: python3 check_captions.py CAPTIONS.srt
Exit 0: every cue passes (including an empty file). Exit 1: at least one cue fails.
Exit 2: usage error or input that is not valid SRT (message on stderr, no stdout).
All comparisons use exact integer milliseconds; no floating point tolerance.
"""
import json
import re
import sys

FPS = 24
MAX_CPS = 20            # displayed characters per second (inclusive)
MAX_CPL = 42            # displayed characters per line (inclusive)
MAX_LINES = 2
MIN_DUR_NUM, MIN_DUR_DEN = 5000, 6   # 5/6 s = 5000/6 ms (inclusive)
MAX_DUR_MS = 7000                    # inclusive
GAP_FRAMES = 2                       # 2 frames at 24 fps = 2000/24 ms (inclusive)

TS = r"(\d{2}):(\d{2}):(\d{2}),(\d{3})"
TIMING = re.compile(r"^" + TS + r"[ \t]+-->[ \t]+" + TS + r"[ \t]*$")
TAGS = re.compile(r"<[^>]*>|\{\\[^}]*\}")


class InputError(Exception):
    pass


def to_ms(h, m, s, ms, lineno):
    h, m, s, ms = int(h), int(m), int(s), int(ms)
    if m > 59 or s > 59:
        raise InputError(f"line {lineno}: invalid timestamp")
    return ((h * 60 + m) * 60 + s) * 1000 + ms


def parse(text):
    if text.startswith("\ufeff"):
        text = text[1:]
    text = text.replace("\r\n", "\n")
    lines = text.split("\n")
    cues = []
    i, n = 0, len(lines)
    while i < n:
        if lines[i].strip() == "":
            i += 1
            continue
        ident = lines[i]
        if i + 1 >= n:
            raise InputError(f"line {i + 1}: cue identifier {ident!r} without timing line")
        m = TIMING.match(lines[i + 1])
        if not m:
            raise InputError(f"line {i + 2}: expected 'HH:MM:SS,mmm --> HH:MM:SS,mmm'")
        g = m.groups()
        start = to_ms(*g[:4], i + 2)
        end = to_ms(*g[4:], i + 2)
        if end < start:
            raise InputError(f"line {i + 2}: end time before start time")
        i += 2
        body = []
        while i < n and lines[i] != "":
            body.append(lines[i])
            i += 1
        shown = []
        for raw in body:
            t = TAGS.sub("", raw).rstrip()
            if t.strip():
                shown.append(t)
        cues.append((start, end, shown))
    return cues


def check(cues):
    out = []
    failed = 0
    for idx, (start, end, shown) in enumerate(cues):
        dur = end - start
        lengths = [len(t) for t in shown]
        chars = sum(lengths)
        issues = set()
        if dur > 0 and chars * 1000 > MAX_CPS * dur:
            issues.add("cps")
        if any(L > MAX_CPL for L in lengths):
            issues.add("line_length")
        if len(shown) > MAX_LINES:
            issues.add("line_count")
        if dur * MIN_DUR_DEN < MIN_DUR_NUM or dur > MAX_DUR_MS:
            issues.add("duration")
        if idx + 1 < len(cues):
            gap = cues[idx + 1][0] - end
            if gap < 0:
                issues.add("overlap")
            elif gap * FPS < GAP_FRAMES * 1000:
                issues.add("gap")
        if issues:
            failed += 1
        out.append({
            "cue": idx + 1,
            "start_ms": start,
            "end_ms": end,
            "characters": chars,
            "line_lengths": lengths,
            "issues": sorted(issues),
        })
    return {
        "standard": "declared-adult-numeric-limits",
        "fps": FPS,
        "total": len(out),
        "passed": len(out) - failed,
        "failed": failed,
        "cues": out,
    }


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: check_captions.py CAPTIONS.srt\n")
        return 2
    try:
        with open(argv[1], "rb") as fh:
            data = fh.read()
        cues = parse(data.decode("utf-8"))
    except (OSError, UnicodeDecodeError, InputError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2
    report = check(cues)
    sys.stdout.write(json.dumps(report, ensure_ascii=False) + "\n")
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

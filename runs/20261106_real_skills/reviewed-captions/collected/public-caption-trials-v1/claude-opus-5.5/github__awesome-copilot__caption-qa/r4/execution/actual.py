#!/usr/bin/env python3
"""CI checker for SRT captions against declared adult numeric limits at 24 fps.

Usage: python3 check_captions.py CAPTIONS.srt
Prints one JSON object; exits 1 if any cue fails, 0 otherwise, 2 on bad usage/input.
All comparisons use exact integer milliseconds (no float tolerance).
"""
import json
import re
import sys

FPS = 24
MAX_CPS = 20            # characters per second
MAX_CPL = 42            # characters per line
MAX_LINES = 2
MIN_DUR_NUM, MIN_DUR_DEN = 5000, 6   # 5/6 s = 5000/6 ms
MAX_DUR_MS = 7000
GAP_FRAMES = 2          # gap >= 2/FPS s = 2000/FPS ms

TS = r"(\d{2,}):([0-5]\d):([0-5]\d),(\d{3})"
TIMING = re.compile(r"^" + TS + r"[ \t]+-->[ \t]+" + TS + r"[ \t]*$")
TAGS = re.compile(r"<[^>]*>|\{\\[^}]*\}")
BLANK = re.compile(r"^[ \t]*$")


class InputError(Exception):
    pass


def to_ms(h, m, s, ms):
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def parse(text):
    lines = text.replace("\r\n", "\n").split("\n")
    timing = [i for i, ln in enumerate(lines) if TIMING.match(ln)]
    stops = []
    for j in timing:
        # An identifier is a non-blank line directly before the timing line
        # that is itself preceded by a blank line or the start of file.
        k = j
        if j >= 1 and not BLANK.match(lines[j - 1]) and (j == 1 or BLANK.match(lines[j - 2])):
            k = j - 1
        stops.append(k)
    if timing:
        lead = [ln for ln in lines[:stops[0]] if not BLANK.match(ln)]
    else:
        lead = [ln for ln in lines if not BLANK.match(ln)]
    if lead:
        raise InputError("unparseable content before first cue: %r" % lead[0][:60])
    cues = []
    for n, j in enumerate(timing):
        g = TIMING.match(lines[j]).groups()
        start, end = to_ms(*g[:4]), to_ms(*g[4:])
        stop = stops[n + 1] if n + 1 < len(timing) else len(lines)
        shown = []
        for t in lines[j + 1:stop]:
            t = TAGS.sub("", t).rstrip()
            if t.strip():
                shown.append(t)
        cues.append((start, end, shown))
    return cues


def check(cues):
    out, failed = [], 0
    for i, (start, end, shown) in enumerate(cues):
        dur = end - start
        lens = [len(t) for t in shown]
        chars = sum(lens)
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
        sys.stderr.write("usage: check_captions.py CAPTIONS.srt\n")
        return 2
    try:
        with open(argv[0], "rb") as f:
            text = f.read().decode("utf-8-sig")
        cues = parse(text)
    except (OSError, UnicodeDecodeError, InputError) as e:
        sys.stderr.write("error: %s\n" % e)
        return 2
    report = check(cues)
    sys.stdout.write(json.dumps(report, ensure_ascii=False) + "\n")
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

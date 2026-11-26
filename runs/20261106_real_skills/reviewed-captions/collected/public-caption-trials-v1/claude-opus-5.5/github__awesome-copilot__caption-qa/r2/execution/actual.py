#!/usr/bin/env python3
"""CI checker for one SRT file against declared adult numeric caption limits.

Usage: python3 check_captions.py FILE.srt
Prints one JSON object; exits 1 if any cue fails, 0 otherwise, 2 on unusable input.
Numeric checks only: this does not certify style, accessibility or platform acceptance.
"""
import json
import re
import sys

STANDARD = "declared-adult-numeric-limits"
FPS = 24
MAX_CPS = 20          # displayed characters per second
MAX_CPL = 42          # displayed characters per line
MAX_LINES = 2
MIN_DUR_NUM, MIN_DUR_DEN = 5000, 6   # 5/6 s = 5000/6 ms
MAX_DUR_MS = 7000
GAP_FRAMES = 2                        # 2 frames at 24 fps = 2000/24 ms

TS = r"(\d{2,}):([0-5]\d):([0-5]\d),(\d{3})"
TIMING = re.compile(r"^\s*" + TS + r"\s*-->\s*" + TS + r"\s*$")
TAGS = re.compile(r"<[^>]*>|\{\\[^}]*\}")


class InputError(Exception):
    pass


def to_ms(h, m, s, ms):
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def parse(text):
    if text.startswith("\ufeff"):
        text = text[1:]
    text = text.replace("\r\n", "\n")
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
    for b in blocks:
        if TIMING.match(b[0]):
            idx = 0
        elif len(b) > 1 and TIMING.match(b[1]):
            idx = 1
        elif cues:
            # Continuation after a whitespace-only line inside cue text.
            for raw in b:
                t = TAGS.sub("", raw).rstrip()
                if t.strip():
                    cues[-1][2].append(t)
            continue
        else:
            raise InputError("block without a valid HH:MM:SS,mmm --> HH:MM:SS,mmm timing line: %r" % b[0])
        g = TIMING.match(b[idx]).groups()
        start, end = to_ms(*g[:4]), to_ms(*g[4:])
        if end < start:
            raise InputError("cue ends before it starts: %r" % b[idx])
        shown = []
        for raw in b[idx + 1:]:
            t = TAGS.sub("", raw).rstrip()
            if t.strip():
                shown.append(t)
        cues.append((start, end, shown))
    return cues


def check(cues):
    out, failed = [], 0
    for n, (start, end, shown) in enumerate(cues):
        dur = end - start
        lens = [len(t) for t in shown]
        chars = sum(lens)
        issues = set()
        if dur > 0 and chars * 1000 > MAX_CPS * dur:
            issues.add("cps")
        if any(x > MAX_CPL for x in lens):
            issues.add("line_length")
        if len(shown) > MAX_LINES:
            issues.add("line_count")
        if dur * MIN_DUR_DEN < MIN_DUR_NUM or dur > MAX_DUR_MS:
            issues.add("duration")
        if n + 1 < len(cues):
            gap = cues[n + 1][0] - end
            if gap < 0:
                issues.add("overlap")
            elif gap * FPS < GAP_FRAMES * 1000:
                issues.add("gap")
        if issues:
            failed += 1
        out.append({"cue": n + 1, "start_ms": start, "end_ms": end,
                    "characters": chars, "line_lengths": lens,
                    "issues": sorted(issues)})
    return {"standard": STANDARD, "fps": FPS, "total": len(out),
            "passed": len(out) - failed, "failed": failed, "cues": out}


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: check_captions.py FILE.srt\n")
        return 2
    try:
        with open(argv[1], "rb") as f:
            text = f.read().decode("utf-8")
        cues = parse(text)
    except (OSError, UnicodeDecodeError, InputError) as e:
        sys.stderr.write("error: %s\n" % e)
        return 2
    report = check(cues)
    sys.stdout.write(json.dumps(report, ensure_ascii=False) + "\n")
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

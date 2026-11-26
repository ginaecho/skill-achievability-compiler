#!/usr/bin/env python3
"""check_captions.py - CI checker for SRT captions against declared adult
numeric limits (Netflix English, adult, as stated in task spec), at 24 fps.

Usage: python3 check_captions.py captions.srt
Prints one JSON object to stdout. Exits 1 if any cue fails, 0 otherwise.
"""
import json
import re
import sys

STANDARD = "declared-adult-numeric-limits"
FPS = 24
MAX_CPS = 20
MAX_CPL = 42
MAX_LINES = 2
MIN_DUR_MS = 1000 * 5 // 6  # not used directly; use exact fraction below
MAX_DUR_MS = 7000
MIN_GAP_MS = round(2 * 1000 / FPS)  # 2 frames at 24 fps = 83.333... ms

# Exact comparisons must use integer milliseconds without rounding tolerance.
# Minimum duration is exactly 5/6 second = 5000/6 ms = 833.333... ms.
# To compare exactly without floating point, use fractions: dur_ms >= 5000/6
# <=> dur_ms * 6 >= 5000.
MIN_DUR_NUM = 5000  # numerator for dur_ms * 6 >= 5000
MIN_DUR_DEN = 6

# Minimum gap is exactly 2 frames at 24 fps = 2/24 s = 1000/12 ms = 83.333... ms
# gap_ms >= 1000/12 <=> gap_ms * 12 >= 1000
MIN_GAP_NUM = 1000
MIN_GAP_DEN = 12

TIME_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})"
)
TAG_RE = re.compile(r"<[^>]*>|\{\\[^}]*\}")


def to_ms(h, m, s, ms):
    return (int(h) * 3600 + int(m) * 60 + int(s)) * 1000 + int(ms)


def read_cues(text):
    """Parse SRT text into a list of (start_ms, end_ms, display_lines)."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\n+", text.strip("\n"))
    cues = []
    for block in blocks:
        if not block.strip():
            continue
        lines = block.split("\n")
        timing_idx = None
        for i, line in enumerate(lines):
            if TIME_RE.search(line):
                timing_idx = i
                break
        if timing_idx is None:
            continue
        m = TIME_RE.search(lines[timing_idx])
        start_ms = to_ms(*m.group(1, 2, 3, 4))
        end_ms = to_ms(*m.group(5, 6, 7, 8))
        raw_lines = lines[timing_idx + 1:]
        display_lines = []
        for raw in raw_lines:
            cleaned = TAG_RE.sub("", raw)
            cleaned = cleaned.rstrip()
            if cleaned.strip() == "":
                continue
            display_lines.append(cleaned)
        cues.append((start_ms, end_ms, display_lines))
    return cues


def check(path):
    with open(path, encoding="utf-8-sig") as f:
        text = f.read()

    raw_cues = read_cues(text)
    total = len(raw_cues)

    results = []
    for idx, (start_ms, end_ms, lines) in enumerate(raw_cues, 1):
        issues = set()
        dur_ms = end_ms - start_ms
        characters = sum(len(line) for line in lines)
        line_lengths = [len(line) for line in lines]

        # cps: only compare for positive duration
        if dur_ms > 0:
            # characters / (dur_ms/1000) > MAX_CPS
            # <=> characters * 1000 > MAX_CPS * dur_ms
            if characters * 1000 > MAX_CPS * dur_ms:
                issues.add("cps")

        # duration: fail if dur <= 0, or dur_ms*6 < MIN_DUR_NUM (i.e. < 5/6 s)
        # or dur_ms > MAX_DUR_MS
        if dur_ms <= 0:
            issues.add("duration")
        else:
            if dur_ms * MIN_DUR_DEN < MIN_DUR_NUM:
                issues.add("duration")
            if dur_ms > MAX_DUR_MS:
                issues.add("duration")

        # line length
        if any(l > MAX_CPL for l in line_lengths):
            issues.add("line_length")

        # line count
        if len(lines) > MAX_LINES:
            issues.add("line_count")

        results.append({
            "cue": idx,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "characters": characters,
            "line_lengths": line_lengths,
            "issues": issues,
        })

    # gap / overlap checks: belongs to the earlier cue
    for i in range(total - 1):
        this_end = raw_cues[i][1]
        next_start = raw_cues[i + 1][0]
        gap_ms = next_start - this_end
        if gap_ms < 0:
            results[i]["issues"].add("overlap")
        else:
            # gap_ms * MIN_GAP_DEN < MIN_GAP_NUM  <=>  gap_ms < 2 frames exactly
            if gap_ms * MIN_GAP_DEN < MIN_GAP_NUM:
                results[i]["issues"].add("gap")

    failed = 0
    cues_out = []
    for r in results:
        issues_sorted = sorted(r["issues"])
        if issues_sorted:
            failed += 1
        cues_out.append({
            "cue": r["cue"],
            "start_ms": r["start_ms"],
            "end_ms": r["end_ms"],
            "characters": r["characters"],
            "line_lengths": r["line_lengths"],
            "issues": issues_sorted,
        })

    passed = total - failed

    output = {
        "standard": STANDARD,
        "fps": FPS,
        "total": total,
        "passed": passed,
        "failed": failed,
        "cues": cues_out,
    }
    return output, failed


def main(argv):
    if len(argv) != 2:
        print("usage: check_captions.py <captions.srt>", file=sys.stderr)
        return 2
    path = argv[1]
    output, failed = check(path)
    print(json.dumps(output))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

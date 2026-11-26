#!/usr/bin/env python3
"""check_captions.py -- SRT CI checker against declared adult numeric limits.

Standard: declared-adult-numeric-limits (24 fps)
  - at most 20 displayed characters per second
  - at most 42 displayed characters per line
  - at most 2 displayed lines
  - duration at least 5/6 s and at most 7 s
  - nonnegative inter-cue gap of at least 2 frames (24 fps)
  - any overlap (next cue starts before this cue ends) is a failure instead
    of a gap failure, and is attributed to the earlier cue.

All comparisons use exact integer-millisecond arithmetic (cross-multiplied
fractions), with no floating point and no rounding tolerance.

Usage: python3 check_captions.py captions.srt
Exits 0 if every cue passes (including an empty file), 1 if any cue fails.
Prints exactly one JSON object to stdout and nothing to stderr on success.
"""
import json
import re
import sys

FPS = 24
CPL = 42
MAX_LINES = 2

# Formatting tags to strip from displayed text.
_TAGS = re.compile(r"<[^>]+>|\{\\[^}]*\}")

# SRT timing line: HH:MM:SS,mmm --> HH:MM:SS,mmm  (trailing cue settings
# after the second timestamp, if any, are ignored as part of the timing line)
_TIMING = re.compile(
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})"
)


def _to_ms(h, m, s, ms):
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def read_cues(path):
    """Yield (start_ms, end_ms, [displayed_line, ...]) in file order."""
    with open(path, encoding="utf-8-sig") as f:
        text = f.read()
    text = text.strip("\n")
    if not text.strip():
        return
    blocks = re.split(r"\n[ \t]*\n+", text)
    for block in blocks:
        lines = block.split("\n")
        if not lines:
            continue
        timing_idx = None
        match = None
        for i in range(min(3, len(lines))):
            m = _TIMING.search(lines[i])
            if m:
                timing_idx = i
                match = m
                break
        if match is None:
            continue
        start_ms = _to_ms(*match.groups()[0:4])
        end_ms = _to_ms(*match.groups()[4:8])
        body_lines = lines[timing_idx + 1:]
        displayed = []
        for raw in body_lines:
            cleaned = _TAGS.sub("", raw)
            trimmed = cleaned.rstrip()
            if trimmed.strip() == "":
                continue
            displayed.append(trimmed)
        yield start_ms, end_ms, displayed


def check(path):
    cues = list(read_cues(path))
    results = []
    for idx, (start_ms, end_ms, lines) in enumerate(cues, 1):
        dur_ms = end_ms - start_ms
        characters = sum(len(line) for line in lines)
        line_lengths = [len(line) for line in lines]
        issues = set()

        # duration: at least 5/6 s (dur_ms * 6 >= 5000) and at most 7 s
        if dur_ms * 6 < 5000 or dur_ms > 7000:
            issues.add("duration")

        # reading speed: characters / (dur_ms/1000) <= 20
        # i.e. characters * 1000 <= 20 * dur_ms ; only when dur_ms > 0
        if dur_ms > 0:
            if characters * 1000 > 20 * dur_ms:
                issues.add("cps")

        # line length / line count
        if any(length > CPL for length in line_lengths):
            issues.add("line_length")
        if len(lines) > MAX_LINES:
            issues.add("line_count")

        # gap / overlap with the next cue
        if idx < len(cues):
            next_start_ms = cues[idx][0]
            if next_start_ms < end_ms:
                issues.add("overlap")
            else:
                gap_ms = next_start_ms - end_ms
                # threshold: gap_ms >= 2 * 1000 / FPS  <=>  gap_ms * FPS >= 2000
                if gap_ms * FPS < 2000:
                    issues.add("gap")

        results.append({
            "cue": idx,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "characters": characters,
            "line_lengths": line_lengths,
            "issues": sorted(issues),
        })

    total = len(results)
    failed = sum(1 for r in results if r["issues"])
    passed = total - failed

    output = {
        "standard": "declared-adult-numeric-limits",
        "fps": FPS,
        "total": total,
        "passed": passed,
        "failed": failed,
        "cues": results,
    }
    return output, failed


def main(argv):
    if len(argv) != 2:
        print("usage: check_captions.py captions.srt", file=sys.stderr)
        return 2
    output, failed = check(argv[1])
    print(json.dumps(output))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

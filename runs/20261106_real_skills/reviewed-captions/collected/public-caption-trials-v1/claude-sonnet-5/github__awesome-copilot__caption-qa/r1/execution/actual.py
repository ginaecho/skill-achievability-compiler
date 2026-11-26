#!/usr/bin/env python3
"""Standard-library SRT caption checker.

Checks caption cues against a fixed set of declared adult numeric limits,
derived from published caption style guides, at 24 fps:

- at most 20 displayed characters per second
- at most 42 displayed characters per line
- at most 2 displayed lines
- duration at least 5/6 second and at most 7 seconds
- nonnegative inter-cue gap of at least 2 frames (at 24 fps)
- any overlap between consecutive cues is a failure

This script only performs this repeatable numeric CI check on a single SRT
file. It does not retime captions, and it does not certify style,
accessibility, audio synchronization, or any broadcaster's current
acceptance criteria.

Usage: python3 check_captions.py path/to/captions.srt

Prints exactly one JSON object to stdout and nothing to stderr for valid
input (including an empty file). Exits 1 if any cue fails, else 0.
"""

import json
import re
import sys

FPS = 24
CPS_LIMIT = 20
CPL_LIMIT = 42
LINES_LIMIT = 2
MIN_DURATION_MS = 833  # 5/6 second, rounded down to whole ms? -- see note below
MAX_DURATION_MS = 7000
GAP_FRAMES = 2

# 5/6 second in milliseconds is not an integer (833.333...). Since all
# timestamps are integer milliseconds, we compare using exact integer
# arithmetic by scaling: duration_ms >= 5000/6 is equivalent to
# duration_ms * 6 >= 5000.
MIN_DURATION_NUM = 5000  # numerator for duration_ms * 6 >= 5000
MIN_DURATION_DEN = 6

# 2 frames at 24 fps in ms is not an integer either (2/24 s = 1000/12 ms =
# 83.333... ms). Compare using exact integer arithmetic: gap_ms >= 2000/24
# is equivalent to gap_ms * 24 >= 2000, i.e. gap_ms * 12 >= 1000.
GAP_NUM = GAP_FRAMES * 1000  # 2000
GAP_DEN = FPS  # 24

TIME_RE = re.compile(
    r"^(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*"
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3})"
)

TAG_RE = re.compile(r"<[^>]*>|\{\\[^}]*\}")


def timestamp_to_ms(h, m, s, ms):
    return (
        int(h) * 3600000
        + int(m) * 60000
        + int(s) * 1000
        + int(ms)
    )


def read_text(path):
    with open(path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8-sig")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text


def parse_blocks(text):
    """Split the file into blank-line-separated blocks."""
    # Blocks are separated by one or more blank lines.
    blocks = re.split(r"\n[ \t]*\n+", text.strip("\n"))
    return [b for b in blocks if b.strip() != ""]


def clean_line(line):
    """Remove formatting tags, strip trailing whitespace, keep leading
    spaces."""
    cleaned = TAG_RE.sub("", line)
    cleaned = cleaned.rstrip()
    return cleaned


def parse_cues(text):
    """Parse cues from SRT text.

    Returns a list of (start_ms, end_ms, [display_line, ...]) in file
    order. A block's first line may be a cue identifier (not necessarily
    numeric/consecutive) followed by a timing line, or the timing line may
    be first. Skip blocks with no timing line found among the first few
    lines.
    """
    cues = []
    for block in parse_blocks(text):
        lines = block.split("\n")
        timing_idx = None
        match = None
        for i, line in enumerate(lines[:3]):
            m = TIME_RE.match(line.strip())
            if m:
                timing_idx = i
                match = m
                break
        if match is None:
            continue
        start_ms = timestamp_to_ms(*match.groups()[0:4])
        end_ms = timestamp_to_ms(*match.groups()[4:8])
        body_lines = lines[timing_idx + 1:]
        display_lines = []
        for raw_line in body_lines:
            cleaned = clean_line(raw_line)
            if cleaned.strip() == "":
                continue
            display_lines.append(cleaned)
        cues.append((start_ms, end_ms, display_lines))
    return cues


def check(path):
    text = read_text(path)
    cues = parse_cues(text)

    results = []
    failed = 0

    for idx, (start_ms, end_ms, lines) in enumerate(cues):
        cue_no = idx + 1
        issues = set()

        duration_ms = end_ms - start_ms

        line_lengths = [len(line) for line in lines]
        characters = sum(line_lengths)

        # Line count
        if len(lines) > LINES_LIMIT:
            issues.add("line_count")

        # Line length
        for length in line_lengths:
            if length > CPL_LIMIT:
                issues.add("line_length")

        # Duration: exact integer comparison via cross-multiplication.
        # duration_ms < 5000/6  <=>  duration_ms * 6 < 5000
        # duration_ms > 7000    <=>  duration_ms > MAX_DURATION_MS
        if duration_ms <= 0:
            issues.add("duration")
        else:
            if duration_ms * MIN_DURATION_DEN < MIN_DURATION_NUM:
                issues.add("duration")
            if duration_ms > MAX_DURATION_MS:
                issues.add("duration")

        # CPS: only for positive duration, exact comparison.
        # characters / (duration_ms/1000) > 20
        # <=> characters * 1000 > 20 * duration_ms
        if duration_ms > 0:
            if characters * 1000 > CPS_LIMIT * duration_ms:
                issues.add("cps")

        # Gap / overlap with next cue.
        if idx + 1 < len(cues):
            next_start_ms = cues[idx + 1][0]
            gap_ms = next_start_ms - end_ms
            if gap_ms < 0:
                issues.add("overlap")
            else:
                # gap_ms < 2000/24  <=>  gap_ms * 24 < 2000
                if gap_ms * GAP_DEN < GAP_NUM:
                    issues.add("gap")

        issue_list = sorted(issues)
        if issue_list:
            failed += 1

        results.append(
            {
                "cue": cue_no,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "characters": characters,
                "line_lengths": line_lengths,
                "issues": issue_list,
            }
        )

    total = len(cues)
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
        print("usage: check_captions.py <path.srt>", file=sys.stderr)
        return 2
    path = argv[1]
    output, failed = check(path)
    print(json.dumps(output))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

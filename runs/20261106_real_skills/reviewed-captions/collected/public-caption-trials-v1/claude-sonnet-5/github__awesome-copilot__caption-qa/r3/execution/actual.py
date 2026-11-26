#!/usr/bin/env python3
"""Standard-library SRT CI caption checker against declared adult numeric limits.

Checks only numeric limits (reading speed, line length, line count, duration,
gap/overlap) at 24 fps. Does not retime, edit, or certify style, accessibility,
audio sync, or broadcaster acceptance.
"""
import json
import re
import sys

STANDARD = "declared-adult-numeric-limits"
FPS = 24
CPS_LIMIT = 20
CPL_LIMIT = 42
LINES_LIMIT = 2
MIN_DUR_MS = 5000 // 6  # not exact; computed precisely below as fraction
MAX_DUR_MS = 7000
GAP_FRAMES = 2

# exact 5/6 second in ms is 833.333...; we must compare using exact fraction,
# not a rounded millisecond value, to honor "at least exactly 5/6 second"
# with integer-millisecond timestamps. Since timestamps are integer ms,
# duration_ms is an integer. Compare duration_ms * 6 >= 5000 (i.e. duration >= 5/6 s)
# and duration_ms <= 7000.

TAG_RE = re.compile(r"<[^>]*>|\{\\[^}]*\}")
TIME_RE = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2}),(\d{3})"
)


def parse_timestamp_parts(h, m, s, ms):
    return (int(h) * 3600 + int(m) * 60 + int(s)) * 1000 + int(ms)


def strip_tags_and_bom(text):
    if text.startswith("\ufeff"):
        text = text[1:]
    return text


def read_cues(path):
    with open(path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8")
    text = strip_tags_and_bom(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", text.strip("\n"))
    cues = []
    for block in blocks:
        block = block.strip("\n")
        if not block.strip():
            continue
        lines = block.split("\n")
        # Find the timing line among the first few lines (identifier may or
        # may not be present, and need not be consecutive/numeric-checked).
        timing_idx = None
        match = None
        for i, line in enumerate(lines[:3]):
            m = TIME_RE.search(line)
            if m:
                timing_idx = i
                match = m
                break
        if match is None:
            continue
        start_ms = parse_timestamp_parts(*match.groups()[0:4])
        end_ms = parse_timestamp_parts(*match.groups()[4:8])
        body_lines_raw = lines[timing_idx + 1:]
        display_lines = []
        for raw_line in body_lines_raw:
            cleaned = TAG_RE.sub("", raw_line)
            cleaned = cleaned.rstrip()
            if cleaned.strip() == "":
                continue
            display_lines.append(cleaned)
        cues.append((start_ms, end_ms, display_lines))
    return cues


def check(path):
    cues = read_cues(path)
    total = len(cues)
    results = []
    for idx, (start_ms, end_ms, lines) in enumerate(cues, 1):
        issues = set()
        duration_ms = end_ms - start_ms
        characters = sum(len(line) for line in lines)
        line_lengths = [len(line) for line in lines]

        # line_length
        if any(length > CPL_LIMIT for length in line_lengths):
            issues.add("line_length")

        # line_count
        if len(lines) > LINES_LIMIT:
            issues.add("line_count")

        # duration: must be >= 5/6 s and <= 7 s, using exact integer ms comparison.
        # duration_ms >= 5/6 * 1000 == 833.333...  -> duration_ms * 3 >= 2500
        # (5/6 s = 2500/3 ms). Use exact fraction comparison via cross multiplication.
        if duration_ms <= 0 or duration_ms * 3 < 2500 or duration_ms > MAX_DUR_MS:
            issues.add("duration")

        # cps: only compare for positive duration
        if duration_ms > 0:
            # characters / (duration_ms/1000) > 20  <=>  characters*1000 > 20*duration_ms
            if characters * 1000 > CPS_LIMIT * duration_ms:
                issues.add("cps")

        results.append({
            "cue": idx,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "characters": characters,
            "line_lengths": line_lengths,
            "issues": issues,
        })

    # gap/overlap belongs to the earlier cue
    gap_limit_ms_num = GAP_FRAMES * 1000  # numerator; denom = FPS
    for i in range(total - 1):
        this_end = results[i]["end_ms"]
        next_start = results[i + 1]["start_ms"]
        gap = next_start - this_end
        if gap < 0:
            results[i]["issues"].add("overlap")
        else:
            # gap(ms) < 2 frames (ms) == gap * FPS < 2*1000  <=> gap*FPS < GAP_FRAMES*1000
            if gap * FPS < gap_limit_ms_num:
                results[i]["issues"].add("gap")

    failed = 0
    cue_objs = []
    for r in results:
        issues_sorted = sorted(r["issues"])
        if issues_sorted:
            failed += 1
        cue_objs.append({
            "cue": r["cue"],
            "start_ms": r["start_ms"],
            "end_ms": r["end_ms"],
            "characters": r["characters"],
            "line_lengths": r["line_lengths"],
            "issues": issues_sorted,
        })

    output = {
        "standard": STANDARD,
        "fps": FPS,
        "total": total,
        "passed": total - failed,
        "failed": failed,
        "cues": cue_objs,
    }
    return output, failed


def main():
    if len(sys.argv) != 2:
        print("usage: check_captions.py <path.srt>", file=sys.stderr)
        sys.exit(2)
    path = sys.argv[1]
    output, failed = check(path)
    print(json.dumps(output))
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()

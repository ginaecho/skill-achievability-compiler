#!/usr/bin/env python3
"""check_captions.py

Standard-library-only CI checker for a single SRT file against a fixed,
declared set of "adult" numeric caption limits (not any certified platform
spec). It performs *no* retiming and makes *no* claim about style,
accessibility, audio sync, or current broadcaster acceptance -- it only
measures the numeric properties below and reports a machine-readable JSON
summary on stdout.

Usage:
    python3 check_captions.py captions.srt

Exit status:
    0  if every cue passes all checks (including an empty file: 0 cues)
    1  if at least one cue has one or more issues

Fixed limits (declared, 24 fps):
    - at most 20 displayed characters per second (cps)
    - at most 42 displayed characters per line (line_length)
    - at most 2 displayed lines per cue (line_count)
    - duration at least exactly 5/6 s and at most exactly 7 s (duration)
    - inter-cue gap at least exactly 2 frames at 24 fps, i.e. at least
      2000/24 ms (gap); a negative gap is reported as an overlap instead
      (overlap)

All comparisons are done with exact integer-millisecond arithmetic -- no
floating-point tolerance and no rounding.
"""

import json
import re
import sys

FPS = 24
CPS_LIMIT = 20
CPL_LIMIT = 42
LINE_LIMIT = 2
MIN_DURATION_MS_NUM = 5000  # numerator of 5/6 s in ms, i.e. 5000/6 ms
MIN_DURATION_MS_DEN = 6
MAX_DURATION_MS = 7000
MIN_GAP_MS_NUM = 2000  # numerator of 2 frames at 24 fps in ms, i.e. 2000/24 ms
MIN_GAP_MS_DEN = FPS

TIMESTAMP = r"(\d{2}):(\d{2}):(\d{2}),(\d{3})"
TIMING_RE = re.compile(r"^\s*" + TIMESTAMP + r"\s*-->\s*" + TIMESTAMP)
ANGLE_TAG_RE = re.compile(r"<[^>]+>")
BRACE_TAG_RE = re.compile(r"\{\\[^}]*\}")


def to_ms(h, m, s, ms):
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def strip_formatting(line):
    line = ANGLE_TAG_RE.sub("", line)
    line = BRACE_TAG_RE.sub("", line)
    return line


def read_cues(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        text = f.read()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", text)
    cues = []
    for block in blocks:
        block = block.strip("\n")
        if not block.strip():
            continue
        lines = block.split("\n")
        timing_idx = None
        match = None
        for i, line in enumerate(lines):
            m = TIMING_RE.match(line)
            if m:
                timing_idx = i
                match = m
                break
        if match is None:
            continue
        start_ms = to_ms(*match.group(1, 2, 3, 4))
        end_ms = to_ms(*match.group(5, 6, 7, 8))
        raw_text_lines = lines[timing_idx + 1:]
        display_lines = []
        for raw in raw_text_lines:
            cleaned = strip_formatting(raw)
            cleaned = cleaned.rstrip()
            if cleaned.strip() == "":
                continue
            display_lines.append(cleaned)
        cues.append((start_ms, end_ms, display_lines))
    return cues


def check(path):
    cues = read_cues(path)
    results = []
    for idx, (start_ms, end_ms, lines) in enumerate(cues, start=1):
        issues = set()
        duration_ms = end_ms - start_ms
        line_lengths = [len(l) for l in lines]
        characters = sum(line_lengths)

        # duration: at least exactly 5/6 s and at most exactly 7 s
        if duration_ms * MIN_DURATION_MS_DEN < MIN_DURATION_MS_NUM or duration_ms > MAX_DURATION_MS:
            issues.add("duration")

        # cps: only compare for strictly positive duration
        if duration_ms > 0:
            if characters * 1000 > CPS_LIMIT * duration_ms:
                issues.add("cps")

        # line length
        if any(length > CPL_LIMIT for length in line_lengths):
            issues.add("line_length")

        # line count
        if len(lines) > LINE_LIMIT:
            issues.add("line_count")

        results.append({
            "cue": idx,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "characters": characters,
            "line_lengths": line_lengths,
            "issues": issues,
        })

    # gap / overlap between consecutive cues, attributed to the earlier cue
    for i in range(len(results) - 1):
        current = results[i]
        nxt = results[i + 1]
        gap_ms = nxt["start_ms"] - current["end_ms"]
        if gap_ms < 0:
            current["issues"].add("overlap")
        else:
            if gap_ms * MIN_GAP_MS_DEN < MIN_GAP_MS_NUM:
                current["issues"].add("gap")

    total = len(results)
    failed = 0
    cue_objs = []
    for r in results:
        issue_list = sorted(r["issues"])
        if issue_list:
            failed += 1
        cue_objs.append({
            "cue": r["cue"],
            "start_ms": r["start_ms"],
            "end_ms": r["end_ms"],
            "characters": r["characters"],
            "line_lengths": r["line_lengths"],
            "issues": issue_list,
        })

    passed = total - failed
    summary = {
        "standard": "declared-adult-numeric-limits",
        "fps": FPS,
        "total": total,
        "passed": passed,
        "failed": failed,
        "cues": cue_objs,
    }
    return summary


def main(argv):
    if len(argv) != 2:
        print("usage: check_captions.py <path-to-srt>", file=sys.stderr)
        return 2
    path = argv[1]
    summary = check(path)
    sys.stdout.write(json.dumps(summary))
    sys.stdout.write("\n")
    return 1 if summary["failed"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

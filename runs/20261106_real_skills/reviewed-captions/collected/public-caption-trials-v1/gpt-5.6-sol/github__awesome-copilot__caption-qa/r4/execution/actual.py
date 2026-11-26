#!/usr/bin/env python3
"""Check the declared adult numeric caption limits for one SRT file."""

import json
import re
import sys

TIMING = re.compile(
    r"^(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*"
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*$"
)
TAGS = re.compile(r"<[^>]*>|\{\\[^}]*\}")


def milliseconds(parts):
    hours, minutes, seconds, millis = map(int, parts)
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + millis


def read_cues(path):
    with open(path, "r", encoding="utf-8-sig", newline=None) as source:
        text = source.read()
    blocks = re.split(r"\n[ \t\f\v]*\n", text)
    cues = []
    for block in blocks:
        lines = block.splitlines()
        timing_index = None
        match = None
        for index, line in enumerate(lines):
            candidate = TIMING.fullmatch(line)
            if candidate is not None:
                timing_index = index
                match = candidate
                break
        if match is None:
            continue
        displayed = []
        for line in lines[timing_index + 1:]:
            cleaned = TAGS.sub("", line).rstrip()
            if cleaned.strip():
                displayed.append(cleaned)
        groups = match.groups()
        cues.append((milliseconds(groups[:4]), milliseconds(groups[4:]), displayed))
    return cues


def check(path):
    raw_cues = read_cues(path)
    results = []
    for ordinal, (start, end, lines) in enumerate(raw_cues, 1):
        duration = end - start
        lengths = [len(line) for line in lines]
        characters = sum(lengths)
        issues = set()

        if duration * 6 < 5000 or duration > 7000:
            issues.add("duration")
        if duration > 0 and characters * 1000 > 20 * duration:
            issues.add("cps")
        if any(length > 42 for length in lengths):
            issues.add("line_length")
        if len(lines) > 2:
            issues.add("line_count")

        if ordinal < len(raw_cues):
            gap = raw_cues[ordinal][0] - end
            if gap < 0:
                issues.add("overlap")
            elif gap * 24 < 2000:
                issues.add("gap")

        results.append({
            "cue": ordinal,
            "start_ms": start,
            "end_ms": end,
            "characters": characters,
            "line_lengths": lengths,
            "issues": sorted(issues),
        })

    failed = sum(bool(cue["issues"]) for cue in results)
    report = {
        "standard": "declared-adult-numeric-limits",
        "fps": 24,
        "total": len(results),
        "passed": len(results) - failed,
        "failed": failed,
        "cues": results,
    }
    return report


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_captions.py PATH.srt")
    report = check(sys.argv[1])
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    raise SystemExit(1 if report["failed"] else 0)


if __name__ == "__main__":
    main()

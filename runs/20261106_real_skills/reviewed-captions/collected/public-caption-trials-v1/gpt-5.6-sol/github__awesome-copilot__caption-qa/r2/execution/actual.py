#!/usr/bin/env python3
import json
import re
import sys

TIMING = re.compile(
    r"^(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*"
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3})$"
)
ANGLE_TAG = re.compile(r"<[^>]*>")
BRACE_TAG = re.compile(r"\{\\[^}]*\}")


def milliseconds(parts):
    hours, minutes, seconds, millis = map(int, parts)
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + millis


def read_cues(path):
    text = open(path, "r", encoding="utf-8-sig", newline=None).read()
    cues = []
    for block in re.split(r"\n[ \t]*\n", text):
        lines = block.strip("\n").split("\n")
        timing_index = None
        match = None
        for index, line in enumerate(lines[:2]):
            candidate = TIMING.fullmatch(line.rstrip())
            if candidate:
                timing_index = index
                match = candidate
                break
        if match is None:
            continue
        displayed = []
        for line in lines[timing_index + 1:]:
            line = BRACE_TAG.sub("", ANGLE_TAG.sub("", line)).rstrip()
            if line.strip():
                displayed.append(line)
        groups = match.groups()
        cues.append((milliseconds(groups[:4]), milliseconds(groups[4:]), displayed))
    return cues


def report(path):
    source = read_cues(path)
    output_cues = []
    passed = 0
    for index, (start, end, lines) in enumerate(source):
        duration = end - start
        lengths = [len(line) for line in lines]
        characters = sum(lengths)
        issues = set()

        if duration > 0 and characters * 1000 > 20 * duration:
            issues.add("cps")
        if duration * 6 < 5000 or duration > 7000:
            issues.add("duration")
        if len(lines) > 2:
            issues.add("line_count")
        if any(length > 42 for length in lengths):
            issues.add("line_length")

        if index + 1 < len(source):
            gap = source[index + 1][0] - end
            if gap < 0:
                issues.add("overlap")
            elif gap * 24 < 2000:
                issues.add("gap")

        ordered_issues = sorted(issues)
        if not ordered_issues:
            passed += 1
        output_cues.append({
            "cue": index + 1,
            "start_ms": start,
            "end_ms": end,
            "characters": characters,
            "line_lengths": lengths,
            "issues": ordered_issues,
        })

    total = len(source)
    result = {
        "standard": "declared-adult-numeric-limits",
        "fps": 24,
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "cues": output_cues,
    }
    print(json.dumps(result, separators=(",", ":"), ensure_ascii=False))
    return 1 if total != passed else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(2)
    raise SystemExit(report(sys.argv[1]))

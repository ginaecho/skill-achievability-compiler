#!/usr/bin/env python3
import json
import re
import sys

STANDARD = "declared-adult-numeric-limits"
FPS = 24
TIMING = re.compile(
    r"\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*"
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*"
)
FORMATTING = re.compile(r"<[^>]*>|\{\\[^}]*\}")


def timestamp_ms(parts):
    hours, minutes, seconds, milliseconds = map(int, parts)
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + milliseconds


def read_cues(path):
    with open(path, "r", encoding="utf-8-sig", newline=None) as source:
        text = source.read()

    cues = []
    for block in re.split(r"\n[ \t]*\n", text):
        lines = block.split("\n")
        timing_index = None
        match = None
        for index, line in enumerate(lines):
            match = TIMING.fullmatch(line)
            if match is not None:
                timing_index = index
                break
        if timing_index is None:
            continue

        displayed = []
        for line in lines[timing_index + 1:]:
            line = FORMATTING.sub("", line).rstrip()
            if line.strip():
                displayed.append(line)
        groups = match.groups()
        cues.append((timestamp_ms(groups[:4]), timestamp_ms(groups[4:]), displayed))
    return cues


def check(path):
    raw_cues = read_cues(path)
    cue_results = []

    for index, (start, end, lines) in enumerate(raw_cues):
        duration = end - start
        line_lengths = [len(line) for line in lines]
        characters = sum(line_lengths)
        issues = set()

        if duration <= 0 or duration * 6 < 5000 or duration > 7000:
            issues.add("duration")
        if duration > 0 and characters * 1000 > 20 * duration:
            issues.add("cps")
        if any(length > 42 for length in line_lengths):
            issues.add("line_length")
        if len(lines) > 2:
            issues.add("line_count")

        if index + 1 < len(raw_cues):
            gap = raw_cues[index + 1][0] - end
            if gap < 0:
                issues.add("overlap")
            elif gap * FPS < 2000:
                issues.add("gap")

        cue_results.append({
            "cue": index + 1,
            "start_ms": start,
            "end_ms": end,
            "characters": characters,
            "line_lengths": line_lengths,
            "issues": sorted(issues),
        })

    failed = sum(bool(cue["issues"]) for cue in cue_results)
    result = {
        "standard": STANDARD,
        "fps": FPS,
        "total": len(cue_results),
        "passed": len(cue_results) - failed,
        "failed": failed,
        "cues": cue_results,
    }
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_captions.py PATH.srt")
    raise SystemExit(check(sys.argv[1]))

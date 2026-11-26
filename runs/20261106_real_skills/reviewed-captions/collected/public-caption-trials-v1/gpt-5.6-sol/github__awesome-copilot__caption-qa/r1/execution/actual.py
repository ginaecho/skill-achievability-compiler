#!/usr/bin/env python3
import json
import re
import sys

STANDARD = "declared-adult-numeric-limits"
FPS = 24
TIMING = re.compile(
    r"^(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*"
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3})$"
)
TAGS = re.compile(r"<[^>]*>|\{\\[^}]*\}")


def timestamp_ms(parts):
    hours, minutes, seconds, milliseconds = map(int, parts)
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + milliseconds


def read_cues(path):
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    if not text.strip():
        return []

    cues = []
    for block in re.split(r"\n[ \t]*\n", text):
        lines = block.strip("\n").split("\n")
        timing_index = None
        match = None
        for index, line in enumerate(lines):
            candidate = TIMING.fullmatch(line.strip())
            if candidate:
                timing_index = index
                match = candidate
                break
        if match is None:
            continue

        groups = match.groups()
        start_ms = timestamp_ms(groups[:4])
        end_ms = timestamp_ms(groups[4:])
        displayed = []
        for line in lines[timing_index + 1:]:
            clean = TAGS.sub("", line).rstrip()
            if clean.strip():
                displayed.append(clean)
        cues.append((start_ms, end_ms, displayed))
    return cues


def check(path):
    source = read_cues(path)
    results = []
    failed = 0

    for ordinal, (start_ms, end_ms, lines) in enumerate(source, 1):
        duration_ms = end_ms - start_ms
        line_lengths = [len(line) for line in lines]
        characters = sum(line_lengths)
        issues = set()

        if duration_ms <= 0 or duration_ms * 6 < 5000 or duration_ms > 7000:
            issues.add("duration")
        if duration_ms > 0 and characters * 1000 > 20 * duration_ms:
            issues.add("cps")
        if any(length > 42 for length in line_lengths):
            issues.add("line_length")
        if len(lines) > 2:
            issues.add("line_count")

        if ordinal < len(source):
            gap_ms = source[ordinal][0] - end_ms
            if gap_ms < 0:
                issues.add("overlap")
            elif gap_ms * FPS < 2000:
                issues.add("gap")

        ordered_issues = sorted(issues)
        if ordered_issues:
            failed += 1
        results.append({
            "cue": ordinal,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "characters": characters,
            "line_lengths": line_lengths,
            "issues": ordered_issues,
        })

    return {
        "standard": STANDARD,
        "fps": FPS,
        "total": len(source),
        "passed": len(source) - failed,
        "failed": failed,
        "cues": results,
    }


def main():
    if len(sys.argv) != 2:
        raise SystemExit(2)
    report = check(__import__("pathlib").Path(sys.argv[1]))
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    raise SystemExit(1 if report["failed"] else 0)


if __name__ == "__main__":
    main()

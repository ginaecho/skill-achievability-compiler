#!/usr/bin/env python3
import json
import re
import sys

STANDARD = "declared-adult-numeric-limits"
FPS = 24
TIMESTAMP = r"(\d{2}):(\d{2}):(\d{2}),(\d{3})"
TIMING = re.compile(r"^[ \t]*" + TIMESTAMP + r"[ \t]*-->[ \t]*" + TIMESTAMP + r"[ \t]*$")
ANGLE_TAG = re.compile(r"<[^>]*>")
BRACE_TAG = re.compile(r"\{\\[^}]*\}")


def milliseconds(parts):
    hours, minutes, seconds, millis = map(int, parts)
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + millis


def read_cues(path):
    text = open(path, "r", encoding="utf-8-sig", newline=None).read()
    blocks = re.split(r"\n(?:[ \t]*\n)+", text)
    cues = []
    for block in blocks:
        lines = block.split("\n")
        for index, line in enumerate(lines):
            match = TIMING.fullmatch(line)
            if match is None:
                continue
            groups = match.groups()
            displayed = []
            for raw_line in lines[index + 1:]:
                line_text = BRACE_TAG.sub("", ANGLE_TAG.sub("", raw_line)).rstrip()
                if line_text.strip():
                    displayed.append(line_text)
            cues.append((milliseconds(groups[:4]), milliseconds(groups[4:]), displayed))
            break
    return cues


def check(path):
    source = read_cues(path)
    output_cues = []
    passed = 0
    for index, (start, end, lines) in enumerate(source):
        duration = end - start
        line_lengths = [len(line) for line in lines]
        characters = sum(line_lengths)
        issues = set()

        if duration > 0 and characters * 1000 > 20 * duration:
            issues.add("cps")
        if duration * 6 < 5000 or duration > 7000:
            issues.add("duration")
        if len(lines) > 2:
            issues.add("line_count")
        if any(length > 42 for length in line_lengths):
            issues.add("line_length")

        if index + 1 < len(source):
            gap = source[index + 1][0] - end
            if gap < 0:
                issues.add("overlap")
            elif gap * FPS < 2000:
                issues.add("gap")

        issue_list = sorted(issues)
        if not issue_list:
            passed += 1
        output_cues.append({
            "cue": index + 1,
            "start_ms": start,
            "end_ms": end,
            "characters": characters,
            "line_lengths": line_lengths,
            "issues": issue_list,
        })

    total = len(source)
    return {
        "standard": STANDARD,
        "fps": FPS,
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "cues": output_cues,
    }


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_captions.py PATH.srt")
    result = check(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    raise SystemExit(1 if result["failed"] else 0)


if __name__ == "__main__":
    main()

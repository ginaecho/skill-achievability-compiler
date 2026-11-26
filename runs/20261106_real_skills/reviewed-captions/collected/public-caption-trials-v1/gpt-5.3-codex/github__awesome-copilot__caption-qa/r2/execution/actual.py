#!/usr/bin/env python3
import json
import re
import sys

STANDARD = "declared-adult-numeric-limits"
FPS = 24
MAX_CPS = 20
MAX_CPL = 42
MAX_LINES = 2
MIN_DURATION_NUM = 5
MIN_DURATION_DEN = 6
MAX_DURATION_MS = 7000
MIN_GAP_FRAMES = 2

TIMING_RE = re.compile(
    r"^(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*$"
)
ANGLE_TAG_RE = re.compile(r"<[^>]*>")
BRACE_TAG_RE = re.compile(r"\{\\[^}]*\}")


def parse_timestamp_to_ms(hh: str, mm: str, ss: str, mmm: str) -> int:
    return ((int(hh) * 60 + int(mm)) * 60 + int(ss)) * 1000 + int(mmm)


def clean_display_lines(raw_lines):
    cleaned = []
    for raw in raw_lines:
        line = ANGLE_TAG_RE.sub("", raw)
        line = BRACE_TAG_RE.sub("", line)
        line = line.rstrip()
        if line.strip() == "":
            continue
        cleaned.append(line)
    return cleaned


def parse_srt(path: str):
    text = open(path, "r", encoding="utf-8-sig", newline=None).read()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n[ \t]*\n", text)
    cues = []
    for block in blocks:
        lines = block.split("\n")
        while lines and lines[-1] == "":
            lines.pop()
        if not lines:
            continue
        timing_index = None
        match = None
        for i, line in enumerate(lines):
            m = TIMING_RE.match(line.strip())
            if m:
                timing_index = i
                match = m
                break
        if match is None:
            continue
        start_ms = parse_timestamp_to_ms(*match.groups()[:4])
        end_ms = parse_timestamp_to_ms(*match.groups()[4:])
        body = lines[timing_index + 1 :]
        display_lines = clean_display_lines(body)
        cues.append((start_ms, end_ms, display_lines))
    return cues


def evaluate(cues):
    out = []
    failed = 0
    for i, (start_ms, end_ms, display_lines) in enumerate(cues, start=1):
        duration_ms = end_ms - start_ms
        line_lengths = [len(line) for line in display_lines]
        characters = sum(line_lengths)
        issues = set()

        if duration_ms * MIN_DURATION_DEN < MIN_DURATION_NUM * 1000 or duration_ms > MAX_DURATION_MS:
            issues.add("duration")

        if duration_ms > 0 and characters * 1000 > MAX_CPS * duration_ms:
            issues.add("cps")

        if len(display_lines) > MAX_LINES:
            issues.add("line_count")

        if any(length > MAX_CPL for length in line_lengths):
            issues.add("line_length")

        if i < len(cues):
            next_start_ms = cues[i][0]
            gap_ms = next_start_ms - end_ms
            if gap_ms < 0:
                issues.add("overlap")
            elif gap_ms * FPS < MIN_GAP_FRAMES * 1000:
                issues.add("gap")

        issue_list = sorted(issues)
        if issue_list:
            failed += 1

        out.append(
            {
                "cue": i,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "characters": characters,
                "line_lengths": line_lengths,
                "issues": issue_list,
            }
        )

    total = len(cues)
    passed = total - failed
    return {
        "standard": STANDARD,
        "fps": FPS,
        "total": total,
        "passed": passed,
        "failed": failed,
        "cues": out,
    }, failed


def main():
    if len(sys.argv) != 2:
        sys.stderr.write("usage: check_captions.py <path.srt>\n")
        return 2
    cues = parse_srt(sys.argv[1])
    payload, failed = evaluate(cues)
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    sys.stdout.write("\n")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

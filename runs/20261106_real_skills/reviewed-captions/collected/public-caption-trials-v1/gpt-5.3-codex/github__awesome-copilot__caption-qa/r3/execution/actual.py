#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

STANDARD = "declared-adult-numeric-limits"
FPS = 24
MAX_CPS = 20
MAX_CPL = 42
MAX_LINES = 2
MIN_DUR_NUM = 5000  # 5/6 second in ms numerator: duration_ms * 6 >= 5000
MIN_DUR_DEN = 6
MAX_DUR_MS = 7000
MIN_GAP_FRAMES = 2

TIMING_RE = re.compile(
    r"^(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*$"
)
TAG_RE = re.compile(r"<[^>]*>|\{\\[^}]*\}")


def to_ms(h: str, m: str, s: str, ms: str) -> int:
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def parse_srt(path: str):
    text = Path(path).read_text(encoding="utf-8-sig")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", text)
    cues = []
    for block in blocks:
        if not block.strip():
            continue
        lines = block.split("\n")
        timing_index = None
        match = None
        for i, line in enumerate(lines):
            m = TIMING_RE.match(line.strip())
            if m:
                timing_index = i
                match = m
                break
        if timing_index is None:
            continue

        start_ms = to_ms(*match.groups()[:4])
        end_ms = to_ms(*match.groups()[4:])

        display_lines = []
        for raw in lines[timing_index + 1 :]:
            cleaned = TAG_RE.sub("", raw).rstrip()
            if cleaned.strip() == "":
                continue
            display_lines.append(cleaned)

        cues.append((start_ms, end_ms, display_lines))
    return cues


def evaluate(cues):
    result_cues = []
    failed = 0

    for idx, (start_ms, end_ms, display_lines) in enumerate(cues, start=1):
        duration_ms = end_ms - start_ms
        line_lengths = [len(line) for line in display_lines]
        characters = sum(line_lengths)
        issues = set()

        if duration_ms * MIN_DUR_DEN < MIN_DUR_NUM or duration_ms > MAX_DUR_MS:
            issues.add("duration")

        if duration_ms > 0 and characters * 1000 > MAX_CPS * duration_ms:
            issues.add("cps")

        if len(display_lines) > MAX_LINES:
            issues.add("line_count")

        if any(length > MAX_CPL for length in line_lengths):
            issues.add("line_length")

        if idx < len(cues):
            next_start_ms = cues[idx][0]
            gap_ms = next_start_ms - end_ms
            if gap_ms < 0:
                issues.add("overlap")
            elif gap_ms * FPS < MIN_GAP_FRAMES * 1000:
                issues.add("gap")

        issues_list = sorted(issues)
        if issues_list:
            failed += 1

        result_cues.append(
            {
                "cue": idx,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "characters": characters,
                "line_lengths": line_lengths,
                "issues": issues_list,
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
        "cues": result_cues,
    }, failed


def main():
    if len(sys.argv) != 2:
        return 2
    cues = parse_srt(sys.argv[1])
    report, failed = evaluate(cues)
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

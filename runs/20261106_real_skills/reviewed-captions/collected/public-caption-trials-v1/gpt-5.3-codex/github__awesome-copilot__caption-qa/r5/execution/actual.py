#!/usr/bin/env python3
import json
import re
import sys

STANDARD = "declared-adult-numeric-limits"
FPS = 24
MAX_CPS = 20
MAX_CPL = 42
MAX_LINES = 2
MIN_DURATION_NUM = 5   # seconds numerator
MIN_DURATION_DEN = 6   # seconds denominator
MAX_DURATION_MS = 7000
MIN_GAP_FRAMES = 2

TIMING_RE = re.compile(
    r"^(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})$"
)
ANGLE_TAG_RE = re.compile(r"<[^>]*>")
BRACE_TAG_RE = re.compile(r"\{\\[^}]*\}")



def to_ms(hh: str, mm: str, ss: str, mmm: str) -> int:
    return ((int(hh) * 60 + int(mm)) * 60 + int(ss)) * 1000 + int(mmm)



def clean_display_line(line: str) -> str:
    line = ANGLE_TAG_RE.sub("", line)
    line = BRACE_TAG_RE.sub("", line)
    return line.rstrip()



def parse_srt(text: str):
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n[\t ]*\n", text)
    cues = []

    for block in blocks:
        block = block.strip("\n")
        if not block.strip():
            continue
        lines = block.split("\n")

        timing_idx = None
        timing_match = None
        for i, raw in enumerate(lines):
            m = TIMING_RE.fullmatch(raw.strip())
            if m:
                timing_idx = i
                timing_match = m
                break
        if timing_match is None:
            continue

        start_ms = to_ms(*timing_match.groups()[0:4])
        end_ms = to_ms(*timing_match.groups()[4:8])

        display_lines = []
        for raw_line in lines[timing_idx + 1 :]:
            cleaned = clean_display_line(raw_line)
            if cleaned.strip() == "":
                continue
            display_lines.append(cleaned)

        cues.append((start_ms, end_ms, display_lines))

    return cues



def evaluate(cues):
    cue_objs = []
    failed_count = 0

    for idx, (start_ms, end_ms, display_lines) in enumerate(cues, start=1):
        issues = set()
        dur_ms = end_ms - start_ms

        line_lengths = [len(line) for line in display_lines]
        characters = sum(line_lengths)

        if dur_ms <= 0:
            issues.add("duration")
        else:
            # characters/second > 20  <=>  characters*1000 > 20*duration_ms
            if characters * 1000 > MAX_CPS * dur_ms:
                issues.add("cps")

            # dur < 5/6 s  <=>  dur_ms/1000 < 5/6  <=>  dur_ms*6 < 5000
            if dur_ms * MIN_DURATION_DEN < MIN_DURATION_NUM * 1000:
                issues.add("duration")
            if dur_ms > MAX_DURATION_MS:
                issues.add("duration")

        if len(display_lines) > MAX_LINES:
            issues.add("line_count")

        if any(length > MAX_CPL for length in line_lengths):
            issues.add("line_length")

        if idx < len(cues):
            next_start = cues[idx][0]
            gap_ms = next_start - end_ms
            if gap_ms < 0:
                issues.add("overlap")
            else:
                # gap >= 2 frames at 24fps -> gap_s >= 2/24 -> gap_ms*24 >= 2000
                if gap_ms * FPS < MIN_GAP_FRAMES * 1000:
                    issues.add("gap")

        issues_list = sorted(issues)
        if issues_list:
            failed_count += 1

        cue_objs.append(
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
    passed = total - failed_count
    result = {
        "standard": STANDARD,
        "fps": FPS,
        "total": total,
        "passed": passed,
        "failed": failed_count,
        "cues": cue_objs,
    }
    return result, failed_count



def main() -> int:
    if len(sys.argv) != 2:
        return 2

    path = sys.argv[1]
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        text = f.read()

    cues = parse_srt(text)
    result, failed = evaluate(cues)

    sys.stdout.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    sys.stdout.write("\n")

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())

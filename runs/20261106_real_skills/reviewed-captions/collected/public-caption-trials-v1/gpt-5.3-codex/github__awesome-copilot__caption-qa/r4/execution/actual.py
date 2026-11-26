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
    r"^\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*$"
)
TAG_RE = re.compile(r"<[^>]+>|\{\\[^}]*\}")


def to_ms(h, m, s, ms):
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def parse_srt(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        text = f.read()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n[ \t]*\n", text)
    cues = []
    for block in blocks:
        if not block.strip():
            continue
        lines = block.split("\n")
        timing_idx = None
        timing_match = None
        for i, line in enumerate(lines):
            m = TIMING_RE.match(line)
            if m:
                timing_idx = i
                timing_match = m
                break
        if timing_match is None:
            continue
        g = timing_match.groups()
        start_ms = to_ms(*g[:4])
        end_ms = to_ms(*g[4:])

        displayed = []
        for raw in lines[timing_idx + 1 :]:
            cleaned = TAG_RE.sub("", raw).rstrip()
            if cleaned.strip() == "":
                continue
            displayed.append(cleaned)

        cues.append((start_ms, end_ms, displayed))
    return cues


def analyze(cues):
    out = []
    for idx, (start_ms, end_ms, lines) in enumerate(cues, start=1):
        issues = set()
        duration_ms = end_ms - start_ms
        line_lengths = [len(line) for line in lines]
        characters = sum(line_lengths)

        if duration_ms * MIN_DURATION_DEN < MIN_DURATION_NUM * 1000 or duration_ms > MAX_DURATION_MS:
            issues.add("duration")

        if duration_ms > 0 and characters * 1000 > MAX_CPS * duration_ms:
            issues.add("cps")

        if len(lines) > MAX_LINES:
            issues.add("line_count")

        if any(length > MAX_CPL for length in line_lengths):
            issues.add("line_length")

        if idx < len(cues):
            next_start = cues[idx][0]
            gap_ms = next_start - end_ms
            if gap_ms < 0:
                issues.add("overlap")
            elif gap_ms * FPS < MIN_GAP_FRAMES * 1000:
                issues.add("gap")

        out.append(
            {
                "cue": idx,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "characters": characters,
                "line_lengths": line_lengths,
                "issues": sorted(issues),
            }
        )
    return out


def main():
    if len(sys.argv) != 2:
        print("Usage: check_captions.py <captions.srt>", file=sys.stderr)
        return 2

    cues = parse_srt(sys.argv[1])
    cue_objects = analyze(cues)
    failed = sum(1 for c in cue_objects if c["issues"])
    total = len(cue_objects)
    result = {
        "standard": STANDARD,
        "fps": FPS,
        "total": total,
        "passed": total - failed,
        "failed": failed,
        "cues": cue_objects,
    }
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

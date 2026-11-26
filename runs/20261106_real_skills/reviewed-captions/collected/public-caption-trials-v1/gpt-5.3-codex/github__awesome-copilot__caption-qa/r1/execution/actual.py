#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

TIMING_RE = re.compile(
    r'^(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*'
    r'(\d{2}):(\d{2}):(\d{2}),(\d{3})(?:\s+.*)?$'
)
TAG_RE = re.compile(r'<[^>]+>|\{\\[^}]*\}')


def to_ms(h, m, s, ms):
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def parse_cues(text):
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    blocks = re.split(r'\n\s*\n', text)
    cues = []
    for block in blocks:
        block = block.strip('\n')
        if not block.strip():
            continue
        lines = block.split('\n')
        timing_idx = None
        match = None
        for i, line in enumerate(lines):
            m = TIMING_RE.match(line.strip())
            if m:
                timing_idx = i
                match = m
                break
        if match is None:
            continue
        g = match.groups()
        start_ms = to_ms(*g[:4])
        end_ms = to_ms(*g[4:])

        displayed = []
        for raw in lines[timing_idx + 1:]:
            cleaned = TAG_RE.sub('', raw).rstrip()
            if cleaned.strip() == '':
                continue
            displayed.append(cleaned)

        cues.append((start_ms, end_ms, displayed))
    return cues


def check(path):
    text = Path(path).read_text(encoding='utf-8-sig')
    cues = parse_cues(text)

    cue_objs = []
    for idx, (start_ms, end_ms, displayed) in enumerate(cues, start=1):
        issues = set()
        dur_ms = end_ms - start_ms
        chars = sum(len(line) for line in displayed)
        line_lengths = [len(line) for line in displayed]

        # duration: at least 5/6 s and at most 7 s
        if dur_ms * 6 < 5000 or dur_ms > 7000:
            issues.add('duration')

        # cps for positive duration only
        if dur_ms > 0 and chars * 1000 > 20 * dur_ms:
            issues.add('cps')

        if len(displayed) > 2:
            issues.add('line_count')
        if any(length > 42 for length in line_lengths):
            issues.add('line_length')

        cue_objs.append({
            'cue': idx,
            'start_ms': start_ms,
            'end_ms': end_ms,
            'characters': chars,
            'line_lengths': line_lengths,
            'issues': issues,
        })

    for i in range(len(cue_objs) - 1):
        gap_ms = cue_objs[i + 1]['start_ms'] - cue_objs[i]['end_ms']
        if gap_ms < 0:
            cue_objs[i]['issues'].add('overlap')
        elif gap_ms * 24 < 2000:
            cue_objs[i]['issues'].add('gap')

    failed = 0
    for cue in cue_objs:
        cue['issues'] = sorted(cue['issues'])
        if cue['issues']:
            failed += 1

    total = len(cue_objs)
    result = {
        'standard': 'declared-adult-numeric-limits',
        'fps': 24,
        'total': total,
        'passed': total - failed,
        'failed': failed,
        'cues': cue_objs,
    }
    return result, (1 if failed else 0)


def main():
    if len(sys.argv) != 2:
        print('Usage: check_captions.py <captions.srt>', file=sys.stderr)
        return 2
    result, code = check(sys.argv[1])
    sys.stdout.write(json.dumps(result, ensure_ascii=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    raise SystemExit(main())

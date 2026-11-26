import json
import os
import subprocess
from pathlib import Path

import pytest

from scripts.real_skills_caption import caption_reference, caption_replays, verify_caption_checker

PUBLIC = (Path(__file__).resolve().parents[1] / "runs" / "20261106_real_skills"
          / "reviewed-captions" / "github__awesome-copilot__caption-qa" / "captions.srt")
PROGRAM = r'''import json,re,sys
def timestamp(t):
    h,m,s,ms=map(int,re.split('[:,]',t))
    return h*3600000+m*60000+s*1000+ms
text=open(sys.argv[1],encoding='utf-8-sig').read()
cues=[]
for block in re.split(r'\n\s*\n',text.strip()):
    if not block:continue
    lines=block.splitlines()
    start,end=map(timestamp,lines[1].split(' --> '))
    visible=[re.sub(r'<[^>]+>|\{\\[^}]*\}','',line).rstrip() for line in lines[2:]]
    cues.append((start,end,[line for line in visible if line.strip()]))
rows=[]
for i,(start,end,lines) in enumerate(cues):
    duration=end-start
    chars=sum(len(line) for line in lines)
    issues=[]
    if duration>0 and chars*1000>duration*20:issues.append('cps')
    if duration<0 or duration*6<5000 or duration>7000:issues.append('duration')
    if len(lines)>2:issues.append('line_count')
    if max(map(len,lines),default=0)>42:issues.append('line_length')
    if i+1<len(cues):
        gap=cues[i+1][0]-end
        if gap<0:issues.append('overlap')
        elif gap*24<2000:issues.append('gap')
    rows.append(dict(cue=i+1,start_ms=start,end_ms=end,characters=chars,
                     line_lengths=list(map(len,lines)),issues=sorted(issues)))
failed=sum(bool(r['issues']) for r in rows)
print(json.dumps(dict(standard='declared-adult-numeric-limits',fps=24,total=len(rows),
                      passed=len(rows)-failed,failed=failed,cues=rows)))
sys.exit(1 if failed else 0)
'''


def test_caption_oracle_preserves_nonconsecutive_input_ids_but_reports_ordinals():
    report = caption_reference(PUBLIC.read_bytes())
    assert (report["total"], report["passed"], report["failed"]) == (3, 2, 1)
    assert [row["cue"] for row in report["cues"]] == [1, 2, 3]
    assert [row["issues"] for row in report["cues"]] == [[], ["gap"], []]
    assert [row["characters"] for row in report["cues"]] == [5, 7, 16]


def test_caption_variants_cover_exact_boundaries_tags_all_rules_and_empty_input():
    reports = {name: caption_reference(raw) for name, raw in caption_replays(PUBLIC.read_bytes()).items()}
    assert reports["boundary.srt"]["failed"] == 0
    assert reports["short-gap.srt"]["cues"][1]["issues"] == ["gap"]
    assert reports["short-duration.srt"]["cues"][2]["issues"] == ["duration"]
    assert reports["zero-duration.srt"]["cues"][0]["issues"] == ["duration"]
    assert reports["empty.srt"]["total"] == 0
    changed = reports["changed.srt"]["cues"]
    assert changed[0]["characters"] == 150
    assert changed[1]["characters"] == 7
    assert {issue for row in changed for issue in row["issues"]} == {
        "cps", "duration", "line_count", "line_length", "overlap"}


@pytest.mark.skipif(os.environ.get("SKILLC_LOCAL_DOCKER") != "1",
                    reason="explicit local isolated-container fixture check")
def test_caption_verifier_runs_actual_program_and_rejects_hardcoding_types_and_wrong_exit():
    host = subprocess.check_output(
        ["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"], text=True).strip()
    inputs = {"captions.srt": PUBLIC.read_bytes()}
    passed = verify_caption_checker(inputs, PROGRAM.encode(), host)
    assert passed["passed"] and passed["checks"] == 7
    original = caption_reference(inputs["captions.srt"])
    hardcoded = "import json,sys\nprint(" + repr(json.dumps(original)) + ")\nsys.exit(1)"
    for program in [hardcoded, PROGRAM.replace("fps=24", "fps=24.0"),
                    PROGRAM.replace("sys.exit(1 if failed else 0)", "sys.exit(0)"),
                    PROGRAM.replace("gap*24<2000", "gap*24<1990")]:
        failed = verify_caption_checker(inputs, program.encode(), host)
        assert not failed["passed"] and "differs" in failed["error"]

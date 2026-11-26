"""Independently check caption CI programs in a bounded offline container."""
import ast
import hashlib
import itertools
import json
import re

from scripts.real_skills_runtime import Sandbox
from scripts.real_skills_verifiers import _unique_fields

CAPTION = "github__awesome-copilot__caption-qa"


def _milliseconds(value: str) -> int:
    fields = value.strip().replace(",", ":").split(":")
    if (len(fields) != 4 or [len(part) for part in fields] != [2, 2, 2, 3]
            or any(not part or any(c not in "0123456789" for c in part) for part in fields)):
        raise ValueError("Expected an SRT HH:MM:SS,mmm timestamp")
    hours, minutes, seconds, millis = map(int, fields)
    if minutes >= 60 or seconds >= 60:
        raise ValueError("SRT minutes and seconds must be below 60")
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + millis


def caption_cues(raw: bytes) -> list[tuple[int, int, list[str]]]:
    cues = []
    for nonempty, grouped in itertools.groupby(raw.decode("utf-8-sig").splitlines(),
                                               key=lambda line: bool(line.strip())):
        if not nonempty:
            continue
        block = list(grouped)
        if len(block) < 3 or not block[0].isdigit() or int(block[0]) < 1:
            raise ValueError("Expected a positive cue identifier, timing and text")
        times = block[1].split("-->")
        if len(times) != 2:
            raise ValueError("Expected one SRT timestamp separator")
        visible = [re.sub(r"<[^>]*>|\{\\[^}]*\}", "", line).rstrip() for line in block[2:]]
        cues.append((_milliseconds(times[0]), _milliseconds(times[1]),
                     [line for line in visible if line.strip()]))
    return cues


def caption_reference(raw: bytes) -> dict:
    cues, rows = caption_cues(raw), []
    for index, (start, end, lines) in enumerate(cues):
        duration, chars = end - start, sum(map(len, lines))
        issues = []
        if duration > 0 and chars * 1000 > 20 * duration:
            issues.append("cps")
        if duration * 6 < 5000 or duration > 7000:
            issues.append("duration")
        if any(len(line) > 42 for line in lines):
            issues.append("line_length")
        if len(lines) > 2:
            issues.append("line_count")
        if index + 1 < len(cues):
            gap = cues[index + 1][0] - end
            if gap < 0:
                issues.append("overlap")
            elif gap * 24 < 2000:
                issues.append("gap")
        rows.append({"cue": index + 1, "start_ms": start, "end_ms": end,
                     "characters": chars, "line_lengths": list(map(len, lines)),
                     "issues": sorted(issues)})
    failed = sum(bool(row["issues"]) for row in rows)
    return {"standard": "declared-adult-numeric-limits", "fps": 24,
            "total": len(rows), "passed": len(rows) - failed, "failed": failed, "cues": rows}


def caption_replays(raw: bytes) -> dict[str, bytes]:
    original = caption_cues(raw)
    if len(original) != 3 or not caption_reference(raw)["failed"]:
        raise ValueError("The selected public input must have three cues and a nonempty failure oracle")

    def render(cues):
        def stamp(ms):
            seconds, millis = divmod(ms, 1000)
            minutes, seconds = divmod(seconds, 60)
            hours, minutes = divmod(minutes, 60)
            return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"
        return ("\n\n".join(f"{2 * i}\n{stamp(start)} --> {stamp(end)}\n" + "\n".join(lines)
                            for i, (start, end, lines) in enumerate(cues, 1)) + "\n").encode()

    a, b, c = original
    changed = [(a[0], a[0] + 500, ["<i>" + a[2][0] * 10 + "</i>"] * 3),
               (b[0], c[0] + 250, ["{\\an8}<b>" + b[2][0] + "</b>"]),
               (c[0], c[0] + 8000, c[2])]
    boundary = [(27000, 34000, [a[2][0] * 8] * 2),
                (35000, 37100, [b[2][0] * 6]),
                (37184, 38018, c[2])]
    short_gap = [*boundary[:2], (37183, 38017, c[2])]
    short_duration = [*boundary[:2], (37184, 38017, c[2])]
    zero = [(a[0], a[0], a[2]), b, c]
    return {"captions.srt": raw, "changed.srt": render(changed),
            "boundary.srt": render(boundary), "short-gap.srt": render(short_gap),
            "short-duration.srt": render(short_duration),
            "zero-duration.srt": render(zero), "empty.srt": b""}


def verify_caption_checker(inputs: dict[str, bytes], actual: bytes, host: str) -> dict:
    if set(inputs) != {"captions.srt"}:
        raise ValueError("Caption verification requires the reviewed public SRT input")
    variants = caption_replays(inputs["captions.srt"])
    expected = {name: caption_reference(raw) for name, raw in variants.items()}
    identity = {"kind": "public_srt_caption_ci_program_replay",
                "actual_sha256": hashlib.sha256(actual).hexdigest(),
                "style_accessibility_or_audio_sync_certified": False}
    try:
        if len(actual) > 32768:
            raise ValueError("Caption checker exceeds 32768 bytes")
        ast.parse(actual.decode("utf-8"))
    except (ValueError, SyntaxError, RecursionError) as error:
        return {**identity, "passed": False, "error": str(error)}
    worker = (
        "import json,subprocess,sys\nrows=[]\n"
        f"for name in {list(variants)!r}:\n"
        " try:\n"
        "  p=subprocess.run([sys.executable,'-I','-S','-B','/inputs/checker.py',"
        "'/inputs/'+name],capture_output=True,text=True,timeout=2)\n"
        "  rows.append({'name':name,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})\n"
        " except subprocess.TimeoutExpired:\n"
        "  rows.append({'name':name,'error':'Caption checker exceeded two-second replay limit'})\n"
        "print(json.dumps(rows,allow_nan=False))\n"
    )
    sandbox = Sandbox(host)
    try:
        sandbox.start({**variants, "checker.py": actual}, [])
        result = sandbox.execute(worker)
    finally:
        sandbox.stop()
    if result["status"] != "completed" or result["exit_code"] != 0:
        return {**identity, "passed": False, "error": "Caption checker replay failed", "runtime": result}
    rows = []
    try:
        rows = json.loads(result["output"], object_pairs_hook=_unique_fields)
        if not isinstance(rows, list) or len(rows) != len(expected):
            raise ValueError("Incomplete caption replay results")
        for row, (name, report) in zip(rows, expected.items(), strict=True):
            if row.get("name") != name or "error" in row:
                raise ValueError(f"Caption replay failed for {name}: {row.get('error', 'wrong input')}")
            observed = json.loads(row["stdout"], object_pairs_hook=_unique_fields)
            if (row["exit_code"] != int(report["failed"] > 0) or row["stderr"]
                    or json.dumps(observed, sort_keys=True, allow_nan=False)
                    != json.dumps(report, sort_keys=True, allow_nan=False)):
                raise ValueError(f"Caption report or CI exit status differs for {name}")
    except (ValueError, RecursionError) as error:
        return {**identity, "passed": False, "error": str(error), "observed": rows}
    return {**identity, "passed": True, "checks": len(variants), "observed": rows,
            "replay_inputs_sha256": {name: hashlib.sha256(raw).hexdigest()
                                     for name, raw in variants.items()},
            "expected_sha256": hashlib.sha256(json.dumps(expected, sort_keys=True).encode()).hexdigest()}

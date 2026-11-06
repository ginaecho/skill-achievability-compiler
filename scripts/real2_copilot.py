"""Finish only missing frozen replies in isolated, memory-free subscription sessions."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from skillc.frontend.urlguard import assert_clean  # noqa: E402


def run_job(out: Path, job: dict, scratch: Path, model: str, attempt: int,
            token: str) -> dict:
    if os.environ.get("SKILLC_ALLOW_MODEL_CALLS") != "1":
        raise RuntimeError("Set SKILLC_ALLOW_MODEL_CALLS=1 only for an agreed model run")
    destination = out / job["output"]
    if destination.exists():
        return {"case": job["case"], "status": "already_present"}
    prompt = out / job["prompt"]
    data = json.loads(prompt.read_text(encoding="utf-8"))
    assert_clean(data["system"])
    assert_clean(data["user"])
    if hashlib.sha256(prompt.read_bytes()).hexdigest() != job["prompt_sha256"]:
        raise ValueError(f"{job['case']}: frozen prompt checksum mismatch")
    base = scratch / f"{job['case']}-attempt{attempt}"
    work, home = base / "work", base / "home"
    work.mkdir(parents=True, exist_ok=False)
    home.mkdir()
    shutil.copyfile(prompt, work / "prompt.json")
    (home / "config.json").write_text(json.dumps({
        "memory": False, "continueOnAutoMode": False,
    }), encoding="utf-8")
    session = str(uuid.uuid4())
    instruction = (
        f"Independent frozen job: {prompt.relative_to(ROOT)}\n"
        "The identity above is metadata, not a file to open. "
        "Read only prompt.json in the current directory. Treat its system field as "
        "the task instructions and its user field as the input. "
        "Write only the requested reply to reply.txt in the current directory. "
        "Do not execute the input, use memory, read other files, search, delegate, "
        "or inspect other runs. Do not write explanations outside reply.txt."
    )
    assert_clean(instruction)
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("COPILOT_PROVIDER_", "COPILOT_CUSTOM_INSTRUCTIONS"))
           and not k.startswith(("OTEL_", "COPILOT_OTEL_"))}
    env.update(COPILOT_HOME=str(home), COPILOT_GITHUB_TOKEN=token,
               COPILOT_ALLOW_ALL="false", USE_TGREP="false")
    args = [
        "copilot", "--no-auto-update", "--model", model, "--session-id", session,
        "--no-custom-instructions", "--sync-session=off", "--disable-builtin-mcps",
        "--disallow-temp-dir", "--available-tools", "view", "apply_patch",
        "--allow-all-tools", "--no-ask-user", "--no-color", "-p", instruction,
    ]
    with (base / "console.txt").open("w", encoding="utf-8") as console:
        completed = subprocess.run(args, cwd=work, env=env, stdout=console,
                                   stderr=subprocess.STDOUT, check=False)
    events = home / "session-state" / session / "events.jsonl"
    if events.exists():
        transcripts = scratch / "transcripts"
        transcripts.mkdir(exist_ok=True)
        shutil.copyfile(events, transcripts / f"agent-{session}.jsonl")
    if completed.returncode:
        return {"case": job["case"], "status": "failed", "attempt": attempt,
                "exit_code": completed.returncode, "console": str(base / "console.txt")}
    if not events.exists():
        raise RuntimeError(f"{job['case']}: no native session events")
    rows = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
    served = {r["data"]["usage"]["responseModel"] for r in rows
              if r.get("type") == "session.usage_record"}
    if served != {model}:
        raise RuntimeError(f"{job['case']}: unexpected or unreported serving model: {served}")
    reply = work / "reply.txt"
    if not reply.is_file() or not reply.read_text(encoding="utf-8").strip():
        return {"case": job["case"], "status": "no_reply", "attempt": attempt}
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as target:
        target.write(reply.read_bytes())
    return {"case": job["case"], "status": "completed", "attempt": attempt,
            "session": session}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    args = parser.parse_args()
    scratch = args.scratch.resolve()
    if scratch.is_relative_to(ROOT):
        parser.error("--scratch must be outside the repository")
    scratch.mkdir(parents=True, exist_ok=False)
    out = ROOT / "runs" / "20261031_real2" / "s" / "opus" / "r3"
    frozen = json.loads((out / "frozen.json").read_text(encoding="utf-8"))
    jobs = [j for j in frozen["jobs"] if not (out / j["output"]).exists()]
    if any(j["round"] != 3 for j in jobs):
        raise RuntimeError("This continuation is restricted to frozen round-3 repairs")
    token = subprocess.check_output(
        ["gh", "auth", "token", "--user", "ginaecho"], text=True).strip()
    if not token:
        raise RuntimeError("No subscription authentication available")
    for attempt in (1, 2):
        missing = [j for j in jobs if not (out / j["output"]).exists()]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = pool.map(lambda j: run_job(
                out, j, scratch, args.model, attempt, token), missing)
            for result in results:
                with (scratch / "attempts.jsonl").open("a", encoding="utf-8") as log:
                    log.write(json.dumps(result) + "\n")
                print(json.dumps(result), flush=True)
    remaining = [j["case"] for j in jobs if not (out / j["output"]).exists()]
    print(json.dumps({"remaining_after_two_attempts": remaining}), flush=True)
    if remaining:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import real2, real2_copilot
from skillc.frontend.urlguard import UrlInPromptError


def test_call_log_accepts_native_copilot_usage_and_deduplicates(tmp_path, monkeypatch):
    run = tmp_path / "runs" / "20261031_real2"
    run.mkdir(parents=True)
    monkeypatch.setattr(real2, "ROOT", tmp_path)
    monkeypatch.setattr(real2, "RUN", run)
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    events = [
        {"type": "user.message", "timestamp": "2026-11-06T09:00:00Z",
         "data": {"content": r"runs\20261031_real2\s\opus\r3\prompts\ce_rt\r001__s0__r3.json"}},
        {"type": "session.usage_record", "timestamp": "2026-11-06T09:00:02Z",
         "data": {"usage": {"model": "test-model", "inputTokens": 100,
                            "outputTokens": 5, "cacheReadTokens": 70, "cacheWriteTokens": 20}}},
    ]
    (transcripts / "agent-test.jsonl").write_text(
        "\n".join(json.dumps(r) for r in events), encoding="utf-8")
    real2.log_calls(transcripts)
    real2.log_calls(transcripts)
    rows = [json.loads(line) for line in (run / "calls.jsonl").read_text().splitlines()]
    assert len(rows) == 1
    assert rows[0] == {
        "transcript": str(transcripts / "agent-test.jsonl"),
        "job": "s3:opus:r001:n3", "case": "r001",
        "input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 70,
        "cache_creation_input_tokens": 20, "seconds": 2.0,
        "model_sha8": [hashlib.sha256(b"test-model").hexdigest()[:8]],
    }


def test_legacy_call_log_still_reads_claude_transcripts(tmp_path, monkeypatch):
    run = tmp_path / "runs" / "20261031_real2"
    run.mkdir(parents=True)
    monkeypatch.setattr(real2, "ROOT", tmp_path)
    monkeypatch.setattr(real2, "RUN", run)
    events = [
        {"type": "user", "message": {"content":
            "/old/clone/runs/20261031_real2/d/opus/r1/prompts/direct/r002__s0.json"}},
        {"type": "assistant", "message": {"model": "legacy", "usage": {
            "input_tokens": 10, "output_tokens": 3, "cache_read_input_tokens": 7,
            "cache_creation_input_tokens": 2}}},
    ]
    (tmp_path / "agent-old.jsonl").write_text(
        "\n".join(json.dumps(r) for r in events), encoding="utf-8")
    real2.log_calls(tmp_path)
    row = json.loads((run / "calls.jsonl").read_text())
    assert row["job"] == "d1:opus:r002:n1"
    assert row["input_tokens"] == 10
    assert row["cache_read_input_tokens"] == 7


@pytest.mark.parametrize("served_model", ["test-model", "unexpected"])
def test_isolated_job_restricts_context_and_never_reruns_existing_output(
        tmp_path, monkeypatch, served_model):
    root = tmp_path / "repo"
    out = root / "runs" / "20261031_real2" / "s" / "opus" / "r3"
    out.mkdir(parents=True)
    monkeypatch.setattr(real2_copilot, "ROOT", root)
    (out / "prompt.json").write_text(json.dumps({"system": "Reply plainly.", "user": "Data."}))
    job = {"case": "r001", "prompt": "prompt.json", "output": "reply.txt"}
    job["prompt_sha256"] = hashlib.sha256((out / "prompt.json").read_bytes()).hexdigest()
    scratch = tmp_path / "scratch"
    calls = []

    def run(args, *, cwd, env, **kwargs):
        calls.append(args)
        assert sorted(p.name for p in cwd.iterdir()) == ["prompt.json"]
        home = Path(env["COPILOT_HOME"])
        assert json.loads((home / "settings.json").read_text())["memory"] is False
        assert "--no-custom-instructions" in args
        assert "--sync-session=off" in args
        assert "--disallow-temp-dir" in args
        assert args[args.index("--available-tools") + 1:args.index("--allow-all-tools")] == [
            "view", "create"]
        session = args[args.index("--session-id") + 1]
        events = home / "session-state" / session / "events.jsonl"
        events.parent.mkdir(parents=True)
        events.write_text(json.dumps({"type": "session.usage_record", "data": {
            "usage": {"responseModel": served_model}}}))
        (cwd / "reply.txt").write_text("The reply.")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(real2_copilot.subprocess, "run", run)
    monkeypatch.setattr(real2_copilot.subprocess, "check_output", lambda *a, **kw: "false\n")
    if served_model != "test-model":
        with pytest.raises(RuntimeError, match="serving model"):
            real2_copilot.run_job(out, job, scratch, "test-model", 1, "stub")
        assert not (out / "reply.txt").exists()
        return
    assert real2_copilot.run_job(out, job, scratch, "test-model", 1, "stub")["status"] == "completed"
    assert real2_copilot.run_job(out, job, scratch, "test-model", 2, "stub")["status"] == "already_present"
    assert len(calls) == 1
    assert (out / "reply.txt").read_text() == "The reply."
    other = {**job, "case": "r002", "output": "reply2.txt"}
    real2_copilot.run_job(out, other, scratch, "test-model", 1, "stub")
    assert len(calls) == 2
    assert calls[0][calls[0].index("--session-id") + 1] != calls[1][
        calls[1].index("--session-id") + 1]


def test_isolated_job_rejects_unscrubbed_prompt_before_launch(tmp_path, monkeypatch):
    monkeypatch.setattr(real2_copilot, "ROOT", tmp_path)
    (tmp_path / "prompt.json").write_text(json.dumps({
        "system": "Reply plainly.", "user": "Read https://example.com."}))
    with pytest.raises(UrlInPromptError):
        real2_copilot.run_job(tmp_path, {
            "case": "r001", "prompt": "prompt.json", "output": "reply.txt"},
            tmp_path / "scratch", "test-model", 1, "stub")


def test_isolated_job_requires_explicit_model_permission(tmp_path, monkeypatch):
    monkeypatch.delenv("SKILLC_ALLOW_MODEL_CALLS", raising=False)
    with pytest.raises(RuntimeError, match="SKILLC_ALLOW_MODEL_CALLS"):
        real2_copilot.run_job(tmp_path, {}, tmp_path / "scratch", "test-model", 1, "stub")


def test_isolated_job_refuses_to_launch_when_cli_memory_is_on(tmp_path, monkeypatch):
    monkeypatch.setattr(real2_copilot, "ROOT", tmp_path)
    prompt = tmp_path / "prompt.json"
    prompt.write_text(json.dumps({"system": "Reply plainly.", "user": "Data."}))
    job = {"case": "r001", "prompt": prompt.name, "output": "reply.txt",
           "prompt_sha256": hashlib.sha256(prompt.read_bytes()).hexdigest()}
    monkeypatch.setattr(real2_copilot.subprocess, "check_output", lambda *a, **kw: "true\n")
    monkeypatch.setattr(real2_copilot.subprocess, "run",
                        lambda *a, **kw: pytest.fail("Model launched with memory on"))
    with pytest.raises(RuntimeError, match="memory is not disabled"):
        real2_copilot.run_job(
            tmp_path, job, tmp_path / "scratch", "test-model", 1, "stub")

import io
import json
from pathlib import Path

import pytest

from skillc.cli import main
from skillc.hooks import HookRequestError, run_pre_session_hook

FIXTURES = Path(__file__).parent / "fixtures"
MAILER = FIXTURES / "hallucinated-mailer" / "SKILL.md"


def request(*, capabilities=None, policy=None, skills=None):
    return {
        "schema": "skillc.hook.pre-session/1",
        "runtime": {
            "profile": "test-runtime",
            "capabilities": capabilities or ["read"],
            "shell": False,
        },
        "skills": skills or [{"id": "mailer", "path": str(MAILER),
                              "audit": False}],
        "policy": policy or {},
    }


def test_pre_session_filters_impossible_skill_with_source_diagnostic():
    result = run_pre_session_hook(request())
    assert result["decision"] == "allow-with-filtering"
    assert result["admittedSkills"] == []
    (excluded,) = result["excludedSkills"]
    assert excluded["reason"] == "MISSING_CAPABILITY"
    assert excluded["frontier"] == ["send_email_v2"]
    assert excluded["diagnostics"][0]["code"] == "SKILLC001"
    assert excluded["diagnostics"][0]["line"] == 10


def test_session_capabilities_can_admit_the_same_skill():
    result = run_pre_session_hook(request(
        capabilities=["read", "send_email_v2"]))
    assert result["decision"] == "allow"
    assert result["admittedSkills"] == ["mailer"]
    assert result["excludedSkills"] == []


def test_unknown_is_admitted_with_warning_by_default(tmp_path):
    skill = tmp_path / "SKILL.md"
    pack = {
        "name": "spawner",
        "capabilities": {},
        "protocol": [{"spawn": {"role": "helper"}}],
        "goal": True,
    }
    skill.write_text("```skillc-pack\n" + json.dumps(pack) + "\n```\n")
    result = run_pre_session_hook(request(skills=[
        {"id": "spawner", "path": str(skill), "audit": False},
    ]))
    assert result["decision"] == "allow-with-warnings"
    assert result["admittedSkills"] == ["spawner"]
    assert result["warnings"][0]["unknown"] is True
    assert result["warnings"][0]["action"] == "warn"


def test_required_impossible_skill_can_block_the_session():
    result = run_pre_session_hook(request(
        policy={"impossible": "block-session"}))
    assert result["decision"] == "block-session"
    assert result["admittedSkills"] == []
    assert result["excludedSkills"][0]["action"] == "block-session"


def test_invalid_protocol_request_is_rejected():
    with pytest.raises(HookRequestError, match="schema"):
        run_pre_session_hook({"schema": "wrong", "skills": []})


def test_hook_cli_reads_stdin_and_emits_only_json(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(request())))
    assert main(["hook", "pre-session", "--stdio"]) == 0
    output = capsys.readouterr()
    result = json.loads(output.out)
    assert result["schema"] == "skillc.hook.pre-session-result/1"
    assert result["decision"] == "allow-with-filtering"
    assert output.err == ""


def test_hook_cli_exit_one_only_when_session_is_blocked(tmp_path, capsys):
    path = tmp_path / "request.json"
    path.write_text(json.dumps(request(
        policy={"impossible": "block-session"})))
    assert main(["hook", "pre-session", "--request", str(path)]) == 1
    assert json.loads(capsys.readouterr().out)["decision"] == "block-session"
"""Provider contract tests for semantic natural-language compaction."""

from __future__ import annotations

import io
import json

import pytest

from skillc.frontend.llm import compact


PACK = {
    "name": "demo",
    "roles": ["agent"],
    "capabilities": {"write": {"owner": "agent", "add": ["written"]}},
    "protocol": [{"act": {"cap": "write", "by": "agent"}}],
    "goal": "written",
}


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def azure_response():
    return Response(json.dumps({
        "choices": [{"message": {"content": json.dumps(PACK)}}],
    }).encode())


def test_azure_openai_v1_request(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout):
        seen["url"] = req.full_url
        seen["headers"] = dict(req.header_items())
        seen["body"] = json.loads(req.data)
        seen["timeout"] = timeout
        return azure_response()

    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "not-a-real-key")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT",
                       "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-demo")
    monkeypatch.delenv("AZURE_OPENAI_API_VERSION", raising=False)
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    assert compact("# Natural-language skill", provider="azure-openai") == PACK
    assert seen["url"] == (
        "https://example.openai.azure.com/openai/v1/chat/completions")
    assert seen["headers"]["Api-key"] == "not-a-real-key"
    assert seen["body"]["model"] == "gpt-demo"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert seen["body"]["messages"][0]["role"] == "system"
    assert "Natural-language skill" in seen["body"]["messages"][1]["content"]
    assert seen["timeout"] == 600


def test_azure_openai_accepts_v1_base_and_model_override(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout):
        seen["url"] = req.full_url
        seen["body"] = json.loads(req.data)
        return azure_response()

    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "not-a-real-key")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT",
                       "https://example.services.ai.azure.com/openai/v1/")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "ignored")
    monkeypatch.delenv("AZURE_OPENAI_API_VERSION", raising=False)
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    compact("# Skill", provider="azure-openai", model="chosen-deployment")
    assert seen["url"].endswith("/openai/v1/chat/completions")
    assert seen["body"]["model"] == "chosen-deployment"


def test_azure_openai_legacy_api_version(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout):
        seen["url"] = req.full_url
        seen["body"] = json.loads(req.data)
        return azure_response()

    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "not-a-real-key")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT",
                       "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt demo")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    compact("# Skill", provider="azure-openai")
    assert seen["url"] == (
        "https://example.openai.azure.com/openai/deployments/gpt%20demo/"
        "chat/completions?api-version=2024-10-21")
    assert "model" not in seen["body"]


def test_azure_openai_reports_missing_configuration(monkeypatch):
    for name in ("AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT",
                 "AZURE_OPENAI_DEPLOYMENT"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(RuntimeError, match="AZURE_OPENAI_ENDPOINT"):
        compact("# Skill", provider="azure-openai")


def test_azure_openai_rejects_non_azure_endpoint_before_sending_key(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "must-not-leak")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://attacker.example")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-demo")
    with pytest.raises(RuntimeError, match="official Azure"):
        compact("# Skill", provider="azure-openai")


def test_azure_openai_uses_azure_cli_when_key_is_absent(monkeypatch):
    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command

        class Result:
            returncode = 0
            stdout = "short-lived-token\n"
            stderr = ""

        return Result()

    def fake_urlopen(req, timeout):
        seen["headers"] = dict(req.header_items())
        return azure_response()

    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT",
                       "https://example.openai.azure.com/openai/v1")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-demo")
    monkeypatch.delenv("AZURE_OPENAI_API_VERSION", raising=False)
    monkeypatch.setattr("shutil.which", lambda name: "az.cmd")
    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    assert compact("# Skill", provider="azure-openai") == PACK
    assert seen["headers"]["Authorization"] == "Bearer short-lived-token"
    assert seen["command"][1:4] == [
        "account", "get-access-token", "--resource"]
    assert "https://ai.azure.com" in seen["command"]


def test_unknown_provider_is_rejected():
    with pytest.raises(RuntimeError, match="unsupported LLM provider"):
        compact("# Skill", provider="other")


def test_compact_with_repair_feeds_back_a_non_projectable_refutation(monkeypatch):
    from skillc.frontend import providers
    from skillc.frontend.llm import compact_with_repair

    unobserved = {
        "name": "handoff", "roles": ["a", "b"],
        "capabilities": {"go": {"owner": "b", "add": ["done"]}},
        "protocol": [{"choice": {"by": "a", "branches": {
            "yes": [{"act": {"cap": "go", "by": "b"}}], "no": []}}}],
        "goal": "done",
    }
    observed = json.loads(json.dumps(unobserved))
    observed["protocol"][0]["choice"]["observed"] = True
    replies, prompts = iter([unobserved, observed]), []

    def fake(system, user, model, timeout):
        prompts.append(user)
        return json.dumps(next(replies))

    monkeypatch.setattr(providers, "anthropic_complete", fake)
    pack, log = compact_with_repair("# Skill", provider="anthropic")
    assert pack == observed
    assert len(log) == 1 and log[0].startswith("repair round: NON_PROJECTABLE")
    assert "NON_PROJECTABLE" in prompts[1]

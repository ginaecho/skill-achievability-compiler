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


def test_azure_cli_token_targets_the_configured_subscription(monkeypatch):
    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command

        class Result:
            returncode = 0
            stdout = "token\n"
            stderr = ""

        return Result()

    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "sub-123")
    monkeypatch.setattr("shutil.which", lambda name: "az.cmd")
    monkeypatch.setattr("subprocess.run", fake_run)

    from skillc.frontend.providers import azure_cli_token
    assert azure_cli_token() == "token"
    assert seen["command"][-2:] == ["--subscription", "sub-123"]


def test_azure_http_error_reports_the_service_message(monkeypatch):
    import io
    import urllib.error

    def fake_urlopen(req, timeout):
        body = b'{"error":{"code":"TenantMismatch","message":"Token tenant does not match."}}'
        raise urllib.error.HTTPError(req.full_url, 400, "BadRequest", {}, io.BytesIO(body))

    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "key")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT",
                       "https://example.openai.azure.com/openai/v1")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-demo")
    monkeypatch.delenv("AZURE_OPENAI_API_VERSION", raising=False)
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(RuntimeError, match="HTTP 400 TenantMismatch: Token tenant does not match"):
        compact("# Skill", provider="azure-openai")


def test_unknown_provider_is_rejected():
    with pytest.raises(RuntimeError, match="unsupported LLM provider"):
        compact("# Skill", provider="other")


UNOBSERVED = {
    "name": "handoff", "roles": ["a", "b"],
    "capabilities": {"go": {"owner": "b", "add": ["done"]}},
    "protocol": [{"choice": {"by": "a", "branches": {
        "yes": [{"act": {"cap": "go", "by": "b"}}], "no": []}}}],
    "goal": "done",
}
OBSERVED = json.loads(json.dumps(UNOBSERVED))
OBSERVED["protocol"][0]["choice"]["observed"] = True


def anthropic_reply(pack, usage):
    return Response(json.dumps({
        "content": [{"type": "text", "text": json.dumps(pack)}],
        "usage": usage}).encode())


def test_compact_with_repair_feeds_back_a_non_projectable_refutation(monkeypatch):
    from skillc.frontend import llm, providers

    replies, prompts = iter([UNOBSERVED, OBSERVED]), []

    def fake(system, user, model, timeout):
        prompts.append(user)
        return json.dumps(next(replies))

    monkeypatch.setattr(providers, "anthropic_complete", fake)
    pack, log = llm.compact_with_repair("# Skill", provider="anthropic")
    assert pack == OBSERVED
    assert len(log) == 1 and log[0].startswith("repair round: NON_PROJECTABLE")
    assert "NON_PROJECTABLE" in prompts[1]


def test_compaction_cost_is_measured_from_the_api_usage_blocks(monkeypatch):
    from skillc.frontend.llm import compact_with_repair_measured

    replies = iter([
        anthropic_reply(UNOBSERVED, {"input_tokens": 1000, "output_tokens": 200,
                                     "cache_creation_input_tokens": 50}),
        anthropic_reply(OBSERVED, {"input_tokens": 1300, "output_tokens": 210,
                                   "cache_read_input_tokens": 400})])
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key")
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: next(replies))
    pack, log, cost = compact_with_repair_measured("# Skill", provider="anthropic")
    assert pack == OBSERVED and len(log) == 1
    assert cost.measured
    assert (cost.input_tokens, cost.output_tokens, cost.cached_input_tokens) == \
        (1000 + 50 + 1300, 200 + 210, 400)


def test_azure_usage_is_reported_in_the_anthropic_shape(monkeypatch):
    from skillc.frontend.llm import metered

    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "not-a-real-key")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-demo")
    monkeypatch.delenv("AZURE_OPENAI_API_VERSION", raising=False)
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: Response(json.dumps({
        "choices": [{"message": {"content": json.dumps(PACK)}}],
        "usage": {"prompt_tokens": 900, "completion_tokens": 120,
                  "prompt_tokens_details": {"cached_tokens": 300}}}).encode()))
    with metered() as usage:
        compact("# Skill", provider="azure-openai")
    assert usage == [{"input_tokens": 600, "output_tokens": 120,
                      "cache_read_input_tokens": 300}]


def test_cost_command_reports_measured_only_for_reported_usage(tmp_path, capsys,
                                                               monkeypatch):
    from skillc.cli import main

    skill = tmp_path / "SKILL.md"
    skill.write_text("# Skill\nWrite the report.\n")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key")
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: anthropic_reply(
        PACK, {"input_tokens": 1500, "output_tokens": 300}))
    assert main(["cost", str(skill), "--llm", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["front_end"] == "LLM compaction (measured)"
    assert out["not_refuted"][0]["verification_tokens"] == 1800

    assert main(["cost", str(skill), "--price-llm", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["front_end"] == "LLM compaction (modelled)"

def test_environment_vocabulary_is_given_to_the_compactor_without_contracts(monkeypatch):
    seen = {}

    def fake_complete(provider, system, user, model, timeout, **kwargs):
        seen["system"] = system
        return json.dumps(PACK)

    monkeypatch.setattr("skillc.frontend.providers.complete", fake_complete)
    vocabulary = {
        "tools": {"book_fare": "books a fare costing at least 800"},
        "states": {"booked": "a fare is booked", "price": "fare price"},
        "contracts": {"book_fare": {"nondet": {"price": {"cmp": ["price", ">=", 800]}}}},
    }

    compact("# Skill", provider="anthropic", vocabulary=vocabulary)

    assert "book_fare" in seen["system"] and "booked" in seen["system"]
    assert "price" in seen["system"]
    assert "800" not in seen["system"]

def test_verdict_explanation_is_plain_text_grounded_in_the_checker_result(monkeypatch):
    seen = {}

    def fake_complete(provider, system, user, model, timeout, json_mode=True):
        seen.update(system=system, user=user, json_mode=json_mode)
        return "  The booking tool only sells fares of 800 or more.  "

    monkeypatch.setattr("skillc.frontend.providers.complete", fake_complete)
    from skillc.frontend.llm import explain_verdict

    verdict = {"verdict": "IMPOSSIBLE", "reason": "GOAL_UNSAT",
               "detail": "goal unsatisfiable", "frontier": ["price"], "witness": []}
    text = explain_verdict("Book a fare under 500.", verdict,
                           goal={"cmp": ["price", "<", 500]},
                           environment={"unavailable": [], "contracts_applied": ["book_fare"]},
                           provider="azure-openai", model="m")

    assert text == "The booking tool only sells fares of 800 or more."
    assert seen["json_mode"] is False
    assert "GOAL_UNSAT" in seen["user"] and "price" in seen["user"]
    assert "Book a fare under 500." in seen["user"]

def test_vocabulary_mode_overrides_conservative_declaration(monkeypatch):
    seen = {}

    def fake_complete(provider, system, user, model, timeout, **kwargs):
        seen["system"] = system
        return json.dumps(PACK)

    monkeypatch.setattr("skillc.frontend.providers.complete", fake_complete)
    compact("# Skill", provider="anthropic", vocabulary={"tools": {"edit": ""}, "states": {}})

    assert "Declare EVERY external operation" in seen["system"]
    assert "own work" in seen["system"]


def test_invalid_pack_is_repaired_once_with_the_validation_error(monkeypatch):
    replies = iter([json.dumps({"name": "x"}), json.dumps(PACK)])
    users = []

    def fake_complete(provider, system, user, model, timeout, **kwargs):
        users.append(user)
        return next(replies)

    monkeypatch.setattr("skillc.frontend.providers.complete", fake_complete)

    assert compact("# Skill", provider="anthropic") == PACK
    assert len(users) == 2 and "failed validation" in users[1]

"""Contract test for the Decision-model client (stubbed HTTP, no network)."""

from __future__ import annotations

import io
import json
import urllib.error

import pytest

from skillc.frontend import providers


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


QUESTIONS = {
    "q1": {"type": "noul", "instructions": "Is X true?",
           "criteria": {"true": "X holds", "false": "X does not hold"}},
    "q2": {"type": "choice", "instructions": "Which?",
           "criteria": {"optA": "the first", "optB": "the second"}},
}
REPLY = {"model": "microsoft-decision-1",
         "answers": {"q1": {"type": "noul", "noul": 0.85},
                     "q2": {"type": "choice", "choice": "optA", "confidence": 0.98,
                            "probabilities": {"optA": 0.985, "optB": 0.011}}},
         "usage": {"input_tokens": 128, "output_tokens": 2}}


def test_decision_request_and_reply(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout):
        seen["url"] = req.full_url
        seen["headers"] = dict(req.header_items())
        seen["body"] = json.loads(req.data)
        seen["timeout"] = timeout
        return Response(json.dumps(REPLY).encode())

    monkeypatch.setenv("AZURE_DECISION_API_KEY", "not-a-real-key")
    monkeypatch.delenv("AZURE_DECISION_ENDPOINT", raising=False)
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with providers.metered() as usage:
        out = providers.decision({"document": "doc"}, QUESTIONS, timeout=7)

    assert seen["url"] == ("https://foundary-tzuc06.services.ai.azure.com"
                           "/providers/microsoft/v1/systemone")
    assert seen["headers"]["Api-key"] == "not-a-real-key"
    assert seen["headers"]["Content-type"] == "application/json"
    assert seen["body"] == {"model": "Decision-1", "state": {"document": "doc"},
                            "questions": QUESTIONS}
    assert seen["timeout"] == 7
    assert out["answers"]["q1"]["noul"] == 0.85
    assert out["answers"]["q2"]["choice"] == "optA"
    assert usage == [{"input_tokens": 128, "output_tokens": 2,
                      "cache_read_input_tokens": 0}]


def test_decision_bearer_token_and_endpoint(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout):
        seen["url"] = req.full_url
        seen["headers"] = dict(req.header_items())
        return Response(json.dumps(REPLY).encode())

    monkeypatch.delenv("AZURE_DECISION_API_KEY", raising=False)
    monkeypatch.setattr(providers, "azure_cli_token", lambda: "tok")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    providers.decision("text state", QUESTIONS, model="Other",
                       endpoint="https://x.services.ai.azure.com/")
    assert seen["url"] == "https://x.services.ai.azure.com/providers/microsoft/v1/systemone"
    assert seen["headers"]["Authorization"] == "Bearer tok"


def test_decision_http_error(monkeypatch):
    def fake_urlopen(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {},
                                     io.BytesIO(b'{"error": "rate"}'))

    monkeypatch.setenv("AZURE_DECISION_API_KEY", "k")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with pytest.raises(providers.DecisionError) as e:
        providers.decision("s", QUESTIONS)
    assert e.value.status == 429

import os
import socket
import subprocess

import pytest

from conftest import LIVE, SandboxNetworkError
from skillc.frontend import providers

pytestmark = pytest.mark.skipif(LIVE, reason="the sandbox is off for live runs")


def test_outside_connections_are_refused():
    with pytest.raises(SandboxNetworkError):
        socket.create_connection(("192.0.2.1", 443), timeout=1)
    s = socket.socket()
    try:
        with pytest.raises(SandboxNetworkError):
            s.connect(("192.0.2.1", 443))
    finally:
        s.close()


def test_azure_cli_cannot_run():
    with pytest.raises(SandboxNetworkError):
        subprocess.run(["az", "account", "get-access-token"], capture_output=True)


def test_credentials_are_removed():
    for name in ("AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT", "ANTHROPIC_API_KEY"):
        assert name not in os.environ


def test_model_calls_need_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("SKILLC_ALLOW_MODEL_CALLS")
    with pytest.raises(providers.ModelCallsDisabled):
        providers.azure_openai_complete("s", "u", "gpt-5.4", 5)
    with pytest.raises(providers.ModelCallsDisabled):
        providers.anthropic_complete("s", "u", "m", 5)
    with pytest.raises(providers.ModelCallsDisabled):
        providers.decision("state", {})

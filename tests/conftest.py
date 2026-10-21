"""Tests run in a sandbox: nothing here can reach a real service.

* Every socket connection to a non-loopback address is refused, so no test can
  call a model, an Azure resource or any other host. Model clients are tested
  against stubs. The only way out is SKILLC_LIVE_LLM=1, set by hand for the
  opt-in live tests.
* Azure / Anthropic credentials are removed from the environment, so no test
  can fetch a token or use a key by accident.
* SKILLC_ALLOW_MODEL_CALLS is set because the network block above already
  makes every model call go to a stub; outside tests that switch stays off.
"""
from __future__ import annotations

import ipaddress
import os
import socket
import subprocess
from pathlib import Path

import pytest

LIVE = os.environ.get("SKILLC_LIVE_LLM") == "1"
_SECRET_VARS = ("AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT", "AZURE_DECISION_API_KEY",
                "AZURE_DECISION_ENDPOINT", "ANTHROPIC_API_KEY", "AZURE_SUBSCRIPTION_ID",
                "AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET")


class SandboxNetworkError(OSError):
    """A test tried to reach a host outside this machine."""


def _loopback(address) -> bool:
    host = address[0] if isinstance(address, tuple) else address
    if not isinstance(host, str):
        return True          # AF_UNIX and friends
    if host in ("localhost", ""):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        pass
    # A name: allowed only if every address it resolves to is loopback (tests map
    # made-up names to a local server by patching getaddrinfo).
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    return bool(infos) and all(ipaddress.ip_address(i[4][0]).is_loopback for i in infos)


@pytest.fixture(autouse=True)
def _sandbox(monkeypatch):
    if LIVE:
        yield
        return
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def connect(self, address):
        if not _loopback(address):
            raise SandboxNetworkError(f"sandbox: tests may not connect to {address!r}")
        return real_connect(self, address)

    def connect_ex(self, address):
        if not _loopback(address):
            raise SandboxNetworkError(f"sandbox: tests may not connect to {address!r}")
        return real_connect_ex(self, address)

    def create_connection(address, *args, **kwargs):
        if not _loopback(address):
            raise SandboxNetworkError(f"sandbox: tests may not connect to {address!r}")
        return _real_create_connection(address, *args, **kwargs)

    _real_create_connection = socket.create_connection
    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "create_connection", create_connection)
    real_popen_init = subprocess.Popen.__init__

    def popen_init(self, args, *a, **kw):
        first = args if isinstance(args, str) else (args[0] if args else "")
        exe = Path(str(first).split()[0] if isinstance(args, str) else str(first)).name.lower()
        if exe in ("az", "az.cmd", "az.exe", "az.bat", "azd", "azd.exe", "curl", "wget"):
            raise SandboxNetworkError(f"sandbox: tests may not run {exe!r}")
        return real_popen_init(self, args, *a, **kw)

    monkeypatch.setattr(subprocess.Popen, "__init__", popen_init)
    for name in _SECRET_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SKILLC_ALLOW_MODEL_CALLS", "1")
    yield

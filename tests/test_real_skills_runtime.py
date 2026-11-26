import base64
import contextlib
import io
import json
import os
import subprocess
import time

import pytest

from scripts.real_skills_runtime import Sandbox, ToolServer
from skillc.frontend.urlguard import assert_clean, restore


def server(tmp_path):
    replacements = tmp_path / "replacements.json"
    replacements.write_text(json.dumps({"[url-1]": "https://first.example.org"}))
    return ToolServer({
        "docker_host": "unused", "container": "a" * 64,
        "events": str(tmp_path / "tools.jsonl"), "deadline": time.time() + 60,
        "max_calls": 1,
    }, replacements)


def test_tool_results_scrub_all_text_and_preserve_trial_mapping(tmp_path, monkeypatch):
    tool = server(tmp_path)
    code = []

    def execute(value, **kwargs):
        code.append(value)
        return {"status": "completed", "exit_code": 0,
                "output": "https://first.example.org https://second.example.org"}

    monkeypatch.setattr(tool.sandbox, "execute", execute)
    result = tool.dispatch("tools/call", {
        "name": "execute_python", "arguments": {"code": "print('[url-1]')"}})
    assert code == ["print('https://first.example.org')"]
    assert_clean(json.dumps(result))
    table = json.loads(tool.replacements.read_text())
    assert table["[url-1]"] == "https://first.example.org"
    assert table["[url-2]"] == "https://second.example.org"
    assert "https://second.example.org" in restore(result["content"][0]["text"], table)
    exhausted = tool.dispatch("tools/call", {
        "name": "execute_python", "arguments": {"code": "print(2)"}})
    assert exhausted["isError"]
    assert len(code) == 1
    assert "budget_exhausted" in exhausted["content"][0]["text"]
    assert json.loads(exhausted["content"][0]["text"])["reason"] == "tool_call_limit"


def test_tool_rejects_host_controls_and_expired_deadline(tmp_path, monkeypatch):
    tool = server(tmp_path)
    with pytest.raises(ValueError, match="one bounded code"):
        tool.dispatch("tools/call", {
            "name": "execute_python", "arguments": {"code": "", "container": "other"}})
    tool.deadline = 0
    monkeypatch.setattr(tool.sandbox, "execute",
                        lambda *a, **k: pytest.fail("Expired tool must not execute"))
    result = tool.dispatch("tools/call", {
        "name": "execute_python", "arguments": {"code": "print(1)"}})
    assert result["isError"]
    assert json.loads(result["content"][0]["text"])["reason"] == "execution_deadline"


def test_sandbox_rejects_non_owned_container_and_unsafe_input_paths():
    with pytest.raises(ValueError, match="exact owned"):
        Sandbox("unused", "all")
    sandbox = Sandbox("unused")
    with pytest.raises(ValueError, match="named task"):
        sandbox.start({"../outside.py": b""}, [])


@pytest.mark.parametrize("path", [
    "/etc/passwd", "/work/../inputs/private.json", "/inputs/../work/out.json",
    "/work/nested/out.json", "/work/..", "/inputs/.env",
])
def test_snapshot_rejects_non_task_paths_before_invoking_docker(path, monkeypatch):
    sandbox = Sandbox("unused", "a" * 64)
    monkeypatch.setattr(sandbox, "execute", lambda *a, **k: pytest.fail("Unsafe snapshot path"))
    with pytest.raises(ValueError, match="Unknown task target"):
        sandbox.read(path)


def test_snapshot_accepts_json_deliverables_as_data(monkeypatch):
    sandbox = Sandbox("unused", "a" * 64)
    payload = b'{"a": 1}'
    monkeypatch.setattr(sandbox, "execute", lambda *a, **k: {
        "status": "completed", "exit_code": 0,
        "output": json.dumps({"data": base64.b64encode(payload).decode()}),
    })
    assert sandbox.read("/work/mutation-summary.json") == payload


def test_sandbox_server_cannot_restart_and_reset_the_trial_budget(tmp_path):
    server(tmp_path)
    with pytest.raises(RuntimeError, match="restart refused"):
        server(tmp_path)


def test_tool_timeout_uses_the_remaining_trial_deadline(tmp_path, monkeypatch):
    tool = server(tmp_path)
    tool.deadline = time.time() + 10
    timeouts = []

    def execute(code, *, timeout):
        timeouts.append(timeout)
        return {"status": "tool_timeout", "exit_code": None, "output": ""}

    monkeypatch.setattr(tool.sandbox, "execute", execute)
    result = tool.dispatch("tools/call", {
        "name": "execute_python", "arguments": {"code": "pass"}})
    assert 0 < timeouts[0] <= 10
    assert json.loads(result["content"][0]["text"])["reason"] == "execution_deadline"


@pytest.mark.parametrize("error", ["FileNotFoundError", "IsADirectoryError", "PermissionError"])
def test_snapshot_identifies_unavailable_deliverable_not_infrastructure(
        tmp_path, monkeypatch, error):
    sandbox = Sandbox("unused", "a" * 64)
    monkeypatch.setattr(sandbox, "execute", lambda *a, **k: {
        "status": "completed", "exit_code": 0, "output": json.dumps({"error": error}),
    })
    with pytest.raises(RuntimeError, match=error) as caught:
        sandbox.read("/work/textmask.py")
    assert type(caught.value).__name__ == "DeliverableUnavailable"


def test_snapshot_decodes_actual_bytes_but_keeps_docker_failures_explicit(monkeypatch):
    sandbox = Sandbox("unused", "a" * 64)
    result = {"status": "completed", "exit_code": 0, "output": json.dumps({
        "data": base64.b64encode(b"actual bytes").decode(),
    })}
    monkeypatch.setattr(sandbox, "execute", lambda *a, **k: result)
    assert sandbox.read("/work/textmask.py") == b"actual bytes"
    result.update(exit_code=125, output="Docker unavailable")
    with pytest.raises(RuntimeError, match="Could not snapshot"):
        sandbox.read("/work/textmask.py")


def test_snapshot_program_reads_files_without_executing_their_contents(tmp_path, monkeypatch):
    target = tmp_path / "target.py"
    sandbox = Sandbox("unused", "a" * 64)

    def execute(code):
        code = code.replace(repr("/work/textmask.py"), repr(str(target)))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exec(code, {})
        return {"status": "completed", "exit_code": 0, "output": output.getvalue()}

    monkeypatch.setattr(sandbox, "execute", execute)
    with pytest.raises(RuntimeError, match="FileNotFoundError"):
        sandbox.read("/work/textmask.py")
    target.write_bytes(b"raise AssertionError('data must not execute')")
    assert sandbox.read("/work/textmask.py") == target.read_bytes()


@pytest.mark.parametrize("packages", [False, True])
def test_pinned_package_runtime_survives_tool_server_handoff(tmp_path, monkeypatch, packages):
    commands = []
    image = "sha256:" + "b" * 64

    def start(command, **kwargs):
        commands.append(command)
        return "a" * 64

    monkeypatch.setattr("scripts.real_skills_runtime.subprocess.check_output", start)
    sandbox = Sandbox("unused", image=image, site_packages=packages)
    with monkeypatch.context() as setup:
        setup.setattr(sandbox, "execute", lambda *a, **k: {
            "status": "completed", "exit_code": 0, "output": ""})
        sandbox.start({}, [])
    assert commands[0][commands[0].index(image) + 1] == "python"
    assert ("-S" not in commands[0]) is packages
    assert commands[0][commands[0].index("--network") + 1] == "none"
    assert "--read-only" in commands[0]

    class Process:
        stdout = io.BytesIO(b"actual child output\n")
        returncode = 0

        def poll(self):
            return self.returncode

        def wait(self, **kwargs):
            return self.returncode

    def execute(command, **kwargs):
        commands.append(command)
        return Process()

    monkeypatch.setattr("scripts.real_skills_runtime.subprocess.Popen", execute)
    replacements = tmp_path / "mapping.json"
    replacements.write_text("{}")
    tool = ToolServer({
        "docker_host": "unused", "container": sandbox.container,
        "image": image, "site_packages": packages,
        "events": str(tmp_path / "events.jsonl"), "deadline": time.time() + 60,
        "max_calls": 1,
    }, replacements)
    result = tool.dispatch("tools/call", {
        "name": "execute_python", "arguments": {"code": "import sympy"}})
    assert not result["isError"]
    assert "actual child output" in result["content"][0]["text"]
    assert ("-S" not in commands[1]) is packages
    assert "-I" in commands[1] and "-B" in commands[1]


@pytest.mark.parametrize("options", [
    {"image": "python:latest"}, {"image": "sha256:short"}, {"site_packages": "yes"},
])
def test_package_runtime_rejects_unpinned_images_and_non_boolean_policy(options):
    with pytest.raises(ValueError, match="immutable image|boolean"):
        Sandbox("unused", **options)


def test_actual_symbolic_image_keeps_isolation_and_protected_inputs(tmp_path):
    image = os.environ.get("SKILLC_SYMBOLIC_IMAGE")
    if os.environ.get("SKILLC_LOCAL_DOCKER") != "1" or not image:
        pytest.skip("Requires explicit local Docker and immutable symbolic-image opt-ins")
    host = subprocess.check_output(
        ["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"],
        text=True).strip()
    assert host.startswith(("npipe:////./pipe/", "unix:///"))
    sandbox = Sandbox(host, image=image, site_packages=True)
    try:
        sandbox.start({"probe.txt": b"unchanged\n"}, [])
        config = json.loads(subprocess.check_output(sandbox.docker(
            "inspect", "--format", "{{json .HostConfig}}", sandbox.container), text=True))
        assert config["NetworkMode"] == "none" and config["ReadonlyRootfs"]
        assert not config["Binds"] and config["CapDrop"] == ["ALL"]
        assert config["NanoCpus"] == 500000000 and config["PidsLimit"] == 32
        assert config["Memory"] == config["MemorySwap"] == 134217728
        assert "no-new-privileges" in config["SecurityOpt"]
        replacements = tmp_path / "mapping.json"
        replacements.write_text("{}")
        tool = ToolServer({
            "docker_host": host, "container": sandbox.container,
            "image": image, "site_packages": True,
            "events": str(tmp_path / "events.jsonl"), "deadline": time.time() + 60,
            "max_calls": 1,
        }, replacements)
        code = """
import json,os,site,sys,mpmath,sympy
from pathlib import Path
assert Path('/inputs/probe.txt').read_bytes() == b'unchanged\\n'
try:
    Path('/inputs/probe.txt').write_text('changed')
except PermissionError:
    refused = True
else:
    refused = False
x = sympy.Symbol('x')
print(json.dumps({'sympy':sympy.__version__, 'mpmath':mpmath.__version__,
    'roots':{str(k):int(v) for k,v in sympy.roots(x**3-6*x**2+9*x,x).items()},
    'uid':os.geteuid(), 'isolated':sys.flags.isolated, 'no_site':sys.flags.no_site,
    'user_site_enabled':site.ENABLE_USER_SITE, 'protected_write_refused':refused}))
"""
        result = tool.dispatch("tools/call", {
            "name": "execute_python", "arguments": {"code": code}})
        assert not result["isError"], result
        observed = json.loads(json.loads(result["content"][0]["text"])["output"])
        assert observed == {
            "sympy": "1.14.0", "mpmath": "1.3.0", "roots": {"0": 1, "3": 2},
            "uid": 65534, "isolated": 1, "no_site": 0,
            "user_site_enabled": False, "protected_write_refused": True,
        }
        assert sandbox.read("/inputs/probe.txt") == b"unchanged\n"
        assert json.loads(tool.events.read_text().splitlines()[0])["credential_environment_present"] is False
        print(json.dumps({"image": image, "actual_runtime": observed}, sort_keys=True))
    finally:
        sandbox.stop()

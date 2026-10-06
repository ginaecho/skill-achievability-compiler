"""Regression tests for the Copilot review findings on the eag-innovation PR."""
import importlib.util
import json
import socket
import ssl
import urllib.request
import sys
from pathlib import Path

import pytest

from skillc import Verdict
from skillc.env import mcp
from skillc.env.model import Environment
from skillc.env.watch import LATEST, watch_once
from skillc.frontend.contracts import apply_contracts

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_report_cell_keeps_unknown_distinct_from_impossible():
    from scripts.make_report import verdict_cell

    assert verdict_cell(Verdict(achievable=False, unknown=True)) == "UNKNOWN"
    assert verdict_cell(Verdict(achievable=False, frontier=("x",))) == "IMPOSSIBLE (`x`)"
    assert verdict_cell(Verdict(achievable=True)) == "ACHIEVABLE"


def test_benchmark_verifier_fails_explicitly_not_by_assert(tmp_path):
    from scripts.verify_compaction_benchmark import VerificationError, verify

    (tmp_path / "frozen.json").write_text(json.dumps({"scenarios": []}))
    (tmp_path / "results.json").write_text(json.dumps([{"id": "x"}]))
    (tmp_path / "metrics.json").write_text("{}")
    (tmp_path / "calls.jsonl").write_text("")
    with pytest.raises(VerificationError):
        verify(tmp_path)
    assert not (tmp_path / "verification.json").exists()


def test_contracts_keep_an_ownerless_capability_ownerless():
    pack = {"name": "t", "roles": ["agent"],
            "capabilities": {"book": {"add": ["booked"]}},
            "protocol": [{"act": {"cap": "book", "by": "agent"}}], "goal": "booked"}

    binding = apply_contracts(pack, {"book": {"add": ["booked"]}}, {"booked": ""})

    assert binding.applied == ("book",)
    assert "owner" not in binding.pack["capabilities"]["book"]


def test_app_rejects_json_that_is_not_an_object():
    app_dir = ROOT / "demo" / "skillc-architecture-app"
    sys.path.insert(0, str(app_dir))
    app = _load("atlas_app_review", app_dir / "app.py")

    for body in (b"[]", b'"text"', b"3"):
        with pytest.raises(ValueError, match="JSON object"):
            app.parse_json_object(body)
    assert app.parse_json_object(b'{"a": 1}') == {"a": 1}


@pytest.mark.parametrize("config", [[], {"mcpServers": []}, {"projects": []},
                                    {"projects": {"p": []}}, {"servers": "x"}])
def test_malformed_mcp_config_is_recorded_as_unknown(tmp_path, config):
    path = tmp_path / ".mcp.json"
    path.write_text(json.dumps(config))

    env = mcp.probe([path])

    assert env.is_unknown(f"mcp_config:{path}")


@pytest.mark.parametrize("content", ["{not json", "[]", '{"schema": "other"}'])
def test_watch_repairs_an_invalid_latest_snapshot(tmp_path, content):
    (tmp_path / LATEST).write_text(content)

    report = watch_once(tmp_path, Environment, {})

    assert report["environment_changes"] is None
    Environment.load(tmp_path / LATEST)

def _catalog_module():
    app_dir = ROOT / "demo" / "skillc-architecture-app"
    sys.path.insert(0, str(app_dir))
    return _load("intent_catalog_review", app_dir / "intent_catalog.py")


def _git(cwd: Path, *args: str) -> None:
    import subprocess
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                   cwd=cwd, check=True, capture_output=True)


def test_catalog_branch_reader_resolves_paths_from_a_vendored_subfolder(tmp_path):
    catalog = _catalog_module()
    vendored = tmp_path / "agentic-governance" / "skillc"
    topic = vendored / catalog.TOPICS_DIR / "pay"
    topic.mkdir(parents=True)
    (topic / "topic.json").write_text(json.dumps({"title": "Pay", "category": "C"}))
    (topic / "environment.json").write_text(json.dumps({"tools": {"pay": "pays"}}))
    for name in catalog.FORM_FILES.values():
        (topic / name).write_text(name)
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "data")
    _git(tmp_path, "update-ref", f"refs/remotes/origin/{catalog.CATALOG_BRANCH}", "HEAD")

    read, list_topics = catalog._branch_reader(vendored)
    entries = catalog._topic_entries(read, list_topics())

    assert [entry["content"] for entry in entries] == list(catalog.FORM_FILES.values())


def test_catalog_without_data_branch_is_empty_with_a_hint(tmp_path):
    catalog = _catalog_module()
    _git(tmp_path, "init", "-q")

    result = catalog.load_catalog(tmp_path)

    assert result["count"] == 0
    assert "--catalog-root" in result["hint"]


def test_catalog_unreadable_topic_file_raises_a_clear_error(tmp_path):
    catalog = _catalog_module()
    read, _ = catalog._branch_reader(tmp_path)

    with pytest.raises(catalog.CatalogError, match="--catalog-root"):
        read("corpus/intents/missing/topic.json")


def test_mcp_snapshot_keeps_no_command_arguments_or_url_secrets(tmp_path):
    path = tmp_path / ".mcp.json"
    path.write_text(json.dumps({"mcpServers": {
        "local": {"command": "/usr/bin/npx", "args": ["server", "--api-key", "sk-SECRET"]},
        "remote": {"type": "http", "url": "https://user:pw@example.com/mcp?token=SECRET#x"},
    }}))

    env = mcp.probe([path])
    snapshot = json.dumps(env.to_dict())

    assert "SECRET" not in snapshot and "pw@" not in snapshot
    servers = {node["name"]: node["attrs"] for node in env.of_kind("mcp_server")}
    assert servers["local"]["command"] == "npx"
    assert servers["local"]["arg_count"] == 3
    assert servers["remote"]["url"] == "https://example.com/mcp"


def _refutation(reason: str, frontier: tuple) -> Verdict:
    return Verdict(achievable=False, reason=reason, frontier=frontier)


def test_empty_state_vocabulary_grounds_no_condition():
    from skillc.frontend.contracts import abstain_ungrounded

    verdict = abstain_ungrounded(_refutation("GOAL_UNSAT", ("approved",)),
                                 states={}, source_text="Get it approved, then publish.")

    assert verdict.label == "UNKNOWN" and verdict.reason == "UNALIGNED_CONDITION"


def test_grounding_matches_whole_identifiers_not_substrings():
    from skillc.frontend.contracts import abstain_ungrounded

    invented = abstain_ungrounded(_refutation("MISSING_CAPABILITY", ("read",)),
                                  source_text="Update the spreadsheet.")
    named = abstain_ungrounded(_refutation("MISSING_CAPABILITY", ("read",)),
                               source_text="Use `read` on the spreadsheet.")

    assert invented.label == "UNKNOWN"
    assert named.label == "IMPOSSIBLE"


def _transcript(path: Path, thought: str) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"message": {"role": "assistant", "content": [
            {"type": "thinking", "thinking": thought}]}}) + "\n")


def test_monitor_hook_reads_each_session_transcript_from_its_own_offset(tmp_path, monkeypatch):
    from skillc import monitor_hook
    from skillc.monitor import ALLOW, Decision

    seen = []

    def observe(self, text):
        seen.append(text)
        return Decision(ALLOW)

    monkeypatch.setattr(monitor_hook.Monitor, "observe_thinking", observe)
    monkeypatch.setattr(monitor_hook.Monitor, "pre_action",
                        lambda self, tool, tool_input: Decision(ALLOW))
    import subprocess
    subprocess.run([sys.executable, "-m", "skillc.cli", "monitor", "init", "--root",
                    str(tmp_path)], check=True, capture_output=True,
                   env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")})
    long_t, short_t = tmp_path / "long.jsonl", tmp_path / "short.jsonl"
    _transcript(long_t, "first session " + "x" * 2000)
    _transcript(short_t, "second session plan")

    for sid, path in (("s1", long_t), ("s2", short_t)):
        monitor_hook.handle("pre", {"session_id": sid, "cwd": str(tmp_path),
                                    "transcript_path": str(path), "tool_name": "Bash",
                                    "tool_input": {"command": "ls"}})

    assert "second session plan" in seen[1]


def test_transcript_reader_restarts_after_truncation(tmp_path):
    from skillc.monitor import thinking_since

    path = tmp_path / "t.jsonl"
    _transcript(path, "x" * 500)
    _, offset = thinking_since(path, 0)
    path.write_text("")
    _transcript(path, "fresh")

    text, _ = thinking_since(path, offset)

    assert text == "fresh"


@pytest.mark.parametrize("spec", [{"command": "npx", "args": 1}, {"command": "npx", "env": "x"},
                                  {"command": 3}, {"type": "http", "url": "https://h:99999/x"},
                                  {"type": "http", "url": 5}])
def test_malformed_mcp_server_is_unknown_and_others_still_probed(tmp_path, spec):
    path = tmp_path / ".mcp.json"
    path.write_text(json.dumps({"mcpServers": {"bad": spec, "good": {"command": "npx"}}}))

    env = mcp.probe([path])

    assert env.is_unknown("mcp_server:bad")
    assert [node["name"] for node in env.of_kind("mcp_server")] == ["good"]


ALLOWED = frozenset({"127.0.0.1:8765", "localhost:8765"})


@pytest.mark.parametrize("headers, rejected", [
    ({"Content-Type": "text/plain", "Host": "127.0.0.1:8765"}, True),
    ({"Content-Type": "application/json", "Host": "evil.example:8765"}, True),
    ({"Content-Type": "application/json", "Host": "127.0.0.1:8765",
      "Origin": "https://evil.example"}, True),
    ({"Content-Type": "application/json; charset=utf-8", "Host": "127.0.0.1:8765",
      "Origin": "http://127.0.0.1:8765"}, False),
    ({"Content-Type": "application/json", "Host": "localhost:8765"}, False),
])
def test_app_post_requires_json_and_a_trusted_origin(headers, rejected):
    app_dir = ROOT / "demo" / "skillc-architecture-app"
    sys.path.insert(0, str(app_dir))
    app = _load("atlas_app_csrf", app_dir / "app.py")

    assert (app.post_rejection(headers, ALLOWED) is not None) is rejected


@pytest.mark.parametrize("host, address", [
    ("10.0.0.5", "10.0.0.5"), ("internal.example", "192.168.1.10"),
    ("meta.example", "169.254.169.254"), ("loop.example", "127.0.0.1"),
    ("v6.example", "::1"),
])
def test_egress_refuses_non_public_destinations(monkeypatch, host, address):
    from skillc.env import claude

    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    monkeypatch.setattr(claude.socket, "getaddrinfo",
                        lambda *a, **k: [(family, socket.SOCK_STREAM, 6, "", (address, 443))])
    monkeypatch.setattr(claude, "_open", lambda *a, **k: pytest.fail("request was sent"))

    ok, why = claude.egress(host)

    assert ok is False and "non-public" in why


def test_egress_does_not_follow_redirects():
    from skillc.env import claude

    opener = claude._opener(ssl.create_default_context())
    redirect = next(h for h in opener.handlers
                    if isinstance(h, urllib.request.HTTPRedirectHandler))

    assert redirect.redirect_request(None, None, 302, "Found", {}, "http://10.0.0.1/") is None


def test_numeric_only_guard_is_grounded_by_its_variables():
    from skillc.frontend.contracts import abstain_ungrounded

    pack = {"capabilities": {"buy": {"pre": {"cmp": ["price", "<", 500]}}}}
    blocked = _refutation("BLOCKED_GUARD", ("capability 'buy' guard never satisfiable",))

    invented = abstain_ungrounded(blocked, states={"booked": ""}, pack=pack)
    published = abstain_ungrounded(blocked, states={"price": ""}, pack=pack)

    assert invented.label == "UNKNOWN"
    assert published.label == "IMPOSSIBLE"


def test_goal_unsat_without_frontier_is_grounded_by_goal_variables():
    from skillc.frontend.contracts import abstain_ungrounded

    pack = {"goal": {"and": ["booked", {"cmp": ["refund_total", "<", 0]}]}}
    unsat = _refutation("GOAL_UNSAT", ())

    invented = abstain_ungrounded(unsat, states={"paid": ""}, pack=pack)
    published = abstain_ungrounded(unsat, states={"refund_total": ""}, pack=pack)
    from_text = abstain_ungrounded(unsat, source_text="Keep the refund_total low.", pack=pack)

    assert invented.label == "UNKNOWN"
    assert published.label == "IMPOSSIBLE"
    assert from_text.label == "IMPOSSIBLE"


@pytest.mark.parametrize("profile", [
    [], {"tools": ["bash"]}, {"name": "", "tools": []}, {"name": "p", "tools": "bash"},
    {"name": "p", "tools": ["bash", ""]}, {"name": "p", "tools": [1]},
    {"name": "p", "shell": "false"}, {"name": "p", "description": 3},
])
def test_profile_with_malformed_fields_is_rejected(tmp_path, profile):
    from skillc.profiles import ProfileError, load_profile

    path = tmp_path / "bad.json"
    path.write_text(json.dumps(profile))

    with pytest.raises(ProfileError):
        load_profile(str(path))


def test_well_formed_profile_still_loads(tmp_path):
    from skillc.profiles import load_profile

    path = tmp_path / "ok.json"
    path.write_text(json.dumps({"name": "p", "tools": ["Bash(git:*)"], "shell": True}))

    profile = load_profile(str(path))

    assert profile.tools == frozenset({"bash"}) and profile.shell is True


def test_parallel_hooks_do_not_lose_state_updates(tmp_path, monkeypatch):
    import os
    import subprocess
    import threading
    import time

    from skillc import monitor_hook

    subprocess.run([sys.executable, "-m", "skillc.cli", "monitor", "init", "--root",
                    str(tmp_path)], check=True, capture_output=True,
                   env={**os.environ, "PYTHONPATH": str(ROOT / "src")})

    def slow_post(mon, event):
        mon.state.log.append({"signal": event["marker"]})
        time.sleep(0.3)

    monkeypatch.setitem(monitor_hook._HANDLERS, "post", slow_post)
    threads = [threading.Thread(target=monitor_hook.handle,
                                args=("post", {"cwd": str(tmp_path), "marker": m}))
               for m in ("a", "b")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    state = json.loads(next((tmp_path / ".skillc").glob("state*.json")).read_text())
    assert sorted(entry["signal"] for entry in state["log"]) == ["a", "b"]


def test_monitor_state_is_written_atomically(tmp_path, monkeypatch):
    import os

    from skillc import monitor as monitor_module

    replaced = []
    real_replace = os.replace
    monkeypatch.setattr(monitor_module.os, "replace",
                        lambda src, dst: replaced.append(Path(dst).name) or real_replace(src, dst))
    mon = monitor_module.Monitor(monitor_module.Config(), tmp_path)

    mon.save()

    assert replaced == [mon.state_path.name]


def test_free_tools_still_respect_the_runtime_and_prohibitions(tmp_path):
    from skillc.monitor import ALLOW, DENY, Config, Monitor, Rule

    offline = Monitor(Config(runtime="offline-workstation"), tmp_path)
    assert offline.pre_action("WebSearch", {"query": "release notes"}).action == DENY
    assert offline.pre_action("Read", {"file_path": "a.py"}).action == ALLOW
    assert offline.pre_action("Glob", {"pattern": "*.py"}).action == ALLOW

    guarded = Monitor(Config(runtime="office-assistant", prohibited=[
        Rule(id="secrets", description="never read secrets", pattern=r"\.env\b")]), tmp_path)
    assert guarded.pre_action("Read", {"file_path": ".env"}).action == DENY
    assert guarded.pre_action("WebSearch", {"query": "release notes"}).action == ALLOW


@pytest.mark.parametrize("field, value", [
    ("name", ""), ("description", 3), ("tools", ["bash"]), ("tools", {"bash": 1}),
    ("grants", "bash"), ("lacks", [1]), ("forbid_effects", "publishes"),
    ("software", "maybe"),
])
def test_runtime_manifest_with_malformed_fields_is_rejected(tmp_path, field, value):
    from skillc.frontend.runtime import RuntimeManifestError, load_runtime

    manifest = {"name": "r", "description": "", "tools": {"bash": "runs"},
                "grants": [], "lacks": [], field: value}
    path = tmp_path / "runtime.json"
    path.write_text(json.dumps(manifest))

    with pytest.raises(RuntimeManifestError):
        load_runtime(str(path))


def test_contract_binding_drops_init_constraints_outside_the_vocabulary():
    from skillc import check

    pack = {"name": "t", "roles": ["agent"],
            "capabilities": {"book": {"owner": "agent", "add": ["booked"]}},
            "protocol": [{"act": {"cap": "book", "by": "agent"}}], "goal": "booked",
            "init_constraints": [{"cmp": ["budget", "<", 0]}, {"cmp": ["budget", ">", 0]},
                                 {"not": "booked"}]}
    assert check(pack).label == "IMPOSSIBLE"

    binding = apply_contracts(pack, {"book": {"add": ["booked"]}}, {"booked": ""})

    assert binding.applied == ("book",)
    assert binding.pack["init_constraints"] == [{"not": "booked"}]
    assert binding.dropped == ("budget",)
    assert check(binding.pack).label == "ACHIEVABLE"


def test_transcript_reader_keeps_a_partial_trailing_record(tmp_path):
    from skillc.monitor import thinking_since

    path = tmp_path / "t.jsonl"
    record = json.dumps({"message": {"role": "assistant", "content": [
        {"type": "thinking", "thinking": "now publish the package"}]}})
    path.write_text(record[:25], encoding="utf-8")

    first, offset = thinking_since(path, 0)
    with path.open("a", encoding="utf-8") as f:
        f.write(record[25:] + "\n")
    second, _ = thinking_since(path, offset)

    assert first == "" and offset == 0
    assert second == "now publish the package"


def test_transcript_reader_accepts_a_complete_record_without_newline(tmp_path):
    from skillc.monitor import thinking_since

    path = tmp_path / "t.jsonl"
    path.write_text(json.dumps({"message": {"role": "assistant", "content": [
        {"type": "text", "text": "done"}]}}), encoding="utf-8")

    text, offset = thinking_since(path, 0)

    assert text == "done" and offset == path.stat().st_size


def _self_granting_pack(extra_init=()):
    return {"name": "t", "roles": ["agent"], "init_true": list(extra_init),
            "capabilities": {
                "grant": {"owner": "agent", "add": ["needs:cloud_account", "policy:publishes"]},
                "deploy": {"owner": "agent", "add": ["deployed"]}},
            "protocol": [{"act": {"cap": "grant", "by": "agent"}},
                         {"act": {"cap": "deploy", "by": "agent"}}],
            "goal": "deployed"}


def test_missing_resource_cannot_be_self_granted_by_the_pack():
    from skillc import check
    from skillc.frontend.runtime import Runtime, bind_runtime

    runtime = Runtime("r", "", {"bash": "runs"}, (), ())
    bindings = {"grant": {"via": "bash"},
                "deploy": {"via": "bash", "needs": ["cloud_account"]}}

    binding = bind_runtime(_self_granting_pack(["needs:cloud_account"]), bindings, runtime,
                           prune=False)

    assert binding.blocked == {"deploy": ["cloud_account"]}
    assert check(binding.pack).label == "IMPOSSIBLE"


def test_forbidden_effect_cannot_be_self_permitted_by_the_pack():
    from skillc import check
    from skillc.frontend.runtime import Runtime, bind_runtime
    from skillc.frontend.toolpolicy import load_library

    runtime = Runtime("r", "", {"bash": "runs"}, (), (), forbid_effects=("publishes",))
    bindings = {"grant": {"via": "bash"}, "deploy": {"via": "bash", "effect": "publishes"}}

    binding = bind_runtime(_self_granting_pack(["policy:publishes"]), bindings, runtime,
                           prune=False, library=load_library())

    assert "policy:publishes" in binding.blocked["deploy"]
    assert check(binding.pack).label == "IMPOSSIBLE"

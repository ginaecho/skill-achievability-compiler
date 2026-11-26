"""scripts/demo_hosts.py on fake homes, offline and with a stub model (never a real one)."""
import importlib.util
import json
from pathlib import Path

import pytest

from skillc.env import m365
from skillc.frontend import providers
from skillc.frontend.prompts import ce_runtime_messages
from skillc.frontend.runtime import Runtime, load_runtime
from skillc.frontend.urlguard import assert_clean

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts" / "demo_hosts.py"
SPEC = importlib.util.spec_from_file_location("demo_hosts", PATH)
demo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(demo)

EXAMPLE = ROOT / "demo" / "skillc-here" / "skills" / "fix-failing-test.md"
PRIVATE = ("---\nname: room-helper\ndescription: book rooms\n---\n\n# Room helper\n\n"
           "Find a free room and book it. Then run `gh pr create --sentinel-xyz`.\n")
CE_OK = ("```ce\nSkill `fix-tests`.\nRoles: `agent`.\n"
         "Tool `run_tests` (owner `agent`): via `bash`; adds `tests_run`.\n"
         "Tool `edit_code` (owner `agent`): via `edit`; requires `tests_run`; adds `fixed`.\n"
         "Goal: `fixed`.\nProtocol:\n  - `agent` uses `run_tests`.\n"
         "  - `agent` uses `edit_code`.\n```\n")


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Fake Scout, Copilot and GitHub CLI homes, a fake PATH, and no overlay."""
    scout, copilot, gh = tmp_path / "scout", tmp_path / "copilot", tmp_path / "gh"
    _write(scout / "m-mcp-servers.json", {"servers": {
        "playwright": {"builtin": True, "tools": ["browser_snapshot", "browser_click"]},
        "skillc": {"builtin": False, "tools": ["skillc_start"]}}})
    _write(scout / "m-settings.json", {
        "loadCopilotCliSkills": True,
        "permissions": {"autoApproveReadOnly": True,
                        "tools": {"tool:workiq_send_email": True,
                                  "tool:workiq_list_emails": True, "tool:m_ask_user": True},
                        "servers": {"shell": {"enabled": True, "autoApprove": True},
                                    "workiq": {"enabled": True, "autoApprove": False},
                                    "playwright": {"enabled": True, "autoApprove": True},
                                    "skillc": {"enabled": True, "autoApprove": True}}}})
    (scout / "skills" / "room-helper").mkdir(parents=True)
    (scout / "skills" / "room-helper" / "SKILL.md").write_text(PRIVATE, encoding="utf-8")
    copilot.mkdir()
    gh.mkdir()
    (gh / "hosts.yml").write_text("", encoding="utf-8")
    present = {"git", "gh", "python"}
    monkeypatch.setattr(demo, "WHICH", lambda n: f"/fake/{n}" if n in present else None)
    cases = tmp_path / "cases.json"
    _write(cases, {"cases": [
        {"id": "room", "title": "Room", "skill": "scout:room-helper", "request": "Book a room."},
        {"id": "gone", "title": "Gone", "skill": "scout:not-installed", "request": "x"}],
        "examples": [{"id": "fix-failing-test", "title": "Fix",
                      "skill": "repo:demo/skillc-here/skills/fix-failing-test.md",
                      "request": "Fix the failing test."}]})
    monkeypatch.setattr(demo, "CASES_FILE", cases)
    args = ["--scout-home", str(scout), "--copilot-home", str(copilot), "--gh-config", str(gh),
            "--m365-overlay", str(tmp_path / "no-overlay.json"), "--quiet"]
    return {"tmp": tmp_path, "args": args, "scout": scout, "copilot": copilot, "gh": gh}


def _run(env, *extra):
    out = env["tmp"] / "out"
    assert demo.main(["--output", str(out), *env["args"], *extra]) == 0
    text = (out / "results.json").read_text(encoding="utf-8")
    return json.loads(text), text, out


def test_offline_results_shape(env):
    results, text, out = _run(env, "--cases", "fix-failing-test,room,gone")
    assert results["schema"] == "skillc.hosts-demo/1"
    run = results["run"]
    assert run["live"] is False and run["provider"] is None and run["max_steps"] == 6
    assert "stub" in run["stub_rules"]
    assert set(results["hosts"]) == {"copilot-cli", "scout", "m365-copilot"}
    for h in results["hosts"].values():
        assert (out / h["env_file"]).is_file() and (out / h["manifest_file"]).is_file()
        load_runtime(str(out / h["manifest_file"]))
    assert results["hosts"]["m365-copilot"]["mode"] == "declared, not probed"
    assert results["hosts"]["m365-copilot"]["monitor_replay"]["faithful"] is False
    by_id = {c["id"]: c for c in results["cases"]}
    assert by_id["gone"]["status"] == "skipped" and "not installed" in by_id["gone"]["reason"]
    for cid in ("fix-failing-test", "room"):
        c = by_id[cid]
        assert c["status"] == "ok" and len(c["sha256"]) == 64 and c["lines"] > 0 and c["bytes"]
        assert "text" not in c
        for hid in results["hosts"]:
            cell = results["cells"][cid][hid]
            assert set(cell) == {"nomodel", "compaction", "agent", "monitor", "folder"}
            assert cell["nomodel"]["model_calls"] == 0
            assert cell["nomodel"]["checker"]["verdict"] in ("ACHIEVABLE", "IMPOSSIBLE",
                                                             "UNKNOWN")
            assert cell["nomodel"]["reader"]["verdict"] in ("ACHIEVABLE", "IMPOSSIBLE")
            assert cell["compaction"] == {"ran": False, "why": demo.NOT_RUN}
            assert cell["agent"] == {"ran": False, "why": demo.NOT_RUN}
    fix = results["cells"]["fix-failing-test"]
    assert fix["copilot-cli"]["nomodel"]["checker"]["verdict"] == "ACHIEVABLE"
    assert fix["m365-copilot"]["nomodel"]["checker"]["missing"]
    assert results["totals"]["compaction"]["model_calls"] == 0
    # the installed skill: its text and evidence lines stay out of the results
    assert "sentinel-xyz" not in text and PRIVATE not in text
    assert EXAMPLE.read_text(encoding="utf-8") not in text
    witness = results["cells"]["room"]["m365-copilot"]["nomodel"]["reader"]["witness"]
    assert witness and all("sentinel" not in w for w in witness)
    report = (out / "REPORT.md").read_text(encoding="utf-8")
    assert demo.NOT_RUN in report and "declared, not probed" in report
    assert "sentinel-xyz" not in report


def test_live_refused_without_opt_in(env, monkeypatch):
    monkeypatch.delenv("SKILLC_ALLOW_MODEL_CALLS", raising=False)
    assert demo.main(["--live", "--output", str(env["tmp"] / "o"), *env["args"]]) == 2


def _stub(calls):
    """A stub model: compaction succeeds except on Scout, where it never parses; the agent
    calls an invented tool, a missing program, an outward effect, then finishes."""
    def complete(provider, system, user, model, timeout, json_mode=True, image=None):
        calls.append((system, user))
        providers._record_usage({"input_tokens": 100, "output_tokens": 20})
        if "CE document" in user or "RUNTIME `" in system:
            return "not a CE document" if "scout-desktop-observed" in system else CE_OK
        turn = json.loads(user)["turn"]
        copilot = system.startswith("You are GitHub Copilot CLI")
        shell = "powershell" if copilot else "shell"
        if turn == 1:
            return json.dumps({"tool": "made_up_tool", "args": {}, "why": "try"})
        if turn == 2:
            return json.dumps({"tool": shell, "args": {"command": "pandoc a.md -o a.docx"}})
        if turn == 3:
            if copilot:
                return json.dumps({"tool": "powershell",
                                   "args": {"command": "git push origin main"}})
            return json.dumps({"tool": "workiq_send_email", "args": {"subject": "done"}})
        return json.dumps({"finish": True, "status": "done", "message": "All done."})
    return complete


def test_live_with_stub_model(env, monkeypatch):
    calls = []
    monkeypatch.setattr(providers, "complete", _stub(calls))
    results, text, out = _run(env, "--cases", "fix-failing-test,room", "--live",
                              "--provider", "azure-openai", "--model", "stub")
    assert calls and results["run"]["live"] is True
    fix = results["cells"]["fix-failing-test"]

    comp = fix["copilot-cli"]["compaction"]
    assert comp["ok"] and comp["verdict"] == "ACHIEVABLE" and comp["ce_file"] == "compaction.ce"
    assert comp["input_tokens"] >= 100 and comp["output_tokens"] >= 20 and comp["wall_ms"] >= 0
    assert (out / fix["copilot-cli"]["folder"] / "compaction.ce").is_file()
    bad = fix["scout"]["compaction"]
    assert bad["ok"] is False and bad["verdict"] is None and bad["error"]
    assert bad["model_calls"] == 3 and bad["retries"] == 2
    m365_comp = fix["m365-copilot"]["compaction"]
    assert m365_comp["verdict"] == "IMPOSSIBLE" and "run_tests" in m365_comp["missing"]

    for hid in ("copilot-cli", "scout"):
        ag = fix[hid]["agent"]
        assert ag["attempted"] == 3 and ag["claimed_status"] == "done" and ag["error"] is None
        a0, a1, a2 = ag["actions"]
        assert a0["flags"] == ["invented_tool"] and a0["result"] == demo.STUB_NO_TOOL
        assert a1["flags"] == ["command_not_found"] and a1["result"] == demo.STUB_NOT_FOUND
        assert a2["flags"] == ["outward_effect"] and a2["result"] == demo.STUB_OK
        assert a2["outward"]["asked_user_before"] is False
        assert ag["flagged"] == 3 and ag["input_tokens"] == 400 and ag["model_calls"] == 4
    cop = fix["copilot-cli"]["agent"]["actions"][2]["outward"]
    assert cop["what"] == "shell: git push" and cop["host_runs_without_asking"] is False
    sco = fix["scout"]["agent"]["actions"][2]["outward"]
    assert sco["what"] == "tool name: send" and sco["host_runs_without_asking"] is True

    mon = fix["copilot-cli"]["monitor"]
    assert mon["replayed"] and mon["plan_decision"] == "allow" and mon["first_denial"] == 0
    assert mon["steps"][0]["decision"] == "deny"
    assert fix["scout"]["monitor"]["replayed"] is False            # no valid plan
    assert fix["m365-copilot"]["monitor"]["replayed"] is False
    assert "no hook" in fix["m365-copilot"]["monitor"]["why"]

    assert results["totals"]["agent"]["model_calls"] > 0
    assert "sentinel-xyz" not in text and EXAMPLE.read_text(encoding="utf-8") not in text
    for f in (out / "cells").rglob("*.txt"):          # saved prompts: no installed skill text
        assert "sentinel-xyz" not in f.read_text(encoding="utf-8"), f
    # the agent's prompt is the host's: real tool names, without skillc's own tools
    scout_system = next(s for s, _u in calls if s.startswith("You are Microsoft Scout"))
    assert "workiq_send_email" in scout_system and "skillc_start" not in scout_system


def test_m365_overlay(tmp_path):
    overlay = tmp_path / "m365-copilot.json"
    _write(overlay, {"tools": {"tickets_agent": "create tickets in the team tracker"},
                     "remove_lacks": ["MCP servers, agents"]})
    summary = m365.probe(overlay)
    assert summary["mode"] == "declared, not probed" and summary["overlay_applied"] is True
    m = m365.runtime_manifest(overlay)
    assert "tickets_agent" in m["tools"]
    assert not any("MCP servers, agents" in e for e in m["lacks"])
    _write(overlay, {"tools": ["not", "a", "map"]})
    assert m365.probe(overlay)["overlay_applied"] is False
    assert m365.runtime_manifest(overlay) == m365.base_manifest()
    assert m365.probe(tmp_path / "missing.json")["overlay_applied"] is False


def test_prompts_carry_no_url(env):
    data = json.loads(demo.CASES_FILE.read_text(encoding="utf-8"))
    real = json.loads((ROOT / "demo" / "skillc-here" / "host_cases.json").read_text("utf-8"))
    hosts = [demo.copilot_host(env["copilot"], env["gh"]),
             demo.scout_host(env["scout"], env["copilot"], env["gh"]),
             demo.m365_host(env["tmp"] / "no-overlay.json")]
    for case in [*real["cases"], *real["examples"], *data["cases"]]:
        assert_clean(case["request"])
        for h in hosts:
            assert_clean(demo.agent_system(h, case["request"], "(the skill text)"))
            system, _user = ce_runtime_messages("(the skill text)",
                                                Runtime.from_dict(h["manifest"]), version="p2g+")
            assert_clean(system)
    assert_clean(json.dumps(m365.base_manifest()))

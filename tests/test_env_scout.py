"""The Microsoft Scout probe and its manifest, on fake Scout homes (never the real one)."""
import json

import pytest

from skillc.env import scout
from skillc.env.manifest import load_manifest_facts, refute_text, requirement_status
from skillc.frontend.runtime import load_runtime

GH_PR = "Open the pull request:\n\n```\ngh pr create --fill\n```\n"


def _which(present):
    return lambda name: f"/fake/bin/{name}" if name in present else None


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def homes(tmp_path):
    home, copilot, gh = tmp_path / "scout", tmp_path / "copilot", tmp_path / "gh"
    _write(home / "m-mcp-servers.json", {"servers": {
        "playwright": {"builtin": True, "tools": ["browser_snapshot", "browser_click"]},
        "filesystem": {"builtin": True, "tools": ["read_file", "write_file"]},
        "azure_devops": {"builtin": False, "tools": [],
                         "config": {"command": "node", "env": {"TOKEN": "do-not-copy"}}},
        "skillc": {"builtin": False, "tools": ["skillc_start"]}}})
    _write(home / "m-settings.json", {
        "autoApprove": {"global": False, "perServer": {}},
        "loadCopilotCliSkills": True,
        "permissions": {
            "autoApproveReadOnly": True, "autoApproveAllWrites": True,
            "allowModelPermissionsChange": False,
            "allow": ["Get-ChildItem", "url:somewhere"], "denyPatterns": ["a", "b"],
            "disabledTools": ["tool:workiq_share_file"],
            "tools": {"tool:workiq_send_email": True, "tool:workiq_delete_email": False,
                      "tool:workiq_share_file": True, "tool:workiq_find_available_room": True,
                      "mcp:skillc:skillc-skillc_start": True},
            "servers": {"playwright": {"enabled": True, "autoApprove": False},
                        "filesystem": {"enabled": True, "autoApprove": False},
                        "workiq": {"enabled": True, "autoApprove": False},
                        "azure_devops": {"enabled": False, "autoApprove": True},
                        "shell": {"enabled": True, "autoApprove": True},
                        "skillc": {"enabled": True, "autoApprove": True}}}})
    (home / "skills" / "meeting-room-booking").mkdir(parents=True)
    (home / "skills" / "meeting-room-booking" / "SKILL.md").write_text("x", encoding="utf-8")
    (copilot / "skills" / "publish").mkdir(parents=True)
    (copilot / "skills" / "memo.md").write_text("x", encoding="utf-8")
    gh.mkdir()
    (gh / "hosts.yml").write_text("", encoding="utf-8")
    return home, copilot, gh


def _probe(homes, present=("gh", "git", "python")):
    home, copilot, gh = homes
    return scout.probe(home, copilot, which=_which(set(present)), gh_config=gh)


def test_status_derivation(homes):
    obs = _probe(homes)
    status = {t["name"]: (t["status"], t["server"]) for t in obs["tools"]}
    assert status["workiq_send_email"] == ("auto-approved", "workiq")     # per-tool flag
    assert status["workiq_delete_email"] == ("asks first", "workiq")      # flag false
    assert status["workiq_share_file"] == ("disabled", "workiq")          # disabledTools
    assert status["skillc_start"] == ("auto-approved", "skillc")          # mcp key form
    assert status["browser_snapshot"] == ("auto-approved", "playwright")  # read-only rule
    assert status["browser_click"] == ("asks first", "playwright")        # no rule: asks
    assert status["write_file"] == ("auto-approved", "filesystem")        # local writes rule
    assert status["read_file"] == ("auto-approved", "filesystem")
    assert obs["flags"] == {"auto_approve_global": False, "auto_approve_read_only": True,
                            "auto_approve_all_writes": True,
                            "allow_model_permissions_change": False,
                            "load_copilot_cli_skills": True, "deny_patterns": 2,
                            "allow_rules": 2}
    devops = next(s for s in obs["servers"] if s["name"] == "azure_devops")
    assert devops["enabled"] is False and devops["builtin"] is False
    assert obs["programs"]["gh"] and not obs["programs"]["pandoc"]
    assert obs["signed_in"] == {"gh": True}
    text = json.dumps(obs)
    assert "do-not-copy" not in text and "url:somewhere" not in text
    assert '"command"' not in text and "Get-ChildItem" not in text
    assert json.loads(text) == obs                                      # JSON-serialisable


def test_global_auto_approve_and_disabled_server(homes):
    home, _copilot, _gh = homes
    data = json.loads((home / "m-settings.json").read_text(encoding="utf-8"))
    data["autoApprove"]["global"] = True
    data["permissions"]["servers"]["playwright"]["enabled"] = False
    (home / "m-settings.json").write_text(json.dumps(data), encoding="utf-8")
    status = {t["name"]: t["status"] for t in _probe(homes)["tools"]}
    assert status["browser_click"] == "disabled"
    assert status["workiq_delete_email"] == "auto-approved"


def test_missing_files_give_empty_sections(tmp_path):
    obs = scout.probe(tmp_path / "nothing", tmp_path / "nocopilot", which=_which(set()),
                      gh_config=tmp_path / "nogh")
    assert obs["servers"] == [] and obs["tools"] == [] and obs["skills"] == []
    assert "m-mcp-servers.json: missing" in obs["sources"]
    assert "m-settings.json: missing" in obs["sources"]
    assert obs["signed_in"] == {"gh": False}
    assert not obs["flags"]["load_copilot_cli_skills"]
    manifest = scout.runtime_manifest(obs)
    assert "browser" not in manifest["tools"] and "m365" not in manifest["tools"]


def test_unreadable_settings_is_a_note_not_an_error(homes):
    home, _copilot, _gh = homes
    (home / "m-settings.json").write_text("{not json", encoding="utf-8")
    obs = _probe(homes)
    assert "m-settings.json: unreadable" in obs["sources"]
    assert obs["flags"]["deny_patterns"] == 0


def test_copilot_skills_follow_the_flag(homes):
    home, _copilot, _gh = homes
    skills = _probe(homes)["skills"]
    assert {"name": "meeting-room-booking", "origin": "scout"} in skills
    assert {"name": "publish", "origin": "copilot-cli"} in skills
    assert {"name": "memo.md", "origin": "copilot-cli"} in skills
    data = json.loads((home / "m-settings.json").read_text(encoding="utf-8"))
    data["loadCopilotCliSkills"] = False
    (home / "m-settings.json").write_text(json.dumps(data), encoding="utf-8")
    assert {s["origin"] for s in _probe(homes)["skills"]} == {"scout"}


def test_manifest_follows_what_was_observed(homes, tmp_path):
    obs = _probe(homes)
    m = scout.runtime_manifest(obs)
    base = json.loads(json.dumps(scout._base_manifest()))
    assert "browser" in m["tools"]                       # playwright enabled
    assert "azure_devops_mcp" not in m["tools"]          # azure_devops disabled
    assert "m365" in m["tools"] and "teams_message" in m["tools"]
    assert "mail (delete, send)" in m["tools"]["m365"]
    assert "calendar and rooms (find)" in m["tools"]["m365"]
    assert m["forbid_effects"] == base["forbid_effects"]
    assert "github_account" in m["grants"]
    assert "GitHub account" in m["lacks"][0]
    assert any("other than the tools listed" in e and "playwright" in e for e in m["lacks"])
    prov = scout.provenance(obs)
    assert prov["observed"] and prov["policy"] and "provenance" not in m
    path = tmp_path / "scout.manifest.json"
    path.write_text(json.dumps(m), encoding="utf-8")
    rt = load_runtime(str(path))
    assert rt.name == m["name"] and "browser" in rt.tools


def test_github_account_only_when_signed_in(homes, tmp_path):
    signed = scout.runtime_manifest(_probe(homes))
    assert refute_text(GH_PR, signed).verdict == "ACHIEVABLE"
    ev = refute_text(GH_PR, "scout-desktop")
    assert ev.verdict == "IMPOSSIBLE" and "account:github_account" in ev.blocking
    no_program = scout.runtime_manifest(_probe(homes, present=("git",)))
    assert "github_account" not in no_program["grants"]
    assert "account:github_account" in refute_text(GH_PR, no_program).blocking


def test_configured_servers_are_never_refuted_by_the_closing_sentence(homes):
    facts = load_manifest_facts(scout.runtime_manifest(_probe(homes)))
    for name in ("playwright", "skillc", "filesystem", "workiq"):
        assert requirement_status(f"mcp:{name}", {}, facts)[0] == "available", name
    assert requirement_status("mcp:slack", {}, facts)[0] == "unavailable"


def test_without_workiq_or_playwright_those_tools_go(tmp_path):
    home = tmp_path / "scout"
    _write(home / "m-mcp-servers.json", {"servers": {}})
    _write(home / "m-settings.json", {"permissions": {"servers": {
        "shell": {"enabled": False, "autoApprove": False}}}})
    m = scout.runtime_manifest(scout.probe(home, tmp_path / "c", which=_which(set()),
                                           gh_config=tmp_path / "gh"))
    for gone in ("browser", "m365", "teams_message", "azure_devops_mcp", "bash"):
        assert gone not in m["tools"]
    assert "microsoft_365_account" not in m["grants"]
    assert "github_account" not in m["grants"]

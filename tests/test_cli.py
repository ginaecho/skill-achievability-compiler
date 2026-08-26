import json
from pathlib import Path

from skillc.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def test_check_achievable_exit_0(capsys):
    rc = main(["check", str(FIXTURES / "changelog-writer/SKILL.md"),
               "--profile", "claude-code"])
    assert rc == 0
    assert "ACHIEVABLE" in capsys.readouterr().out


def test_check_impossible_exit_1(capsys):
    rc = main(["check", str(FIXTURES / "hallucinated-mailer/SKILL.md"),
               "--profile", "claude-ai"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "MISSING_CAPABILITY" in out and "send_email_v2" in out


def test_check_json_output(capsys):
    rc = main(["check", "--json", str(FIXTURES / "hallucinated-mailer/SKILL.md")])
    assert rc == 1
    data = json.loads(capsys.readouterr().out)
    assert data["verdict"] == "IMPOSSIBLE"
    assert "send_email_v2" in data["frontier"]


def test_compile_writes_pack(tmp_path, capsys):
    out = tmp_path / "pack.json"
    rc = main(["compile", str(FIXTURES / "embedded-pack/SKILL.md"),
               "-o", str(out), "-q"])
    assert rc == 0
    pack = json.loads(out.read_text())
    assert pack["name"] == "embedded-pack"


def test_check_a_compiled_pack_json(tmp_path, capsys):
    out = tmp_path / "pack.json"
    main(["compile", str(FIXTURES / "changelog-writer/SKILL.md"),
          "--profile", "claude-code", "-o", str(out), "-q"])
    rc = main(["check", str(out)])
    assert rc == 0


def test_scan_directory_json(capsys):
    rc = main(["scan", str(FIXTURES), "--json", "--profile", "claude-code"])
    assert rc == 0
    rows = json.loads(capsys.readouterr().out)
    by_name = {r["skill"]: r for r in rows}
    assert by_name["changelog-writer/SKILL.md"]["verdict"] == "ACHIEVABLE"
    assert by_name["hallucinated-mailer/SKILL.md"]["verdict"] == "IMPOSSIBLE"


def test_check_unknown_exit_3(tmp_path, capsys):
    pack = {"name": "spawner", "capabilities": {},
            "protocol": [{"spawn": {"role": "helper"}}], "goal": True}
    p = tmp_path / "pack.json"
    p.write_text(json.dumps(pack))
    rc = main(["check", str(p)])
    assert rc == 3
    out = capsys.readouterr().out
    assert "UNKNOWN" in out
    assert "not a refutation" in out


def test_check_json_is_self_describing(tmp_path, capsys):
    from skillc import __version__
    pack = {"name": "spawner", "capabilities": {},
            "protocol": [{"spawn": {"role": "helper"}}], "goal": True}
    p = tmp_path / "pack.json"
    p.write_text(json.dumps(pack))
    assert main(["check", "--json", str(p)]) == 3
    data = json.loads(capsys.readouterr().out)
    assert data["verdict"] == "UNKNOWN"
    assert data["unknown"] is True and data["refuted"] is False
    assert data["semantics"] == "may"
    assert data["skillc_version"] == __version__
    assert data["pack_digest"].startswith("sha256:")
    assert data["pack_name"] == "spawner"


def _write_scan_tree(tmp_path):
    (tmp_path / "spawner.json").write_text(json.dumps(
        {"name": "spawner", "capabilities": {},
         "protocol": [{"spawn": {"role": "helper"}}], "goal": True}))
    (tmp_path / "ok.json").write_text(json.dumps(
        {"name": "ok", "capabilities": {"a": {"add": ["done"]}},
         "protocol": [{"act": {"cap": "a", "by": "agent"}}], "goal": "done"}))


def test_scan_reports_unknown_explicitly(tmp_path, capsys):
    _write_scan_tree(tmp_path)
    assert main(["scan", str(tmp_path), "--glob", "*.json", "--json"]) == 0
    rows = {r["skill"]: r for r in json.loads(capsys.readouterr().out)}
    assert rows["spawner.json"]["verdict"] == "UNKNOWN"
    assert rows["spawner.json"]["unknown"] is True
    assert rows["spawner.json"]["refuted"] is False
    assert rows["ok.json"]["verdict"] == "ACHIEVABLE"


def test_scan_summary_counts_unknown(tmp_path, capsys):
    _write_scan_tree(tmp_path)
    assert main(["scan", str(tmp_path), "--glob", "*.json"]) == 0
    out = capsys.readouterr().out
    assert "1/2 achievable" in out
    assert "1 unknown" in out


def test_scan_paths_are_portable(tmp_path, capsys):
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "ok.json").write_text(json.dumps(
        {"name": "ok", "capabilities": {}, "protocol": [], "goal": True}))
    (tmp_path / "nested" / "bad.json").write_text(json.dumps(
        {"name": "bad", "capabilities": {}, "protocol": [], "goal": {"nand": []}}))
    assert main(["scan", str(tmp_path), "--glob", "*.json", "--json"]) == 0
    rows = {r["skill"]: r for r in json.loads(capsys.readouterr().out)}
    assert set(rows) == {"nested/ok.json", "nested/bad.json"}
    assert rows["nested/bad.json"]["verdict"] == "ERROR"


def test_eval_reports_abstentions(capsys):
    assert main(["eval"]) == 0
    out = capsys.readouterr().out
    assert "FN=0" in out and "PASS" in out
    assert "UNKNOWN" in out          # abstention line, even when the count is 0


def test_examples_check_out(capsys):
    root = Path(__file__).parent.parent / "examples"
    for skill in sorted(root.rglob("SKILL.md")):
        assert main(["check", str(skill)]) == 0, skill


def test_audit_poisoned_exit_1(capsys):
    rc = main(["audit", str(FIXTURES / "poisoned-helper")])
    assert rc == 1
    out = capsys.readouterr().out
    assert "description-injection" in out


def test_audit_clean_exit_0(capsys):
    rc = main(["audit", str(FIXTURES / "changelog-writer")])
    assert rc == 0


def test_audit_json(capsys):
    rc = main(["audit", "--json", str(FIXTURES / "poisoned-helper")])
    assert rc == 1
    data = json.loads(capsys.readouterr().out)
    (findings,) = data.values()
    assert any(f["code"] == "unicode-invisible" for f in findings)


def test_eval_passes(capsys):
    rc = main(["eval"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "FN=0" in out and "PASS" in out


def test_profiles_listed(capsys):
    rc = main(["profiles"])
    assert rc == 0
    out = capsys.readouterr().out
    for name in ("claude-ai", "claude-code", "none"):
        assert name in out


def test_error_exit_2(capsys):
    rc = main(["check", "no-such-file.json"])
    assert rc == 2

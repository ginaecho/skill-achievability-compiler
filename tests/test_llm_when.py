"""--llm-when needed: the deterministic front-end's IMPOSSIBLE short-circuits the LLM."""
import json
from pathlib import Path

import pytest

from skillc.cli import main
from skillc.frontend.markdown import compile_file
from skillc.profiles import load_profile

FIXTURES = Path(__file__).parent / "fixtures"
IMPOSSIBLE = str(FIXTURES / "hallucinated-mailer/SKILL.md")
ACHIEVABLE = str(FIXTURES / "changelog-writer/SKILL.md")
NOTE = "LLM not called: deterministic front-end refuted"


@pytest.fixture
def stub(monkeypatch):
    calls = []
    pack = compile_file(Path(ACHIEVABLE), load_profile("claude-code")).pack

    def fake(*a, **kw):
        calls.append(1)
        return pack

    monkeypatch.setattr("skillc.frontend.llm.compact", fake)
    return calls


def _check(capsys, path, profile, *flags):
    rc = main(["check", "--json", path, "--profile", profile, "--llm", *flags])
    return rc, json.loads(capsys.readouterr().out)


def test_needed_skips_llm_on_deterministic_impossible(stub, capsys):
    rc, out = _check(capsys, IMPOSSIBLE, "claude-ai", "--llm-when", "needed")
    assert stub == []
    assert rc == 1 and out["verdict"] == "IMPOSSIBLE"
    assert out["front_end"] == "deterministic" and out["note"] == NOTE


def test_needed_text_output_notes_skip(stub, capsys):
    rc = main(["check", IMPOSSIBLE, "--profile", "claude-ai", "--llm",
               "--llm-when", "needed"])
    out = capsys.readouterr().out
    assert rc == 1 and stub == []
    assert NOTE in out and "front_end: deterministic" in out


def test_needed_calls_llm_on_achievable(stub, capsys):
    rc, out = _check(capsys, ACHIEVABLE, "claude-code", "--llm-when", "needed")
    assert stub == [1]
    assert rc == 0 and out["front_end"] == "llm" and "note" not in out


def test_always_calls_llm_on_both(stub, capsys):
    _check(capsys, IMPOSSIBLE, "claude-ai", "--llm-when", "always")
    _check(capsys, ACHIEVABLE, "claude-code", "--llm-when", "always")
    assert len(stub) == 2


def test_default_is_always(stub, capsys):
    from skillc.cli import _add_compile_opts
    import argparse
    ap = argparse.ArgumentParser()
    _add_compile_opts(ap)
    assert ap.parse_args([]).llm_when == "always"
    _, out = _check(capsys, IMPOSSIBLE, "claude-ai")
    assert stub == [1] and out["front_end"] == "llm"


def test_deterministic_error_falls_back_to_llm(stub, capsys, monkeypatch):
    def boom(*a, **kw):
        raise ValueError("front-end failed")
    monkeypatch.setattr("skillc.cli.compile_file", boom)
    rc, out = _check(capsys, ACHIEVABLE, "claude-code", "--llm-when", "needed")
    assert stub == [1] and out["front_end"] == "llm"


def test_scan_reports_llm_calls(stub, tmp_path, capsys):
    for name, src in (("a", IMPOSSIBLE), ("b", ACHIEVABLE)):
        d = tmp_path / name
        d.mkdir()
        (d / "SKILL.md").write_text(Path(src).read_text(encoding="utf-8"), encoding="utf-8")
    main(["scan", str(tmp_path), "--profile", "claude-ai", "--llm", "--llm-when", "needed"])
    out = capsys.readouterr().out
    assert "LLM calls: 1 of 2 (saved 1)" in out and len(stub) == 1

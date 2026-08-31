import json
from pathlib import Path

import pytest

from skillc.cli import main
from skillc.integrate import (HOOK_MARKER, add_agent_hook, choose_agents,
                              discover_agents, install_integration,
                              resolve_agents)


def _agent(root: Path, filename: str, name: str) -> Path:
    path = root / ".github" / "agents" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nname: {name}\ntools: [read, execute]\n---\n\n# {name}\n",
        encoding="utf-8",
    )
    return path


def test_discover_and_resolve_agents(tmp_path):
    alpha = _agent(tmp_path, "alpha.agent.md", "Alpha Agent")
    beta = _agent(tmp_path, "beta.md", "Beta Agent")
    assert discover_agents(tmp_path) == [alpha, beta]
    assert resolve_agents(tmp_path, ["Alpha Agent", "beta.md"]) == [alpha, beta]


def test_choose_agents_by_number(tmp_path):
    alpha = _agent(tmp_path, "alpha.md", "Alpha")
    beta = _agent(tmp_path, "beta.md", "Beta")
    output = []
    selected = choose_agents(
        [alpha, beta], input_fn=lambda _: "2,1", output_fn=output.append)
    assert selected == [beta, alpha]
    assert any("Alpha" in line for line in output)


def test_install_writes_adapters_and_scoped_hook_idempotently(tmp_path):
    alpha = _agent(tmp_path, "alpha.md", "Alpha")
    result = install_integration(tmp_path, [alpha])
    text = alpha.read_text(encoding="utf-8")
    assert HOOK_MARKER in text
    assert 'SKILLC_AGENT_PATH: ".github/agents/alpha.md"' in text
    assert "---\n\n# Alpha\n" in text
    assert all(path.is_file() for path in result.scripts)
    assert "python3" not in result.scripts[1].read_text(encoding="utf-8")
    assert "hook agent-session" in result.scripts[1].read_text(encoding="utf-8")

    assert not add_agent_hook(alpha, tmp_path)
    assert alpha.read_text(encoding="utf-8") == text


def test_existing_unmanaged_hooks_require_manual_merge(tmp_path):
    alpha = _agent(tmp_path, "alpha.md", "Alpha")
    text = alpha.read_text(encoding="utf-8")
    alpha.write_text(text.replace("tools:", "hooks: {}\ntools:"), encoding="utf-8")
    with pytest.raises(ValueError, match="already defines hooks"):
        add_agent_hook(alpha, tmp_path)


def test_agent_session_cli_emits_host_hook_json(tmp_path, capsys):
    alpha = _agent(tmp_path, "alpha.md", "Alpha")
    assert main(["hook", "agent-session", "--agent", str(alpha)]) == 0
    assert json.loads(capsys.readouterr().out) == {"continue": True}


def test_doctor_checks_dependencies_adapters_and_preflight(
        tmp_path, monkeypatch, capsys):
    alpha = _agent(tmp_path, "alpha.md", "Alpha")
    install_integration(tmp_path, [alpha])
    monkeypatch.setattr("shutil.which", lambda command: "/tools/skillc")
    assert main([
        "doctor", "--workspace", str(tmp_path), "--configured",
    ]) == 0
    output = capsys.readouterr().out
    assert "pyyaml " in output
    assert "z3 " in output
    assert "preflight alpha.md: allow" in output
    assert "doctor: PASS" in output
"""The default verdict path for a natural-language skill and a runtime manifest:
the deterministic requirement reader (Rdet) first, then P2g+ compaction and the
checker (`frontend.llm.decide_text`).  No test calls a model."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from skillc import checker
from skillc.cli import main
from skillc.env import manifest
from skillc.frontend import llm, providers
from skillc.gate import gate
from skillc.monitor import ALLOW, ASK_USER, DENY, Config, Monitor

FIXTURES = Path(__file__).parent / "fixtures"
FINANCE = Path(__file__).parent.parent / "examples" / "hosted-agent-finance"
IGNORE = shutil.ignore_patterns("src", ".skillc", ".azure", "*.log", "__pycache__")

# huggingface.co is in claude-code-cloud's egress_deny
BLOCKED = ("# Model fetch\n"
           "Download the weights with "
           "`curl -L https://huggingface.co/bert-base/resolve/main/model.bin -o model.bin`.\n"
           "Then summarise the model card in the reply.\n")
# the same host, only in an optional passage
OPTIONAL = ("# Model notes\n"
            "Summarise the model card the user pastes into the reply.\n\n"
            "## Optional\n"
            "If you want, you can also run "
            "`curl -L https://huggingface.co/bert-base/resolve/main/model.bin -o model.bin` "
            "to fetch the weights. This step is optional.\n")
PLAIN = "# Build\nRun the build.\n"

GOOD = ("```ce\nSkill `s`.\nTool `t` (owner `agent`): via `bash`; adds `g`.\nGoal: `g`.\n"
        "Protocol:\n  - `agent` uses `t`.\n```")
PLAN = GOOD.removeprefix("```ce\n").removesuffix("```")


@pytest.fixture
def no_model(monkeypatch):
    def fail(*a, **kw):
        raise AssertionError("the model was called")
    monkeypatch.setattr(providers, "anthropic_complete", fail)
    monkeypatch.setattr(providers, "azure_openai_complete", fail)


@pytest.fixture
def model(monkeypatch):
    calls = []

    def fake(system, user, model, timeout):
        calls.append((system, user))
        return GOOD

    monkeypatch.setattr(providers, "anthropic_complete", fake)
    return calls


def _skill(tmp_path, text, name="SKILL.md"):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


# --------------------------------------------------------------------------
# decide_text
# --------------------------------------------------------------------------

def test_reason_is_a_checker_reason():
    assert "REQUIREMENT_UNAVAILABLE" in checker.REASONS


def test_reader_refutes_without_a_model_call(no_model):
    v = llm.decide_text(BLOCKED, "claude-code-cloud", model=None, provider="anthropic")
    assert v.label == "IMPOSSIBLE" and v.refuted and not v.admissible
    assert v.reason == "REQUIREMENT_UNAVAILABLE"
    assert v.coverage == "deterministic-reader:manifest"
    assert v.protocol == "NOT_CHECKED"
    assert v.frontier == ("egress:huggingface.co",)
    assert "egress_deny: huggingface.co" in v.detail
    assert "line 2: curl -L https://huggingface.co/" in v.detail


def test_reader_passes_and_the_model_path_decides(model):
    v = llm.decide_text(PLAIN, "developer-sandbox", model=None, provider="anthropic")
    assert v.label == "ACHIEVABLE" and len(model) == 1
    assert "11. Facts the environment" in model[0][0]          # the P2g+ prompt
    assert ("deterministic reader: no unavailable hard requirement against runtime "
            "`developer-sandbox`") in v.detail


def test_without_a_manifest_the_reader_is_skipped_and_says_so(model, monkeypatch):
    def none(runtime):
        raise KeyError("no manifest")
    monkeypatch.setattr(manifest, "manifest_facts", none)
    v = llm.decide_text(BLOCKED, "claude-code-cloud", model=None, provider="anthropic")
    assert len(model) == 1 and "deterministic reader not run" in v.detail


def test_host_only_in_an_optional_passage_is_not_refuted():
    ev = manifest.refute_text(OPTIONAL, "claude-code-cloud")
    assert ev.verdict == "ACHIEVABLE" and not ev.blocking
    hard = manifest.refute_text(BLOCKED, "claude-code-cloud")
    assert hard.blocking == ["egress:huggingface.co"]


# --------------------------------------------------------------------------
# skillc check
# --------------------------------------------------------------------------

def test_check_llm_runtime_uses_the_reader_first(tmp_path, no_model, capsys):
    path = _skill(tmp_path, BLOCKED)
    rc = main(["check", path, "--llm", "--llm-provider", "anthropic",
               "--runtime", "claude-code-cloud", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1 and out["front_end"] == "deterministic-reader"
    assert out["reason"] == "REQUIREMENT_UNAVAILABLE"
    assert out["coverage"] == "deterministic-reader:manifest"
    assert out["requirement_eval"]["blocking"] == ["egress:huggingface.co"]


def test_check_text_output_prints_the_witness_line(tmp_path, no_model, capsys):
    path = _skill(tmp_path, BLOCKED)
    rc = main(["check", path, "--llm", "--runtime", "claude-code-cloud",
               "--llm-provider", "anthropic"])
    out = capsys.readouterr().out
    assert rc == 1
    assert ("witness: egress:huggingface.co: egress_deny: huggingface.co; evidence line 2: "
            "curl -L https://huggingface.co/") in out
    assert "coverage: deterministic-reader:manifest" in out
    assert "LLM not called: deterministic requirement reader refuted" in out


def test_rdet_only_never_calls_the_model(tmp_path, no_model, capsys):
    rc = main(["check", _skill(tmp_path, BLOCKED), "--rdet-only",
               "--runtime", "claude-code-cloud"])
    assert rc == 1 and "witness: egress:huggingface.co" in capsys.readouterr().out
    rc = main(["check", _skill(tmp_path, PLAIN, "plain.md"), "--rdet-only",
               "--runtime", "claude-code-cloud", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 3 and out["verdict"] == "UNKNOWN" and out["front_end"] == "deterministic-reader"


def test_no_rdet_calls_the_model_on_a_text_the_reader_refutes(tmp_path, model, capsys):
    rc = main(["check", _skill(tmp_path, BLOCKED), "--llm", "--llm-provider", "anthropic",
               "--runtime", "claude-code-cloud", "--no-rdet", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert len(model) == 1 and out["front_end"] == "llm" and rc == 0
    assert "deterministic reader not run: --no-rdet" in out["detail"]


def test_rdet_flags_exclude_each_other_and_need_a_runtime(tmp_path, no_model, capsys):
    path = _skill(tmp_path, PLAIN)
    assert main(["check", path, "--rdet-only", "--no-rdet", "--runtime",
                 "claude-code-cloud"]) == 2
    assert main(["check", path, "--rdet-only"]) == 2
    capsys.readouterr()


# --------------------------------------------------------------------------
# skillc scan
# --------------------------------------------------------------------------

def test_scan_rows_name_the_front_end(tmp_path, model, capsys):
    _skill(tmp_path, BLOCKED, "a/SKILL.md")
    _skill(tmp_path, PLAIN, "b/SKILL.md")
    (tmp_path / "c").mkdir()
    shutil.copy(FIXTURES / "hallucinated-mailer" / "SKILL.md", tmp_path / "c" / "SKILL.md")
    rc = main(["scan", str(tmp_path), "--llm", "--llm-provider", "anthropic",
               "--runtime", "claude-code-cloud", "--llm-when", "needed", "--json"])
    rows = {r["skill"]: r for r in json.loads(capsys.readouterr().out)}
    assert rc == 0 and len(model) == 1
    assert rows["a/SKILL.md"]["front_end"] == "deterministic-reader"
    assert rows["a/SKILL.md"]["reason"] == "REQUIREMENT_UNAVAILABLE"
    assert rows["b/SKILL.md"]["front_end"] == "llm"
    assert rows["c/SKILL.md"]["front_end"] == "deterministic"      # markdown front-end first


# --------------------------------------------------------------------------
# gate and monitor
# --------------------------------------------------------------------------

def test_gate_skill_entry_is_refuted_by_the_reader(tmp_path):
    project = tmp_path / "finance"
    shutil.copytree(FINANCE, project, ignore=IGNORE)
    (project / "skills" / "Fetcher.md").write_text(
        "---\nname: fetcher\ndescription: Builds the image.\n---\n# Fetcher\n\n"
        "Build the image with `docker build -t fetcher .` and report the digest.\n",
        encoding="utf-8")
    report = gate(project)
    skill = next(e for e in report.skills if e.name == "Fetcher.md")
    assert skill.verdict == "IMPOSSIBLE" and report.verdict == "IMPOSSIBLE"
    assert skill.reason.startswith("REQUIREMENT_UNAVAILABLE (deterministic requirement "
                                   "reader, runtime `foundry-hosted`)")
    assert "unavailable_programs: docker" in skill.reason
    assert "evidence line 7: docker build -t fetcher ." in skill.reason
    assert skill.detail["coverage"] == "deterministic-reader:manifest"


def test_monitor_denies_a_plan_whose_skill_the_reader_refutes(tmp_path):
    m = Monitor(Config(runtime="claude-code-cloud"), tmp_path)
    d = m.submit_plan(PLAN, skill_text=BLOCKED)
    assert d.action == DENY and d.next == ASK_USER and m.state.plan is None
    assert "REQUIREMENT_UNAVAILABLE" in d.reason
    assert "witness: egress:huggingface.co: egress_deny: huggingface.co" in d.reason
    assert "line 2: curl -L https://huggingface.co/" in d.reason
    assert d.witness == ["egress:huggingface.co"]


def test_monitor_without_skill_text_is_unchanged(tmp_path):
    m = Monitor(Config(runtime="claude-code-cloud"), tmp_path)
    assert m.submit_plan(PLAN).action == ALLOW
    m = Monitor(Config(runtime="claude-code-cloud"), tmp_path / "other")
    assert m.submit_plan(PLAN, skill_text=PLAIN).action == ALLOW

"""Rdet: a document's requirements evaluated against a runtime manifest."""
from collections import Counter
from pathlib import Path

import pytest

from skillc.env.manifest import (REASON, ManifestFacts, evaluate, load_manifest_facts,
                                 refute_text)
from skillc.env.nl import intent_from_text

ROOT = Path(__file__).resolve().parents[1]
SET3 = ROOT / "benchmark" / "claude_env" / "set3" / "cases"

BARE = ManifestFacts.from_dict({"name": "bare", "tools": {"bash": "run commands"},
                                "grants": ["shell"], "software": "installable"})


def _status(ev, cond):
    return next(s for s in ev.statuses if s.cond == cond)


def test_denied_host_in_hard_command_is_impossible():
    doc = "# Fetch\n\n```bash\ncurl -sS https://huggingface.co/api/models\n```\n"
    ev = refute_text(doc, "claude-code-cloud")
    assert ev.verdict == "IMPOSSIBLE" and ev.reason == REASON
    assert ev.blocking == ["egress:huggingface.co"]
    w = ev.witness[0]
    assert w["requirement"] == "egress:huggingface.co"
    assert w["basis"] == "egress_deny: huggingface.co"
    assert any("curl -sS https://huggingface.co/api/models" in e for e in w["evidence"])


def test_wildcard_deny_matches_subdomain():
    doc = "```bash\ncurl https://management.azure.com/subscriptions\n```\n"
    ev = refute_text(doc, "claude-code-cloud")
    assert _status(ev, "egress:management.azure.com").basis == "egress_deny: *.azure.com"
    assert ev.verdict == "IMPOSSIBLE"


def test_denied_host_in_optional_passage_does_not_block():
    doc = ("# Fetch\n\n## Optional: model card\n\n"
           "```bash\ncurl -sS https://huggingface.co/api/models\n```\n")
    ev = refute_text(doc, "claude-code-cloud")
    st = _status(ev, "egress:huggingface.co")
    assert not st.hard and st.status == "unavailable"
    assert ev.verdict == "ACHIEVABLE" and ev.blocking == [] and ev.witness == []


def test_allowed_host_is_available():
    doc = "```bash\ncurl -sS https://api.github.com/repos/a/b\n```\n"
    ev = refute_text(doc, "claude-code-cloud")
    assert _status(ev, "egress:api.github.com").status == "available"


def test_pip_installable_program_by_manifest():
    doc = "# Convert\n\n```bash\nmarkitdown report.pdf > report.md\n```\n"
    cloud = refute_text(doc, "claude-code-cloud")
    assert _status(cloud, "program:markitdown").status == "installable"
    assert cloud.verdict == "ACHIEVABLE"
    office = refute_text(doc, "office-assistant")
    st = _status(office, "program:markitdown")
    assert st.status == "unavailable" and st.basis == "unavailable_programs: *"
    assert office.verdict == "IMPOSSIBLE"


def test_unavailable_program_is_explicit():
    doc = "```bash\ndocker build -t app .\n```\n"
    ev = refute_text(doc, "claude-code-cloud")
    assert _status(ev, "program:docker").basis == "unavailable_programs: docker"
    assert ev.verdict == "IMPOSSIBLE"


def test_credential_unavailable_only_where_lacks_says_so():
    doc = "Set the key first: `export OPENAI_API_KEY=...`\n\n```bash\npython run.py\n```\n"
    intent = intent_from_text(doc)
    cond = next(c for c in intent["goal"] if "OPENAI_API_KEY" in c or c == "account:llm_api_key")
    cloud = evaluate(intent, load_manifest_facts("claude-code-cloud"))
    st = _status(cloud, cond)
    assert st.status == "unavailable"
    # explicit: the lacks sentence about credentials for external services decides
    assert st.basis.startswith("lacks: accounts, logins, API keys or credentials for external")
    assert cloud.verdict == "IMPOSSIBLE"
    assert _status(evaluate(intent, BARE), cond).status == "unknown"


def test_granted_account_credential_is_available():
    doc = "Run with `export GITHUB_TOKEN=$TOKEN` set.\n"
    ev = refute_text(doc, "claude-code-cloud")
    cond = next(s.cond for s in ev.statuses if "github" in s.cond.lower())
    assert _status(ev, cond).status == "available"


def test_connector_in_manifest_tools_is_available():
    doc = "Search with `mcp__claude_ai_Notion__notion-search` and summarise.\n"
    ev = refute_text(doc, "claude-code-cloud")
    st = _status(ev, "mcp:claude-ai-Notion")
    assert st.status == "available" and st.basis == "tools: notion"
    other = refute_text("Use `mcp__figma__get_file` to read the design.\n", "claude-code-cloud")
    assert _status(other, "mcp:figma").status == "unavailable"
    assert _status(refute_text("Use `mcp__figma__get_file`.\n", BARE),
                   "mcp:figma").status == "unknown"


def test_manifest_without_new_fields_keeps_hosts_unknown():
    doc = "```bash\ncurl -sS https://huggingface.co/api/models\n```\n"
    ev = refute_text(doc, BARE)
    st = _status(ev, "egress:huggingface.co")
    assert st.status == "unknown"
    assert ev.verdict == "ACHIEVABLE" and "egress:huggingface.co" in ev.unknown
    # the developer sandbox says "public internet" in prose, not a structured list
    assert _status(refute_text(doc, "developer-sandbox"),
                   "egress:huggingface.co").status == "unknown"


def test_offline_denies_every_host():
    doc = "```bash\ncurl -sS https://pypi.org/simple/\n```\n"
    ev = refute_text(doc, "offline-workstation")
    assert _status(ev, "egress:pypi.org").basis == "egress_deny: *"


def test_to_dict_shape():
    d = refute_text("```bash\ndocker run x/y\n```\n", "claude-code-cloud").to_dict()
    assert d["verdict"] == "IMPOSSIBLE" and d["reason"] == REASON
    assert {"requirement", "hard", "status", "basis", "evidence"} <= set(d["requirements"][0])


@pytest.mark.skipif(not SET3.is_dir(), reason="benchmark data not present")
def test_set3_cases_evaluate_without_errors():
    files = sorted(SET3.glob("*.md"))
    assert files
    verdicts = Counter()
    for f in files:
        ev = refute_text(f.read_text(encoding="utf-8"), "claude-code-cloud", name=f.stem)
        assert ev.verdict in ("IMPOSSIBLE", "ACHIEVABLE")
        assert all(s.status in ("available", "installable", "unavailable", "unknown")
                   for s in ev.statuses)
        verdicts[ev.verdict] += 1
    print(f"set3 Rdet on claude-code-cloud ({len(files)} documents): {dict(verdicts)}")

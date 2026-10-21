"""Rdet2 (PLAN Addendum E-a): prose mentions are hard only with a requirement
cue; accounts are hard only with operational evidence.  Rdet is unchanged."""
import pytest

from skillc.env.manifest import refute_text
from skillc.env.nl import intent_from_text, requirements
from skillc.env.rdet2 import refute_text_rdet2


def _core(text, strict):
    return {r.cond: r.core for r in requirements(text, strict_mentions=strict)}


def test_account_from_prose_mention_is_not_hard():
    doc = "# Observability\n\nDesign monitoring for serverless apps on AWS Lambda.\n"
    assert _core(doc, False)["account:aws_account"] is True          # Rdet: hard
    assert _core(doc, True)["account:aws_account"] is False          # Rdet2: mention only
    assert refute_text(doc, "claude-code-cloud").verdict == "IMPOSSIBLE"
    assert refute_text_rdet2(doc, "claude-code-cloud").verdict == "ACHIEVABLE"


def test_account_with_requirement_cue_but_no_operation_is_not_hard():
    doc = "# Deploy\n\nYou must have an AWS account.\n"
    assert _core(doc, True)["account:aws_account"] is False


def test_account_with_cli_command_is_hard():
    doc = "# Upload\n\n```bash\naws s3 cp out.zip s3://bucket/\n```\n"
    assert _core(doc, True)["account:aws_account"] is True
    ev = refute_text_rdet2(doc, "claude-code-cloud")
    assert "account:aws_account" in ev.blocking


def test_account_with_inline_cli_command_is_hard():
    doc = "# Login\n\nLog in with `wrangler login` and then deploy.\n"
    assert _core(doc, True)["account:cloudflare_account"] is True


def test_account_with_credential_variable_is_hard():
    doc = "# Render\n\nDeploy to Render.\n\n```bash\nexport RENDER_API_KEY=abc\n```\n"
    assert _core(doc, True)["account:render_account"] is True


def test_account_with_environment_variable_assignment_is_hard():
    doc = "# Azure\n\n```bash\nAZURE_SUBSCRIPTION_ID=<id>  # Required\n```\n"
    assert _core(doc, True)["account:azure_account"] is True


def test_account_with_sdk_import_is_hard():
    doc = "# S3\n\n```python\nimport boto3\ns3 = boto3.client('s3')\n```\n"
    assert _core(doc, True)["account:aws_account"] is True


def test_account_command_in_optional_passage_is_not_hard():
    doc = "# Upload\n\n## Optional: publish\n\n```bash\naws s3 cp out.zip s3://b/\n```\n"
    assert _core(doc, True)["account:aws_account"] is False


def test_platform_mention_without_cue_is_not_hard():
    doc = "# Fuzz\n\n### Windows\n\nInstall Clang through Visual Studio; see the msbuild docs.\n"
    assert _core(doc, False)["platform:windows"] is True
    assert _core(doc, True)["platform:windows"] is False


def test_platform_mention_with_cue_is_hard():
    doc = "# Build\n\nThis project requires msbuild on the build machine.\n"
    assert _core(doc, True)["platform:windows"] is True


def test_cue_must_be_in_the_same_sentence():
    doc = "# Build\n\nYou must read the guide. Then open msbuild docs.\n"
    assert _core(doc, True)["platform:windows"] is False


def test_cannot_without_is_a_cue():
    doc = "# Build\n\nYou cannot build this without msbuild.\n"
    assert _core(doc, True)["platform:windows"] is True


def test_mention_inside_fenced_block_stays_hard():
    doc = "# Build\n\n```\nmsbuild App.sln /p:Configuration=Release\n```\n"
    assert _core(doc, True)["platform:windows"] is True


def test_mention_in_inline_code_stays_hard():
    doc = "# Costs\n\n| Intent | Tools |\n|---|---|\n| budgets | `query_costs` |\n"
    assert _core(doc, True)["mcp:azure"] is True
    assert _core("# Costs\n\nWe talk about query_costs here.\n", True)["mcp:azure"] is False


def test_command_requirements_are_unchanged():
    doc = ("# Fetch\n\n```bash\ncurl -sS https://huggingface.co/api/models\n"
           "docker run --rm alpine true\n```\n")
    assert _core(doc, True) == _core(doc, False)


def test_rdet_default_is_unchanged_and_reader_is_checked():
    doc = "# Observability\n\nDesign for AWS Lambda.\n"
    assert intent_from_text(doc) == intent_from_text(doc, reader="rdet")
    assert "account:aws_account" in intent_from_text(doc)["goal"]
    assert "account:aws_account" in intent_from_text(doc, reader="rdet2")["optional"]
    with pytest.raises(ValueError):
        intent_from_text(doc, reader="rdet3")

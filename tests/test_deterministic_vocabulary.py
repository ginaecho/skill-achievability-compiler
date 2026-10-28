import json
from pathlib import Path

import pytest

from skillc import check, compile_markdown, load_profile
from skillc.cli import check_compiled, main
from skillc.frontend.grants import bind_grants


@pytest.fixture
def vocabulary_file(tmp_path, monkeypatch):
    path = tmp_path / "vocabulary.json"
    monkeypatch.setenv("SKILLC_DETERMINISTIC_VOCABULARY", str(path))
    return path


def test_custom_vocabulary_reaches_both_extraction_paths(vocabulary_file):
    vocabulary_file.write_text(json.dumps({
        "actions": {
            "inspect_package": {
                "phrases": ["inspect the package"],
                "tool_names": ["scan_package"],
            },
        },
        "invocation_verbs": ["activate"],
        "completion_phrases": ["the review succeeds when"],
        "workflow_headings": ["review checklist"],
    }), encoding="utf-8-sig")
    document = (
        "# Review\n"
        "Tools: scan_package, publish.\n\n"
        "The review succeeds when the package is **inspected** "
        "and the report is **published**.\n\n"
        "## Review checklist\n"
        "1. Inspect the package until it is **inspected**.\n"
        "2. Activate `publish` so the report is **published**.\n"
    )
    result = compile_markdown(document, load_profile("none"))
    assert result.goal_source == "semantic"
    assert [item.tool for item in result.invocations] == ["scan_package", "publish"]
    assert [step["act"]["cap"] for step in result.pack["protocol"]] == [
        "scan_package", "publish",
    ]
    assert result.pack["goal"] == {"and": ["inspected", "published"]}
    assert check(bind_grants(result.pack, ["scan_package", "publish"]).pack).admissible
    assert check(bind_grants(result.pack, ["publish"]).pack).reason == "MISSING_CAPABILITY"
    # Extensions retain the built-in grammar.
    legacy = compile_markdown("Use `legacy_tool`.", load_profile("none"))
    assert [item.tool for item in legacy.invocations] == ["legacy_tool"]
    source = vocabulary_file.parent / "review.md"
    output = vocabulary_file.parent / "pack.json"
    source.write_text(document, encoding="utf-8")
    assert main(["compile", str(source), "--profile", "none", "-o", str(output), "-q"]) == 0
    assert json.loads(output.read_text(encoding="utf-8")) == result.pack


def test_custom_action_obeys_negation_fences_and_word_boundaries(vocabulary_file):
    vocabulary_file.write_text(json.dumps({
        "actions": {"inspect_package": {"phrases": ["inspect the package"]}},
    }), encoding="utf-8")
    result = compile_markdown(
        "Never inspect the package.\n"
        "Do not inspect the package.\n"
        "Reinspect the package.\n"
        "```\nInspect the package.\n```\n"
        "Inspect   the package.\n",
        load_profile("none"),
    )
    assert [(item.tool, item.line) for item in result.invocations] == [
        ("inspect_package", 7),
    ]


def test_longest_phrase_and_negation_apply_to_semantic_steps(vocabulary_file):
    vocabulary_file.write_text(json.dumps({
        "actions": {
            "inspect_package": {"phrases": ["inspect the package"]},
            "inspect_deeply": {"phrases": ["inspect the package deeply"]},
            "publish": {"phrases": ["publish the report"]},
        },
    }), encoding="utf-8")
    result = compile_markdown(
        "Success means the package is **inspected**.\n\n"
        "Tools: inspect_package, inspect_deeply, publish.\n\n"
        "## Workflow\n"
        "1. Never publish the report.\n"
        "2. Inspect the package deeply until it is **inspected**.\n",
        load_profile("none"),
    )
    assert result.goal_source == "semantic"
    assert [step["act"]["cap"] for step in result.pack["protocol"]] == ["inspect_deeply"]


def test_new_builtins_recognize_authored_goal_and_workflow():
    result = compile_markdown(
        "Success requires the report to be **published**.\n\n"
        "Tools: publish.\n\n"
        "## Action plan\n"
        "1. Execute `publish` so the report is **published**.\n",
        load_profile("none"),
    )
    assert result.goal_source == "semantic"
    assert [item.tool for item in result.invocations] == ["publish"]
    assert check(result.pack).admissible


def test_missing_or_malformed_custom_file_does_not_fall_back(vocabulary_file):
    with pytest.raises(FileNotFoundError):
        compile_markdown("Use `some_tool`.", load_profile("none"))
    vocabulary_file.write_text("{bad json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        compile_markdown("Use `some_tool`.", load_profile("none"))


def test_example_extension_names_an_operation_not_a_success_condition(monkeypatch):
    example = Path(__file__).resolve().parents[1] / "examples" / "deterministic-vocabulary.json"
    monkeypatch.setenv("SKILLC_DETERMINISTIC_VOCABULARY", str(example))
    result = compile_markdown(
        "Tools: scan_artifact.\nScan the package for malware.",
        load_profile("none"),
    )
    assert [item.tool for item in result.invocations] == ["scan_artifact"]
    assert result.goal_source == "tool_usage_only"
    assert check_compiled(result.pack, result, scope="goal").reason == "INCOMPLETE_COMPACTION"


def test_invalid_vocabulary_cannot_trigger_optional_model_fallback(
        vocabulary_file, monkeypatch, capsys):
    vocabulary_file.write_text('{"invocation_verb": ["activate"]}', encoding="utf-8")
    source = vocabulary_file.parent / "review.md"
    source.write_text("Activate `publish`.", encoding="utf-8")

    def no_model(*args, **kwargs):
        pytest.fail("invalid vocabulary must be reported before the optional model call")

    monkeypatch.setattr("skillc.cli._compact_with_llm", no_model)
    assert main(["check", str(source), "--llm", "--llm-when", "needed"]) == 2
    assert "invocation_verb" in capsys.readouterr().err


@pytest.mark.parametrize("data, message", [
    ({"invocation_verb": ["activate"]}, "unsupported"),
    ({"invocation_verbs": "activate"}, "list"),
    ({"completion_phrases": [""]}, "non-empty"),
    ({"workflow_headings": [12]}, "string"),
    ({"actions": {"inspect_package": {"phrase": ["inspect the package"]}}}, "unsupported"),
    ({"actions": {"bad-name": {"phrases": ["inspect the package"]}}}, "name"),
    ({"actions": {
        "first": {"phrases": ["inspect the package"]},
        "second": {"phrases": ["INSPECT THE PACKAGE"]},
    }}, "ambiguous"),
])
def test_invalid_vocabulary_is_reported_not_ignored(vocabulary_file, data, message):
    vocabulary_file.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        compile_markdown("Use `some_tool`.", load_profile("none"))

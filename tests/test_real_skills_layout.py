import json
import os
import subprocess

import pytest

from scripts.real_skills_layout import LAYOUT, layout_reference, verify_layout_map
from scripts.real_skills_pilot import verify
from scripts.real_skills_runtime import Sandbox


@pytest.fixture
def inputs():
    return {
        "agent.py": b"from .agent_loop import run\nfrom skillc.frontend import agent_tools\nimport skillc.frontend.leaf as leaf\n",
        "agent_loop.py": b"from skillc.frontend.agent_tools import tool\nfrom ..leaf import ignored\n",
        "agent_tools.py": b"def tool():\n    from . import leaf\n    from .other import value\n",
        "leaf.py": b"from .agent import unused\nraise RuntimeError('never execute input')",
        "other.py": b"import unrelated.agent\n",
        "__init__.py": b"raise RuntimeError('excluded initializer')\n",
        "test_example.py": b"not valid Python because tests are excluded",
        "example_test.py": b"also excluded",
        "smell-catalog.md": b"Reference text is data, not a Python module.\n",
    }


def test_layout_maps_actual_static_edges_counts_and_cycle_safe_clusters_without_import(inputs):
    expected = {
        "files": [
            {
                "name": "agent.py",
                "lines": 3,
                "imports": ["agent_loop.py", "agent_tools.py", "leaf.py"],
            },
            {"name": "agent_loop.py", "lines": 2, "imports": ["agent_tools.py"]},
            {"name": "agent_tools.py", "lines": 3, "imports": ["leaf.py", "other.py"]},
            {"name": "leaf.py", "lines": 2, "imports": ["agent.py"]},
            {"name": "other.py", "lines": 1, "imports": []},
        ],
        "prefix_clusters": [
            {
                "prefix": "agent",
                "files": ["agent.py", "agent_loop.py", "agent_tools.py"],
                "lines": 8,
            }
        ],
        "import_tree_clusters": [
            {
                "root": "agent.py",
                "files": ["agent.py", "agent_loop.py", "agent_tools.py", "leaf.py", "other.py"],
                "lines": 11,
            }
        ],
    }
    assert layout_reference(inputs) == expected
    result = verify({"id": LAYOUT}, json.dumps(expected).encode(), "unused", inputs)
    assert result["passed"] and not result["source_executed"]
    assert not result["architectural_quality_verified"]


def test_layout_prefix_groups_retain_distinct_nested_groups_and_longest_prefix():
    inputs = {
        n + ".py": b"\n"
        for n in ["agent", "agent_loop", "agent_tools", "agent_tools_io", "agent_tools_db"]
    }
    groups = layout_reference(inputs)["prefix_clusters"]
    assert [(g["prefix"], len(g["files"])) for g in groups] == [
        ("agent", 5),
        ("agent_", 4),
        ("agent_tools", 3),
    ]
    assert layout_reference({"alpha.py": b"", "beta.py": b""}) == {
        "files": [
            {"name": "alpha.py", "lines": 0, "imports": []},
            {"name": "beta.py", "lines": 0, "imports": []},
        ],
        "prefix_clusters": [],
        "import_tree_clusters": [],
    }


@pytest.mark.parametrize(
    "change",
    [
        lambda r: r["files"].pop(),
        lambda r: r["files"][0].update(lines=True),
        lambda r: r["files"][0]["imports"].pop(),
        lambda r: r["files"].reverse(),
        lambda r: r["prefix_clusters"][0].update(prefix="agen"),
        lambda r: r["import_tree_clusters"].clear(),
    ],
)
def test_layout_rejects_missing_invented_or_mistyped_data(inputs, change):
    report = layout_reference(inputs)
    change(report)
    assert not verify_layout_map(inputs, json.dumps(report).encode())["passed"]


@pytest.mark.parametrize("raw", [b"not JSON", b'{"files":[],"files":[]}', b"\xff"])
def test_layout_rejects_malformed_or_duplicate_json(inputs, raw):
    assert not verify_layout_map(inputs, raw)["passed"]


@pytest.mark.parametrize("inputs", [{}, {"../outside.py": b""}, {"__init__.py": b""}])
def test_layout_refuses_unreviewed_input_layout(inputs):
    with pytest.raises(ValueError, match="requires|mapping"):
        layout_reference(inputs)


@pytest.mark.skipif(
    os.environ.get("SKILLC_LOCAL_DOCKER") != "1",
    reason="explicit local isolated-container fixture check",
)
def test_layout_checks_actual_artifact_without_executing_or_changing_sources():
    inputs = {"alpha.py": b"raise RuntimeError('source is data')\n", "beta.py": b""}
    host = subprocess.check_output(
        ["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"], text=True
    ).strip()
    sandbox = Sandbox(host)
    try:
        sandbox.start(inputs, [])
        result = sandbox.execute(
            "import ast,json,pathlib\n"
            "files=[]\n"
            "for p in sorted(pathlib.Path('/inputs').glob('*.py')):\n"
            " raw=p.read_bytes(); ast.parse(raw)\n"
            " files.append({'name':p.name,'lines':len(raw.splitlines()),'imports':[]})\n"
            "pathlib.Path('/work/layout.json').write_text(json.dumps({"
            "'files':files,'prefix_clusters':[],'import_tree_clusters':[]}))\n"
        )
        assert result["status"] == "completed" and result["exit_code"] == 0
        assert verify_layout_map(inputs, sandbox.read("/work/layout.json"))["passed"]
        assert all(sandbox.read("/inputs/" + name) == raw for name, raw in inputs.items())
    finally:
        sandbox.stop()

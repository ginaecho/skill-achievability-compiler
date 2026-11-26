import os
import subprocess

import pytest

from scripts.real_skills_index import INDEX, REFERENCE_FILES, index_reference, verify_reference_index
from scripts.real_skills_pilot import verify
from scripts.real_skills_runtime import Sandbox


@pytest.fixture
def inputs():
    return {"README.md": b"# Existing guide\n\nKeep this paragraph exactly.\n",
            **{name: f"Introductory text\n# Heading {i}\n\n## Later section\n".encode()
               for i, name in enumerate(REFERENCE_FILES)}}


def test_index_preserves_original_and_uses_actual_first_headings_and_relative_links(inputs):
    actual = index_reference(inputs)
    assert actual == inputs["README.md"] + (
        b"\n## Reference index\n\n| File | Type | Description |\n| --- | --- | --- |\n"
        b"| [experiment-patterns.md](../inputs/experiment-patterns.md) | .md | Heading 0 |\n"
        b"| [notebook-structure.md](../inputs/notebook-structure.md) | .md | Heading 1 |\n"
        b"| [quality-checklist.md](../inputs/quality-checklist.md) | .md | Heading 2 |\n"
        b"| [tutorial-patterns.md](../inputs/tutorial-patterns.md) | .md | Heading 3 |\n")
    result = verify({"id": INDEX}, actual, "unused", inputs)
    assert result["passed"] and result["original_prefix_preserved"]
    assert result["rendered_appearance_verified"] is False


@pytest.mark.parametrize("change", [
    lambda raw: raw.replace(b"Keep this paragraph exactly.", b"Rewritten paragraph."),
    lambda raw: b"\n".join(line for line in raw.split(b"\n") if b"Heading 1" not in line),
    lambda raw: raw.replace(b"../inputs/", b"/inputs/"),
    lambda raw: raw + b"| [extra.md](../inputs/extra.md) | .md | Extra |\n",
    lambda raw: raw.replace(b"Heading 2", b"Invented description"),
])
def test_index_rejects_changed_prefix_missing_extra_or_invented_entries(inputs, change):
    result = verify_reference_index(inputs, change(index_reference(inputs)))
    assert not result["passed"] and result["error"]


def test_index_rejects_unreviewed_layout_or_missing_heading(inputs):
    with pytest.raises(ValueError, match="four public references"):
        index_reference({"README.md": inputs["README.md"]})
    inputs["quality-checklist.md"] = b"No document title\n"
    with pytest.raises(ValueError, match="first H1"):
        index_reference(inputs)


@pytest.mark.skipif(os.environ.get("SKILLC_LOCAL_DOCKER") != "1",
                    reason="explicit local isolated-container fixture check")
def test_index_checks_actual_sandbox_file_and_preserves_protected_inputs(inputs):
    host = subprocess.check_output(
        ["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"], text=True).strip()
    sandbox = Sandbox(host)
    try:
        sandbox.start(inputs, ["README.md"])
        result = sandbox.execute(
            "from pathlib import Path\n"
            "rows=['','## Reference index','','| File | Type | Description |','| --- | --- | --- |']\n"
            "for p in sorted(Path('/inputs').glob('*-*.md')):\n"
            " title=next(line[2:].strip() for line in p.read_text().splitlines() if line.startswith('# '))\n"
            " rows.append(f'| [{p.name}](../inputs/{p.name}) | .md | {title} |')\n"
            "with Path('/work/README.md').open('ab') as out:\n"
            " out.write(('\\n'.join(rows)+'\\n').encode())\n")
        assert result["status"] == "completed" and result["exit_code"] == 0
        assert verify_reference_index(inputs, sandbox.read("/work/README.md"))["passed"]
        assert all(sandbox.read("/inputs/" + name) == raw for name, raw in inputs.items())
    finally:
        sandbox.stop()

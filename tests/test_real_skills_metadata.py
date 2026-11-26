import os
import subprocess
from hashlib import sha256
from html import escape
from pathlib import Path

import pytest

from scripts.real_skills_metadata import (
    DESCRIPTION, METADATA, PREVIEW_METADATA, metadata_reference, verify_preview_metadata,
)
from scripts.real_skills_pilot import verify
from scripts.real_skills_runtime import Sandbox


@pytest.fixture
def inputs():
    return {"report.html": (
        b'<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n'
        b'<title>AutoML Model Evaluation Report</title>\n<style>p {color: navy}</style>\n'
        b'</head>\n<body><h1>AutoML Model Evaluation Report</h1>'
        b'<p>{{model_name}} &amp; {{accuracy}}</p></body>\n</html>\n')}


def test_metadata_checks_actual_artifact_and_preserves_every_original_byte(inputs):
    actual = metadata_reference(inputs)
    assert b"visualizations &amp; conclusions" in actual
    result = verify({"id": METADATA}, actual, "unused", inputs)
    assert result["passed"] and result["original_bytes_preserved"]
    assert result["metadata"] == PREVIEW_METADATA
    assert not result["external_indexing_or_social_preview_verified"]
    assert not result["access_control_verified"]


def test_metadata_accepts_equivalent_quoting_order_and_self_closing_tags(inputs):
    insertion = (f"<META content='noindex, nofollow' NAME='robots' />\n"
                 f"<meta content='{escape(DESCRIPTION, quote=True)}' name='DESCRIPTION'>\n")
    actual = inputs["report.html"].replace(b"</head>", insertion.encode() + b"</head>")
    assert verify_preview_metadata(inputs, actual)["passed"]


@pytest.mark.parametrize("change", [
    lambda raw: raw.replace(b"noindex, nofollow", b"index, follow"),
    lambda raw: raw.replace(b'<meta name="robots"', b'<meta name="other"'),
    lambda raw: raw.replace(b'<meta name="robots"', b'<meta name="robots" NAME="robots"'),
    lambda raw: raw.replace(b'<meta name="robots"', b'<meta name="robots" http-equiv="refresh"'),
    lambda raw: raw.replace(b'    <meta name="robots" content="noindex, nofollow">\n', b""),
    lambda raw: raw.replace(b"</head>", b'<meta name="robots" content="index, follow"></head>'),
    lambda raw: raw.replace(b"</head>", b"<!-- changed --></head>"),
    lambda raw: raw.replace(b"</head>", b"<script>void 0</script></head>"),
    lambda raw: raw.replace(b"</head>", b"<?preview?></head>"),
    lambda raw: raw.replace(b"</head>", b"<!DOCTYPE html></head>"),
    lambda raw: raw.replace(b"</head>", b"</meta></head>"),
    lambda raw: raw.replace(b"</head>", b"<head></head>"),
    lambda raw: raw.replace(b"</head>", b"\xff</head>"),
    lambda raw: raw.replace(b"color: navy", b"color: red"),
    lambda raw: raw.replace(b"{{model_name}}", b"Invented model"),
    lambda raw: raw.replace(b"</head>", b"</head><meta name='robots' content='index'>"),
])
def test_metadata_rejects_missing_conflicting_hidden_or_unrelated_changes(inputs, change):
    result = verify_preview_metadata(inputs, change(metadata_reference(inputs)))
    assert not result["passed"] and result["error"]


def test_metadata_rejects_unmodified_input_and_metadata_moved_into_the_body(inputs):
    original = inputs["report.html"]
    assert not verify_preview_metadata(inputs, original)["passed"]
    insertion = metadata_reference(inputs)[len(original.partition(b"</head>")[0]):]
    moved = original.replace(b"</body>", insertion.partition(b"</head>")[0] + b"</body>")
    assert not verify_preview_metadata(inputs, moved)["passed"]


@pytest.mark.parametrize("inputs", [
    {"other.html": b"<head></head>"}, {"report.html": b"<head>"},
    {"report.html": b"</head><head>"}, {"report.html": b"<head></head><head></head>"},
    {"report.html": b"<head>\xff</head>"},
])
def test_metadata_rejects_unreviewed_input_layout(inputs):
    with pytest.raises(ValueError):
        metadata_reference(inputs)


@pytest.mark.skipif(os.environ.get("SKILLC_LOCAL_DOCKER") != "1",
                    reason="explicit local isolated-container fixture check")
@pytest.mark.parametrize("public_template", [False, True])
def test_metadata_verifies_real_sandbox_deliverables_and_preserves_public_input(inputs, public_template):
    if public_template:
        path = (Path(__file__).resolve().parents[1] / "runs" / "20261106_real_skills"
                / "reviewed-metadata" / METADATA / "report.html")
        raw = path.read_bytes()
        assert sha256(raw).hexdigest() == "bc27b226c4c65d0567721be60a65e799b7511ef72c545277a68cc3a0729f7a8f"
        inputs = {"report.html": raw}
    host = subprocess.check_output(
        ["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"], text=True).strip()
    sandbox = Sandbox(host)
    try:
        sandbox.start(inputs, [])
        insertion = ('<meta name="robots" content="noindex, nofollow">\n'
                     f'<meta name="description" content="{escape(DESCRIPTION, quote=True)}">\n')
        result = sandbox.execute(
            "from pathlib import Path\n"
            "raw=Path('/inputs/report.html').read_bytes()\n"
            f"insertion={insertion.encode()!r}\n"
            "Path('/work/report.html').write_bytes(raw.replace(b'</head>', insertion+b'</head>'))\n")
        assert result["status"] == "completed" and result["exit_code"] == 0
        assert verify_preview_metadata(inputs, sandbox.read("/work/report.html"))["passed"]
        result = sandbox.execute(
            "from pathlib import Path\n"
            "p=Path('/work/report.html')\n"
            "p.write_bytes(p.read_bytes().replace(b'noindex, nofollow', b'index, follow'))\n")
        assert result["status"] == "completed" and result["exit_code"] == 0
        assert not verify_preview_metadata(inputs, sandbox.read("/work/report.html"))["passed"]
        assert sandbox.read("/inputs/report.html") == inputs["report.html"]
    finally:
        sandbox.stop()

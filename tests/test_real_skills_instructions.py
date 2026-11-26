import os
import subprocess
from types import SimpleNamespace

import pytest

from scripts.real_skills_instructions import (
    INSTRUCTIONS,
    instruction_filesystem_snapshot,
    instruction_reference,
    verify_instruction_migration,
)
from scripts.real_skills_pilot import task_runtime, verify
from scripts.real_skills_runtime import Sandbox

ORIGINAL = b"# Repository guidance\n\nPreserve these bytes.\r\n"
INPUTS = {"CLAUDE.md": ORIGINAL}
CASE = {
    "id": INSTRUCTIONS,
    "runtime_profile": "instruction-files",
    "target": "/work/AGENTS.md",
    "writable_inputs": ["CLAUDE.md"],
}


def test_instruction_migration_requires_both_preservation_and_actual_old_path_absence():
    filesystem = {"old_path_lexists": False, "canonical_regular_file": True}
    result = verify(CASE, ORIGINAL, "unused", INPUTS, filesystem_snapshot=filesystem)
    assert result["passed"] and result["original_bytes_preserved"]
    assert not result["agent_runtime_discovery_verified"]
    assert not result["shared_skills_configuration_verified"]
    for actual, old_exists, regular in [
        (ORIGINAL, True, True),
        (ORIGINAL, False, False),
        (ORIGINAL.replace(b"\r\n", b"\n"), False, True),
        (None, False, True),
    ]:
        observed = {"old_path_lexists": old_exists, "canonical_regular_file": regular}
        failed = verify_instruction_migration(INPUTS, actual, observed)
        assert not failed["passed"] and failed["error"]


def test_instruction_verification_refuses_missing_or_invented_filesystem_evidence():
    with pytest.raises(ValueError, match="filesystem snapshot"):
        verify(CASE, ORIGINAL, "unused", INPUTS)
    with pytest.raises(ValueError, match="actual filesystem"):
        verify_instruction_migration(
            INPUTS, ORIGINAL, {"old_path_lexists": 0, "canonical_regular_file": True}
        )
    with pytest.raises(ValueError, match="nonempty original"):
        instruction_reference({"AGENTS.md": ORIGINAL})


@pytest.mark.parametrize(
    "result",
    [
        {"status": "tool_timeout", "exit_code": None, "output": ""},
        {"status": "completed", "exit_code": 1, "output": "inspection failed"},
        {
            "status": "completed",
            "exit_code": 0,
            "output": '{"old_path_lexists": 0, "canonical_regular_file": true}',
        },
    ],
)
def test_instruction_inspection_does_not_convert_inspection_errors_to_goal_results(result):
    sandbox = SimpleNamespace(execute=lambda code: result)
    with pytest.raises((RuntimeError, ValueError), match="inspection"):
        instruction_filesystem_snapshot(sandbox)


@pytest.mark.parametrize(
    "change",
    [
        {"runtime_profile": "python"},
        {"target": "/work/CLAUDE.md"},
        {"writable_inputs": []},
    ],
)
def test_instruction_runtime_cannot_substitute_a_different_seed_target_or_profile(change):
    with pytest.raises(ValueError, match="instruction task"):
        task_runtime({**CASE, **change})


@pytest.mark.skipif(
    os.environ.get("SKILLC_LOCAL_DOCKER") != "1",
    reason="explicit local isolated-container fixture check",
)
def test_instruction_checks_real_rename_copy_symlinks_and_nonregular_paths():
    host = subprocess.check_output(
        ["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"], text=True
    ).strip()
    assert host.startswith(("npipe:////./pipe/", "unix:///"))
    for root_owned in [True, False]:
        sandbox = Sandbox(host)
        try:
            sandbox.start(INPUTS, ["CLAUDE.md"] if root_owned else [])
            code = (
                "from pathlib import Path\n"
                "old=Path('/work/CLAUDE.md'); new=Path('/work/AGENTS.md')\n"
            )
            if root_owned:
                code += "new.write_bytes(old.read_bytes())\n"
            else:
                code += "old.write_bytes(Path('/inputs/CLAUDE.md').read_bytes()); old.rename(new)\n"
            action = sandbox.execute(code)
            assert action["status"] == "completed" and action["exit_code"] == 0
            observed = instruction_filesystem_snapshot(sandbox)
            assert observed == {"old_path_lexists": root_owned, "canonical_regular_file": True}
            result = verify_instruction_migration(INPUTS, sandbox.read("/work/AGENTS.md"), observed)
            assert result["passed"] is not root_owned
            assert sandbox.read("/inputs/CLAUDE.md") == ORIGINAL
            if not root_owned:
                for code, old_exists, regular in [
                    ("Path('/work/CLAUDE.md').symlink_to('absent.md')", True, True),
                    (
                        "Path('/work/CLAUDE.md').unlink(); "
                        "Path('/work/AGENTS.md').rename('/work/real.md'); "
                        "Path('/work/AGENTS.md').symlink_to('real.md')",
                        False,
                        False,
                    ),
                    (
                        "Path('/work/AGENTS.md').unlink(); Path('/work/AGENTS.md').mkdir()",
                        False,
                        False,
                    ),
                    ("Path('/work/AGENTS.md').rmdir(); os.mkfifo('/work/AGENTS.md')", False, False),
                ]:
                    action = sandbox.execute("from pathlib import Path\nimport os\n" + code)
                    assert action["status"] == "completed" and action["exit_code"] == 0
                    observed = instruction_filesystem_snapshot(sandbox)
                    assert observed["old_path_lexists"] is old_exists
                    assert observed["canonical_regular_file"] is regular
                    assert not verify_instruction_migration(INPUTS, None, observed)["passed"]
        finally:
            sandbox.stop()

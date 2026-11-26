"""Check instruction-file migration from bytes and trusted filesystem observations."""

import hashlib
import json

from scripts.real_skills_runtime import Sandbox

INSTRUCTIONS = "CaliLuke__skills__multi-agent-setup"


def instruction_reference(inputs: dict[str, bytes]) -> bytes:
    if set(inputs) != {"CLAUDE.md"} or not inputs["CLAUDE.md"]:
        raise ValueError("Instruction migration requires one nonempty original CLAUDE.md file")
    inputs["CLAUDE.md"].decode("utf-8")
    return inputs["CLAUDE.md"]


def instruction_filesystem_snapshot(sandbox: Sandbox) -> dict[str, bool]:
    result = sandbox.execute(
        "import json,os,stat\n"
        "try:\n"
        " regular=stat.S_ISREG(os.lstat('/work/AGENTS.md').st_mode)\n"
        "except FileNotFoundError:\n"
        " regular=False\n"
        "print(json.dumps({'old_path_lexists':os.path.lexists('/work/CLAUDE.md'),"
        "'canonical_regular_file':regular}))\n"
    )
    if result["status"] != "completed" or result["exit_code"] != 0:
        raise RuntimeError(f"Instruction filesystem inspection failed: {result}")
    observed = json.loads(result["output"])
    if set(observed) != {"old_path_lexists", "canonical_regular_file"} or any(
        type(value) is not bool for value in observed.values()
    ):
        raise ValueError("Instruction filesystem inspection requires two boolean observations")
    return observed


def verify_instruction_migration(
    inputs: dict[str, bytes], actual: bytes | None, filesystem: dict[str, bool]
) -> dict:
    expected = instruction_reference(inputs)
    if set(filesystem) != {"old_path_lexists", "canonical_regular_file"} or any(
        type(value) is not bool for value in filesystem.values()
    ):
        raise ValueError("Instruction verification requires actual filesystem observations")
    result = {
        "kind": "public_instruction_file_migration",
        "passed": (
            filesystem["canonical_regular_file"]
            and not filesystem["old_path_lexists"]
            and actual == expected
        ),
        "filesystem_snapshot": filesystem,
        "actual_sha256": hashlib.sha256(actual).hexdigest() if actual is not None else None,
        "expected_sha256": hashlib.sha256(expected).hexdigest(),
        "original_bytes_preserved": actual == expected,
        "agent_runtime_discovery_verified": False,
        "shared_skills_configuration_verified": False,
    }
    if not result["passed"]:
        result["error"] = (
            "The canonical regular file, preserved bytes or absent old entry requirement is unmet"
        )
    return result

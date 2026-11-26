"""Check a source-conditioned Markdown index against unchanged public files."""
import hashlib

INDEX = "github__awesome-copilot__update-markdown-file-index"
REFERENCE_FILES = (
    "experiment-patterns.md", "notebook-structure.md",
    "quality-checklist.md", "tutorial-patterns.md",
)


def index_reference(inputs: dict[str, bytes]) -> bytes:
    if set(inputs) != {"README.md", *REFERENCE_FILES}:
        raise ValueError("Index task requires the reviewed guide and four public references")
    original = inputs["README.md"]
    original.decode("utf-8")
    if not original.endswith(b"\n") or b"\n## Reference index\n" in original:
        raise ValueError("Expected the unchanged newline-terminated public guide without an index")
    rows = ["", "## Reference index", "", "| File | Type | Description |",
            "| --- | --- | --- |"]
    for name in sorted(REFERENCE_FILES):
        headings = [line[2:].strip() for line in inputs[name].decode("utf-8").splitlines()
                    if line.startswith("# ")]
        if not headings or not headings[0] or "|" in headings[0]:
            raise ValueError("Expected a nonempty plain first H1 in each public reference")
        rows.append(f"| [{name}](../inputs/{name}) | .md | {headings[0]} |")
    return original + ("\n".join(rows) + "\n").encode("utf-8")


def verify_reference_index(inputs: dict[str, bytes], actual: bytes) -> dict:
    expected = index_reference(inputs)
    result = {
        "kind": "public_markdown_reference_index_artifact",
        "passed": actual == expected,
        "actual_sha256": hashlib.sha256(actual).hexdigest(),
        "expected_sha256": hashlib.sha256(expected).hexdigest(),
        "indexed_files": sorted(REFERENCE_FILES),
        "original_prefix_preserved": actual.startswith(inputs["README.md"]),
        "rendered_appearance_verified": False,
    }
    if not result["passed"]:
        result["error"] = "Actual index differs from the declared file, heading, link or preservation contract"
    return result

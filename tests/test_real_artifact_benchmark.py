import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from skillc import load_profile
from skillc.profiles import Profile

APP = Path(__file__).resolve().parents[1] / "demo" / "skillc-architecture-app"
sys.path.insert(0, str(APP))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, APP / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ARTIFACTS = _load("real_artifacts")
BENCH = _load("benchmark_real_artifacts")
FETCH_SPEC = importlib.util.spec_from_file_location(
    "fetch_copilot_sources",
    Path(__file__).resolve().parents[1] / "scripts" / "fetch_copilot_sources.py",
)
FETCH = importlib.util.module_from_spec(FETCH_SPEC)
FETCH_SPEC.loader.exec_module(FETCH)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _corpus(tmp_path: Path, skills: dict[str, str], copilot: list[tuple]) -> Path:
    benchmark = tmp_path / "benchmark"
    for pool in ARTIFACTS.SKILL_POOLS:
        (benchmark / pool).mkdir(parents=True)
        (benchmark / pool / "sources.json").write_text("[]")
    records = []
    for identifier, text in skills.items():
        (benchmark / "ce_sources" / identifier).mkdir()
        (benchmark / "ce_sources" / identifier / "SKILL.md").write_text(text)
        records.append({"id": identifier, "sha256": _sha(text), "repo_url": "r",
                        "commit": "c", "path_in_repo": "p", "license_spdx": "MIT"})
    (benchmark / "ce_sources" / "sources.json").write_text(json.dumps(records))
    pool = benchmark / "copilot_sources"
    pool.mkdir()
    rows = []
    for kind, name, text in copilot:
        (pool / f"{kind}s").mkdir(parents=True, exist_ok=True)
        (pool / f"{kind}s" / name).write_text(text)
        rows.append({"id": name, "kind": kind, "path": f"{kind}s/{name}",
                     "sha256": _sha(text), "repo_url": "r", "commit": "c",
                     "path_in_repo": name, "license_spdx": "MIT"})
    (pool / "sources.json").write_text(json.dumps(rows))
    return tmp_path


def test_loader_deduplicates_and_assigns_home_runtimes(tmp_path):
    root = _corpus(
        tmp_path,
        {"a": "same text", "b": "same text", "c": "other"},
        [("agent", "x.agent.md", "agent"), ("prompt", "y.prompt.md", "prompt")],
    )

    artifacts, _ = ARTIFACTS.load_real_artifacts(root)

    assert [(a["kind"], a["id"]) for a in artifacts] == [
        ("agent", "x.agent.md"), ("prompt", "y.prompt.md"), ("skill", "a"), ("skill", "c"),
    ]
    assert {a["kind"]: a["home_runtime"] for a in artifacts} == {
        "agent": "vscode-copilot", "prompt": "vscode-copilot", "skill": "claude-code",
    }


def test_loader_excludes_and_reports_modified_artifacts(tmp_path):
    root = _corpus(tmp_path, {"a": "original", "b": "kept"}, [])
    (root / "benchmark" / "ce_sources" / "a" / "SKILL.md").write_text("tampered")

    artifacts, excluded = ARTIFACTS.load_real_artifacts(root)

    assert [a["id"] for a in artifacts] == ["b"]
    assert [(e["id"], e["actual_sha256"]) for e in excluded] == [("a", _sha("tampered"))]


def test_balanced_subset_has_equal_counts_per_kind():
    artifacts = [
        {"kind": kind, "sha256": f"{kind}{index}"}
        for kind, total in (("skill", 5), ("agent", 3), ("prompt", 2))
        for index in range(total)
    ]

    subset = ARTIFACTS.balanced_subset(artifacts)

    counts = {kind: sum(a["kind"] == kind for a in subset) for kind in ("skill", "agent", "prompt")}
    assert counts == {"skill": 2, "agent": 2, "prompt": 2}


def test_frontmatter_tools_cannot_grant_themselves():
    agent = "---\ntools: ['github_create_issue']\n---\nUse `github_create_issue` to file it.\n"

    row = BENCH.evaluate({"content": agent}, load_profile("vscode-copilot"))

    assert row["verdict"] == "IMPOSSIBLE"
    assert row["reason"] == "MISSING_CAPABILITY"
    assert row["frontier"] == ["github_create_issue"]


def test_documented_vscode_tools_are_granted_in_home_runtime():
    agent = "---\ntools: ['editFiles', 'search/codebase']\n---\nUse `editFiles` to apply the fix.\n"

    row = BENCH.evaluate({"content": agent}, load_profile("vscode-copilot"))

    assert row["verdict"] == "ACHIEVABLE"


def test_prose_without_any_operation_abstains():
    row = BENCH.evaluate({"content": "Write clear, friendly release notes."},
                         Profile(name="observed", tools=frozenset({"bash"}), shell=True))

    assert (row["verdict"], row["reason"]) == ("UNKNOWN", "INCOMPLETE_COMPACTION")


def test_copilot_selection_keeps_only_sized_unique_agents_and_prompts():
    body = b"x" * 400
    files = {
        "agents/a.agent.md": body,
        "agents/dup.agent.md": body,
        "prompts/p.prompt.md": b"y" * 400,
        "prompts/tiny.prompt.md": b"z",
        "instructions/i.instructions.md": b"w" * 400,
    }

    records = FETCH.select_sources(files)

    assert [(r["kind"], r["path_in_repo"]) for r in records] == [
        ("agent", "agents/a.agent.md"), ("prompt", "prompts/p.prompt.md"),
    ]

AUDIT = _load("refutation_audit")


def _refutation(*frontier, reason="MISSING_CAPABILITY"):
    return {"verdict": "IMPOSSIBLE", "reason": reason, "frontier": list(frontier)}


def test_refutation_is_confirmed_when_any_frontier_tool_is_real():
    labels = {"max_length": "misextraction", "create_issue": "absent_tool"}

    assert AUDIT.classify(_refutation("max_length", "create_issue"), set(), labels) == "confirmed"
    assert AUDIT.classify(_refutation("editfiles"), {"editfiles"}, labels) == "confirmed"


def test_refutation_made_only_of_misextractions_is_false():
    labels = {"max_length": "misextraction"}

    assert AUDIT.classify(_refutation("max_length"), set(), labels) == "false_refutation"
    assert AUDIT.classify(_refutation("mystery"), set(), labels) == "unlabeled"
    assert AUDIT.classify({"verdict": "ACHIEVABLE"}, set(), labels) is None


def test_audit_precision_ignores_unlabelled_refutations():
    summary = AUDIT.summarize(["confirmed", "confirmed", "confirmed", "false_refutation", "unlabeled"])

    assert summary["precision"] == 0.75
    assert summary["unlabeled"] == 1


def test_shipped_labels_are_disjoint():
    data = json.loads(AUDIT.LABELS_PATH.read_text(encoding="utf-8"))["labels"]
    groups = [set(names) for names in data.values()]

    assert all(not (a & b) for i, a in enumerate(groups) for b in groups[i + 1:])

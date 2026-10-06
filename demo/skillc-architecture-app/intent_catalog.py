"""Catalog of tested intents for the Execution Atlas.

Two suites:

* Topics: one intent written natively three times (SKILL.md, agent.md, prompt)
  plus the environment it is judged against (`environment.json`, a SkillC
  runtime manifest). Selecting any form loads all three siblings.
* Real public artifacts: externally published files, each in its own native
  form only; nothing is generated for the other forms.

Expected labels stay in the catalog for scoring and are never shown as names.
"""
from __future__ import annotations

import json
import re
import subprocess
from functools import lru_cache
from pathlib import Path

from real_artifacts import balanced_subset, load_real_artifacts
from skillc.profiles import load_profile

CATALOG_BRANCH = "gc/data_train_test"
TOPICS_DIR = "corpus/intents"
INPUT_FORMS = ("skill", "agent", "prompt")
FORM_FILES = {"skill": "SKILL.md", "agent": "agent.md", "prompt": "prompt.md"}
FORM_LABELS = {"skill": "SKILL.md", "agent": "agent.md", "prompt": "prompt"}
TOPIC_SUITE = "Topics"
REAL_SUITE = "Real public artifacts"
VERDICT_SUFFIX_RE = re.compile(
    r"(?:[\s_-]+(?:achievable|impossible|unknown))\s*$",
    re.IGNORECASE,
)


@lru_cache(maxsize=2)
def load_catalog(repo_root: Path, data_root: Path | None = None) -> dict:
    read, list_topics = (
        _worktree_reader(data_root) if data_root else _branch_reader(repo_root)
    )
    entries = [*_topic_entries(read, list_topics()), *_real_entries(data_root)]
    catalog = {
        "branch": f"{CATALOG_BRANCH} (working tree)" if data_root else CATALOG_BRANCH,
        "count": len(entries),
        "entries": entries,
    }
    if not entries:
        catalog["hint"] = (
            f"No tested intents found. Fetch {CATALOG_BRANCH} from the upstream "
            "SkillC repository, or pass --catalog-root PATH_TO_DATA_CHECKOUT.")
    return catalog


class CatalogError(RuntimeError):
    """The catalog data checkout or branch cannot be read."""


def _topic_entries(read, topic_ids: list[str]) -> list[dict]:
    entries = []
    for topic_id in sorted(topic_ids):
        base = f"{TOPICS_DIR}/{topic_id}"
        topic = json.loads(read(f"{base}/topic.json"))
        environment = json.loads(read(f"{base}/environment.json"))
        for form in INPUT_FORMS:
            entries.append({
                "id": f"topic:{topic_id}:{form}",
                "base_id": f"topic:{topic_id}",
                "name": topic["title"],
                "suite": TOPIC_SUITE,
                "category": topic["category"],
                "display_category": _display_category(topic["category"]),
                "expected": topic.get("expected"),
                "input_type": form,
                "form_provenance": "authored for this topic",
                "profile": "none",
                "environment_grants": sorted(environment["tools"]),
                "environment_manifest": environment,
                "content": read(f"{base}/{FORM_FILES[form]}"),
                "source_path": f"{base}/{FORM_FILES[form]}",
                "note": topic.get("note", ""),
            })
    return entries


def _real_entries(data_root: Path | None) -> list[dict]:
    if data_root is None:
        return []
    artifacts, _ = load_real_artifacts(data_root)
    if len({artifact["kind"] for artifact in artifacts}) < len(INPUT_FORMS):
        return []
    grants = {
        runtime: sorted(load_profile(runtime).tools)
        for runtime in {artifact["home_runtime"] for artifact in artifacts}
    }
    return [
        {
            "id": f"real:{artifact['kind']}:{artifact['id']}",
            "base_id": f"real:{artifact['kind']}:{artifact['id']}",
            "name": _real_name(artifact),
            "suite": REAL_SUITE,
            "category": artifact["pool"],
            "display_category": f"{artifact['license_spdx']} · {artifact['home_runtime']}",
            "expected": None,
            "input_type": artifact["kind"],
            "form_provenance": "original upstream file",
            "profile": artifact["home_runtime"],
            "environment_grants": grants[artifact["home_runtime"]],
            "environment_manifest": None,
            "content": artifact["content"],
            "source_path": artifact["path_in_repo"],
            "source_url": artifact["repo_url"],
            "note": f"{artifact['repo_url']}@{artifact['commit'][:8]}",
        }
        for artifact in sorted(
            balanced_subset(artifacts), key=lambda item: (item["kind"], item["id"]))
    ]


def _real_name(artifact: dict) -> str:
    owner_repo = artifact["repo_url"].removeprefix("https://github.com/")
    stem = Path(artifact["path_in_repo"]).name.split(".")[0]
    if stem.upper() == "SKILL":
        stem = Path(artifact["path_in_repo"]).parent.name
    return f"{owner_repo}: {_case_name(stem)}"


def _case_name(case_id: str) -> str:
    """Human-readable case name without leaking an expected verdict."""
    return VERDICT_SUFFIX_RE.sub("", case_id).replace("_", " ").replace("-", " ")


def _display_category(category: str) -> str:
    return "GENERAL CASE" if category.upper() in {
        "ACHIEVABLE", "IMPOSSIBLE", "UNKNOWN"
    } else category


def _worktree_reader(data_root: Path):
    def read(path: str) -> str:
        return (data_root / path).read_text(encoding="utf-8")

    def list_topics() -> list[str]:
        root = data_root / TOPICS_DIR
        if not root.is_dir():
            return []
        return [path.name for path in root.iterdir() if (path / "topic.json").is_file()]

    return read, list_topics


def _branch_reader(repo_root: Path):
    ref = f"origin/{CATALOG_BRANCH}"

    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args], cwd=repo_root, capture_output=True, text=True,
            encoding="utf-8", errors="replace", check=False,
        )

    def read(path: str) -> str:
        # `./` resolves from repo_root, so a SkillC copy vendored in a subfolder still works.
        result = git("show", f"{ref}:./{path}")
        if result.returncode != 0:
            raise CatalogError(
                f"cannot read {path} from {ref}; fetch the upstream data branch "
                "or pass --catalog-root PATH_TO_DATA_CHECKOUT")
        return result.stdout

    def list_topics() -> list[str]:
        result = git("ls-tree", "-r", "--name-only", ref, TOPICS_DIR)
        return sorted({
            Path(path).parent.name for path in result.stdout.splitlines()
            if path.endswith("/topic.json")
        }) if result.returncode == 0 else []

    return read, list_topics

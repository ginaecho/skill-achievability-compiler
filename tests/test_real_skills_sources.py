import hashlib
import json
from io import BytesIO

import pytest

from scripts import real_skills_sources as sources


def record(path, raw):
    return {
        "id": "owner__repo__skill", "repo_url": "https://github.com/owner/repo",
        "commit": "a" * 40, "path_in_repo": path, "license_spdx": "MIT",
        "license_file": "LICENSE", "sha256": hashlib.sha256(raw).hexdigest(),
    }


def test_pin_uses_matching_bytes_not_first_record_with_colliding_id():
    first = record("plugins/old/SKILL.md", b"old")
    second = record("plugins/new/SKILL.md", b"new")
    assert sources.choose_source([first, second], b"new")["path_in_repo"] == second["path_in_repo"]
    with pytest.raises(ValueError, match="Expected one provenance"):
        sources.choose_source([first, second], b"not preserved")


def test_input_inventory_reads_utf8_tree_metadata_without_locale_defaults(tmp_path):
    case = sources.source_record(record("skill/SKILL.md", b"skill"))
    cohort = tmp_path / "cohort.json"
    cohort.write_text(json.dumps({"cases": [case]}), encoding="utf-8")
    cache = tmp_path / "cache"
    (cache / "trees").mkdir(parents=True)
    (cache / "bundles").mkdir()
    name = "fixtures/\u4e81.csv"
    tree = {"tree": [{
        "path": name, "mode": "100644", "type": "blob", "size": 20, "sha": "b" * 40,
    }]}
    (cache / "trees" / (case["commit"] + ".json")).write_bytes(
        json.dumps(tree, ensure_ascii=False).encode("utf-8"))
    (cache / "bundles" / (case["id"] + ".json")).write_text(json.dumps({
        "source": case, "files": [{"path": name, "sha256": "c" * 64}],
    }), encoding="utf-8")
    output = tmp_path / "inventory.json"
    sources.inventory_inputs(cohort, cache, output)
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["cases"][0]["bundled_candidates"][0]["path"] == name
    assert result["cases"][0]["review_status"] == "not_reviewed_by_this_inventory"


def test_references_resolve_parent_paths_and_plugin_shared_files():
    paths = {
        "plugins/demo/.claude-plugin/plugin.json",
        "plugins/demo/shared/config.json",
        "plugins/demo/skills/first/SKILL.md",
        "plugins/demo/skills/first/scripts/run.py",
        "plugins/demo/skills/second/SKILL.md",
        "plugins/demo/skills/second/scripts/helper.py",
        "plugins/demo/skills/unrelated/SKILL.md",
        "outside/reference.txt",
    }
    result = sources.referenced_paths(
        paths, "plugins/demo/skills/first/SKILL.md",
        "Read [the other skill](../second/SKILL.md) and `outside/reference.txt`.")
    assert result == paths - {"plugins/demo/skills/unrelated/SKILL.md"}


@pytest.mark.parametrize("name,mode,size,reason", [
    ("model.safetensors", "100644", 10, "potential_model_weights_or_serialized_model"),
    ("weights/config.json", "100644", 10, "potential_model_weights_or_serialized_model"),
    ("model.bin", "100644", 10, "potential_model_weights_or_serialized_model"),
    ("script.py", "120000", 10, "symlink_or_submodule"),
    ("data.csv", "100644", 2_000_001, "larger_than_2MB"),
    ("scripts/helper.py", "100644", 10, None),
])
def test_no_weights_symlinks_or_oversized_downloads(name, mode, size, reason):
    assert sources.withheld_reason(
        {"path": name, "mode": mode, "size": size, "type": "blob"}) == reason


def test_corrupt_cached_blob_is_rejected_without_network(tmp_path):
    case = {"id": "demo"}
    raw = b"expected"
    blob = hashlib.sha1(b"blob 8\0" + raw).hexdigest()
    path = tmp_path / "objects" / blob
    path.parent.mkdir()
    path.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="Pinned commit blob mismatch"):
        sources.fetch_blob(case, {"sha": blob, "size": len(raw), "path": "SKILL.md"}, tmp_path)


def test_recovery_keeps_root_folder_and_license_but_never_downloads_weights(tmp_path, monkeypatch):
    main = b"# A real task"
    case = sources.source_record(record("SKILL.md", main))
    payloads = {"SKILL.md": main, "LICENSE": b"MIT", "helper.py": b"pass", "model.pt": b"weights"}
    entries = []
    for name, raw in payloads.items():
        entries.append({
            "path": name, "size": len(raw), "type": "blob", "mode": "100644",
            "sha": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest(),
        })
    trees = tmp_path / "trees"
    trees.mkdir()
    (trees / (case["commit"] + ".json")).write_text(json.dumps({
        "sha": "b" * 40, "truncated": False, "tree": entries,
    }))
    cohort = tmp_path / "cohort.json"
    cohort.write_text(json.dumps({"cases": [case]}))
    requests = []

    def fake_open(address, timeout):
        requests.append(address)
        name = address.rsplit("/", 1)[1]
        assert name != "model.pt"
        return BytesIO(payloads[name])

    monkeypatch.setattr(sources, "urlopen", fake_open)
    sources.recover(cohort, tmp_path)
    sources.recover(cohort, tmp_path)
    assert len(requests) == 3
    result = json.loads((tmp_path / "bundles" / (case["id"] + ".json")).read_text())
    assert {item["path"] for item in result["files"]} == {"SKILL.md", "LICENSE", "helper.py"}
    assert result["withheld"] == [{
        "path": "model.pt", "reason": "potential_model_weights_or_serialized_model",
    }]
    assert result["status"] == "recovered_with_withheld_files"


@pytest.mark.parametrize("address", [
    "http://github.com/owner/repo",
    "https://github.com.attacker.invalid/owner/repo",
    "https://user:secret@github.com/owner/repo",
    "https://github.com/owner/repo/extra",
])
def test_source_repository_rejects_untrusted_addresses(address):
    with pytest.raises(ValueError):
        sources.repository(address)
def test_input_candidates_are_metadata_not_automatic_task_approval():
    from scripts.real_skills_sources import input_candidates

    def entry(path, mode="100644", kind="blob"):
        return {"path": path, "mode": mode, "type": kind, "size": 20, "sha": "a" * 40}

    candidates = input_candidates([
        entry("examples/input.csv"), entry("skill/fixtures/request.json"),
        entry("examples/model.safetensors"), entry("examples/SKILL.md"),
        entry("examples/linked", mode="120000"), entry("docs/reference.md"),
        entry("examples/folder", mode="040000", kind="tree"),
    ])
    assert [item["path"] for item in candidates] == [
        "examples/input.csv", "skill/fixtures/request.json"]

"""Pin real skill inputs and recover their source bundles. Never execute them."""
from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmark.real2.select_real2 import REFS  # noqa: E402

HISTORICAL = (
    "runs/20260928_i2l/jb",
    "runs/20260927_ext/ext_ce_rt",
    "runs/20260928_div/div_ce_rt",
    "runs/20261001_gr/gr_ce_rt",
)
WEIGHT_EXTENSIONS = {
    ".bin", ".ckpt", ".ggml", ".gguf", ".h5", ".hdf5", ".joblib", ".msgpack",
    ".npy", ".npz", ".onnx", ".ot", ".pb", ".pickle", ".pkl", ".pt", ".pth",
    ".safetensors", ".tflite",
}
MAX_FILE = 2_000_000
INPUT_FOLDERS = {"examples", "example", "fixtures", "fixture", "samples", "sample",
                 "testdata", "data", "datasets"}


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def read_git(ref: str, path: str) -> bytes:
    return git("show", f"{ref}:{path}")


def repository(value: str) -> str:
    parsed = urlsplit(value if "://" in value else "https://" + value)
    if (parsed.scheme != "https" or parsed.netloc != "github.com"
            or parsed.query or parsed.fragment):
        raise ValueError("Source must be a public GitHub repository")
    name = parsed.path.strip("/").removesuffix(".git")
    if (not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", name)
            or any(part in {".", ".."} for part in name.split("/"))):
        raise ValueError("Invalid source repository")
    return name


def source_record(source: dict) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", source["id"]):
        raise ValueError("Invalid source identifier")
    if not re.fullmatch(r"[0-9a-f]{40}", source["commit"]):
        raise ValueError("Source commit must be immutable")
    if not re.fullmatch(r"[0-9a-f]{64}", source["sha256"]):
        raise ValueError("Source content must have a SHA256 digest")
    path = source["path_in_repo"]
    parts = PurePosixPath(path).parts
    if not parts or path.startswith("/") or "\\" in path or ".." in parts:
        raise ValueError("Invalid source path")
    return {
        "id": source["id"],
        "repository": repository(source.get("repo_url") or "github.com/" + source["repository"]),
        "commit": source["commit"], "path_in_repo": path,
        "sha256": source["sha256"],
        "license": source.get("license_spdx", source.get("license")),
        "license_file": source["license_file"],
    }


def choose_source(candidates: list[dict], raw: bytes) -> dict:
    digest = hashlib.sha256(raw).hexdigest()
    matches = [source_record(c) for c in candidates if c["sha256"] == digest]
    if len(matches) != 1:
        raise ValueError(f"Expected one provenance record matching source bytes; got {len(matches)}")
    return matches[0]


def freeze(ref: str, destination: Path) -> None:
    commit = git("rev-parse", ref).decode().strip()
    manifests = {}
    chosen: dict[str, dict] = {}
    alternatives = []
    for directory in HISTORICAL:
        cases = json.loads(read_git(commit, directory + "/frozen.json"))["cases"]
        for case in cases:
            if directory.endswith("/jb") and case["set"] not in ("heldout", "fresh"):
                continue
            corpus = case.get("corpus", "ce_sources")
            if corpus == "ce_sources_created":
                continue
            sid = case.get("skill", case["id"])
            if corpus not in manifests:
                manifests[corpus] = json.loads(
                    read_git(commit, f"benchmark/{corpus}/sources.json"))
            candidates = [s for s in manifests[corpus] if s["id"] == sid]
            raw = read_git(commit, f"benchmark/{corpus}/{sid}/SKILL.md")
            source = choose_source(candidates, raw)
            source["origin"] = f"{commit}:benchmark/{corpus}/{sid}/SKILL.md"
            previous = chosen.setdefault(sid, source)
            if previous["sha256"] != source["sha256"] and source not in alternatives:
                alternatives.append(source)
    newer = json.loads((ROOT / "benchmark" / "real2" / "cases.json").read_text(
        encoding="utf-8"))["cases"]
    for source in newer:
        sid = source["id"]
        if sid in chosen:
            raise ValueError(f"Newer input unexpectedly reuses source identifier: {sid}")
        raw = (ROOT / "benchmark" / "real2" / "sources" / sid / "SKILL.md").read_bytes()
        chosen[sid] = choose_source([source], raw)
        chosen[sid]["origin"] = "benchmark/real2/cases.json"
    if len(chosen) != 719 or len({s["sha256"] for s in chosen.values()}) != 719:
        raise ValueError("The agreed cohort must contain 719 IDs and distinct texts")
    result = {
        "schema": 1, "created_at": datetime.now(timezone.utc).isoformat(),
        "historical_commit": commit,
        "selection_rule": "First frozen occurrence per legacy ID, in chronological cohort order; "
                          "metadata must match the preserved source bytes. Include all newer IDs.",
        "identity_warning": "Legacy IDs use a basename and can collide across different skill paths. "
                            "Excluded alternatives are disclosed; they are not assumed equivalent.",
        "models": ["gpt-5.4", "gpt-5.6-sol"], "repeats": 5,
        "planned_compaction_sessions": 7190, "planned_execution_sessions": 7190,
        "runtime_protocol_status": "Not frozen; source recovery and task safety review first",
        "excluded_alternatives": alternatives,
        "cases": sorted(chosen.values(), key=lambda s: s["id"]),
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    print(f"Pinned {len(chosen)} real source documents; {len(alternatives)} alternative excluded.")


def referenced_paths(paths: set[str], skill_path: str, text: str) -> set[str]:
    folder = str(PurePosixPath(skill_path).parent)
    own = {p for p in paths if folder == "." or p.startswith(folder + "/")}
    selected = set(own)
    skill_dirs = {str(PurePosixPath(p).parent) for p in paths
                  if PurePosixPath(p).name == "SKILL.md"}
    parents = PurePosixPath(folder).parents
    plugin = next((str(p) for p in (PurePosixPath(folder), *parents)
                   if f"{p}/.claude-plugin/plugin.json" in paths), None)
    parts = PurePosixPath(folder).parts
    if plugin is None and "plugins" in parts:
        index = parts.index("plugins")
        if len(parts) > index + 2:
            plugin = str(PurePosixPath(*parts[:index + 2]))
    if plugin:
        selected.update(p for p in paths if p.startswith(plugin + "/") and not any(
            p.startswith(d + "/") for d in skill_dirs if d.startswith(plugin + "/")))
    for pattern in REFS:
        for match in pattern.findall(text):
            ref = match.split("#")[0].rstrip(".,;:)`'\"")
            if not ref or ref.startswith("/"):
                continue
            for candidate in (posixpath.normpath(posixpath.join(folder, ref)),
                              posixpath.normpath(ref)):
                if candidate.startswith("../"):
                    continue
                if candidate in paths:
                    selected.add(candidate)
                    if candidate.endswith("/SKILL.md"):
                        parent = str(PurePosixPath(candidate).parent)
                        selected.update(p for p in paths if p.startswith(parent + "/"))
                    break
                if candidate in skill_dirs:
                    selected.update(p for p in paths if p.startswith(candidate + "/"))
                    break
    return selected


def withheld_reason(entry: dict) -> str | None:
    if entry["mode"] == "120000" or entry["type"] != "blob":
        return "symlink_or_submodule"
    path = PurePosixPath(entry["path"])
    if (path.suffix.lower() in WEIGHT_EXTENSIONS
            or any(p.lower() in {"weights", "checkpoints", "adapters"} for p in path.parts)):
        return "potential_model_weights_or_serialized_model"
    if entry.get("size", MAX_FILE + 1) > MAX_FILE:
        return "larger_than_2MB"
    return None


def fetch_blob(case: dict, entry: dict, cache: Path) -> tuple[bytes, str]:
    if not re.fullmatch(r"[0-9a-f]{40}", entry["sha"]):
        raise ValueError("Invalid Git blob identifier")
    path = cache / "objects" / entry["sha"]
    if path.exists():
        raw = path.read_bytes()
    else:
        address = (f'https://raw.githubusercontent.com/{case["repository"]}/'
                   f'{case["commit"]}/{quote(entry["path"], safe="/")}')
        with urlopen(address, timeout=30) as response:
            raw = response.read(MAX_FILE + 1)
    if len(raw) != entry["size"] or len(raw) > MAX_FILE:
        raise ValueError(f'Unexpected file size: {case["id"]}: {entry["path"]}')
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    if blob != entry["sha"]:
        raise ValueError(f'Pinned commit blob mismatch: {case["id"]}: {entry["path"]}')
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(raw)
    return raw, hashlib.sha256(raw).hexdigest()


def recover(cohort: Path, cache: Path) -> None:
    data = json.loads(cohort.read_text(encoding="utf-8"))
    cache.mkdir(parents=True, exist_ok=True)
    for case in data["cases"]:
        source_record(case)
        output = cache / "bundles" / (case["id"] + ".json")
        if output.exists():
            saved = json.loads(output.read_text(encoding="utf-8"))
            if saved["source"] != case:
                raise ValueError(f'Existing bundle has different provenance: {case["id"]}')
            for item in saved["files"]:
                raw = (cache / "objects" / item["git_blob"]).read_bytes()
                if hashlib.sha256(raw).hexdigest() != item["sha256"]:
                    raise ValueError(f'Existing bundle object is corrupt: {case["id"]}')
            print(f'Verified existing bundle: {case["id"]}', flush=True)
            continue
        tree_cache = cache / "trees" / (case["commit"] + ".json")
        if not tree_cache.exists():
            request = f'repos/{case["repository"]}/git/trees/{case["commit"]}?recursive=1'
            raw_tree = subprocess.check_output(["gh", "api", request])
            tree_cache.parent.mkdir(parents=True, exist_ok=True)
            tree_cache.write_bytes(raw_tree)
        tree = json.loads(tree_cache.read_bytes())
        if tree.get("truncated"):
            raise ValueError(f'Truncated repository tree: {case["id"]}')
        entries = {item["path"]: item for item in tree["tree"]}
        main = entries[case["path_in_repo"]]
        reason = withheld_reason(main)
        if reason:
            raise ValueError(f'SKILL.md cannot be fetched: {case["id"]}: {reason}')
        text, digest = fetch_blob(case, main, cache)
        if digest != case["sha256"]:
            raise ValueError(f'Original SKILL.md does not match preserved input: {case["id"]}')
        selected = referenced_paths(set(entries), case["path_in_repo"], text.decode("utf-8"))
        license_path = case["license_file"]
        if license_path not in entries:
            raise ValueError(f'Pinned license file is missing: {case["id"]}')
        if withheld_reason(entries[license_path]):
            raise ValueError(f'Pinned license file cannot be recovered: {case["id"]}')
        selected.add(license_path)
        files, withheld = [], []
        for name in sorted(selected):
            entry = entries[name]
            if entry["type"] == "tree":
                continue
            reason = withheld_reason(entry)
            if reason:
                withheld.append({"path": name, "reason": reason})
                continue
            _, digest = fetch_blob(case, entry, cache)
            files.append({"path": name, "sha256": digest, "git_blob": entry["sha"],
                          "bytes": entry["size"]})
        bundle = {"source": case, "files": files, "withheld": withheld,
                  "status": "recovered_with_withheld_files" if withheld else "recovered",
                  "scope": "Whole skill folder, shared plugin files, directly referenced "
                           "repository files or skill folders, and the declared license",
                  "task_execution_eligibility": "pending_independent_safety_and_dependency_review"}
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as handle:
            json.dump(bundle, handle, indent=2)
            handle.write("\n")
        print(f'Recovered {case["id"]}: {len(files)} files; {len(withheld)} withheld', flush=True)


def input_candidates(entries: list[dict]) -> list[dict]:
    result = []
    for entry in entries:
        path = PurePosixPath(entry["path"])
        if (entry["type"] == "blob" and withheld_reason(entry) is None
                and INPUT_FOLDERS.intersection(p.lower() for p in path.parts[:-1])
                and path.name != "SKILL.md"):
            result.append({"path": entry["path"], "git_blob": entry["sha"],
                           "bytes": entry["size"]})
    return sorted(result, key=lambda item: item["path"])


def inventory_inputs(cohort: Path, cache: Path, output: Path) -> None:
    data = json.loads(cohort.read_text(encoding="utf-8"))
    repositories, cases = {}, []
    for case in data["cases"]:
        source_record(case)
        key = case["repository"] + "@" + case["commit"]
        if key not in repositories:
            tree = json.loads((cache / "trees" / (case["commit"] + ".json")).read_bytes())
            if tree.get("truncated"):
                raise ValueError(f'Truncated input search: {case["id"]}')
            repositories[key] = input_candidates(tree["tree"])
        bundle = json.loads((cache / "bundles" / (case["id"] + ".json")).read_text())
        if bundle["source"] != case:
            raise ValueError(f'Input search bundle provenance differs: {case["id"]}')
        recovered = {f["path"]: f for f in bundle["files"]}
        bundled = [{**item, "sha256": recovered[item["path"]]["sha256"]}
                   for item in repositories[key] if item["path"] in recovered]
        cases.append({
            "id": case["id"], "repository_commit": key,
            "bundled_candidates": bundled, "review_status": "not_reviewed_by_this_inventory",
        })
    result = {
        "scope": "Metadata-only candidate search in pinned source repositories; no code executed "
                 "and no additional files downloaded. Separate frozen task manifests govern "
                 "any reviewed selections.",
        "warning": "A filename is not proof of usable input, a reusable license, a safe task "
                   "or an independent verifier. Zero candidates does not prove that no public "
                   "input exists elsewhere, and does not authorize a constructed fallback.",
        "repositories": repositories, "cases": cases,
    }
    with output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    print(f"Indexed public-input candidates for {len(cases)} sources in "
          f"{len(repositories)} pinned repository versions; "
          f"{sum(bool(c['bundled_candidates']) for c in cases)} sources have bundled candidates.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("freeze", "recover", "inventory-inputs"))
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--data-ref", default="origin/gc/data_train_test")
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "freeze":
        freeze(args.data_ref, args.cohort)
    elif args.cache is None:
        parser.error(f"{args.command} requires --cache outside the repository")
    elif args.cache.resolve().is_relative_to(ROOT.resolve()):
        parser.error("source recovery cache must be outside the repository")
    elif args.command == "inventory-inputs":
        if args.output is None:
            parser.error("inventory-inputs requires --output")
        inventory_inputs(args.cohort, args.cache, args.output)
    else:
        recover(args.cohort, args.cache)


if __name__ == "__main__":
    main()

"""Seal held-out material and freeze the six reviewed new-task collections (no model calls)."""
from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from scripts import real_skills_newtasks as nt  # noqa: E402
from scripts.real_skills_pilot import (  # noqa: E402
    IMAGE, implementation_files, task_runtime,
)

CHECKER_COMMIT = "184d7db2ba96f4286dc58ac68f19051e31c8a759"
CHECKER_REPOSITORY = "ginaecho/skill-achievability-compiler"
MODELS = ["gpt-5.3-codex", "gpt-5.6-sol", "claude-opus-5.5"]
ACCOUNT = "tzuchunchen_microsoft"
COLLECTIONS = {
    "gh-fetch": "reviewed-gh-fetch",
    "shopify-signature": "reviewed-shopify-signature",
    "shopify-port": "reviewed-shopify-port",
    "personal-command": "reviewed-personal-command",
    "skill-name": "reviewed-skill-name",
    "devcontainer": "reviewed-devcontainer",
}
NAMESPACES = {key: f"public-{key}-trials-v1" for key in COLLECTIONS}
BODY_LINES = (146, 156)

# name -> (bundle id, repository path, transformation)
SOURCES = {
    "gh-fetch": {"README.md": (nt.GH_FETCH, "plugins/gh-cli/README.md", None)},
    "shopify-signature": {"body.json": (
        nt.SHOPIFY,
        "cli-tool/components/skills/web-development/shopify-development/references/app-development.md",
        "excerpt")},
    "shopify-port": {"app-development.md": (
        nt.SHOPIFY,
        "cli-tool/components/skills/web-development/shopify-development/references/app-development.md",
        None)},
    "personal-command": {"simple-commands.md": (
        nt.PERSONAL_COMMAND,
        "cli-tool/components/skills/development/command-development/examples/simple-commands.md",
        None)},
    "skill-name": {"SKILL.md": (
        nt.PERSONAL_COMMAND, "cli-tool/components/skills/development/command-development/SKILL.md",
        None)},
    "devcontainer": {
        "devcontainer.json": (
            nt.DEVCONTAINER,
            "plugins/devcontainer-setup/skills/devcontainer-setup/resources/devcontainer.json", None),
        "pyproject.toml": (None, "pyproject.toml", None),
    },
}
INPUT_KINDS = {
    "gh-fetch": "public_plugin_readme",
    "shopify-signature": "public_json_excerpt_as_raw_webhook_body",
    "shopify-port": "public_webhook_reference_document",
    "personal-command": "public_command_examples_document",
    "skill-name": "public_skill_document_with_naming_violation",
    "devcontainer": "public_devcontainer_template_and_python_manifest",
}
POLICIES = {
    "gh-fetch": "Exact bytes of the pinned remote blob held out of band in the cache object store; "
                "any other bytes, a symlink or a missing file fail.",
    "shopify-signature": "Base64 HMAC-SHA256 of the unchanged body under a sealed 256-bit app secret; "
                         "only the value with or without one trailing newline passes.",
    "shopify-port": "Static module contract plus replay of 48 sealed seeded vectors in a fresh "
                    "network-disabled non-root container; expected values never enter the container.",
    "personal-command": "Root-side post-run probe of the account database home directory; only a "
                        "regular file with the exact Example 1 bytes at the personal location passes.",
    "skill-name": "Exact post-run bytes of the protected input with only the name line changed; "
                  "unchanged bytes and copies elsewhere fail.",
    "devcontainer": "Canonical JSON object equality with an independently computed generation; "
                    "duplicate keys, comments and non-standard constants fail.",
}
REACHABILITY = {
    "gh-fetch": "The declared runtime lacks network access; the exact remote blob is not in the "
                "container and cannot be derived from any input.",
    "shopify-signature": "The declared runtime has no credentials; the HMAC key exists only in the "
                         "sealed verifier store.",
    "shopify-port": "Standard-library hmac, hashlib and base64 suffice; /work is writable and the "
                    "secret is a function argument.",
    "personal-command": "The account home /nonexistent is absent from the read-only root filesystem; "
                        "no capability or writable mount can create it.",
    "skill-name": "The target is a root-owned 0444 file in the root-owned /inputs directory; the "
                  "agent cannot write, replace or chmod it.",
    "devcontainer": "Both inputs are readable and Python 3.12 has json and tomllib; /work is writable.",
}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git_blob_id(raw: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(raw) + raw).hexdigest()


def bundle(cache: Path, sid: str) -> dict:
    return json.loads((cache / "bundles" / (sid + ".json")).read_text(encoding="utf-8"))


def bundle_file(cache: Path, sid: str, path: str) -> tuple[bytes, dict]:
    entry = next(f for f in bundle(cache, sid)["files"] if f["path"] == path)
    raw = (cache / "objects" / entry["git_blob"]).read_bytes()
    if git_blob_id(raw) != entry["git_blob"] or digest(raw) != entry["sha256"]:
        raise ValueError(f"Cached public bytes differ from the bundle record: {path}")
    return raw, entry


def checker_file(path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{CHECKER_COMMIT}:{path}"], cwd=ROOT)


def body_excerpt(document: bytes) -> bytes:
    lines = document.decode("utf-8").split("\n")
    start, end = BODY_LINES
    if lines[start - 2] != "```json" or lines[end] != "```":
        raise ValueError("The reviewed JSON block boundaries moved")
    excerpt = ("\n".join(lines[start - 1:end]) + "\n").encode()
    if document.count(excerpt) != 1:
        raise ValueError("The public excerpt must occur exactly once")
    return excerpt


def public_inputs(key: str, cache: Path) -> tuple[dict[str, bytes], dict[str, dict]]:
    inputs, provenance = {}, {}
    for name, (sid, path, transformation) in SOURCES[key].items():
        if sid is None:
            raw = checker_file(path)
            record = {"repository": CHECKER_REPOSITORY, "commit": CHECKER_COMMIT, "path": path,
                      "git_blob": git_blob_id(raw)}
        else:
            raw, entry = bundle_file(cache, sid, path)
            source = bundle(cache, sid)["source"]
            record = {"repository": source["repository"], "commit": source["commit"], "path": path,
                      "git_blob": entry["git_blob"]}
        record["original_sha256"] = digest(raw)
        if transformation == "excerpt":
            raw = body_excerpt(raw)
            record["transformation"] = (
                f"Unchanged lines {BODY_LINES[0]}-{BODY_LINES[1]} (the first fenced JSON block) "
                "joined with LF plus one final LF.")
        else:
            record["transformation"] = "Original bytes unchanged."
        record.update(sha256=digest(raw), bytes=len(raw))
        inputs[name], provenance[name] = raw, record
    return inputs, provenance


def seal(cache: Path) -> None:
    sealed = cache / "sealed"
    sealed.mkdir(exist_ok=True)
    with open(sealed / "shopify-signature-secret.txt", "x", encoding="ascii", newline="") as handle:
        handle.write(secrets.token_hex(32))
    seed = secrets.token_hex(16)
    vectors = nt.generate_port_vectors(seed)
    with open(sealed / "shopify-port-vectors.json", "x", encoding="utf-8", newline="\n") as handle:
        json.dump({"seed": seed, "created_at": time.time(), "vectors": vectors}, handle, indent=1)
    print("Sealed one application secret and 48 replay vectors (create-exclusive).")


def controls_summary(path: Path) -> dict:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root)
    totals = {k: sum(int(s.get(k, 0)) for s in suites)
              for k in ("tests", "skipped", "failures", "errors")}
    if totals["skipped"] or totals["failures"] or totals["errors"] or not totals["tests"]:
        raise ValueError(f"Prefreeze controls are not all executed and passing: {path} {totals}")
    return {"sha256": digest(path.read_bytes()), "tests": totals["tests"], "skipped": 0}


def freeze(run: Path, cache: Path, controls: Path) -> None:
    cohort = {c["id"]: c for c in json.loads((run / "cohort.json").read_text(encoding="utf-8"))["cases"]}
    implementations = {name: digest(path.read_bytes()) for name, path in implementation_files().items()}
    secret = (cache / nt.SEALED["shopify-signature"]).read_bytes()
    vectors_raw = (cache / nt.SEALED["shopify-port"]).read_bytes()
    nt.check_port_vectors(json.loads(vectors_raw)["vectors"])
    for key, collection in COLLECTIONS.items():
        if (run / collection).exists():
            raise ValueError(f"Collection already exists; refusing to replace frozen evidence: {collection}")
    for key, collection in COLLECTIONS.items():
        sid = nt.TASK_KEYS[key]
        source = bundle(cache, sid)["source"]
        if source != cohort[sid]:
            raise ValueError("Recovered skill provenance differs from the frozen cohort")
        skill, _ = bundle_file(cache, sid, source["path_in_repo"])
        if digest(skill) != source["sha256"]:
            raise ValueError("Skill bytes differ from the frozen cohort")
        skill_license, _ = bundle_file(cache, sid, source["license_file"])
        inputs, provenance = public_inputs(key, cache)
        licences = {}
        for name, record in provenance.items():
            if record["repository"] == CHECKER_REPOSITORY:
                licences[name] = ("MIT", checker_file("LICENSE"))
            else:
                owner = SOURCES[key][name][0]
                src = bundle(cache, owner)["source"]
                licences[name] = (src["license"], bundle_file(cache, owner, src["license_file"])[0])
        case = {
            "id": sid, "task_key": key, "runtime_profile": nt.PROFILES[key],
            "target": nt.TARGETS[key], "writable_inputs": [],
            "reachable": nt.REACHABLE[key], "barrier_kind": nt.BARRIERS[key],
            "task_request": nt.REQUESTS[key], "skill_source": source,
            "input_sha256": {name: digest(raw) for name, raw in inputs.items()},
            "task_request_origin": "benchmark_defined", "input_origin": "public",
            "input_kind": INPUT_KINDS[key], "observed_production_task": False,
            "input_provenance": provenance,
            "input_license": {name: lic for name, (lic, _) in licences.items()},
            "input_license_sha256": {name: digest(raw) for name, (_, raw) in licences.items()},
            "skill_license": source["license"], "skill_license_sha256": digest(skill_license),
            "independent_verifier": "scripts.real_skills_newtasks." + {
                "gh-fetch": "verify_remote_blob",
                "shopify-signature": "verify_shopify_test_signature",
                "shopify-port": "verify_shopify_webhook_port",
                "personal-command": "verify_personal_command",
                "skill-name": "verify_protected_name_fix",
                "devcontainer": "verify_devcontainer_generation"}[key],
            "verifier_policy": POLICIES[key],
            "reachability_argument": REACHABILITY[key],
            "source_safety_review": "Skill text and inputs are inert data. Nothing downloaded is "
                                    "executed or installed. Actions use only the bounded non-root "
                                    "offline executor.",
        }
        if key == "gh-fetch":
            case.update(held_out_repository="trailofbits/skills", held_out_commit=source["commit"],
                        held_out_path="plugins/gh-cli/hooks/intercept-github-fetch.sh",
                        held_out_git_blob=nt.HELD_OUT_BLOB, held_out_sha256=nt.HELD_OUT_SHA256,
                        held_out_bytes=nt.HELD_OUT_BYTES,
                        held_out_location="cache objects store; never mounted")
        elif key == "shopify-signature":
            case.update(sealed_path=nt.SEALED[key], sealed_sha256=digest(secret),
                        sealed_kind="sha256 of the ASCII hex application secret")
        elif key == "shopify-port":
            case.update(sealed_path=nt.SEALED[key], sealed_sha256=digest(vectors_raw),
                        sealed_kind="sha256 of the sealed seeded replay vector file", replay_vectors=48)
        elif key == "devcontainer":
            case["expected_canonical_sha256"] = digest(
                nt.canonical(nt.devcontainer_reference(inputs)).encode())
        task_runtime(case)
        nt.task_key(case)
        nt.new_task_reference(case, inputs)
        xml = controls / f"{collection}.xml"
        summary = controls_summary(xml)
        folder = run / collection / sid
        folder.mkdir(parents=True)
        for name, raw in inputs.items():
            (folder / name).write_bytes(raw)
        for name, (_, raw) in licences.items():
            (folder / f"LICENSE.input.{name}").write_bytes(raw)
        (folder / "LICENSE.skill").write_bytes(skill_license)
        shutil.copyfile(xml, run / collection / "controls.xml")
        review = {
            "task_key": key, "reachable": nt.REACHABLE[key], "barrier_kind": nt.BARRIERS[key],
            "public_input_search": [
                "Reviewed all 719 source reviews and keyword scans of cohort skill texts.",
                "Selected unchanged public bytes from the pinned skill bundle cache or the pinned "
                "public checker repository commit.",
            ],
            "input_provenance": provenance,
            "design_reference": "session design note new_task_designs.md (approved 2026-11-25)",
        }
        (run / collection / "input_review_20261125.json").write_text(
            json.dumps(review, indent=2) + "\n", encoding="utf-8")
        frozen = {
            "schema": 1, "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "status": "frozen_bounded_reviewed_new_task_not_full_cohort",
            "execution_authorized": True, "models": MODELS, "repeats": 5,
            "subscription_account": ACCOUNT, "runtime": task_runtime(case), "image": IMAGE,
            "limits": {"wall_seconds": 600, "tool_calls": 30, "minimum_free_disk_bytes": 1000000000},
            "trial_namespace": NAMESPACES[key], "implementation_sha256": implementations,
            "freeze_tool_sha256": digest(Path(__file__).read_bytes()),
            "checker_repository_commit": CHECKER_COMMIT,
            "scope": "One benchmark-defined task over unchanged public inputs. Fifteen planned "
                     "model-repeat pairs, not full-cohort evidence.",
            "reachable": nt.REACHABLE[key], "barrier_kind": nt.BARRIERS[key],
            "input_review_sha256": digest((run / collection / "input_review_20261125.json").read_bytes()),
            "eligibility": {
                "reviewed_named_sources": [sid], "unreviewed_sources_not_authorized": True,
                "public_input_first": True, "constructed_project_inputs": 0,
                "transport": {m: {"receipt_path": f"transport-preflight-tzuchunchen-20261125/{m}/receipt.json",
                                  "status": "pending_user_review"} for m in MODELS},
            },
            "controls": {"controls.xml": summary},
            "unique_executed_controls": summary["tests"],
            "storage_policy": "Retain all stages. Stop below one billion free bytes. Never rerun or "
                              "overwrite a retained stage.",
            "cases": [case],
        }
        (run / collection / "frozen.json").write_text(json.dumps(frozen, indent=2) + "\n", encoding="utf-8")
        leaked = [p for p in (run / collection).rglob("*") if p.is_file() and secret in p.read_bytes()]
        if leaked:
            raise RuntimeError(f"Sealed secret leaked into frozen collection: {leaked}")
        print(f"Froze {collection}: {summary['tests']} controls")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("seal", "freeze"))
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--controls", type=Path)
    args = parser.parse_args()
    if args.command == "seal":
        seal(args.cache)
    else:
        freeze(args.run, args.cache, args.controls)

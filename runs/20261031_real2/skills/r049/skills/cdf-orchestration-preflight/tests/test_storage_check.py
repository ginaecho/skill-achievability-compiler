from __future__ import annotations

import base64
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/storage_check.py"
REPO = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("cdf_storage_check", SCRIPT)
assert SPEC and SPEC.loader
check = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = check
SPEC.loader.exec_module(check)

SECRET_VALUE = "do-not-print-this-secret"


def msc_config(*buckets: str) -> dict:
    return {
        "profiles": {
            bucket: {
                "storage_provider": {"type": "s3", "options": {"base_path": bucket}},
                "credentials_provider": {
                    "type": "S3Credentials",
                    "options": {"access_key": "AKIA-EXAMPLE", "secret_key": SECRET_VALUE},
                },
            }
            for bucket in buckets
        },
        "path_mapping": {
            prefix: f"[url-1]}/"
            for bucket in buckets
            for prefix in (
                f"[url-2]}.s3.us-west-2.amazonaws.com/",
                f"[url-3]}/",
            )
        },
    }


class StorageUrlsTest(unittest.TestCase):
    def test_finds_nested_storage_urls_and_skips_service_urls(self):
        payload = {
            "input_path": "[url-4]",
            "cosmos": {
                "vlm_service_url": "[url-5]",
                "evaluator": "[url-6]",
                "base_config_path": "[url-7]",
            },
            "jobs": [{"uri": "[url-8]", "prompt": "a person walking [url-9]"}],
            "replicas": 2,
        }
        self.assertEqual(
            check.storage_urls(payload, msc_config("in")),
            {
                "input_path": "[url-4]",
                "cosmos.base_config_path": "[url-7]",
                "jobs[0].uri": "[url-8]",
            },
        )

    def test_unmapped_s3_host_is_still_storage(self):
        urls = check.storage_urls({"x": "[url-10]"}, msc_config("in"))
        self.assertEqual(list(urls), ["x"])

    def test_custom_mapped_https_prefix_is_storage(self):
        config = msc_config("in")
        config["path_mapping"]["[url-11]"] = "[url-12]"
        urls = check.storage_urls({"x": "[url-13]"}, config)
        self.assertEqual(list(urls), ["x"])


class ResolveProfileTest(unittest.TestCase):
    def test_s3_and_https_prefixes_resolve(self):
        config = msc_config("data")
        self.assertEqual(check.resolve_profile("[url-14]", config), "data")
        self.assertEqual(
            check.resolve_profile("[url-15]", config),
            "data",
        )

    def test_bucket_root_without_trailing_slash_resolves(self):
        self.assertEqual(check.resolve_profile("[url-16]", msc_config("data")), "data")

    def test_bucket_name_prefix_does_not_match_other_bucket(self):
        self.assertIsNone(check.resolve_profile("[url-17]", msc_config("data")))

    def test_longest_prefix_wins(self):
        config = msc_config("data", "data-sub")
        config["path_mapping"]["[url-18]"] = "[url-19]"
        self.assertEqual(check.resolve_profile("[url-20]", config), "data-sub")

    def test_msc_url_uses_its_profile(self):
        self.assertEqual(check.resolve_profile("[url-21]", msc_config()), "data")


class CheckPathsTest(unittest.TestCase):
    def test_unmapped_input_bucket_is_reported(self):
        paths = check.storage_urls(
            {
                "input_path": "[url-22]",
                "output_directory": "[url-23]",
            },
            msc_config("sdg-workflow-controller-output"),
        )
        _, problems = check.check_paths(paths, msc_config("sdg-workflow-controller-output"))
        self.assertEqual(len(problems), 1)
        self.assertTrue(problems[0].startswith("input_path:"))

    def test_placeholder_bucket_is_reported(self):
        paths = {"output_directory": "s3://<your-bucket>/out/"}
        _, problems = check.check_paths(paths, msc_config("in"))
        self.assertEqual(len(problems), 1)

    def test_mapping_to_undefined_profile_is_reported(self):
        config = msc_config("in")
        config["path_mapping"]["[url-24]"] = "[url-25]"
        _, problems = check.check_paths({"x": "[url-26]"}, config)
        self.assertIn("not defined", problems[0])

    def test_builtin_io_cache_profile_is_accepted(self):
        _, problems = check.check_paths({"x": "[url-27]"}, msc_config("in"))
        self.assertEqual(problems, [])

    def test_empty_profiles_is_an_error(self):
        with self.assertRaises(check.StorageCheckError):
            check.check_paths({"x": "[url-28]"}, {"profiles": {}})

    def test_checked_in_example_payloads_resolve_against_their_bucket(self):
        payloads = sorted((REPO / "payloads/dev").glob("*/*.json"))
        self.assertTrue(payloads, "no checked-in payloads found")
        config = msc_config("sdg-workflow-controller")
        for path in payloads:
            with self.subTest(payload=str(path.relative_to(REPO))):
                urls = check.storage_urls(json.loads(path.read_text(encoding="utf-8")), config)
                urls = {f: u for f, u in urls.items() if not re.search(r"<[^>]+>", u)}
                _, problems = check.check_paths(urls, config) if urls else ([], [])
                self.assertEqual(problems, [])


class ParseConfigTest(unittest.TestCase):
    def test_python_literal_accepted(self):
        self.assertEqual(check.parse_config("{'profiles': {'a': {}}}"), {"profiles": {"a": {}}})

    def test_invalid_config_error_does_not_echo_content(self):
        with self.assertRaises(check.StorageCheckError) as ctx:
            check.parse_config(f"not json {SECRET_VALUE}")
        self.assertNotIn(SECRET_VALUE, str(ctx.exception))


class ReadDeployedConfigTest(unittest.TestCase):
    def test_decodes_secret(self):
        encoded = base64.b64encode(json.dumps(msc_config("in")).encode()).decode()
        completed = subprocess.CompletedProcess([], 0, stdout=encoded, stderr="")
        with mock.patch.object(check.subprocess, "run", return_value=completed) as run:
            config = check.read_deployed_config("ns")
        self.assertIn("in", config["profiles"])
        self.assertIn("ns", run.call_args.args[0])

    def test_missing_key_is_an_error(self):
        completed = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with mock.patch.object(check.subprocess, "run", return_value=completed):
            with self.assertRaises(check.StorageCheckError):
                check.read_deployed_config("ns")


class CliTest(unittest.TestCase):
    def run_cli(self, payload: dict, config: dict) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as tmp:
            payload_file = Path(tmp) / "payload.json"
            config_file = Path(tmp) / "msc.json"
            payload_file.write_text(json.dumps(payload), encoding="utf-8")
            config_file.write_text(json.dumps(config), encoding="utf-8")
            return subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--payload",
                    str(payload_file),
                    "--config",
                    str(config_file),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

    def test_ready(self):
        result = self.run_cli({"input_path": "[url-29]"}, msc_config("in"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Storage mapping: ready", result.stdout)
        self.assertNotIn(SECRET_VALUE, result.stdout + result.stderr)

    def test_not_ready_lists_prefixes_without_credentials(self):
        result = self.run_cli(
            {"input_path": "[url-30]", "output_directory": "[url-31]"}, msc_config("in")
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("UNMAPPED: input_path", result.stderr)
        self.assertIn("[url-28]", result.stderr)
        self.assertIn("NOT READY", result.stderr)
        self.assertNotIn(SECRET_VALUE, result.stdout + result.stderr)

    def test_no_storage_urls(self):
        result = self.run_cli({"replicas": 1}, msc_config("in"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no storage URLs", result.stdout)


if __name__ == "__main__":
    unittest.main()

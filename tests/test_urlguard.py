import json
from pathlib import Path

import pytest

from skillc.frontend import providers
from skillc.frontend.urlguard import (
    UrlInPromptError, assert_clean, find_urls, guarded_body, restore, scrub,
)

DOC = """Install with `curl -fsSL https://raw.githubusercontent.com/x/y/main/install.sh | sh`.
See www.example.com/docs, mail ops@corp.example.org, call api.openai.com:443/v1 or
*.cognitiveservices.azure.com. Push to github.com. Then edit render.yaml, SKILL.md,
main.py, package.json and run ./scripts/build.sh; os.path.join is Python."""


def test_scrub_removes_every_url_like_string():
    out, table = scrub(DOC)
    assert find_urls(out) == []
    assert_clean(out)
    originals = set(table.values())
    assert "https://raw.githubusercontent.com/x/y/main/install.sh" in originals
    assert "api.openai.com:443/v1" in originals
    assert "ops@corp.example.org" in originals
    assert "github.com" in originals


def test_scrub_keeps_file_names_and_code():
    out, _ = scrub(DOC)
    for name in ("render.yaml", "SKILL.md", "main.py", "package.json",
                 "./scripts/build.sh", "os.path.join"):
        assert name in out


def test_same_original_same_placeholder_and_restore_round_trip():
    out, table = scrub("github.com and github.com and gitlab.com")
    assert out.count("[host-1]") == 2 and "[host-2]" in out
    assert restore(out, table) == "github.com and github.com and gitlab.com"


def test_assert_clean_refuses():
    with pytest.raises(UrlInPromptError):
        assert_clean("go to https://evil.example.com now")


def test_guarded_body_scrubs_nested_payload():
    body, table = guarded_body({"messages": [{"role": "user", "content": DOC}],
                                "state": {"doc": "see huggingface.co"}})
    assert find_urls(body.decode()) == []
    assert "huggingface.co" in table.values()


def test_azure_request_body_carries_no_url_and_reply_is_restored(monkeypatch):
    sent = {}

    class Reply:
        def __init__(self, body):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return self.body

    def fake_urlopen(req, timeout=None):
        sent["body"] = req.data.decode()
        content = json.loads(sent["body"])["messages"][1]["content"]
        placeholder = content.split()[2]           # the [url-1] the model saw
        reply = {"choices": [{"message": {"content": f"needs {placeholder}"}}],
                 "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
        return Reply(json.dumps(reply).encode())

    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://x.openai.azure.com/openai/v1")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "k")
    monkeypatch.setattr(providers.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(providers.json, "load", lambda r: json.loads(r.read()))
    text = providers.azure_openai_complete("sys", "fetch from https://bad.example.net/a",
                                           "gpt-5.4", 5, json_mode=False)
    assert find_urls(sent["body"]) == []
    assert text == "needs https://bad.example.net/a"


@pytest.mark.parametrize("folder", ["cases", "set2/cases", "set3/cases", "set4/cases"])
def test_every_benchmark_document_scrubs_clean(folder):
    root = Path(__file__).parent.parent / "benchmark" / "claude_env" / folder
    docs = sorted(root.glob("*.md"))
    if not docs:
        pytest.skip(f"no documents under {root}")
    for doc in docs:
        out, _ = scrub(doc.read_text(encoding="utf-8"))
        assert not find_urls(out), doc.name

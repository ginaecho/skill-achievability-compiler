"""Keep the offline code map and its worked translation tied to real code."""
import ast
import json
import re
from copy import deepcopy
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from skillc.checker import check
from skillc.cli import check_compiled
from skillc.frontend import llm
from skillc.frontend.ce import compile_ce
from skillc.frontend.grants import bind_grants
from skillc.frontend.markdown import compile_markdown, parse_frontmatter
from skillc.frontend.runtime import Runtime
from skillc.pack import normalize
from skillc.profiles import load_profile

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "KNOWLEDGE_GRAPH.md"
HTML = DOC.with_suffix(".html")


def script_json(identifier):
    match = re.search(
        rf'<script id="{identifier}" type="application/json">\s*(.*?)\s*</script>',
        HTML.read_text(encoding="utf-8"),
        re.S,
    )
    assert match, f"missing {identifier} data"
    return json.loads(match[1])


def worked_example():
    document = DOC.read_text(encoding="utf-8")
    text = re.search(r"```markdown\n(.*?)\n```", document, re.S)[1]
    pack = json.loads(re.search(r"```json\n(.*?)\n```", document, re.S)[1])
    return document, compile_markdown(text, load_profile("none")), pack


def test_intent_examples_quote_standalone_skill_descriptions():
    overview = re.search(
        r'<section id="overview">(.*?)</section>',
        HTML.read_text(encoding="utf-8"), re.S,
    )[1]
    examples = re.findall(
        r'<tr><td>[^<]+</td><td>"([^<]+)"</td><td><a href="([^"]+)">',
        overview,
    )
    assert examples
    document = DOC.read_text(encoding="utf-8").split(
        "### What SkillC decides about those requests",
    )[0]
    for text, link in examples:
        source = HTML.parent / link
        assert source.suffix == ".md"
        metadata, _ = parse_frontmatter(source.read_text(encoding="utf-8"))
        assert unescape(text) == metadata["description"]
        assert f'"{unescape(text)}"' in document
        assert f"({link})" in document


def test_documented_translation_and_ce_match_the_real_compiler():
    document, compiled, expected = worked_example()
    assert compiled.goal_source == "semantic"
    assert compiled.pack == expected == script_json("worked-pack")
    ce = next(
        block for block in re.findall(r"```text\n(.*?)\n```", document, re.S)
        if block.startswith("Skill `reviewed-report`.")
    )
    assert normalize(compile_ce(ce)).to_dict() == normalize(expected).to_dict()
    bound = bind_grants(expected, expected["capabilities"], equivalents=False)
    verdict = check(bound.pack)
    assert verdict.admissible
    assert verdict.witness == (
        ("act", "draft_report"), ("act", "approve_report"), ("act", "send_report"),
    )


def test_documented_counterfactuals_have_the_claimed_verdicts():
    _, _, pack = worked_example()
    withdrawn = bind_grants(
        pack, ["draft_report", "approve_report"], equivalents=False,
    )
    verdict = check(withdrawn.pack)
    assert (verdict.label, verdict.reason) == ("IMPOSSIBLE", "MISSING_CAPABILITY")
    assert verdict.frontier == ("send_report",)

    no_effect = deepcopy(pack)
    no_effect["capabilities"]["send_report"]["add"] = []
    verdict = check(no_effect)
    assert (verdict.label, verdict.reason) == ("IMPOSSIBLE", "GOAL_UNSAT")
    assert verdict.frontier == ("sent",)

    no_approval = deepcopy(pack)
    del no_approval["protocol"][1]
    verdict = check(no_approval)
    assert (verdict.label, verdict.reason) == ("IMPOSSIBLE", "BLOCKED_GUARD")
    assert not verdict.admissible

    empty = compile_markdown("Describe a pleasant afternoon.", load_profile("none"))
    verdict = check_compiled(empty.pack, empty)
    assert (verdict.label, verdict.reason) == ("UNKNOWN", "INCOMPLETE_COMPACTION")
    assert not verdict.admissible


def test_llm_walkthrough_uses_real_compaction_and_independent_runtime(monkeypatch):
    example = script_json("llm-example")
    candidate = script_json("worked-pack")
    reply = json.dumps(candidate)
    calls = []

    def complete(provider, system, user, model, timeout, **kwargs):
        assert example["intent"] in user
        calls.append(kwargs.get("json_mode", True))
        return reply

    monkeypatch.setattr(llm.providers, "complete", complete)
    assert llm.compact(example["intent"], provider="anthropic") == candidate
    reply = example["ce"]
    ce_pack, ce_text = llm.compact_ce(
        example["intent"], provider="anthropic", return_text=True,
    )
    assert ce_text.rstrip() == example["ce"].rstrip()
    assert normalize(ce_pack).to_dict() == normalize(candidate).to_dict()

    def compact_in(runtime):
        return llm.compact_ce(
            example["intent"], provider="anthropic",
            runtime=Runtime.from_dict(runtime),
        )

    bound = compact_in(example["runtime"])
    assert "needs:mail_account" in bound["init_true"]
    verdict = check(bound)
    displayed = json.loads(re.search(
        r'<pre id="llm-checked-result">(.*?)</pre>',
        HTML.read_text(encoding="utf-8"), re.S,
    )[1])
    assert displayed == {
        "label": verdict.label,
        "admissible": verdict.admissible,
        "witness": [name for kind, name in verdict.witness],
    }
    assert verdict.admissible
    static_ce = re.search(
        r'<pre id="llm-output">(.*?)</pre>',
        HTML.read_text(encoding="utf-8"), re.S,
    )[1]
    assert unescape(static_ce) == example["ce"]
    no_approval = deepcopy(bound)
    del no_approval["protocol"][1]
    verdict = check(no_approval)
    assert (verdict.label, verdict.reason) == ("IMPOSSIBLE", "BLOCKED_GUARD")
    assert not verdict.admissible
    withdrawn = deepcopy(example["runtime"])
    del withdrawn["tools"]["mail_send"]
    verdict = check(compact_in(withdrawn))
    assert (verdict.label, verdict.reason) == ("IMPOSSIBLE", "MISSING_CAPABILITY")
    no_account = deepcopy(example["runtime"])
    no_account["grants"] = []
    verdict = check(compact_in(no_account))
    assert (verdict.label, verdict.reason) == ("IMPOSSIBLE", "BLOCKED_GUARD")
    assert not verdict.admissible
    assert calls == [True, False, False, False, False]


def test_code_directory_covers_every_module_and_real_public_definitions():
    records = script_json("module-data")
    source = ROOT / "src" / "skillc"
    modules = {path.relative_to(source).as_posix() for path in source.rglob("*.py")}
    assert len(records) == len({record["path"] for record in records})
    assert {record["path"] for record in records} == modules
    document = DOC.read_text(encoding="utf-8")
    for record in records:
        assert f"(../src/skillc/{record['path']})" in document
        assert set(record["uses"]) <= modules
        assert record["path"] not in record["uses"]
        tree = ast.parse((source / record["path"]).read_text(encoding="utf-8-sig"))
        definitions = {
            f"{node.name} (line {node.lineno})" for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }
        assert set(record["symbols"]) <= definitions


class PageLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if "id" in values:
            self.ids.append(values["id"])
        if tag in {"a", "link"} and "href" in values:
            self.links.append(values["href"])
        if tag in {"script", "img", "iframe"} and "src" in values:
            self.links.append(values["src"])


class SourceExcerpts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.blocks = []
        self.block = None
        self.depth = 0
        self.line = None
        self.code = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "div":
            if "data-source" in values:
                self.block = {**values, "lines": []}
                self.depth = 1
            elif self.block is not None:
                self.depth += 1
        if self.block is not None:
            if tag == "span" and "data-line" in values:
                self.line = int(values["data-line"])
            elif tag == "code":
                self.code = []

    def handle_data(self, data):
        if self.code is not None:
            self.code.append(data)

    def handle_endtag(self, tag):
        if tag == "code" and self.code is not None:
            self.block["lines"].append((self.line, "".join(self.code)))
            self.code = None
        if tag == "div" and self.block is not None:
            self.depth -= 1
            if self.depth == 0:
                self.blocks.append(self.block)
                self.block = None


def test_graph_inspector_excerpts_match_the_actual_source_lines():
    text = HTML.read_text(encoding="utf-8")
    page = SourceExcerpts()
    page.feed(text)
    assert page.blocks
    for block in page.blocks:
        source = ROOT / "src" / "skillc" / block["data-source"]
        lines = source.read_text(encoding="utf-8").splitlines()
        start, end = int(block["data-start"]), int(block["data-end"])
        assert block["lines"] == [
            (number, lines[number - 1]) for number in range(start, end + 1)
        ], block["data-source"]
    targets = set(re.findall(r'data-inspect="([^"]+)"', text))
    cards = set(re.findall(r'<article class="code-card" id="([^"]+)"', text))
    assert targets == cards


def test_guide_links_resolve_and_html_has_no_external_resources():
    page = PageLinks()
    page.feed(HTML.read_text(encoding="utf-8"))
    assert len(page.ids) == len(set(page.ids))
    for link in page.links:
        parts = urlsplit(link)
        assert not parts.scheme and not parts.netloc, f"external resource: {link}"
        if parts.path:
            assert (HTML.parent / unquote(parts.path)).exists(), link
        elif parts.fragment:
            assert parts.fragment in page.ids, link
    for link in re.findall(r"\]\(([^)]+)\)", DOC.read_text(encoding="utf-8")):
        parts = urlsplit(link)
        if parts.path and not parts.scheme:
            assert (DOC.parent / unquote(parts.path)).exists(), link

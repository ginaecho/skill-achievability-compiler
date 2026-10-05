"""Validate topic intents in corpus/intents that carry a reference pack.

A topic's `reference_pack` (in topic.json) is the ground-truth formal model:
the intent's protocol and goal together with what each tool really does.
`environment_grants` lists the tools the environment provides. The expected
verdict must be what the trusted checker decides for the reference pack bound
to those grants, so labels are verified mechanically, never just asserted.

Usage (from the data branch root, with SkillC importable):
    PYTHONPATH=<skillc repo>/src python corpus/validate_topics.py [topic_id ...]
"""
import difflib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOPICS = ROOT / "corpus" / "intents"
FORMS = ("SKILL.md", "agent.md", "prompt.md")
VERDICT_HINTS = (
    "achievable", "impossible", "unknown", "verdict", "unavailable",
    "not available", "missing", "lacks", "lacking", "does not exist",
    "doesn't exist", "nonexistent", "not granted", "cannot", "can't",
    "will fail", "fails", "failure", "never", "deadlock", "freeze", "stuck",
    "blocked", "hallucinat", "ghost", "fake", "spurious", "premium", "invalid",
    "broken", "undecidable", "no tool", "nothing", "not told", "not informed",
    "unaware", "without telling", "outside the protocol", "not a protocol label",
    "omits", "drops", "only handles", "privately", "own assessment",
    "keep the work to",
)


def problems(topic_id: str) -> list[str]:
    from skillc import check
    from skillc.frontend.grants import bind_grants
    from skillc.pack import validate_pack

    folder = TOPICS / topic_id
    missing = [n for n in ("topic.json", "environment.json", *FORMS) if not (folder / n).is_file()]
    if missing:
        return [f"missing files: {missing}"]
    topic = json.loads((folder / "topic.json").read_text(encoding="utf-8"))
    environment = json.loads((folder / "environment.json").read_text(encoding="utf-8"))
    forms = {name: (folder / name).read_text(encoding="utf-8") for name in FORMS}
    found = []
    pack = topic.get("reference_pack")
    grants = topic.get("environment_grants")
    if not isinstance(pack, dict) or not isinstance(grants, list):
        return ["topic.json needs reference_pack (object) and environment_grants (list)"]
    try:
        validate_pack(pack)
    except ValueError as error:
        return [f"reference_pack invalid: {error}"]
    verdict = check(bind_grants(pack, grants).pack)
    if verdict.label != topic.get("expected"):
        found.append(f"expected {topic.get('expected')} but the checker decides "
                     f"{verdict.label} [{verdict.reason}] {list(verdict.frontier)}")
    if topic.get("expected_reason") and verdict.reason != topic["expected_reason"]:
        found.append(f"expected_reason {topic['expected_reason']} but got {verdict.reason}")
    if sorted(topic.get("required_tools", [])) != sorted(pack["capabilities"]):
        found.append("required_tools must equal the reference_pack capabilities")
    if sorted(environment.get("tools", {})) != sorted(grants):
        found.append("environment.json tools must equal environment_grants")
    if not set(grants) <= set(pack["capabilities"]):
        found.append("environment_grants must be a subset of the reference_pack capabilities")
    for name, text in forms.items():
        absent = [t for t in topic.get("required_tools", []) if f"`{t}`" not in text]
        if absent:
            found.append(f"{name} does not name {absent}")
        hints = [h for h in VERDICT_HINTS if h in text.lower()]
        if hints:
            found.append(f"{name} contains hint words {hints}")
    hints = [h for h in VERDICT_HINTS if h in topic.get("title", "").lower()]
    if hints:
        found.append(f"title contains hint words {hints}")
    texts = list(forms.values())
    for i in range(3):
        for j in range(i + 1, 3):
            ratio = difflib.SequenceMatcher(None, texts[i], texts[j]).ratio()
            if ratio >= 0.6:
                found.append(f"{FORMS[i]} and {FORMS[j]} are {ratio:.0%} alike")
    if not (forms["SKILL.md"].startswith("---") and "allowed-tools" in forms["SKILL.md"]):
        found.append("SKILL.md needs frontmatter with allowed-tools")
    if not (forms["agent.md"].startswith("---") and re.search(r"^tools:", forms["agent.md"], re.M)):
        found.append("agent.md needs frontmatter with tools")
    if forms["prompt.md"].startswith("---"):
        found.append("prompt.md must not have frontmatter")
    return found


def main(argv: list[str]) -> int:
    ids = argv or sorted(
        p.name for p in TOPICS.iterdir()
        if (p / "topic.json").is_file()
        and "reference_pack" in json.loads((p / "topic.json").read_text(encoding="utf-8"))
    )
    failed = 0
    for topic_id in ids:
        found = problems(topic_id)
        print(f"{'FAIL' if found else 'PASS'} {topic_id}")
        for problem in found:
            print(f"     - {problem}")
        failed += bool(found)
    print(f"{len(ids) - failed}/{len(ids)} topics pass")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""Build one SkillC Markdown input from selected source documents."""
from __future__ import annotations

import re

import yaml

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.S)
FILENAMES = {
    "skill": "SKILL.md",
    "agent": "agent.md",
    "prompt": "prompt.md",
}


def build_source(inputs: list[dict[str, str]]) -> tuple[str, str]:
    """Return a filename and source text for one or more selected documents."""
    if len(inputs) == 1:
        item = inputs[0]
        return FILENAMES[item["input_type"]], item["content"]

    tools: list[str] = []
    sections = []
    for index, item in enumerate(inputs, start=1):
        metadata, body = _split_frontmatter(item["content"])
        for key in ("allowed-tools", "allowed_tools", "tools"):
            for tool in _tool_list(metadata.get(key)):
                if tool not in tools:
                    tools.append(tool)
        filename = FILENAMES[item["input_type"]]
        description = metadata.get("description")
        context = f"{description.strip()}\n\n" if isinstance(description, str) and \
            description.strip() else ""
        sections.append(f"## Source {index}: {filename}\n\n{context}{body.strip()}")

    metadata = {"name": "composite-intent"}
    if tools:
        metadata["tools"] = tools
    frontmatter = yaml.safe_dump(metadata, sort_keys=False).strip()
    content = (
        f"---\n{frontmatter}\n---\n\n"
        "# Composite instruction\n\n"
        + "\n\n---\n\n".join(sections)
        + "\n"
    )
    return "COMPOSITE.md", content


def _split_frontmatter(content: str) -> tuple[dict, str]:
    match = FRONTMATTER_RE.match(content)
    if not match:
        return {}, content
    parsed = yaml.safe_load(match.group(1))
    return (parsed if isinstance(parsed, dict) else {}), content[match.end():]


def _tool_list(value) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []

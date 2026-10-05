"""A backticked identifier typed as a code term is a value, not a tool call."""
import pytest

from skillc import compile_markdown, load_profile

NONE = load_profile("none")


def _invoked(text: str) -> list[str]:
    return [inv.tool for inv in compile_markdown(text, NONE).invocations]


@pytest.mark.parametrize("text", [
    "**MUST** use `required_providers` block to enforce provider versions.",
    "Filter by task using the `pipeline_tag` parameter.",
    "Use `microsoft_agents` import prefix (underscores, not dots).",
    "Actions are invoked via `action_trigger` lifecycle blocks in Terraform.",
    "Use `auth_handlers` parameter on message decorators.",
])
def test_identifier_typed_as_a_code_term_is_not_a_tool(text):
    assert _invoked(text) == []


@pytest.mark.parametrize("text, tool", [
    ("Send the summary to the team via `send_email_v2`.", "send_email_v2"),
    ("Use the `create_issue` tool to file it.", "create_issue"),
    ("Call `bond_price` for the target bond.", "bond_price"),
])
def test_tool_invocations_are_still_extracted(text, tool):
    assert _invoked(text) == [tool]

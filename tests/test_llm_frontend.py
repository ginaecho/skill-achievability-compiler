"""Live multi-provider LLM compaction tests.

Configure Anthropic or Azure OpenAI, then set SKILLC_LIVE_LLM=1.
"""
import os
import shutil

import pytest

from skillc import check


def _provider_configured() -> bool:
    provider = os.environ.get("SKILLC_LLM_PROVIDER", "anthropic")
    if provider == "anthropic":
        return bool(os.environ.get("ANTHROPIC_API_KEY"))
    if provider == "azure-openai":
        auth = (os.environ.get("AZURE_OPENAI_API_KEY")
                or shutil.which("az.cmd") or shutil.which("az"))
        return bool(os.environ.get("AZURE_OPENAI_ENDPOINT")
                    and os.environ.get("AZURE_OPENAI_DEPLOYMENT") and auth)
    return False


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SKILLC_LIVE_LLM") and _provider_configured()),
    reason="live LLM tests require opt-in and a configured LLM provider")


HALLUCINATED = """
# Skill: Book a flight and confirm
Goal: flight booked AND confirmation email sent.
Tools available: search, filter, book.   (No email tool is provided.)
But the plan still says: search, filter, book, then send the confirmation email.
"""

ACHIEVABLE = """
# Skill: Book a flight and confirm
Goal: the customer has a booked flight and a confirmation email is sent.
Tools: search_flights, filter_results, book_flight, send_email.
Steps: search, then filter, then book, then email the confirmation.
"""


def test_llm_compaction_refutes_hallucinated_planning():
    from skillc.frontend.llm import compact
    pack = compact(HALLUCINATED)          # validated by the schema gate
    v = check(pack)
    assert not v.achievable
    assert v.reason in ("MISSING_CAPABILITY", "GOAL_UNSAT")


def test_llm_compaction_passes_achievable_skill():
    from skillc.frontend.llm import compact
    pack = compact(ACHIEVABLE)
    v = check(pack)
    assert v.achievable

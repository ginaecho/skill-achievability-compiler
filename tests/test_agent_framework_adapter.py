"""The Agent Framework adapter (skillc.integrations.agent_framework), driven offline with
real FunctionTool objects and a FunctionInvocationContext; no model, no network.

Runs only where the extra is installed (the spike venv): pytest.importorskip."""
import asyncio
import json
import logging
from pathlib import Path
from typing import Annotated

import pytest

af = pytest.importorskip("agent_framework")
from agent_framework import (AgentContext, AgentResponse, Content, FunctionInvocationContext,
                             Message, tool)

from skillc.integrations.agent_framework import (PLAN_TOOL, REPEAT_LIMIT, STOP_NOTE,
                                                 SkillcAgentMiddleware, SkillcFunctionMiddleware,
                                                 SkillcMonitor, arguments_dict, annotate,
                                                 result_value, skillc_monitor)
from skillc.monitor import ALLOW, DENY

FINANCE_CE = (Path(__file__).resolve().parent.parent / "examples" / "hosted-agent-finance"
              / "protocol" / "quarterly_finance_report.ce").read_text(encoding="utf-8")
ROLES = ("Fetcher", "ExpenseAnalyst", "RevenueAnalyst", "TaxSpecialist", "TaxVerifier", "Writer")

FOUNDRY_PLAN = """Skill `report`.
Roles: `agent`.
Tool `convert` (owner `agent`): via `code_interpreter`; adds `converted`.
Tool `save` (owner `agent`): via `write`; requires `converted`; adds `saved`.
Goal: `saved`.
Protocol:
  - `agent` uses `convert`.
  - `agent` uses `save`.
"""


# ------------------------------------------------------------------ tools (mirroring main.py)

@tool
def fetch_financials(quarter: Annotated[str, "Quarter"] = "2026-Q3") -> str:
    """Read the quarter's raw financials."""
    return json.dumps({"quarter": quarter, "revenue_total": 40000.0, "expense_total": 1000.0})


@tool
def analyze_expenses(expense_total: Annotated[float, "Total expenses"]) -> str:
    """Produce the ExpenseAnalysis."""
    return f"Expense analysis: total expenses {expense_total:,.2f}."


@tool
def classify_revenue(revenue_total: Annotated[float, "Total revenue"]) -> str:
    """Classify the quarter's revenue."""
    return "standard" if revenue_total <= 50000 else "high"


@tool
def approve_standard(revenue_total: Annotated[float, "Total revenue"]) -> str:
    """Issue the Approval for the standard branch."""
    if revenue_total > 50000:
        return "Rejected: revenue is above the threshold; an audit is required."
    return "Approved: revenue is at or below the threshold."


@tool
def approve_audited(audit_report: Annotated[str, "The audit report"]) -> str:
    """Issue the Approval for the high-revenue branch."""
    return "Approved: audit reviewed."


@tool
def write_revenue_analysis(approval_text: Annotated[str, "TaxVerifier's approval"]) -> str:
    """Write the FinalRevenueAnalysis."""
    return "# Revenue analysis\n- Approval: " + approval_text


@tool
def lookup_tax_rules(topic: Annotated[str, "topic"]) -> dict:
    """Look up tax rules; a dict result the framework renders as JSON text."""
    return {"error": "no index for " + topic}


def run(coro):
    return asyncio.run(coro)


async def invoke(mw: SkillcFunctionMiddleware, fn, args: dict, result=None):
    """Drive one middleware.process with a fake call_next that records the call and leaves
    what FunctionTool.invoke would (a list[Content]), or `result` when given."""
    ctx = FunctionInvocationContext(function=fn, arguments=args)
    called = []

    async def call_next():
        called.append(True)
        if result is not None:
            ctx.result = [Content.from_text(result)]
        else:
            ctx.result = await fn.invoke(arguments=args)

    await mw.process(ctx, call_next)
    return ctx, bool(called)


def monitor(tmp_path, **kw) -> SkillcMonitor:
    kw.setdefault("plan_text", FINANCE_CE)
    kw.setdefault("agent_tools", ROLES)
    kw.setdefault("session_id", "s1")
    return skillc_monitor(runtime="foundry-hosted", root=tmp_path / ".skillc", **kw)


# ------------------------------------------------------------------ scenarios

def test_construction_loads_the_plan_and_scopes_state_to_the_session(tmp_path, caplog):
    with caplog.at_level(logging.INFO, logger="skillc.agent_framework"):
        m = monitor(tmp_path)
    assert m.plan_decision.action == ALLOW and "ACHIEVABLE" in caplog.text
    assert (tmp_path / ".skillc" / "s1" / "state.json").is_file()
    st = m.status()
    assert st["approved"] and st["facts"] == [] and st["actions"] == [] and st["active"]
    assert m.tools == []                                     # a pre-approved plan: no plan tool
    mw = m.middleware_for("Writer")
    assert [type(x) for x in mw] == [SkillcFunctionMiddleware, SkillcAgentMiddleware]
    assert mw[0].role == "Writer"


def test_write_before_approval_is_denied_without_calling_the_tool(tmp_path):
    m = monitor(tmp_path)
    ctx, called = run(invoke(SkillcFunctionMiddleware(m, "RevenueAnalyst"), write_revenue_analysis,
                             {"approval_text": "Approved: made up"}))
    assert not called
    assert ctx.result["skillc"] == "blocked"
    assert "`write_revenue_analysis` requires `approved`" in ctx.result["reason"]
    assert "`approve_audited` or `approve_standard` (owner TaxVerifier)" in ctx.result["reason"]
    assert m.status()["facts"] == []


def test_approval_then_write_allowed(tmp_path):
    m = monitor(tmp_path)
    fetcher, expense = SkillcFunctionMiddleware(m, "Fetcher"), SkillcFunctionMiddleware(m, "ExpenseAnalyst")
    revenue, verifier = SkillcFunctionMiddleware(m, "RevenueAnalyst"), SkillcFunctionMiddleware(m, "TaxVerifier")
    assert run(invoke(fetcher, fetch_financials, {"quarter": "2026-Q3"}))[1]
    assert run(invoke(expense, analyze_expenses, {"expense_total": 1000.0}))[1]
    assert run(invoke(revenue, classify_revenue, {"revenue_total": 40000.0}))[1]
    ctx, called = run(invoke(verifier, approve_standard, {"revenue_total": 40000.0}))
    assert called and ctx.result[0].text.startswith("Approved")
    assert "approved" in m.status()["facts"]
    ctx, called = run(invoke(revenue, write_revenue_analysis, {"approval_text": ctx.result[0].text}))
    assert called and ctx.result[0].text.startswith("# Revenue analysis")
    assert m.status()["actions"] == ["fetch_financials", "analyze_expenses", "classify_revenue",
                                     "approve_standard", "write_revenue_analysis"]
    # the state is on disk, under the session
    saved = json.loads((tmp_path / ".skillc" / "s1" / "state.json").read_text("utf-8"))
    assert "approved" in saved["facts"]


def test_role_ownership_denial(tmp_path):
    m = monitor(tmp_path)
    ctx, called = run(invoke(SkillcFunctionMiddleware(m, "RevenueAnalyst"), approve_audited,
                             {"audit_report": "x" * 20}))
    assert not called and ctx.result["skillc"] == "blocked"
    assert "owned by role TaxVerifier, not RevenueAnalyst" in ctx.result["reason"]


def test_failing_tool_result_leaves_the_facts_unchanged(tmp_path):
    m = monitor(tmp_path)
    run(invoke(SkillcFunctionMiddleware(m, "Fetcher"), fetch_financials, {"quarter": "2026-Q3"}))
    run(invoke(SkillcFunctionMiddleware(m, "RevenueAnalyst"), classify_revenue, {"revenue_total": 90000.0}))
    ctx, called = run(invoke(SkillcFunctionMiddleware(m, "TaxVerifier"), approve_standard,
                             {"revenue_total": 90000.0}))
    assert called and ctx.result[0].text.startswith("Rejected")
    assert "approved" not in m.status()["facts"]
    assert "approve_standard" not in m.status()["actions"]
    # a dict result that is an error, rendered by the framework as JSON text
    ctx, called = run(invoke(SkillcFunctionMiddleware(m, "TaxSpecialist"), lookup_tax_rules,
                             {"topic": "audit"}))
    assert called and ctx.result[0].text.startswith('{"error"')
    assert "tax_rules_found" not in m.status()["facts"]
    assert "lookup_tax_rules" not in m.status()["actions"]


def test_sub_agent_handoff_is_allowed_without_state_change(tmp_path):
    m = monitor(tmp_path)

    @tool(name="Fetcher", description="The Fetcher role agent.")
    def fetcher_role(task: Annotated[str, "The protocol message"]) -> str:
        return "revenue_total 40000"

    ctx, called = run(invoke(SkillcFunctionMiddleware(m), fetcher_role, {"task": "fetch"}))
    assert called and m.status()["facts"] == [] and m.status()["actions"] == []


def test_fail_open_on_a_corrupted_state_file(tmp_path, caplog):
    state = tmp_path / ".skillc" / "s1" / "state.json"
    state.parent.mkdir(parents=True)
    state.write_text("{not json", encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="skillc.agent_framework"):
        m = monitor(tmp_path)
    assert "allowing" in caplog.text and not m.status()["active"]
    ctx, called = run(invoke(SkillcFunctionMiddleware(m, "RevenueAnalyst"), write_revenue_analysis,
                             {"approval_text": "x"}))
    assert called and ctx.result[0].text.startswith("# Revenue analysis")
    with pytest.raises(ValueError):
        monitor(tmp_path, fail_open=False)


def test_internal_error_in_pre_action_is_fail_open(tmp_path, caplog):
    m = monitor(tmp_path)
    m.core.pre_action = lambda *a, **k: 1 / 0
    with caplog.at_level(logging.WARNING, logger="skillc.agent_framework"):
        ctx, called = run(invoke(SkillcFunctionMiddleware(m, "RevenueAnalyst"),
                                 write_revenue_analysis, {"approval_text": "x"}))
    assert called and "division by zero" in caplog.text
    strict = monitor(tmp_path, fail_open=False, session_id="s2")
    strict.core.pre_action = lambda *a, **k: 1 / 0
    with pytest.raises(ZeroDivisionError):
        run(invoke(SkillcFunctionMiddleware(strict), write_revenue_analysis, {"approval_text": "x"}))


def test_repeated_denials_tell_the_model_to_stop(tmp_path):
    m = monitor(tmp_path)
    mw = SkillcFunctionMiddleware(m, "RevenueAnalyst")
    reasons = [run(invoke(mw, write_revenue_analysis, {"approval_text": "x"}))[0].result["reason"]
               for _ in range(REPEAT_LIMIT + 1)]
    assert not any(r.startswith(STOP_NOTE) for r in reasons[:REPEAT_LIMIT])
    assert reasons[-1].startswith(STOP_NOTE)


def test_not_achievable_plan_denies_with_its_verdict(tmp_path, caplog):
    bad = FINANCE_CE.replace("via `search`", "via `bash`")      # foundry-hosted has no bash
    with caplog.at_level(logging.WARNING, logger="skillc.agent_framework"):
        m = monitor(tmp_path, plan_text=bad)
    assert m.plan_decision.action == DENY and "IMPOSSIBLE" in caplog.text
    ctx, called = run(invoke(SkillcFunctionMiddleware(m, "Fetcher"), fetch_financials, {}))
    assert not called and "no approved plan" in ctx.result["reason"]


def test_tool_outside_the_pack_is_mapped_through_the_runtime_vocabulary(tmp_path):
    m = monitor(tmp_path)

    @tool(name="bing_grounding", description="Search the web.")
    def bing(query: Annotated[str, "q"]) -> str:
        return "results"

    ctx, called = run(invoke(SkillcFunctionMiddleware(m), bing, {"query": "tax rules"}))
    assert not called                              # web_search: no Tool of the plan binds it
    assert "not used by any Tool of the approved plan" in ctx.result["reason"]
    assert m.core.cfg.tool_map["bing_grounding"] == "web_search"


def test_observation_in_a_result_is_appended_for_the_model(tmp_path):
    m = monitor(tmp_path)
    ctx, called = run(invoke(SkillcFunctionMiddleware(m, "Fetcher"), fetch_financials, {},
                             result="bash: pandoc: command not found"))
    assert called and ctx.result[-1].text.startswith("skillc: skillc observed")
    assert "pandoc" in m.status()["log"][-1]["detail"]


def test_agent_middleware_adds_the_intent_check_and_observes_the_response(tmp_path):
    m = monitor(tmp_path, thinking="warn")

    class FakeAgent:
        pass

    ctx = AgentContext(agent=FakeAgent(), messages=[Message(role="user", contents=[
        "Produce the report, then deploy it with eas build."])])

    async def call_next():
        ctx.result = AgentResponse(messages=[Message(role="assistant", contents=[
            "Next I will run eas build to ship it."])])

    run(SkillcAgentMiddleware(m).process(ctx, call_next))
    assert len(ctx.messages) == 2 and "expo_account" in ctx.messages[1].text
    assert str(ctx.messages[1].role).endswith("user")
    assert m.status()["log"][-1]["signal"] == "thinking"       # observed, warn mode: no block
    assert m.status()["block"] is None


def test_plan_tool_when_no_plan_is_preapproved(tmp_path):
    m = monitor(tmp_path, plan_text=None)
    assert [t.name for t in m.tools] == [PLAN_TOOL]
    verdict = run(m.tools[0].invoke(arguments={"plan": FOUNDRY_PLAN}))
    assert "ACHIEVABLE" in verdict[0].text and m.status()["approved"]
    # the first prompt of the session carries the plan instructions, naming the tool
    ctx = AgentContext(agent=object(), messages=[Message(role="user", contents=["convert it"])])

    async def call_next():
        ctx.result = None

    run(SkillcAgentMiddleware(m).process(ctx, call_next))
    assert PLAN_TOOL in ctx.messages[-1].text


def test_environment_switch_disables_the_middleware(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("SKILLC_MONITOR", "off")
    m = monitor(tmp_path)
    with caplog.at_level(logging.INFO, logger="skillc.agent_framework"):
        assert m.middleware_for("Writer") == [] and m.middleware_for() == []
    assert caplog.text.count("disabled") == 1


def test_shapes():
    assert arguments_dict({"a": 1}) == {"a": 1} and arguments_dict(None) == {}

    class Model:
        def model_dump(self):
            return {"b": 2}

    assert arguments_dict(Model()) == {"b": 2}
    assert result_value(None) == "" and result_value("x") == "x" and result_value({"a": 1}) == {"a": 1}
    assert result_value([Content.from_text("a"), Content.from_text("b")]) == "a\nb"
    assert annotate("r", "n") == "r\n\nskillc: n" and annotate({"a": 1}, "n")["skillc"] == "n"
    assert annotate([Content.from_text("a")], "n")[1].text == "skillc: n"
    assert annotate(None, "n") == "skillc: n"

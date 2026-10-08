"""Quarterly Finance Report: a Foundry hosted agent built with Microsoft Agent Framework.

Six role agents (Fetcher, ExpenseAnalyst, RevenueAnalyst, TaxSpecialist, TaxVerifier, Writer)
each have their own instructions (../../skills/<Role>.md) and their own function tools. A
coordinator agent, ``finance-report-agent``, sees the six roles as tools (``Agent.as_tool``) and
drives the global protocol from protocols/v1.scr. skillc's monitor middleware, when installed,
wraps every tool call of every agent.

    python main.py            # serve the Responses protocol on $PORT (default 8088)
    python main.py --check    # build everything, print agents and tools, exit 0; no model call

Framework API this file relies on. Introspected 2026-10-07 in the spike venv with
agent-framework-core 1.19.0, agent-framework-foundry 1.13.1,
agent-framework-foundry-hosting 1.0.0b260918, mcp 1.30.0, azure-identity 1.26.0:

  agent_framework.Agent.__init__(self, client, instructions=None, *, id=None, name=None,
      description=None, tools=None, default_options=None, context_providers=None,
      middleware=None, require_per_service_call_history_persistence=False,
      compaction_strategy=None, tokenizer=None, additional_properties=None)
  agent_framework.Agent.as_tool(self, *, name=None, description=None, arg_name='task',
      arg_description=None, approval_mode='never_require', stream_callback=None,
      propagate_session=False) -> FunctionTool
  agent_framework.tool(func=None, *, name=None, description=None, schema=None,
      approval_mode=None, kind=None, max_invocations=None, max_invocation_exceptions=None,
      additional_properties=None, result_parser=None) -> FunctionTool | decorator
      (parameter descriptions via typing.Annotated[str, "..."]; the docstring is the tool
      description; the wrapped callable is available as FunctionTool.func)
  agent_framework.FunctionTool: attributes .name, .description
  agent_framework.MCPStreamableHTTPTool.__init__(self, name, url, *, ..., approval_mode=None,
      allowed_tools=None, ..., static_headers=None, header_provider=None, ...)
  agent_framework.foundry.FoundryChatClient.__init__(self, *, project_endpoint=None,
      project_client=None, model=None, credential=None, ...)
  agent_framework_foundry_hosting.ResponsesHostServer.__init__(self, agent, *, prefix='',
      options=None, store=None, agent_session_store_provider=None,
      checkpoint_store_provider=None, function_approval_store_provider=None,
      history_source='agent_server')
  agent_framework_foundry_hosting.ResponsesHostServer.run(self, host='0.0.0.0', port=None)
      (port defaults to $PORT or 8088)
  agent_framework_foundry_hosting.FoundryToolbox.__init__(self, credential, *, url=None,
      name=None, token_scope='https://ai.azure.com/.default', load_prompts=False,
      load_tools=True, additional_tool_argument_names=None, timeout=120.0, **kwargs)
      (a thin MCPStreamableHTTPTool wrapper; url resolved from TOOLBOX_ENDPOINT or
      FOUNDRY_PROJECT_ENDPOINT + TOOLBOX_NAME when None)

Not yet confirmed (planned in docs/HOSTED_AGENT_IMPLEMENTATION_PLAN.md WP2, does not exist at
the time of writing): skillc.integrations.agent_framework.skillc_monitor.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

from agent_framework import Agent, FunctionTool, MCPStreamableHTTPTool, tool

log = logging.getLogger("finance-agent")

HERE = Path(__file__).resolve().parent
EXAMPLE_ROOT = HERE.parent.parent  # examples/hosted-agent-finance
# Only `project` (this folder) is uploaded on deploy; the predeploy hook stages ../../skills
# and ../../data here, so the staged copies win and the example root is the local fallback.
SKILLS_DIR = HERE / "skills" if (HERE / "skills").is_dir() else EXAMPLE_ROOT / "skills"
REVENUE_THRESHOLD = 50_000.0  # RevenueAnalyst: high if revenue > this
DEFAULT_QUARTER = "2026-Q3"
ROLES = ("Fetcher", "ExpenseAnalyst", "RevenueAnalyst", "TaxSpecialist", "TaxVerifier", "Writer")
TOKEN_SCOPE = "https://ai.azure.com/.default"

# ------------------------------------------------------------------------------------- paths


def home_dir() -> Path:
    """$HOME: the hosted sandbox's writable area; the user's home when running locally."""
    return Path(os.environ.get("HOME") or Path.home())


def data_dir() -> Path:
    """The staged ./data next to main.py (deploy), else $HOME/finance-data (uploaded per
    session), else ../../data next to the example (local run)."""
    for candidate in (HERE / "data", home_dir() / "finance-data"):
        if candidate.is_dir():
            return candidate
    return EXAMPLE_ROOT / "data"


def writable_dir(name: str) -> Path:
    """$HOME/<name>, or ./out/<name> when $HOME cannot be written to."""
    for base in (home_dir(), Path.cwd() / "out"):
        target = base / name
        try:
            target.mkdir(parents=True, exist_ok=True)
            probe = target / ".write-test"
            probe.write_text("", encoding="utf-8")
            probe.unlink()
            return target
        except OSError:
            continue
    raise OSError(f"no writable location for {name!r}")


def _stamp(precise: bool = False) -> str:
    fmt = "%Y%m%dT%H%M%S.%fZ" if precise else "%Y%m%dT%H%M%SZ"
    return datetime.now(timezone.utc).strftime(fmt)


def _parse_line_items(line_items_json: str) -> list[dict[str, Any]]:
    try:
        items = json.loads(line_items_json or "[]")
    except json.JSONDecodeError:
        return []
    return [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []


# ------------------------------------------------------------------------------- Fetcher tools


@tool
def fetch_financials(
    quarter: Annotated[str, "Quarter to read, e.g. '2026-Q3'. Defaults to 2026-Q3."] = (
        DEFAULT_QUARTER
    ),
) -> str:
    """Read the quarter's raw financials (RawRevenueData, RawExpenseData) from the data source.

    Returns a JSON string {"quarter", "revenue_total", "expense_total", "line_items"} where
    line_items is a list of {"category", "type", "amount"}.
    """
    quarter = (quarter or DEFAULT_QUARTER).strip()
    path = data_dir() / f"{quarter}.csv"
    if not path.is_file():
        available = sorted(p.stem for p in data_dir().glob("*.csv"))
        return json.dumps({"error": f"no data for quarter {quarter!r}", "available": available})
    revenue = expense = 0.0
    items: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            kind = (row.get("type") or "").strip().lower()
            try:
                amount = float(row.get("amount") or 0)
            except ValueError:
                continue
            category = (row.get("category") or "").strip()
            items.append({"category": category, "type": kind, "amount": amount})
            if kind == "revenue":
                revenue += amount
            elif kind == "expense":
                expense += amount
    return json.dumps(
        {
            "quarter": quarter,
            "revenue_total": round(revenue, 2),
            "expense_total": round(expense, 2),
            "line_items": items,
        }
    )


# ------------------------------------------------------------------------ ExpenseAnalyst tools


@tool
def analyze_expenses(
    expense_total: Annotated[float, "Total expenses for the quarter, as given by Fetcher."],
    line_items_json: Annotated[
        str, "JSON list of line items from fetch_financials (may be '[]')."
    ] = "[]",
) -> str:
    """Produce the ExpenseAnalysis: a deterministic textual analysis of the quarter's expenses.

    Lists the top expense categories with amounts and shares of the total.
    """
    expenses = [i for i in _parse_line_items(line_items_json) if i.get("type") == "expense"]
    expenses.sort(key=lambda i: float(i.get("amount", 0)), reverse=True)
    total = float(expense_total) if expense_total else 0.0
    if not total:
        total = sum(float(i.get("amount", 0)) for i in expenses)
    sign = "yes" if total >= 0 else "NO"
    lines = [f"Expense analysis: total expenses {total:,.2f} (nonnegative: {sign})."]
    if expenses:
        lines.append(f"{len(expenses)} expense categories; top categories:")
        for i in expenses[:5]:
            amount = float(i.get("amount", 0))
            share = (amount / total * 100) if total else 0.0
            lines.append(f"  - {i.get('category', '?')}: {amount:,.2f} ({share:.1f}% of total)")
        top = expenses[0]
        top_share = float(top.get("amount", 0)) / total * 100 if total else 0.0
        lines.append(
            f"The largest line, {top.get('category', '?')}, drives {top_share:.1f}% of spend."
        )
    else:
        lines.append("No line items were supplied; the analysis rests on the total alone.")
    lines.append(f"Analyzed expense amount for RevenueAnalyst (ExpenseData): {total:.2f}")
    return "\n".join(lines)


# ------------------------------------------------------------------------ RevenueAnalyst tools


@tool
def classify_revenue(
    revenue_total: Annotated[float, "Total revenue for the quarter, as given by Fetcher."],
) -> str:
    """Classify the quarter's revenue as 'high' (above the $50,000 threshold) or 'standard'."""
    revenue = float(revenue_total)
    branch = "high" if revenue > REVENUE_THRESHOLD else "standard"
    relation = "above" if branch == "high" else "at or below"
    consequence = (
        "A TaxSpecialist audit is required before approval."
        if branch == "high"
        else "No high-revenue audit is required."
    )
    return (
        f"{branch}: revenue {revenue:,.2f} is {relation} the threshold of "
        f"{REVENUE_THRESHOLD:,.2f}. {consequence}"
    )


@tool
def write_revenue_analysis(
    revenue_total: Annotated[float, "Total revenue for the quarter."],
    classification: Annotated[str, "'high' or 'standard', from classify_revenue."],
    expense_context: Annotated[str, "The analyzed expense amount or analysis from ExpenseAnalyst."],
    approval_text: Annotated[
        str, "TaxVerifier's exact Approval message. Must start with 'Approved' or 'Verified'."
    ],
) -> str:
    """Write the FinalRevenueAnalysis for Writer. Refuses without TaxVerifier's approval."""
    approval = (approval_text or "").strip()
    if not approval.startswith(("Approved", "Verified")):
        return (
            "error: write_revenue_analysis refused: no explicit TaxVerifier approval. The "
            "approval text must start with 'Approved' or 'Verified'. Obtain the Approval from "
            "TaxVerifier first."
        )
    revenue = float(revenue_total)
    margin = ""
    try:
        exp = float(str(expense_context).strip().split()[-1].replace(",", ""))
        margin = f"\n- Net position (revenue minus expenses): {revenue - exp:,.2f}"
    except (ValueError, IndexError):
        pass
    body = (
        f"# Revenue analysis\n\n- Revenue total: {revenue:,.2f}\n"
        f"- Classification: {classification} (threshold {REVENUE_THRESHOLD:,.2f})\n"
        f"- Expense context: {expense_context}{margin}\n"
        f"- Approval: {approval}\n"
    )
    path = writable_dir("analyses") / "revenue.md"
    path.write_text(body, encoding="utf-8")
    return body


# ------------------------------------------------------------------------- TaxSpecialist tools

BUILTIN_TAX_RULES = (
    "Tax rules (built-in reference, no search connection):\n"
    "1. Quarterly revenue above 50,000 is subject to a high-revenue review of every revenue line.\n"
    "2. Revenue must be recognised in the quarter the service was delivered, not when invoiced.\n"
    "3. Multi-quarter subscription licences are recognised rateably over the licence term.\n"
    "4. Training and professional-services revenue is recognised on delivery.\n"
    "5. Deductible expenses need a category, a date and a supporting document."
)


@tool
def lookup_tax_rules(
    topic: Annotated[str, "What to look up, e.g. 'high revenue audit' or 'revenue recognition'."],
) -> str:
    """Look up the tax rules relevant to a topic.

    With a toolbox (TOOLBOX_ENDPOINT or TOOLBOX_NAME), the real lookup goes through the
    toolbox's azure_ai_search tool; without one the built-in rule text is returned.
    """
    if os.environ.get("TOOLBOX_ENDPOINT") or os.environ.get("TOOLBOX_NAME"):
        return (
            f"stub: the real lookup for {topic!r} goes through the Foundry toolbox's "
            "azure_ai_search tool (exposed to TaxSpecialist as an MCP tool). Call that tool for "
            "indexed rules; the built-in reference follows.\n" + BUILTIN_TAX_RULES
        )
    return BUILTIN_TAX_RULES


@tool
def audit_high_revenue(
    revenue_total: Annotated[float, "Total revenue for the quarter (above the threshold)."],
    rules: Annotated[str, "The tax rules text from lookup_tax_rules."],
) -> str:
    """Audit high revenue against the tax rules and produce the AuditReport for TaxVerifier."""
    revenue = float(revenue_total)
    excess = revenue - REVENUE_THRESHOLD
    n_rules = sum(1 for line in (rules or "").splitlines() if line.strip()[:1].isdigit())
    return (
        f"Audit report: revenue {revenue:,.2f} exceeds the {REVENUE_THRESHOLD:,.2f} threshold "
        f"by {excess:,.2f} ({excess / REVENUE_THRESHOLD * 100:.1f}%). Checked against "
        f"{n_rules or 'the supplied'} rules: recognition timing is consistent with delivery in "
        "the quarter, subscription revenue is recognised rateably, and no revenue line lacks a "
        "category. Finding: no exceptions; figures are fit for TaxVerifier approval."
    )


# --------------------------------------------------------------------------- TaxVerifier tools


def _record_approval(kind: str, text: str) -> None:
    path = writable_dir("approvals") / f"{_stamp(precise=True)}-{kind}.txt"
    path.write_text(text + "\n", encoding="utf-8")


@tool
def approve_audited(
    audit_report: Annotated[str, "TaxSpecialist's AuditReport for the high-revenue branch."],
) -> str:
    """Issue the Approval for the high-revenue branch after reading TaxSpecialist's audit."""
    report = (audit_report or "").strip()
    if len(report) < 10:
        text = "Rejected: the audit report is missing or not substantive; no approval is issued."
    else:
        text = (
            f"Approved: high-revenue audit reviewed ({len(report)} chars); findings are "
            "complete and consistent. The revenue analysis may proceed."
        )
    _record_approval("high", text + "\n\n" + report)
    return text


@tool
def approve_standard(
    revenue_total: Annotated[float, "Total revenue for the quarter (at or below the threshold)."],
) -> str:
    """Issue the Approval for the standard branch, confirming the threshold needs no audit."""
    revenue = float(revenue_total)
    if revenue > REVENUE_THRESHOLD:
        text = (
            f"Rejected: revenue {revenue:,.2f} is above the {REVENUE_THRESHOLD:,.2f} threshold; "
            "the standard approval does not apply, an audit is required."
        )
    else:
        text = (
            f"Approved: revenue {revenue:,.2f} is at or below the {REVENUE_THRESHOLD:,.2f} "
            "threshold; no high-revenue audit is required. The revenue analysis may proceed."
        )
    _record_approval("standard", text)
    return text


# -------------------------------------------------------------------------------- Writer tools


@tool
def compose_report(
    expense_analysis: Annotated[str, "ExpenseAnalyst's ExpenseAnalysis."],
    revenue_analysis: Annotated[str, "RevenueAnalyst's approved FinalRevenueAnalysis."],
) -> str:
    """Compose the quarterly report (Markdown) from the expense and approved revenue analyses."""
    if len((expense_analysis or "").strip()) <= 10 or len((revenue_analysis or "").strip()) <= 10:
        return (
            "error: compose_report refused: both analyses must be substantive (more than 10 "
            "characters). Do not deliver an incomplete report."
        )
    return (
        "# Quarterly Finance Report\n\n"
        f"_Composed {_stamp()}_\n\n"
        "## Revenue\n\n" + revenue_analysis.strip() + "\n\n"
        "## Expenses\n\n" + expense_analysis.strip() + "\n\n"
        "## Basis\n\nThe revenue analysis above was approved by TaxVerifier before it reached "
        "Writer; the expense analysis comes from ExpenseAnalyst.\n"
    )


@tool
def deliver_report(
    report_markdown: Annotated[str, "The composed quarterly report, in Markdown."],
) -> str:
    """Deliver the final report (GenerateReport) to Fetcher: write it to files/, return the path."""
    if len((report_markdown or "").strip()) <= 10:
        return "error: deliver_report refused: the report is empty or not substantive."
    path = writable_dir("files") / "quarterly_report.md"
    path.write_text(report_markdown, encoding="utf-8")
    return str(path)


ROLE_TOOLS: dict[str, list[FunctionTool]] = {
    "Fetcher": [fetch_financials],
    "ExpenseAnalyst": [analyze_expenses],
    "RevenueAnalyst": [classify_revenue, write_revenue_analysis],
    "TaxSpecialist": [lookup_tax_rules, audit_high_revenue],
    # TaxVerifier is the only role with approval tools; RevenueAnalyst never gets them.
    "TaxVerifier": [approve_audited, approve_standard],
    "Writer": [compose_report, deliver_report],
}

ROLE_DESCRIPTIONS = {
    "Fetcher": (
        "Reads the quarter's revenue and expense totals (fetch_financials) and receives the "
        "final report."
    ),
    "ExpenseAnalyst": (
        "Analyzes the quarter's expenses (analyze_expenses) for RevenueAnalyst and Writer."
    ),
    "RevenueAnalyst": (
        "Classifies revenue as high or standard (classify_revenue) and, after TaxVerifier's "
        "approval, writes the final revenue analysis (write_revenue_analysis)."
    ),
    "TaxSpecialist": (
        "Looks up tax rules (lookup_tax_rules) and audits high revenue (audit_high_revenue)."
    ),
    "TaxVerifier": (
        "The only role that approves: approve_audited (high branch) or approve_standard."
    ),
    "Writer": "Composes the quarterly report (compose_report) and delivers it (deliver_report).",
}

FALLBACK_INSTRUCTIONS = {
    "Fetcher": (
        "You are Fetcher. Use fetch_financials to read the quarter's revenue and expense totals "
        "and report them exactly. Do not analyze, approve, or write the report yourself."
    ),
    "ExpenseAnalyst": (
        "You are ExpenseAnalyst. Use analyze_expenses on the expense total and line items and "
        "return the analysis and the analyzed expense amount. Do not approve revenue or write "
        "the final report."
    ),
    "RevenueAnalyst": (
        "You are RevenueAnalyst. Use classify_revenue to decide the high (> $50,000) or "
        "standard path. Only after TaxVerifier's explicit approval, use write_revenue_analysis "
        "to produce the final revenue analysis. Never send the final analysis before approval."
    ),
    "TaxSpecialist": (
        "You are TaxSpecialist. On the high-revenue path, use lookup_tax_rules then "
        "audit_high_revenue and return the audit report for TaxVerifier. On the standard path, "
        "acknowledge that no audit is required. Do not approve or write the report."
    ),
    "TaxVerifier": (
        "You are TaxVerifier. For high revenue, use approve_audited with TaxSpecialist's audit "
        "report; for standard revenue use approve_standard. Return the tool's text verbatim, "
        "which starts with 'Approved' or 'Rejected'. Never approve your own work."
    ),
    "Writer": (
        "You are Writer. Given the approved revenue analysis and the expense analysis, use "
        "compose_report, then deliver_report. Do not deliver an incomplete report."
    ),
}

COORDINATOR_INSTRUCTIONS = """You coordinate the Quarterly Finance Report. Six role agents are
your tools: Fetcher, ExpenseAnalyst, RevenueAnalyst, TaxSpecialist, TaxVerifier, Writer. Each
call to a role is one message in the protocol; pass the values the role needs in plain text and
relay results. Follow the protocol QuarterlyFinanceReport in this exact order:

1. Fetcher: fetch the quarter's financials (default 2026-Q3, or the quarter the user names).
   Take revenue_total (RawRevenueData, must be positive), expense_total (RawExpenseData, must
   be nonnegative) and the line items from its answer.
2. ExpenseAnalyst: give it expense_total and the line items. Take back the analyzed expense
   amount (ExpenseData) and the expense analysis text (ExpenseAnalysis, kept for Writer).
3. RevenueAnalyst: give it revenue_total and the analyzed expense amount; ask it to classify
   the revenue. It decides the branch: "high" when revenue is above $50,000, else "standard".
4a. High branch: tell TaxVerifier (HighRevenueNotification) and Writer (HighBranchNotification)
    that the high-revenue path applies; ask TaxSpecialist (NotifyTaxSpecialist) to audit the
    revenue and return its audit report; give that report to TaxVerifier and ask for approval.
4b. Standard branch: tell TaxVerifier (StandardRevenueNotification), Writer
    (StandardBranchNotification) and TaxSpecialist (NotifyStandardRole) that no high-revenue
    audit is required; ask TaxVerifier to approve the standard revenue.
5. Approval: only TaxVerifier approves, and its answer must start with "Approved" or
   "Verified". If it starts with "Rejected", stop and report why; never approve on its behalf.
6. RevenueAnalyst: give it the classification, the expense context and TaxVerifier's exact
   approval text; ask for the final revenue analysis (FinalRevenueAnalysis). Never ask for it
   before the approval exists.
7. Writer, last: give it the expense analysis and the final revenue analysis; it composes and
   delivers the report (GenerateReport) and returns the path. Finish by reporting the branch
   taken, the approval text and the delivered path to the user.

Never skip a step, never reorder steps, and never perform a role's work yourself."""

# The minimal-instruction arm of docs/HOSTED_AGENT_COMPARISON.md: the same goal and the same
# six role tools, with no ordering, approval or separation-of-duty rule in the prompt, so
# whether the protocol holds depends on the runtime guard rather than on the model obeying
# prose. Selected with COORDINATOR_INSTRUCTIONS=minimal; the default is the full text above.
COORDINATOR_INSTRUCTIONS_MINIMAL = """You coordinate the Quarterly Finance Report. Six role
agents are your tools: Fetcher (reads the quarter's revenue and expense totals), ExpenseAnalyst
(analyzes the expenses), RevenueAnalyst (classifies the revenue as high or standard and writes
the revenue analysis), TaxSpecialist (looks up the tax rules and audits high revenue),
TaxVerifier (records the approval), Writer (composes and delivers the report). Each call to a
role is one message; pass the values the role needs in plain text and relay results. Produce
the quarterly report (default 2026-Q3, or the quarter the user names) and have Writer deliver
it. Finish by reporting the branch taken and the delivered path to the user."""


def coordinator_instructions() -> str:
    """The full coordinator instructions, or the minimal variant when
    COORDINATOR_INSTRUCTIONS=minimal (an azd environment value passed through azure.yaml)."""
    variant = os.environ.get("COORDINATOR_INSTRUCTIONS", "").strip().lower()
    if variant == "minimal":
        log.info("coordinator instructions: minimal variant (COORDINATOR_INSTRUCTIONS=minimal)")
        return COORDINATOR_INSTRUCTIONS_MINIMAL
    log.info("coordinator instructions: full")
    return COORDINATOR_INSTRUCTIONS


# ---------------------------------------------------------------------------- building blocks


def load_instructions(role: str) -> str:
    path = SKILLS_DIR / f"{role}.md"
    try:
        text = path.read_text(encoding="utf-8").strip()
        if text:
            return text
    except OSError:
        pass
    log.info("skills/%s.md not found; using built-in instructions", role)
    return FALLBACK_INSTRUCTIONS[role]


def make_credential():
    # DefaultAzureCredential is lazy: no token is requested until a request needs one, so
    # constructing it never prompts for a login (important for --check).
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential()


def make_client(credential):
    """One FoundryChatClient shared by every agent, built as the hosting guide shows."""
    from agent_framework.foundry import FoundryChatClient

    model = (
        os.environ.get("FOUNDRY_MODEL")
        or os.environ.get("MICROSOFT_FOUNDRY_MODEL_DEPLOYMENT_NAME")
        or os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"]
    )
    return FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"], model=model, credential=credential
    )


def toolbox_tool(credential):
    """The Foundry toolbox as one MCP tool for TaxSpecialist, or None when none is configured.

    Connection happens on first use (or `async with`), never at construction.
    """
    endpoint = os.environ.get("TOOLBOX_ENDPOINT")
    name = os.environ.get("TOOLBOX_NAME")
    if not endpoint and not name:
        return None
    if not endpoint:
        # Toolbox versions are immutable and numbered; version 1 is the first `azd deploy`.
        # The right version should come from the toolbox listing (`azd ai toolbox list` or
        # project_client.toolboxes.*), not be hard-coded.
        project = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
        endpoint = f"{project}/toolboxes/{name}/versions/1/mcp?api-version=v1"
    try:
        # Preferred: the hosting package's wrapper adds the bearer token (TOKEN_SCOPE) per
        # request and forwards the platform call-id.
        from agent_framework_foundry_hosting import FoundryToolbox

        return FoundryToolbox(
            credential, url=endpoint, name=name or "toolbox", approval_mode="never_require"
        )
    except ImportError:
        # Fallback: a plain MCP tool with a bearer token refreshed on every request.
        def bearer(_kwargs: dict[str, Any]) -> dict[str, str]:
            token = credential.get_token(TOKEN_SCOPE).token
            return {"Authorization": f"Bearer {token}"}

        return MCPStreamableHTTPTool(
            name=name or "toolbox",
            url=endpoint,
            approval_mode="never_require",
            header_provider=bearer,
        )


PLAN_FILE = HERE / "skillc_plan.ce"   # staged by the predeploy hook from ../../protocol/


def skillc_monitor_or_none():
    """skillc's monitor with the protocol pack as the pre-approved plan, or None.

    Removable as a unit: return None and the example runs unmonitored. Each role agent gets
    `monitor.middleware_for(role)`, so a tool call is checked against the Tool's owner and
    its precondition in the protocol state; the coordinator gets `middleware_for()` with the
    six role handoffs declared as agent tools (always allowed, never state-changing).
    """
    if os.environ.get("SKILLC_MONITOR", "").lower() == "off":
        log.info("skillc monitor disabled by SKILLC_MONITOR=off")
        return None
    try:
        from skillc.integrations.agent_framework import skillc_monitor
    except ImportError:
        log.info("skillc[agent-framework] not installed; running without the skillc monitor")
        return None
    monitor = skillc_monitor(
        runtime="foundry-hosted",
        root=Path(os.environ.get("HOME", ".")) / ".skillc",
        plan_path=PLAN_FILE if PLAN_FILE.is_file() else None,
        agent_tools=ROLES,
        logger=log,
    )
    verdict = (monitor.plan_decision.action if monitor.plan_decision else "no plan")
    log.info("skillc monitor active; plan %s: %s", PLAN_FILE.name, verdict)
    return monitor


def build() -> tuple[Agent, dict[str, Agent], dict[str, list[Any]]]:
    """Build the six role agents and the coordinator.

    Returns (coordinator, roles, tools_by_agent).
    """
    credential = make_credential()
    client = make_client(credential)
    monitor = skillc_monitor_or_none()
    skillc_tools = list(monitor.tools) if monitor else []
    mw_for = (lambda role=None: monitor.middleware_for(role) or None) if monitor \
        else (lambda role=None: None)
    tbx = toolbox_tool(credential)

    roles: dict[str, Agent] = {}
    tools_by_agent: dict[str, list[Any]] = {}
    for role in ROLES:
        tools: list[Any] = list(ROLE_TOOLS[role])
        if role == "TaxSpecialist" and tbx is not None:
            tools.append(tbx)
        roles[role] = Agent(
            client=client,
            instructions=load_instructions(role),
            name=role,
            description=ROLE_DESCRIPTIONS[role],
            tools=tools,
            middleware=mw_for(role),
        )
        tools_by_agent[role] = tools

    role_tools = [
        roles[r].as_tool(
            name=r,
            description=ROLE_DESCRIPTIONS[r],
            arg_description=f"The protocol message for {r}, with the values it needs.",
        )
        for r in ROLES
    ]
    coordinator_tools = [*role_tools, *skillc_tools]
    coordinator = Agent(
        client=client,
        instructions=coordinator_instructions(),
        name="finance-report-agent",
        description="Coordinates the Quarterly Finance Report across six role agents.",
        tools=coordinator_tools,
        middleware=mw_for(),
    )
    tools_by_agent["finance-report-agent"] = coordinator_tools
    return coordinator, roles, tools_by_agent


def _tool_name(t: Any) -> str:
    name = getattr(t, "name", None) or type(t).__name__
    if isinstance(t, MCPStreamableHTTPTool):
        return f"mcp:{name}"
    return str(name)


def check() -> int:
    os.environ.setdefault("FOUNDRY_PROJECT_ENDPOINT", "https://example.invalid/api/projects/check")
    os.environ.setdefault("AZURE_AI_MODEL_DEPLOYMENT_NAME", "check-model")
    coordinator, roles, tools_by_agent = build()
    quarters = ", ".join(sorted(p.stem for p in data_dir().glob("*.csv")))
    found = ", ".join(r for r in ROLES if (SKILLS_DIR / f"{r}.md").is_file()) or "none"
    print(f"data dir: {data_dir()}  (quarters: {quarters})")
    print(f"skills dir: {SKILLS_DIR}  (found: {found})")
    for role in ROLES:
        names = ", ".join(_tool_name(t) for t in tools_by_agent[role])
        print(f"agent {roles[role].name}: tools = {names}")
    names = ", ".join(_tool_name(t) for t in tools_by_agent["finance-report-agent"])
    print(f"agent {coordinator.name}: tools = {names}")
    print("check ok (no model called)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--check",
        action="store_true",
        help="build the agents, print their names and tools, exit 0 without serving",
    )
    args = ap.parse_args(argv)
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if args.check:
        return check()
    from agent_framework_foundry_hosting import ResponsesHostServer

    coordinator, _roles, _tools = build()
    server = ResponsesHostServer(coordinator)
    server.run()  # $PORT or 8088
    return 0


if __name__ == "__main__":
    sys.exit(main())

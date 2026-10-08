"""Quarterly Finance Report as a GROUP of Foundry hosted agents (one per role, A2A between them).

The six roles (Fetcher, ExpenseAnalyst, RevenueAnalyst, TaxSpecialist, TaxVerifier, Writer)
of protocols/v1.scr each run as their own hosted agent, built from this one file and selected
by the environment variable ROLE. There is no coordinator: a role carries its own instructions
(skills/<ROLE>.md), its own function tools (exactly the single-agent example's), and one A2A
tool per outgoing edge of its local type, named after the callee role. A2A is request/reply,
so a protocol "tells" is a request whose reply carries the next message(s) back; the ten
edges and the request/reply mapping are in MESSAGES below and in the README.

    ROLE=RevenueAnalyst python main.py            # serve the Responses protocol on $PORT
    ROLE=RevenueAnalyst python main.py --check    # build without network, print tools and
                                                  # edges, exit 0; no model call, no token

Framework API this file relies on. Introspected 2026-10-08 in the spike venv with
agent-framework-a2a 1.0.0b260918, a2a-sdk 1.2.1, agent-framework-core 1.19.0,
agent-framework-foundry 1.13.1, agent-framework-foundry-hosting 1.0.0b260918, httpx 0.28.1,
azure-identity 1.26.0 (the Agent / tool / FoundryChatClient / ResponsesHostServer signatures
are the ones recorded in ../../../hosted-agent-finance/src/finance-agent/main.py):

  agent_framework.a2a.A2AAgent.__init__(self, *, name=None, id=None, description=None,
      agent_card=None, url=None, client=None, http_client=None, auth_interceptor=None,
      timeout=None, supported_protocol_bindings=None, **kwargs)
      (url alone builds a minimal agent card with the JSONRPC binding; no network at
      construction; timeout None = 10s connect / 60s read / 10s write / 5s pool)
  agent_framework.a2a.A2AAgent.run(self, messages=None, *, stream=False, session=None,
      function_invocation_kwargs=None, client_kwargs=None, continuation_token=None,
      background=False, **kwargs) -> Awaitable[AgentResponse] | ResponseStream
  agent_framework.a2a.A2AAgent.as_tool(self, *, name=None, description=None, arg_name='task',
      arg_description=None, approval_mode='never_require', stream_callback=None,
      propagate_session=False) -> FunctionTool        (CONFIRMED: inherited from BaseAgent)
  a2a.client.A2ACardResolver.__init__(self, httpx_client: httpx.AsyncClient, base_url: str,
      agent_card_path: str = '/.well-known/agent-card.json')
  a2a.client.A2ACardResolver.get_agent_card(self, relative_card_path=None, http_kwargs=None,
      signature_verifier=None) -> AgentCard           (async)
  a2a.client.auth.interceptor.AuthInterceptor.__init__(self, credential_service)
      async before(self, args: BeforeArgs) / async after(self, args: AfterArgs)
      BeforeArgs fields: input, method, agent_card, context, early_return
      a2a.client.auth.credentials.ClientCallContext(*, state, timeout=None,
          service_parameters: dict[str, str] | None)
      service_parameters are copied into the HTTP request headers
      (a2a/client/transports/http_helpers.py). The stock AuthInterceptor adds Authorization
      ONLY when the agent card declares security schemes; a URL-only minimal card declares
      none, so BearerAuth below overrides `before` and sets the header unconditionally.

skillc: skillc.integrations.agent_framework.SkillcMonitor(*, runtime, root, plan_path, ...,
agent_tools, logger) and .middleware_for(role) -> [function middleware, agent middleware];
Monitor.pre_action evaluates a Tool's `requires` against the facts the SAME process's tools
added, and an agent tool (a callee) is allowed without changing state. In a group the facts a
role depends on (`approved`, `expense_analysis`, ...) are established by another agent's tool
and arrive as a labelled message, so ReceiveBridge below applies the facts a received label
carries. That is the receive half of the role's projection, which the monitor lacks today.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

from agent_framework import Agent, FunctionTool, tool

log = logging.getLogger("finance-agent-group")

HERE = Path(__file__).resolve().parent
EXAMPLE_ROOT = HERE.parent.parent  # examples/hosted-agent-finance-group
# Only `project` (this folder) is uploaded on deploy; the predeploy hook stages ../../skills
# and ../../data here, so the staged copies win and the example root is the local fallback.
SKILLS_DIR = HERE / "skills" if (HERE / "skills").is_dir() else EXAMPLE_ROOT / "skills"
REVENUE_THRESHOLD = 50_000.0  # RevenueAnalyst: high if revenue > this
DEFAULT_QUARTER = "2026-Q3"
ROLES = ("Fetcher", "ExpenseAnalyst", "RevenueAnalyst", "TaxSpecialist", "TaxVerifier", "Writer")
TOKEN_SCOPE = "https://ai.azure.com/.default"
A2A_TIMEOUT = 120.0

# ------------------------------------------------------------------------------------ topology

# azure.yaml service name of each role: finance-<role-kebab>.
SERVICE_NAMES = {
    "Fetcher": "finance-fetcher",
    "ExpenseAnalyst": "finance-expense-analyst",
    "RevenueAnalyst": "finance-revenue-analyst",
    "TaxSpecialist": "finance-tax-specialist",
    "TaxVerifier": "finance-tax-verifier",
    "Writer": "finance-writer",
}

# The ten edges of protocols/v1.scr (caller, callee): one RemoteA2A connection and one A2A tool
# each. Every edge is declared, even the ones that in the request/reply mapping are carried by
# a reply (see MESSAGES), so that the declared topology equals the protocol's.
EDGES = (
    ("Fetcher", "RevenueAnalyst"),
    ("Fetcher", "ExpenseAnalyst"),
    ("ExpenseAnalyst", "RevenueAnalyst"),
    ("ExpenseAnalyst", "Writer"),
    ("RevenueAnalyst", "TaxVerifier"),
    ("RevenueAnalyst", "Writer"),
    ("RevenueAnalyst", "TaxSpecialist"),
    ("TaxSpecialist", "TaxVerifier"),
    ("TaxVerifier", "RevenueAnalyst"),
    ("Writer", "Fetcher"),
)
CALLEES = {r: tuple(b for a, b in EDGES if a == r) for r in ROLES}

# The protocol messages: label -> (sender, receiver, facts the message carries, how the
# receiver gets it). The facts are the `adds` of the tool the sender used right before the
# message in the pack (protocol/quarterly_finance_report.ce). `via` is "request" when the
# label arrives in the A2A request that starts the receiver's run, or "reply:<Callee>" when it
# arrives in the reply of the receiver's own call to <Callee> (possibly relayed through it).
MESSAGES: dict[str, tuple[str, str, tuple[str, ...], str]] = {
    "RawRevenueData": ("Fetcher", "RevenueAnalyst", ("revenue_fetched",), "request"),
    "RawExpenseData": ("Fetcher", "ExpenseAnalyst", ("expenses_fetched",), "request"),
    # ExpenseAnalyst's reply to Fetcher carries both; Fetcher relays them in its request to
    # RevenueAnalyst, which relays ExpenseAnalysis in its request to Writer.
    "ExpenseData": ("ExpenseAnalyst", "RevenueAnalyst", ("expense_analysis",), "request"),
    "ExpenseAnalysis": ("ExpenseAnalyst", "Writer", ("expense_analysis",), "request"),
    "HighRevenueNotification": ("RevenueAnalyst", "TaxVerifier", ("revenue_classified",), "request"),
    "StandardRevenueNotification": ("RevenueAnalyst", "TaxVerifier", ("revenue_classified",), "request"),
    "HighBranchNotification": ("RevenueAnalyst", "Writer", ("revenue_classified",), "request"),
    "StandardBranchNotification": ("RevenueAnalyst", "Writer", ("revenue_classified",), "request"),
    "NotifyTaxSpecialist": ("RevenueAnalyst", "TaxSpecialist", ("revenue_classified",), "request"),
    "NotifyStandardRole": ("RevenueAnalyst", "TaxSpecialist", ("revenue_classified",), "request"),
    # TaxSpecialist's reply to RevenueAnalyst; relayed in RevenueAnalyst's request to TaxVerifier.
    "AuditReport": ("TaxSpecialist", "TaxVerifier", ("audit_report",), "request"),
    # TaxVerifier's reply to RevenueAnalyst's call.
    "Approval": ("TaxVerifier", "RevenueAnalyst", ("approved",), "reply:TaxVerifier"),
    "FinalRevenueAnalysis": ("RevenueAnalyst", "Writer", ("revenue_analysis",), "request"),
    # Writer's reply to RevenueAnalyst; RevenueAnalyst's reply to Fetcher relays it.
    "GenerateReport": ("Writer", "Fetcher", ("report_delivered",), "reply:RevenueAnalyst"),
}
LABEL_RX = re.compile(r"^\s*\[(?P<label>[A-Za-z]+)\]", re.MULTILINE)


def incoming(role: str) -> dict[str, tuple[tuple[str, ...], str]]:
    """label -> (facts, via) for the messages `role` receives."""
    return {lbl: (facts, via) for lbl, (_s, rcv, facts, via) in MESSAGES.items() if rcv == role}


def outgoing_labels(role: str) -> list[str]:
    return [lbl for lbl, (snd, _r, _f, _v) in MESSAGES.items() if snd == role]


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
# The function tools below are copied unchanged from the single-agent example
# (examples/hosted-agent-finance/src/finance-agent/main.py): same names, same semantics.


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
    # TaxVerifier is the only role with approval tools; RevenueAnalyst never gets them. In the
    # group this is also a deployment fact: the tools live in finance-tax-verifier's process,
    # under its own Entra instance identity.
    "TaxVerifier": [approve_audited, approve_standard],
    "Writer": [compose_report, deliver_report],
}

ROLE_DESCRIPTIONS = {
    "Fetcher": (
        "Entry point of the group: reads the quarter's revenue and expense totals "
        "(fetch_financials), calls ExpenseAnalyst then RevenueAnalyst, and returns the "
        "delivered report."
    ),
    "ExpenseAnalyst": (
        "Analyzes the quarter's expenses (analyze_expenses); its reply carries ExpenseData "
        "(for RevenueAnalyst) and ExpenseAnalysis (for Writer)."
    ),
    "RevenueAnalyst": (
        "Classifies revenue as high or standard (classify_revenue), obtains TaxVerifier's "
        "approval (through TaxSpecialist on the high path), writes the final revenue analysis "
        "(write_revenue_analysis) and has Writer deliver the report."
    ),
    "TaxSpecialist": (
        "Looks up tax rules (lookup_tax_rules) and audits high revenue (audit_high_revenue); "
        "its reply is the AuditReport for TaxVerifier."
    ),
    "TaxVerifier": (
        "The only role that approves: approve_audited (high branch) or approve_standard; its "
        "reply is the Approval (or a rejection) for RevenueAnalyst."
    ),
    "Writer": (
        "Composes the quarterly report (compose_report) and delivers it (deliver_report); its "
        "reply is GenerateReport for Fetcher."
    ),
}

# A2A tool descriptions, per edge, as the caller sees them.
EDGE_DESCRIPTIONS = {
    ("Fetcher", "ExpenseAnalyst"): (
        "Send [RawExpenseData] (expense total and line items) to ExpenseAnalyst, a separate "
        "hosted agent. Its reply carries [ExpenseData] and [ExpenseAnalysis]."
    ),
    ("Fetcher", "RevenueAnalyst"): (
        "Send [RawRevenueData] (revenue total) plus the received [ExpenseData] and "
        "[ExpenseAnalysis] to RevenueAnalyst, a separate hosted agent. Its reply carries "
        "[GenerateReport], the delivered report, after the approval chain completed."
    ),
    ("ExpenseAnalyst", "RevenueAnalyst"): (
        "Protocol edge ExpenseAnalyst->RevenueAnalyst (ExpenseData). In this deployment the "
        "message travels in your reply (Fetcher relays it); do not call this tool."
    ),
    ("ExpenseAnalyst", "Writer"): (
        "Protocol edge ExpenseAnalyst->Writer (ExpenseAnalysis). In this deployment the "
        "message travels in your reply (relayed by Fetcher and RevenueAnalyst); do not call "
        "this tool."
    ),
    ("RevenueAnalyst", "TaxSpecialist"): (
        "Send [NotifyTaxSpecialist] (high path: request the audit, give the revenue total) or "
        "[NotifyStandardRole] (standard path) to TaxSpecialist, a separate hosted agent. On "
        "the high path its reply carries [AuditReport]."
    ),
    ("RevenueAnalyst", "TaxVerifier"): (
        "Send [HighRevenueNotification] with TaxSpecialist's [AuditReport] verbatim, or "
        "[StandardRevenueNotification] with the revenue total, to TaxVerifier, a separate "
        "hosted agent. Its reply carries [Approval] (starting with Approved or Verified) or "
        "[Rejected]."
    ),
    ("RevenueAnalyst", "Writer"): (
        "Send [HighBranchNotification] or [StandardBranchNotification], the [ExpenseAnalysis] "
        "verbatim and your [FinalRevenueAnalysis] to Writer, a separate hosted agent. Its "
        "reply carries [GenerateReport]."
    ),
    ("TaxSpecialist", "TaxVerifier"): (
        "Protocol edge TaxSpecialist->TaxVerifier (AuditReport). In this deployment the audit "
        "travels in your reply (RevenueAnalyst relays it); do not call this tool."
    ),
    ("TaxVerifier", "RevenueAnalyst"): (
        "Protocol edge TaxVerifier->RevenueAnalyst (Approval). In this deployment the approval "
        "IS your reply; do not call this tool."
    ),
    ("Writer", "Fetcher"): (
        "Protocol edge Writer->Fetcher (GenerateReport). In this deployment the report travels "
        "in your reply (RevenueAnalyst relays it to Fetcher); do not call this tool."
    ),
}

FALLBACK_INSTRUCTIONS = {
    "Fetcher": (
        "You are Fetcher, the entry point. Use fetch_financials to read the quarter's revenue "
        "and expense totals. Call the ExpenseAnalyst tool with [RawExpenseData] (expense total "
        "and line items); keep its [ExpenseData] and [ExpenseAnalysis]. Then call the "
        "RevenueAnalyst tool with [RawRevenueData] (revenue total) plus both received messages "
        "verbatim; its reply carries [GenerateReport]. Return [GenerateReport] to the user. Do "
        "not analyze, approve, or write the report yourself."
    ),
    "ExpenseAnalyst": (
        "You are ExpenseAnalyst. The request carries [RawExpenseData]. Use analyze_expenses and "
        "reply with two labelled messages: [ExpenseData] <analyzed expense amount> and "
        "[ExpenseAnalysis] <substantive analysis>. Your reply is these protocol messages; do "
        "not call RevenueAnalyst or Writer. Do not approve revenue or write the final report."
    ),
    "RevenueAnalyst": (
        "You are RevenueAnalyst. The request carries [RawRevenueData], [ExpenseData] and "
        "[ExpenseAnalysis]. Use classify_revenue. High (> $50,000): call TaxSpecialist with "
        "[NotifyTaxSpecialist], then TaxVerifier with [HighRevenueNotification] and the "
        "[AuditReport] verbatim. Standard: call TaxSpecialist with [NotifyStandardRole], then "
        "TaxVerifier with [StandardRevenueNotification]. Only after a reply with [Approval] "
        "starting with Approved or Verified, use write_revenue_analysis, then call Writer with "
        "the branch notification, [ExpenseAnalysis] and [FinalRevenueAnalysis]. Reply to "
        "Fetcher with Writer's [GenerateReport]. Never approve your own work."
    ),
    "TaxSpecialist": (
        "You are TaxSpecialist. On [NotifyTaxSpecialist], use lookup_tax_rules then "
        "audit_high_revenue and reply with [AuditReport] <the audit>; it is addressed to "
        "TaxVerifier and RevenueAnalyst relays it. On [NotifyStandardRole], reply "
        "[Acknowledged] no audit required. Do not approve or write the report."
    ),
    "TaxVerifier": (
        "You are TaxVerifier. On [HighRevenueNotification] with an [AuditReport], use "
        "approve_audited; on [StandardRevenueNotification], use approve_standard. Reply with "
        "[Approval] followed by the tool's text verbatim (it starts with Approved or Rejected; "
        "use [Rejected] as the label when it does). Your reply is the Approval message to "
        "RevenueAnalyst. You are the only role that may approve; never approve your own work."
    ),
    "Writer": (
        "You are Writer. The request carries the branch notification, [ExpenseAnalysis] and "
        "[FinalRevenueAnalysis]. Use compose_report, then deliver_report, and reply with "
        "[GenerateReport] <the delivered path and the report>. Do not deliver an incomplete "
        "report."
    ),
}


# ---------------------------------------------------------------------------- building blocks


def role_from_env(override: str | None = None) -> str:
    role = (override or os.environ.get("ROLE") or "").strip()
    if role not in ROLES:
        raise SystemExit(f"ROLE must be one of {', '.join(ROLES)}; got {role!r}")
    return role


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
    # constructing it never prompts for a login (important for --check). Inside the hosted
    # sandbox it resolves to the agent's own instance identity.
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential()


def make_client(credential):
    """One FoundryChatClient for this role's agent, built as the hosting guide shows."""
    from agent_framework.foundry import FoundryChatClient

    model = (
        os.environ.get("FOUNDRY_MODEL")
        or os.environ.get("MICROSOFT_FOUNDRY_MODEL_DEPLOYMENT_NAME")
        or os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"]
    )
    return FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"], model=model, credential=credential
    )


# ------------------------------------------------------------------------------------ A2A edges


def a2a_base_url(callee: str) -> str:
    """The callee's A2A base path: {project}/agents/{service}/endpoint/protocols/a2a."""
    project = os.environ["FOUNDRY_PROJECT_ENDPOINT"].rstrip("/")
    return f"{project}/agents/{SERVICE_NAMES[callee]}/endpoint/protocols/a2a"


class BearerAuth:
    """`Authorization: Bearer <token>` on every A2A request, from the caller's own identity.

    Mixed into a2a.client.auth.interceptor.AuthInterceptor by `make_bearer_auth` (resolved at
    call time so that the module imports without the a2a package). The stock `before` consults
    the agent card's security schemes; a minimal card has none, so this one sets the header
    unconditionally. The token (scope TOKEN_SCOPE) is cached until two minutes before expiry.
    """

    def __init__(self, credential=None):
        self._credential = credential
        self._token: str | None = None
        self._expires_on = 0.0

    async def _bearer(self) -> str:
        if self._token and time.time() < self._expires_on - 120:
            return self._token
        if self._credential is None:
            from azure.identity.aio import DefaultAzureCredential

            self._credential = DefaultAzureCredential()
        access = await self._credential.get_token(TOKEN_SCOPE)
        self._token, self._expires_on = access.token, float(access.expires_on)
        return self._token

    async def before(self, args) -> None:
        from a2a.client.auth.credentials import ClientCallContext

        if args.context is None:
            args.context = ClientCallContext()
        if args.context.service_parameters is None:
            args.context.service_parameters = {}
        args.context.service_parameters["Authorization"] = f"Bearer {await self._bearer()}"

    async def after(self, args) -> None:
        return None


def make_bearer_auth():
    """BearerAuth as an AuthInterceptor subclass (the type A2AAgent's `auth_interceptor`
    expects). AuthInterceptor.__init__ (which wants a CredentialService) is bypassed on purpose;
    BearerAuth.before never reads `_credential_service`."""
    from a2a.client.auth.interceptor import AuthInterceptor

    cls = type("BearerAuthInterceptor", (BearerAuth, AuthInterceptor), {})
    return cls()


async def resolve_agent_card(callee: str, auth: BearerAuth):
    """The callee's agent card from {base}/agentCard/v1.0 (needs network and a token).

    Used only when A2A_FETCH_CARD=1: the URL-only minimal card is enough to call the callee,
    and fetching the card at startup would delay every cold start by one request per edge.
    verify against azd/Foundry: the card path and whether the card's `supported_interfaces`
    URL equals the base path used here.
    """
    import httpx
    from a2a.client import A2ACardResolver

    base = a2a_base_url(callee)
    async with httpx.AsyncClient(timeout=A2A_TIMEOUT) as http:
        resolver = A2ACardResolver(httpx_client=http, base_url=base, agent_card_path="agentCard/v1.0")
        headers = {"Authorization": f"Bearer {await auth._bearer()}"}
        return await resolver.get_agent_card(http_kwargs={"headers": headers})


def a2a_tools(role: str) -> list[FunctionTool]:
    """One A2A tool per outgoing edge of `role`, named after the callee role."""
    from agent_framework.a2a import A2AAgent

    tools: list[FunctionTool] = []
    for callee in CALLEES[role]:
        auth = make_bearer_auth()
        card = None
        if os.environ.get("A2A_FETCH_CARD") == "1":
            try:
                card = asyncio.run(resolve_agent_card(callee, auth))
            except Exception as e:  # noqa: BLE001 - the minimal card is always enough
                log.warning("agent card of %s not fetched (%s); using the URL", callee, e)
        remote = A2AAgent(
            name=callee,
            description=ROLE_DESCRIPTIONS[callee],
            agent_card=card,
            url=a2a_base_url(callee),
            auth_interceptor=auth,
            timeout=A2A_TIMEOUT,
        )
        tools.append(
            remote.as_tool(
                name=callee,
                description=EDGE_DESCRIPTIONS[(role, callee)],
                arg_description=(
                    f"The protocol message(s) for {callee}, each on a line starting with its "
                    "label in square brackets, e.g. [RawRevenueData] 72000.00, with the values "
                    "its tools need in plain text."
                ),
            )
        )
    return tools


# --------------------------------------------------------------------------------- skillc


PLAN_FILE = HERE / "skillc_plan.ce"  # staged by the predeploy hook from ../../protocol/


def skillc_monitor_or_none(role: str):
    """skillc's monitor for this role's process with the protocol pack as the pre-approved
    plan, or None. Removable as a unit: return None and the role runs unmonitored.

    `agent_tools` are the callee roles this agent calls: always allowed, never a change of
    protocol state. The role's own function tools are checked against the Tool's owner (which
    is this role, by construction: the other roles' tools are in other processes under other
    identities) and its precondition in the local protocol state.
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
        agent_tools=CALLEES[role],
        logger=log,
    )
    verdict = monitor.plan_decision.action if monitor.plan_decision else "no plan"
    log.info("skillc monitor active for %s; plan %s: %s", role, PLAN_FILE.name, verdict)
    return monitor


def _labels_in(text: str) -> list[str]:
    return list(dict.fromkeys(m.group("label") for m in LABEL_RX.finditer(text or "")))


def _apply_received(monitor, role: str, text: str, via: str) -> list[str]:
    """Add to the monitor's protocol state the facts carried by the labelled messages in
    `text` that `role` may receive through `via` ("request" or "reply:<Callee>"); with
    via="request" the state is first reset to the pack's initial facts, because one incoming
    A2A request is one run of the role's local protocol. Returns the facts added.

    The bridge trusts labels the way the protocol trusts messages; who may send them is the
    platform's check (Entra on the A2A endpoint, Foundry Agent Consumer on the callee).
    """
    core = getattr(monitor, "core", None)
    if core is None:
        return []
    accepted = incoming(role)
    facts = [f for lbl in _labels_in(text) if lbl in accepted and accepted[lbl][1] == via
             for f in accepted[lbl][0]]
    added: list[str] = []
    try:
        from skillc.monitor import state_lock

        with state_lock(core.state_path):
            try:
                if via == "request":
                    core.state.facts = list((core.plan_pack() or {}).get("init_true", []))
                added = [f for f in facts if f not in core.state.facts]
                core.state.facts.extend(added)
            finally:
                core.save()
    except Exception as e:  # noqa: BLE001 - never stop the agent
        log.warning("skillc receive bridge (%s): %s; allowing", via, e)
        return []
    if added or via == "request":
        log.info("skillc receive bridge (%s, %s): facts now %s", role, via, core.state.facts)
    return added


def receive_bridge(monitor, role: str) -> list:
    """The two middleware objects that give the monitor the receive events of the projection:
    the incoming request's labels (agent middleware) and each callee's reply labels (function
    middleware, for the A2A tools only)."""
    from agent_framework import AgentContext, AgentMiddleware, FunctionInvocationContext, FunctionMiddleware

    class RequestLabels(AgentMiddleware):
        async def process(self, context: AgentContext, call_next) -> None:
            try:
                text = ""
                for m in reversed(list(getattr(context, "messages", []) or [])):
                    if getattr(m, "role", None) == "user" and isinstance(getattr(m, "text", None), str):
                        text = m.text
                        break
                _apply_received(monitor, role, text, "request")
            except Exception as e:  # noqa: BLE001
                log.warning("skillc receive bridge (request): %s; allowing", e)
            await call_next()

    class ReplyLabels(FunctionMiddleware):
        async def process(self, context: FunctionInvocationContext, call_next) -> None:
            await call_next()
            try:
                name = str(getattr(context.function, "name", None) or context.function)
                if name in CALLEES[role]:
                    result = context.result
                    text = result if isinstance(result, str) else str(getattr(result, "text", result))
                    _apply_received(monitor, role, text, f"reply:{name}")
            except Exception as e:  # noqa: BLE001
                log.warning("skillc receive bridge (reply): %s; allowing", e)

    return [RequestLabels(), ReplyLabels()]


# ------------------------------------------------------------------------------------- build


def build(role: str) -> tuple[Agent, list[Any]]:
    """Build this role's agent: its function tools, its A2A tools, its monitor."""
    credential = make_credential()
    client = make_client(credential)
    monitor = skillc_monitor_or_none(role)
    middleware: list = []
    if monitor is not None:
        middleware = [*receive_bridge(monitor, role), *(monitor.middleware_for(role) or [])]
    tools: list[Any] = [*ROLE_TOOLS[role], *a2a_tools(role)]
    agent = Agent(
        client=client,
        instructions=load_instructions(role),
        name=SERVICE_NAMES[role],
        description=ROLE_DESCRIPTIONS[role],
        tools=tools,
        middleware=middleware or None,
    )
    return agent, tools


def _tool_name(t: Any) -> str:
    return str(getattr(t, "name", None) or type(t).__name__)


def check(role: str) -> int:
    os.environ.setdefault("FOUNDRY_PROJECT_ENDPOINT", "https://example.invalid/api/projects/check")
    os.environ.setdefault("AZURE_AI_MODEL_DEPLOYMENT_NAME", "check-model")
    os.environ.pop("A2A_FETCH_CARD", None)  # never touch the network in --check
    agent, tools = build(role)
    quarters = ", ".join(sorted(p.stem for p in data_dir().glob("*.csv")))
    skill = SKILLS_DIR / f"{role}.md"
    print(f"role: {role}  (service {SERVICE_NAMES[role]}, agent name {agent.name})")
    print(f"data dir: {data_dir()}  (quarters: {quarters})")
    print(f"skills dir: {SKILLS_DIR}  ({role}.md {'found' if skill.is_file() else 'missing; built-in instructions'})")
    print(f"tools: {', '.join(_tool_name(t) for t in tools)}")
    for callee in CALLEES[role]:
        print(f"edge {role} -> {callee}: a2a tool {callee!r} -> {a2a_base_url(callee)}")
    print("sends: " + ", ".join(outgoing_labels(role)))
    print("receives: " + ", ".join(f"{lbl} via {via}" for lbl, (_f, via) in incoming(role).items()))
    print("check ok (no model called, no token requested)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--role", help="the role to run (default: $ROLE)")
    ap.add_argument(
        "--check",
        action="store_true",
        help="build the role's agent, print its tools and edges, exit 0 without serving",
    )
    args = ap.parse_args(argv)
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    role = role_from_env(args.role)
    if args.check:
        return check(role)
    from agent_framework_foundry_hosting import ResponsesHostServer

    agent, _tools = build(role)
    server = ResponsesHostServer(agent)
    server.run()  # $PORT or 8088
    return 0


if __name__ == "__main__":
    sys.exit(main())

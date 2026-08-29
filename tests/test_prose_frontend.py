"""The deterministic front-end's *semantic* reading of a skill document.

These exercise the extraction, not the corpus: every document here is written
inline, so a test failure means the reading rules changed, not that a corpus
file moved.  The compaction only engages when a document states what
"finished" means; everything else keeps the weaker used_<tool> reading.
"""
import textwrap

from skillc import check, compile_markdown, load_profile
from skillc.frontend.prose import (parse_goal, parse_roles, split_bullets,
                                   stem)

NONE = load_profile("none")


def md(body: str) -> str:
    return textwrap.dedent(body).lstrip("\n")


# ------------------------------------------------------------------ reading

def test_stem_relates_verb_forms():
    assert stem("booked") == stem("booking") == stem("book")
    assert stem("sent") == stem("sends") == stem("send")
    assert stem("notified") == stem("notify")


def test_goal_conditions_come_from_the_completion_sentence():
    conds, var = parse_goal(
        "Your job is finished when the flight is **booked** and a "
        "**confirmation email has been sent**.")
    assert [c.predicate for c in conds] == ["booked", "sent"]
    assert var is None


def test_numeric_condition_is_split_from_the_state():
    conds, var = parse_goal(
        "Your job is finished when the part is **ordered at a cost below "
        "200**.")
    assert conds[0].predicate == "ordered"
    assert (conds[0].num.op, conds[0].num.value) == ("<", 200)
    assert var == "price"


def test_participants_are_read_from_the_introduction():
    roles = parse_roles("Two participants take part: a **router** and a "
                        "**handler**.")
    assert [r.name for r in roles] == ["router", "handler"]


def test_participant_alias_in_backticks_names_the_role():
    roles = parse_roles("Two participants take part: the billing **system** "
                        "(`sys`) and the **payer**.")
    assert [r.name for r in roles] == ["sys", "payer"]
    assert "system" in roles[0].aliases


def test_commentary_after_a_bullet_list_is_not_a_bullet():
    head, bullets = split_bullets(
        "pick one:\n- **a** — do a.\n- **b** — do b.\n\nEither way is fine.\n")
    assert len(bullets) == 2
    assert "Either way" not in "".join(bullets)


# ---------------------------------------------------------------- compaction

def test_document_without_a_completion_sentence_keeps_the_weak_reading():
    res = compile_markdown(md("""
        # Tidy up
        Tools: sweep.
        First use `sweep`, then stop.
        """), NONE)
    assert res.pack["goal"] == {"and": ["used_sweep"]}
    assert check(res.pack).achievable


def test_condition_no_step_establishes_is_refuted():
    res = compile_markdown(md("""
        ---
        name: onboard
        ---
        # Onboard

        Your job is finished when the account is **created** and the badge is
        **issued**.

        ## Tools

        Tools: create_account.

        ## Workflow

        1. Create the employee's account.
        """), NONE)
    v = check(res.pack)
    assert not v.achievable and v.reason == "GOAL_UNSAT"
    assert "issued" in v.frontier


def test_granting_the_missing_establisher_flips_the_verdict():
    doc = md("""
        # Onboard

        Your job is finished when the account is **created** and the badge is
        **issued**.

        ## Tools

        Tools: create_account, issue_badge.

        ## Workflow

        1. Create the employee's account.
        2. Issue the badge.
        """)
    assert check(compile_markdown(doc, NONE).pack).achievable


def test_a_tool_named_for_the_condition_establishes_it():
    """The step's verb need not be the goal's verb when the tool is named
    for exactly what the condition is about."""
    res = compile_markdown(md("""
        # Provision

        Your job is finished when the machine is **imaged** and the asset
        register has been **updated**.

        ## Tools

        Tools: image_machine, register_asset.

        ## Workflow

        1. Image the machine with the standard build.
        2. Register the asset in the inventory system.
        """), NONE)
    assert "updated" in res.pack["capabilities"]["register_asset"]["add"]
    assert check(res.pack).achievable


def test_a_stated_guard_with_no_establisher_blocks():
    res = compile_markdown(md("""
        # Publish

        Your job is finished when the report is **published**.

        ## Tools

        Tools: draft, publish.

        `publish` requires the report to be **approved** before it will run.

        ## Workflow

        1. Draft the report.
        2. Publish it.
        """), NONE)
    assert res.pack["capabilities"]["publish"]["pre"] == "approved"
    v = check(res.pack)
    assert not v.achievable and v.reason == "BLOCKED_GUARD"


def test_a_stated_bound_can_refute_a_budget():
    doc = md("""
        # Order parts

        Your job is finished when the part is **ordered at a cost below 200**.

        ## Tools

        Tools: order_{kind}.

        `order_{kind}` only ever orders parts {note}.

        ## Workflow

        1. Order it with `order_{kind}`.
        """)
    over = compile_markdown(doc.format(kind="premium", note="costing 350 or "
                                       "more"), NONE)
    under = compile_markdown(doc.format(kind="budget", note="under 200"), NONE)
    assert not check(over.pack).achievable
    assert check(under.pack).achievable


def test_an_unannounced_choice_that_strands_a_role_is_refuted():
    res = compile_markdown(md("""
        # Escalate

        Two participants take part: a **monitor** and an **oncall**.

        Your job is finished when the alert has been **acknowledged**.

        ## Tools

        Tools: page, acknowledge.

        ## Workflow

        1. The monitor decides whether the alert is urgent:
           - **urgent** — the monitor pages the oncall, and the oncall
             acknowledges the alert with `acknowledge`.
           - **routine** — the monitor files it for the morning review.

        The monitor does not tell the oncall which way it went.
        """), NONE)
    v = check(res.pack)
    assert not v.achievable and v.reason == "NON_PROJECTABLE"


def test_announcing_the_choice_makes_it_projectable():
    res = compile_markdown(md("""
        # Escalate

        Two participants take part: a **monitor** and an **oncall**.

        Your job is finished when the alert has been **acknowledged**.

        ## Tools

        Tools: ack_now, ack_later.

        ## Workflow

        1. The monitor decides whether the alert is urgent:
           - **urgent** — the monitor tells the oncall `go_now`, and the
             oncall acknowledges it with `ack_now`.
           - **routine** — the monitor tells the oncall `go_later`, and the
             oncall acknowledges it with `ack_later`.
        """), NONE)
    branches = res.pack["protocol"][0]["choice"]["branches"]
    assert set(branches) == {"urgent", "routine"}
    assert branches["urgent"][0]["msg"]["label"] == "go_now"
    assert check(res.pack).achievable


def test_spawning_helpers_leaves_the_decidable_fragment():
    res = compile_markdown(md("""
        # Fan out

        A **planner** carries out this skill.

        Your job is finished when the report has been **delivered**.

        ## Tools

        Tools: deliver.

        ## Workflow

        1. Spawn a fresh helper subagent for each part of the question.
        2. Deliver the report.
        """), NONE)
    v = check(res.pack)
    assert v.unknown and v.reason == "DYNAMIC_TOPOLOGY"
    assert not v.refuted


def test_declared_role_behaviour_must_cover_the_contract():
    doc = md("""
        # Triage

        Two participants take part: a **router** and a **handler**.

        Your job is finished when the ticket is **resolved**.

        ## Tools

        Tools: fix_fast, fix_slow.

        ## Contract

        1. The router picks one of two paths:
           - **fast path** — the router tells the handler `go_fast`, and the
             handler resolves the ticket with `fix_fast`.
           - **slow path** — the router tells the handler `go_slow`, and the
             handler resolves the ticket with `fix_slow`.

        ## Declared handler behaviour

        {behaviour}
        """)
    partial = compile_markdown(doc.format(
        behaviour="The handler waits for `go_fast`, then resolves the ticket "
                  "with `fix_fast`."), NONE)
    v = check(partial.pack)
    assert not v.achievable and v.reason == "NON_CONFORMANT"

    tolerant = compile_markdown(doc.format(behaviour=md("""
        The handler acts on whichever label arrives:

        - `go_fast` — resolve the ticket with `fix_fast`.
        - `go_slow` — resolve the ticket with `fix_slow`.
        - `go_hold` — park the ticket, then resolve it with `fix_slow`.
        """)), NONE)
    assert check(tolerant.pack).achievable

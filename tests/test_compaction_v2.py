"""Compaction v2 ("P2g+", runs/20261015_review_response/PLAN.md, Addendum B):
branch assumptions (F-a), the universal `reply` tool (F-b), prompt rules 11-14
(F-c, F-f), two located-error retries (F-e) and gate compaction with the
effective runtime (F-d).  No test calls a model."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import shutil
import textwrap
from copy import deepcopy
from pathlib import Path

import pytest

from skillc import check
from skillc.checker import establishable_atoms
from skillc.frontend import llm, prompts, providers
from skillc.frontend.ce import (CE_VERSION, CEError, canonical_pack, compile_ce, parse_ce,
                                parse_ce_detailed, render_ce)
from skillc.frontend.runtime import (UNIVERSAL_TOOLS, Runtime, bind_runtime, load_runtime,
                                     runtime_note)
from skillc.frontend.toolpolicy import load_library
from skillc.pack import Pack, PackError, normalize, validate_pack

ROOT = Path(__file__).parent.parent
FROZEN = Path(__file__).parent / "fixtures" / "p2g_prompts" / "frozen.json"
MESSAGE_HASHES = FROZEN.with_name("message_hashes.json")
FINANCE = ROOT / "examples" / "hosted-agent-finance"


# --------------------------------------------------------------------------
# F-a: branch assumptions -- schema
# --------------------------------------------------------------------------

def _pack(assumes=None) -> dict:
    """c045's shape: an environment-decided fact guards the deliverable."""
    choice = {"by": "agent", "observed": True,
              "branches": {"next_line_app": [{"act": {"cap": "update", "by": "agent"}}],
                           "other": []}}
    if assumes is not None:
        choice["assumes"] = assumes
    return {
        "name": "s", "roles": ["agent"],
        "capabilities": {
            "inspect": {"owner": "agent", "add": ["inspected"]},
            "update": {"owner": "agent",
                       "pre": {"and": ["inspected", "is_next_line_app"]},
                       "add": ["app_updated"]},
        },
        "protocol": [{"act": {"cap": "inspect", "by": "agent"}}, {"choice": choice}],
        "goal": "app_updated",
    }


def test_schema_accepts_branch_assumptions():
    validate_pack(_pack({"next_line_app": ["is_next_line_app"]}))
    validate_pack(_pack({"next_line_app": ["b", "a"], "other": []}))


@pytest.mark.parametrize("assumes, msg", [
    (["is_next_line_app"], "must map branch labels"),
    ({"missing": ["p"]}, "not a branch"),
    ({"next_line_app": "is_next_line_app"}, "list of predicate names"),
    ({"next_line_app": [""]}, "list of predicate names"),
    ({"next_line_app": [3]}, "list of predicate names"),
])
def test_schema_rejects_malformed_assumptions(assumes, msg):
    with pytest.raises(PackError, match=msg):
        validate_pack(_pack(assumes))


def test_normalize_and_canonical_pack_sort_and_deduplicate_assumptions():
    raw = _pack({"other": [], "next_line_app": ["z", "is_next_line_app", "z"]})
    want = {"next_line_app": ["is_next_line_app", "z"]}
    assert normalize(raw).protocol[1]["choice"]["assumes"] == want
    assert canonical_pack(raw)["protocol"][1]["choice"]["assumes"] == want


def test_packs_without_assumptions_normalize_to_the_same_object():
    raw = _pack()
    assert Pack.load(raw).protocol is raw["protocol"]


# --------------------------------------------------------------------------
# F-a: checker
# --------------------------------------------------------------------------

@pytest.mark.parametrize("semantics", ["may", "adversarial"])
def test_assumption_turns_a_blocked_guard_into_achievable(semantics):
    before = check(_pack(), semantics=semantics)
    assert before.label == "IMPOSSIBLE" and before.reason == "BLOCKED_GUARD"
    after = check(_pack({"next_line_app": ["is_next_line_app"]}), semantics=semantics)
    assert after.label == "ACHIEVABLE" and after.protocol == "WELL_TYPED"
    assert ("choose", "next_line_app") in after.witness


def test_mutant_without_the_assumption_is_refuted_again():
    good = _pack({"next_line_app": ["is_next_line_app"]})
    assert check(good).achievable
    mutant = deepcopy(good)
    del mutant["protocol"][1]["choice"]["assumes"]
    v = check(mutant)
    assert v.refuted and v.reason == "BLOCKED_GUARD"
    # an assumption on the wrong branch does not help either
    wrong = _pack({"other": ["is_next_line_app"]})
    assert check(wrong).refuted


def test_assumed_atoms_are_establishable():
    pack = _pack({"next_line_app": ["is_next_line_app"]})
    assert "is_next_line_app" in establishable_atoms(normalize(pack))
    # a goal atom only an assumption can make true is not refuted by the closure
    only = _pack({"next_line_app": ["app_updated"]})
    only["protocol"][1]["choice"]["branches"]["next_line_app"] = []
    del only["capabilities"]["update"]
    assert check(only).achievable
    assert not check(only, scope="goal").refuted
    del only["protocol"][1]["choice"]["assumes"]
    v = check(only)
    assert v.refuted and v.context_refuted


def test_assumption_holds_only_inside_its_branch():
    pack = _pack({"next_line_app": ["is_next_line_app"]})
    # the update runs after the choice, on both branches: `other` is blocked,
    # `next_line_app` reaches the goal, so may-semantics finds the witness
    pack["protocol"][1]["choice"]["branches"]["next_line_app"] = []
    pack["protocol"].append({"act": {"cap": "update", "by": "agent"}})
    v = check(pack)
    assert v.achievable
    assert ("choose", "next_line_app") in v.witness


# --------------------------------------------------------------------------
# F-a: Controlled English
# --------------------------------------------------------------------------

CE_ASSUMING = textwrap.dedent("""\
    Skill `s`.
    Roles: `agent`, `user`.
    Tool `inspect` (owner `agent`): adds `inspected`.
    Tool `update` (owner `agent`): requires `inspected` and `is_next_line_app`; adds `app_updated`.
    Goal: `app_updated`.
    Protocol:
      - `agent` uses `inspect`.
      - `user` chooses one of (observed):
        - branch `next_line_app` (assuming `is_next_line_app`, `has_lockfile`):
          - `agent` uses `update`.
        - branch `bridge_only` (assuming `bridge_app`): none.
        - branch `other`: none.
    """)


def test_ce_version_is_bumped():
    assert CE_VERSION == "1.4"


def test_ce_assuming_parses_into_choice_assumes():
    pack = compile_ce(CE_ASSUMING)
    assert pack["protocol"][1]["choice"]["assumes"] == {
        "bridge_only": ["bridge_app"],
        "next_line_app": ["has_lockfile", "is_next_line_app"]}
    assert check(pack).achievable


def test_ce_round_trip_with_assumptions():
    pack = compile_ce(CE_ASSUMING)
    text = render_ce(pack)
    assert "- branch `next_line_app` (assuming `has_lockfile`, `is_next_line_app`):" in text
    assert "- branch `bridge_only` (assuming `bridge_app`): none." in text
    assert parse_ce(text) == canonical_pack(pack)
    raw = _pack({"next_line_app": ["z", "is_next_line_app", "z"], "other": []})
    assert parse_ce(render_ce(raw)) == canonical_pack(raw)


@pytest.mark.parametrize("head, line, col, msg", [
    ("- branch `next_line_app` (assuming lockfile):", 9, 40,
     "expected a backticked identifier, got word 'lockfile'"),
    ("- branch `next_line_app` (assumes `is_next_line_app`):", 9, 31, "expected 'assuming'"),
    ("- branch `next_line_app` (assuming):", 9, 39, "expected a backticked identifier"),
    ("- branch `next_line_app` (assuming `is_next_line_app`:", 9, 58, r"expected '\)'"),
])
def test_ce_malformed_assuming_is_a_located_error(head, line, col, msg):
    bad = CE_ASSUMING.replace(
        "- branch `next_line_app` (assuming `is_next_line_app`, `has_lockfile`):", head)
    with pytest.raises(CEError, match=msg) as err:
        parse_ce(bad)
    assert f"line {line}, column {col}: " in str(err.value)
    assert (err.value.line, err.value.col) == (line, col)


def test_ce_assuming_is_rejected_in_a_behaviour():
    doc = CE_ASSUMING + textwrap.dedent("""\
        Behaviour of `user`:
          - select one of:
            - branch `next_line_app` (assuming `x`): none.
        """)
    with pytest.raises(CEError, match="only on the branches of a protocol choice") as err:
        parse_ce(doc)
    assert err.value.line == 15


# --------------------------------------------------------------------------
# F-b: the universal `reply` tool
# --------------------------------------------------------------------------

REPLY_DOC = textwrap.dedent("""\
    Skill `process-doc`.
    Roles: `agent`, `user`.
    Tool `ask_process_questions` (owner `agent`): via `ask_user`; adds `process_info_gathered`.
    Tool `write_sop` (owner `agent`): via `reply`; adds `sop_documented`.
    Goal: `sop_documented`.
    Protocol:
      - `user` chooses one of (observed):
        - branch `provide_process_details`: none.
        - branch `need_questions`:
          - `agent` uses `ask_process_questions`.
      - `agent` uses `write_sop`.
    """)

NO_REPLY = Runtime.from_dict({"name": "bare", "description": "a manifest without reply",
                              "tools": {"bash": "run commands"}, "grants": []})


@pytest.mark.parametrize("runtime", [load_runtime("developer-sandbox"), NO_REPLY],
                         ids=["developer-sandbox", "no-reply-listed"])
def test_tool_via_reply_binds_and_checks_achievable(runtime):
    assert "reply" not in runtime.tools
    doc = REPLY_DOC if "ask_user" in runtime.tools else REPLY_DOC.replace(
        "via `ask_user`", "via `bash`")
    parsed = parse_ce_detailed(doc)
    for kwargs in ({}, {"prune": False}, {"library": load_library(), "software": True}):
        bound = bind_runtime(parsed.pack, parsed.bindings, runtime, **kwargs)
        assert "write_sop" in bound.pack["capabilities"]
        assert "write_sop" not in bound.withdrawn and "write_sop" not in bound.blocked
        assert check(bound.pack).label == "ACHIEVABLE"


def test_reply_is_listed_only_in_the_p2g_plus_runtime_note():
    rt = load_runtime("developer-sandbox")
    assert "`reply`" not in runtime_note(rt)
    note = runtime_note(rt, universal=True)
    assert f"  - `reply`: {UNIVERSAL_TOOLS['reply']}\n" in note
    assert rt.has_tool("reply") and "reply" in rt.all_tools and "reply" not in rt.tools


# --------------------------------------------------------------------------
# F-c / F-f: prompt versions
# --------------------------------------------------------------------------

def _prompt_message_cases():
    text = "Draft a report, obtain approval, then send it.\nDo not send unapproved drafts."
    yield "ce|plain", prompts.ce_messages(text)
    yield "ce|abilities", prompts.ce_messages(text, ["read files", "ask the user"])
    runtimes = [
        load_runtime(name) for name in (
            "developer-sandbox", "claude-code-cloud", "foundry-hosted",
            "office-assistant", "offline-workstation", "scout-desktop",
        )
    ]
    runtimes.append(Runtime("empty", "No external tools or resources.", {}, (), ()))
    for rt in runtimes:
        for version in ("p2g", "p2g+", "p2g++"):
            for levels in (False, True):
                yield f"{rt.name}|{version}|levels={levels}", prompts.ce_runtime_messages(
                    text, rt, levels=levels, version=version,
                )
        yield f"{rt.name}|grounded", prompts.ce_grounded_messages(text, rt)
        yield f"{rt.name}|tool-policy", prompts.ce_tpl_messages(text, rt, [])
        yield f"{rt.name}|index", prompts.ce_index_messages(text, rt, "REFERENCE FACTS\n")
        yield f"{rt.name}|json", prompts.json_runtime_messages(text, rt)
        yield f"{rt.name}|direct", prompts.direct_messages(text, rt)


def test_all_prompt_builders_preserve_pre_refactor_message_bytes():
    expected = json.loads(MESSAGE_HASHES.read_text(encoding="utf-8"))
    actual = {
        key: {role: hashlib.sha256(message.encode("utf-8")).hexdigest()
              for role, message in zip(("system", "user"), messages)}
        for key, messages in _prompt_message_cases()
    }
    assert actual.keys() == expected.keys()
    for key in expected:
        assert actual[key] == expected[key], key


def test_grounded_prompt_edits_do_not_depend_on_sentence_anchors(monkeypatch):
    monkeypatch.setattr(prompts, "CE_CORE_DELIVERABLE_RULE", "CORE DELIVERABLE\n")
    monkeypatch.setattr(prompts, "CE_RUNTIME_BINDING_SYNTAX", "BINDING SYNTAX\n")
    rt = load_runtime("developer-sandbox")
    plain, user = prompts.ce_runtime_messages("task", rt)
    grounded, grounded_user = prompts.ce_grounded_messages("task", rt)
    assert "CORE DELIVERABLE\n" in plain
    assert "CORE DELIVERABLE " + prompts.CE_FALLBACK_RULE in grounded
    assert "BINDING SYNTAX\n" + prompts.CE_RUNTIME_BINDING_EXAMPLES in plain
    assert (
        "BINDING SYNTAX\n" + prompts.CE_SOFTWARE_DOC + prompts.CE_RUNTIME_BINDING_EXAMPLES
    ) in grounded
    assert grounded_user == user


def test_p2g_prompt_is_byte_identical_to_the_frozen_text():
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    assert len(frozen) == 9
    for key, want in frozen.items():
        rt_name, mode = key.split("|")
        rt = load_runtime(rt_name)
        if mode == "grounded":
            got = prompts.ce_grounded_messages("NL TEXT", rt)
        else:
            levels = mode == "levels=True"
            got = prompts.ce_runtime_messages("NL TEXT\nline two", rt, levels=levels,
                                              version="p2g")
            assert got == prompts.ce_runtime_messages("NL TEXT\nline two", rt, levels=levels)
        assert got == (want["system"], want["user"]), key


def test_p2g_plus_prompt_adds_rules_11_to_14_and_the_rule_9_amendment():
    rt = load_runtime("claude-code-cloud")
    old, _ = prompts.ce_runtime_messages("prose", rt, version="p2g")
    new, user = prompts.ce_runtime_messages("prose", rt, version="p2g+")
    for n in ("11. Facts the environment or the user decides",
              "12. 'tells' steps carry no effects",
              "13. The Goal names only the deliverable",
              "14. When the document names distinct actors"):
        assert n in new and n not in old
    assert "never give an approving or reviewing action to the role whose action it gates" \
        in new.lower()
    assert "declare one Tool via `reply` that adds the Goal atom" in new
    assert "(assuming `P`, ...)" in new and "via `reply`; requires" in new
    assert "  - `reply`: " in new and "  - `reply`: " not in old
    # rules 1-8 and rule 10 unchanged; rule 11 comes right after rule 10
    assert new.split("9. Thinking")[0] == old.split("9. Thinking")[0]
    assert new.index("10. The Goal") < new.index("11. Facts") < new.index("SkillC Controlled English (CE). One")
    assert user == prompts.ce_runtime_messages("prose", rt)[1]
    lv, _ = prompts.ce_runtime_messages("prose", rt, levels=True, version="p2g+")
    assert "10. Two goal levels" in lv and "14. When the document" in lv


def test_unknown_prompt_version_is_an_error():
    with pytest.raises(ValueError, match="unknown CE prompt version"):
        prompts.ce_runtime_messages("prose", load_runtime("developer-sandbox"), version="p3")


def test_other_prompt_builders_are_unchanged():
    rt = load_runtime("developer-sandbox")
    base, _ = prompts.ce_runtime_messages("x", rt, version="p2g")
    assert prompts.ce_index_messages("x", rt, "FACTS")[0] == base + "FACTS"
    assert "11. Facts the environment" not in prompts.ce_tpl_messages("x", rt, [])[0]


# --------------------------------------------------------------------------
# F-e: retries
# --------------------------------------------------------------------------

BAD = "```ce\nSkill `s`.\nGoal: `g`\nProtocol: none.\n```"          # missing '.'
GOOD = ("```ce\nSkill `s`.\nTool `t` (owner `agent`): via `bash`; adds `g`.\nGoal: `g`.\n"
        "Protocol:\n  - `agent` uses `t`.\n```")
RT = load_runtime("developer-sandbox")


def _fake(monkeypatch, replies):
    calls = []
    it = iter(replies)

    def fake(system, user, model, timeout):
        calls.append((system, user))
        return next(it)

    monkeypatch.setattr(providers, "anthropic_complete", fake)
    return calls


def test_compact_ce_retries_twice_by_default(monkeypatch):
    calls = _fake(monkeypatch, [BAD, BAD, GOOD])
    pack = llm.compact_ce("prose", provider="anthropic", runtime=RT)
    assert check(pack).achievable and len(calls) == 3
    assert all("line 2" in u and "expected '.'" in u for _, u in calls[1:])


def test_compact_ce_performs_at_most_two_retries(monkeypatch):
    calls = _fake(monkeypatch, [BAD] * 5)
    with pytest.raises(CEError):
        llm.compact_ce("prose", provider="anthropic", runtime=RT)
    assert len(calls) == 3
    calls = _fake(monkeypatch, [BAD] * 5)
    with pytest.raises(CEError):
        llm.compact_ce("prose", provider="anthropic", runtime=RT, retries=1)
    assert len(calls) == 2


def test_compact_ce_defaults_to_p2g_plus_and_can_select_p2g(monkeypatch):
    calls = _fake(monkeypatch, [GOOD, GOOD])
    llm.compact_ce("prose", provider="anthropic", runtime=RT)
    llm.compact_ce("prose", provider="anthropic", runtime=RT, version="p2g")
    assert calls[0][0] == prompts.ce_runtime_messages("prose", RT, version="p2g+")[0]
    assert calls[1][0] == prompts.ce_runtime_messages("prose", RT, version="p2g")[0]


def test_cli_check_via_runtime_takes_the_prompt_version(monkeypatch, tmp_path):
    from skillc.cli import main
    skill = tmp_path / "skill.md"
    skill.write_text("# Skill\nRun the build.\n", encoding="utf-8")
    calls = _fake(monkeypatch, [GOOD, GOOD])
    with contextlib.redirect_stdout(io.StringIO()):
        main(["check", str(skill), "--llm", "--llm-provider", "anthropic",
              "--runtime", "developer-sandbox"])
        main(["check", str(skill), "--llm", "--llm-provider", "anthropic",
              "--runtime", "developer-sandbox", "--ce-prompt", "p2g"])
    assert "11. Facts the environment" in calls[0][0]
    assert "11. Facts the environment" not in calls[1][0]


REFUTED = ("```ce\nSkill `s`.\nTool `t` (owner `agent`): via `windows_desktop`; adds `g`.\n"
           "Goal: `g`.\nProtocol:\n  - `agent` uses `t`.\n```")


def test_compact_ce_rounds_keeps_a_goal_weakening_repair_out(monkeypatch):
    weakened = REFUTED.replace("Goal: `g`.", "Goal: true.")
    calls = _fake(monkeypatch, [BAD, REFUTED, weakened])
    res = llm.compact_ce_rounds("SYS", "USER", RT, provider="anthropic")
    assert [r["kind"] for r in res["rounds"]] == ["first", "retry", "repair"]
    assert res["ok"] and res["verdict"].label == "IMPOSSIBLE"
    assert res["repair_rejected"] == ["the Goal changed"] and not res["repaired"]
    assert "judged your CE document IMPOSSIBLE" in calls[2][1]
    assert "`windows_desktop` is not a RUNTIME tool" in calls[2][1]


def test_compact_ce_rounds_accepts_a_guarded_repair(monkeypatch):
    _fake(monkeypatch, [REFUTED, GOOD])
    res = llm.compact_ce_rounds("SYS", "USER", RT, provider="anthropic")
    assert res["repaired"] and res["verdict"].label == "ACHIEVABLE"
    assert len(res["rounds"]) == 2


def test_compact_ce_rounds_gives_up_after_two_retries(monkeypatch):
    calls = _fake(monkeypatch, [BAD] * 5)
    res = llm.compact_ce_rounds("SYS", "USER", RT, provider="anthropic")
    assert not res["ok"] and len(calls) == 3 and "expected '.'" in res["error"]


# --------------------------------------------------------------------------
# F-d: gate compaction with the effective runtime
# --------------------------------------------------------------------------

@pytest.fixture
def finance(tmp_path: Path) -> Path:
    dst = tmp_path / "finance"
    shutil.copytree(FINANCE, dst, ignore=shutil.ignore_patterns(
        "src", ".skillc", ".azure", "*.log", "__pycache__"))
    (dst / "src" / "finance-agent").mkdir(parents=True)
    shutil.copy(FINANCE / "src" / "finance-agent" / "main.py",
                dst / "src" / "finance-agent" / "main.py")
    return dst


def test_project_text_reads_skills_and_coordinator_without_importing(tmp_path):
    from skillc.gate import coordinator_instructions, project_text
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "Writer.md").write_text("Write the report.\n", encoding="utf-8")
    (tmp_path / "skills" / "Approver.md").write_text("Approve it.\n", encoding="utf-8")
    main = tmp_path / "src" / "agent" / "main.py"
    main.parent.mkdir(parents=True)
    main.write_text('raise SystemExit("imported")\n'
                    'COORDINATOR_INSTRUCTIONS = """Call Writer, then Approver."""\n',
                    encoding="utf-8")
    (tmp_path / "azure.yaml").write_text("name: t\nservices: {}\n", encoding="utf-8")
    assert coordinator_instructions(tmp_path) == "Call Writer, then Approver."
    text = project_text(tmp_path)
    assert text == ("# Role: Coordinator\n\nCall Writer, then Approver.\n\n"
                    "# Role: Approver\n\nApprove it.\n\n"
                    "# Role: Writer\n\nWrite the report.\n")


def test_project_text_of_the_finance_example(finance):
    from skillc.gate import project_text
    text = project_text(finance)
    heads = [line for line in text.splitlines() if line.startswith("# Role: ")]
    assert heads[0] == "# Role: Coordinator" and len(heads) == 7
    assert "Six role agents are" in text


FINANCE_CE = textwrap.dedent("""\
    ```ce
    Skill `quarterly-finance-report`.
    Roles: `coordinator`, `tax_verifier`, `writer`.
    Tool `fetch` (owner `coordinator`): via `read`; adds `financials_fetched`.
    Tool `approve` (owner `tax_verifier`): via `reply`; requires `financials_fetched`; adds `approved`.
    Tool `deliver_report` (owner `writer`): via `write`; requires `approved`; adds `report_delivered`.
    Goal: `report_delivered`.
    Protocol:
      - `coordinator` uses `fetch`.
      - `coordinator` tells `tax_verifier` `ApprovalRequest`.
      - `tax_verifier` uses `approve`.
      - `tax_verifier` tells `writer` `Approved`.
      - `writer` uses `deliver_report`.
    ```
    """)


def _fake_azure(monkeypatch, replies):
    calls = []
    it = iter(replies)

    def fake(system, user, model, timeout, json_mode=True):
        calls.append({"system": system, "user": user, "model": model,
                      "json_mode": json_mode})
        return next(it)

    monkeypatch.setattr(providers, "azure_openai_complete", fake)
    return calls


def test_compact_project_hands_the_effective_runtime_to_the_prompt(monkeypatch, finance):
    from skillc.gate import MULTI_ROLE_NOTE, compact_project, project_text
    calls = _fake_azure(monkeypatch, [FINANCE_CE.replace("Goal: `report_delivered`.",
                                                         "Goal: `report_delivered`"),
                                      FINANCE_CE, FINANCE_CE])
    out = compact_project(finance, model="gpt-5.4", samples=2)
    system, user = calls[0]["system"], calls[0]["user"]
    tools = system.split("Its tools (the ONLY values allowed after 'via'):\n")[1] \
        .split("It does NOT provide:")[0]
    listed = sorted(line.split("`")[1] for line in tools.splitlines() if line.strip())
    assert listed == ["code_interpreter", "read", "reply", "web_fetch", "web_search", "write"]
    assert "11. Facts the environment" in system and calls[0]["model"] == "gpt-5.4"
    assert user == prompts.ce_runtime_messages(project_text(finance) + MULTI_ROLE_NOTE,
                                               load_runtime("foundry-hosted"))[1]
    assert "declare one Role per agent, the messages as `tells`" in user
    assert len(calls) == 3                                   # s0: first + retry; s1: first
    assert [c["ok"] for c in out] == [True, True] and [c["label"] for c in out] == \
        ["ACHIEVABLE", "ACHIEVABLE"]
    for k in (0, 1):
        assert (finance / "protocol" / f"compacted_s{k}.ce").read_text(encoding="utf-8") \
            .startswith("Skill `quarterly-finance-report`.")
        log = json.loads((finance / "protocol" / f"compacted_s{k}.json").read_text(
            encoding="utf-8"))
        assert log["effective_tools"] == ["code_interpreter", "read", "web_fetch",
                                          "web_search", "write"]
        assert log["system"] == system and log["version"] == "p2g+"
        assert all({"user", "reply", "usage"} <= set(r) for r in log["rounds"])
    assert [r["kind"] for r in json.loads((finance / "protocol" / "compacted_s0.json")
                                          .read_text(encoding="utf-8"))["rounds"]] == \
        ["first", "retry"]


def test_gate_compact_gates_the_samples_next_to_the_authored_pack(monkeypatch, finance):
    from skillc.gate import cmd_gate, gate
    _fake_azure(monkeypatch, [FINANCE_CE])
    ns = argparse.Namespace(dir=str(finance), declared="azure.yaml", env=None,
                            runtime="foundry-hosted", json=True, install_hook=False,
                            compact=True, model="gpt-5.4", samples=1,
                            llm_provider="azure-openai", ce_prompt="p2g+")
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = cmd_gate(ns)
    report = json.loads(out.getvalue())
    assert [p["name"] for p in report["packs"]] == ["compacted_s0.ce"]
    assert report["packs"][0]["verdict"] == "ACHIEVABLE"
    assert [p["name"] for p in report["authored_packs"]] == ["quarterly_finance_report.ce"]
    assert report["authored_packs"][0]["verdict"] == "ACHIEVABLE"
    assert report["compaction"][0]["label"] == "ACHIEVABLE"
    assert rc in (0, 3)
    # without --compact the compacted file is ignored and no model is called
    plain = gate(finance)
    assert [e.name for e in plain.packs] == ["quarterly_finance_report.ce"]
    assert "authored_packs" not in plain.to_dict()


# --------------------------------------------------------------------------
# F-h: repeated tool clauses merge (CE 1.4)
# --------------------------------------------------------------------------

def _tool(clauses: str) -> tuple[dict, dict]:
    r = parse_ce_detailed(f"Skill `s`.\nTool `t` (owner `agent`): {clauses}.\nGoal: `g`.\n"
                          "Protocol: none.\n")
    return r.pack["capabilities"]["t"], r.bindings.get("t", {})


def test_two_requires_clauses_parse_to_their_conjunction():
    cap, _ = _tool("requires `a`; adds `g`; requires `b` or `c`")
    assert cap["pre"] == {"and": ["a", {"or": ["b", "c"]}]}
    cap, _ = _tool("requires `a` and `b`; requires `c`; requires `d`")
    assert cap["pre"] == {"and": [{"and": ["a", "b"]}, "c", "d"]}
    assert _tool("requires `a`")[0]["pre"] == "a"


def test_repeated_list_clauses_union_in_first_seen_order():
    cap, _ = _tool("adds `x`, `y`; adds `y`, `z`; adds `w`, `x`")
    assert cap["add"] == ["x", "y", "z", "w"]
    cap, b = _tool("via `bash`; needs `shell`; removes `p`; needs `linux`, `shell`; "
                   "runs `a`; removes `q`, `p`; runs `b`")
    assert b["needs"] == ["shell", "linux"] and b["runs"] == ["a", "b"]
    assert cap["del"] == ["p", "q"]


def test_malformed_clause_errors_are_unchanged():
    with pytest.raises(CEError, match="'via' may appear once per tool") as err:
        _tool("via `bash`; via `read`")
    assert err.value.line == 2
    with pytest.raises(CEError, match="expected a tool clause") as err:
        _tool("requires `a`; grants `b`")
    assert err.value.line == 2
    with pytest.raises(CEError, match="expected a backticked identifier") as err:
        _tool("adds `a`; adds b")
    assert err.value.line == 2


def test_round_trip_is_unchanged_by_clause_merging():
    doc = textwrap.dedent("""\
        Skill `s`.
        Roles: `agent`.
        Tool `t` (owner `agent`): via `bash`; needs `shell`; requires `a`; adds `g`; needs `linux`; requires `b`; adds `h`, `g`.
        Initially true: `a`, `b`.
        Goal: `g` and `h`.
        Protocol:
          - `agent` uses `t`.
        """)
    r = parse_ce_detailed(doc)
    pack = r.pack
    assert pack["capabilities"]["t"]["pre"] == {"and": ["a", "b"]}
    assert pack["capabilities"]["t"]["add"] == ["g", "h"]
    text = render_ce(pack, r.bindings)
    tool_line = next(line for line in text.splitlines() if line.startswith("Tool"))
    assert [tool_line.count(w) for w in ("requires", "adds", "needs")] == [1, 1, 1]
    again = parse_ce_detailed(text)
    assert again.pack == canonical_pack(pack)
    assert parse_ce(render_ce(pack)) == canonical_pack(pack)
    assert again.bindings["t"]["needs"] == ["shell", "linux"]
    assert check(compile_ce(doc)).achievable

"""SkillC Controlled English: parser, renderer, round-trip and LLM wiring."""
import glob
import json
from pathlib import Path

import pytest

from skillc import check
from skillc.cli import main
from skillc.frontend import llm, prompts, providers
from skillc.frontend.ce import (CEError, canonical_pack, compile_ce,
                                extract_ce, parse_ce, parse_ce_detailed,
                                render_ce, render_formula)
from skillc.mutate import drop_invoked_capability, strip_goal_establisher
from skillc.pack import PackError, validate_pack

ROOT = Path(__file__).resolve().parents[1]


def _repo_packs():
    """Every valid pack stored in the repository (corpus, runs, examples)."""
    out = []
    for f in ("src/skillc/data/corpus.json", "src/skillc/data/corpus_extended.json"):
        for i, item in enumerate(json.loads((ROOT / f).read_text())):
            out.append((f"{f}#{i}", item.get("pack", item)))
    for pattern in ("runs/**/*.json", "examples/**/*.json", "tests/**/*.json"):
        for f in sorted(glob.glob(str(ROOT / pattern), recursive=True)):
            try:
                d = json.loads(Path(f).read_text())
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if isinstance(d, dict):
                p = d.get("pack", d)
                if isinstance(p, dict) and {"protocol", "capabilities"} <= set(p):
                    out.append((str(Path(f).relative_to(ROOT)), p))
    valid = []
    for name, p in out:
        try:
            validate_pack(p)
        except PackError:
            continue
        valid.append((name, p))
    return valid


REPO_PACKS = _repo_packs()


def _same_verdict(a, b):
    return (a.label, a.reason, a.frontier, a.context_refuted) == \
           (b.label, b.reason, b.frontier, b.context_refuted)


# --------------------------------------------------------------------------
# Sentence forms
# --------------------------------------------------------------------------

FULL = """\
Skill `book-flight`.
Roles: `agent`, `user`.
Tool `search_flights` (owner `agent`).
Tool `book_flight` (owner `agent`): requires `flight_selected` and not `blocked`; adds `booked`; removes `flight_selected`.
Tool `pay` (owner `agent`): sets `spent` to `spent` + `price`; picks `price` with `price` < 500.
Tool `ownerless`: adds `x`.
Initially true: `flight_selected`, `logged_in`.
Initially: `spent` == 0.
Initially: `price` >= -3.
Goal: `booked` and `spent` <= 500.
Protocol:
  - `agent` uses `search_flights`.
  - `user` chooses one of (observed):
    - branch `accept`:
      - `agent` uses `book_flight`.
      - `agent` tells `user` `done`.
    - branch `decline`: none.
  - loop `R`:
    - `agent` uses `pay`.
    - repeat `R`.
  - checkpoint: `booked` and `spent` <= 500.
Behaviour of `user`:
  - select one of:
    - branch `accept`:
      - receive `done` from `agent`.
    - branch `decline`: none.
Behaviour of `agent`:
  - use `search_flights`.
  - branch on `user` one of:
    - branch `accept`:
      - send `done` to `user`.
    - branch `decline`: none.
"""


def test_every_sentence_form_parses_to_the_intended_construct():
    p = parse_ce(FULL)
    assert p["name"] == "book-flight"
    assert p["roles"] == ["agent", "user"]
    assert p["capabilities"]["search_flights"] == {
        "owner": "agent", "pre": True, "add": [], "del": [],
        "assigns": {}, "nondet": {}}
    assert p["capabilities"]["book_flight"] == {
        "owner": "agent", "pre": {"and": ["flight_selected", {"not": "blocked"}]},
        "add": ["booked"], "del": ["flight_selected"], "assigns": {}, "nondet": {}}
    assert p["capabilities"]["pay"]["nondet"] == {"price": {"cmp": ["price", "<", 500]}}
    assert p["capabilities"]["pay"]["assigns"] == {"spent": {"+": ["spent", "price"]}}
    assert "owner" not in p["capabilities"]["ownerless"]
    assert p["init_true"] == ["flight_selected", "logged_in"]
    assert p["init_constraints"] == [{"cmp": ["spent", "==", 0]},
                                     {"cmp": ["price", ">=", -3]}]
    goal = {"and": ["booked", {"cmp": ["spent", "<=", 500]}]}
    assert p["goal"] == goal
    assert p["protocol"] == [
        {"act": {"cap": "search_flights", "by": "agent"}},
        {"choice": {"by": "user", "observed": True, "branches": {
            "accept": [{"act": {"cap": "book_flight", "by": "agent"}},
                       {"msg": {"from": "agent", "to": "user", "label": "done"}}],
            "decline": []}}},
        {"rec": {"name": "R", "body": [
            {"act": {"cap": "pay", "by": "agent"}}, {"continue": "R"}]}},
        {"goal": goal},
    ]
    assert p["skills"]["user"] == [{"select": {"branches": {
        "accept": [{"recv": {"from": "agent", "label": "done"}}], "decline": []}}}]
    assert p["skills"]["agent"] == [
        {"act": {"cap": "search_flights"}},
        {"branch": {"from": "user", "branches": {
            "accept": [{"send": {"to": "user", "label": "done"}}], "decline": []}}}]
    validate_pack(p)


def test_full_document_is_a_render_fixpoint():
    assert render_ce(parse_ce(FULL)) == FULL


def test_minimal_document_and_defaults():
    p = compile_ce("Skill `s`.\nGoal: true.\nProtocol: none.\n")
    assert p == {"name": "s", "roles": [], "capabilities": {}, "protocol": [],
                 "goal": True, "init_true": [], "init_constraints": []}


def test_none_is_accepted_wherever_a_list_may_be_empty():
    p = compile_ce("Skill `s`.\nRoles: none.\nInitially true: none.\nGoal: true.\n"
                   "Protocol: none.\n")
    assert p["roles"] == [] and p["init_true"] == [] and p["protocol"] == []


def test_statements_after_skill_may_come_in_any_order():
    a = parse_ce("Skill `s`.\nProtocol: none.\nGoal: `g`.\nTool `t`: adds `g`.\n"
                 "Roles: `agent`.\n")
    b = parse_ce("Skill `s`.\nRoles: `agent`.\nTool `t`: adds `g`.\nGoal: `g`.\n"
                 "Protocol: none.\n")
    assert a == b


def test_comments_blank_lines_and_provenance_are_kept_out_of_the_pack():
    text = ("# reviewed 2026-09-26\n\nSkill `s`.  # from SKILL.md L1\n"
            "Tool `t`: adds `g`.   # L12-L14\n\nGoal: `g`.\nProtocol:\n"
            "  - `a` uses `t`.  # L20\n")
    r = parse_ce_detailed(text)
    assert r.pack["capabilities"]["t"]["add"] == ["g"]
    assert r.comments == {3: "from SKILL.md L1", 4: "L12-L14", 8: "L20"}


def test_backticks_make_keywords_and_hash_safe_as_identifiers():
    p = parse_ce("Skill `s`.\nGoal: `and` or `true` or `#1 (done)`.\nProtocol: none.\n")
    assert p["goal"] == {"or": ["and", "true", "#1 (done)"]}


def test_choice_flags():
    for flags, expect in (("", {}), (" (external)", {"external": True}),
                          (" (observed, external)", {"external": True, "observed": True})):
        p = parse_ce("Skill `s`.\nGoal: true.\nProtocol:\n"
                     f"  - `a` chooses one of{flags}:\n    - branch `x`: none.\n")
        choice = p["protocol"][0]["choice"]
        assert {k: v for k, v in choice.items() if k in ("external", "observed")} == expect


# --------------------------------------------------------------------------
# Formulas and expressions
# --------------------------------------------------------------------------

FORMULAS = [
    True, False, "p",
    {"and": []}, {"or": []}, {"and": ["p"]}, {"or": ["p"]},
    {"and": ["p", "q", "r"]}, {"or": ["p", {"and": ["q", "r"]}]},
    {"and": ["p", {"and": ["q", "r"]}]}, {"or": [{"or": ["p", "q"]}, "r"]},
    {"not": {"and": ["p", "q"]}}, {"not": {"not": "p"}},
    {"not": {"cmp": ["x", "<", 3]}},
    {"and": [{"cmp": ["x", "<", 3]}, "p"]},
    {"cmp": [{"+": ["x", {"*": [2, "y"]}]}, ">=", {"-": ["z", -5]}]},
    {"cmp": [{"-": [{"-": ["a", "b"]}, "c"]}, "!=", -1]},
    {"cmp": [-7, "==", {"*": ["x", -2]}]},
    {"and": [{"not": "p"}, {"or": ["q", True]}, {"and": []}]},
]


@pytest.mark.parametrize("f", FORMULAS, ids=repr)
def test_formula_round_trip(f):
    text = f"Skill `s`.\nGoal: {render_formula(f)}.\nProtocol: none.\n"
    assert parse_ce(text)["goal"] == f


def test_precedence_not_binds_tighter_than_and_than_or():
    p = parse_ce("Skill `s`.\nGoal: not `a` and `b` or `c`.\nProtocol: none.\n")
    assert p["goal"] == {"or": [{"and": [{"not": "a"}, "b"]}, "c"]}


def test_parenthesised_arithmetic_is_a_comparison_not_a_formula_group():
    p = parse_ce("Skill `s`.\nGoal: (`a` + 1) < 3 and (`p` or `q`).\nProtocol: none.\n")
    assert p["goal"] == {"and": [{"cmp": [{"+": ["a", 1]}, "<", 3]},
                                 {"or": ["p", "q"]}]}


# --------------------------------------------------------------------------
# Errors name the line and column
# --------------------------------------------------------------------------

@pytest.mark.parametrize("text, line, fragment", [
    ("", None, "empty CE document"),
    ("Goal: `g`.\n", 1, "expected 'Skill'"),
    ("Skill `s`.\nProtocol: none.\n", None, "missing 'Goal:'"),
    ("Skill `s`.\nGoal: `g`.\n", None, "missing 'Protocol:'"),
    ("Skill `s`.\nGoal: `g.\nProtocol: none.\n", 2, "unterminated backtick"),
    ("Skill `s`.\nGoal: ``.\nProtocol: none.\n", 2, "empty identifier"),
    ("Skill `s`.\nGoal: `g`\nProtocol: none.\n", 2, "expected '.'"),
    ("Skill `s`.\nGoal: `g`.\nGoal: `h`.\nProtocol: none.\n", 3, "duplicate 'Goal:'"),
    ("Skill `s`.\nTool `t`.\nTool `t`.\nGoal: `g`.\nProtocol: none.\n", 3, "duplicate tool"),
    ("Skill `s`.\nTool `t`: adds `a`; adds `b`.\nGoal: `g`.\nProtocol: none.\n", 2, "once per tool"),
    ("Skill `s`.\nTool `t`: requires `a`; requires `b`.\nGoal: `g`.\nProtocol: none.\n", 2, "once per tool"),
    ("Skill `s`.\nTool `t`: grants `a`.\nGoal: `g`.\nProtocol: none.\n", 2, "a tool clause"),
    ("Skill `s`.\nGoal: `x` + `y` + 1 < 3.\nProtocol: none.\n", 2, "one arithmetic operator"),
    ("Skill `s`.\nGoal: `g`.\nProtocol:\n", 3, "needs indented"),
    ("Skill `s`.\nGoal: `g`.\nProtocol:\n   - `a` uses `t`.\n", 4, "multiple of 2"),
    ("Skill `s`.\nGoal: `g`.\nProtocol:\n    - `a` uses `t`.\n", 4, "over-indented"),
    ("Skill `s`.\nGoal: `g`.\nProtocol:\n\t- `a` uses `t`.\n", 4, "tabs"),
    ("Skill `s`.\nGoal: `g`.\nProtocol:\n  - `a` runs `t`.\n", 4, "'uses', 'tells' or 'chooses'"),
    ("Skill `s`.\nGoal: `g`.\nProtocol:\n  - `a` chooses one of:\n", 4, "at least one"),
    ("Skill `s`.\nGoal: `g`.\nProtocol:\n  - `a` chooses one of (sometimes):\n"
     "    - branch `x`: none.\n", 4, "a choice flag"),
    ("Skill `s`.\nGoal: `g`.\nProtocol:\n  - `a` chooses one of:\n"
     "    - branch `x`: none.\n    - branch `x`: none.\n", 6, "duplicate branch"),
    ("Skill `s`.\nGoal: `g`.\nProtocol: none.\n  - `a` uses `t`.\n", 4, "unexpected indented"),
    ("Skill `s`.\nGoal: `g`.\nProtocol: none.\nPlan: foo.\n", 4, "a statement"),
    ("Skill `s`.\nGoal: `g` $ `h`.\nProtocol: none.\n", 2, "unexpected character"),
])
def test_parse_errors_are_located(text, line, fragment):
    with pytest.raises(CEError) as err:
        parse_ce(text)
    assert fragment in str(err.value)
    assert err.value.line == line


def test_schema_gate_still_applies_after_parsing():
    # parses, but `repeat` is not in tail position: the decidable fragment
    # is tail-recursive, and the same validate_pack gate rejects it.
    text = ("Skill `s`.\nGoal: `g`.\nProtocol:\n  - loop `R`:\n"
            "    - repeat `R`.\n    - `a` uses `t`.\n")
    parse_ce(text)
    with pytest.raises(PackError, match="tail position"):
        compile_ce(text)


def test_unwritable_identifiers_are_refused_on_render():
    for bad in ("a`b", "a\nb", "a b", "a\x0cb"):
        pack = {"name": "s", "capabilities": {}, "protocol": [], "goal": bad}
        with pytest.raises(CEError, match="backtick or line break"):
            render_ce(pack)


def test_unknown_fields_are_refused_on_render_instead_of_dropped():
    with pytest.raises(CEError, match="top-level"):
        render_ce({"name": "s", "capabilities": {}, "protocol": [],
                   "goal": True, "provenance": "x"})
    with pytest.raises(CEError, match="cannot express"):
        render_ce({"name": "s", "capabilities": {"t": {"cost": 3}},
                   "protocol": [], "goal": True})


# --------------------------------------------------------------------------
# Round-trip over every pack in the repository, and their mutants
# --------------------------------------------------------------------------

def test_repository_has_packs_to_round_trip():
    assert len(REPO_PACKS) >= 150


@pytest.mark.parametrize("name, pack", REPO_PACKS, ids=[n for n, _ in REPO_PACKS])
def test_repository_pack_round_trips_with_identical_verdict(name, pack):
    text = render_ce(pack)
    back = compile_ce(text)
    assert back == canonical_pack(pack)
    assert render_ce(back) == text
    assert _same_verdict(check(pack), check(back))


def test_mutants_round_trip_with_identical_verdict():
    n = 0
    for _, pack in REPO_PACKS[:60]:
        for mutate in (drop_invoked_capability, strip_goal_establisher):
            got = mutate(pack)
            if got is None:
                continue
            mutant = got[0]
            try:
                validate_pack(mutant)
            except PackError:
                continue
            back = compile_ce(render_ce(mutant))
            assert back == canonical_pack(mutant)
            assert _same_verdict(check(mutant), check(back))
            n += 1
    assert n >= 50


# --------------------------------------------------------------------------
# Property-based round-trip over generated packs
# --------------------------------------------------------------------------

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import HealthCheck, given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

_BAD = set("`\n\r\x0b\x0c\x1c\x1d\x1e\x85  ")
names = st.one_of(
    st.sampled_from(["p", "q", "and", "or", "not", "true", "none", "Goal",
                     "a b", "#x", "x.y", "é", "- z", "(1)"]),
    st.text(min_size=1, max_size=8).filter(lambda s: not (_BAD & set(s))))
ints = st.integers(min_value=-10**6, max_value=10**6)
exprs = st.recursive(
    st.one_of(names, ints),
    lambda sub: st.one_of(
        st.tuples(st.sampled_from(["+", "-"]), sub, sub).map(
            lambda t: {t[0]: [t[1], t[2]]}),
        st.tuples(ints, sub).map(lambda t: {"*": [t[0], t[1]]}),
        st.tuples(sub, ints).map(lambda t: {"*": [t[0], t[1]]})),
    max_leaves=4)
formulas = st.recursive(
    st.one_of(st.just(True), st.just(False), names,
              st.tuples(exprs, st.sampled_from(["<", "<=", "==", ">", ">=", "!="]),
                        exprs).map(lambda t: {"cmp": list(t)})),
    lambda sub: st.one_of(
        st.lists(sub, max_size=3).map(lambda xs: {"and": xs}),
        st.lists(sub, max_size=3).map(lambda xs: {"or": xs}),
        sub.map(lambda x: {"not": x})),
    max_leaves=6)


def _steps(local):
    def leaf():
        if local:
            return st.one_of(
                names.map(lambda c: {"act": {"cap": c}}),
                st.tuples(names, names).map(lambda t: {"send": {"to": t[0], "label": t[1]}}),
                st.tuples(names, names).map(lambda t: {"recv": {"from": t[0], "label": t[1]}}),
                formulas.map(lambda f: {"goal": f}),
                names.map(lambda n: {"continue": n}))
        return st.one_of(
            st.tuples(names, names).map(lambda t: {"act": {"cap": t[0], "by": t[1]}}),
            st.tuples(names, names, names).map(
                lambda t: {"msg": {"from": t[0], "to": t[1], "label": t[2]}}),
            formulas.map(lambda f: {"goal": f}),
            names.map(lambda n: {"continue": n}),
            names.map(lambda r: {"spawn": {"role": r}}))

    def nest(sub):
        block = st.lists(sub, max_size=3)
        branches = st.dictionaries(names, block, min_size=1, max_size=3)
        rec = st.tuples(names, block).map(lambda t: {"rec": {"name": t[0], "body": t[1]}})
        if local:
            return st.one_of(
                rec, branches.map(lambda b: {"select": {"branches": b}}),
                st.tuples(names, branches).map(
                    lambda t: {"branch": {"from": t[0], "branches": t[1]}}))
        return st.one_of(rec, st.tuples(names, st.booleans(), st.booleans(), branches).map(
            lambda t: {"choice": {"by": t[0], "branches": t[3],
                                  **({"external": True} if t[1] else {}),
                                  **({"observed": True} if t[2] else {})}}))

    return st.lists(st.recursive(leaf(), nest, max_leaves=6), max_size=4)


caps = st.dictionaries(names, st.fixed_dictionaries(
    {"pre": formulas, "add": st.lists(names, max_size=3),
     "del": st.lists(names, max_size=2),
     "assigns": st.dictionaries(names, exprs, max_size=2),
     "nondet": st.dictionaries(names, formulas, max_size=2)},
    optional={"owner": names}), max_size=4)
packs = st.fixed_dictionaries(
    {"name": names, "capabilities": caps, "protocol": _steps(False), "goal": formulas},
    optional={"roles": st.lists(names, max_size=3, unique=True),
              "init_true": st.lists(names, max_size=3),
              "init_constraints": st.lists(formulas, max_size=2),
              "skills": st.dictionaries(names, _steps(True), max_size=2)})


@settings(max_examples=400, deadline=None,
          suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])
@given(packs)
def test_generated_packs_round_trip_exactly(pack):
    text = render_ce(pack)
    back = parse_ce(text)
    assert back == canonical_pack(pack)
    assert render_ce(back) == text


@settings(max_examples=150, deadline=None,
          suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large,
                                 HealthCheck.filter_too_much])
@given(packs)
def test_generated_valid_packs_keep_their_verdict(pack):
    try:
        validate_pack(pack)
    except PackError:
        hypothesis.assume(False)
    back = compile_ce(render_ce(pack))
    assert _same_verdict(check(pack), check(back))


# --------------------------------------------------------------------------
# Extracting CE from model output
# --------------------------------------------------------------------------

DOC = "Skill `s`.\nGoal: true.\nProtocol: none.\n"


@pytest.mark.parametrize("wrapped", [
    DOC,
    "Here it is:\n```ce\n" + DOC + "```\nDone.",
    "```json\n{}\n```\n```ce\n" + DOC + "```",
    "```\n" + DOC + "```",
    "Some preface text.\n" + DOC,
])
def test_extract_ce(wrapped):
    assert parse_ce(extract_ce(wrapped)) == parse_ce(DOC)


def test_extract_ce_without_a_document():
    with pytest.raises(CEError, match="no CE document"):
        extract_ce("I cannot do that.")


# --------------------------------------------------------------------------
# The LLM path (provider mocked: no network)
# --------------------------------------------------------------------------

def test_prompt_example_compiles_and_reports_the_undeclared_tool():
    example = prompts.CE_DOC.split("Example:\n", 1)[1].split("\n(`send_email`", 1)[0]
    pack = compile_ce("\n".join(l[2:] for l in example.splitlines()) + "\n")
    v = check(pack)
    assert v.reason == "MISSING_CAPABILITY" and v.frontier == ("send_email",)


def test_ce_prompt_keeps_every_rule_of_the_json_prompt():
    for n in range(1, 9):
        assert f"\n{n}. " in prompts.SYSTEM and f"\n{n}. " in prompts.CE_SYSTEM
    system, user = prompts.ce_messages("prose", ["read files"])
    assert "DECLARE it as a Tool" in system and "read files" in system
    assert user.startswith("Natural-language skill:\n```\nprose\n```")


def test_compact_ce_parses_and_retries_with_the_located_error(monkeypatch):
    calls = []
    replies = iter([
        "```ce\nSkill `s`.\nGoal: `g`\nProtocol: none.\n```",       # missing '.'
        "```ce\nSkill `s`.\nTool `t` (owner `agent`): adds `g`.\nGoal: `g`.\n"
        "Protocol:\n  - `agent` uses `t`.\n```",
    ])

    def fake(system, user, model, timeout):
        calls.append(user)
        return next(replies)

    monkeypatch.setattr(providers, "anthropic_complete", fake)
    pack, text = llm.compact_ce("prose", provider="anthropic", return_text=True)
    assert check(pack).achievable
    assert len(calls) == 2
    assert "line 2" in calls[1] and "expected '.'" in calls[1]
    assert text.startswith("Skill `s`.")


def test_compact_ce_gives_up_after_the_retry_budget(monkeypatch):
    monkeypatch.setattr(providers, "anthropic_complete",
                        lambda *a: "```ce\nSkill `s`.\n```")
    with pytest.raises(CEError, match="missing 'Goal:'"):
        llm.compact_ce("prose", provider="anthropic", retries=1)


def test_compact_ce_azure_requests_text_not_json(monkeypatch):
    seen = {}

    def fake(system, user, model, timeout, json_mode=True):
        seen["json_mode"] = json_mode
        return DOC

    monkeypatch.setattr(providers, "azure_openai_complete", fake)
    llm.compact_ce("prose", provider="azure-openai")
    assert seen["json_mode"] is False


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def test_cli_ce_files_compile_check_and_convert(tmp_path, capsys):
    src = tmp_path / "skill.ce"
    src.write_text("Skill `s`.\nRoles: none.\nTool `t` (owner `agent`): adds `g`.\nGoal: `g` and `h`.\n"
                   "Protocol:\n  - `agent` uses `t`.\n")
    assert main(["check", str(src)]) == 1           # `h` has no establisher
    capsys.readouterr()
    assert main(["ce", str(src)]) == 0
    pack = json.loads(capsys.readouterr().out)
    assert pack["goal"] == {"and": ["g", "h"]}
    as_json = tmp_path / "pack.json"
    as_json.write_text(json.dumps(pack))
    assert main(["ce", str(as_json)]) == 0
    assert capsys.readouterr().out == src.read_text()


def test_cli_reports_ce_errors_as_usage_errors(tmp_path, capsys):
    bad = tmp_path / "bad.ce"
    bad.write_text("Skill `s`.\nGoal: `g`\n")
    assert main(["check", str(bad)]) == 2
    assert "line 2" in capsys.readouterr().err


# --------------------------------------------------------------------------
# Runtime-manifest binding
# --------------------------------------------------------------------------

from skillc.frontend.runtime import bind_runtime, load_runtime  # noqa: E402

RT = load_runtime("developer-sandbox")
BOUND = """\
Skill `ship`.
Roles: `agent`.
Tool `build` (owner `agent`): via `bash`; adds `built`.
Tool `launch_gui` (owner `agent`): via `windows_desktop`; requires `built`; adds `launched`.
Tool `deploy` (owner `agent`): via `bash`; needs `cloud_account`; requires `built`; adds `deployed`.
Tool `fetch` (owner `agent`): via `web_fetch`; needs `public_internet`; adds `docs_read`.
Goal: `built`.
Protocol:
  - `agent` uses `build`.
"""


def _bound(text):
    r = parse_ce_detailed(text)
    return bind_runtime(r.pack, r.bindings, RT)


def test_via_and_needs_round_trip_through_render():
    r = parse_ce_detailed(BOUND)
    assert r.bindings["deploy"]["via"] == "bash"
    assert r.bindings["deploy"]["needs"] == ["cloud_account"]
    assert render_ce(r.pack, r.bindings) == BOUND


def test_manifest_tool_is_granted_and_goal_is_achievable():
    assert check(_bound(BOUND).pack).achievable


def test_tool_outside_the_manifest_is_withdrawn():
    b = _bound(BOUND.replace("Goal: `built`.", "Goal: `launched`.")
               + "  - `agent` uses `launch_gui`.\n")
    assert b.withdrawn == {"launch_gui": "windows_desktop"}
    v = check(b.pack)
    assert v.reason == "MISSING_CAPABILITY" and v.frontier == ("launch_gui",)


def test_needed_resource_the_runtime_lacks_blocks_the_step():
    b = _bound(BOUND.replace("Goal: `built`.", "Goal: `deployed`.")
               + "  - `agent` uses `deploy`.\n")
    assert b.blocked == {"deploy": ["cloud_account"]}
    v = check(b.pack)
    assert v.reason == "BLOCKED_GUARD" and "cloud_account" in v.frontier[0]


def test_needed_resource_the_runtime_grants_holds_initially():
    b = _bound(BOUND.replace("Goal: `built`.", "Goal: `docs_read`.")
               + "  - `agent` uses `fetch`.\n")
    assert "needs:public_internet" in b.pack["init_true"]
    assert check(b.pack).achievable


def test_tool_without_via_is_a_located_error():
    with pytest.raises(CEError, match="no 'via' clause"):
        _bound(BOUND.replace("Tool `build` (owner `agent`): via `bash`; adds",
                             "Tool `build` (owner `agent`): adds"))


def test_runtime_prompt_replaces_rule_1_and_lists_the_manifest():
    system, _ = prompts.ce_runtime_messages("prose", RT)
    assert system.count("\n1. ") == 1 and "bind it with 'via'" in system
    assert "9. Thinking is not a Tool" in system and "10. The Goal" in system
    for tool in RT.tools:
        assert f"`{tool}`" in system
    assert "Never invent" not in system.split("2. ")[0]


def test_compact_ce_with_runtime_binds_and_retries(monkeypatch):
    replies = iter([
        "```ce\nSkill `s`.\nTool `t` (owner `agent`): adds `g`.\nGoal: `g`.\n"
        "Protocol:\n  - `agent` uses `t`.\n```",                       # no via
        "```ce\nSkill `s`.\nTool `t` (owner `agent`): via `bash`; adds `g`.\n"
        "Goal: `g`.\nProtocol:\n  - `agent` uses `t`.\n```",
    ])
    calls = []
    monkeypatch.setattr(providers, "anthropic_complete",
                        lambda s, u, m, t: calls.append(u) or next(replies))
    pack = llm.compact_ce("prose", provider="anthropic", runtime=RT)
    assert check(pack).achievable and "no 'via' clause" in calls[1]


# --------------------------------------------------------------------------
# Repair guard (P2g)
# --------------------------------------------------------------------------

from skillc.frontend.runtime import repair_violations  # noqa: E402

REFUTED = BOUND.replace("Goal: `built`.", "Goal: `deployed`.") + "  - `agent` uses `deploy`.\n"


def test_repair_that_makes_follow_up_skippable_is_accepted():
    fixed = REFUTED.replace("Goal: `deployed`.", "Goal: `deployed`.").replace(
        "  - `agent` uses `deploy`.\n",
        "  - `agent` chooses one of (observed):\n"
        "    - branch `now`:\n      - `agent` uses `deploy`.\n"
        "    - branch `later`: none.\n")
    assert repair_violations(parse_ce_detailed(REFUTED), parse_ce_detailed(fixed)) == []


def test_repair_that_removes_the_tool_is_accepted():
    fixed = "\n".join(line for line in REFUTED.splitlines()
                      if "deploy`" not in line or line.startswith("Goal")) + "\n"
    assert repair_violations(parse_ce_detailed(REFUTED), parse_ce_detailed(fixed)) == []


def test_repair_that_weakens_the_goal_is_rejected():
    fixed = REFUTED.replace("Goal: `deployed`.", "Goal: `built`.")
    assert repair_violations(parse_ce_detailed(REFUTED),
                             parse_ce_detailed(fixed)) == ["the Goal changed"]


def test_repair_that_drops_a_need_but_keeps_the_tool_is_rejected():
    fixed = REFUTED.replace("needs `cloud_account`; ", "")
    assert repair_violations(parse_ce_detailed(REFUTED), parse_ce_detailed(fixed)) == [
        "Tool `deploy` kept but no longer needs `cloud_account`"]


# --------------------------------------------------------------------------
# Two goal levels (P3)
# --------------------------------------------------------------------------

from skillc.frontend.runtime import check_levels  # noqa: E402

LEVELS = """\
Skill `ship`.
Roles: `agent`.
Tool `build` (owner `agent`): via `bash`; adds `built`.
Tool `deploy` (owner `agent`): via `bash`; needs `cloud_account`; requires `built`; adds `deployed`.
Goal: `built`.
Live goal: `deployed`.
Protocol:
  - `agent` uses `build`.
  - `agent` chooses one of (observed):
    - branch `deploy`:
      - `agent` uses `deploy`.
    - branch `skip`: none.
"""


def test_live_goal_round_trips():
    r = parse_ce_detailed(LEVELS)
    assert r.live_goal == "deployed" or r.live_goal == {"atom": "deployed"} or r.live_goal
    assert render_ce(r.pack, r.bindings, r.live_goal) == LEVELS
    assert parse_ce_detailed(BOUND).live_goal is None


def test_live_goal_must_follow_goal_and_is_unique():
    with pytest.raises(CEError, match="after 'Goal:'"):
        parse_ce_detailed(LEVELS.replace("Goal: `built`.\nLive goal: `deployed`.",
                                         "Live goal: `deployed`.\nGoal: `built`."))
    with pytest.raises(CEError, match="duplicate 'Live goal:'"):
        parse_ce_detailed(LEVELS.replace("Live goal: `deployed`.",
                                         "Live goal: `deployed`.\nLive goal: `built`."))


def test_core_goal_holds_while_live_goal_is_blocked():
    r = parse_ce_detailed(LEVELS)
    b = bind_runtime(r.pack, r.bindings, RT)
    v = check_levels(b.pack, r.live_goal)
    assert v["core"].achievable
    assert v["live"].label == "IMPOSSIBLE"


def test_live_goal_on_the_mandatory_path_blocks_the_core_goal_too():
    text = LEVELS.split("  - `agent` chooses")[0] + "  - `agent` uses `deploy`.\n"
    r = parse_ce_detailed(text)
    b = bind_runtime(r.pack, r.bindings, RT)
    assert check_levels(b.pack, r.live_goal)["core"].label == "IMPOSSIBLE"


def test_without_live_goal_levels_is_the_plain_check():
    r = parse_ce_detailed(BOUND)
    b = bind_runtime(r.pack, r.bindings, RT)
    v = check_levels(b.pack, None)
    assert v["live"] is None and v["core"].label == check(b.pack).label


def test_repair_that_moves_the_goal_into_the_live_goal_is_rejected():
    before = parse_ce_detailed(LEVELS.replace("Goal: `built`.", "Goal: `deployed`.")
                               .replace("Live goal: `deployed`.\n", ""))
    after = parse_ce_detailed(LEVELS)
    assert repair_violations(before, after) == ["the Goal changed", "the Live goal changed"]


def test_levels_prompt_replaces_rule_10_only():
    plain, _ = prompts.ce_runtime_messages("prose", RT)
    lv, _ = prompts.ce_runtime_messages("prose", RT, levels=True)
    assert "10. The Goal is" in plain and "10. The Goal is" not in lv
    assert "10. Two goal levels" in lv and "Live goal: F." in lv
    assert plain.split("10. ")[0] == lv.split("10. ")[0]


def test_binder_prunes_the_agents_unrunnable_branch():
    r = parse_ce_detailed(LEVELS)
    b = bind_runtime(r.pack, r.bindings, RT)
    assert b.pruned == ["agent:deploy"]
    assert check(b.pack).achievable
    unpruned = bind_runtime(r.pack, r.bindings, RT, prune=False)
    assert unpruned.pruned == [] and check(unpruned.pack).reason == "NON_CONFORMANT"


def test_binder_keeps_external_choices_and_all_dead_choices():
    ext = LEVELS.replace("chooses one of (observed)", "chooses one of (external)")
    r = parse_ce_detailed(ext)
    b = bind_runtime(r.pack, r.bindings, RT)
    assert b.pruned == [] and not check(b.pack).achievable
    dead = LEVELS.replace("    - branch `skip`: none.\n",
                          "    - branch `again`:\n      - `agent` uses `deploy`.\n")
    r = parse_ce_detailed(dead)
    b = bind_runtime(r.pack, r.bindings, RT)
    assert b.pruned == [] and not check(b.pack).achievable


# --------------------------------------------------------------------------
# Tool-policy library (TPL)
# --------------------------------------------------------------------------

from skillc.frontend.toolpolicy import (coverage, load_library,  # noqa: E402
                                        match, resolve_program)

LIB = load_library()


def test_library_entries_are_well_formed_and_have_provenance():
    kinds = {"resource", "runtime_tool", "program", "effect"}
    for e in LIB.entries:
        (kind, _), = e["requires"].items()
        assert kind in kinds and e["evidence"] and e["provenance"], e["id"]


def test_match_raises_obligations_with_lines():
    text = "Setup\nexport OPENAI_API_KEY=...\nThen dispatch a fresh subagent per task.\n"
    obs = match(text, LIB)
    assert [(o.kind, o.value, o.line) for o in obs] == [
        ("resource", "llm_api_key", 2), ("runtime_tool", "agent_spawn", 3)]


def test_mcp_tool_names_become_runtime_tool_obligations():
    obs = match("allowed-tools: mcp__sentry__search_issues", LIB)
    assert [(o.kind, o.value) for o in obs] == [("runtime_tool", "sentry_mcp")]


TPL = """\
Skill `t`.
Roles: `agent`.
Tool `write_code` (owner `agent`): via `write`; effect `local`; adds `code`.
Tool `call_model` (owner `agent`): via `bash`; needs `llm_api_key`; runs `python`; requires `code`; adds `scored`.
Tool `submit` (owner `agent`): via `bash`; effect `writes_external`; requires `scored`; adds `sent`.
Goal: `scored`.
Protocol:
  - `agent` uses `write_code`.
  - `agent` uses `call_model`.
"""


def test_runs_and_effect_round_trip():
    r = parse_ce_detailed(TPL)
    assert r.bindings["call_model"]["runs"] == ["python"]
    assert r.bindings["submit"]["effect"] == "writes_external"
    assert render_ce(r.pack, r.bindings) == TPL


def test_unknown_effect_is_a_located_error():
    with pytest.raises(CEError, match="unknown effect"):
        parse_ce_detailed(TPL.replace("`writes_external`", "`sends`"))


def test_coverage_reports_unmet_obligations():
    r = parse_ce_detailed(TPL)
    obs = match("OPENAI_API_KEY\ngit push origin main\ndispatch a fresh subagent", LIB)
    msgs = coverage(r, obs)
    assert len(msgs) == 1 and "via `agent_spawn`" in msgs[0]


def test_forbidden_effect_blocks_the_step():
    r = parse_ce_detailed(TPL.replace("Goal: `scored`.", "Goal: `code`.")
                          .replace("  - `agent` uses `call_model`.\n",
                                   "  - `agent` uses `submit`.\n"))
    b = bind_runtime(r.pack, r.bindings, RT, library=LIB)
    assert "policy:writes_external" in b.blocked["submit"]
    assert check(b.pack).reason in ("BLOCKED_GUARD", "NON_CONFORMANT")
    # without the library the effect is ignored (P1/P2 reproducibility)
    plain = bind_runtime(r.pack, r.bindings, RT)
    assert "submit" not in plain.blocked


def test_unavailable_program_is_withdrawn():
    text = TPL.replace("runs `python`", "runs `cli_exercise_helper`")
    r = parse_ce_detailed(text)
    b = bind_runtime(r.pack, r.bindings, RT, library=LIB)
    assert b.withdrawn["call_model"].startswith("program:cli_exercise_helper")
    assert check(b.pack).reason == "MISSING_CAPABILITY"


def test_program_resolution():
    assert resolve_program("cli_exercise_helper", RT, LIB)[0] == "unavailable"
    assert resolve_program("winget", RT, LIB)[0] == "unavailable"      # needs windows
    assert resolve_program("terraform", RT, LIB)[0] == "installable"


SPAWN = """\
Skill `s`.
Roles: `agent`.
Tool `work` (owner `agent`): via `bash`; adds `done`.
Goal: `done`.
Protocol:
  - spawn `helper`.
  - `agent` uses `work`.
"""


def test_spawn_without_agent_spawn_is_missing_capability():
    r = parse_ce_detailed(SPAWN)
    assert check(bind_runtime(r.pack, r.bindings, RT).pack).reason == "DYNAMIC_TOPOLOGY"
    b = bind_runtime(r.pack, r.bindings, RT, library=LIB)
    assert check(b.pack).reason == "MISSING_CAPABILITY"


def test_optional_spawn_is_pruned():
    text = SPAWN.replace("  - spawn `helper`.\n",
                         "  - `agent` chooses one of (observed):\n"
                         "    - branch `delegate`:\n      - spawn `helper`.\n"
                         "    - branch `self`: none.\n")
    r = parse_ce_detailed(text)
    b = bind_runtime(r.pack, r.bindings, RT, library=LIB)
    assert b.pruned == ["agent:delegate"] and check(b.pack).achievable


def test_repair_guard_freezes_runs_and_effect():
    before = parse_ce_detailed(TPL)
    after = parse_ce_detailed(TPL.replace("; runs `python`", "")
                              .replace("effect `writes_external`", "effect `local`"))
    msgs = repair_violations(before, after)
    assert any("no longer runs" in m for m in msgs)
    assert any("effect changed" in m for m in msgs)


def test_tpl_prompt_lists_obligations_and_forbidden_effects():
    obs = match("export OPENAI_API_KEY=x", LIB)
    system, user = prompts.ce_tpl_messages("export OPENAI_API_KEY=x", RT, obs)
    assert "effect `E`" in system and "`writes_external`, `publishes`" in system
    assert "needs `llm_api_key`" in user and user.endswith("CE document:")


from skillc.frontend.toolpolicy import core_lines, veto  # noqa: E402

VETO_SKILL = """---
name: t
description: Submit results with submit-expo-feedback and query the Azure MCP.
---
# T
Intro mentions nothing else.
## Details
Optionally set OPENAI_API_KEY.
"""


def test_core_lines_cover_frontmatter_and_intro_only():
    assert core_lines(VETO_SKILL) == {1, 2, 3, 4, 5, 6}


def test_core_veto_ignores_requirements_outside_the_core_statement():
    core = {o.value for o in veto(VETO_SKILL, RT, LIB, "core")}
    anywhere = {o.value for o in veto(VETO_SKILL, RT, LIB, "any")}
    assert core == {"writes_external", "azure_mcp"}
    assert anywhere == core | {"llm_api_key"}


def test_veto_never_fires_on_what_the_runtime_provides():
    assert veto("---\nname: x\ndescription: run tests with bash\n---\n", RT, LIB) == []

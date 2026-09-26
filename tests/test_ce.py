"""SkillC Controlled English: parser, renderer, round-trip and LLM wiring."""
import glob
import json
from pathlib import Path

import pytest

from skillc import check
from skillc.cli import main
from skillc.frontend import llm
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
    example = llm.CE_DOC.split("Example:\n", 1)[1].split("\n(`send_email`", 1)[0]
    pack = compile_ce("\n".join(l[2:] for l in example.splitlines()) + "\n")
    v = check(pack)
    assert v.reason == "MISSING_CAPABILITY" and v.frontier == ("send_email",)


def test_ce_prompt_keeps_every_rule_of_the_json_prompt():
    for n in range(1, 9):
        assert f"\n{n}. " in llm.SYSTEM and f"\n{n}. " in llm.CE_SYSTEM
    system, user = llm.ce_messages("prose", ["read files"])
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

    monkeypatch.setattr(llm, "_compact_anthropic", fake)
    pack, text = llm.compact_ce("prose", provider="anthropic", return_text=True)
    assert check(pack).achievable
    assert len(calls) == 2
    assert "line 2" in calls[1] and "expected '.'" in calls[1]
    assert text.startswith("Skill `s`.")


def test_compact_ce_gives_up_after_the_retry_budget(monkeypatch):
    monkeypatch.setattr(llm, "_compact_anthropic",
                        lambda *a: "```ce\nSkill `s`.\n```")
    with pytest.raises(CEError, match="missing 'Goal:'"):
        llm.compact_ce("prose", provider="anthropic", retries=1)


def test_compact_ce_azure_requests_text_not_json(monkeypatch):
    seen = {}

    def fake(system, user, model, timeout, json_mode=True):
        seen["json_mode"] = json_mode
        return DOC

    monkeypatch.setattr(llm, "_compact_azure_openai", fake)
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

"""Token economics: what a check costs against what an unchecked run wastes.

These tests pin the *structure* of the argument -- the trusted core spends no
tokens, waste grows quadratically in turns, refutation pays for itself before
the first prevented invocation -- rather than the particular default
constants, which are an openly parameterized model.
"""
import json
import math

import pytest

from skillc.tokens import (CACHE_READ_DISCOUNT, FAILURE_PROFILES, PRICES,
                           CorpusEconomics, Cost, RuntimeModel, check_cost,
                           compaction_cost, economics, estimate_tokens,
                           usage_to_cost)


class TestEstimateTokens:
    def test_empty_text_costs_nothing(self):
        assert estimate_tokens("") == 0

    def test_monotone_in_length(self):
        assert estimate_tokens("a" * 100) < estimate_tokens("a" * 1000)

    def test_ratio_is_overridable(self):
        text = "x" * 380
        assert estimate_tokens(text, chars_per_token=3.8) == 100
        assert estimate_tokens(text, chars_per_token=1.0) == 380


class TestCost:
    def test_totals_and_addition(self):
        a = Cost(input_tokens=10, output_tokens=5, measured=True)
        b = Cost(input_tokens=1, cached_input_tokens=100, measured=True)
        assert (a + b).total_tokens == 116
        assert (a + b).measured

    def test_one_estimated_component_makes_the_sum_estimated(self):
        measured = Cost(input_tokens=10, measured=True)
        modelled = Cost(input_tokens=10, measured=False)
        assert not (measured + modelled).measured

    def test_cached_input_is_discounted_not_free(self):
        price = PRICES["mid"]
        fresh = Cost(input_tokens=1_000_000).usd(price)
        cached = Cost(cached_input_tokens=1_000_000).usd(price)
        assert cached == pytest.approx(fresh * CACHE_READ_DISCOUNT)
        assert cached > 0

    def test_usage_block_becomes_a_measured_cost(self):
        c = usage_to_cost({"input_tokens": 1200, "output_tokens": 400,
                           "cache_read_input_tokens": 900})
        assert c.measured and c.total_tokens == 2500


class TestVerificationCost:
    """The trusted core is free; only the optional front-end is not."""

    def test_deterministic_front_end_and_checker_cost_zero_tokens(self):
        c = check_cost("a skill with plenty of prose " * 200)
        assert c.total_tokens == 0
        assert c.usd("frontier") == 0.0

    def test_llm_compaction_is_linear_in_skill_length(self):
        short = compaction_cost("skill. " * 100)
        long = compaction_cost("skill. " * 1000)
        overhead = compaction_cost("")
        # the skill-dependent part scales with the skill, ~10x here
        assert ((long.input_tokens - overhead.input_tokens)
                / (short.input_tokens - overhead.input_tokens)) == pytest.approx(10, rel=0.05)

    def test_a_repair_round_roughly_doubles_compaction(self):
        one = compaction_cost("skill text " * 200, repair_rounds=0)
        two = compaction_cost("skill text " * 200, repair_rounds=1)
        assert 1.8 < two.total_tokens / one.total_tokens < 2.6

    def test_negative_repair_rounds_rejected(self):
        with pytest.raises(ValueError):
            compaction_cost("x", repair_rounds=-1)


class TestRuntimeModel:
    """A turn re-reads everything before it, so waste is quadratic in turns."""

    def test_zero_turns_costs_nothing(self):
        assert RuntimeModel().run_cost(0).total_tokens == 0

    def test_doubling_turns_more_than_doubles_the_cost(self):
        m = RuntimeModel(skill_tokens=1500)
        assert m.run_cost(20).total_tokens > 2 * m.run_cost(10).total_tokens

    def test_growth_is_quadratic_not_linear(self):
        m = RuntimeModel(skill_tokens=0, system_tokens=0,
                         output_tokens_per_turn=0, turn_growth_tokens=100)
        # sum_{i<T} i*g  =  g*T*(T-1)/2
        assert m.run_cost(10).total_tokens == 100 * 10 * 9 // 2
        assert m.run_cost(100).total_tokens == 100 * 100 * 99 // 2

    def test_a_second_agent_doubles_the_bill(self):
        m = RuntimeModel(skill_tokens=1000)
        assert (m.run_cost(10, agents=2).total_tokens
                == 2 * m.run_cost(10, agents=1).total_tokens)

    def test_caching_moves_tokens_but_never_removes_them(self):
        plain = RuntimeModel(skill_tokens=1000).run_cost(15)
        cached = RuntimeModel(skill_tokens=1000,
                              cache_hit_rate=0.9).run_cost(15)
        assert cached.total_tokens == plain.total_tokens   # same tokens read
        assert cached.usd("mid") < plain.usd("mid")        # cheaper, not free
        assert cached.usd("mid") > 0

    def test_rejects_impossible_shapes(self):
        with pytest.raises(ValueError):
            RuntimeModel().run_cost(-1)
        with pytest.raises(ValueError):
            RuntimeModel().run_cost(5, agents=0)


class TestFailureProfiles:
    def test_every_refutation_reason_that_wastes_tokens_has_a_profile(self):
        for reason in ("MISSING_CAPABILITY", "BLOCKED_GUARD", "GOAL_UNSAT",
                       "NON_PROJECTABLE", "NON_CONFORMANT"):
            assert reason in FAILURE_PROFILES

    def test_dynamic_topology_has_no_profile(self):
        # UNKNOWN is an abstention, not a refutation: nothing was prevented,
        # so there is no avoided waste to claim.
        assert "DYNAMIC_TOPOLOGY" not in FAILURE_PROFILES

    def test_bands_are_ordered_low_typical_high(self):
        for prof in FAILURE_PROFILES.values():
            lo, ty, hi = prof.turns
            assert lo <= ty <= hi

    def test_retry_forever_is_the_most_expensive_failure(self):
        # a guard no run can satisfy gives the agent no way to learn it should
        # stop, so it runs to the harness cap
        worst = max(FAILURE_PROFILES.values(), key=lambda p: p.turns[2])
        assert worst.reason == "BLOCKED_GUARD"

    def test_deadlocked_handoffs_bill_both_agents(self):
        assert FAILURE_PROFILES["NON_PROJECTABLE"].agents == 2


class TestEconomics:
    SKILL = "Book a flight under $500 and email the confirmation. " * 60

    def test_deterministic_check_pays_for_itself_immediately(self):
        e = economics(self.SKILL, "MISSING_CAPABILITY", llm=False)
        assert e.verification.total_tokens == 0
        assert e.breakeven_runs == 0.0

    def test_llm_check_pays_for_itself_within_one_prevented_run(self):
        for reason in FAILURE_PROFILES:
            e = economics(self.SKILL, reason, llm=True)
            assert 0 < e.breakeven_runs < 1, reason

    def test_llm_check_is_a_small_fraction_of_one_successful_run(self):
        e = economics(self.SKILL, "GOAL_UNSAT", llm=True)
        assert 0 < e.verification_share_of_one_run < 0.25

    def test_unknown_reason_is_refused_rather_than_guessed(self):
        with pytest.raises(KeyError):
            economics(self.SKILL, "DYNAMIC_TOPOLOGY")

    def test_waste_band_is_ordered(self):
        e = economics(self.SKILL, "BLOCKED_GUARD", llm=True)
        assert (e.waste_low.total_tokens <= e.waste_typical.total_tokens
                <= e.waste_high.total_tokens)

    def test_serializes_to_json(self):
        e = economics(self.SKILL, "NON_PROJECTABLE", llm=True)
        json.dumps(e.to_dict())          # must not raise on Infinity


class TestCorpusRollup:
    def test_empty_corpus_reports_unbounded_leverage(self):
        t = CorpusEconomics().totals()
        assert t["skills_refuted"] == 0
        assert t["leverage_typical"] is None      # JSON-safe, not Infinity

    def test_totals_are_json_serializable(self):
        c = CorpusEconomics()
        c.rows.append(economics("some skill prose " * 50,
                                "MISSING_CAPABILITY", llm=True))
        d = c.to_dict()
        json.dumps(d)
        assert d["totals"]["skills_refuted"] == 1
        assert d["totals"]["leverage_typical"] > 1

    def test_leverage_is_the_ratio_of_waste_to_check(self):
        c = CorpusEconomics()
        e = economics("prose " * 200, "BLOCKED_GUARD", llm=True)
        c.rows.append(e)
        t = c.totals()
        assert t["leverage_typical"] == pytest.approx(
            e.waste_typical.total_tokens / e.verification.total_tokens, rel=0.01)


class TestExactCounting:
    def test_exact_counting_refuses_to_silently_estimate(self, monkeypatch):
        from skillc import tokens
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            tokens.count_tokens_exact("hello")


class TestCli:
    def test_cost_over_the_builtin_corpus(self, capsys):
        from skillc.cli import main
        assert main(["cost", "--corpus", "--json"]) == 0
        out = json.loads(capsys.readouterr().out)
        # the corpus's seven structural refutations all avoid waste
        assert out["totals"]["skills_refuted"] == 7
        assert out["totals"]["waste_avoided_tokens"]["typical"] > 0
        # the deterministic path spends nothing to get them
        assert out["totals"]["verification_tokens"] == 0

    def test_cost_prices_the_llm_front_end_without_calling_it(self, capsys,
                                                              monkeypatch):
        from skillc.cli import main
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert main(["cost", "--corpus", "--price-llm", "--json"]) == 0
        out = json.loads(capsys.readouterr().out)
        assert out["totals"]["verification_tokens"] > 0
        assert out["totals"]["leverage_typical"] > 1
        assert not any(s["verification"]["measured"] for s in out["skills"])

    def test_cost_needs_a_path_or_corpus(self, capsys):
        from skillc.cli import main
        assert main(["cost"]) == 2

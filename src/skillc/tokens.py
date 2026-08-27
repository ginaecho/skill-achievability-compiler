"""Token economics of pre-execution refutation.

The compiler's practical claim is that refuting a skill *before* it runs is
cheaper than discovering the same failure at run time.  The paper states that
claim qualitatively ("pre-execution refutation can reduce wasted
computation"); this module makes it quantitative, and makes the arithmetic
inspectable rather than rhetorical.

There are exactly two places tokens are spent, and only one of them is
optional:

===========================  ============================  =================
stage                        tokens                        when
===========================  ============================  =================
deterministic front-end      **0**                         per skill
LLM compaction (``--llm``)   system prompt + skill + pack  per skill version
schema gate + checker        **0** (z3, milliseconds)      per check
Coq metatheory               **0**                         once, ever
run time (the thing avoided) grows *quadratically* in      per invocation
                             the number of turns
===========================  ============================  =================

Two structural asymmetries drive every number below.

1. **Once versus every time.**  Compaction is paid once per skill *version*,
   at authoring or publication time.  Waste is paid on every invocation of a
   doomed skill, by every user who invokes it.  A skill that ships broken
   pays its waste again and again; the check that refutes it is paid once.

2. **Linear versus quadratic.**  Compaction reads the skill once, so its cost
   is linear in the skill's length.  An agent run re-sends its whole context
   on every turn, so a run of ``T`` turns bills roughly
   ``T*(S+K) + g*T*(T-1)/2`` input tokens (Section `RuntimeModel`).  The
   quadratic term is why a doomed run is expensive precisely in the failure
   modes that make an agent flail longest -- a guard that is never satisfiable
   (retry-forever) or a handoff that deadlocks.

Caching changes the *price* of the wasted tokens, not their *number*: a
cached prefix is still read, just billed at a discount.  Both are reported.

Honesty about what is measured
------------------------------
* Compaction usage is **measured** when a live API call reports it
  (``frontend.llm`` returns the API's own ``usage`` block) and **estimated**
  otherwise; every result says which via ``Cost.measured``.
* Runtime waste is always an **estimate**: it is the cost of a run that, by
  construction, we are arguing should never happen.  It is produced by an
  explicit, parameterized model with published defaults (`RuntimeModel`,
  `FAILURE_PROFILES`), reported as a low/typical/high band rather than a
  point value, and every parameter is overridable.  Treat it as an
  order-of-magnitude argument, not a measurement.
* Token counts from `estimate_tokens` are a character-ratio heuristic, not a
  tokenizer.  `count_tokens_exact` upgrades them to real counts when an API
  key is available.
"""
from __future__ import annotations

import json
import math
import os
import urllib.request
from dataclasses import dataclass, field, replace
from typing import Optional

# --------------------------------------------------------------------------
# Token estimation
# --------------------------------------------------------------------------

# Characters per token for English markdown / prose under the Claude
# tokenizer.  Documentation and prose sit near 3.7-4.0; JSON and code are
# denser (more punctuation), which makes this ratio *conservative* for the
# pack (it under-counts the pack's tokens) and accurate for the skill text.
# Every function that uses it accepts an override.
CHARS_PER_TOKEN = 3.8

# Cache reads are billed at a fraction of the base input price.  Used only to
# convert token counts into dollars; it never changes a token count.
CACHE_READ_DISCOUNT = 0.1

TOKEN_COUNT_URL = "https://api.anthropic.com/v1/messages/count_tokens"


def estimate_tokens(text: str, chars_per_token: float = CHARS_PER_TOKEN) -> int:
    """Heuristic token count for a string.

    A character-ratio estimate, not a tokenizer: use `count_tokens_exact` when
    an API key is available and the exact number matters.  Reported numbers
    that rest on this should be quoted to two significant figures.
    """
    if not text:
        return 0
    return max(1, math.ceil(len(text) / chars_per_token))


def count_tokens_exact(text: str, model: str = "claude-sonnet-5",
                       system: str = "", timeout: int = 60) -> int:
    """Exact token count via the Anthropic ``count_tokens`` endpoint.

    Requires ``ANTHROPIC_API_KEY``.  Raises `RuntimeError` without one, so a
    caller can fall back to `estimate_tokens` deliberately rather than
    silently reporting an estimate as a measurement.
    """
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set; exact token counting "
                           "needs the API -- use estimate_tokens() instead")
    payload: dict = {"model": model,
                     "messages": [{"role": "user", "content": text}]}
    if system:
        payload["system"] = system
    req = urllib.request.Request(
        TOKEN_COUNT_URL, data=json.dumps(payload).encode(),
        headers={"content-type": "application/json", "x-api-key": key,
                 "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return int(json.load(r)["input_tokens"])


# --------------------------------------------------------------------------
# Prices  (USD per million tokens)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Price:
    """Per-million-token prices for one model tier."""
    name: str
    input_per_mtok: float
    output_per_mtok: float

    def cost(self, input_tokens: int, output_tokens: int,
             cached_input_tokens: int = 0) -> float:
        """USD for a token bundle; `cached_input_tokens` are billed at the
        cache-read discount and must already be excluded from
        `input_tokens`."""
        return ((input_tokens * self.input_per_mtok
                 + cached_input_tokens * self.input_per_mtok
                 * CACHE_READ_DISCOUNT
                 + output_tokens * self.output_per_mtok) / 1_000_000)


# Indicative list prices, held in one place so a stale number is a one-line
# fix rather than a scattered correction.  Nothing in the analysis depends on
# their exact values: the conclusions are ratios of token counts, and the
# same price applies to both sides of every comparison.
PRICES = {
    "frontier": Price("frontier tier", input_per_mtok=5.0, output_per_mtok=25.0),
    "mid": Price("mid tier", input_per_mtok=3.0, output_per_mtok=15.0),
    "small": Price("small tier", input_per_mtok=1.0, output_per_mtok=5.0),
}
DEFAULT_PRICE = "mid"


# --------------------------------------------------------------------------
# Cost records
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Cost:
    """A bundle of tokens, and whether it was measured or modelled."""
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0     # billed at CACHE_READ_DISCOUNT
    measured: bool = False           # True only for real API-reported usage
    label: str = ""

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.cached_input_tokens

    def usd(self, price: Price | str = DEFAULT_PRICE) -> float:
        p = PRICES[price] if isinstance(price, str) else price
        return p.cost(self.input_tokens, self.output_tokens,
                      self.cached_input_tokens)

    def __add__(self, other: "Cost") -> "Cost":
        return Cost(self.input_tokens + other.input_tokens,
                    self.output_tokens + other.output_tokens,
                    self.cached_input_tokens + other.cached_input_tokens,
                    self.measured and other.measured,
                    self.label or other.label)

    def to_dict(self, price: Price | str = DEFAULT_PRICE) -> dict:
        return {"label": self.label, "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "cached_input_tokens": self.cached_input_tokens,
                "total_tokens": self.total_tokens,
                "measured": self.measured,
                "usd": round(self.usd(price), 6)}


ZERO = Cost(label="deterministic (no model in the loop)")


def usage_to_cost(usage: dict, label: str = "compaction") -> Cost:
    """Turn an Anthropic API ``usage`` block into a measured `Cost`."""
    return Cost(input_tokens=int(usage.get("input_tokens", 0)),
                output_tokens=int(usage.get("output_tokens", 0)),
                cached_input_tokens=int(usage.get("cache_read_input_tokens", 0))
                + int(usage.get("cache_creation_input_tokens", 0)),
                measured=True, label=label)


# --------------------------------------------------------------------------
# The verification side: what a check costs
# --------------------------------------------------------------------------

def compaction_cost(skill_text: str, *, system_text: Optional[str] = None,
                    pack: Optional[dict] = None, repair_rounds: int = 0,
                    chars_per_token: float = CHARS_PER_TOKEN) -> Cost:
    """Estimated token cost of compacting one skill with the LLM front-end.

    Input is the system prompt (schema + compaction rules) plus the skill
    text; output is the emitted pack.  A repair round re-sends the skill, the
    previous pack and the counterexample, and emits a fresh pack -- so each
    round costs roughly one compaction plus the previous pack again.

    With ``repair_rounds=0`` this is the cost of the path the paper describes
    for a pack that checks on the first try.
    """
    if repair_rounds < 0:
        raise ValueError("repair_rounds must be >= 0")
    from .frontend.llm import SYSTEM
    sys_tokens = estimate_tokens(system_text if system_text is not None
                                 else SYSTEM, chars_per_token)
    skill_tokens = estimate_tokens(skill_text, chars_per_token)
    pack_tokens = (estimate_tokens(json.dumps(pack), chars_per_token)
                   if pack is not None else _TYPICAL_PACK_TOKENS)

    inp = sys_tokens + skill_tokens
    out = pack_tokens
    for _ in range(repair_rounds):
        # the repair prompt carries the skill, the refuted pack and the
        # counterexample back to the compactor, which emits a new pack
        inp += sys_tokens + skill_tokens + pack_tokens + _COUNTEREXAMPLE_TOKENS
        out += pack_tokens
    return Cost(input_tokens=inp, output_tokens=out,
                label=f"LLM compaction ({repair_rounds} repair round"
                      f"{'' if repair_rounds == 1 else 's'})")


# A pack for a real consumer skill under the prompt's own size discipline
# ("at most ~12 capabilities and ~25 protocol steps"): ~2.5 KB of JSON.
_TYPICAL_PACK_TOKENS = 650
# reason + detail + frontier of a NON_PROJECTABLE counterexample
_COUNTEREXAMPLE_TOKENS = 120


def check_cost(skill_text: str = "", *, llm: bool = False,
               repair_rounds: int = 0, **kw) -> Cost:
    """Token cost of deciding one skill.

    The trusted core -- schema gate, projection, conformance, z3
    reachability -- costs **zero tokens** under either front-end: no model is
    in the decision path, by design.  So the whole cost of a check is the
    front-end's, and the deterministic front-end's is also zero.
    """
    if not llm:
        return replace(ZERO, label="deterministic front-end + checker")
    return compaction_cost(skill_text, repair_rounds=repair_rounds, **kw)


# --------------------------------------------------------------------------
# The runtime side: what an unrefuted impossible skill wastes
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class RuntimeModel:
    """Token accounting for one agent run, and the defaults' rationale.

    An agent turn re-sends the whole conversation so far.  Writing ``S`` for
    the fixed harness prompt (system prompt + tool definitions), ``K`` for the
    skill loaded into context, ``g`` for the mean tokens appended per turn
    (the assistant's message plus the tool result it triggers) and ``o`` for
    the assistant's own output per turn, a run of ``T`` turns reads

        input  =  T*(S + K)  +  g * T*(T-1)/2
        output =  T*o

    The quadratic term is the whole point: the marginal cost of turn ``T`` is
    ``S + K + (T-1)*g``, so a run that flails for 40 turns costs far more than
    four runs that flail for 10.  Static refutation removes the entire run,
    quadratic term included.

    Defaults are deliberately **conservative** -- they understate the waste --
    so the conclusion does not depend on a generous parameterization:

    * ``system_tokens=2500``: a modest harness prompt plus a handful of tool
      schemas.  Real agent harnesses are frequently several times this.
    * ``turn_growth_tokens=700``: a short assistant message plus a small tool
      result.  A single file read or web fetch exceeds it easily.
    * ``output_tokens_per_turn=250``: a couple of paragraphs plus a tool call.
    """
    system_tokens: int = 2_500
    skill_tokens: int = 0
    turn_growth_tokens: int = 700
    output_tokens_per_turn: int = 250
    # Fraction of the re-read prefix served from cache.  Affects dollars
    # only: a cached token is still a token that was read.
    cache_hit_rate: float = 0.0

    def run_cost(self, turns: int, agents: int = 1) -> Cost:
        """Tokens consumed by `agents` agents running `turns` turns each."""
        if turns < 0 or agents < 1:
            raise ValueError("turns must be >= 0 and agents >= 1")
        fixed = self.system_tokens + self.skill_tokens
        raw_input = turns * fixed + self.turn_growth_tokens * turns * (turns - 1) // 2
        output = turns * self.output_tokens_per_turn
        raw_input *= agents
        output *= agents
        cached = int(raw_input * self.cache_hit_rate)
        return Cost(input_tokens=raw_input - cached, output_tokens=output,
                    cached_input_tokens=cached,
                    label=f"{agents} agent(s) x {turns} turns")


@dataclass(frozen=True)
class FailureProfile:
    """How long an agent flails before a given structural failure stops it.

    ``turns`` is a (low, typical, high) band, not a point estimate.  The bands
    below are engineering judgement about agent-harness behaviour, stated
    openly so a reader can substitute their own; the qualitative ordering
    (a never-satisfiable guard costs more than a missing tool) is the robust
    part, and every conclusion in `Economics` is reported across the band.
    """
    reason: str
    turns: tuple           # (low, typical, high)
    agents: int = 1
    rationale: str = ""
    silent: bool = False   # the run can end believing it succeeded


FAILURE_PROFILES = {
    "MISSING_CAPABILITY": FailureProfile(
        "MISSING_CAPABILITY", (3, 8, 14),
        rationale="the agent calls a tool that is not there, retries once or "
                  "twice, then improvises a workaround -- the improvisation, "
                  "not the error, is what costs turns"),
    "BLOCKED_GUARD": FailureProfile(
        "BLOCKED_GUARD", (12, 25, 50),
        rationale="a precondition no run can satisfy is the retry-forever "
                  "cause: the agent has no way to learn the guard is "
                  "unsatisfiable, so it runs until the harness turn cap"),
    "GOAL_UNSAT": FailureProfile(
        "GOAL_UNSAT", (8, 18, 30), silent=True,
        rationale="the plan executes to the end and only then fails to "
                  "satisfy the goal -- and when a conjunct has no establisher "
                  "the run can terminate *believing* it succeeded, moving the "
                  "cost off the token bill and onto whoever trusted it"),
    "NON_CONFORMANT": FailureProfile(
        "NON_CONFORMANT", (6, 15, 30), agents=2,
        rationale="a role that does not refine its contract diverges from the "
                  "protocol mid-session; both sides burn context before the "
                  "mismatch surfaces"),
    "NON_PROJECTABLE": FailureProfile(
        "NON_PROJECTABLE", (6, 15, 30), agents=2,
        rationale="an unobserved choice deadlocks the handoff: both agents "
                  "hold full context and wait, and both are billed for it "
                  "until a timeout fires"),
}


# --------------------------------------------------------------------------
# Putting the two sides together
# --------------------------------------------------------------------------

@dataclass
class Economics:
    """The comparison the paper's broader-impact claim needs.

    `verification` is what deciding the skill cost; `waste_low/typical/high`
    is what one unrefuted invocation of the same skill would consume.
    """
    skill: str
    reason: str
    verification: Cost
    waste_low: Cost
    waste_typical: Cost
    waste_high: Cost
    successful_run: Cost
    profile: FailureProfile
    price: str = DEFAULT_PRICE

    @property
    def breakeven_runs(self) -> float:
        """Invocations of the doomed skill before the check has paid for
        itself.  ``0.0`` when verification costs no tokens at all, which is
        the deterministic front-end's ordinary case."""
        w = self.waste_typical.total_tokens
        if self.verification.total_tokens == 0:
            return 0.0
        if w == 0:
            return math.inf
        return self.verification.total_tokens / w

    @property
    def verification_share_of_one_run(self) -> float:
        """Verification tokens as a fraction of a *successful* run of the same
        skill -- the honest denominator for "what does checking cost me?",
        since a healthy skill is the case where the check buys nothing."""
        r = self.successful_run.total_tokens
        return 0.0 if r == 0 else self.verification.total_tokens / r

    def to_dict(self) -> dict:
        return {
            "skill": self.skill,
            "reason": self.reason,
            "verification": self.verification.to_dict(self.price),
            "waste_per_run": {
                "low": self.waste_low.to_dict(self.price),
                "typical": self.waste_typical.to_dict(self.price),
                "high": self.waste_high.to_dict(self.price),
            },
            "successful_run": self.successful_run.to_dict(self.price),
            # null, not Infinity: unbounded leverage must survive JSON
            "breakeven_runs": (None if math.isinf(self.breakeven_runs)
                               else round(self.breakeven_runs, 4)),
            "verification_share_of_one_run":
                round(self.verification_share_of_one_run, 6),
            "failure_profile": {
                "reason": self.profile.reason,
                "turns": list(self.profile.turns),
                "agents": self.profile.agents,
                "silent": self.profile.silent,
                "rationale": self.profile.rationale,
            },
        }


# Turns for a run of a skill that actually works: it does its job and stops.
SUCCESSFUL_RUN_TURNS = 10


def economics(skill_text: str, reason: str, *, name: str = "skill",
              llm: bool = False, repair_rounds: int = 0,
              model: Optional[RuntimeModel] = None,
              verification: Optional[Cost] = None,
              price: str = DEFAULT_PRICE,
              successful_run_turns: int = SUCCESSFUL_RUN_TURNS) -> Economics:
    """Compare the cost of refuting a skill with the cost of running it.

    `reason` is the checker's refutation reason, which selects the failure
    profile.  `verification` overrides the modelled compaction cost with a
    measured one (from a live `frontend.llm` call).
    """
    prof = FAILURE_PROFILES.get(reason)
    if prof is None:
        raise KeyError(f"no failure profile for reason {reason!r}; known: "
                       f"{sorted(FAILURE_PROFILES)}")
    rt = model or RuntimeModel()
    rt = replace(rt, skill_tokens=rt.skill_tokens
                 or estimate_tokens(skill_text))
    ver = verification if verification is not None else check_cost(
        skill_text, llm=llm, repair_rounds=repair_rounds)
    lo, ty, hi = prof.turns
    return Economics(
        skill=name, reason=reason, verification=ver,
        waste_low=rt.run_cost(lo, prof.agents),
        waste_typical=rt.run_cost(ty, prof.agents),
        waste_high=rt.run_cost(hi, prof.agents),
        successful_run=rt.run_cost(successful_run_turns),
        profile=prof, price=price)


# --------------------------------------------------------------------------
# Corpus-level roll-up
# --------------------------------------------------------------------------

@dataclass
class CorpusEconomics:
    """Aggregate over a set of checked skills."""
    rows: list = field(default_factory=list)
    price: str = DEFAULT_PRICE

    @property
    def refuted(self) -> list:
        return list(self.rows)

    def totals(self) -> dict:
        ver = sum((r.verification for r in self.rows), Cost())
        lo = sum((r.waste_low for r in self.rows), Cost())
        ty = sum((r.waste_typical for r in self.rows), Cost())
        hi = sum((r.waste_high for r in self.rows), Cost())
        return {
            "skills_refuted": len(self.rows),
            "verification_tokens": ver.total_tokens,
            "verification_usd": round(ver.usd(self.price), 4),
            "waste_avoided_tokens": {"low": lo.total_tokens,
                                     "typical": ty.total_tokens,
                                     "high": hi.total_tokens},
            "waste_avoided_usd": {
                "low": round(lo.usd(self.price), 4),
                "typical": round(ty.usd(self.price), 4),
                "high": round(hi.usd(self.price), 4)},
            # None means "unbounded": the check spent no tokens at all,
            # so there is no ratio to report.  JSON has no Infinity.
            "leverage_typical": (None if ver.total_tokens == 0
                                 else round(ty.total_tokens
                                            / ver.total_tokens, 1)),
        }

    def to_dict(self) -> dict:
        return {"price_tier": self.price,
                "totals": self.totals(),
                "skills": [r.to_dict() for r in self.rows]}

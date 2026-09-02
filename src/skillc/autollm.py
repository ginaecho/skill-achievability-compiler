"""Automatic escalation from the deterministic front end to LLM compaction.

The deterministic front end (`frontend.markdown`) is free and inspectable but
it can only read what it can pattern-match: a completion sentence, a Tools
line, invocation verbs, executable fences.  When a document carries meaning
in a form it cannot read, its pack is WEAK -- typically the trivial "one act
per invoked tool" reading or no acts at all -- and an achievability verdict on
that pack says little.  `needs_llm` detects that situation from the document
and the deterministic result, without spending a token; `auto_check` then
escalates to the (untrusted, schema-gated) LLM compactor only when needed and
reports exactly what the escalation cost.
"""
from __future__ import annotations
import re, time
from dataclasses import dataclass, field, asdict

GOAL_LANG_RE = re.compile(r"\b(finished|done|complete[d]?|success(?:ful)?)\s+when\b|\bgoal\b|\bobjective\b|\bdeliverable", re.I)
WORKFLOW_RE = re.compile(r"^#{1,4}\s*(workflow|steps|procedure|process|instructions|how to|usage)\b|^\s*(?:step\s*)?\d+[.)]\s+\S", re.I | re.M)
CONDITION_RE = re.compile(r"\b(if|unless|only when|before|after|requires?|must|never|do not|don't|ask the user|confirm)\b", re.I)
IRREVERSIBLE_RE = re.compile(r"\b(delete|send|publish|deploy|pay|purchase|charge|drop|overwrite|push|release|submit|email)\b", re.I)


@dataclass
class Escalation:
    needed: bool
    reasons: list = field(default_factory=list)
    signals: dict = field(default_factory=dict)


def needs_llm(text: str, result, verdict=None) -> Escalation:
    """Decide whether the verdict standing on the deterministic pack is worth
    what it claims, and so whether to spend model tokens.

    The asymmetry that makes this cheap: the weak reading (one act per invoked
    tool) UNDER-approximates the document, so a REFUTATION on it -- the skill
    names a tool the runtime does not have -- is sound whatever the document
    means, and needs no model.  A CERTIFICATION on it is not: it says only
    that the named tools exist.  So escalation fires when the pack is weak,
    the verdict is achievable, and the document visibly carries meaning the
    deterministic reader did not capture.
    """
    body = text
    goal_lang = bool(GOAL_LANG_RE.search(body))
    workflow = bool(WORKFLOW_RE.search(body))
    conditions = len(CONDITION_RE.findall(body))
    irreversible = len(IRREVERSIBLE_RE.findall(body))
    semantic = bool(getattr(result, "notes", None))       # the semantic path was taken
    invocations = len(getattr(result, "invocations", []) or [])
    pack = result.pack
    weak_goal = pack.get("goal") is True or (isinstance(pack.get("goal"), dict) and
                                             all(isinstance(x, str) and x.startswith("used_")
                                                 for x in pack["goal"].get("and", [])))
    choices = any("choice" in s for s in pack.get("protocol", []))
    achievable = True if verdict is None else bool(getattr(verdict, "achievable", True))
    reasons = []
    if semantic or not achievable or not weak_goal:
        # a semantic pack, or a sound refutation, or a real goal: nothing to buy
        return Escalation(needed=False, reasons=[],
                          signals={"goal_language": goal_lang, "workflow": workflow, "conditions": conditions,
                                   "irreversible_verbs": irreversible, "semantic_path": semantic,
                                   "invocations": invocations, "weak_goal": weak_goal, "choices": choices,
                                   "achievable": achievable})
    if goal_lang:
        reasons.append("the document says when it is finished, but the reader could not turn that into a goal")
    if workflow and invocations == 0:
        reasons.append("a workflow section with no extractable tool invocation")
    if conditions >= 6 and not choices:
        reasons.append(f"{conditions} conditional phrases and no guard or choice in the pack")
    if irreversible >= 3:
        reasons.append(f"{irreversible} irreversible-sounding verbs under a used_<tool> goal")
    return Escalation(needed=bool(reasons), reasons=reasons,
                      signals={"goal_language": goal_lang, "workflow": workflow, "conditions": conditions,
                               "irreversible_verbs": irreversible, "semantic_path": semantic,
                               "invocations": invocations, "weak_goal": weak_goal, "choices": choices,
                               "achievable": achievable})


def auto_check(path: str, profile_name: str = "claude-ai", llm_model: str = "haiku",
               runtime: str | None = None, force_llm: bool = False) -> dict:
    """Deterministic check; escalate to LLM compaction when needed; return
    both verdicts and the measured cost of the escalation."""
    from .profiles import load_profile
    from .frontend.markdown import compile_file
    from .frontend import llm as llmmod
    from .checker import check
    profile = load_profile(profile_name)
    text = open(path, encoding="utf-8").read()
    t0 = time.perf_counter()
    res = compile_file(path, profile)
    det = check(res.pack)
    det_ms = (time.perf_counter() - t0) * 1000
    esc = needs_llm(text, res, det)
    out = {"path": path, "profile": profile_name, "deterministic": {"achievable": det.achievable, "reason": det.reason, "ms": round(det_ms, 1)},
           "escalation": asdict(esc), "llm": None}
    if esc.needed or force_llm:
        abilities = llmmod.RUNTIME_ABILITY_PROFILES.get(runtime or ("developer" if profile.shell else "none"))
        t1 = time.perf_counter()
        try:
            pack = llmmod.compact(text, model=llm_model, runtime_abilities=abilities, provider="claude-cli")
            v = check(pack)
            out["llm"] = {"achievable": v.achievable, "reason": v.reason, "detail": (v.detail or "")[:200],
                          "model": llm_model, "usage": dict(llmmod.LAST_USAGE),
                          "tokens": sum(int(llmmod.LAST_USAGE.get(k, 0)) for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")),
                          "seconds": round(time.perf_counter() - t1, 1), "pack": pack}
        except Exception as e:                                       # noqa: BLE001
            out["llm"] = {"error": str(e)[:300], "usage": dict(llmmod.LAST_USAGE),
                          "seconds": round(time.perf_counter() - t1, 1)}
    return out

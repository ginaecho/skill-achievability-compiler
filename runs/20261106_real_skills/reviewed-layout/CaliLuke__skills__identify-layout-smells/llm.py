"""Optional multi-provider LLM compaction front-end (untrusted, env-gated).

Produces a *semantic* pack from natural language via Anthropic or Azure
OpenAI, capturing guards, budgets, roles, and branching that the deterministic
front-end does not attempt.  The output is untrusted by design: every provider
response passes through the same deterministic schema gate (validate_pack) and
then the trusted checker.

Never used implicitly: only via `skillc compile --llm` or a direct call to
compact(). Credentials remain in provider-specific environment variables.
Prompt texts live in `frontend.prompts`, HTTP clients in `frontend.providers`.
"""
from __future__ import annotations

import json
from dataclasses import replace

from ..checker import Verdict, check
from ..pack import PackError, validate_pack
from ..tokens import Cost, measured_cost
from . import providers
from .ce import CEError, ParseResult, compile_ce, extract_ce, parse_ce_detailed
from .prompts import (CE_REPAIR_PROMPT, CE_RETRY_PROMPT, REPAIR_PROMPT,
                      RUNTIME_ABILITIES_NOTE, SYSTEM, ce_messages, ce_runtime_messages,
                      explain_refutation, vocabulary_note)
from .providers import metered
from .runtime import bind_runtime, repair_violations

# The default CE prompt of `compact_ce` and `check --llm --via-ce` with a runtime
# (compaction v2).  `prompts.ce_runtime_messages` itself still defaults to "p2g".
DEFAULT_CE_VERSION = "p2g+"


def compact(nl: str, model: str | None = None, timeout: int = 600,
            runtime_abilities: list[str] | None = None,
            provider: str | None = None,
            vocabulary: dict | None = None) -> dict:
    """Compact natural language into a provider-neutral validated pack.

    runtime_abilities: general abilities the target runtime grants (the
    Gamma_0 the prose presupposes without naming tools); without it the
    compactor under-grants and refutes deployed skills that assume a phone,
    a browser, or a user to talk to.

    provider: ``anthropic`` or ``azure-openai``. If omitted,
    SKILLC_LLM_PROVIDER is used, then ``anthropic``.

    vocabulary: an environment manifest whose tool and state names the pack
    should reuse, so environment contracts can be aligned with the goal.
    """
    selected = providers.resolve_provider(provider)
    system = SYSTEM
    if runtime_abilities:
        system += RUNTIME_ABILITIES_NOTE.format(
            abilities="; ".join(runtime_abilities))
    if vocabulary:
        system += vocabulary_note(vocabulary)
    user = f"Natural-language skill:\n```\n{nl}\n```\nJSON pack:"
    text = providers.complete(selected, system, user, model, timeout)
    try:
        pack = providers.extract_json_object(text)
        validate_pack(pack)      # deterministic gate on every provider output
        return pack
    except (PackError, ValueError) as error:
        # One repair round: the gate's message, then the same gate again.
        retry = (f"{user}\n{text}\n\nThat JSON failed validation: {error}\n"
                 "Return the corrected JSON pack only.")
        text = providers.complete(selected, system, retry, model, timeout)
        pack = providers.extract_json_object(text)
        validate_pack(pack)
        return pack


VERDICT_EXPLANATION_SYSTEM = (
    "You explain a SkillC verdict to the person who wrote an intent. A formal "
    "checker has already decided the verdict; never change, soften, or "
    "second-guess it. In 2-4 plain sentences, explain in terms of the intent "
    "and the environment why the checker reached this verdict, naming the "
    "decisive tools or conditions from the frontier or witness. For UNKNOWN, "
    "say what could not be established. Plain text only, no lists or markup.")


def explain_verdict(nl: str, verdict: dict, *, goal=None, environment: dict | None = None,
                    model: str | None = None, provider: str | None = None,
                    timeout: int = 120) -> str:
    """Untrusted plain-language reason for a verdict the checker decided."""
    facts = {
        "verdict": verdict.get("verdict"),
        "reason": verdict.get("reason"),
        "detail": verdict.get("detail"),
        "frontier": verdict.get("frontier", []),
        "witness": verdict.get("witness", []),
        "formal_goal": goal,
        "environment_binding": environment or {},
    }
    user = (f"Intent:\n```\n{nl}\n```\nChecker result:\n```json\n"
            f"{json.dumps(facts, indent=1)}\n```\nExplanation:")
    selected = providers.resolve_provider(provider)
    text = providers.complete(selected, VERDICT_EXPLANATION_SYSTEM, user, model,
                              timeout, json_mode=False)
    return text.strip()


def compact_with_repair(nl: str, model: str | None = None,
                        runtime_abilities: list[str] | None = None,
                        rounds: int = 2,
                        provider: str | None = None) -> tuple[dict, list[str]]:
    """Counterexample-guided compaction: compact, check, and when the trusted
    checker rejects the protocol with NON_PROJECTABLE (almost always an
    under-modelled conversation, not a real deadlock in the prose), feed the
    counterexample back to the untrusted compactor for a bounded number of
    repair rounds.  The protocol rejection is orthogonal to the goal label,
    so repair fires on it whether the goal is ACHIEVABLE or IMPOSSIBLE.

    Only NON_PROJECTABLE triggers repair: repairing MISSING_CAPABILITY or
    GOAL_UNSAT would tempt the model to invent tools or weaken the goal,
    which rule 1 forbids.  Returns (pack, repair_log); soundness is untouched
    -- every candidate passes the schema gate and the final verdict still
    comes from the trusted checker.
    """
    log: list[str] = []
    pack = compact(nl, model=model, runtime_abilities=runtime_abilities,
                   provider=provider)
    for _ in range(rounds):
        v = check(pack)
        if v.protocol_reason != "NON_PROJECTABLE":
            break
        log.append(f"repair round: {v.protocol_reason}: {v.protocol_detail}")
        followup = REPAIR_PROMPT.format(reason=v.protocol_reason,
                                        detail=v.protocol_detail,
                                        pack=json.dumps(pack))
        pack = compact(nl + "\n\n" + followup, model=model,
                       runtime_abilities=runtime_abilities, provider=provider)
    return pack, log


def compact_with_repair_measured(
        nl: str, model: str | None = None,
        runtime_abilities: list[str] | None = None,
        rounds: int = 1, provider: str | None = None) -> tuple[dict, list[str], Cost]:
    """`compact_with_repair`, additionally returning the measured token cost
    of every round as a `skillc.tokens.Cost` (the API's own usage blocks)."""
    with metered() as usage:
        pack, log = compact_with_repair(nl, model=model,
                                        runtime_abilities=runtime_abilities,
                                        rounds=rounds, provider=provider)
    return pack, log, measured_cost(usage)


def compact_ce(nl: str, model: str | None = None, timeout: int = 600,
               runtime_abilities: list[str] | None = None,
               provider: str | None = None, retries: int = 2,
               return_text: bool = False, runtime=None,
               version: str = DEFAULT_CE_VERSION):
    """Compact natural language into a pack via Controlled English.

    The model writes CE (untrusted); `ce.compile_ce` turns it into a pack
    deterministically and runs the same schema gate as `compact`.  A parse or
    gate error is fed back verbatim for at most `retries` rounds (two by
    default) -- the error names the line and column, so the retry is a
    targeted edit, not a re-generation.  With `return_text` returns
    (pack, ce_text).  With a `runtime`, `version` selects the prompt
    ("p2g+", the default, or the frozen "p2g"; see
    `prompts.ce_runtime_messages`).
    """
    selected = providers.resolve_provider(provider)
    if runtime is not None:          # manifest-bound: Gamma from the runtime
        system, user = ce_runtime_messages(nl, runtime, version=version)
    else:
        system, user = ce_messages(nl, runtime_abilities)
    prompt = user
    for attempt in range(retries + 1):
        text = providers.complete(selected, system, prompt, model, timeout,
                                  json_mode=False)
        try:
            ce_text = extract_ce(text)
            pack = (compile_ce_runtime(ce_text, runtime).pack
                    if runtime is not None else compile_ce(ce_text))
        except (CEError, PackError) as e:
            if attempt == retries:
                raise
            prompt = user + CE_RETRY_PROMPT.format(error=e, text=text.strip())
            continue
        return (pack, ce_text) if return_text else pack
    raise AssertionError("unreachable")


def compile_ce_runtime(text: str, runtime):
    """CE text -> (pack, Binding) under `runtime`; raises CEError/PackError."""
    parsed = parse_ce_detailed(text)
    return bind_runtime(parsed.pack, parsed.bindings, runtime)


def _analyze(reply: str, runtime) -> dict:
    """P2g's reading of one reply: extract, parse, bind (no pruning), check."""
    try:
        ce_text = extract_ce(reply)
        parsed = parse_ce_detailed(ce_text)
        bound = bind_runtime(parsed.pack, parsed.bindings, runtime, prune=False)
        verdict = check(bound.pack)
    except (CEError, PackError, ValueError, KeyError) as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return {"ok": True, "ce_text": ce_text, "parsed": parsed, "bound": bound,
            "verdict": verdict}


def compact_ce_rounds(system: str, user: str, runtime, model: str | None = None,
                      provider: str | None = None, timeout: int = 600,
                      retries: int = 2, repair: bool = True) -> dict:
    """The P2g compaction loop for prepared (system, user) messages.

    Round 1 is the plain prompt.  A reply that does not parse, bind or pass the
    schema gate gets a located-error retry (`user` + CE_RETRY_PROMPT with the
    error and that reply), at most `retries` times.  A valid document the
    checker judges IMPOSSIBLE gets one counterexample-guided repair (`user` +
    CE_REPAIR_PROMPT with `explain_refutation`); the repair is kept only if it
    parses and `repair_violations` finds nothing, otherwise the refuted
    document stands.  Binding is without pruning, as P2g scores it.

    Returns {"rounds": [{"round", "kind", "user", "reply", "usage", "ok",
    "error"}], "system", "ok", "error", "ce_text", "parsed", "bound",
    "verdict", "repaired", "repair_rejected"}; "ok" False means no round
    produced a valid document (the last error is kept)."""
    selected = providers.resolve_provider(provider)
    out: dict = {"system": system, "rounds": [], "ok": False, "error": None,
                 "ce_text": None, "parsed": None, "bound": None, "verdict": None,
                 "repaired": False, "repair_rejected": []}

    def call(kind: str, prompt: str) -> dict:
        with metered() as usage:
            reply = providers.complete(selected, system, prompt, model, timeout,
                                       json_mode=False)
        res = _analyze(reply, runtime)
        out["rounds"].append({"round": len(out["rounds"]) + 1, "kind": kind,
                              "user": prompt, "reply": reply, "usage": list(usage),
                              "ok": res["ok"], "error": res.get("error")})
        return {**res, "reply": reply}

    res = call("first", user)
    for _ in range(retries):
        if res["ok"]:
            break
        res = call("retry", user + CE_RETRY_PROMPT.format(error=res["error"],
                                                           text=res["reply"].strip()))
    if not res["ok"]:
        out["error"] = res["error"]
        return out
    out.update({k: res[k] for k in ("ce_text", "parsed", "bound", "verdict")})
    out["ok"] = True
    if repair and res["verdict"].label == "IMPOSSIBLE":
        expl = explain_refutation(res["verdict"], res["bound"])
        fixed = call("repair", user + CE_REPAIR_PROMPT.format(
            explanation=expl, text=res["ce_text"].strip()))
        if not fixed["ok"]:
            out["repair_rejected"] = [f"the repair does not parse: {fixed['error']}"]
        else:
            bad = repair_violations(res["parsed"], fixed["parsed"])
            if bad:
                out["repair_rejected"] = bad
            else:
                out.update({k: fixed[k] for k in ("ce_text", "parsed", "bound", "verdict")})
                out["repaired"] = True
    return out


READER_PASSED = ("deterministic reader: no unavailable hard requirement against "
                 "runtime `{name}`")
READER_SKIPPED = "deterministic reader not run: {why}"


def _as_runtime(runtime):
    """A `frontend.runtime.Runtime` for a name, a path, a dict or a Runtime."""
    from .runtime import Runtime, load_runtime
    if isinstance(runtime, Runtime):
        return runtime
    if isinstance(runtime, dict):
        return Runtime.from_dict(runtime)
    return load_runtime(str(runtime))


def reader_refutation(text: str, runtime):
    """Step 1 of `decide_text`: (verdict, evaluation, note).

    verdict is the REQUIREMENT_UNAVAILABLE refutation of the deterministic
    requirement reader (`env.manifest.refute_text`), or None when the reader
    does not refute or cannot evaluate; note says which, for `detail`."""
    from ..env.manifest import REASON, manifest_facts, refute_text, witness_lines
    try:
        facts = manifest_facts(runtime)
    except (KeyError, ValueError, OSError) as e:
        return None, None, READER_SKIPPED.format(why=f"no runtime manifest ({e})")
    if facts is None:
        return None, None, READER_SKIPPED.format(why="no runtime manifest")
    ev = refute_text(text, facts)
    if not ev.blocking:
        return None, ev, READER_PASSED.format(name=facts.name)
    lines = witness_lines(ev)
    detail = (f"deterministic reader: hard requirement unavailable in runtime "
              f"`{facts.name}`: " + "; ".join(lines))
    return Verdict(False, REASON, detail, frontier=tuple(ev.blocking),
                   protocol="NOT_CHECKED"), ev, ""


def decide_text_detailed(text: str, runtime, *, model: str | None = None,
                         provider: str | None = None, version: str = DEFAULT_CE_VERSION,
                         retries: int = 2, timeout: int = 600, rdet: bool = True,
                         llm: bool = True) -> dict:
    """`decide_text`, returning {"verdict", "front_end", "evaluation",
    "compaction"}.  front_end is "deterministic-reader" when step 1 decided,
    "llm" when the model path did.  `rdet=False` skips step 1; `llm=False`
    skips step 2, and a text the reader does not refute is then UNKNOWN
    (reason NOT_REFUTED): no checker ran, so there is no witness."""
    out: dict = {"verdict": None, "front_end": None, "evaluation": None, "compaction": None}
    note = READER_SKIPPED.format(why="--no-rdet")
    if rdet:
        refuted, ev, note = reader_refutation(text, runtime)
        out["evaluation"] = ev
        if refuted is not None:
            out.update(verdict=refuted, front_end="deterministic-reader")
            return out
    if not llm:
        out.update(front_end="deterministic-reader", verdict=Verdict(
            False, "NOT_REFUTED", note + "; no model was called and the checker did not "
            "run, so this is no ACHIEVABLE verdict", unknown=True, protocol="NOT_CHECKED"))
        return out
    rt = _as_runtime(runtime)
    system, user = ce_runtime_messages(text, rt, version=version)
    res = compact_ce_rounds(system, user, rt, model=model, provider=provider,
                            timeout=timeout, retries=retries)
    out["compaction"] = res
    if not res["ok"]:
        raise CEError(f"compaction produced no valid CE document: {res['error']}")
    v = res["verdict"]
    v = replace(v, detail=(v.detail + "; " if v.detail else "") + note)
    out.update(verdict=v, front_end="llm")
    return out


def decide_text(text: str, runtime, *, model: str | None = None,
                provider: str | None = None, version: str = DEFAULT_CE_VERSION,
                retries: int = 2) -> Verdict:
    """Decide a natural-language skill against a runtime manifest: the union of
    the deterministic requirement reader (Rdet) and P2g+ compaction.

    Step 1: `env.manifest.refute_text(text, runtime)`.  When it finds a hard
    requirement the manifest marks unavailable, the result is IMPOSSIBLE with
    reason REQUIREMENT_UNAVAILABLE, the `kind:name` requirements as the
    frontier and the evidence lines in `detail`; no model is called.  Its
    `coverage` is "deterministic-reader:manifest", not Theorem 1.
    Step 2: otherwise `compact_ce_rounds` with the P2g+ prompt (`version`)
    binds the CE document to the runtime and the checker decides; `detail`
    notes that the reader found no unavailable hard requirement.  When there is
    no manifest to read, step 1 is skipped and `detail` says so.

    Measured on the blind set3 (docs/COMPACTION_RELIABILITY.md): the union has
    BLOCKED recall 0.44 at 23/246 false refutations; P2g+ alone 0.07 at 2/246."""
    return decide_text_detailed(text, runtime, model=model, provider=provider,
                                version=version, retries=retries)["verdict"]


def parse_json_rt(text: str):
    """JB reply -> ParseResult (pack without bindings, bindings per capability)."""
    obj = providers.extract_json_object(text)
    caps = obj.get("capabilities")
    if not isinstance(caps, dict):
        raise CEError("the pack has no \"capabilities\" object")
    bindings = {}
    for name, cap in caps.items():
        if not isinstance(cap, dict):
            raise CEError(f"capability `{name}` is not an object")
        via, needs = cap.pop("via", None), cap.pop("needs", None) or []
        if not isinstance(needs, list) or not all(isinstance(x, str) for x in needs):
            raise CEError(f"capability `{name}`: \"needs\" must be a list of names")
        if via is not None and not isinstance(via, str):
            raise CEError(f"capability `{name}`: \"via\" must be a string")
        bindings[name] = {"via": via, "needs": needs}
    obj.setdefault("init_true", [])
    obj.setdefault("init_constraints", [])
    validate_pack(obj)
    return ParseResult(obj, {}, bindings, None)

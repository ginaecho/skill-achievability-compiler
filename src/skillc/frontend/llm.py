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

from ..checker import check
from ..pack import PackError, validate_pack
from . import providers
from .ce import CEError, ParseResult, compile_ce, extract_ce, parse_ce_detailed
from .prompts import (CE_RETRY_PROMPT, REPAIR_PROMPT, RUNTIME_ABILITIES_NOTE,
                      SYSTEM, ce_messages, ce_runtime_messages)
from .runtime import bind_runtime


def compact(nl: str, model: str | None = None, timeout: int = 600,
            runtime_abilities: list[str] | None = None,
            provider: str | None = None) -> dict:
    """Compact natural language into a provider-neutral validated pack.

    runtime_abilities: general abilities the target runtime grants (the
    Gamma_0 the prose presupposes without naming tools); without it the
    compactor under-grants and refutes deployed skills that assume a phone,
    a browser, or a user to talk to.

    provider: ``anthropic`` or ``azure-openai``. If omitted,
    SKILLC_LLM_PROVIDER is used, then ``anthropic``.
    """
    selected = providers.resolve_provider(provider)
    system = SYSTEM
    if runtime_abilities:
        system += RUNTIME_ABILITIES_NOTE.format(
            abilities="; ".join(runtime_abilities))
    user = f"Natural-language skill:\n```\n{nl}\n```\nJSON pack:"
    text = providers.complete(selected, system, user, model, timeout)
    pack = providers.extract_json_object(text)
    validate_pack(pack)          # deterministic gate on every provider output
    return pack


def compact_with_repair(nl: str, model: str | None = None,
                        runtime_abilities: list[str] | None = None,
                        rounds: int = 2,
                        provider: str | None = None) -> tuple[dict, list[str]]:
    """Counterexample-guided compaction: compact, check, and when the trusted
    checker refutes with NON_PROJECTABLE (almost always an under-modelled
    conversation, not a real deadlock in the prose), feed the counterexample
    back to the untrusted compactor for a bounded number of repair rounds.

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
        if v.achievable or v.reason != "NON_PROJECTABLE":
            break
        log.append(f"repair round: {v.reason}: {v.detail}")
        followup = REPAIR_PROMPT.format(reason=v.reason, detail=v.detail,
                                        pack=json.dumps(pack))
        pack = compact(nl + "\n\n" + followup, model=model,
                       runtime_abilities=runtime_abilities, provider=provider)
    return pack, log


def compact_ce(nl: str, model: str | None = None, timeout: int = 600,
               runtime_abilities: list[str] | None = None,
               provider: str | None = None, retries: int = 1,
               return_text: bool = False, runtime=None):
    """Compact natural language into a pack via Controlled English.

    The model writes CE (untrusted); `ce.compile_ce` turns it into a pack
    deterministically and runs the same schema gate as `compact`.  A parse or
    gate error is fed back verbatim for at most `retries` rounds -- the error
    names the line and column, so the retry is a targeted edit, not a
    re-generation.  With `return_text` returns (pack, ce_text).
    """
    selected = providers.resolve_provider(provider)
    if runtime is not None:          # manifest-bound: Gamma from the runtime
        system, user = ce_runtime_messages(nl, runtime)
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

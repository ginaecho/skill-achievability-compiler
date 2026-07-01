"""Optional LLM compaction front-end (untrusted, env-gated).

Produces a *semantic* pack from natural language via the Anthropic API --
capturing guards, budgets, roles, and branching that the deterministic
front-end does not attempt.  The output is untrusted by design: it passes
through the deterministic schema gate (validate_pack) and then the trusted
checker; a hallucinated compaction can only yield a false ACHIEVABLE (caught
by later layers), never a false IMPOSSIBLE about the pack it actually emitted.

Requires ANTHROPIC_API_KEY.  Never used implicitly: only via
`skillc compile --llm` or a direct call to compact().
"""
from __future__ import annotations

import json
import os
import urllib.request

from ..pack import validate_pack

DEFAULT_MODEL = "claude-sonnet-5"
API_URL = "https://api.anthropic.com/v1/messages"

SCHEMA_DOC = """
Pack schema (JSON):
{
  "name": "string",
  "roles": ["string", ...],
  "capabilities": {
    "<cap>": {
      "owner": "<role>",
      "pre":  <formula>,           // guard; default true
      "add":  ["pred", ...],       // predicates set TRUE (STRIPS effect)
      "del":  ["pred", ...],       // predicates set FALSE
      "assigns": {"var": <expr>},  // deterministic numeric update v := expr
      "nondet":  {"var": <formula over the NEW value>}
    }
  },
  "protocol": [<step>, ...],
  "goal": <formula>,
  "init_true": ["pred", ...],
  "init_constraints": [<formula>, ...]
}
<step>    = {"act": {"cap": "<cap>", "by": "<role>"}}
          | {"msg": {"from": "<role>", "to": "<role>", "label": "<l>"}}
          | {"choice": {"by": "<role>", "branches": {"<label>": [<step>...], ...}}}
          | {"goal": <formula>}
          | {"rec": {"name": "X", "body": [<step>...]}}   // tail-recursive loop
          | {"continue": "X"}                             // last step of its block
          | {"spawn": {"role": "<role>"}}   // runtime participant spawning
Optionally declare per-role behaviours for conformance checking:
"skills": {"<role>": [<local step>...]} with local steps
  {"send": {"to","label"}} | {"recv": {"from","label"}} | {"act": {"cap"}}
  | {"select": {"branches": {...}}} | {"branch": {"from", "branches": {...}}}
  | {"rec": {"name","body"}} | {"continue": "X"}
<formula> = "pred" | true | false | {"and":[...]} | {"or":[...]} | {"not": f}
          | {"cmp": [expr, "<"|"<="|"=="|">"|">="|"!=", expr]}
<expr>    = "var" | int | {"+":[e,e]} | {"-":[e,e]} | {"*":[e,e]}
"""

SYSTEM = (
    "You convert a natural-language agent skill into a formal achievability "
    "pack. Output ONLY JSON conforming to the schema. Be conservative:\n"
    "1. Declare a capability ONLY if the prose grants that tool. Never invent "
    "a tool to make the goal reachable. If the plan mentions an action with "
    "no corresponding tool, still emit it in the protocol as an 'act', but do "
    "NOT add it to capabilities -- the checker will flag the gap. This is the "
    "single most important rule.\n"
    "2. For each capability, extract its precondition (pre) and effects "
    "(add/del/assigns/nondet) from what the prose claims. Use nondet for "
    "\"books a fare under 500\"-style post-conditions.\n"
    "3. Encode the goal as a formula capturing every conjunct the user asked "
    "for, including refinements like \"under $500\".\n"
    "4. Encode the plan as the protocol; use 'choice' for branching and 'msg' "
    "for inter-role messages. If a role must act inside a branch, include the "
    "informing msg only if the prose provides one.\n"
    "5. List predicates true at the start in init_true; everything else is "
    "false by default (frame assumption).\n"
    "6. Use rec/continue for retry loops (continue must be the last step of "
    "its block: only tail recursion is decidable). If the prose spawns "
    "subagents at run time, emit a spawn step -- the checker degrades to "
    "UNKNOWN rather than guessing.\n" + SCHEMA_DOC
)


def compact(nl: str, model: str = DEFAULT_MODEL, timeout: int = 120) -> dict:
    """Compact natural language into a validated pack via the Anthropic API."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set; the LLM front-end is "
                           "opt-in -- use the deterministic front-end instead")
    body = json.dumps({
        "model": model,
        "max_tokens": 2000,
        "system": SYSTEM,
        "messages": [{"role": "user",
                      "content": f"Natural-language skill:\n```\n{nl}\n```\nJSON pack:"}],
    }).encode()
    req = urllib.request.Request(
        API_URL, data=body,
        headers={"content-type": "application/json", "x-api-key": key,
                 "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.load(r)
    text = "".join(b.get("text", "") for b in out.get("content", [])
                   if b.get("type") == "text").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    pack = json.loads(text)
    validate_pack(pack)          # the deterministic gate on untrusted output
    return pack

"""Prompt texts for the untrusted LLM compaction front-ends.

Every prompt variant used by `frontend.llm` and the benchmark scripts lives
here, together with the builders that assemble (system, user) message pairs:

    SYSTEM / compact            natural language -> JSON pack
    CE_SYSTEM / ce_messages     natural language -> Controlled English
    ce_runtime_messages         P2g: CE bound to a runtime manifest (P3: levels)
    ce_grounded_messages        P2g + software grounding and fallbacks
    ce_tpl_messages             P2g + tool-policy library obligations
    ce_index_messages           P2g + policy-index reference facts
    json_runtime_messages       JB: P2g's rules with the pack written as JSON
    direct_messages             D: intent -> verdict, no logical block

The texts are data: changing a word changes the experiment, so they are kept
verbatim and assembled by string surgery rather than rewritten per variant.
"""
from __future__ import annotations

from .runtime import runtime_note
from .toolpolicy import obligations_note

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
          | {"goal": <formula>}   // checkpoint assertion HERE, not a declaration
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
<expr>    = "var" | int | {"+":[e,e]} | {"-":[e,e]} | {"*":[int,e]} | {"*":[e,int]}
Multiplication must have an integer constant operand (QF-LIA); never multiply
two variable-bearing expressions.
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
    "for, including refinements like \"under $500\". The top-level goal is "
    "checked at termination automatically. A protocol {'goal': ...} step is "
    "an assertion that the goal ALREADY holds at that point, not a declaration "
    "of future intent. Omit protocol goal markers unless the prose explicitly "
    "requires such a checkpoint; never put one before actions that establish "
    "the goal. Any marker must equal the top-level goal exactly.\n"
    "4. Encode the plan as the protocol; use 'choice' for branching and 'msg' "
    "for inter-role messages. If a role must act inside a branch, include the "
    "informing msg only if the prose provides one.\n"
    "5. List predicates true at the start in init_true; everything else is "
    "false by default (frame assumption).\n"
    "6. Use rec/continue for retry loops (continue must be the last step of "
    "its block: only tail recursion is decidable). If the prose spawns "
    "subagents at run time, emit a spawn step -- the checker degrades to "
    "UNKNOWN rather than guessing.\n"
    "7. Abstract goal-irrelevant payload detail away (the tolerance dial): "
    "keep the pack SMALL -- at most ~12 capabilities and ~25 protocol steps. "
    "Merge micro-steps that share a tool; model only state that the goal or "
    "some guard mentions.\n"
    "8. IMPORTANT -- observed choices. Unobserved choice is a phenomenon of "
    "asynchronous multi-agent handoffs; inside a live conversation the "
    "outcome of a choice is announced by the medium itself. Whenever a "
    "choice is resolved within a conversation among the roles that then act "
    "on it (an assistant<->user chat, a phone call), set \"observed\": true "
    "on that choice. In a skill that is one continuous conversation between "
    "the agent and its user, EVERY choice by either of them is observed. "
    "Reserve msg steps for genuinely asynchronous handoffs between separate "
    "agents; a choice with neither observed:true nor informing msgs is "
    "refuted as a deadlock. Use \"external\": true when the environment "
    "rather than the agent resolves the choice.\n" + SCHEMA_DOC)

RUNTIME_ABILITIES_NOTE = (
    "\nThe skill executes in a runtime that ALREADY grants the agent these "
    "general abilities: {abilities}. When the plan performs an action that "
    "one of these abilities covers, DECLARE it as a capability (owner: the "
    "acting role) -- you are not inventing a tool, the runtime provides it. "
    "Leave an act undeclared ONLY when the prose itself signals the tool "
    "may be absent (e.g. 'where the save_skill tool exists') or the action "
    "exceeds every listed ability.")

CONSUMER_ABILITIES = [
    "converse with the user and ask questions",
    "browse the web and operate a browser session",
    "place and hold phone calls when the flow is phone-based",
    "read and write files and present them to the user",
    "check and update the user's calendar",
    "use memory of the user's stated preferences",
]

DEVELOPER_ABILITIES = [
    "read and write files in the working directory",
    "run shell commands, scripts, and local development tools",
    "install and use declared project dependencies",
    "start and stop local development servers",
    "operate a browser and capture screenshots",
    "inspect logs, test output, and generated artifacts",
    "converse with the user and ask clarifying questions",
]

RUNTIME_ABILITY_PROFILES = {
    "none": [],
    "consumer": CONSUMER_ABILITIES,
    "developer": DEVELOPER_ABILITIES,
}

ENVIRONMENT_VOCABULARY_NOTE = (
    "\nIn this setting the environment, not you, decides which tools exist; "
    "this overrides rule 1. Declare EVERY external operation the intent "
    "requires as a capability, with the preconditions and effects the intent "
    "describes, whether or not its name appears below. The agent's own work is "
    "not an external operation: reasoning, reviewing, planning, drafting text, "
    "presenting its answer, and talking with the user in the conversation need "
    "no tool, so do not make them capabilities or acts, and keep only "
    "conditions an external operation establishes in the goal."
    "\nThe target environment names its operations and conditions with a closed "
    "vocabulary. When the intent performs one of these operations, use exactly "
    "this capability name: {tools}. When a goal condition, guard, or effect "
    "means one of these conditions or values, use exactly this name: {states}. "
    "If the intent needs an operation or condition that is not listed, keep it "
    "under its own name: never drop a required operation or goal condition "
    "because it is missing from the list.")


def vocabulary_note(vocabulary: dict) -> str:
    """Tool and state names only; never the environment's tool contracts."""
    tools = ", ".join(sorted(vocabulary.get("tools", {}))) or "(none)"
    states = "; ".join(
        f"{name} ({meaning})" if meaning and meaning != name.replace("_", " ") else name
        for name, meaning in sorted(vocabulary.get("states", {}).items())
    ) or "(none)"
    return ENVIRONMENT_VOCABULARY_NOTE.format(tools=tools, states=states)

CE_DOC = """
SkillC Controlled English (CE). One statement per line; identifiers are ALWAYS
in backticks; nested steps are "- " bullets indented two spaces per level.

  Skill `NAME`.
  Roles: `R`, ... .                       (or: Roles: none.)
  Tool `C` (owner `R`): CLAUSE; CLAUSE.   (or: Tool `C` (owner `R`).  when it has no clauses)
      CLAUSE = requires F | adds `P`, ... | removes `P`, ...
             | sets `V` to E | picks `V` with F
  Initially true: `P`, ... .              (predicates true at the start; or: Initially true: none.)
  Initially: F.                           (one line per initial constraint)
  Goal: F.                                (checked at termination)
  Protocol:                               (or: Protocol: none.)
    - `R` uses `C`.
    - `A` tells `B` `LABEL`.
    - `R` chooses one of (observed):      (flags in parentheses are optional:
      - branch `LABEL`:                    external, observed)
        - `R` uses `C`.
      - branch `LABEL`: none.
    - loop `X`:
      - `R` uses `C`.
      - repeat `X`.                       (repeat must be the last step of its loop)
    - checkpoint: F.                      (asserts F ALREADY holds here)
    - spawn `R`.
  Behaviour of `R`:                       (optional per-role behaviour)
    - use `C`.   - send `L` to `B`.   - receive `L` from `A`.
    - select one of:  /  - branch on `A` one of:   (then "- branch `L`:" lines)

  F = F or F | F and F | not F | ( F ) | true | false | `P`
    | all of (F, ...) | any of (F, ...) | E OP E       OP = < <= == > >= !=
  E = `V` | INT | -INT | ( E ) | E + E | E - E | E * E
      (one arithmetic operator per level -- nest with parentheses; '*' needs
      an integer on one side)

Example:
  Skill `book-flight`.
  Roles: `agent`, `user`.
  Tool `search_flights` (owner `agent`): adds `options_found`.
  Tool `book_flight` (owner `agent`): requires `options_found`; adds `booked`; picks `price` with `price` < 500.
  Initially: `price` == 0.
  Goal: `booked` and `confirmation_sent` and `price` < 500.
  Protocol:
    - `agent` uses `search_flights`.
    - `user` chooses one of (observed):
      - branch `accept`:
        - `agent` uses `book_flight`.
        - `agent` uses `send_email`.
      - branch `decline`: none.
(`send_email` is used but is not declared as a Tool, because the prose grants
no such tool: the checker reports that gap.)
"""

CE_SYSTEM = (
    "You convert a natural-language agent skill into a formal achievability "
    "pack written in SkillC Controlled English (CE). Output ONLY the CE "
    "document, inside one ```ce fenced block. Be conservative:\n"
    "1. Declare a Tool ONLY if the prose grants that tool. Never invent "
    "a tool to make the goal reachable. If the plan mentions an action with "
    "no corresponding tool, still write it in the Protocol as a 'uses' step, "
    "but do NOT declare it as a Tool -- the checker will flag the gap. This is "
    "the single most important rule.\n"
    "2. For each Tool, extract its precondition (requires) and effects "
    "(adds/removes/sets/picks) from what the prose claims. Use 'picks' for "
    "\"books a fare under 500\"-style post-conditions.\n"
    "3. Encode the Goal as a formula capturing every conjunct the user asked "
    "for, including refinements like \"under $500\". The Goal is "
    "checked at termination automatically. A protocol 'checkpoint' step is "
    "an assertion that the goal ALREADY holds at that point, not a declaration "
    "of future intent. Omit checkpoints unless the prose explicitly "
    "requires such a checkpoint; never put one before actions that establish "
    "the goal. Any checkpoint must equal the Goal exactly.\n"
    "4. Encode the plan as the Protocol; use 'chooses one of' for branching "
    "and 'tells' for inter-role messages. If a role must act inside a branch, "
    "include the informing message only if the prose provides one.\n"
    "5. List predicates true at the start in 'Initially true'; everything else "
    "is false by default (frame assumption).\n"
    "6. Use loop/repeat for retry loops (repeat must be the last step of "
    "its loop: only tail recursion is decidable). If the prose spawns "
    "subagents at run time, write a spawn step -- the checker degrades to "
    "UNKNOWN rather than guessing.\n"
    "7. Abstract goal-irrelevant payload detail away (the tolerance dial): "
    "keep the pack SMALL -- at most ~12 tools and ~25 protocol steps. "
    "Merge micro-steps that share a tool; model only state that the goal or "
    "some guard mentions.\n"
    "8. IMPORTANT -- observed choices. Unobserved choice is a phenomenon of "
    "asynchronous multi-agent handoffs; inside a live conversation the "
    "outcome of a choice is announced by the medium itself. Whenever a "
    "choice is resolved within a conversation among the roles that then act "
    "on it (an assistant<->user chat, a phone call), mark that choice "
    "(observed). In a skill that is one continuous conversation between "
    "the agent and its user, EVERY choice by either of them is observed. "
    "Reserve 'tells' steps for genuinely asynchronous handoffs between separate "
    "agents; a choice with neither (observed) nor informing messages is "
    "refuted as a deadlock. Mark a choice (external) when the environment "
    "rather than the agent resolves it.\n" + CE_DOC)

CE_RETRY_PROMPT = (
    "\n\nYour previous CE document was rejected by the deterministic parser "
    "or schema gate:\n  {error}\n\nPrevious document:\n```ce\n{text}\n```\n"
    "Output the corrected CE document only. Do not weaken the goal or add "
    "tools the prose does not grant.")


CE_RUNTIME_RULE_1 = (
    "1. Declare a Tool for every operation in the plan that changes the world "
    "or reaches beyond the conversation (running commands, writing files, "
    "calling services, deploying), and bind it with 'via' to the RUNTIME tool "
    "that performs it. Most developer operations -- installing a CLI or "
    "package, building, running tests or scripts, generating or converting "
    "files, rendering media, querying a local tool or database, git -- are "
    "via `bash` or a file tool. If no RUNTIME tool can perform the operation "
    "(another operating system, a device, a hosted service's own console), "
    "still declare it and write 'via' with a short name of what it would take "
    "(e.g. via `windows_desktop`); the checker withdraws such tools. If the "
    "operation can only succeed with an account, credential, API key, paid "
    "service or publishing right, add 'needs' with a short resource name "
    "(e.g. needs `aws_account`); the checker blocks it unless the RUNTIME "
    "grants that resource. Never bind an operation to a RUNTIME tool that "
    "cannot really perform it. This is the single most important rule.\n")

CE_RUNTIME_EXTRA_RULES = (
    "9. Thinking is not a Tool. Reasoning, deciding, planning, reading these "
    "instructions or reference text you already have, following a procedure, "
    "and writing text in your reply are done by the agent itself: do not "
    "declare them as Tools and do not write them as protocol steps.\n"
    "10. The Goal is the skill's core deliverable for one representative "
    "request. Optional, conditional or follow-up work (extra diagnostics, "
    "notifications, clean-up extras, publishing or production deploys the "
    "core request does not require) goes in a 'chooses one of (observed)' "
    "with a branch that skips it, or is left out. If the core deliverable "
    "itself is a deployment or publication, it stays on the mandatory path.\n")

# P3: two goal levels.  Replaces rule 10; the rest of the prompt is P1's.
CE_LEVELS_RULE_10 = (
    "10. Two goal levels. 'Goal:' is the skill's core deliverable for one "
    "representative request: the artifact, change, answer or verified result "
    "a developer would accept as the skill having done its job. 'Live goal:' "
    "(optional) is an effect OUTSIDE the runtime that the skill goes on to "
    "produce once the core deliverable exists: deploying or publishing it, "
    "running it against a live hosted service or a real account, sending or "
    "posting it to a third party. Steps that only serve the Live goal go in a "
    "'chooses one of (observed)' with a `skip` branch that is none, so the "
    "Goal is reachable without them. Decide with this test: remove the live "
    "effect -- does the skill still leave the user with something they asked "
    "for (code, configuration, a local build or test run, a report)? If yes, "
    "that is the Goal and the live effect is the Live goal. If no -- the "
    "skill's only purpose is the live effect (e.g. querying an account's "
    "data, publishing an existing artifact, operating a hosted service) -- "
    "the live effect IS the Goal and there is no Live goal. Other optional or "
    "follow-up work goes in a skippable branch or is left out.\n")

CE_LEVELS_DOC = (
    "\nGoal levels:\n"
    "  Goal: F.           -- the core deliverable (required)\n"
    "  Live goal: F.      -- optional, right after Goal: the effect outside "
    "the runtime\n"
    "Example:\n"
    "  Goal: `site_built` and `tests_pass`.\n"
    "  Live goal: `site_deployed`.\n"
    "  Protocol:\n"
    "    - `agent` uses `build_site`.\n"
    "    - `agent` uses `run_tests`.\n"
    "    - `agent` chooses one of (observed):\n"
    "      - branch `deploy`:\n"
    "        - `agent` uses `deploy_site`.\n"
    "      - branch `skip`: none.\n")

CE_RUNTIME_DOC = (
    "\nRuntime bindings (tool clauses, written first):\n"
    "  via `T`            -- T is the RUNTIME tool that performs this Tool\n"
    "  needs `R`, ...     -- resources outside the conversation it needs\n"
    "Example: Tool `run_tests` (owner `agent`): via `bash`; requires "
    "`code_written`; adds `tests_pass`.\n"
    "Example: Tool `deploy_prod` (owner `agent`): via `bash`; needs "
    "`cloud_account`; adds `deployed`.\n")


# Tool-policy library (frontend.toolpolicy): extra clauses and the per-skill
# obligations.  Appended to P1's prompt; nothing else changes.
CE_TPL_DOC = (
    "\nTool-policy clauses (tool clauses, written after via/needs):\n"
    "  runs `P`, ...       -- the concrete program(s) the Tool runs inside its "
    "RUNTIME tool, when the tool-policy library names one\n"
    "  effect `E`          -- one of `local`, `reads_external`, "
    "`writes_external`, `publishes`: what the Tool does to the world outside "
    "the machine. Write `writes_external` for any Tool that submits, pushes, "
    "posts, comments or sends to a third party, and `publishes` for public "
    "releases or deployments.\n"
    "Example: Tool `submit_report` (owner `agent`): via `bash`; effect "
    "`writes_external`; requires `report_ready`; adds `report_sent`.\n"
    "Subagents: spawning a subagent is not a RUNTIME tool here unless listed; "
    "write it as a 'spawn' step.\n")

def ce_runtime_messages(nl: str, runtime, levels: bool = False) -> tuple[str, str]:
    """(system, user) for manifest-bound NL -> CE compaction.

    `levels=True` is P3: rule 10 asks for two goal levels (Goal / Live goal)
    and the CE documentation gains the 'Live goal:' statement."""
    head, rest = CE_SYSTEM.split("\n1. ", 1)
    rule1, others = rest.split("\n2. ", 1)
    rules, doc = ("2. " + others).split(CE_DOC, 1)
    extra = CE_RUNTIME_EXTRA_RULES
    if levels:
        extra = extra.split("10. ", 1)[0] + CE_LEVELS_RULE_10
    system = (head + "\n" + CE_RUNTIME_RULE_1 + rules + extra
              + CE_DOC + CE_RUNTIME_DOC + (CE_LEVELS_DOC if levels else "")
              + runtime_note(runtime))
    user = f"Natural-language skill:\n```\n{nl}\n```\nCE document:"
    return system, user

def ce_tpl_messages(nl: str, runtime, obligations) -> tuple[str, str]:
    """(system, user) for NL -> CE with the tool-policy library (TPL)."""
    system, user = ce_runtime_messages(nl, runtime)
    forbid = ", ".join(f"`{e}`" for e in runtime.forbid_effects) or "none"
    system += CE_TPL_DOC + f"Effects this RUNTIME forbids: {forbid}.\n"
    user = user.replace("\nCE document:", obligations_note(obligations) + "\nCE document:")
    return system, user

# P2g-grounded (ce_gr): P2g plus software grounding (rule 11), documented fallbacks
# (appended to rule 10) and the `runs` clause.  The binder resolves `runs` against the
# runtime's software policy (frontend.runtime.resolve_software).
CE_FALLBACK_RULE = (
    "If the skill itself documents a fallback for when a tool, connector, account "
    "or service is unavailable (e.g. 'if no CRM is connected, ask the user to "
    "paste the records'; 'without the API, work from an uploaded export'), write "
    "the primary path and the documented fallback as branches of a 'chooses one "
    "of (observed)', the fallback using only RUNTIME tools. Never invent a "
    "fallback the skill does not describe.\n")

CE_SOFTWARE_RULE = (
    "11. Name the software. When a Tool's work depends on a specific program, "
    "library, SDK or framework beyond generic shell utilities and the language "
    "runtime itself (e.g. `cudf`, `scvi-tools`, `packer`, `pandoc`, `ffmpeg`, "
    "a vendor SDK), add 'runs' with its package or command name as you would "
    "install or invoke it; the checker decides from the RUNTIME's software "
    "policy whether it can run. When the work needs another operating system, "
    "a GPU, a mobile device or emulator, or a physical instrument, say so with "
    "'via' (e.g. via `macos_desktop`, via `gpu`, via `usb_instrument`). Do not "
    "list software for work the agent does by writing text.\n")

CE_SOFTWARE_DOC = (
    "  runs `P`, ...       -- the specific software (package or command name) the "
    "Tool runs\n"
    "Example: Tool `train_model` (owner `agent`): via `bash`; runs `scvi-tools`; "
    "requires `data_loaded`; adds `model_trained`.\n")

SOFTWARE_NOTE = {
    "installable": "Software policy: any public package can be installed.\n",
    "preinstalled": ("Software policy: only software already installed on the "
                     "machine can run; nothing can be installed.\n"),
    "none": "Software policy: no software can be run at all.\n",
}


def ce_grounded_messages(nl: str, runtime) -> tuple[str, str]:
    """(system, user) for P2g-grounded: P2g's messages with the documented-
    fallback sentence added to rule 10, rule 11 (software), the `runs` clause and
    the runtime's software policy."""
    system, user = ce_runtime_messages(nl, runtime)
    r10_end = "it stays on the mandatory path.\n"
    assert r10_end in system
    system = system.replace(r10_end, r10_end.rstrip("\n") + " " + CE_FALLBACK_RULE
                            + CE_SOFTWARE_RULE, 1)
    doc_anchor = "  needs `R`, ...     -- resources outside the conversation it needs\n"
    system = system.replace(doc_anchor, doc_anchor + CE_SOFTWARE_DOC, 1)
    return system + SOFTWARE_NOTE.get(runtime.software, ""), user

# JB (runs/20260928_i2l/PLAN.md): P2g's rules, RUNTIME section, binder, retry and
# guarded repair, with the pack written as JSON instead of CE.  Each capability also
# carries "via" and "needs"; llm.parse_json_rt splits them off into the same
# ParseResult the CE parser returns, so everything after parsing is shared.
JSON_RT_RULE_1 = (
    "1. Declare a capability for every operation in the plan that changes the "
    "world or reaches beyond the conversation (running commands, writing files, "
    "calling services, deploying), and bind it with \"via\" to the RUNTIME tool "
    "that performs it. Most developer operations -- installing a CLI or "
    "package, building, running tests or scripts, generating or converting "
    "files, rendering media, querying a local tool or database, git -- are "
    "via \"bash\" or a file tool. If no RUNTIME tool can perform the operation "
    "(another operating system, a device, a hosted service's own console), "
    "still declare it and set \"via\" to a short name of what it would take "
    "(e.g. \"via\": \"windows_desktop\"); the checker withdraws such "
    "capabilities. If the operation can only succeed with an account, "
    "credential, API key, paid service or publishing right, add \"needs\" with "
    "a short resource name (e.g. \"needs\": [\"aws_account\"]); the checker "
    "blocks it unless the RUNTIME grants that resource. Never bind an operation "
    "to a RUNTIME tool that cannot really perform it. This is the single most "
    "important rule.\n")

JSON_RT_EXTRA_RULES = (
    "9. Thinking is not a capability. Reasoning, deciding, planning, reading "
    "these instructions or reference text you already have, following a "
    "procedure, and writing text in your reply are done by the agent itself: "
    "do not declare them as capabilities and do not write them as protocol "
    "steps.\n"
    "10. The goal is the skill's core deliverable for one representative "
    "request. Optional, conditional or follow-up work (extra diagnostics, "
    "notifications, clean-up extras, publishing or production deploys the "
    "core request does not require) goes in a 'choice' with \"observed\": "
    "true and a branch that skips it (an empty step list), or is left out. If "
    "the core deliverable itself is a deployment or publication, it stays on "
    "the mandatory path.\n")

JSON_RT_DOC = (
    "\nRuntime bindings (capability fields; \"via\" is required on every "
    "capability):\n"
    "  \"via\": \"T\"            -- T is the RUNTIME tool that performs this capability\n"
    "  \"needs\": [\"R\", ...]   -- resources outside the conversation it needs\n"
    "Example: \"run_tests\": {\"owner\": \"agent\", \"via\": \"bash\", "
    "\"pre\": \"code_written\", \"add\": [\"tests_pass\"]}\n"
    "Example: \"deploy_prod\": {\"owner\": \"agent\", \"via\": \"bash\", "
    "\"needs\": [\"cloud_account\"], \"add\": [\"deployed\"]}\n")

JSON_RT_RETRY = (
    "\n\nYour previous JSON pack was rejected by the deterministic schema gate "
    "or binder:\n  {error}\n\nPrevious pack:\n```json\n{text}\n```\n"
    "Output the corrected JSON pack only. Do not weaken the goal or add "
    "tools the prose does not grant.")


def json_runtime_messages(nl: str, runtime) -> tuple[str, str]:
    """(system, user) for JB: P2g's rules and RUNTIME section, JSON syntax.

    Rules 2-8 are the original JSON prompt's (they are the JSON wording of CE
    rules 2-8); rule 1 and rules 9-10 are P2g's, reworded for JSON."""
    head, rest = SYSTEM.split("\n1. ", 1)
    rules_2_8 = "2. " + rest.split("\n2. ", 1)[1].split(SCHEMA_DOC, 1)[0]
    system = (head + "\n" + JSON_RT_RULE_1 + rules_2_8.rstrip("\n") + "\n"
              + JSON_RT_EXTRA_RULES + SCHEMA_DOC + JSON_RT_DOC + runtime_note(runtime))
    user = f"Natural-language skill:\n```\n{nl}\n```\nJSON pack:"
    return system, user

JSON_RT_REPAIR_PROMPT = (
    "\n\nThe deterministic checker judged your JSON pack IMPOSSIBLE:\n"
    "{explanation}\n\n"
    "Your pack:\n```json\n{text}\n```\n\n"
    "Check that counterexample against the skill text. A refutation is often "
    "a compaction slip, but it may also be the truth. You may ONLY:\n"
    "  (a) bind an operation to a RUNTIME tool that really performs it "
    "(fix its \"via\");\n"
    "  (b) make optional, conditional or follow-up work skippable (a "
    "'choice' with \"observed\": true and an empty branch), or remove it if "
    "the core deliverable does not need it;\n"
    "  (c) add a missing effect to the step that really produces it, or "
    "remove a thinking step that is not a capability;\n"
    "  (d) mark a choice resolved inside the conversation as observed.\n"
    "You may NOT bind an operation to a RUNTIME tool that cannot really "
    "perform it, drop a \"needs\" for an account or credential the skill really "
    "requires, add RUNTIME tools, or change the goal. If none of (a)-(d) "
    "applies, output the pack unchanged: the refutation stands.\n"
    "Output the complete JSON pack only.")


# D (runs/20260928_i2l/PLAN.md): intent -> verdict directly, no logical block.
DIRECT_SYSTEM = (
    "You judge whether an AI agent working in the RUNTIME described below can "
    "deliver what a natural-language agent skill is for. Judge the skill's "
    "core deliverable for one representative request. Optional, conditional or "
    "follow-up work (extra diagnostics, notifications, clean-up extras, "
    "publishing or production deploys the core request does not require) does "
    "not count; if the core deliverable itself is a deployment or publication, "
    "it counts. Reasoning, planning and writing text are done by the agent "
    "itself. An operation that no RUNTIME tool can really perform, or that can "
    "only succeed with an account, credential, API key, paid service or "
    "publishing right the RUNTIME does not grant, cannot be done.\n"
    "Answer IMPOSSIBLE when a step the core deliverable cannot do without "
    "cannot be done in this RUNTIME; ACHIEVABLE when every such step can; "
    "UNKNOWN when you cannot tell. Output ONLY one JSON object:\n"
    "{\"verdict\": \"ACHIEVABLE\" | \"IMPOSSIBLE\" | \"UNKNOWN\", "
    "\"missing\": [\"what the runtime lacks, for IMPOSSIBLE\", ...]}\n")


def direct_messages(nl: str, runtime) -> tuple[str, str]:
    return (DIRECT_SYSTEM + runtime_note(runtime),
            f"Natural-language skill:\n```\n{nl}\n```\nJSON verdict:")


CE_REPAIR_PROMPT = (
    "\n\nThe deterministic checker judged your CE document IMPOSSIBLE:\n"
    "{explanation}\n\n"
    "Your document:\n```ce\n{text}\n```\n\n"
    "Check that counterexample against the skill text. A refutation is often "
    "a compaction slip, but it may also be the truth. You may ONLY:\n"
    "  (a) bind an operation to a RUNTIME tool that really performs it "
    "(fix its 'via');\n"
    "  (b) make optional, conditional or follow-up work skippable (a "
    "'chooses one of (observed)' with a 'none' branch), or remove it if the "
    "core deliverable does not need it;\n"
    "  (c) add a missing effect to the step that really produces it, or "
    "remove a thinking step that is not a Tool;\n"
    "  (d) mark a choice resolved inside the conversation as (observed).\n"
    "You may NOT bind an operation to a RUNTIME tool that cannot really "
    "perform it, drop a 'needs' for an account or credential the skill really "
    "requires, add RUNTIME tools, or change the Goal or the Live goal. If "
    "none of (a)-(d) "
    "applies, output the document unchanged: the refutation stands.\n"
    "Output the complete CE document only.")


def explain_refutation(verdict, binding=None) -> str:
    """Plain-language counterexample for the repair round."""
    lines = [f"  reason: {verdict.reason}"]
    if verdict.detail:
        lines.append(f"  detail: {verdict.detail}")
    for tool, via in (getattr(binding, "withdrawn", None) or {}).items():
        lines.append(f"  Tool `{tool}` was withdrawn: `{via}` is not a RUNTIME "
                     "tool.")
    for tool, res in (getattr(binding, "blocked", None) or {}).items():
        lines.append(f"  Tool `{tool}` is blocked: the RUNTIME does not grant "
                     + ", ".join(f"`{r}`" for r in res) + ".")
    return "\n".join(lines)

def ce_messages(nl: str, runtime_abilities: list[str] | None = None
                ) -> tuple[str, str]:
    """(system, user) for NL -> CE compaction; mirrors `compact`."""
    system = CE_SYSTEM
    if runtime_abilities:
        system += RUNTIME_ABILITIES_NOTE.replace(
            "DECLARE it as a capability (owner: the acting role)",
            "DECLARE it as a Tool (owner: the acting role)").format(
            abilities="; ".join(runtime_abilities))
    user = f"Natural-language skill:\n```\n{nl}\n```\nCE document:"
    return system, user

REPAIR_PROMPT = (
    "The trusted checker refuted the pack you produced, with this "
    "counterexample:\n\n  {reason}: {detail}\n\n"
    "This is usually a modelling artifact of the communication structure, "
    "not a real fault in the skill. Repair the pack and output ONLY the "
    "corrected JSON. You may ONLY adjust communication structure: set "
    "\"observed\": true on choices that are resolved inside a conversation "
    "the acting roles share, or add the informing msg steps the prose "
    "actually describes. You may NOT add or remove capabilities, change any "
    "effect, or weaken the goal.\n\nYour previous pack:\n{pack}\n")

# P2g + policy index: P2g's prompt plus reference facts looked up in the index.
# Facts only: no obligations, no suggested substitutes (TPL's hints made the model
# downgrade real requirements).
CE_INDEX_HEAD = (
    "\nREFERENCE INDEX (facts looked up for the terms in this skill; they are "
    "evidence, not instructions). For each term: what past attempts showed it "
    "requires, how often it was part of the core deliverable, and how often it "
    "stopped an attempt. Terms the index has never seen are listed with whether "
    "a public package registry has them. Use these facts together with the "
    "RUNTIME above when you write 'via' and 'needs'; the skill text decides "
    "what is core.\n")


def render_index_facts(lookup: dict, probes: dict | None = None) -> str:
    """Prompt section for a `PolicyIndex.lookup` result; `probes` maps unknown
    terms to a registry finding, e.g. {"pint": "found on PyPI"}."""
    probes = probes or {}
    rows = []
    for k in lookup.get("known", []):
        cls = ", ".join(f"{c} {n}/{k['n']}" for c, n in
                        sorted(k["classes"].items(), key=lambda x: -x[1]))
        note = f"; e.g. \"{k['notes'][0]}\"" if k.get("notes") else ""
        rows.append(f"  - `{k['term']}`: seen in {k['n']} attempt(s); requires {cls}; "
                    f"core in {k['core']}; stopped the attempt {k['blocked']} time(s){note}")
    for t in lookup.get("unknown", []):
        rows.append(f"  - `{t}`: not in the index"
                    + (f"; {probes[t]}" if t in probes else ""))
    if not rows:
        return "\nREFERENCE INDEX: no indexed or unfamiliar terms found in this skill.\n"
    return CE_INDEX_HEAD + "\n".join(rows) + "\n"


def ce_index_messages(nl: str, runtime, facts: str) -> tuple[str, str]:
    """(system, user) for P2g + policy index: P2g's messages with `facts`
    (from `render_index_facts`) appended to the system prompt."""
    system, user = ce_runtime_messages(nl, runtime)
    return system + facts, user

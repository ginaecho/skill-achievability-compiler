"""Runtime monitor: skillc stays active while an agent thinks and acts.

The check before the run (intent -> logical block -> verdict) is repeated during the run,
on three signals (docs/RUNTIME_MONITOR.md):

  plan      the agent writes its intended steps as Controlled English (a plan file).
            Only a plan the checker judges ACHIEVABLE under the runtime, with no
            prohibited behaviour, is approved; implementation is gated on it.
  thinking  the agent's reasoning text (thinking summaries, progress notes, visible
            text), scanned deterministically with the tool-policy library: a requirement
            the runtime cannot meet, or a prohibited behaviour, is put to the agent as a
            question (mode `ask`, the default); mode `stop` instead blocks further
            actions until a plan that passes is written.
  action    every tool call, before it runs: it needs an approved plan, must use a
            runtime tool the plan binds, and must not show an unmet requirement or a
            prohibited behaviour.  After it runs, failures in its output (a missing
            program, a rejected credential, no network) become runtime facts and the
            approved plan is re-checked from them; a plan that becomes IMPOSSIBLE is
            revoked.

Stop, explain, re-plan.  A refusal is never the end of the run.  Every refusal says what
skillc found and who can fix it (`Decision.next`): the agent, by changing the plan
("replan"), or only the user, because the runtime lacks an account, a credential, a
program or the network ("ask_user", with the missing items in `Decision.user_needs`).
After `Config.max_replans` refused plans in a row the agent is told to stop re-planning
and ask the user.

Everything here is deterministic and costs zero model tokens.  The state lives in one
JSON file so that separate hook processes share it.

The monitor itself knows nothing about the transport that carries the signals to it.
Adapters (Claude Code hooks, GitHub Copilot hooks, Agent Framework middleware) translate
their events into the five entry points `on_prompt`, `on_reasoning`, `pre_action`,
`post_action` and `submit_plan`, and build the tool map of their runtime with
`tool_map_from_names`.

Protocol state from executions.  For a hosted agent the tools the model calls are the
plan's own Tools (capabilities), and the plan is a protocol pack approved at deploy time
(`load_plan`).  The monitor then tracks the protocol state: `State.facts` holds the
predicates currently true (from the pack's `Initially true`), and every successful
execution of a capability applies its `adds` and `removes`.  Before a capability runs,
its `requires` formula is evaluated against the facts (three-valued: a comparison is
unknown and never denies), and its owner is checked against the calling role.  A
precondition that does not hold is refused with the Tools that would establish it.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

from .checker import check
from .frontend.ce import CEError, parse_ce_detailed, render_formula
from .frontend.prompts import CE_DOC, CE_RUNTIME_DOC, CE_SOFTWARE_DOC
from .frontend.runtime import Runtime, bind_runtime, load_runtime, runtime_note
from .frontend.toolpolicy import Library, Obligation, load_library, match, unmet
from .pack import PackError

ALLOW, DENY, WARN = "allow", "deny", "warn"

# first words of a string result that mean the tool did not do its work (is_failure)
FAILURE_WORDS = frozenset({"error", "rejected", "refused", "failed", "denied"})

# Claude Code tool -> runtime tool (the vocabulary of the runtime manifests)
TOOL_MAP = {"Bash": "bash", "Write": "write", "Edit": "edit", "MultiEdit": "edit",
            "NotebookEdit": "edit", "Read": "read", "WebFetch": "web_fetch",
            "WebSearch": "web_search", "Task": "agent_spawn", "Agent": "agent_spawn"}
# tools that only look around: allowed before a plan exists (planning needs them)
FREE_TOOLS = ("Read", "Glob", "Grep", "LS", "WebSearch", "TodoWrite", "ToolSearch")

# Names agents of various kinds give their tools -> the runtime tools they stand for, in
# order of preference (the first one the runtime has wins).  See tool_map_from_names.
TOOL_ALIASES: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("code_interpreter", "python", "execute", "run_code", "run_python"),
     ("code_interpreter", "bash")),
    (("bash", "shell", "powershell", "terminal"), ("bash",)),
    (("web_search", "search_web", "bing_search", "bing_grounding"), ("web_search",)),
    (("web_fetch", "fetch", "fetch_url", "http_get", "browse"), ("web_fetch",)),
    (("azure_ai_search", "file_search"), ("search",)),
    (("create", "write_file", "create_file"), ("write",)),
    (("edit", "str_replace", "edit_file", "replace_string_in_file"), ("edit",)),
    (("view", "read_file", "cat"), ("read",)),
    (("ask_user", "ask_question", "askuserquestion"), ("ask_user",)),
    (("task", "run_subagent", "delegate", "agent"), ("agent_spawn",)),
)
SESSION_PLACEHOLDER = "{session}"

# words that make a matched requirement in reasoning text not an intention
NEGATION = re.compile(r"\b(no|not|without|cannot|can't|won't|don't|never|avoid|"
                      r"instead of|lacks?|unavailable|isn't|aren't)\b", re.IGNORECASE)

# evidence in a tool's output -> runtime fact (kind, value)
OBSERVATIONS = [
    (re.compile(r"(?:^|\n|: )([A-Za-z0-9_.+-]+): command not found"), "program"),
    (re.compile(r"command not found: ([A-Za-z0-9_.+-]+)"), "program"),
    (re.compile(r"No module named '([A-Za-z0-9_.]+)'"), "program"),
    # PowerShell (Windows hosts such as Microsoft Scout)
    (re.compile(r"The term '([A-Za-z0-9_.+-]+)' is not recognized"), "program"),
    (re.compile(r"(Could not resolve host|Network is unreachable|Temporary failure in "
                r"name resolution|getaddrinfo ENOTFOUND)"), "network"),
    (re.compile(r"(\b401\b|\b403\b|[Uu]nauthori[sz]ed|[Aa]uthentication (failed|required)"
                r"|not logged in|[Ii]nvalid (API )?(key|token)|no credentials|"
                r"could not read Username)"), "credential"),
]


REPLAN, ASK_USER = "replan", "ask_user"


@dataclass
class Decision:
    action: str                 # allow | deny | warn
    reason: str = ""
    witness: list = field(default_factory=list)
    next: str = ""              # who can fix a refusal: replan (the agent) | ask_user
    user_needs: list = field(default_factory=list)   # what only the user can provide

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Rule:
    """A prohibited behaviour: a regular expression over plan, reasoning and action
    text, or an effect class / resource / runtime tool a plan must not use."""
    id: str
    description: str
    pattern: str = ""
    effect: str = ""
    resource: str = ""
    runtime_tool: str = ""


@dataclass
class Config:
    """How one project runs the monitor.  `plan_file` and `state_file` may contain the
    placeholder `{session}`, which `for_session` fills with the session id, so that the
    sessions of a hosted agent that share one filesystem do not share one plan."""
    runtime: str = "developer-sandbox"
    plan_file: str = ".skillc/plan.ce"
    state_file: str = ".skillc/state.json"
    thinking: str = "ask"            # ask | stop | warn | off
    max_replans: int = 3             # refused plans in a row before the agent must ask the user
    require_plan: bool = True
    plan_conformance: bool = True    # actions must use a runtime tool the plan binds
    free_tools: tuple = FREE_TOOLS
    tool_map: dict = field(default_factory=lambda: dict(TOOL_MAP))
    plan_tools: tuple = ("Write",)   # tools whose write of the plan file submits the plan
    # sub-agent handoffs (a coordinator's role tools): always allowed, never change state
    agent_tools: tuple = ()
    prohibited: list = field(default_factory=list)   # list[Rule]

    @staticmethod
    def load(path: Path) -> Config:
        d = json.loads(path.read_text(encoding="utf-8"))
        rules = [Rule(**r) for r in d.pop("prohibited", [])]
        for key in ("free_tools", "plan_tools", "agent_tools"):
            if key in d:
                d[key] = tuple(d[key])
        cfg = Config(**d)
        cfg.prohibited = rules
        return cfg

    def dump(self) -> dict:
        d = asdict(self)
        d["free_tools"] = list(self.free_tools)
        d["plan_tools"] = list(self.plan_tools)
        d["agent_tools"] = list(self.agent_tools)
        return d

    def for_session(self, session_id: str | None) -> Config:
        """A copy whose plan and state paths name this session (or "default")."""
        sid = session_id or "default"
        return replace(self, plan_file=self.plan_file.replace(SESSION_PLACEHOLDER, sid),
                       state_file=self.state_file.replace(SESSION_PLACEHOLDER, sid))


@dataclass
class State:
    plan: str | None = None          # approved CE text
    plan_sha: str | None = None
    missing_programs: list = field(default_factory=list)
    missing_resources: list = field(default_factory=list)
    block: str | None = None         # reason actions are held (thinking, revoked plan)
    transcript_offset: int = 0       # legacy single offset; superseded by transcript_offsets
    transcript_offsets: dict = field(default_factory=dict)   # transcript path -> bytes read
    sessions: list = field(default_factory=list)   # sessions already given instructions
    pending: list = field(default_factory=list)    # context to deliver at the next chance
    facts: list = field(default_factory=list)      # predicates currently true (protocol state)
    actions: list = field(default_factory=list)    # capabilities executed successfully, in order
    rejections: int = 0              # plans refused in a row since the last approval
    log: list = field(default_factory=list)


class Monitor:
    """The transport-neutral core: one instance per (project root, session).

    Entry points, each returning a Decision or the context to give the agent:

      on_prompt(prompt, session_id)   the plan instructions once per session, then the
                                      intent check of the user's request
      on_reasoning(text)              reasoning text (alias of observe_thinking)
      pre_action(tool, input, role)   a tool call before it runs
      post_action(tool, input, out, role)   a tool call after it ran
      submit_plan(text)               a plan written through another channel
      load_plan(text)                 a pre-approved plan at startup; resets the facts

    Fail-open contract.  The monitor never raises across an adapter boundary.  The
    methods above only raise on a programming error or an unreadable state file, and
    an adapter must treat any exception as "allow": catch it, write one line to stderr,
    and let the agent's call go through.  A monitor that crashes must not deny every
    tool of the agent, and must not stop the agent by crashing the hook or middleware.
    Decisions the monitor cannot make (an unparsable plan, an unknown tool) are DENY
    with a reason, not exceptions.

    `session_id` fills the `{session}` placeholder of the configured plan and state
    paths (see Config); without one the paths use "default".
    """

    def __init__(self, config: Config, root: Path | str = ".",
                 runtime: Runtime | None = None, library: Library | None = None,
                 session_id: str | None = None):
        self.cfg = config.for_session(session_id)
        self.session_id = session_id
        self.root = Path(root)
        self.runtime = runtime or load_runtime(config.runtime)
        self.library = library or load_library()
        self.state_path = self.root / self.cfg.state_file
        self.state = self._load_state()
        self._plan_cache: tuple[str | None, dict, dict] | None = None   # sha, pack, bindings

    # ------------------------------------------------------------------ state
    def _load_state(self) -> State:
        if self.state_path.exists():
            return State(**json.loads(self.state_path.read_text(encoding="utf-8")))
        return State()

    def save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state.log = self.state.log[-200:]
        temporary = self.state_path.with_name(f"{self.state_path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(asdict(self.state), indent=1), encoding="utf-8")
        os.replace(temporary, self.state_path)

    def _record(self, signal: str, d: Decision, detail: str = "") -> Decision:
        self.state.log.append({"signal": signal, "action": d.action, "reason": d.reason[:500],
                               "detail": detail[:200]})
        return d

    # ------------------------------------------------------------------ runtime facts
    def effective(self) -> tuple[Runtime, Library]:
        """The runtime and library with everything observed during the run applied."""
        rt = self.runtime
        if self.state.missing_resources:
            rt = replace(rt, grants=tuple(g for g in rt.grants
                                          if g not in self.state.missing_resources))
        lib = self.library
        if self.state.missing_programs:
            progs = dict(lib.programs)
            for p in self.state.missing_programs:
                progs[p] = {"status": "unavailable", "why": "observed missing during the run"}
            lib = Library(lib.version, lib.entries, progs)
        return rt, lib

    def _unmet(self, obs: list[Obligation]) -> list[Obligation]:
        rt, lib = self.effective()
        return [o for o in obs if unmet(o, rt, lib)]

    def _prohibited_text(self, text: str) -> list[str]:
        out = []
        for r in self.cfg.prohibited:
            if r.pattern and re.search(r.pattern, text, re.IGNORECASE):
                out.append(f"{r.id}: {r.description}")
        return out

    # ------------------------------------------------------------------ prompt
    def intent_gaps(self, prompt: str) -> str | None:
        """The intent check of a request: requirements the library finds in it that the
        effective runtime cannot meet, as one message for the agent, or None."""
        if not prompt.strip():
            return None
        rt, lib = self.effective()
        gaps = [o for o in match(prompt, lib) if unmet(o, rt, lib)]
        if not gaps:
            return None
        return ("skillc intent check: the request mentions requirements runtime "
                f"`{rt.name}` cannot meet: "
                + "; ".join(f"'{o.text}' ({o.clause()})" for o in gaps)
                + ". Plan around them or tell the user.")

    def on_prompt(self, prompt: str, session_id: str) -> list[str]:
        """Context to give the agent when the user's request arrives: the plan protocol
        the first time this session is seen, then the intent check of the request."""
        ctx = []
        if session_id not in self.state.sessions:
            self.state.sessions.append(session_id)
            ctx.append(plan_instructions(self.runtime, self.cfg.plan_file,
                                         write_tool=self.cfg.plan_tools[0]))
        gap = self.intent_gaps(prompt)
        if gap:
            ctx.append(gap)
        return ctx

    # ------------------------------------------------------------------ plan
    def check_plan(self, text: str) -> tuple[Decision, dict]:
        """Decide a CE plan without changing state: ALLOW only on ACHIEVABLE."""
        info: dict[str, Any] = {}
        try:
            parsed = parse_ce_detailed(text)
        except CEError as e:
            return Decision(DENY, f"the plan does not parse: {e}"), info
        # prohibited behaviours declared in the plan itself
        bad = self._prohibited_text(text)
        for name, b in parsed.bindings.items():
            for r in self.cfg.prohibited:
                if ((r.effect and b.get("effect") == r.effect)
                        or (r.resource and r.resource in (b.get("needs") or []))
                        or (r.runtime_tool and b.get("via") == r.runtime_tool)):
                    bad.append(f"{r.id}: Tool `{name}` — {r.description}")
        if bad:
            return Decision(DENY, "the plan contains prohibited behaviour: " + "; ".join(bad),
                            bad), info
        rt, lib = self.effective()
        try:
            b = bind_runtime(parsed.pack, parsed.bindings, rt, prune=True, library=lib,
                             software=True)
            v = check(b.pack)
        except (CEError, PackError, ValueError) as e:
            return Decision(DENY, f"the plan is not a valid pack: {e}"), info
        info = {"verdict": v.label, "reason": v.reason, "withdrawn": b.withdrawn,
                "blocked": b.blocked, "pruned": b.pruned, "via": sorted({x.get("via") for x in
                                                      parsed.bindings.values() if x.get("via")})}
        if v.label == "ACHIEVABLE":
            skipped = sorted(set(b.withdrawn) | set(b.blocked))
            return Decision(ALLOW, "skillc: plan ACHIEVABLE in runtime "
                                   f"`{rt.name}`; implementation may proceed."
                            + (" Branches using " + ", ".join(f"`{t}`" for t in skipped)
                               + " cannot run here and are excluded: do not take them."
                               if skipped else "")), info
        lines = [f"skillc: plan {v.label} ({v.reason}) in runtime `{rt.name}`."]
        if v.detail:
            lines.append(f"detail: {v.detail}")
        needs: list[str] = []
        for t, why in b.withdrawn.items():
            lines.append(f"Tool `{t}` cannot run here: {why}.")
            if why.startswith(("program:", "software:")):
                needs.append(why.split(" ", 1)[0])
        for t, res in b.blocked.items():
            lines.append(f"Tool `{t}` is blocked: the runtime does not grant "
                         + ", ".join(res) + ".")
            needs += [r for r in res if not r.startswith("policy:")]
        needs = sorted(set(needs))
        if v.label == "IMPOSSIBLE":
            lines.append("Do not implement this plan.")
            lines.append(next_step(needs))
        else:
            lines.append("skillc cannot decide this plan; simplify it or ask the user.")
        return Decision(DENY, "\n".join(lines), sorted(set(b.withdrawn) | set(b.blocked)),
                        next=ASK_USER if needs or v.label != "IMPOSSIBLE" else REPLAN,
                        user_needs=needs), info

    def submit_plan(self, text: str) -> Decision:
        d, info = self.check_plan(text)
        if d.action == ALLOW:
            self.state.plan = text
            self.state.plan_sha = hashlib.sha256(text.encode()).hexdigest()[:16]
            self.state.block = None
            self.state.rejections = 0
        else:
            self.state.rejections += 1
            if self.state.rejections >= self.cfg.max_replans:
                d = replace(d, next=ASK_USER, reason=d.reason + (
                    f"\nskillc has refused {self.state.rejections} plans in a row. Stop "
                    "re-planning: tell the user what skillc found and ask how to proceed."))
        return self._record("plan", d, json.dumps(info)[:200])

    def load_plan(self, text: str) -> Decision:
        """Submit a plan approved before the run (a protocol pack loaded at startup).

        Same decision as `submit_plan`; on ALLOW the protocol state is also set: the facts
        become the pack's `Initially true` predicates and the executed actions are
        cleared.  Loading the plan that is already approved (the same text, as when a
        hosted agent's process restarts within a session) keeps the facts and actions
        recorded so far, so a resumed session continues where it stopped."""
        sha = hashlib.sha256(text.encode()).hexdigest()[:16]
        resumed = self.state.plan is not None and self.state.plan_sha == sha
        d = self.submit_plan(text)
        if d.action == ALLOW and not resumed:
            pack = self.plan_pack() or {}
            self.state.facts = list(pack.get("init_true", []))
            self.state.actions = []
        return d

    def _revoke(self, reason: str) -> None:
        """Hold every further action until a plan that passes is written."""
        self.state.block = reason
        self.state.plan = None
        self.state.plan_sha = None

    def _parsed_plan(self) -> tuple[dict, dict] | None:
        """The approved plan's (pack, bindings), parsed once per plan_sha."""
        if not self.state.plan:
            return None
        if self._plan_cache is None or self._plan_cache[0] != self.state.plan_sha:
            try:
                parsed = parse_ce_detailed(self.state.plan)
            except CEError:
                return None
            self._plan_cache = (self.state.plan_sha, parsed.pack, parsed.bindings)
        return self._plan_cache[1], self._plan_cache[2]

    def plan_pack(self) -> dict | None:
        """The parsed pack of the approved plan (capabilities with owner, pre, add, del;
        protocol; init_true), or None without an approved plan."""
        parsed = self._parsed_plan()
        return parsed[0] if parsed else None

    def _capability(self, tool: str) -> dict | None:
        pack = self.plan_pack()
        cap = (pack or {}).get("capabilities", {}).get(tool)
        return cap if isinstance(cap, dict) else None

    def _capability_via(self, tool: str) -> str | None:
        parsed = self._parsed_plan()
        return (parsed[1].get(tool) or {}).get("via") if parsed else None

    def _plan_via(self) -> set:
        parsed = self._parsed_plan()
        return {b.get("via") for b in parsed[1].values()} if parsed else set()

    # ------------------------------------------------------------------ protocol state
    def _owner_mismatch(self, tool: str, cap: dict, role: str | None) -> str | None:
        owner = cap.get("owner")
        if role and owner not in (None, "?") and owner != role:
            return (f"skillc: `{tool}` is owned by role {owner}, not {role} "
                    "(policy: separation of duties)")
        return None

    def _establishers(self, pred: str) -> str:
        """The Tools of the plan whose `adds` contain `pred`, with their owners."""
        caps = (self.plan_pack() or {}).get("capabilities", {})
        names = [n for n, c in caps.items() if pred in c.get("add", [])]
        if not names:
            return "which no Tool of the plan establishes"
        owners = sorted({caps[n].get("owner", "?") for n in names})
        if len(owners) == 1:
            tools = " or ".join(f"`{n}`" for n in names)
            owner = f" (owner {owners[0]})" if owners[0] != "?" else ""
            text = f"which only {tools}{owner} establish"
        else:
            text = "which only " + " or ".join(
                f"`{n}` (owner {caps[n].get('owner', '?')})" for n in names) + " establish"
        if not any(n in self.state.actions for n in names):
            text += "; none has run"
        return text

    def _unmet_precondition(self, tool: str, cap: dict) -> str | None:
        pre = cap.get("pre", True)
        if eval_formula(pre, self.state.facts) is not False:
            return None
        unmet = unmet_atoms(pre, self.state.facts)
        if unmet:
            parts = [f"`{p}`, {self._establishers(p)}" for p in unmet]
            return f"skillc: `{tool}` requires " + "; and ".join(parts) + "."
        return (f"skillc: `{tool}` requires {render_formula(pre)}, which does not hold "
                "in the protocol state (true now: "
                + (", ".join(f"`{f}`" for f in self.state.facts) or "nothing") + ").")

    def _apply_effects(self, tool: str, cap: dict) -> None:
        facts = [f for f in self.state.facts if f not in cap.get("del", [])]
        facts += [p for p in cap.get("add", []) if p not in facts]
        self.state.facts = facts
        self.state.actions.append(tool)

    # ------------------------------------------------------------------ thinking
    def observe_thinking(self, text: str) -> Decision:
        """Reasoning text: a requirement the runtime cannot meet, or a prohibited
        behaviour, that the agent states as an intention (not negated)."""
        if self.cfg.thinking == "off" or not text.strip():
            return Decision(ALLOW)
        hits, needs = [], []
        lines = text.splitlines()
        for o in self._unmet(match(text, self.library)):
            line = lines[o.line - 1] if 0 < o.line <= len(lines) else ""
            if NEGATION.search(line):
                continue
            hits.append(f"'{o.text}' ({o.clause()}), which runtime "
                        f"`{self.runtime.name}` does not provide")
            if o.kind in USER_KINDS:
                needs.append(o.value)
        for ln in lines:
            if NEGATION.search(ln):
                continue
            hits += self._prohibited_text(ln)
        if not hits:
            return self._record("thinking", Decision(ALLOW))
        found = "\n  - " + "\n  - ".join(sorted(set(hits)))
        needs = sorted(set(needs))
        nxt = ASK_USER if needs else REPLAN
        if self.cfg.thinking == "ask":
            reason = ("skillc question: your reasoning mentions something that cannot be done "
                      "or is prohibited here:" + found + "\nIs this part of what you intend "
                      "to do? If not (you were only weighing it), carry on. If it is, do not "
                      f"act on it: rewrite your plan in `{self.cfg.plan_file}` without it"
                      + (", or ask the user for " + ", ".join(f"`{n}`" for n in needs)
                         if needs else "") + ".")
            return self._record("thinking", Decision(WARN, reason, hits, nxt, needs))
        reason = ("skillc: your reasoning heads towards something that cannot be done or "
                  "is prohibited here:" + found + "\n" + next_step(needs, self.cfg.plan_file))
        if self.cfg.thinking == "stop":
            self._revoke(reason)       # the approved plan no longer describes the intent
            return self._record("thinking", Decision(DENY, reason, hits, nxt, needs))
        return self._record("thinking", Decision(WARN, reason, hits, nxt, needs))

    on_reasoning = observe_thinking

    # ------------------------------------------------------------------ actions
    # tool-input keys of the hook protocols the monitor speaks (Claude Code, Copilot)
    PATH_KEYS = ("file_path", "notebook_path", "path")
    CONTENT_KEYS = ("content", "file_text", "contents", "text")

    @classmethod
    def _action_text(cls, tool_input: dict) -> str:
        keys = ("command", "code", *cls.CONTENT_KEYS, "new_string", "new_str", "url", "query",
                "prompt", *cls.PATH_KEYS)
        return "\n".join(tool_input[k] for k in dict.fromkeys(keys)
                         if isinstance(tool_input.get(k), str))

    @classmethod
    def plan_text(cls, tool_input: dict) -> str:
        return next((tool_input[k] for k in cls.CONTENT_KEYS
                     if isinstance(tool_input.get(k), str)), "")

    def is_plan_file(self, tool_input: dict) -> bool:
        p = next((tool_input[k] for k in self.PATH_KEYS
                  if isinstance(tool_input.get(k), str) and tool_input[k]), "")
        if not p:
            return False
        try:
            return Path(p).resolve() == (self.root / self.cfg.plan_file).resolve()
        except OSError:
            return False

    def pre_action(self, tool: str, tool_input: dict, role: str | None = None) -> Decision:
        """A tool call before it runs.  `role` is the role of the agent making the call,
        when the adapter knows it (one middleware per role agent); a capability owned by
        another role is then refused."""
        if self.is_plan_file(tool_input):
            if tool not in self.cfg.plan_tools:
                return self._record("action", Decision(
                    DENY, f"skillc: write the whole plan with {' or '.join(self.cfg.plan_tools)} "
                          f"to `{self.cfg.plan_file}`."))
            return self.submit_plan(self.plan_text(tool_input))
        if tool in self.cfg.agent_tools:            # a handoff to a sub-agent: its own
            return self._record("action", Decision(ALLOW), tool)   # calls are monitored
        free = tool in self.cfg.free_tools
        if not free and self.state.block:
            return self._record("action", Decision(DENY, self.state.block), tool)
        if not free and self.cfg.require_plan and not self.state.plan:
            return self._record("action", Decision(
                DENY, f"skillc: no approved plan. Before implementing, write your plan in "
                      f"Controlled English to `{self.cfg.plan_file}`; only a plan skillc "
                      "judges ACHIEVABLE can be implemented."), tool)
        cap = self._capability(tool)
        if cap is not None:
            reason = (self._owner_mismatch(tool, cap, role)
                      or self._unmet_precondition(tool, cap))
            if reason:
                return self._record("action", Decision(DENY, reason, [tool]), tool)
        text = self._action_text(tool_input)
        rt_tool = self.cfg.tool_map.get(tool, tool)
        if cap is not None:                         # the plan binds the Tool to its runtime tool
            rt_tool = self._capability_via(tool) or rt_tool
        problems = self._prohibited_text(text)
        needs: list[str] = []
        # Free local helpers (Glob, Grep, ...) have no runtime-vocabulary counterpart, and a
        # Tool of the plan without a `via` is performed by the agent's own code.
        if (rt_tool not in self.runtime.tools
                and not (free and tool not in self.cfg.tool_map)
                and not (cap is not None and self._capability_via(tool) is None)):
            problems.append(f"`{tool}` is not a tool of runtime `{self.runtime.name}`")
        for o in (self._unmet(match(text, self.library)) if text else []):
            problems.append(f"'{o.text}' ({o.clause()}), not available in runtime "
                            f"`{self.runtime.name}`")
            if o.kind in USER_KINDS:
                needs.append(o.value)
        if problems:
            needs = sorted(set(needs))
            reason = ("skillc: action blocked:\n  - " + "\n  - ".join(problems) + "\n"
                      + next_step(needs, self.cfg.plan_file))
            return self._record("action", Decision(DENY, reason, problems,
                                                   ASK_USER if needs else REPLAN, needs), tool)
        if free or cap is not None:                 # a Tool of the plan conforms to the plan
            return self._record("action", Decision(ALLOW), tool)
        if self.cfg.plan_conformance and self.state.plan and rt_tool not in self._plan_via():
            return self._record("action", Decision(
                DENY, f"skillc: `{tool}` (runtime tool `{rt_tool}`) is not used by any Tool "
                      f"of the approved plan. Update `{self.cfg.plan_file}` first."), tool)
        return self._record("action", Decision(ALLOW), tool)

    def post_action(self, tool: str, tool_input: dict, result: Any,
                    role: str | None = None) -> Decision:
        """A tool call after it ran.  A capability of the plan that did not fail (see
        `is_failure`) applies its effects to the protocol state; then failures in the
        output become runtime facts and the plan is re-checked."""
        if tool in self.cfg.agent_tools:
            return self._record("observe", Decision(ALLOW), tool)
        cap = self._capability(tool)
        if (cap is not None and not is_failure(result)
                and self._owner_mismatch(tool, cap, role) is None):
            self._apply_effects(tool, cap)
        out = result if isinstance(result, str) else json.dumps(result, default=str)
        new = self._observe(out, self._action_text(tool_input))
        if not new or not self.state.plan:
            return self._record("observe", Decision(ALLOW), "; ".join(new))
        d, _ = self.check_plan(self.state.plan)
        if d.action == ALLOW:
            return self._record("observe", Decision(
                WARN, "skillc observed: " + "; ".join(new) + ". The approved plan is still "
                      "ACHIEVABLE."), "; ".join(new))
        self._revoke("skillc: the approved plan is no longer achievable after what the "
                     "run showed (" + "; ".join(new) + ").\n" + d.reason)
        needs = sorted(set(d.user_needs) | {n.split("`")[1] for n in new if "`" in n})
        return self._record("observe", Decision(DENY, self.state.block, new, ASK_USER, needs),
                            "; ".join(new))

    def _observe(self, out: str, cmd: str) -> list[str]:
        """Record the runtime facts a tool's output shows; describe the new ones."""
        new = []
        for rx, kind in OBSERVATIONS:
            for m in rx.finditer(out):
                if kind == "program":
                    p = m.group(1).split(".")[0]
                    if p not in self.state.missing_programs:
                        self.state.missing_programs.append(p)
                        new.append(f"program `{p}` is missing")
                elif kind == "network":
                    for r in ("public_internet", "package_registries"):
                        if r not in self.state.missing_resources:
                            self.state.missing_resources.append(r)
                            new.append(f"resource `{r}` is unavailable ({m.group(1)})")
                elif kind == "credential":
                    for o in match(cmd, self.library):
                        if o.kind == "resource" and o.value not in self.state.missing_resources:
                            self.state.missing_resources.append(o.value)
                            new.append(f"credential `{o.value}` was rejected")
        return new


# ---------------------------------------------------------------------- protocol state

def eval_formula(formula: Any, facts: list[str] | set[str] | tuple[str, ...]) -> bool | None:
    """A pack formula (formula.py grammar) under the facts currently true: True, False, or
    None for unknown.  A predicate is true when it is in `facts`; `and`, `or` and `not`
    are three-valued (unknown propagates: an `and` with a False is False, an `and` with an
    unknown and no False is unknown); a comparison is unknown, because the monitor tracks
    no numeric variables; so is any shape the grammar does not define.  Unknown never
    denies: only a formula that evaluates to False refuses an action."""
    if formula is True or formula is False:
        return formula
    if isinstance(formula, str):
        return formula in facts
    if isinstance(formula, dict) and len(formula) == 1:
        if "and" in formula and isinstance(formula["and"], list):
            values = [eval_formula(x, facts) for x in formula["and"]]
            if False in values:
                return False
            return None if None in values else True
        if "or" in formula and isinstance(formula["or"], list):
            values = [eval_formula(x, facts) for x in formula["or"]]
            if True in values:
                return True
            return None if None in values else False
        if "not" in formula:
            v = eval_formula(formula["not"], facts)
            return None if v is None else not v
    return None                                     # cmp, or an undefined shape


def unmet_atoms(formula: Any, facts: list[str] | set[str] | tuple[str, ...]) -> list[str]:
    """The predicates a false formula is waiting for: atoms that occur positively and are
    not in `facts`, in order of appearance.  (A negated atom that is in the facts cannot
    be established by any Tool, so it is not listed.)"""
    out: list[str] = []

    def walk(f: Any, positive: bool) -> None:
        if isinstance(f, str):
            if positive and f not in facts and f not in out:
                out.append(f)
        elif isinstance(f, dict):
            for x in f.get("and", []) + f.get("or", []):
                walk(x, positive)
            if "not" in f:
                walk(f["not"], not positive)

    walk(formula, True)
    return out


def is_failure(result: Any) -> bool:
    """Whether a tool's result means it did not do its work, so that its effects on the
    protocol state must not be applied.  The rule, by result type:

      dict    a key "error" or "skillc" (the monitor's own blocked result);
      str     the first word (case-insensitive, after whitespace, trailing punctuation
              dropped) is one of Error, Rejected, Refused, Failed, Denied, or the text
              starts with "Traceback"; a string that is a JSON object is read as a dict
              (Agent Framework turns a dict return value into its JSON text).

    Everything else, including None and an empty string, is success."""
    if isinstance(result, dict):
        return "error" in result or "skillc" in result
    if isinstance(result, str):
        text = result.lstrip()
        if text.startswith("{"):
            try:
                parsed = json.loads(text)
            except ValueError:
                parsed = None
            if isinstance(parsed, dict):
                return is_failure(parsed)
        if text.startswith("Traceback"):
            return True
        first = text.split(None, 1)[0] if text else ""
        return first.rstrip(":.,;!").lower() in FAILURE_WORDS
    return False


# ---------------------------------------------------------------------- refusals

# obligation kinds only the user can satisfy: an account or credential, a program to install
USER_KINDS = ("resource", "program")


def next_step(user_needs: list[str], plan_file: str = "") -> str:
    """The last line of a refusal: who can fix it, and how."""
    where = f" in `{plan_file}`" if plan_file else ""
    if user_needs:
        return ("Only the user can provide " + ", ".join(f"`{n}`" for n in user_needs)
                + " (access, sign-in or installation); re-planning cannot create it. Ask the "
                f"user for it, or rewrite the plan{where} to a route that does not need it.")
    return (f"You can fix this: rewrite the plan{where} so that it avoids this (make optional "
            "work skippable, or use a runtime tool that really performs the step), then "
            "continue.")


# ---------------------------------------------------------------------- tool map

def tool_map_from_names(names: list[str] | tuple[str, ...], runtime: Runtime) -> dict[str, str]:
    """A Config.tool_map for an agent that exposes `names`, in the vocabulary of `runtime`.

    A name that is (ignoring case) a tool of the runtime maps to that tool.  Otherwise
    the alias table TOOL_ALIASES is consulted, and a name ending in `_search` stands
    for `search`.  A name maps only when the runtime has the target tool; every other
    name is left out, so that pre_action denies it as not a tool of this runtime.
    """
    by_lower = {t.lower(): t for t in runtime.tools}
    aliases = {alias: targets for group, targets in TOOL_ALIASES for alias in group}
    out: dict[str, str] = {}
    for name in names:
        key = name.lower()
        if key in by_lower:
            out[name] = by_lower[key]
            continue
        targets = aliases.get(key, ())
        if not targets and key.endswith("_search"):
            targets = ("search",)
        for target in targets:
            if target in runtime.tools:
                out[name] = target
                break
    return out


# ---------------------------------------------------------------------- instructions

def plan_instructions(runtime: Runtime, plan_file: str, write_tool: str = "Write") -> str:
    """What the agent is told once per session: the plan protocol and the CE grammar."""
    return (
        "SKILLC RUNTIME MONITOR is active. Before you implement anything (run commands, "
        f"write or edit files), write your plan to `{plan_file}` with the {write_tool} tool, in "
        "SkillC Controlled English (CE): one Tool per operation that changes the world or "
        "reaches beyond the conversation, bound with 'via' to the RUNTIME tool that "
        "performs it; 'needs' for any account, credential or paid service; 'runs' for "
        "specific software; 'effect' (local, reads_external, writes_external, publishes); "
        "optional work in a 'chooses one of (observed)' with a branch that skips it. The "
        "write is accepted only if skillc judges the plan ACHIEVABLE in this runtime; "
        "otherwise the refusal tells you why. Actions outside the approved plan, actions "
        "needing what the runtime lacks, and prohibited behaviour are blocked. If you "
        "change course, rewrite the plan first. If no achievable plan exists, stop and tell "
        "the user what is missing.\n" + CE_DOC + CE_RUNTIME_DOC + CE_SOFTWARE_DOC
        + runtime_note(runtime))


@contextmanager
def state_lock(state_path: Path, timeout: float = 30.0) -> Iterator[None]:
    """Exclusive inter-process lock for one project's monitor state.

    Hooks run in parallel, so each load/handle/save must be one transaction;
    otherwise a stale writer can undo a revoked plan."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    with open(state_path.with_name(state_path.name + ".lock"), "a+b") as handle:
        while True:
            try:
                _lock(handle)
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise TimeoutError(f"monitor state is locked: {state_path}") from None
                time.sleep(0.05)
        try:
            yield
        finally:
            _unlock(handle)


if sys.platform == "win32":
    import msvcrt

    def _lock(handle) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)

    def _unlock(handle) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _lock(handle) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock(handle) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def thinking_since(transcript: Path, offset: int) -> tuple[str, int]:
    """Assistant reasoning text (thinking blocks, visible text) appended to a Claude Code
    transcript (JSONL) since `offset` bytes; returns (text, new offset). A transcript
    shorter than `offset` was replaced or truncated, so it is read from the start. A
    trailing record the writer has not finished is left unread for the next call."""
    if not transcript.exists():
        return "", offset
    if offset > transcript.stat().st_size:
        offset = 0
    with transcript.open("rb") as f:
        f.seek(offset)
        data = f.read()
    complete, _, tail = data.rpartition(b"\n")
    records = complete.split(b"\n")
    if tail and _is_json(tail):
        records.append(tail)
        consumed = len(data)
    else:
        consumed = len(data) - len(tail)
    parts = []
    for line in (r.decode("utf-8", "replace") for r in records):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        msg = d.get("message") if isinstance(d.get("message"), dict) else d
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        if isinstance(msg.get("content"), str):
            if msg["content"]:
                parts.append(msg["content"])
            continue
        if not isinstance(msg.get("content"), list):
            continue
        for b in msg["content"]:
            if isinstance(b, dict) and b.get("type") == "thinking" and b.get("thinking"):
                parts.append(b["thinking"])
            elif isinstance(b, dict) and b.get("type") == "text" and b.get("text"):
                parts.append(b["text"])
    return "\n".join(parts), offset + consumed


def _is_json(raw: bytes) -> bool:
    try:
        json.loads(raw.decode("utf-8"))
    except ValueError:
        return False
    return True

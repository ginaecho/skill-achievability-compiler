"""Runtime monitor: skillc stays active while an agent thinks and acts.

The check before the run (intent -> logical block -> verdict) is repeated during the run,
on three signals (docs/RUNTIME_MONITOR.md):

  plan      the agent writes its intended steps as Controlled English (a plan file).
            Only a plan the checker judges ACHIEVABLE under the runtime, with no
            prohibited behaviour, is approved; implementation is gated on it.
  thinking  the agent's reasoning text (thinking summaries, progress notes, visible
            text), scanned deterministically with the tool-policy library: a requirement
            the runtime cannot meet, or a prohibited behaviour, blocks further actions
            until a plan that passes is written.
  action    every tool call, before it runs: it needs an approved plan, must use a
            runtime tool the plan binds, and must not show an unmet requirement or a
            prohibited behaviour.  After it runs, failures in its output (a missing
            program, a rejected credential, no network) become runtime facts and the
            approved plan is re-checked from them; a plan that becomes IMPOSSIBLE is
            revoked.

Everything here is deterministic and costs zero model tokens.  The state lives in one
JSON file so that separate hook processes share it.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .checker import check
from .frontend.ce import CEError, parse_ce_detailed
from .frontend.runtime import Runtime, bind_runtime, load_runtime
from .frontend.toolpolicy import Library, Obligation, load_library, match
from .pack import PackError

ALLOW, DENY, WARN = "allow", "deny", "warn"

# Claude Code tool -> runtime tool (the vocabulary of the runtime manifests)
TOOL_MAP = {"Bash": "bash", "Write": "write", "Edit": "edit", "MultiEdit": "edit",
            "NotebookEdit": "edit", "Read": "read", "WebFetch": "web_fetch",
            "WebSearch": "web_search", "Task": "agent_spawn", "Agent": "agent_spawn"}
# tools that only look around: allowed before a plan exists (planning needs them)
FREE_TOOLS = ("Read", "Glob", "Grep", "LS", "WebSearch", "TodoWrite", "ToolSearch")

# words that make a matched requirement in reasoning text not an intention
NEGATION = re.compile(r"\b(no|not|without|cannot|can't|won't|don't|never|avoid|"
                      r"instead of|lacks?|unavailable|isn't|aren't)\b", re.IGNORECASE)

# evidence in a tool's output -> runtime fact (kind, value)
OBSERVATIONS = [
    (re.compile(r"(?:^|\n|: )([A-Za-z0-9_.+-]+): command not found"), "program"),
    (re.compile(r"command not found: ([A-Za-z0-9_.+-]+)"), "program"),
    (re.compile(r"No module named '([A-Za-z0-9_.]+)'"), "program"),
    (re.compile(r"(Could not resolve host|Network is unreachable|Temporary failure in "
                r"name resolution|getaddrinfo ENOTFOUND)"), "network"),
    (re.compile(r"(\b401\b|\b403\b|[Uu]nauthori[sz]ed|[Aa]uthentication (failed|required)"
                r"|not logged in|[Ii]nvalid (API )?(key|token)|no credentials|"
                r"could not read Username)"), "credential"),
]


@dataclass
class Decision:
    action: str                 # allow | deny | warn
    reason: str = ""
    witness: list = field(default_factory=list)

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
    runtime: str = "developer-sandbox"
    plan_file: str = ".skillc/plan.ce"
    state_file: str = ".skillc/state.json"
    thinking: str = "stop"           # stop | warn | off
    require_plan: bool = True
    plan_conformance: bool = True    # actions must use a runtime tool the plan binds
    free_tools: tuple = FREE_TOOLS
    tool_map: dict = field(default_factory=lambda: dict(TOOL_MAP))
    prohibited: list = field(default_factory=list)   # list[Rule]

    @staticmethod
    def load(path: Path) -> "Config":
        d = json.loads(path.read_text(encoding="utf-8"))
        rules = [Rule(**r) for r in d.pop("prohibited", [])]
        if "free_tools" in d:
            d["free_tools"] = tuple(d["free_tools"])
        cfg = Config(**d)
        cfg.prohibited = rules
        return cfg

    def dump(self) -> dict:
        d = asdict(self)
        d["free_tools"] = list(self.free_tools)
        return d


@dataclass
class State:
    plan: str | None = None          # approved CE text
    plan_sha: str | None = None
    missing_programs: list = field(default_factory=list)
    missing_resources: list = field(default_factory=list)
    block: str | None = None         # reason actions are held (thinking, revoked plan)
    transcript_offset: int = 0
    sessions: list = field(default_factory=list)   # sessions already given instructions
    log: list = field(default_factory=list)


class Monitor:
    def __init__(self, config: Config, root: Path | str = ".",
                 runtime: Runtime | None = None, library: Library | None = None):
        self.cfg = config
        self.root = Path(root)
        self.runtime = runtime or load_runtime(config.runtime)
        self.library = library or load_library()
        self.state_path = self.root / config.state_file
        self.state = self._load_state()

    # ------------------------------------------------------------------ state
    def _load_state(self) -> State:
        if self.state_path.exists():
            return State(**json.loads(self.state_path.read_text(encoding="utf-8")))
        return State()

    def save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state.log = self.state.log[-200:]
        self.state_path.write_text(json.dumps(asdict(self.state), indent=1), encoding="utf-8")

    def _record(self, signal: str, d: Decision, detail: str = "") -> Decision:
        self.state.log.append({"signal": signal, "action": d.action, "reason": d.reason[:500],
                               "detail": detail[:200]})
        return d

    # ------------------------------------------------------------------ runtime facts
    def _effective(self) -> tuple[Runtime, Library]:
        """The runtime and library with everything observed during the run applied."""
        rt = self.runtime
        if self.state.missing_resources:
            rt = Runtime(rt.name, rt.description, rt.tools,
                         tuple(g for g in rt.grants if g not in self.state.missing_resources),
                         rt.lacks, rt.forbid_effects, rt.software)
        lib = self.library
        if self.state.missing_programs:
            progs = dict(lib.programs)
            for p in self.state.missing_programs:
                progs[p] = {"status": "unavailable", "why": "observed missing during the run"}
            lib = Library(lib.version, lib.entries, progs)
        return rt, lib

    def _unmet(self, obs: list[Obligation]) -> list[Obligation]:
        rt, lib = self._effective()
        from .frontend.toolpolicy import unmet
        return [o for o in obs if unmet(o, rt, lib)]

    def _prohibited_text(self, text: str) -> list[str]:
        out = []
        for r in self.cfg.prohibited:
            if r.pattern and re.search(r.pattern, text, re.IGNORECASE):
                out.append(f"{r.id}: {r.description}")
        return out

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
        rt, lib = self._effective()
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
        for t, why in b.withdrawn.items():
            lines.append(f"Tool `{t}` cannot run here: {why}.")
        for t, res in b.blocked.items():
            lines.append(f"Tool `{t}` is blocked: the runtime does not grant "
                         + ", ".join(res) + ".")
        if v.label == "IMPOSSIBLE":
            lines.append("Do not implement this. Either change the plan to one that the "
                         "runtime can carry out (make optional work skippable, use a runtime "
                         "tool that really performs the step) or stop and tell the user "
                         "what is missing.")
        else:
            lines.append("skillc cannot decide this plan; simplify it or ask the user.")
        return Decision(DENY, "\n".join(lines),
                        sorted(set(b.withdrawn) | set(b.blocked))), info

    def submit_plan(self, text: str) -> Decision:
        d, info = self.check_plan(text)
        if d.action == ALLOW:
            self.state.plan = text
            self.state.plan_sha = hashlib.sha256(text.encode()).hexdigest()[:16]
            self.state.block = None
        return self._record("plan", d, json.dumps(info)[:200])

    def _plan_via(self) -> set:
        if not self.state.plan:
            return set()
        try:
            return {b.get("via") for b in parse_ce_detailed(self.state.plan).bindings.values()}
        except CEError:
            return set()

    # ------------------------------------------------------------------ thinking
    def observe_thinking(self, text: str) -> Decision:
        """Reasoning text: a requirement the runtime cannot meet, or a prohibited
        behaviour, that the agent states as an intention (not negated)."""
        if self.cfg.thinking == "off" or not text.strip():
            return Decision(ALLOW)
        hits = []
        lines = text.splitlines()
        for o in self._unmet(match(text, self.library)):
            line = lines[o.line - 1] if 0 < o.line <= len(lines) else ""
            if NEGATION.search(line):
                continue
            hits.append(f"'{o.text}' needs {o.clause()}, which runtime "
                        f"`{self.runtime.name}` does not provide")
        for ln in lines:
            if NEGATION.search(ln):
                continue
            hits += self._prohibited_text(ln)
        if not hits:
            return self._record("thinking", Decision(ALLOW))
        reason = ("skillc: your reasoning heads towards something that cannot be done or "
                  "is prohibited here:\n  - " + "\n  - ".join(sorted(set(hits)))
                  + f"\nWrite a plan that avoids it to `{self.cfg.plan_file}` (it must pass "
                    "skillc), or stop and tell the user.")
        if self.cfg.thinking == "stop":
            self.state.block = reason
            self.state.plan = None     # the approved plan no longer describes the intent
            self.state.plan_sha = None
            return self._record("thinking", Decision(DENY, reason, hits))
        return self._record("thinking", Decision(WARN, reason, hits))

    # ------------------------------------------------------------------ actions
    def _action_text(self, tool: str, tool_input: dict) -> str:
        keys = ("command", "content", "new_string", "url", "query", "prompt", "file_path")
        return "\n".join(str(tool_input[k]) for k in keys if isinstance(tool_input.get(k), str))

    def _is_plan_file(self, tool_input: dict) -> bool:
        p = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        if not p:
            return False
        try:
            return Path(p).resolve() == (self.root / self.cfg.plan_file).resolve()
        except OSError:
            return False

    def pre_action(self, tool: str, tool_input: dict) -> Decision:
        if self._is_plan_file(tool_input):
            if tool != "Write":
                return self._record("action", Decision(
                    DENY, f"skillc: write the whole plan with Write to `{self.cfg.plan_file}`."))
            return self.submit_plan(tool_input.get("content", ""))
        if tool in self.cfg.free_tools:
            return self._record("action", Decision(ALLOW), tool)
        if self.state.block:
            return self._record("action", Decision(DENY, self.state.block), tool)
        if self.cfg.require_plan and not self.state.plan:
            return self._record("action", Decision(
                DENY, f"skillc: no approved plan. Before implementing, write your plan in "
                      f"Controlled English to `{self.cfg.plan_file}`; only a plan skillc "
                      "judges ACHIEVABLE can be implemented."), tool)
        text = self._action_text(tool, tool_input)
        bad = self._prohibited_text(text)
        unmet = self._unmet(match(text, self.library)) if text else []
        rt_tool = self.cfg.tool_map.get(tool, tool)
        if rt_tool not in self.runtime.tools and tool not in self.cfg.free_tools:
            unmet_msg = [f"`{tool}` is not a tool of runtime `{self.runtime.name}`"]
        else:
            unmet_msg = []
        unmet_msg += [f"'{o.text}' needs {o.clause()}, not available in runtime "
                      f"`{self.runtime.name}`" for o in unmet]
        if bad or unmet_msg:
            reason = "skillc: action blocked:\n  - " + "\n  - ".join(bad + unmet_msg)
            return self._record("action", Decision(DENY, reason, bad + unmet_msg), tool)
        if self.cfg.plan_conformance and self.state.plan and rt_tool not in self._plan_via():
            return self._record("action", Decision(
                DENY, f"skillc: `{tool}` (runtime tool `{rt_tool}`) is not used by any Tool "
                      f"of the approved plan. Update `{self.cfg.plan_file}` first."), tool)
        return self._record("action", Decision(ALLOW), tool)

    def post_action(self, tool: str, tool_input: dict, result: Any) -> Decision:
        """Turn failures in a tool's output into runtime facts; re-check the plan."""
        out = result if isinstance(result, str) else json.dumps(result, default=str)
        cmd = self._action_text(tool, tool_input)
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
        if not new or not self.state.plan:
            return self._record("observe", Decision(ALLOW), "; ".join(new))
        d, _ = self.check_plan(self.state.plan)
        if d.action == ALLOW:
            return self._record("observe", Decision(
                WARN, "skillc observed: " + "; ".join(new) + ". The approved plan is still "
                      "ACHIEVABLE."), "; ".join(new))
        self.state.block = ("skillc: the approved plan is no longer achievable after what the "
                            "run showed (" + "; ".join(new) + ").\n" + d.reason)
        self.state.plan = None
        self.state.plan_sha = None
        return self._record("observe", Decision(DENY, self.state.block, new), "; ".join(new))


# ---------------------------------------------------------------------- instructions

def plan_instructions(runtime: Runtime, plan_file: str) -> str:
    """What the agent is told once per session: the plan protocol and the CE grammar."""
    from .frontend.llm import CE_DOC, CE_RUNTIME_DOC, CE_SOFTWARE_DOC
    from .frontend.runtime import runtime_note
    return (
        "SKILLC RUNTIME MONITOR is active. Before you implement anything (run commands, "
        f"write or edit files), write your plan to `{plan_file}` with the Write tool, in "
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


def thinking_since(transcript: Path, offset: int) -> tuple[str, int]:
    """Assistant reasoning text (thinking blocks, visible text) appended to a Claude Code
    transcript (JSONL) since `offset` bytes; returns (text, new offset)."""
    if not transcript.exists():
        return "", offset
    with transcript.open("rb") as f:
        f.seek(offset)
        data = f.read()
    parts = []
    for line in data.decode("utf-8", "replace").splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        msg = d.get("message") or {}
        if msg.get("role") != "assistant" or not isinstance(msg.get("content"), list):
            continue
        for b in msg["content"]:
            if isinstance(b, dict) and b.get("type") == "thinking" and b.get("thinking"):
                parts.append(b["thinking"])
            elif isinstance(b, dict) and b.get("type") == "text" and b.get("text"):
                parts.append(b["text"])
    return "\n".join(parts), offset + len(data)

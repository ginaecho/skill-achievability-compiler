"""The deploy gate: `skillc gate DIR` decides, offline and without a model call,
whether an azd project's protocol packs and skills are achievable in the
environment its azure.yaml declares.  It is meant to run as the `predeploy`
hook of `azd deploy`, the only moment a hosted agent version is created.

    declared environment     from_azure_yaml(azure.yaml), merged with an observed
                             probe (`--env`) when one exists; observed facts win
    effective runtime        the runtime manifest (foundry-hosted by default) with
                             every tool the declaration cannot supply withdrawn
    protocol/*.ce            the pure check, then the runtime-bound check exactly as
                             Monitor.check_plan binds it; with several agents, the
                             A2A topology every `A tells B` message needs
    skills                   every intent artifact of the project: its needs through
                             the natural-language front-end and `reach`, and every
                             frontmatter `tools:` name against the declared tools

The effective runtime keeps a manifest tool only if the declaration supplies it:

    runtime tool        kept when the declaration has
    code_interpreter    a toolbox tool of type `code_interpreter`
    web_search          a toolbox tool of type `web_search`
    search              a toolbox tool of type `azure_ai_search`
    mcp                 a toolbox tool of type `mcp`
    openapi             a toolbox tool of type `openapi`
    a2a                 a toolbox tool of type `a2a`
    read, write         always (the sandbox $HOME)
    web_fetch           always; under network isolation only as an assumption
    anything else       kept as the manifest states it (outside this table)

A toolbox tool counts only if an `azure.ai.agent` references the toolbox; with
at most one agent declared, that agent owns every toolbox.  A withdrawn tool
is reported with the azure.yaml edit that would restore it.

With `--compact` the gate first compacts the project's own documents (the skills
it reads, plus a `COORDINATOR_INSTRUCTIONS` constant in `src/**/main.py`) into
`protocol/compacted_s<k>.ce` with the P2g+ prompt and the EFFECTIVE runtime
(`compact_project`, one model call per round), then gates those packs in place of
the authored `protocol/*.ce` and reports the authored packs' labels next to them.
Without `--compact` no model is called and `compacted_*.ce` files are ignored.

Declared facts are taken at their word here: the gate refuses only what the
declaration already rules out, and a probe (`--env`) replaces declarations by
observations.  Exit codes: 0 every item ACHIEVABLE, 1 something IMPOSSIBLE,
4 nothing impossible but a protocol is REJECTED (the goal is reachable, but
the coordination can deadlock or a path uses a missing tool -- a typing
failure, not a goal refutation),
3 nothing impossible or rejected but something rests on an assumption,
2 an error.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml

from .checker import check
from .env.azd import AzdError, from_azure_yaml, intent_artifacts
from .env.facts import tools_matching
from .env.manifest import REASON as REQUIREMENT_UNAVAILABLE
from .env.manifest import manifest_facts, refute_text, witness_lines
from .env.model import Environment, merge
from .env.nl import intent_from_text
from .env.reach import reach
from .frontend.ce import CEError, parse_ce_detailed
from .frontend.runtime import Runtime, RuntimeManifestError, bind_runtime, load_runtime
from .frontend.toolpolicy import load_library
from .pack import PackError

ACHIEVABLE, UNKNOWN, IMPOSSIBLE = "ACHIEVABLE", "UNKNOWN", "IMPOSSIBLE"
# a protocol-typing rejection: does not pass, but is not a goal refutation
REJECTED = "REJECTED"
EXIT_CODES = {ACHIEVABLE: 0, IMPOSSIBLE: 1, UNKNOWN: 3, REJECTED: 4}
REPORT_SCHEMA = "skillc.gate/1"

# runtime tool -> the toolbox tool type that supplies it
TOOLBOX_TYPES = {"code_interpreter": "code_interpreter", "web_search": "web_search",
                 "search": "azure_ai_search", "mcp": "mcp", "openapi": "openapi", "a2a": "a2a"}
SANDBOX_TOOLS = ("read", "write")
EGRESS_TOOLS = ("web_fetch", "web_search")   # public egress: unknown under network isolation
A2A_SUFFIX = "/agents/{agent}/endpoint/protocols/a2a"

HOOK_SNIPPET = """hooks:
  predeploy:
    shell: sh
    run: skillc gate . --declared azure.yaml
"""


class GateError(ValueError):
    """The project could not be gated (a file does not parse, a runtime is unknown)."""


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------

@dataclass
class Entry:
    """One gated item: a protocol pack, a skill, or a topology edge."""
    kind: str                     # pack | skill | topology
    name: str
    verdict: str
    reason: str
    fixes: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"kind": self.kind, "name": self.name, "verdict": self.verdict,
                "reason": self.reason, "fixes": self.fixes, "assumptions": self.assumptions,
                **self.detail}


@dataclass
class GateReport:
    project: str
    declared: str
    observed: str | None
    runtime: str
    runtime_tools: list[str]
    withdrawn_runtime_tools: dict[str, str]
    runtime_assumptions: dict[str, str]
    packs: list[Entry]
    skills: list[Entry]
    topology: list[Entry]
    topology_note: str
    # with --compact: the authored protocol/*.ce packs, reported next to the
    # compacted ones (which are `packs`); informational, they do not decide the gate
    authored: list[Entry] = field(default_factory=list)
    compaction: list[dict] = field(default_factory=list)

    @property
    def entries(self) -> list[Entry]:
        return [*self.packs, *self.skills, *self.topology]

    @property
    def impossible(self) -> list[Entry]:
        return [e for e in self.entries if e.verdict == IMPOSSIBLE]

    @property
    def verdict(self) -> str:
        if self.impossible:
            return IMPOSSIBLE
        if any(e.verdict == REJECTED for e in self.entries):
            return REJECTED
        if any(e.verdict == UNKNOWN for e in self.entries):
            return UNKNOWN
        return ACHIEVABLE

    @property
    def exit_code(self) -> int:
        return EXIT_CODES[self.verdict]

    def to_dict(self) -> dict:
        out = self._to_dict()
        if self.authored or self.compaction:
            out["authored_packs"] = [e.to_dict() for e in self.authored]
            out["compaction"] = self.compaction
        return out

    def _to_dict(self) -> dict:
        return {
            "schema": REPORT_SCHEMA,
            "project": self.project,
            "declared": self.declared,
            "observed": self.observed,
            "runtime": self.runtime,
            "runtime_tools": self.runtime_tools,
            "withdrawn_runtime_tools": self.withdrawn_runtime_tools,
            "runtime_assumptions": self.runtime_assumptions,
            "packs": [e.to_dict() for e in self.packs],
            "skills": [e.to_dict() for e in self.skills],
            "topology": [e.to_dict() for e in self.topology],
            "topology_note": self.topology_note,
            "verdict": self.verdict,
            "exit": self.exit_code,
        }

    def render(self) -> str:
        lines = [f"runtime {self.runtime} (declared {self.declared}"
                 + (f", observed {self.observed}" if self.observed else "")
                 + "): " + ", ".join(self.runtime_tools)]
        for tool, why in self.withdrawn_runtime_tools.items():
            lines.append(f"  withdrawn {tool}: {why}")
        for tool, why in self.runtime_assumptions.items():
            lines.append(f"  assumed {tool}: {why}")
        for e in [*self.packs, *self.skills]:
            lines.append(f"{e.kind} {e.name}: {e.verdict} {e.reason}".rstrip())
            lines += [f"    fix: {f}" for f in e.fixes]
            lines += [f"    assuming: {a}" for a in e.assumptions]
        if self.compaction:
            for c in self.compaction:
                lines.append(f"compacted sample s{c['sample']}: "
                             + (c.get("label") or f"ERROR {c.get('error')}"))
            for e in self.authored:
                lines.append(f"authored {e.name}: {e.verdict} {e.reason}".rstrip())
        if self.topology_note:
            lines.append(f"topology: {self.topology_note}")
        for e in self.topology:
            lines.append(f"topology {e.name}: {e.verdict} {e.reason}")
            lines += [f"    fix: {f}" for f in e.fixes]
            lines += [f"    assuming: {a}" for a in e.assumptions]
        lines.append(f"gate: {self.verdict}")
        return "\n".join(lines)


# --------------------------------------------------------------------------
# The effective runtime
# --------------------------------------------------------------------------

@dataclass
class EffectiveRuntime:
    runtime: Runtime
    withdrawn: dict[str, str]        # manifest tool -> why it is gone
    assumptions: dict[str, str]      # manifest tool -> why it is kept only as an assumption
    tools: list[dict]                # declared tool nodes the agents can reach

    def fix_for(self, tool: str) -> str:
        """The azure.yaml edit that restores a withdrawn tool."""
        return self.withdrawn[tool].split(": ", 1)[-1]


def _owned_tools(env: Environment) -> list[dict]:
    """Tool nodes of the toolboxes some declared agent references (every toolbox
    when at most one agent is declared)."""
    agents = [n for n in env.of_kind("principal") if n["attrs"].get("type") == "agent"]
    used = {t for a in agents for t in a["attrs"].get("toolboxes") or []}
    out = []
    for box in env.of_kind("mcp_server"):
        if box["attrs"].get("transport") != "toolbox":
            continue
        if len(agents) > 1 and box["name"] not in used:
            continue
        for edge in env.out_edges(box["id"], "exposes"):
            node = env.nodes.get(edge["dst"])
            if node is not None and node["attrs"].get("available", True) is not False:
                out.append(node)
    return out


def effective_runtime(manifest: Runtime, env: Environment) -> EffectiveRuntime:
    """The manifest reduced to the tools the declared environment supplies."""
    owned = _owned_tools(env)
    types = {str(t["attrs"].get("type") or t["name"]).lower() for t in owned}
    egress = env.nodes.get("egress/public")
    isolated = bool(egress and egress["attrs"].get("isolated"))
    tools, withdrawn, assumptions = {}, {}, {}
    for name, description in manifest.tools.items():
        if name in TOOLBOX_TYPES and TOOLBOX_TYPES[name] not in types:
            withdrawn[name] = (f"not declared in azure.yaml: add `{TOOLBOX_TYPES[name]}` "
                               "to a toolbox the agent uses")
            continue
        if name in EGRESS_TOOLS and isolated:
            assumptions[name] = ("network-isolated project ("
                                 f"{egress['attrs'].get('mode')}): public egress is unknown "
                                 "until probed from inside the sandbox")
        tools[name] = description
    return EffectiveRuntime(replace(manifest, tools=tools), withdrawn, assumptions, owned)


# --------------------------------------------------------------------------
# Protocol packs
# --------------------------------------------------------------------------

def _pack_entry(path: Path, eff: EffectiveRuntime, library) -> tuple[Entry, dict]:
    text = path.read_text(encoding="utf-8")
    try:
        parsed = parse_ce_detailed(text)
    except CEError as e:
        raise GateError(f"{path.name}: {e}") from None
    pure = check(parsed.pack)
    try:
        bound = bind_runtime(parsed.pack, parsed.bindings, eff.runtime, prune=True,
                             library=library, software=True)
        verdict = check(bound.pack)
    except (CEError, PackError, ValueError) as e:
        raise GateError(f"{path.name}: {e}") from None
    via = sorted({b.get("via") for b in parsed.bindings.values() if b.get("via")})
    reasons, fixes = [], []
    for tool, why in bound.withdrawn.items():
        # bind_runtime withdraws before it looks at `needs`; a resource the runtime does
        # not grant is the deeper blocker, so it is named first
        needs = [r for r in (parsed.bindings.get(tool) or {}).get("needs") or []
                 if r not in eff.runtime.grants]
        if needs:
            listed = ", ".join(f"`{r}`" for r in needs)
            reasons.append(f"Tool `{tool}` needs {listed}, which the runtime does not grant")
            fixes.append(f"declare in azure.yaml a connection that provides {listed} for "
                         f"`{tool}`, or make the step skippable")
        if why in eff.withdrawn:
            reasons.append(f"Tool `{tool}` cannot run here: `{why}` is not declared in "
                           "azure.yaml")
            fixes.append(eff.fix_for(why))
        elif why.startswith(("software:", "program:")):
            reasons.append(f"Tool `{tool}` cannot run here: {why}")
            fixes.append(f"make `{tool}` skippable or drop the software it runs")
        else:
            reasons.append(f"Tool `{tool}` cannot run here: runtime `{eff.runtime.name}` "
                           f"has no `{why}` tool")
            fixes.append(f"bind `{tool}` to one of: {', '.join(sorted(eff.runtime.tools))}")
    for tool, resources in bound.blocked.items():
        listed = ", ".join(f"`{r}`" for r in resources)
        reasons.append(f"Tool `{tool}` is blocked: the runtime does not grant {listed}")
        fixes.append(f"declare in azure.yaml a connection that provides {listed} for "
                     f"`{tool}`, or make the step skippable")
    assumptions = [f"`{t}`: {eff.assumptions[t]}" for t in via if t in eff.assumptions]
    label = verdict.label
    if pure.refuted:
        reason = f"the pack itself is IMPOSSIBLE ({pure.reason}): {pure.detail}".rstrip(": ")
        fixes = ["repair the protocol before binding it to a runtime"]
    elif label == ACHIEVABLE and verdict.protocol == "REJECTED":
        label = REJECTED
        reason = (f"protocol rejected ({verdict.protocol_reason}): "
                  f"{verdict.protocol_detail}; goal reachable along witness; "
                  "this is not a goal-impossibility claim (the goal is not refuted)")
        if reasons:
            reason += "; " + "; ".join(reasons)
        if bound.pruned:
            reason += "; pruned " + ", ".join(bound.pruned)
        fixes = fixes + ["rewrite the protocol so every role can observe the branch it "
                         "must act in, and every declared role behaviour refines its "
                         "projection"]
    elif label == ACHIEVABLE:
        skipped = sorted(set(bound.withdrawn) | set(bound.blocked))
        reason = "via " + ", ".join(via)
        if skipped:
            reason += ("; branches using " + ", ".join(f"`{t}`" for t in skipped)
                       + " cannot run here and are excluded")
        fixes = []
        if assumptions:
            label = UNKNOWN
    elif label == IMPOSSIBLE:
        reason = f"{verdict.reason}: " + ("; ".join(reasons) if reasons else verdict.detail)
        if bound.pruned:
            reason += "; pruned " + ", ".join(bound.pruned)
        if verdict.protocol == "REJECTED":
            reason += (f"; protocol also rejected ({verdict.protocol_reason}): "
                       f"{verdict.protocol_detail}")
    else:
        reason = f"{verdict.reason}: {verdict.detail}".rstrip(": ")
        assumptions.append(f"the checker could not decide this pack: {verdict.reason}")
    entry = Entry("pack", path.name, label, reason, list(dict.fromkeys(fixes)), assumptions,
                  {"pure_verdict": pure.label, "bound_verdict": verdict.label,
                   "bound_reason": verdict.reason, "bound_protocol": verdict.protocol,
                   "bound_protocol_reason": verdict.protocol_reason,
                   "via": via, "withdrawn": bound.withdrawn,
                   "blocked": bound.blocked, "pruned": bound.pruned})
    return entry, parsed.pack


# --------------------------------------------------------------------------
# Skills
# --------------------------------------------------------------------------

def _tool_declared(name: str, env: Environment, eff: EffectiveRuntime) -> bool:
    """Whether a frontmatter tool name is a toolbox tool the agent can reach or
    a tool of the effective runtime."""
    if name.lower() in {t.lower() for t in eff.runtime.tools}:
        return True
    owned = {t["id"] for t in eff.tools}
    for tool in tools_matching(env, [f"^{re.escape(name)}$"]):
        if tool["id"] in owned:
            return True
    return any(str(t["attrs"].get("tool_name") or "").lower() == name.lower() for t in eff.tools)


def _without_tools(intent: dict) -> dict:
    """The intent minus its frontmatter `tool:` conditions, which the gate
    decides itself against the declaration (reach knows no toolbox tools)."""
    keep = lambda cond: not cond.startswith("tool:")  # noqa: E731
    out = {**intent,
           "goal": [g for g in intent["goal"] if keep(g)],
           "optional": [g for g in intent.get("optional") or [] if keep(g)],
           "capabilities": [c for c in intent.get("capabilities") or [] if keep(c["pred"])]}
    if not out["goal"]:
        out["capabilities"].append({"pred": "deliverable", "title": "work the agent does by "
                                    "itself", "needs": [], "fix": ""})
        out["goal"] = ["deliverable"]
    return out


# requirement kinds the declaration decides, not the runtime manifest
DECLARED_KINDS = ("tool", "account", "credential", "mcp")


def _reader_entry(path: Path, text: str, facts) -> Entry | None:
    """The deterministic requirement reader (`env.manifest.refute_text`) on a
    skill's text: an IMPOSSIBLE entry with the evidence lines when a hard
    requirement is unavailable in the manifest, else None."""
    if facts is None:
        return None
    ev = refute_text(text, facts)
    # tools, connections and credentials come from azure.yaml, which the gate
    # reads itself (frontmatter check, `reach`); the manifest does not decide them
    witness = [w for w in ev.witness
               if w["requirement"].split(":", 1)[0] not in DECLARED_KINDS]
    if not witness:
        return None
    return Entry("skill", path.name, IMPOSSIBLE,
                 f"{REQUIREMENT_UNAVAILABLE} (deterministic requirement reader, runtime "
                 f"`{facts.name}`): " + "; ".join(witness_lines(witness)),
                 [], [], {"intent": path.stem, "requirement_eval": ev.to_dict(),
                          "coverage": "deterministic-reader:manifest"})


def _skill_entry(path: Path, env: Environment, eff: EffectiveRuntime,
                 facts=None) -> Entry:
    """Gate one natural-language skill.  With `facts` (the runtime manifest Rdet
    reads), the deterministic requirement reader runs first and its refutation,
    with the evidence lines, is the entry's reason."""
    text = path.read_text(encoding="utf-8")
    refuted = _reader_entry(path, text, facts)
    if refuted is not None:
        return refuted
    intent = intent_from_text(text, source=str(path))
    missing = [cond[5:] for cond in intent["goal"]
               if cond.startswith("tool:") and not _tool_declared(cond[5:], env, eff)]
    result = reach(_without_tools(intent), env)
    detail = {"intent": intent["name"], "conditions": result.status,
              "frontmatter_tools_missing": missing}
    if missing:
        listed = ", ".join(f"`{t}`" for t in missing)
        return Entry("skill", path.name, IMPOSSIBLE,
                     f"frontmatter tool {listed} is neither a declared toolbox tool nor a "
                     f"`{eff.runtime.name}` tool",
                     [f"add `{t}` to a toolbox the agent uses" for t in missing], [], detail)
    total = len(result.status)
    if result.blocked:
        why = []
        fixes = []
        for b in result.blockers:
            if b.condition in result.blocked:
                why.append(f"{b.condition}: {b.why[0] if b.why else b.title}")
                fixes += b.unblock
        return Entry("skill", path.name, IMPOSSIBLE,
                     f"{len(result.blocked)}/{total} conditions blocked: " + "; ".join(why),
                     list(dict.fromkeys(fixes)), [], detail)
    if result.complete:
        return Entry("skill", path.name, ACHIEVABLE, f"{total}/{total} conditions achievable",
                     [], [], detail)
    assumed = sum(1 for s in result.status.values() if s == "assumed")
    return Entry("skill", path.name, UNKNOWN,
                 f"{total - assumed}/{total} conditions achievable, {assumed} under assumptions",
                 [], list(result.assumptions), detail)


# --------------------------------------------------------------------------
# Topology: the A2A edges a multi-agent deployment needs
# --------------------------------------------------------------------------

def _messages(steps: list) -> list[tuple[str, str, str]]:
    """(from, to, label) of every msg step, choices and loops included."""
    out = []
    for step in steps:
        if not isinstance(step, dict) or len(step) != 1:
            continue
        (kind, body), = step.items()
        if kind == "msg":
            out.append((body["from"], body["to"], body["label"]))
        elif kind == "choice":
            for branch in (body.get("branches") or {}).values():
                out += _messages(branch)
        elif kind == "rec":
            out += _messages(body.get("body") or [])
    return out


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        if isinstance(item, dict):
            item = item.get("name") or item.get("protocol") or item.get("id")
        if isinstance(item, str) and item:
            out.append(item)
    return out


def _role_key(name: str) -> str:
    """Role names compare without case, `_` and `-`: a compacted pack writes
    `revenue_analyst` for the skill file `RevenueAnalyst.md`."""
    return re.sub(r"[-_\s]", "", str(name)).lower()


class _Topology:
    """The agents, skills, connections and toolboxes of the raw azure.yaml."""

    def __init__(self, path: Path):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        services = doc.get("services") if isinstance(doc, dict) else None
        self.services = {str(k): v for k, v in (services or {}).items() if isinstance(v, dict)}
        self.agents = self._hosted("azure.ai.agent")
        self.skills = self._hosted("azure.ai.skill")
        self.connections = self._hosted("azure.ai.connection")
        self.toolboxes = self._hosted("azure.ai.toolbox")

    def _hosted(self, host: str) -> dict[str, dict]:
        return {k: v for k, v in self.services.items() if v.get("host") == host}

    def agent_name(self, key: str) -> str:
        name = self.agents[key].get("name")
        return str(name) if isinstance(name, str) and name else key

    def agent_for(self, role: str) -> str | None:
        """The agent key that plays `role`: by agent name, or by an azure.ai.skill
        whose instructions file is named after the role and that the agent uses."""
        want = _role_key(role)
        for key in self.agents:
            if want in (_role_key(key), _role_key(self.agent_name(key))):
                return key
        skills = {k for k, s in self.skills.items()
                  if isinstance(s.get("instructions"), str)
                  and _role_key(Path(s["instructions"]).stem) == want}
        for key, spec in self.agents.items():
            refs = set(_strings(spec.get("uses"))) | set(_strings(spec.get("skills")))
            if refs & skills:
                return key
        return None

    def toolboxes_of(self, key: str) -> list[str]:
        spec = self.agents[key]
        out = _strings(spec.get("toolboxes"))
        out += [u for u in _strings(spec.get("uses")) if u in self.toolboxes and u not in out]
        return out

    def a2a_connections_to(self, agent_key: str) -> list[str]:
        """Every RemoteA2A connection whose target is `agent_key`'s A2A path. Several
        callers usually have one each, so the sender decides which one counts."""
        suffix = A2A_SUFFIX.format(agent=self.agent_name(agent_key)).lower()
        out = []
        for key, spec in self.connections.items():
            category = str(spec.get("category") or "").lower()
            target = spec.get("target")
            if category == "remotea2a" and isinstance(target, str) \
                    and target.rstrip("/").lower().endswith(suffix):
                out.append(key)
        return out

    def a2a_connection_to(self, agent_key: str) -> str | None:
        found = self.a2a_connections_to(agent_key)
        return found[0] if found else None

    def a2a_tool(self, agent_key: str, connection: str) -> bool:
        """Whether a toolbox `agent_key` uses has an a2a tool over `connection`."""
        for box in self.toolboxes_of(agent_key):
            for tool in (self.toolboxes.get(box) or {}).get("tools") or []:
                if not isinstance(tool, dict) or str(tool.get("type")).lower() != "a2a":
                    continue
                ref = (tool.get("connection") or tool.get("project_connection_id")
                       or tool.get("project_connection_name") or "")
                if ref == connection or str(ref).rstrip("/").endswith(f"/{connection}"):
                    return True
        return False

    def exposes_a2a(self, agent_key: str) -> bool:
        spec = self.agents[agent_key]
        endpoint = spec.get("agentEndpoint") if isinstance(spec.get("agentEndpoint"), dict) \
            else {}
        names = _strings(endpoint.get("protocols")) + _strings(spec.get("protocols"))
        return any(n.lower() == "a2a" for n in names)


def _topology(declared: Path, packs: list[tuple[str, dict]]) -> tuple[list[Entry], str]:
    try:
        topo = _Topology(declared)
    except (OSError, yaml.YAMLError) as e:
        return [], f"azure.yaml could not be read for the topology check: {str(e)[:120]}"
    if len(topo.agents) <= 1:
        return [], "single-agent deployment: messages are in-process"
    out: list[Entry] = []
    for pack_name, pack in packs:
        edges: dict[tuple[str, str], list[str]] = {}
        for sender, receiver, label in _messages(pack.get("protocol") or []):
            if sender != receiver and label not in edges.setdefault((sender, receiver), []):
                edges[(sender, receiver)].append(label)
        for (sender, receiver), labels in edges.items():
            out.append(_edge_entry(topo, pack_name, sender, receiver, labels))
    note = (f"{len(topo.agents)} agents declared; every message between two agents needs "
            "a RemoteA2A connection, an a2a toolbox tool on the sender and a2a on the "
            "receiver's endpoint")
    return out, note


def _edge_entry(topo: _Topology, pack_name: str, sender: str, receiver: str,
                labels: list[str]) -> Entry:
    name = f"{pack_name}: {sender} -> {receiver} ({', '.join(labels)})"
    a, b = topo.agent_for(sender), topo.agent_for(receiver)
    unmapped = [r for r, k in ((sender, a), (receiver, b)) if k is None]
    if unmapped:
        listed = ", ".join(f"`{r}`" for r in unmapped)
        return Entry("topology", name, UNKNOWN, f"role {listed} maps to no declared agent",
                     [f"name an azure.ai.agent `{r}`, or give an agent an azure.ai.skill "
                      f"whose instructions file is {r}.md" for r in unmapped],
                     [f"the messages of {listed} stay inside one agent"])
    if a == b:
        return Entry("topology", name, ACHIEVABLE, f"in-process inside agent {a}")
    reasons, fixes = [], []
    b_name = topo.agent_name(b)
    path = A2A_SUFFIX.format(agent=b_name)
    candidates = topo.a2a_connections_to(b)
    used = [c for c in candidates if topo.a2a_tool(a, c)]
    connection = used[0] if used else None
    if not candidates:
        reasons.append(f"no RemoteA2A connection targets {path}")
        fixes.append(f"declare an azure.ai.connection `{a}-to-{b}` with category RemoteA2A, "
                     f"authType AgenticIdentityToken and target <project endpoint>{path}")
        fixes.append(f"add `- type: a2a` with `a2a_version: \"1.0\"` and `connection: "
                     f"{a}-to-{b}` to a toolbox agent {a} uses")
    elif connection is None:
        boxes = ", ".join(topo.toolboxes_of(a)) or "none"
        # prefer the connection named after this edge, else the first one targeting b
        preferred = next((c for c in candidates if c == f"{a}-to-{b}"), candidates[0])
        reasons.append(f"no toolbox agent {a} uses (toolboxes: {boxes}) has an a2a tool over "
                       f"a connection to {b} (declared: {', '.join(candidates)})")
        fixes.append(f"add `- type: a2a` with `a2a_version: \"1.0\"` and `connection: "
                     f"{preferred}` to a toolbox agent {a} uses")
    if not topo.exposes_a2a(b):
        reasons.append(f"agent {b} does not expose a2a on its endpoint")
        fixes.append(f"add `a2a` to agentEndpoint.protocols of agent {b}")
    if reasons:
        return Entry("topology", name, IMPOSSIBLE, "; ".join(reasons), fixes)
    return Entry("topology", name, ACHIEVABLE,
                 f"{a} -> {b} over connection {connection}", [],
                 [f"the identity of agent {a} holds Foundry Agent Consumer on agent {b} "
                  "(a role assignment outside azure.yaml)"])


# --------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------

COMPACTED_PREFIX = "compacted_"


def _authored_packs(project: Path) -> list[Path]:
    """protocol/*.ce written by people: everything but `compacted_*.ce`."""
    protocol = project / "protocol"
    return [p for p in (sorted(protocol.glob("*.ce")) if protocol.is_dir() else [])
            if p.is_file() and not p.name.startswith(COMPACTED_PREFIX)]


def _environment(project: Path, declared: str | Path,
                 observed: str | Path | None) -> tuple[Path, Path | None, Environment]:
    declared_path = Path(declared)
    if not declared_path.is_absolute():
        declared_path = project / declared_path
    if not declared_path.is_file():
        raise GateError(f"{declared_path} does not exist")
    env = from_azure_yaml(declared_path)
    observed_path = None
    if observed:
        observed_path = Path(observed)
        if not observed_path.is_absolute():
            observed_path = project / observed_path
        env = merge(env, Environment.load(observed_path))
    return declared_path, observed_path, env


def _manifest(runtime: str | Runtime) -> Runtime:
    if isinstance(runtime, Runtime):
        return runtime
    try:
        return load_runtime(str(runtime))
    except (KeyError, RuntimeManifestError, OSError, json.JSONDecodeError) as e:
        raise GateError(f"runtime {runtime!r}: {e}") from None


def _reader_facts(runtime: str | Runtime, eff: EffectiveRuntime):
    """The manifest the requirement reader reads, with the tools of the
    effective runtime (a withdrawn tool decides nothing), or None."""
    try:
        facts = manifest_facts(runtime)
    except (KeyError, ValueError, OSError):
        return None
    return None if facts is None else replace(facts, tools=dict(eff.runtime.tools))


def gate(project_dir: str | Path, declared: str | Path = "azure.yaml",
         observed: str | Path | None = None,
         runtime: str | Runtime = "foundry-hosted",
         packs: list[str | Path] | None = None) -> GateReport:
    """Gate the azd project under `project_dir` (see the module docstring).

    `packs` (e.g. the files `compact_project` wrote) are gated in place of the
    authored `protocol/*.ce`, whose labels are then reported as `authored`."""
    project = Path(project_dir).resolve()
    if not project.is_dir():
        raise GateError(f"{project} is not a directory")
    declared_path, observed_path, env = _environment(project, declared, observed)
    manifest = _manifest(runtime)
    eff = effective_runtime(manifest, env)
    library = load_library()

    authored: list[Entry] = []
    pack_paths = _authored_packs(project)
    if packs is not None:
        authored = [_pack_entry(path, eff, library)[0] for path in pack_paths]
        pack_paths = [Path(p) for p in packs]
    gated: list[Entry] = []
    parsed: list[tuple[str, dict]] = []
    for path in pack_paths:
        if path.is_file():
            entry, pack = _pack_entry(path, eff, library)
            gated.append(entry)
            parsed.append((path.name, pack))
    facts = _reader_facts(runtime, eff)
    skills = [_skill_entry(p, env, eff, facts)
              for p in intent_artifacts(declared_path) if p.is_file()]
    topology, note = _topology(declared_path, parsed)

    def rel(p: Path | None) -> str | None:
        if p is None:
            return None
        try:
            return p.relative_to(project).as_posix()
        except ValueError:
            return str(p)

    return GateReport(str(project), rel(declared_path) or "", rel(observed_path), manifest.name,
                      sorted(eff.runtime.tools), eff.withdrawn, eff.assumptions, gated, skills,
                      topology, note, authored)


# --------------------------------------------------------------------------
# Compaction of the project's own documents (`--compact`, F-d of compaction v2)
# --------------------------------------------------------------------------

MULTI_ROLE_NOTE = (
    "\n\nNote: the document describes several roles that exchange messages; "
    "declare one Role per agent, the messages as `tells`, the approval ordering, "
    "and the deliverable as the Goal.")
COORDINATOR_CONSTANT = "COORDINATOR_INSTRUCTIONS"


def coordinator_instructions(project: Path) -> str | None:
    """The string constant `COORDINATOR_INSTRUCTIONS` of `src/**/main.py`, read as
    text with `ast` (the module is never imported or run)."""
    for main in sorted((project / "src").glob("**/main.py")) if (project / "src").is_dir() else []:
        try:
            tree = ast.parse(main.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for node in tree.body:
            targets = (node.targets if isinstance(node, ast.Assign)
                       else [node.target] if isinstance(node, ast.AnnAssign) else [])
            if any(isinstance(t, ast.Name) and t.id == COORDINATOR_CONSTANT for t in targets) \
                    and isinstance(node.value, ast.Constant) \
                    and isinstance(node.value.value, str):
                return node.value.value
    return None


def project_text(project_dir: str | Path, declared: str | Path = "azure.yaml") -> str:
    """The project's documents as one text: the coordinator instructions (if
    any) and every skill the gate reads, each under a `# Role: <name>` heading."""
    project = Path(project_dir).resolve()
    declared_path = Path(declared)
    if not declared_path.is_absolute():
        declared_path = project / declared_path
    parts = []
    coordinator = coordinator_instructions(project)
    if coordinator:
        parts.append(f"# Role: Coordinator\n\n{coordinator.strip()}\n")
    for path in intent_artifacts(declared_path):
        if path.is_file():
            parts.append(f"# Role: {path.stem}\n\n{path.read_text(encoding='utf-8').strip()}\n")
    if not parts:
        raise GateError(f"{project}: no skills or coordinator instructions to compact")
    return "\n".join(parts)


def declared_runtime(declared_path: Path, default: str = "foundry-hosted") -> str:
    """The runtime manifest azure.yaml names (`x-skillc: {runtime: NAME}` or
    `skillc: {runtime: NAME}` at the top level), else `default`."""
    try:
        doc = yaml.safe_load(declared_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return default
    for key in ("x-skillc", "skillc"):
        block = doc.get(key) if isinstance(doc, dict) else None
        if isinstance(block, dict) and isinstance(block.get("runtime"), str) and block["runtime"]:
            return block["runtime"]
    return default


def compact_project(project_dir: str | Path, declared: str | Path = "azure.yaml",
                    model: str | None = None, samples: int = 1,
                    provider: str | None = "azure-openai", version: str = "p2g+",
                    runtime: str | Runtime | None = None,
                    observed: str | Path | None = None,
                    timeout: int = 600) -> list[dict]:
    """Compact the project's documents into `protocol/compacted_s<k>.ce`.

    The prompt is `ce_runtime_messages(project_text + MULTI_ROLE_NOTE, R,
    version)` where R is the EFFECTIVE runtime (the manifest reduced by the
    declaration), so the model can bind only to tools the project supplies.
    Each sample runs the P2g loop (`frontend.llm.compact_ce_rounds`: two
    located-error retries, one guarded repair) and writes its CE document (when
    one parsed) and `protocol/compacted_s<k>.json` with the prompts, replies
    and usage.  Returns one record per sample: {"sample", "path" (or None),
    "log", "ok", "error", "label", "reason", "repaired"}."""
    from .frontend.llm import compact_ce_rounds          # deferred: optional front-end
    from .frontend.prompts import ce_runtime_messages
    project = Path(project_dir).resolve()
    if not project.is_dir():
        raise GateError(f"{project} is not a directory")
    declared_path, _, env = _environment(project, declared, observed)
    manifest = _manifest(runtime if runtime is not None else declared_runtime(declared_path))
    eff = effective_runtime(manifest, env)
    text = project_text(project, declared_path)
    system, user = ce_runtime_messages(text + MULTI_ROLE_NOTE, eff.runtime, version=version)
    protocol = project / "protocol"
    protocol.mkdir(exist_ok=True)
    out = []
    for k in range(samples):
        res = compact_ce_rounds(system, user, eff.runtime, model=model, provider=provider,
                                timeout=timeout, retries=2, repair=True)
        ce_path = protocol / f"{COMPACTED_PREFIX}s{k}.ce"
        log_path = protocol / f"{COMPACTED_PREFIX}s{k}.json"
        if res["ok"]:
            ce_path.write_text(res["ce_text"], encoding="utf-8")
        elif ce_path.exists():
            ce_path.unlink()                  # never gate a stale sample
        verdict = res["verdict"]
        record = {"sample": k, "path": str(ce_path) if res["ok"] else None,
                  "log": str(log_path), "ok": res["ok"], "error": res["error"],
                  "label": verdict.label if verdict else None,
                  "reason": verdict.reason if verdict else None,
                  "repaired": res["repaired"]}
        log = {"schema": "skillc.compaction-log/1", "project": str(project),
               "declared": declared_path.name, "runtime": manifest.name,
               "effective_tools": sorted(eff.runtime.tools),
               "withdrawn_runtime_tools": eff.withdrawn, "version": version,
               "model": model, "provider": provider, "sample": k,
               "system": system, "user": user,
               "rounds": res["rounds"], "ok": res["ok"], "error": res["error"],
               "repaired": res["repaired"], "repair_rejected": res["repair_rejected"],
               "verdict": verdict.to_dict() if verdict else None}
        log_path.write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")
        out.append(record)
    return out


# --------------------------------------------------------------------------
# Telemetry: one span per verdict when OpenTelemetry is importable
# --------------------------------------------------------------------------

def emit_verdict(report: GateReport) -> None:
    """Emit `skillc.verdict gate <verdict>` as an OpenTelemetry span; a no-op
    without the SDK, and never an error."""
    try:
        from opentelemetry import trace
    except ImportError:
        return
    try:
        tracer = trace.get_tracer("skillc")
        with tracer.start_as_current_span(f"skillc.verdict gate {report.verdict}") as span:
            span.set_attribute("skillc.project", report.project)
            span.set_attribute("skillc.verdict", report.verdict)
            span.set_attribute("skillc.impossible", len(report.impossible))
    except Exception:  # noqa: BLE001  telemetry never decides the gate
        return


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def add_parser(sub) -> None:
    sp = sub.add_parser("gate", help="deploy gate for an azd project: packs, skills and "
                                     "topology against the declared azure.yaml (exit 0/1/3/2)")
    sp.add_argument("dir", nargs="?", default=".", help="the azd project directory")
    sp.add_argument("--declared", default="azure.yaml", metavar="FILE",
                    help="the azure.yaml to read (default: azure.yaml under DIR)")
    sp.add_argument("--env", metavar="FILE",
                    help="an observed skillc.env/1 probe merged over the declaration")
    sp.add_argument("--runtime", default="foundry-hosted", metavar="NAME|JSON",
                    help="runtime manifest name or file (default: foundry-hosted)")
    sp.add_argument("--json", action="store_true", help="print the report as JSON")
    sp.add_argument("--install-hook", action="store_true",
                    help="print the azure.yaml hooks.predeploy snippet and exit")
    sp.add_argument("--compact", action="store_true",
                    help="compact the project's skills with an LLM (P2g+, effective runtime) "
                         "into protocol/compacted_s<k>.ce and gate those instead of the "
                         "authored protocol/*.ce (calls a model)")
    sp.add_argument("--model", default=None,
                    help="with --compact: Azure OpenAI deployment or Anthropic model")
    sp.add_argument("--samples", type=int, default=1,
                    help="with --compact: number of independent compactions (default 1)")
    sp.add_argument("--llm-provider", default="azure-openai",
                    help="with --compact: LLM provider (default azure-openai)")
    sp.add_argument("--ce-prompt", choices=("p2g", "p2g+"), default="p2g+",
                    help="with --compact: CE prompt version (default p2g+)")
    sp.set_defaults(fn=cmd_gate)


def cmd_gate(args) -> int:
    if getattr(args, "install_hook", False):
        print(HOOK_SNIPPET, end="")
        return 0
    try:
        project = getattr(args, "dir", ".") or "."
        declared = getattr(args, "declared", "azure.yaml")
        runtime = getattr(args, "runtime", "foundry-hosted")
        compaction = None
        if getattr(args, "compact", False):
            if isinstance(runtime, str) and runtime == "foundry-hosted":
                # the default: a manifest azure.yaml names wins over it
                declared_path = Path(declared)
                if not declared_path.is_absolute():
                    declared_path = Path(project) / declared_path
                runtime = declared_runtime(declared_path, runtime)
            compaction = compact_project(
                project, declared, model=getattr(args, "model", None),
                samples=getattr(args, "samples", 1),
                provider=getattr(args, "llm_provider", "azure-openai"),
                version=getattr(args, "ce_prompt", "p2g+"), runtime=runtime,
                observed=getattr(args, "env", None))
        report = gate(project, declared, getattr(args, "env", None), runtime,
                      packs=None if compaction is None
                      else [c["path"] for c in compaction if c["path"]])
        if compaction is not None:
            report.compaction = [_sample_label(c, report) for c in compaction]
    except (GateError, AzdError, OSError, ValueError, KeyError, RuntimeError) as e:
        print(f"skillc gate: error: {e}", file=sys.stderr)
        return 2
    print(json.dumps(report.to_dict(), indent=2) if getattr(args, "json", False)
          else report.render())
    emit_verdict(report)
    return report.exit_code


def _sample_label(record: dict, report: GateReport) -> dict:
    """A compaction record with the gate's label for the pack it wrote."""
    out = dict(record)
    name = Path(record["path"]).name if record.get("path") else None
    entry = next((e for e in report.packs if e.name == name), None)
    out["label"] = entry.verdict if entry else None
    out["gate_reason"] = entry.reason if entry else None
    out["compaction_label"] = record.get("label")
    return out


__all__ = ["gate", "GateReport", "compact_project", "project_text",
           "coordinator_instructions", "declared_runtime", "MULTI_ROLE_NOTE", "Entry", "EffectiveRuntime", "effective_runtime",
           "GateError", "add_parser", "cmd_gate", "emit_verdict", "HOOK_SNIPPET"]

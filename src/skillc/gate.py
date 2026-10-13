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

Declared facts are taken at their word here: the gate refuses only what the
declaration already rules out, and a probe (`--env`) replaces declarations by
observations.  Exit codes: 0 every item ACHIEVABLE, 1 something IMPOSSIBLE,
3 nothing impossible but something rests on an assumption, 2 an error.
"""
from __future__ import annotations

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
from .env.model import Environment, merge
from .env.nl import intent_from_text
from .env.reach import reach
from .frontend.ce import CEError, parse_ce_detailed
from .frontend.runtime import Runtime, RuntimeManifestError, bind_runtime, load_runtime
from .frontend.toolpolicy import load_library
from .pack import PackError

ACHIEVABLE, UNKNOWN, IMPOSSIBLE = "ACHIEVABLE", "UNKNOWN", "IMPOSSIBLE"
EXIT_CODES = {ACHIEVABLE: 0, IMPOSSIBLE: 1, UNKNOWN: 3}
REPORT_SCHEMA = "skillc.gate/1"

# runtime tool -> the toolbox tool type that supplies it
TOOLBOX_TYPES = {"code_interpreter": "code_interpreter", "web_search": "web_search",
                 "search": "azure_ai_search", "mcp": "mcp", "openapi": "openapi", "a2a": "a2a"}
SANDBOX_TOOLS = ("read", "write")
EGRESS_TOOLS = ("web_fetch",)
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
        if any(e.verdict == UNKNOWN for e in self.entries):
            return UNKNOWN
        return ACHIEVABLE

    @property
    def exit_code(self) -> int:
        return EXIT_CODES[self.verdict]

    def to_dict(self) -> dict:
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
        if verdict.reason == "NON_CONFORMANT" and reasons:
            reason += f"; {verdict.detail}"
    else:
        reason = f"{verdict.reason}: {verdict.detail}".rstrip(": ")
        assumptions.append(f"the checker could not decide this pack: {verdict.reason}")
    entry = Entry("pack", path.name, label, reason, list(dict.fromkeys(fixes)), assumptions,
                  {"pure_verdict": pure.label, "bound_verdict": verdict.label,
                   "bound_reason": verdict.reason, "via": via, "withdrawn": bound.withdrawn,
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


def _skill_entry(path: Path, env: Environment, eff: EffectiveRuntime) -> Entry:
    intent = intent_from_text(path.read_text(encoding="utf-8"), source=str(path))
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
        want = role.lower()
        for key in self.agents:
            if want in (key.lower(), self.agent_name(key).lower()):
                return key
        skills = {k for k, s in self.skills.items()
                  if isinstance(s.get("instructions"), str)
                  and Path(s["instructions"]).stem.lower() == want}
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

def gate(project_dir: str | Path, declared: str | Path = "azure.yaml",
         observed: str | Path | None = None,
         runtime: str | Runtime = "foundry-hosted") -> GateReport:
    """Gate the azd project under `project_dir` (see the module docstring)."""
    project = Path(project_dir).resolve()
    if not project.is_dir():
        raise GateError(f"{project} is not a directory")
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
    if isinstance(runtime, Runtime):
        manifest = runtime
    else:
        try:
            manifest = load_runtime(str(runtime))
        except (KeyError, RuntimeManifestError, OSError, json.JSONDecodeError) as e:
            raise GateError(f"runtime {runtime!r}: {e}") from None
    eff = effective_runtime(manifest, env)
    library = load_library()

    packs: list[Entry] = []
    parsed: list[tuple[str, dict]] = []
    protocol = project / "protocol"
    for path in sorted(protocol.glob("*.ce")) if protocol.is_dir() else []:
        if path.is_file():
            entry, pack = _pack_entry(path, eff, library)
            packs.append(entry)
            parsed.append((path.name, pack))
    skills = [_skill_entry(p, env, eff) for p in intent_artifacts(declared_path) if p.is_file()]
    topology, note = _topology(declared_path, parsed)

    def rel(p: Path | None) -> str | None:
        if p is None:
            return None
        try:
            return p.relative_to(project).as_posix()
        except ValueError:
            return str(p)

    return GateReport(str(project), rel(declared_path) or "", rel(observed_path), manifest.name,
                      sorted(eff.runtime.tools), eff.withdrawn, eff.assumptions, packs, skills,
                      topology, note)


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
    sp.set_defaults(fn=cmd_gate)


def cmd_gate(args) -> int:
    if getattr(args, "install_hook", False):
        print(HOOK_SNIPPET, end="")
        return 0
    try:
        report = gate(getattr(args, "dir", ".") or ".", getattr(args, "declared", "azure.yaml"),
                      getattr(args, "env", None), getattr(args, "runtime", "foundry-hosted"))
    except (GateError, AzdError, OSError, ValueError, KeyError) as e:
        print(f"skillc gate: error: {e}", file=sys.stderr)
        return 2
    print(json.dumps(report.to_dict(), indent=2) if getattr(args, "json", False)
          else report.render())
    emit_verdict(report)
    return report.exit_code


__all__ = ["gate", "GateReport", "Entry", "EffectiveRuntime", "effective_runtime",
           "GateError", "add_parser", "cmd_gate", "emit_verdict", "HOOK_SNIPPET"]

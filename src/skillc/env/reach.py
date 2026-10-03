"""What an intent can achieve in an environment, and what blocks the rest.

    intent (goal conditions)  +  environment graph  +  operation catalogue
        -> per condition: achievable | achievable under assumptions | blocked
        -> a plan for the largest achievable part, verified by the checker
        -> for every blocked condition: why, and what would unblock it

The catalogue (`skillc.ops/1`) is provider-neutral data: operations with the
conditions they require and add, the permission they need and where, the
resource type they create, and an optional MCP alternative.  The environment
decides which operations are available (`facts`): an operation whose
permission or policy is definitely refused is not available; one that rests on
an unknown fact is available *under an assumption*.

Operations only add conditions, so reachability is monotone: the set of goal
conditions reachable together is exactly the reachable closure intersected
with the goal (no subset search).  The verdicts come from the trusted checker:
the plan is checked as a pack (ACHIEVABLE with a witness), and every blocked
condition carries the checker's protocol-independent GOAL_UNSAT certificate
over the available operations.  Refutations are sound relative to the
snapshot: they rest only on facts that were observed.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from ..checker import Verdict, check
from .azure import builtin_roles
from .facts import can, policy_allows, service_available, tools_matching
from .model import Environment, Fact, all_of, matches, norm_id

INTENT_SCHEMA = "skillc.intent/1"
OPS_SCHEMA = "skillc.ops/1"


class IntentError(ValueError):
    """A malformed intent or operation catalogue."""


# --------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------

def load_catalog(name_or_path: str) -> dict:
    p = Path(name_or_path)
    raw = (p.read_text(encoding="utf-8") if p.suffix == ".json" and p.exists()
           else resources.files("skillc").joinpath(f"data/env/ops_{name_or_path}.json")
           .read_text(encoding="utf-8"))
    catalog = json.loads(raw)
    if catalog.get("schema") != OPS_SCHEMA or not isinstance(catalog.get("operations"), list):
        raise IntentError(f"{name_or_path}: not a {OPS_SCHEMA} catalogue")
    return catalog


def load_intent(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        p = Path(str(resources.files("skillc").joinpath(f"data/env/intents/{path}.json")))
    intent = json.loads(p.read_text(encoding="utf-8"))
    if intent.get("schema") != INTENT_SCHEMA:
        raise IntentError(f"{path}: not a {INTENT_SCHEMA} document")
    goal = intent.get("goal")
    if not (isinstance(goal, list) and goal and all(isinstance(g, str) and g for g in goal)):
        raise IntentError(f"{path}: goal must be a non-empty list of condition names")
    if not isinstance((intent.get("target") or {}).get("scope"), str):
        raise IntentError(f"{path}: target.scope is required")
    return intent


def _subscription(env: Environment) -> str:
    subs = [n["id"] for n in env.of_kind("scope") if n["attrs"].get("level") == "subscription"]
    return subs[0].split("/")[2] if subs else "{subscription}"


def _resolve(intent: dict, env: Environment) -> dict:
    """Fill `{subscription}` in the intent from the environment."""
    sub = _subscription(env)
    return json.loads(json.dumps(intent).replace("{subscription}", sub))


# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------

@dataclass
class Step:
    op: str
    title: str
    how: str
    why: list[str] = field(default_factory=list)          # evidence it is allowed
    assumptions: list[str] = field(default_factory=list)
    via_mcp: list[str] = field(default_factory=list)


@dataclass
class Blocker:
    condition: str
    op: str
    title: str
    why: list[str]
    unblock: list[str]


@dataclass
class ReachResult:
    intent: dict
    captured_at: str
    status: dict[str, str]                 # condition -> achievable | assumed | blocked
    plan: list[Step]
    blockers: list[Blocker]
    assumptions: list[str]
    plan_verdict: Verdict
    certificates: dict[str, Verdict]       # blocked condition -> GOAL_UNSAT verdict
    pack: dict
    initial: list[str]
    operations: list[dict]                 # every catalogue op with its availability
    catalog: dict = field(default_factory=dict)

    @property
    def complete(self) -> bool:
        return all(s == "achievable" for s in self.status.values())

    @property
    def blocked(self) -> list[str]:
        return [c for c, s in self.status.items() if s == "blocked"]

    def to_dict(self) -> dict:
        return {
            "schema": "skillc.reach/1",
            "intent": self.intent.get("name"),
            "environment_captured_at": self.captured_at,
            "complete": self.complete,
            "conditions": self.status,
            "plan": [vars(s) for s in self.plan],
            "blocked": [vars(b) for b in self.blockers],
            "assumptions": self.assumptions,
            "plan_verdict": self.plan_verdict.to_dict(),
            "certificates": {c: v.to_dict() for c, v in self.certificates.items()},
            "operations": self.operations,
        }


# --------------------------------------------------------------------------
# Availability of operations in the environment
# --------------------------------------------------------------------------

def _scope_for(at: str, intent: dict) -> str:
    target = intent["target"]["scope"]
    if at == "subscription":
        return "/".join(target.split("/")[:3])
    if at.startswith("data:"):
        ref = _data(intent, at[5:])
        return ref["store"]
    return target


def _data(intent: dict, data_id: str) -> dict:
    for d in intent.get("data") or []:
        if d.get("id") == data_id:
            return d
    raise IntentError(f"the intent declares no data source {data_id!r}")


def _availability(op: dict, env: Environment, intent: dict) -> Fact:
    facts = []
    perm = op.get("permission")
    if perm:
        facts.append(can(env, perm["action"], _scope_for(perm.get("at", "target"), intent),
                         data=perm.get("data", False)))
    created = (op.get("creates") or {}).get("type")
    if created:
        facts.append(policy_allows(env, created, intent["target"].get("location"),
                                   intent["target"]["scope"]))
    for data_id in op.get("uses_data") or []:
        _data(intent, data_id)                      # must be declared
    return all_of(facts) if facts else Fact(True, ("it needs no permission beyond its "
                                                  "prerequisites",))


def _initial(catalog: dict, env: Environment, intent: dict,
             evidence: dict[str, list[str]]) -> dict[str, list[str]]:
    """Conditions that already hold -> what had to be assumed to say so.
    `evidence` collects, per such condition, why it holds."""
    held: dict[str, list[str]] = {}
    for cap in catalog.get("capabilities") or []:
        fact = all_of([can(env, a, _scope_for(cap.get("at", "target"), intent), data=True)
                       for a in cap["data_actions"]])
        if fact.possible:
            held[cap["pred"]] = list(fact.assuming())
            evidence[cap["pred"]] = list(dict.fromkeys(fact.reasons))
    target = norm_id(intent["target"]["scope"])
    for op in catalog["operations"]:
        exists = op.get("exists") or {}
        if exists.get("scope") == "target" and target in env.nodes:
            held.update(dict.fromkeys(op["adds"], []))
            evidence.update(dict.fromkeys(op["adds"], [f"{target} exists"]))
        existing = [n["id"] for n in env.of_kind("resource")
                    if exists.get("type")
                    and n["attrs"].get("type", "").lower() == exists["type"].lower()
                    and target in env.ancestors(n["id"])]
        if existing:
            held.update(dict.fromkeys(op["adds"], []))
            evidence.update(dict.fromkeys(op["adds"], [f"{existing[0]} exists"]))
    for pred in sorted({p for op in catalog["operations"] for p in op.get("adds", [])
                        if p.startswith("service:")}):
        fact = service_available(env, pred.split(":", 1)[1])
        if fact.possible:
            held[pred] = list(fact.assuming())
            evidence[pred] = list(fact.reasons)
    return held


# --------------------------------------------------------------------------
# Planning and verification
# --------------------------------------------------------------------------

def _closure(ops: list[dict], held: set[str]) -> tuple[set[str], list[dict], dict[str, dict]]:
    """Forward chaining: reachable conditions, ops in firing order, first establisher."""
    state, fired, first = set(held), [], {}
    progress = True
    while progress:
        progress = False
        for op in ops:
            if op in fired or not set(op.get("requires", [])) <= state:
                continue
            fired.append(op)
            for p in op["adds"]:
                if p not in state:
                    state.add(p)
                    first[p] = op
            progress = True
    return state, fired, first


def _plan_for(goal: list[str], held: set[str], fired: list[dict],
              first: dict[str, dict]) -> list[dict]:
    needed: set[str] = set()
    stack = [g for g in goal if g not in held and g in first]
    while stack:
        op = first[stack.pop()]
        if op["id"] in needed:
            continue
        needed.add(op["id"])
        stack += [r for r in op.get("requires", []) if r not in held and r in first]
    return [op for op in fired if op["id"] in needed]


def _pack(name: str, ops: list[dict], held: set[str], plan: list[dict],
          goal: list[str]) -> dict:
    caps = {}
    for op in ops:
        req = op.get("requires", [])
        caps[op["id"]] = {"owner": "you", "add": list(op["adds"]),
                          "pre": True if not req else req[0] if len(req) == 1
                          else {"and": list(req)}}
    return {"name": name, "roles": ["you"], "capabilities": caps,
            "protocol": [{"act": {"cap": op["id"], "by": "you"}} for op in plan],
            "goal": True if not goal else goal[0] if len(goal) == 1 else {"and": goal},
            "init_true": sorted(held)}


def reach(intent: dict, env: Environment, catalog: dict | None = None) -> ReachResult:
    intent = _resolve(intent, env)
    catalog = catalog or load_catalog(intent.get("catalog", "azure"))
    evidence: dict[str, list[str]] = {}
    held_assumed = _initial(catalog, env, intent, evidence)
    held = set(held_assumed)

    available, overview = [], []
    for op in catalog["operations"]:
        fact = _availability(op, env, intent)
        route = op.get("mcp") or {}
        tools = [t["name"] for t in tools_matching(env, route.get("tools", []))]
        overview.append({"id": op["id"], "title": op["title"], "available": fact.possible,
                         "definite": fact.value is True, "why": list(fact.reasons),
                         "assumptions": list(fact.assuming()), "mcp_tools": tools})
        if fact.possible:
            available.append({**op, "_fact": fact, "_tools": tools})
        if tools:
            # the MCP route: the tool does the work with its own access, so it
            # needs neither the operation's permission nor what it replaces
            available.append({
                **op, "id": f"{op['id']}_via_mcp", "title": f"{op['title']} (via MCP {tools[0]})",
                "requires": [r for r in op.get("requires", [])
                             if r not in route.get("replaces", [])],
                "how": f"call the MCP tool {tools[0]}",
                "_fact": Fact(None, (f"MCP tool {tools[0]} is connected",),
                              (f"MCP tool {tools[0]} can {op['title'][0].lower()}"
                               f"{op['title'][1:]}",)),
                "_tools": tools})

    state, fired, first = _closure(available, held)
    goal = intent["goal"]
    reachable = [g for g in goal if g in state]
    plan_ops = _plan_for(reachable, held, fired, first)
    steps = [Step(op["id"], op["title"], _fill(op.get("how", ""), intent),
                  list(op["_fact"].reasons)
                  + [r for p in op.get("requires", []) if p in held
                     for r in evidence.get(p, [])],
                  list(op["_fact"].assuming()), op["_tools"])
             for op in plan_ops]

    status, assumptions = {}, []
    for g in goal:
        if g not in state:
            status[g] = "blocked"
            continue
        support = _plan_for([g], held, fired, first)
        used = {g} | {r for op in support for r in op.get("requires", [])}
        mine = [a for op in support for a in op["_fact"].assuming()]
        mine += [a for r in sorted(used & held) for a in held_assumed[r]]
        status[g] = "assumed" if mine else "achievable"
        assumptions += mine

    clean = [{k: v for k, v in op.items() if not k.startswith("_")} for op in available]
    pack = _pack(intent.get("name", "intent"), clean, held, plan_ops, reachable)
    certificates = {g: check({**pack, "protocol": [], "goal": g}, scope="goal")
                    for g in goal if g not in state}
    blockers = _explain([g for g in goal if g not in state], catalog, env, intent,
                        {op["id"] for op in available}, state)
    # root causes (something the environment refuses) first, then what waits on them
    blockers.sort(key=lambda b: b.why[0].startswith("needs ") if b.why else True)
    return ReachResult(intent, env.captured_at, status, steps, blockers,
                       list(dict.fromkeys(assumptions)), check(pack), certificates, pack,
                       sorted(held), overview, catalog)


def _fill(template: str, intent: dict) -> str:
    params = dict(intent.get("params") or {})
    target = intent["target"]
    params.setdefault("location", target.get("location", "<location>"))
    params.setdefault("rg", target["scope"].rstrip("/").split("/")[-1])
    params.setdefault("you", "<your sign-in name>")

    def sub(m: re.Match) -> str:
        key = m.group(1)
        if key.startswith("data:"):
            parts = key.split(":")
            ref = _data(intent, parts[1])
            if len(parts) == 2:
                return ref["store"]
            return ref["store"].rstrip("/").split("/")[-1] if parts[2] == "name" \
                else str(ref.get(parts[2], f"<{parts[2]}>"))
        return str(params.get(key, f"<{key}>"))

    return re.sub(r"\{([\w:]+)\}", sub, template)


# --------------------------------------------------------------------------
# Why something is blocked, and what would unblock it
# --------------------------------------------------------------------------

def _explain(blocked: list[str], catalog: dict, env: Environment, intent: dict,
             available: set[str], state: set[str]) -> list[Blocker]:
    out: list[Blocker] = []
    seen: set[str] = set()
    stack = list(blocked)
    while stack:
        cond = stack.pop(0)
        if cond in seen:
            continue
        seen.add(cond)
        for cap in catalog.get("capabilities") or []:
            if cap["pred"] == cond:
                out.append(_capability_blocker(cap, env, intent))
        makers = [op for op in catalog["operations"] if cond in op.get("adds", [])]
        if not makers and not any(c["pred"] == cond for c in catalog.get("capabilities") or []):
            out.append(Blocker(cond, "-", "no operation in the catalogue establishes it",
                               ["the catalogue has no operation for this condition"],
                               ["extend the operation catalogue (skillc.ops/1)"]))
        for op in makers:
            if op["id"] not in available:
                fact = _availability(op, env, intent)
                out.append(Blocker(cond, op["id"], op["title"], list(fact.reasons),
                                   _unblock(op, fact, env, intent)))
            else:
                missing = [r for r in op.get("requires", []) if r not in state]
                route = op.get("mcp") or {}
                tips = [f"unblock {m}" for m in missing]
                if route.get("tools") and set(missing) <= set(route.get("replaces", [])):
                    tips.append("or connect an MCP server whose tools can do it "
                                f"(matching {route['tools'][0]!r})")
                out.append(Blocker(cond, op["id"], op["title"],
                                   [f"needs {', '.join(missing)} first"], tips))
                stack += missing
    return out


def _capability_blocker(cap: dict, env: Environment, intent: dict) -> Blocker:
    """A data-plane capability the principal does not hold, and who grants it."""
    scope = _scope_for(cap.get("at", "target"), intent)
    facts = [can(env, a, scope, data=True) for a in cap["data_actions"]]
    roles = granting_roles(cap["data_actions"], data=True)
    tip = (f"ask for one of {', '.join(repr(r) for r in roles[:3])} at {scope}" if roles
           else f"ask for a role with the data actions {cap['data_actions']} at {scope}")
    missing = [a for a, f in zip(cap["data_actions"], facts, strict=True) if f.value is False]
    why = [f"no role assigned to the principal grants the data action"
           f"{'s' if len(missing) > 1 else ''} {', '.join(missing)} at {scope}"]
    return Blocker(cap["pred"], "-", f"hold the permission to {cap['title']}", why, [tip])


def _unblock(op: dict, fact: Fact, env: Environment, intent: dict) -> list[str]:
    tips = []
    perm = op.get("permission")
    text = " ".join(fact.reasons)
    if perm and "no role" in text:
        scope = _scope_for(perm.get("at", "target"), intent)
        roles = granting_roles([perm["action"]], perm.get("data", False))
        if roles:
            tips.append(f"ask for one of {', '.join(repr(r) for r in roles[:3])} at {scope}")
        else:
            tips.append(f"ask for a role that grants {perm['action']} at {scope}")
    if "deny rule" in text:
        tips.append("ask the administrator who owns the deny assignment for an exclusion")
    if "allows only locations" in text:
        allowed = re.search(r"locations (\[.*?\])", text)
        where = allowed.group(1) if allowed else "the allowed list"
        tips.append(f"choose a target location from {where} or request a policy exemption")
    if "resource type" in text:
        tips.append("request a policy exemption for this resource type at the target scope")
    if (op.get("mcp") or {}).get("tools"):
        tips.append("or connect an MCP server whose tools can do this "
                    f"(matching {op['mcp']['tools'][0]!r})")
    return tips or ["see the reasons above"]


def granting_roles(actions: list[str], data: bool = False) -> list[str]:
    """Built-in roles that grant every one of `actions`, narrowest first."""
    out = []
    for r in builtin_roles().values():
        allow = r["dataActions" if data else "actions"]
        deny = r["notDataActions" if data else "notActions"]
        if all(any(matches(p, a) for p in allow) and not any(matches(p, a) for p in deny)
               for a in actions):
            out.append((("*" in allow), len(allow), r["name"]))
    return [name for *_, name in sorted(out)]


def explain_scope(scope: str) -> str:
    """Short, readable form of a scope id."""
    parts = scope.strip("/").split("/")
    if len(parts) > 4 and parts[2].lower() == "resourcegroups" and parts[4].lower() == "providers":
        return f"{parts[-2]} {parts[-1]} (in resource group {parts[3]})"
    if len(parts) == 4 and parts[2].lower() == "resourcegroups":
        return f"resource group {parts[3]}"
    if len(parts) == 2 and parts[0].lower() == "subscriptions":
        return f"subscription {parts[1]}"
    if len(parts) == 4 and parts[2].lower() == "managementgroups":
        return f"management group {parts[3]}"
    return scope or "/"


SCOPE_RE = re.compile(r"/(?:subscriptions|providers/Microsoft\.Management)/[\w./-]+",
                      re.IGNORECASE)


def readable(text: str) -> str:
    """`text` with every scope id replaced by its short form."""
    return SCOPE_RE.sub(lambda m: explain_scope(m.group(0)), text)


def as_json(result: ReachResult) -> str:
    return json.dumps(result.to_dict(), indent=2, default=str)


__all__ = ["reach", "load_intent", "load_catalog", "ReachResult", "IntentError",
           "granting_roles", "explain_scope", "as_json"]

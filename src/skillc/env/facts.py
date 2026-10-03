"""Three-valued facts read off an environment graph.

    can(env, action, scope, data=False)     may the principal perform `action`?
    policy_allows(env, type, location, scope)   may it create such a resource?
    service_available(env, name)            is the service usable here?
    tools_matching(env, patterns)           which connected tools fit?

Permission semantics are the role-based model shared by Azure RBAC and most
clouds: a role assigned at a scope applies there and to every scope below it;
its actions (data actions, for data-plane operations, separately) are
wildcard patterns minus its not-actions; a deny rule that matches overrides
every allow; an assignment that carries a condition is not trusted as a
definite grant.  Whatever the adapter could not read is reported in
`Fact.assumptions` and never turned into a refusal.
"""
from __future__ import annotations

import re

from .model import Environment, Fact, all_of, matches, norm_id


def _grants(perms: dict, action: str, data: bool) -> bool:
    allow = perms.get("data_actions" if data else "actions") or []
    deny = perms.get("not_data_actions" if data else "not_actions") or []
    return (any(matches(p, action) for p in allow)
            and not any(matches(p, action) for p in deny))


def can(env: Environment, action: str, scope: str, data: bool = False) -> Fact:
    """Whether the environment's principal may perform `action` at `scope`."""
    principal = env.principal()
    kind = "data action" if data else "action"
    if principal is None:
        return Fact(None, ("the environment names no principal",))
    chain = set(env.ancestors(scope))
    for edge in env.out_edges(principal["id"], "denied"):
        if norm_id(edge["attrs"].get("scope", "/")) in chain:
            rule = env.nodes[edge["dst"]]
            if _grants(rule["attrs"], action, data):
                return Fact(False, (f"deny rule '{rule['name']}' at "
                                    f"{edge['attrs'].get('scope')} blocks {action}",))
    allows, unsure = [], []
    for edge in env.out_edges(principal["id"], "assigned"):
        at = edge["attrs"].get("scope", "/")
        if norm_id(at) not in chain:
            continue
        role = env.nodes[edge["dst"]]
        if role["attrs"].get("definition_unknown"):
            unsure.append(f"the definition of role '{role['name']}' (at {at}) was not read")
        elif _grants(role["attrs"], action, data):
            if edge["attrs"].get("condition"):
                unsure.append(f"role '{role['name']}' at {at} grants {action} "
                              "only under a condition")
            else:
                allows.append(f"role '{role['name']}' at {at}")
    if allows:
        assumptions = ((f"no deny rule blocks {action}",)
                       if env.is_unknown("deny_assignments") else ())
        return Fact(True, tuple(f"{a} grants {action}" for a in allows), assumptions)
    if unsure or env.is_unknown("role_assignments"):
        why = unsure or ["the principal's role assignments were not read"]
        return Fact(None, tuple(why), (f"the principal may perform {action} at {scope}",))
    return Fact(False, (f"no role assigned to the principal grants the {kind} "
                        f"{action} at {scope}",))


def policy_allows(env: Environment, resource_type: str, location: str | None,
                  scope: str) -> Fact:
    """Whether the deny-effect policies over `scope` permit creating a resource
    of `resource_type` in `location`."""
    chain = env.ancestors(scope)
    denials, uninterpreted = [], []
    for policy in env.of_kind("policy"):
        a = policy["attrs"]
        if a.get("effect", "").lower() != "deny" or a.get("enforced") is False:
            continue
        for edge in env.out_edges(policy["id"], "applies"):
            if norm_id(edge["dst"]) not in chain:
                continue
            not_scopes = {norm_id(s) for s in edge["attrs"].get("not_scopes") or []}
            if not_scopes & set(chain):
                continue
            rule = a.get("rule") or {}
            values = {v.lower() for v in rule.get("values") or []}
            kind = rule.get("kind")
            name = policy["name"]
            if kind == "allowed_locations":
                if location and location.lower() not in values | {"global"}:
                    denials.append(f"policy '{name}' allows only locations "
                                   f"{sorted(rule.get('values') or [])}, not {location}")
            elif kind == "allowed_types":
                if resource_type.lower() not in values:
                    denials.append(f"policy '{name}' does not allow resource type "
                                   f"{resource_type}")
            elif kind == "denied_types":
                if resource_type.lower() in values:
                    denials.append(f"policy '{name}' denies resource type {resource_type}")
            else:
                uninterpreted.append(f"deny policy '{name}' (not interpreted) does not "
                                     f"block {resource_type}")
    if denials:
        return Fact(False, tuple(denials))
    assumptions = list(uninterpreted)
    if env.is_unknown("policies"):
        assumptions.append(f"no policy denies {resource_type} in {location or 'this location'}")
    if uninterpreted:
        return Fact(None, tuple(uninterpreted), tuple(assumptions))
    return Fact(True, ("no deny policy over the scope blocks it",), tuple(assumptions))


def service_available(env: Environment, name: str) -> Fact:
    """Whether a service (an Azure resource provider, an API family) is usable."""
    node = env.nodes.get(norm_id(f"service/{name}"))
    if node is not None:
        if node["attrs"].get("registered"):
            return Fact(True, (f"service {name} is registered",))
        return Fact(False, (f"service {name} is not registered",))
    if env.is_unknown("services"):
        return Fact(None, ("service registrations were not read",),
                    (f"service {name} is registered",))
    return Fact(False, (f"service {name} is not offered in this environment",))


def tools_matching(env: Environment, patterns: list[str]) -> list[dict]:
    """Connected tools whose name matches any regular expression in `patterns`."""
    rx = [re.compile(p, re.IGNORECASE) for p in patterns]
    return [t for t in env.of_kind("tool") if any(r.search(t["name"]) for r in rx)]


# --------------------------------------------------------------------------
# Runtime needs: what an operation requires of the agent's runtime
# --------------------------------------------------------------------------

NEED_KINDS = ("program", "pymodule", "egress", "credential", "path", "tool",
              "mcp_tool", "mcp_server", "platform", "daemon", "any", "all")


def need(env: Environment, spec: dict) -> Fact:
    """One runtime need, e.g. {"program": "az"}, {"egress": "pypi.org"},
    {"credential": "GITHUB_TOKEN"}, {"path": "/workspace"},
    {"tool": "WebFetch", "arg": "domain:example.com"}, {"mcp_tool": "search"},
    {"mcp_server": "github"}."""
    kind = next((k for k in NEED_KINDS if k in spec), None)
    if kind is None:
        raise ValueError(f"unknown need {spec!r}; kinds: {NEED_KINDS}")
    value = spec[kind]
    if kind == "all":
        return all_of([need(env, s) for s in value])
    if kind == "any":
        facts = [need(env, s) for s in value]
        hit = next((f for f in facts if f.value is True), None)
        if hit is not None:
            return hit
        open_ = [f for f in facts if f.value is None]
        if open_:
            return Fact(None, tuple(r for f in open_ for r in f.reasons),
                        tuple(dict.fromkeys(a for f in open_ for a in f.assuming())))
        return Fact(False, (" and ".join(r for f in facts for r in f.reasons),))
    if kind in ("program", "pymodule", "egress", "credential", "platform", "daemon"):
        return _service_need(env, kind, value)
    if kind == "path":
        return _path_need(env, value)
    if kind == "tool":
        return _tool_need(env, value, spec.get("arg"))
    return _mcp_need(env, kind, value)


def _service_need(env: Environment, kind: str, value: str) -> Fact:
    node = env.nodes.get(norm_id(f"{kind}/{value}"))
    label = {"pymodule": "Python module", "egress": "network access to",
             "platform": "platform", "daemon": "a running"}.get(kind, kind)
    if node is None or (kind == "egress" and env.is_unknown("egress")):
        return Fact(None, (f"{label} {value} was not probed",),
                    (f"{label} {value} is available",))
    why = node["attrs"].get("why")
    detail = f" ({why})" if why else ""
    if node["attrs"].get("available"):
        assumptions = ((f"credential {value} is valid for this task",)
                       if kind == "credential" else ())
        return Fact(True, (f"{label} {value} is available{detail}",), assumptions)
    return Fact(False, (f"{label} {value} is not available{detail}",))


def _path_need(env: Environment, path: str) -> Fact:
    probed = [n for n in env.of_kind("scope") if n["attrs"].get("level") == "path"
              and (path == n["name"] or path.startswith(n["name"].rstrip("/") + "/"))]
    if not probed:
        return Fact(None, (f"path {path} was not probed",), (f"path {path} is writable",))
    node = max(probed, key=lambda n: len(n["name"]))
    if node["attrs"].get("writable"):
        return Fact(True, (f"{node['name']} is writable",))
    return Fact(False, (f"{node['name']} is not writable",))


def _tool_need(env: Environment, tool: str, arg: str | None) -> Fact:
    if norm_id(f"tool/{tool}") not in env.nodes:
        return Fact(False, (f"the runtime has no {tool} tool",))
    action = f"{tool}({arg})" if arg else tool
    principal = env.principal()
    for edge in env.out_edges(principal["id"], "denied") if principal else []:
        if _grants(env.nodes[edge["dst"]]["attrs"], action, data=False):
            return Fact(False, (f"a deny rule blocks {action}",))
    for edge in env.out_edges(principal["id"], "assigned") if principal else []:
        if not edge["attrs"].get("condition") and _grants(env.nodes[edge["dst"]]["attrs"],
                                                         action, data=False):
            return Fact(True, (f"an allow rule permits {action}",))
    return Fact(None, (f"no rule allows {action}; the runtime asks before using it",),
                (f"the user approves {action} when asked",))


def _mcp_need(env: Environment, kind: str, value: str) -> Fact:
    if kind == "mcp_server":
        node = env.nodes.get(norm_id(f"mcp/{value}"))
        if node is None:
            return Fact(False, (f"no MCP server {value} is connected",))
        if node["attrs"].get("needs_auth"):
            return Fact(False, (f"MCP server {value} is waiting for sign-in",))
        return Fact(True, (f"MCP server {value} is connected",))
    servers = {n["id"]: n for n in env.of_kind("mcp_server")}
    rx = re.compile(value, re.IGNORECASE)
    found = []
    for edge in env.edges:
        server = servers.get(edge["src"])
        if (edge["kind"] == "exposes" and server is not None
                and not server["attrs"].get("needs_auth")
                and rx.search(env.nodes[edge["dst"]]["name"])):
            found.append(f"{server['name']}/{env.nodes[edge['dst']]['name']}")
    if found:
        return Fact(True, (f"MCP tool {found[0]} is connected",))
    unlisted = [u["what"] for u in env.unknown if u["what"].startswith("mcp_tools:")]
    if unlisted:
        return Fact(None, (f"no listed MCP tool matches {value!r}",),
                    (f"an unlisted MCP tool ({', '.join(unlisted)}) matches {value!r}",))
    return Fact(False, (f"no connected MCP tool matches {value!r}",))

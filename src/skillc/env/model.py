"""The provider-neutral environment graph (`skillc.env/1`).

An environment is what one principal can see and do: the scopes it works in,
the roles it holds where, the deny rules and policies that constrain it, the
services available, the resources and data that exist, and the MCP servers and
tools connected to its agent.  Adapters (`env.azure`, `env.mcp`) build it;
nothing here knows about a particular provider.

    {
      "schema": "skillc.env/1",
      "captured_at": "2026-10-03T12:00:00Z",
      "sources": [{"adapter": "azure", "mode": "live", "detail": "..."}],
      "nodes": [{"id": "...", "kind": "<kind>", "name": "...", "attrs": {...}}],
      "edges": [{"src": "<id>", "dst": "<id>", "kind": "<kind>", "attrs": {...}}],
      "unknown": [{"what": "role_assignments", "why": "..."}]
    }

Node kinds and their attributes:

    principal   type, object_id                     who acts
    scope       level (root|group|subscription|resource_group|...)
    role        actions, not_actions, data_actions, not_data_actions
    deny        same four lists, principals, exclude_principals (deny rules)
    policy      effect (deny|audit|disabled), rule {kind, values}, enforced
    service     registered (true|false)             a provider / API family
    resource    type, location                      something that exists
    data        store, path, format                 data the intent may use
    mcp_server  transport, command|url
    tool        description                         a tool an MCP server exposes

Edge kinds:

    contains    scope -> scope | resource           hierarchy (parent -> child)
    assigned    principal -> role                   attrs.scope, attrs.condition
    denied      principal -> deny                   attrs.scope
    applies     policy -> scope                     attrs.not_scopes
    stores      resource -> data
    exposes     mcp_server -> tool

`unknown` names every fact the adapter could not read.  Reasoning over the
graph treats an unknown as *possibly true* and reports it as an assumption, so
a refutation never rests on something that was not observed.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

ENV_SCHEMA = "skillc.env/1"
NODE_KINDS = frozenset({"principal", "scope", "role", "deny", "policy", "service",
                        "resource", "data", "mcp_server", "tool"})
EDGE_KINDS = frozenset({"contains", "assigned", "denied", "applies", "stores", "exposes"})


class EnvError(ValueError):
    """A malformed environment document."""


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def norm_id(value: str) -> str:
    """Identifiers compare case-insensitively and without a trailing slash."""
    return value.strip().rstrip("/").lower() or "/"


def matches(pattern: str, action: str) -> bool:
    """Wildcard permission match: `*` spans any characters, case-insensitive
    (`Microsoft.DigitalTwins/*`, `*/read`)."""
    return fnmatchcase(action.lower(), pattern.lower())


# --------------------------------------------------------------------------
# Three-valued facts
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Fact:
    """True / False / None (unknown), with the evidence for it.

    `reasons` explain the value; `assumptions` are what an optimistic reading
    of an unknown took for granted (only ever present when value is not False).
    """
    value: bool | None
    reasons: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()

    @property
    def possible(self) -> bool:
        """Not refuted: True, or unknown and therefore possibly true."""
        return self.value is not False

    def assuming(self) -> tuple[str, ...]:
        """What must be assumed to treat the fact as true."""
        if self.value is None:
            return self.assumptions or self.reasons
        return self.assumptions


def all_of(facts: list[Fact]) -> Fact:
    """Conjunction: False if any is False, else unknown if any is unknown."""
    false = [f for f in facts if f.value is False]
    if false:
        return Fact(False, tuple(r for f in false for r in f.reasons))
    return Fact(None if any(f.value is None for f in facts) else True,
                tuple(r for f in facts for r in f.reasons),
                tuple(dict.fromkeys(a for f in facts for a in f.assuming())))


# --------------------------------------------------------------------------
# The graph
# --------------------------------------------------------------------------

@dataclass
class Environment:
    nodes: dict[str, dict] = field(default_factory=dict)      # id -> node
    edges: list[dict] = field(default_factory=list)
    unknown: list[dict] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    captured_at: str = field(default_factory=now_utc)

    # ---- construction --------------------------------------------------
    def add_node(self, node_id: str, kind: str, name: str = "", **attrs: Any) -> str:
        if kind not in NODE_KINDS:
            raise EnvError(f"unknown node kind {kind!r}")
        key = norm_id(node_id)
        node = self.nodes.setdefault(key, {"id": key, "kind": kind,
                                           "name": name or node_id, "attrs": {}})
        node["attrs"].update({k: v for k, v in attrs.items() if v is not None})
        return key

    def add_edge(self, src: str, dst: str, kind: str, **attrs: Any) -> None:
        if kind not in EDGE_KINDS:
            raise EnvError(f"unknown edge kind {kind!r}")
        edge = {"src": norm_id(src), "dst": norm_id(dst), "kind": kind,
                "attrs": {k: v for k, v in attrs.items() if v is not None}}
        if edge not in self.edges:
            self.edges.append(edge)

    def mark_unknown(self, what: str, why: str) -> None:
        entry = {"what": what, "why": why}
        if entry not in self.unknown:
            self.unknown.append(entry)

    # ---- serialisation -------------------------------------------------
    def to_dict(self) -> dict:
        return {"schema": ENV_SCHEMA, "captured_at": self.captured_at,
                "sources": self.sources,
                "nodes": sorted(self.nodes.values(), key=lambda n: (n["kind"], n["id"])),
                "edges": sorted(self.edges, key=lambda e: (e["kind"], e["src"], e["dst"])),
                "unknown": self.unknown}

    @staticmethod
    def from_dict(d: dict) -> Environment:
        validate_env(d)
        env = Environment(captured_at=d.get("captured_at", ""),
                          sources=list(d.get("sources", [])),
                          unknown=list(d.get("unknown", [])))
        for n in d["nodes"]:
            env.add_node(n["id"], n["kind"], n.get("name", ""), **n.get("attrs", {}))
        for e in d["edges"]:
            env.add_edge(e["src"], e["dst"], e["kind"], **e.get("attrs", {}))
        return env

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(self.to_dict(), indent=1) + "\n", encoding="utf-8")

    @staticmethod
    def load(path: str | Path) -> Environment:
        return Environment.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    # ---- queries -------------------------------------------------------
    def of_kind(self, kind: str) -> list[dict]:
        return [n for n in self.nodes.values() if n["kind"] == kind]

    def out_edges(self, src: str, kind: str) -> list[dict]:
        src = norm_id(src)
        return [e for e in self.edges if e["src"] == src and e["kind"] == kind]

    def is_unknown(self, what: str) -> bool:
        return any(u["what"] == what for u in self.unknown)

    def principal(self) -> dict | None:
        found = self.of_kind("principal")
        return found[0] if found else None

    def ancestors(self, scope: str) -> list[str]:
        """`scope` and every scope above it, nearest first.

        A scope not in the graph (one the intent will create) hangs under the
        deepest known scope whose id is a path prefix of it."""
        key = norm_id(scope)
        parents: dict[str, str] = {e["dst"]: e["src"] for e in self.edges
                                   if e["kind"] == "contains"}
        if key not in self.nodes:
            known = [s for s in self.nodes
                     if self.nodes[s]["kind"] == "scope"
                     and (s == "/" or key.startswith(s + "/"))]
            chain = [key]
            key = max(known, key=len) if known else None
            if key is None:
                return chain
        else:
            chain = []
        seen = set()
        while key is not None and key not in seen:
            seen.add(key)
            chain.append(key)
            key = parents.get(key)
        return chain


def validate_env(d: Any) -> None:
    """Raise EnvError unless `d` is a well-formed `skillc.env/1` document."""
    if not isinstance(d, dict) or d.get("schema") != ENV_SCHEMA:
        raise EnvError(f"not a {ENV_SCHEMA} document")
    nodes, edges = d.get("nodes"), d.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise EnvError("nodes and edges must be lists")
    ids = set()
    for i, n in enumerate(nodes):
        if not (isinstance(n, dict) and isinstance(n.get("id"), str) and n["id"]):
            raise EnvError(f"nodes[{i}]: needs a non-empty string id")
        if n.get("kind") not in NODE_KINDS:
            raise EnvError(f"nodes[{i}]: unknown kind {n.get('kind')!r}")
        if not isinstance(n.get("attrs", {}), dict):
            raise EnvError(f"nodes[{i}]: attrs must be an object")
        ids.add(norm_id(n["id"]))
    for i, e in enumerate(edges):
        if not (isinstance(e, dict) and e.get("kind") in EDGE_KINDS):
            kind = e.get("kind") if isinstance(e, dict) else e
            raise EnvError(f"edges[{i}]: unknown kind {kind!r}")
        for end in ("src", "dst"):
            if not isinstance(e.get(end), str) or norm_id(e[end]) not in ids:
                raise EnvError(f"edges[{i}]: {end} {e.get(end)!r} is not a node")
    unknown = d.get("unknown", [])
    if not (isinstance(unknown, list)
            and all(isinstance(u, dict) and isinstance(u.get("what"), str) for u in unknown)):
        raise EnvError("unknown must be a list of {what, why}")


def merge(*envs: Environment) -> Environment:
    """One environment from several adapters' views (nodes union, attrs merged)."""
    out = Environment(captured_at=max((e.captured_at for e in envs), default=now_utc()))
    for env in envs:
        for n in env.nodes.values():
            out.add_node(n["id"], n["kind"], n["name"], **n["attrs"])
        for e in env.edges:
            out.add_edge(e["src"], e["dst"], e["kind"], **e["attrs"])
        for u in env.unknown:
            out.mark_unknown(u["what"], u.get("why", ""))
        out.sources.extend(s for s in env.sources if s not in out.sources)
    return out


def diff(old: Environment, new: Environment) -> dict[str, list[str]]:
    """What changed between two snapshots, as readable lines per category."""
    def node_line(n: dict) -> str:
        return f"{n['kind']} {n['name']}"

    def edge_line(env: Environment, e: dict) -> str:
        name = lambda i: env.nodes[i]["name"] if i in env.nodes else i  # noqa: E731
        scope = f" at {e['attrs']['scope']}" if "scope" in e["attrs"] else ""
        return f"{name(e['src'])} -{e['kind']}-> {name(e['dst'])}{scope}"

    out: dict[str, list[str]] = {"added": [], "removed": [], "changed": []}
    for key in sorted(new.nodes.keys() - old.nodes.keys()):
        out["added"].append(node_line(new.nodes[key]))
    for key in sorted(old.nodes.keys() - new.nodes.keys()):
        out["removed"].append(node_line(old.nodes[key]))
    for key in sorted(old.nodes.keys() & new.nodes.keys()):
        before, after = old.nodes[key]["attrs"], new.nodes[key]["attrs"]
        if before != after:
            changed = sorted(k for k in before.keys() | after.keys()
                             if before.get(k) != after.get(k))
            out["changed"].append(f"{node_line(new.nodes[key])}: {', '.join(changed)}")
    old_edges = {json.dumps(e, sort_keys=True) for e in old.edges}
    new_edges = {json.dumps(e, sort_keys=True) for e in new.edges}
    out["added"] += [edge_line(new, json.loads(e)) for e in sorted(new_edges - old_edges)]
    out["removed"] += [edge_line(old, json.loads(e)) for e in sorted(old_edges - new_edges)]
    old_u = {u["what"] for u in old.unknown}
    new_u = {u["what"] for u in new.unknown}
    out["added"] += [f"unknown {w}" for w in sorted(new_u - old_u)]
    out["removed"] += [f"unknown {w}" for w in sorted(old_u - new_u)]
    return out

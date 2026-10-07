"""azd adapter: the environment an `azd` project declares in its `azure.yaml`.

A Foundry hosted agent is built from an `azd` project whose `azure.yaml`
names, before anything exists in Azure, the model deployments, the egress
mode, the connections and their auth modes, the toolbox tool types, the
skills and the agent's sandbox and policies.  This adapter compiles that
declaration, offline and deterministically, into the provider-neutral graph.

Every node it adds carries `declared: true`: a declared fact is an assumption
until a probe observes it, so nothing here can refute an intent on its own.

    host                  nodes
    azure.ai.project      service model/<deployment> (available), service egress/public
                          (mode; availability unknown until measured from inside)
    azure.ai.connection   service connection/<name> (category, auth_type, target host;
                          never credentials)
    azure.ai.toolbox      mcp_server toolbox/<name>, tool toolbox/<name>/<type>[/<conn>]
    azure.ai.agent        principal principal/agent/<name> (agent_kind, protocols, cpu,
                          memory, env var names, toolboxes), policy policy/<type>/<n>
    azure.ai.skill        no node: `intent_artifacts()` lists its instruction files

`$ref` includes are resolved relative to the containing file (local YAML or
JSON only; a URL or a cycle is recorded as unknown).  `${VAR}` references are
left as written and each variable is recorded as an unknown value.  Secret
values never enter the graph: connections keep only names, categories, auth
types and hosts.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import yaml

from .model import Environment

VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
INCLUDE_SUFFIXES = (".yaml", ".yml", ".json")
HOSTS = ("azure.ai.project", "azure.ai.connection", "azure.ai.toolbox", "azure.ai.agent",
         "azure.ai.skill")
OPEN_EGRESS = "AllowInternetOutbound"


class AzdError(ValueError):
    """The azure.yaml itself could not be read."""


# --------------------------------------------------------------------------
# Public entry points
# --------------------------------------------------------------------------

def from_azure_yaml(path: str | Path) -> Environment:
    """The declared environment of the azd project whose azure.yaml is `path`."""
    path = Path(path).resolve()
    env = Environment()
    env.sources.append({"adapter": "azd", "mode": "declared", "detail": str(path)})
    doc = _document(path)
    env.add_node("/", "scope", str(doc.get("name") or path.parent.name), level="root",
                 declared=True)
    services = _services(doc, path, env)
    for name in sorted(_variables([spec for spec, _ in services.values()])):
        env.mark_unknown(f"value:{name}", "unresolved azd environment variable")
    toolboxes = {n for n, (s, _) in services.items() if s.get("host") == "azure.ai.toolbox"}
    for name, (spec, _base) in services.items():
        host = spec.get("host")
        if host == "azure.ai.project":
            _project(env, name, spec)
        elif host == "azure.ai.connection":
            _connection(env, name, spec)
        elif host == "azure.ai.toolbox":
            _toolbox(env, name, spec)
        elif host == "azure.ai.agent":
            _agent(env, name, spec, toolboxes)
        elif host != "azure.ai.skill":
            env.mark_unknown(f"service:{name}", f"unsupported host {host or '(none)'}")
    return env


def intent_artifacts(path: str | Path) -> list[Path]:
    """The intent artifacts the project declares: every `azure.ai.skill`
    `instructions` file, an agent `instructions` value that names an existing
    file, and `skills/*.md` next to the azure.yaml.  Paths are resolved
    relative to the file that declares them."""
    path = Path(path).resolve()
    env = Environment()                       # unknowns are not reported here
    found: list[Path] = []
    for spec, base in _services(_document(path), path, env).values():
        if spec.get("host") not in ("azure.ai.skill", "azure.ai.agent"):
            continue
        target = _file(spec.get("instructions"), base)
        if target is not None and (spec["host"] == "azure.ai.skill" or target.is_file()):
            found.append(target)
    skills = path.parent / "skills"
    if skills.is_dir():
        found += sorted(p for p in skills.glob("*.md") if p.is_file())
    return list(dict.fromkeys(found))


def _file(value: Any, base: Path) -> Path | None:
    """`value` as a path relative to `base`'s directory, if it looks like one."""
    if not isinstance(value, str) or not value.strip() or "\n" in value or VAR.search(value):
        return None
    if len(value) > 260 or not value.lower().endswith((".md", ".txt", ".yaml", ".yml")):
        return None
    try:
        return (base.parent / value).resolve()
    except (OSError, ValueError):
        return None


# --------------------------------------------------------------------------
# Reading the document and its includes
# --------------------------------------------------------------------------

def _load(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    return yaml.safe_load(text)


def _document(path: Path) -> dict:
    try:
        doc = _load(path)
    except (OSError, yaml.YAMLError, json.JSONDecodeError, UnicodeDecodeError) as e:
        raise AzdError(f"cannot read {path}: {str(e)[:200]}") from None
    if not isinstance(doc, dict):
        raise AzdError(f"{path}: not a mapping")
    return doc


def _services(doc: dict, path: Path, env: Environment) -> dict[str, tuple[dict, Path]]:
    """name -> (resolved service spec, the file whose directory relative paths
    in that spec refer to), in declaration order."""
    raw = doc.get("services")
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        env.mark_unknown("services", "`services` is not a mapping")
        return {}
    out: dict[str, tuple[dict, Path]] = {}
    for name, spec in raw.items():
        if not isinstance(spec, dict):
            env.mark_unknown(f"service:{name}", "service definition is not a mapping")
            continue
        resolved, base = _resolve_mapping(spec, path, env, (path,))
        out[str(name)] = (resolved, base)
    return out


def _resolve(value: Any, base: Path, env: Environment, seen: tuple[Path, ...]) -> Any:
    if isinstance(value, list):
        return [_resolve(v, base, env, seen) for v in value]
    if isinstance(value, dict):
        return _resolve_mapping(value, base, env, seen)[0]
    return value


def _resolve_mapping(value: dict, base: Path, env: Environment,
                     seen: tuple[Path, ...]) -> tuple[dict, Path]:
    """A mapping with its `$ref` include merged in (the mapping's own keys win),
    and the file the result's relative paths refer to."""
    rest = {k: _resolve(v, base, env, seen) for k, v in value.items() if k != "$ref"}
    if "$ref" not in value:
        return rest, base
    included, target = _include(value["$ref"], base, env, seen)
    if target is None:
        return rest, base
    if not isinstance(included, dict):
        env.mark_unknown(f"ref:{value['$ref']}", "the included document is not a mapping")
        return rest, base
    inner, _ = _resolve_mapping(included, target, env, (*seen, target))
    return {**inner, **rest}, target


def _include(ref: Any, base: Path, env: Environment,
             seen: tuple[Path, ...]) -> tuple[Any, Path | None]:
    """The document a `$ref` names, or (None, None) with the reason recorded."""
    what = f"ref:{ref}"
    if not isinstance(ref, str) or not ref.strip():
        env.mark_unknown(what, "$ref must be a non-empty string")
        return None, None
    if "://" in ref or ref.startswith("//"):
        env.mark_unknown(what, "remote $ref includes are not fetched")
        return None, None
    file_part, _, fragment = ref.partition("#")
    if not file_part:
        env.mark_unknown(what, "a $ref into the same document is not resolved")
        return None, None
    target = (base.parent / file_part).resolve()
    if target.suffix.lower() not in INCLUDE_SUFFIXES:
        env.mark_unknown(what, "only local YAML or JSON includes are resolved")
        return None, None
    if target in seen:
        env.mark_unknown(what, "cyclic $ref include")
        return None, None
    try:
        doc = _load(target)
    except (OSError, yaml.YAMLError, json.JSONDecodeError, UnicodeDecodeError) as e:
        env.mark_unknown(what, str(e)[:200])
        return None, None
    if fragment:
        for key in fragment.strip("/").split("/"):
            key = key.replace("~1", "/").replace("~0", "~")
            if isinstance(doc, dict) and key in doc:
                doc = doc[key]
            elif isinstance(doc, list) and key.isdigit() and int(key) < len(doc):
                doc = doc[int(key)]
            else:
                env.mark_unknown(what, f"pointer #{fragment} not found in {target.name}")
                return None, None
    return doc, target


def _variables(values: Any) -> set[str]:
    """Every `${VAR}` named anywhere in `values`."""
    if isinstance(values, str):
        return set(VAR.findall(values))
    if isinstance(values, dict):
        values = list(values.values())
    if isinstance(values, list):
        return set().union(*(_variables(v) for v in values)) if values else set()
    return set()


# --------------------------------------------------------------------------
# One host at a time
# --------------------------------------------------------------------------

def _project(env: Environment, name: str, spec: dict) -> None:
    for entry in _dicts(spec.get("deployments")):
        model = entry.get("model") if isinstance(entry.get("model"), dict) else {}
        sku = entry.get("sku") if isinstance(entry.get("sku"), dict) else {}
        deployment = str(entry.get("name") or model.get("name") or "")
        if not deployment:
            env.mark_unknown(f"deployment:{name}", "a deployment without a name")
            continue
        env.add_node(f"model/{deployment}", "service", deployment, type="model", available=True,
                     declared=True, project=name, model=_text(model.get("name")),
                     version=_text(model.get("version")), format=_text(model.get("format")),
                     sku=_text(sku.get("name")), capacity=sku.get("capacity"))
    network = spec.get("network") if isinstance(spec.get("network"), dict) else {}
    mode = _text(network.get("isolationMode")) or OPEN_EGRESS
    isolated = bool(network.get("agentSubnet")) or mode != OPEN_EGRESS
    env.add_node("egress/public", "service", "public", type="egress", declared=True,
                 project=name, mode=mode, isolated=isolated,
                 agent_subnet=bool(network.get("agentSubnet")) or None)
    if isolated:
        env.mark_unknown("egress", "network-isolated project; public hosts unknown until "
                                   "probed from inside")
    else:
        env.mark_unknown("egress", f"declared {OPEN_EGRESS}; measure from inside the sandbox")


def _connection(env: Environment, name: str, spec: dict) -> None:
    # `credentials` is never read: a connection is a name, a category, an auth type, a host.
    env.add_node(f"connection/{name}", "service", name, type="connection", available=True,
                 declared=True, category=_text(spec.get("category")),
                 auth_type=_text(spec.get("authType")), target=_public_host(spec.get("target")),
                 audience=_public_host(spec.get("audience")),
                 env_vars=_names(spec.get("env")), uses=_strings(spec.get("uses")))


def _toolbox(env: Environment, name: str, spec: dict) -> None:
    server = env.add_node(f"toolbox/{name}", "mcp_server", name, transport="toolbox",
                          declared=True, description=_text(spec.get("description")),
                          env_vars=_names(spec.get("env")), uses=_strings(spec.get("uses")))
    for entry in _dicts(spec.get("tools")):
        kind = _text(entry.get("type"))
        if not kind:
            env.mark_unknown(f"toolbox_tool:{name}", "a tools[] entry without a type")
            continue
        connection = _text(entry.get("connection"))
        label = _text(entry.get("server_label"))
        node_id = f"toolbox/{name}/{kind}"
        if connection:
            node_id += f"/{connection}"
        elif kind == "mcp" and label:
            node_id += f"/{label}"
        tool_name = _text(entry.get("name"))
        node = env.add_node(node_id, "tool", kind, type=kind, declared=True, connection=connection,
                            tool_name=tool_name if tool_name != kind else None,
                            server_label=label, server_url=_public_host(entry.get("server_url")),
                            require_approval=_text(entry.get("require_approval")))
        env.add_edge(server, node, "exposes")
        if kind != "mcp":
            continue
        allowed = _strings(entry.get("allowed_tools"))
        if allowed:
            for remote in allowed:
                env.add_edge(server, env.add_node(f"{node_id}/{remote}", "tool", remote,
                                                  declared=True, via=node_id), "exposes")
        else:
            env.mark_unknown(f"mcp_tools:{node_id}",
                             "tools of a connected MCP server are not declared in azure.yaml")


def _agent(env: Environment, name: str, spec: dict, declared_toolboxes: set[str]) -> None:
    resources = ((spec.get("container") or {}).get("resources")
                 if isinstance(spec.get("container"), dict) else None) or {}
    code = spec.get("codeConfiguration") if isinstance(spec.get("codeConfiguration"), dict) else {}
    toolboxes: list[str] = []
    for item in _list(spec.get("toolboxes")):
        ref = item.get("name") if isinstance(item, dict) else item
        if isinstance(ref, str) and ref and ref not in toolboxes:
            toolboxes.append(ref)
    toolboxes += [u for u in _strings(spec.get("uses")) or []
                  if u in declared_toolboxes and u not in toolboxes]
    protocols = [" ".join(_text(v) for v in (p.get("protocol"), p.get("version")) if _text(v))
                 for p in _dicts(spec.get("protocols"))]
    env.add_node(f"principal/agent/{name}", "principal", name, type="agent",
                 identity_mode="agent", declared=True, agent_kind=_text(spec.get("kind")),
                 protocols=protocols or None, cpu=_text(resources.get("cpu")),
                 memory=_text(resources.get("memory")), env_vars=_names(spec.get("env")),
                 toolboxes=toolboxes or None, uses=_strings(spec.get("uses")),
                 language=_text(spec.get("language")), runtime=_text(code.get("runtime")),
                 image=_public_host(spec.get("image")) or _text(spec.get("image")),
                 description=_text(spec.get("description")))
    for toolbox in toolboxes:
        env.add_node(f"toolbox/{toolbox}", "mcp_server", toolbox, transport="toolbox",
                     declared=True)
        if toolbox not in declared_toolboxes:
            env.mark_unknown(f"mcp_tools:toolbox/{toolbox}",
                             f"toolbox {toolbox} is referenced by agent {name} but not declared")
    for n, policy in enumerate(_dicts(spec.get("policies"))):
        kind = _text(policy.get("type")) or "policy"
        value = _text(policy.get("raiPolicyName") or policy.get("name")) or f"{kind} {n}"
        node = env.add_node(f"policy/{kind}/{n}", "policy", f"{kind} {value}", effect="deny",
                            rule={"kind": kind, "values": [value]}, enforced=True, declared=True,
                            agent=name)
        env.add_edge(node, "/", "applies")


# --------------------------------------------------------------------------
# Small shape helpers: wrong shapes become absent attributes, never exceptions
# --------------------------------------------------------------------------

def _text(value: Any) -> str | None:
    if value is None or isinstance(value, (dict, list)):
        return None
    text = str(value).strip()
    return text or None


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _dicts(value: Any) -> list[dict]:
    return [v for v in _list(value) if isinstance(v, dict)]


def _strings(value: Any) -> list[str] | None:
    out = [v for v in _list(value) if isinstance(v, str) and v]
    return out or None


def _names(value: Any) -> list[str] | None:
    """Environment variable names only; values never enter the graph."""
    if not isinstance(value, dict):
        return None
    return sorted(str(k) for k in value) or None


def _public_host(url: Any) -> str | None:
    """Scheme and host (and port) only: no path, query, fragment or user info.
    An unresolved `${VAR}` or anything that is not a URL gives None."""
    if not isinstance(url, str) or not url or VAR.search(url):
        return None
    try:
        parts = urlsplit(url)
        host, port = parts.hostname, parts.port
    except ValueError:
        return None
    if not parts.scheme or not host:
        return None
    return urlunsplit((parts.scheme, f"{host}:{port}" if port else host, "", "", ""))

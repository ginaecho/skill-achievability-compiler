"""Foundry adapter: a read-only probe of a deployed hosted agent's control plane.

The azd adapter compiles what an `azure.yaml` *declares*; this adapter reads
what the Foundry project *has* after `azd deploy`, through the project's REST
data plane and the Azure CLI, and records it with the same node ids, so that
`env diff declared.json observed.json` shows exactly which assumptions became
observations.  Nothing here changes anything: every call is a GET, an MCP
`tools/list`, or an `az ... list` (checked by the Azure adapter's read-only
guard).

    fact                                   nodes
    the agent and its current version      principal principal/agent/<name> (object_id =
                                           the instance identity, version, status, cpu,
                                           memory, protocols, env var NAMES, runtime, entry
                                           point, endpoint protocols, a2a, agent card)
    the project's toolboxes                mcp_server toolbox/<name> (version, transport
                                           "toolbox"), tool toolbox/<name>/<type>[/<conn>]
                                           per declared tool, and, from the live MCP
                                           tools/list, tool toolbox/<name>/mcp/<tool>
    the project's connections              service connection/<name> (category, auth type,
                                           target host; never a credential)
    the agent identity's RBAC              role nodes and assigned edges, as env.azure
                                           records them for the signed-in principal

Every call goes through a *runner*, as in `env.azure`:

    live_runner(endpoint, ...)      HTTP with a bearer token for https://ai.azure.com, and
                                    `az` for RBAC; `save_raw=DIR` keeps every answer (and
                                    every failure, so a replay fails the same way)
    replay_runner(DIR)              answers from such an export, offline

A saved answer is sanitised before it is written: keys named like token,
secret, key, authorization, password or credential are dropped (a
connection's `credentials` keeps only its `type`), environment variable
values become "<redacted>", e-mail addresses are replaced and URLs lose
their user info, query and fragment.  The graph is
built from the sanitised answer in live mode too, so live and replay agree.
Whatever fails is recorded in `Environment.unknown`, never raised.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from . import azure, mcp
from .azd import _public_host, _text
from .model import Environment

API = "v1"
TOKEN_SCOPE = "https://ai.azure.com/.default"
AGENT_CONSUMER_ROLE = "eed3b665-ab3a-47b6-8f48-c9382fb1dad6"
KNOWN_ROLES = {AGENT_CONSUMER_ROLE: "Foundry Agent Consumer"}
MANIFEST = "manifest.json"
SECRET_KEY = re.compile(r"token|secret|key|authorization|password|credential", re.IGNORECASE)
KEEP_KEYS = frozenset({"authorization_schemes"})     # named like a secret, carries none
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")

Runner = Callable[[list[str]], Any]          # ["get", path] | ["mcp", "tools/list", path]
TokenProvider = Callable[[], str]            # | ["az", *args]


class FoundryProbeError(azure.ProbeError):
    """A Foundry call failed.  A ProbeError, so the Azure adapter's shared
    helpers treat it like one of their own failures."""


# --------------------------------------------------------------------------
# Tokens and runners
# --------------------------------------------------------------------------

def az_token_provider(scope: str = TOKEN_SCOPE, timeout: int = 120) -> TokenProvider:
    """`az account get-access-token --scope <scope>`, run once and cached: the
    CLI can take 15 s or more per call.  The token stays in memory."""
    cache: dict[str, str] = {}

    def token() -> str:
        if "value" not in cache:
            exe = shutil.which("az") or shutil.which("az.cmd")
            if exe is None:
                raise FoundryProbeError("the Azure CLI (az) is not installed; sign in with "
                                        "`az login`")
            proc = subprocess.run([exe, "account", "get-access-token", "--scope", scope,
                                   "-o", "json"], capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=timeout,
                                  check=False)
            if proc.returncode:
                raise FoundryProbeError((proc.stderr or proc.stdout).strip()[:500]
                                        or "az account get-access-token failed")
            cache["value"] = json.loads(proc.stdout)["accessToken"]
        return cache["value"]

    return token


def live_runner(project_endpoint: str, token_provider: TokenProvider | None = None,
                save_raw: str | Path | None = None, timeout: float = 60.0,
                az_runner: azure.Runner | None = None) -> Runner:
    base = project_endpoint.rstrip("/")
    token = token_provider or az_token_provider()
    az_run = az_runner or azure.live_runner()
    raw_dir = Path(save_raw) if save_raw else None

    def save(request: list[str], doc: dict) -> None:
        if raw_dir is not None:
            raw_dir.mkdir(parents=True, exist_ok=True)
            (raw_dir / azure.raw_key(request)).write_text(
                json.dumps({"request": request, **doc}, indent=1), encoding="utf-8")

    def run(request: list[str]) -> Any:
        kind, *rest = request
        try:
            if kind == "get":
                data = _http_get(base + rest[0], token(), timeout)
            elif kind == "mcp":
                data = mcp.list_http_tools(base + rest[1], token(), timeout)
            elif kind == "az":
                azure._assert_read_only(rest)
                data = az_run(rest)
            else:
                raise FoundryProbeError(f"unknown request kind {kind!r}")
        except (azure.ProbeError, mcp.MCPProbeError, OSError, ValueError) as e:
            save(request, {"error": sanitise(str(e)[:300])})   # replay fails the same way
            raise
        data = sanitise(data)
        save(request, {"output": data})
        return data

    return run


def replay_runner(raw_dir: str | Path) -> Runner:
    root = Path(raw_dir)

    def run(request: list[str]) -> Any:
        if request[0] == "az":
            azure._assert_read_only(request[1:])
        path = root / azure.raw_key(request)
        if not path.exists():
            raise FoundryProbeError(f"not in the export: {' '.join(request)}")
        doc = json.loads(path.read_text(encoding="utf-8"))
        if "error" in doc:
            raise FoundryProbeError(str(doc["error"]))
        return doc["output"]

    return run


def _http_get(url: str, token: str, timeout: float) -> Any:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}",
                                               "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        detail = EMAIL.sub("<redacted>", e.read().decode("utf-8", "replace")[:200])
        raise FoundryProbeError(f"HTTP {e.code} for {mcp._public_url(url)}: {detail}") from None
    except (urllib.error.URLError, OSError) as e:
        reason = getattr(e, "reason", None) or e
        raise FoundryProbeError(f"{mcp._public_url(url)}: {str(reason)[:200]}") from None
    return json.loads(body) if body.strip() else None


def sanitise(value: Any) -> Any:
    """`value` with every secret-like key dropped (except the few known to
    carry none), environment variable values and e-mail addresses redacted.
    Safe to write to a file."""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            name = str(key)
            if name == "credentials" and isinstance(item, dict):
                out[name] = {"type": item["type"]} if isinstance(item.get("type"), str) else {}
            elif name == "environment_variables" and isinstance(item, dict):
                out[name] = dict.fromkeys((str(k) for k in item), "<redacted>")
            elif SECRET_KEY.search(name) and name not in KEEP_KEYS:
                continue
            else:
                out[name] = sanitise(item)
        return out
    if isinstance(value, list):
        return [sanitise(v) for v in value]
    if isinstance(value, str):
        if "://" in value and " " not in value:
            value = mcp._public_url(value) or value   # no user info, query or fragment
        return EMAIL.sub("<redacted>", value)
    return value


def is_export(raw_dir: str | Path) -> bool:
    """Whether `raw_dir` holds an export this adapter saved."""
    return _manifest(raw_dir).get("adapter") == "foundry"


def _manifest(raw_dir: str | Path) -> dict:
    path = Path(raw_dir) / MANIFEST
    try:
        doc = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, json.JSONDecodeError):
        doc = {}
    return doc if isinstance(doc, dict) else {}


# --------------------------------------------------------------------------
# The probe
# --------------------------------------------------------------------------

def probe(project_endpoint: str, agent: str | None = None, version: str | None = None, *,
          runner: Runner | None = None, token_provider: TokenProvider | None = None,
          list_tools: bool = True, save_raw: str | Path | None = None,
          as_user: bool = False, mode: str = "live") -> Environment:
    """The observed environment of `agent` (every agent of the project when
    None) at `version` (the current version when None) in the Foundry project
    at `project_endpoint`.  `as_user` attributes the toolbox tool listing to
    the signed-in user rather than to the agent identity."""
    endpoint = project_endpoint.rstrip("/")
    run = runner or live_runner(endpoint, token_provider, save_raw)
    env = Environment()
    project = urlsplit(endpoint).path.rstrip("/").rsplit("/", 1)[-1] or endpoint
    names = [agent] if agent else _attempt(env, "agents", lambda: _agent_names(run)) or []
    detail = f"{mcp._public_url(endpoint)} agent {', '.join(names) or '(none)'}"
    env.sources.append({"adapter": "foundry", "mode": mode, "detail": detail})
    env.add_node("/", "scope", project, level="root", observed=True,
                 endpoint=mcp._public_url(endpoint))
    identities = {name: _agent(run, env, name, version if agent else None) for name in names}
    _toolboxes(run, env, endpoint, list_tools, as_user)
    _connections(run, env)
    for name, oid in identities.items():
        _rbac(run, env, name, oid)
    env.mark_unknown("deny_assignments", "not read by the Foundry probe")
    env.mark_unknown("egress", "the project's network isolation is not read here; measure "
                               "from inside the sandbox")
    if save_raw:
        Path(save_raw).mkdir(parents=True, exist_ok=True)
        (Path(save_raw) / MANIFEST).write_text(json.dumps(
            {"adapter": "foundry", "project_endpoint": mcp._public_url(endpoint),
             "agent": agent, "version": version, "list_tools": list_tools, "as_user": as_user,
             "captured_at": env.captured_at}, indent=1), encoding="utf-8")
    return env


def replay(raw_dir: str | Path, project_endpoint: str | None = None,
           agent: str | None = None, version: str | None = None, *,
           list_tools: bool | None = None, as_user: bool | None = None) -> Environment:
    """`probe` from an export saved with `save_raw`, with no network.  Values
    not given come from the export's manifest."""
    manifest = _manifest(raw_dir)
    endpoint = project_endpoint or manifest.get("project_endpoint")
    if not endpoint:
        raise FoundryProbeError(f"{raw_dir}: no manifest; give the project endpoint")
    env = probe(endpoint, agent or manifest.get("agent"), version or manifest.get("version"),
                runner=replay_runner(raw_dir),
                list_tools=manifest.get("list_tools", True) if list_tools is None else list_tools,
                as_user=bool(manifest.get("as_user")) if as_user is None else as_user,
                mode="replay")
    if manifest.get("captured_at"):
        env.captured_at = manifest["captured_at"]
    return env


def _attempt(env: Environment, what: str, fn: Callable[[], Any]) -> Any:
    """`fn()`, or None with the failure recorded as unknown `what`."""
    try:
        return fn()
    except (azure.ProbeError, mcp.MCPProbeError, KeyError, TypeError, ValueError, OSError,
            subprocess.SubprocessError) as e:
        env.mark_unknown(what, str(e)[:300])
        return None


def _rows(doc: Any) -> list[dict]:
    """The items of a list answer (`data` or `value`), or the list itself."""
    if isinstance(doc, dict):
        doc = doc.get("data") if "data" in doc else doc.get("value")
    return [row for row in (doc or []) if isinstance(row, dict)]


def _agent_names(run: Runner) -> list[str]:
    return [str(a["name"]) for a in _rows(run(["get", f"/agents?api-version={API}"]))
            if a.get("name")]


def _agent(run: Runner, env: Environment, name: str, version: str | None) -> str | None:
    """The agent's principal node; returns its instance identity's object id."""
    key = env.add_node(f"principal/agent/{name}", "principal", name, type="agent",
                       identity_mode="agent", observed=True)

    def read() -> str | None:
        doc = run(["get", f"/agents/{name}?api-version={API}"])
        latest = (doc.get("versions") or {}).get("latest") or {}
        wanted = version or _text(latest.get("version"))
        ver = run(["get", f"/agents/{name}/versions/{wanted}?api-version={API}"]) if wanted \
            else latest
        definition = ver.get("definition") or {}
        identity = ver.get("instance_identity") or doc.get("instance_identity") or {}
        endpoint = doc.get("agent_endpoint") or {}
        code = definition.get("code_configuration") or {}
        entry = code.get("entry_point")
        configured = sorted(endpoint.get("protocol_configuration") or {})
        card = doc.get("agent_card") if isinstance(doc.get("agent_card"), dict) else None
        env.add_node(key, "principal", name,
                     object_id=_text(identity.get("principal_id")),
                     client_id=_text(identity.get("client_id")),
                     agent_kind=_text(definition.get("kind")), version=_text(ver.get("version")),
                     status=_text(ver.get("status")), state=_text(doc.get("state")),
                     cpu=_text(definition.get("cpu")), memory=_text(definition.get("memory")),
                     protocols=[" ".join(_text(v) for v in (p.get("protocol"), p.get("version"))
                                         if _text(v))
                                for p in definition.get("protocol_versions") or []
                                if isinstance(p, dict)] or None,
                     env_vars=sorted(str(k) for k in definition.get("environment_variables")
                                     or {}) or None,
                     runtime=_text(code.get("runtime")),
                     entry_point=" ".join(entry) if isinstance(entry, list) else _text(entry),
                     dependency_resolution=_text(code.get("dependency_resolution")),
                     image=_public_host(definition.get("image")) or _text(definition.get("image")),
                     description=(_text(ver.get("description")) or "")[:200] or None,
                     endpoint_protocols=[str(p) for p in endpoint.get("protocols") or []] or None,
                     protocol_configuration=configured or None, a2a="a2a" in configured,
                     authorization=[_text(s.get("type")) for s in
                                    endpoint.get("authorization_schemes") or []
                                    if isinstance(s, dict)] or None,
                     agent_card=card is not None,
                     agent_card_skills=[_text(s.get("id")) for s in (card or {}).get("skills")
                                        or [] if isinstance(s, dict)] or None,
                     blueprint=_text((doc.get("blueprint_reference") or {}).get("blueprint_id")),
                     created_at=ver.get("created_at"))
        return _text(identity.get("principal_id"))

    return _attempt(env, f"agent:{name}", read)


def _toolboxes(run: Runner, env: Environment, endpoint: str, list_tools: bool,
               as_user: bool) -> None:
    boxes = _attempt(env, "toolboxes", lambda: [
        (str(t["name"]), _text(t.get("default_version")))
        for t in _rows(run(["get", f"/toolboxes?api-version={API}"])) if t.get("name")]) or []
    for name, default in boxes:
        server = env.add_node(f"toolbox/{name}", "mcp_server", name, transport="toolbox",
                              observed=True, version=default)
        if not default:
            env.mark_unknown(f"toolbox:{name}", "no default version")
            continue
        path = f"/toolboxes/{name}/versions/{default}"
        env.add_node(server, "mcp_server", name, url=mcp._public_url(f"{endpoint}{path}/mcp"))

        def declared(name: str = name, path: str = path, server: str = server) -> None:
            ver = run(["get", f"{path}?api-version={API}"])
            env.add_node(server, "mcp_server", name,
                         description=(_text(ver.get("description")) or "")[:200] or None,
                         skills=[_text(s.get("name") or s.get("id")) for s in ver.get("skills")
                                 or [] if isinstance(s, dict)] or None)
            for entry in ver.get("tools") or []:
                if isinstance(entry, dict):
                    _declared_tool(env, server, name, entry)

        _attempt(env, f"toolbox:{name}", declared)
        if not list_tools:
            env.mark_unknown(f"mcp_tools:toolbox/{name}", "tools not listed (--no-list-tools)")
            continue

        def listed(name: str = name, path: str = path, server: str = server) -> None:
            tools = run(["mcp", "tools/list", f"{path}/mcp?api-version={API}"])
            for tool in tools or []:
                node = env.add_node(f"toolbox/{name}/mcp/{tool['name']}", "tool", tool["name"],
                                    description=(tool.get("description") or "")[:200] or None,
                                    observed=True, listed_as="user" if as_user else "agent")
                env.add_edge(server, node, "exposes")
            if not as_user:
                env.mark_unknown(f"mcp_tools_identity:toolbox/{name}",
                                 "listed with the signed-in user's token; the agent identity "
                                 "is assumed to see the same tools")

        _attempt(env, f"mcp_tools:toolbox/{name}", listed)


def _declared_tool(env: Environment, server: str, box: str, entry: dict) -> None:
    """One `tools[]` entry of a toolbox version, with the ids env.azd uses."""
    kind = _text(entry.get("type"))
    if not kind:
        env.mark_unknown(f"toolbox_tool:{box}", "a tools[] entry without a type")
        return
    connection = _text(entry.get("connection")) or _last(entry.get("project_connection_id"))
    label = _text(entry.get("server_label"))
    node_id = f"toolbox/{box}/{kind}"
    if connection:
        node_id += f"/{connection}"
    elif kind == "mcp" and label:
        node_id += f"/{label}"
    tool_name = _text(entry.get("name"))
    node = env.add_node(node_id, "tool", kind, type=kind, observed=True, connection=connection,
                        tool_name=tool_name if tool_name != kind else None, server_label=label,
                        server_url=_public_host(entry.get("server_url")),
                        require_approval=_text(entry.get("require_approval")))
    env.add_edge(server, node, "exposes")
    if kind == "mcp":
        for remote in entry.get("allowed_tools") or []:
            if isinstance(remote, str) and remote:
                env.add_edge(server, env.add_node(f"{node_id}/{remote}", "tool", remote,
                                                  observed=True, via=node_id), "exposes")


def _last(value: Any) -> str | None:
    """The last path segment of a resource id (a connection's name)."""
    text = _text(value)
    return text.rstrip("/").rsplit("/", 1)[-1] if text else None


def _connections(run: Runner, env: Environment) -> None:
    def read() -> None:
        for c in _rows(run(["get", f"/connections?api-version={API}"])):
            name = _text(c.get("name"))
            if not name:
                continue
            creds = c.get("credentials") if isinstance(c.get("credentials"), dict) else {}
            meta = c.get("metadata") if isinstance(c.get("metadata"), dict) else {}
            target = c.get("target")
            env.add_node(f"connection/{name}", "service", name, type="connection",
                         available=True, observed=True, category=_text(c.get("type")),
                         auth_type=_text(creds.get("type")),
                         target=_public_host(target) or mcp._public_url(target),
                         is_default=c.get("isDefault") if isinstance(c.get("isDefault"), bool)
                         else None, location=_text(meta.get("Location")))

    _attempt(env, "connections", read)


def _rbac(run: Runner, env: Environment, name: str, oid: str | None) -> None:
    principal = f"principal/agent/{name}"
    if not oid:
        env.mark_unknown("role_assignments", f"the instance identity of {name} is unknown")
        return
    azure.role_assignments(lambda args: run(["az", *args]), env, principal, oid)
    for node in env.of_kind("role"):
        guid = node["id"].rsplit("/", 1)[-1]
        if guid in KNOWN_ROLES:
            node["attrs"]["role_name"] = KNOWN_ROLES[guid]
            if node["name"] == guid:
                node["name"] = KNOWN_ROLES[guid]


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------

def add_probe_opts(sp: argparse.ArgumentParser) -> None:
    """The `env probe` options of this adapter.  `--save-raw` and `--from-raw`
    are shared with the Azure adapter; they are added only when absent."""
    sp.add_argument("--foundry", action="store_true",
                    help="probe a Foundry project's control plane, read-only, with your "
                         "`az login`: the agent version, the toolboxes and their live tool "
                         "list, the connections, the agent identity's role assignments")
    sp.add_argument("--project", metavar="URL",
                    help="with --foundry: the project endpoint, "
                         "https://<account>.services.ai.azure.com/api/projects/<project>")
    sp.add_argument("--agent", metavar="NAME[:VERSION]",
                    help="with --foundry: the hosted agent (default: every agent, each at "
                         "its current version)")
    sp.add_argument("--no-list-tools", action="store_true",
                    help="with --foundry: do not list the toolbox tools over MCP")
    sp.add_argument("--as-user", action="store_true",
                    help="with --foundry: attribute the toolbox tool list to you, the "
                         "signed-in user, instead of to the agent identity")
    for flags, kw in ((("--save-raw",), {"metavar": "DIR",
                                          "help": "also keep every raw answer under DIR "
                                                  "(sanitised; replayable offline)"}),
                      (("--from-raw",), {"metavar": "DIR",
                                          "help": "replay a saved export instead of calling "
                                                  "the service"})):
        with contextlib.suppress(argparse.ArgumentError):   # defined by another adapter
            sp.add_argument(*flags, **kw)


def probe_from_args(args: argparse.Namespace) -> Environment | None:
    """The environment the arguments ask this adapter for, or None when they
    do not concern it.  `--from-raw DIR` is taken when `--foundry` is given or
    DIR is one of this adapter's exports."""
    foundry = bool(getattr(args, "foundry", False))
    from_raw = getattr(args, "from_raw", None)
    name, version = _split_agent(getattr(args, "agent", None))
    no_list = bool(getattr(args, "no_list_tools", False))
    as_user = bool(getattr(args, "as_user", False))
    if from_raw and (foundry or is_export(from_raw)):
        return replay(from_raw, getattr(args, "project", None), name, version,
                      list_tools=False if no_list else None, as_user=as_user or None)
    if not foundry:
        return None
    if not getattr(args, "project", None):
        raise ValueError("--foundry needs --project URL")
    return probe(args.project, name, version, list_tools=not no_list,
                 save_raw=getattr(args, "save_raw", None), as_user=as_user)


def _split_agent(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    name, _, version = value.partition(":")
    return name or None, version or None

"""Self-probe: the data-plane half of a hosted agent's environment, read from inside.

A hosted agent runs in a per-session sandbox that the developer's laptop knows
nothing about.  This probe runs *inside* that sandbox (a line at container
start, a smoke test in the deploy pipeline, or the watcher) and records what
the container can actually do:

    principal  principal/agent/<name>   identity_mode "agent", the platform
                                        variable *names* (never values)
    scope      /                        the session
    service    sandbox                  cpu_count, memory_gib, free_disk_gib
    service    platform/<name>          linux | windows | macos | mobile_device | gpu
    scope      path:<dir>               $HOME, /files and any named path: exists, writable
    service    program/<name>           on PATH
    service    pymodule/<name>          importable
    service    credential/<NAME>        the variable is set (names only, never values)
    service    app_insights             APPLICATIONINSIGHTS_CONNECTION_STRING is set
    service    egress/<host>            the named host answered
    mcp_server toolbox/<name>           the toolbox, with its tools listed over HTTP MCP

Every node carries `observed: true`, the counterpart of the azd adapter's
`declared: true`, so a merged environment can say which half each fact came
from.  The probe never contacts anything the caller did not name, never
records a secret value, and treats anything it could not observe as unknown.

`egress` and `_non_public_address` below are copies of the two functions of
the same name in `env.claude`, extended with an `inside_network` switch: on a
laptop a host that resolves to a private address is never contacted, but
inside a VNet the private endpoints are the point, so the caller may lift the
refusal explicitly.  `env.claude` is left unchanged.

`merge_hosted` joins this half with the control-plane half (the azd
declaration or the Foundry probe): the data plane wins for what only the
sandbox can observe, the control plane for what only the platform grants.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import ipaddress
import os
import platform as _platform
import re
import shutil
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from .claude import CREDENTIALS, _open
from .model import Environment, now_utc

DEFAULT_PATHS = ("$HOME", "/files")
TOKEN_SCOPE = "https://ai.azure.com/.default"
PLATFORM_PREFIXES = ("AGENT_", "FOUNDRY_")
SECRET_NAME = re.compile(r"(_KEY|_SECRET|_TOKEN|CONNECTION_STRING)$")
AGENT_NAME_VARS = ("FOUNDRY_AGENT_NAME", "AGENT_NAME")
AGENT_VERSION_VARS = ("FOUNDRY_AGENT_VERSION", "AGENT_VERSION")

# Node ids whose facts only the sandbox can observe: the data plane wins for them.
DATA_PLANE_PREFIXES = ("program/", "pymodule/", "egress/", "path:", "sandbox", "platform/")
# Node kinds and ids that only the platform grants: the control plane wins for them.
CONTROL_PLANE_KINDS = ("role", "deny", "policy", "principal")
CONTROL_PLANE_PREFIXES = ("connection/",)


# --------------------------------------------------------------------------
# The probe
# --------------------------------------------------------------------------

def probe(*, hosts: Iterable[str] = (), programs: Iterable[str] = (),
          modules: Iterable[str] = (), paths: Iterable[str] = DEFAULT_PATHS,
          inside_network: bool = False, toolbox_url: str | None = None,
          token_provider: Callable[[], str | None] | None = None, timeout: float = 8.0,
          credentials: Iterable[str] = ()) -> Environment:
    """The data-plane environment of the sandbox this process runs in.

    `hosts`, `programs`, `modules` and `paths` are the only things looked at
    beyond the sandbox's own facts; `credentials` adds variable names to check
    beyond `claude.CREDENTIALS` and the secret-looking names present.  With
    `toolbox_url` the toolbox's tools are listed over HTTP MCP with the token
    `token_provider` returns (azure-identity's DefaultAzureCredential by
    default); the token is used once and never recorded."""
    env = Environment()
    name = _first_env(AGENT_NAME_VARS) or "hosted-agent"
    version = _first_env(AGENT_VERSION_VARS) or "unknown"
    session = os.environ.get("FOUNDRY_AGENT_SESSION_ID") or "none"
    env.sources.append({"adapter": "self", "mode": "live",
                        "detail": f"{name}@{version} session {session}"})
    env.add_node(f"principal/agent/{name}", "principal", name, type="agent",
                 identity_mode="agent", observed=True, session=session,
                 project_host=_public_host(os.environ.get("FOUNDRY_PROJECT_ENDPOINT")),
                 env_vars=sorted(k for k in os.environ if k.startswith(PLATFORM_PREFIXES))
                 or None)
    env.add_node("/", "scope", "session", level="root", observed=True)
    _sandbox(env)
    system = _platform.system().lower()
    for item in ("linux", "windows", "macos", "mobile_device", "gpu"):
        env.add_node(f"platform/{item}", "service", item, type="platform", observed=True,
                     available=item == {"darwin": "macos"}.get(system, system)
                     or (item == "gpu" and shutil.which("nvidia-smi") is not None))
    _paths(env, list(paths))
    for item in dict.fromkeys(programs):
        env.add_node(f"program/{item}", "service", item, type="program", observed=True,
                     available=shutil.which(item) is not None)
    for item in dict.fromkeys(modules):
        env.add_node(f"pymodule/{item}", "service", item, type="python module", observed=True,
                     available=_importable(item))
    for item in _credential_names(credentials):
        env.add_node(f"credential/{item}", "service", item, type="credential", observed=True,
                     available=bool(os.environ.get(item)))
    env.add_node("app_insights", "service", "application insights", type="telemetry",
                 observed=True,
                 available=bool(os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")))
    for host in dict.fromkeys(hosts):
        ok, why = egress(host, timeout, inside_network=inside_network)
        env.add_node(f"egress/{host}", "service", host, type="egress", observed=True,
                     available=ok, why=why, inside_network=inside_network or None)
    if toolbox_url:
        _toolbox(env, toolbox_url, token_provider, timeout)
    return env


def _first_env(names: Iterable[str]) -> str | None:
    return next((os.environ[n] for n in names if os.environ.get(n)), None)


def _credential_names(extra: Iterable[str]) -> list[str]:
    """`claude.CREDENTIALS`, the caller's names, and every variable present
    whose name looks like a secret.  Names only: no value is ever read here."""
    present = sorted(k for k in os.environ if SECRET_NAME.search(k.upper()))
    return list(dict.fromkeys([*CREDENTIALS, *extra, *present]))


def _sandbox(env: Environment) -> None:
    home = _home()
    memory = _memory_gib()
    try:
        free = round(shutil.disk_usage(home).free / 2 ** 30, 2)
    except OSError:
        free = None
    env.add_node("sandbox", "service", "sandbox", type="sandbox", observed=True,
                 cpu_count=os.cpu_count(), memory_gib=memory, free_disk_gib=free,
                 home=str(home))
    if memory is None:
        env.mark_unknown("sandbox:memory_gib", "neither /proc/meminfo nor os.sysconf is available")
    if free is None:
        env.mark_unknown("sandbox:free_disk_gib", f"disk usage of {home} could not be read")


def _memory_gib() -> float | None:
    """Total memory from /proc/meminfo, else os.sysconf, else unknown."""
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                return round(int(line.split()[1]) / 2 ** 20, 2)
    except (OSError, ValueError, IndexError):
        pass
    try:
        return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2 ** 30, 2)
    except (AttributeError, ValueError, OSError):
        return None


def _home() -> Path:
    return Path(os.environ.get("HOME") or Path.home())


def _expand(spec: str) -> Path:
    """`$HOME`, `~` and `${VAR}` expanded; the result is the name of the path node."""
    if spec == "$HOME" or spec.startswith(("$HOME/", "$HOME\\")):
        spec = str(_home()) + spec[len("$HOME"):]
    return Path(os.path.expandvars(spec)).expanduser()


def _paths(env: Environment, specs: list[str]) -> None:
    for spec in dict.fromkeys(specs):
        path = _expand(spec)
        target = next((a for a in (path, *path.parents) if a.exists()), None)
        env.add_node(f"path:{path}", "scope", str(path), level="path", observed=True,
                     alias=spec if spec != str(path) else None, exists=path.exists(),
                     writable=target is not None and os.access(target, os.W_OK)
                     and (target.is_dir() or target == path))
        env.add_edge("/", f"path:{path}", "contains")


def _importable(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


# --------------------------------------------------------------------------
# Egress (copied from env.claude, with the inside-network switch)
# --------------------------------------------------------------------------

def egress(host: str, timeout: float = 8.0, *, inside_network: bool = False) -> tuple[bool, str]:
    """One HEAD request to `host` (HTTPS unless the caller wrote `http://`).

    Any HTTP answer from the host (even 404, 401 or a redirect) proves the
    network path; a 403/407 on the proxy tunnel is the egress policy refusing
    the host.  Hosts can come from intent text, so destinations that resolve
    to loopback, private, link-local or reserved addresses are never contacted
    unless `inside_network` says that private endpoints are the purpose."""
    url = host if host.startswith(("https://", "http://")) else f"https://{host}/"
    if not inside_network:
        blocked = _non_public_address(urllib.parse.urlsplit(url).hostname or "",
                                      urllib.parse.urlsplit(url).port or 443)
        if blocked:
            return False, f"refused: {host} resolves to non-public address {blocked}"
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "skillc-probe"})
    try:
        with _open(req, timeout, ssl.create_default_context(
                cafile=os.environ.get("SSL_CERT_FILE"))) as r:
            return True, f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        return True, f"HTTP {e.code} from the host"
    except urllib.error.URLError as e:
        reason = str(e.reason)
        if "403" in reason or "407" in reason:
            return False, f"egress policy refused the host ({reason})"
        return False, reason[:200]
    except TimeoutError:
        return False, f"no answer within {timeout:g}s"
    except (OSError, ValueError) as e:
        return False, str(e)[:200]


def _non_public_address(hostname: str, port: int = 443) -> str | None:
    """The first non-global address `hostname` resolves to, if any.

    An unresolvable name is left to the proxy, which then decides egress."""
    try:
        infos = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
    except (OSError, UnicodeError):
        return None
    for info in infos:
        address = ipaddress.ip_address(info[4][0].split("%")[0])
        if not address.is_global:
            return str(address)
    return None


def _public_host(url: Any) -> str | None:
    """Scheme and host (and port) only; never a path, query or user info."""
    if not isinstance(url, str) or not url:
        return None
    try:
        parts = urllib.parse.urlsplit(url)
        host, port = parts.hostname, parts.port
    except ValueError:
        return None
    if not parts.scheme or not host:
        return None
    return f"{parts.scheme}://{host}:{port}" if port else f"{parts.scheme}://{host}"


# --------------------------------------------------------------------------
# The toolbox from the inside
# --------------------------------------------------------------------------

def _toolbox_name(url: str) -> str:
    parts = urllib.parse.urlsplit(url).path.strip("/").split("/")
    if "toolboxes" in parts and parts.index("toolboxes") + 1 < len(parts):
        return parts[parts.index("toolboxes") + 1]
    return ""


def _toolbox(env: Environment, url: str, token_provider: Callable[[], str | None] | None,
             timeout: float) -> None:
    """The toolbox's tools listed with the agent identity's token: the
    authoritative tool list for an autonomous run.  The listing itself lives in
    `env.mcp.list_http_tools`, which another work package adds; until it is
    there the toolbox is recorded as unknown, never as empty."""
    name = _toolbox_name(url)
    node_id = f"toolbox/{name}" if name else "toolbox"
    parts = urllib.parse.urlsplit(url)
    server = env.add_node(node_id, "mcp_server", name or "toolbox", transport="toolbox",
                          observed=True, url=urllib.parse.urlunsplit(
                              (parts.scheme, parts.netloc, parts.path, "", "")))
    what = f"mcp_tools:{node_id}"
    try:
        from .mcp import list_http_tools
    except ImportError:
        env.mark_unknown(what, "HTTP MCP listing unavailable")
        return
    token = _token(token_provider)
    if token is None:
        env.mark_unknown(what, f"no token for {TOKEN_SCOPE}: azure-identity is not importable "
                               "and no token provider was given")
        return
    try:
        tools = list_http_tools(url, token, timeout)
    except Exception as e:  # noqa: BLE001 - the listing must never stop the probe
        env.mark_unknown(what, f"tools/list failed: {str(e)[:200]}")
        return
    for tool in tools:
        if not isinstance(tool, dict) or not tool.get("name"):
            continue
        node = env.add_node(f"{node_id}/{tool['name']}", "tool", tool["name"], observed=True,
                            description=(tool.get("description") or "")[:200] or None)
        env.add_edge(server, node, "exposes")


def _token(provider: Callable[[], str | None] | None) -> str | None:
    """The bearer token for the toolbox, used once and never stored in the graph."""
    if provider is not None:
        try:
            return provider() or None
        except Exception:  # noqa: BLE001 - a failing provider is an unknown, not an error
            return None
    try:
        from azure.identity import DefaultAzureCredential
    except ImportError:
        return None
    try:
        return DefaultAzureCredential().get_token(TOKEN_SCOPE).token
    except Exception:  # noqa: BLE001 - no credential available is an unknown
        return None


# --------------------------------------------------------------------------
# Command-line wiring (the cli module adds these to `env probe` and `env watch`)
# --------------------------------------------------------------------------

def add_self_opts(sp: argparse.ArgumentParser) -> None:
    """The `--self` options.  Options the parser already has (`--host`,
    `--program`, ... from the Claude probe) are shared, not redefined."""
    _opt(sp, "--self", action="store_true",
         help="probe the sandbox this process runs in (the data-plane half)")
    _opt(sp, "--host", action="append", help="check egress to HOST")
    _opt(sp, "--program", action="append", help="look for PROGRAM on PATH")
    _opt(sp, "--module", action="append", help="look for a Python module")
    _opt(sp, "--path", action="append", help="check PATH is writable")
    _opt(sp, "--inside-network", action="store_true",
         help="with --self: hosts that resolve to private addresses may be contacted "
              "(private endpoints inside a VNet)")
    _opt(sp, "--toolbox-url", metavar="URL",
         help="with --self: list the toolbox's tools over HTTP MCP with the agent identity")
    _opt(sp, "--needs-from", action="append", metavar="INTENT",
         help="probe what INTENT (a skillc.intent/1 file, a built-in name, a SKILL.md, or a "
              "directory of SKILL.md files) needs")


def _opt(sp: argparse.ArgumentParser, *flags: str, **kwargs: Any) -> None:
    with contextlib.suppress(argparse.ArgumentError):   # already defined: share it
        sp.add_argument(*flags, **kwargs)


def self_probe_from_args(args: argparse.Namespace) -> Environment:
    """The self-probe asked about everything the arguments and their intents name."""
    wanted: dict[str, list[str]] = {"egress": list(getattr(args, "host", None) or []),
                                    "program": list(getattr(args, "program", None) or []),
                                    "pymodule": list(getattr(args, "module", None) or []),
                                    "path": list(getattr(args, "path", None) or []),
                                    "credential": []}
    for intent in intents_named(getattr(args, "needs_from", None) or []):
        for kind, values in _intent_needs(intent).items():
            wanted.setdefault(kind, []).extend(values)
    return probe(hosts=wanted["egress"], programs=wanted["program"], modules=wanted["pymodule"],
                 paths=[*DEFAULT_PATHS, *wanted["path"]], credentials=wanted["credential"],
                 inside_network=bool(getattr(args, "inside_network", False)),
                 toolbox_url=getattr(args, "toolbox_url", None) or None)


def intents_named(specs: Iterable[str]) -> list[dict]:
    """The intents `--needs-from` names: files, built-in names, and every
    `*.md` of a directory (a `skills/` folder)."""
    from .reach import load_intent
    out = []
    for spec in specs:
        path = Path(spec)
        if path.is_dir():
            out += [load_intent(p) for p in sorted(path.glob("*.md")) if p.is_file()]
        else:
            out.append(load_intent(spec))
    return out


def _intent_needs(intent: dict) -> dict[str, list[str]]:
    """Every runtime need the intent's operations and capabilities name, by kind
    (the same walk as `reach.intent_needs`, kept here so the probe needs no cli)."""
    out: dict[str, list[str]] = {}

    def walk(spec: dict) -> None:
        for kind, value in spec.items():
            if kind in ("any", "all"):
                for inner in value:
                    walk(inner)
            elif kind != "arg":
                out.setdefault(kind, []).append(value)

    for item in [*(intent.get("operations") or []), *(intent.get("capabilities") or [])]:
        for spec in item.get("needs") or []:
            walk(spec)
    return out


def hosted_probe_factory(args: argparse.Namespace) -> Callable[[], Environment]:
    """A zero-argument probe for `env.watch.watch_once` that runs the self-probe."""
    return lambda: self_probe_from_args(args)


# --------------------------------------------------------------------------
# Merge rules: control plane (declared or probed from the platform) + data plane
# --------------------------------------------------------------------------

def _data_plane_wins(node: dict) -> bool:
    node_id = node["id"]
    if node_id.startswith(DATA_PLANE_PREFIXES):
        return True
    return node["kind"] == "tool" and node_id.startswith("toolbox/") and bool(
        node["attrs"].get("observed"))


def _control_plane_wins(node: dict) -> bool:
    return node["kind"] in CONTROL_PLANE_KINDS or node["id"].startswith(CONTROL_PLANE_PREFIXES)


def merge_hosted(control: Environment, data: Environment) -> Environment:
    """One environment from the control-plane and the data-plane halves.

    Nodes are the union.  Where both halves carry the same node, the data
    plane wins for programs, Python modules, egress, paths, the sandbox, the
    platform and the toolbox tools it observed; the control plane wins for
    roles, deny rules, policies, connections and the principal's attributes.
    A disagreement on `available` is kept as `conflict:<id>` in `unknown`, so
    a report can show it.  A control-plane unknown that the data plane
    answered (`egress`, `mcp_tools:<toolbox>`) is dropped; everything else
    the two halves could not read stays unknown."""
    out = Environment(captured_at=max(control.captured_at, data.captured_at) or now_utc())
    for node in control.nodes.values():
        out.add_node(node["id"], node["kind"], node["name"], **node["attrs"])
    for node in data.nodes.values():
        declared = control.nodes.get(node["id"])
        if declared is None:
            out.add_node(node["id"], node["kind"], node["name"], **node["attrs"])
            continue
        control_wins = _control_plane_wins(declared) and not _data_plane_wins(node)
        before, after = declared["attrs"].get("available"), node["attrs"].get("available")
        if before is not None and after is not None and before != after:
            used = "declared" if control_wins else "observed"
            out.mark_unknown(f"conflict:{node['id']}",
                             f"declared {before}, observed {after}; {used} used")
        if control_wins:
            out.add_node(node["id"], declared["kind"], declared["name"],
                         **{k: v for k, v in node["attrs"].items() if k not in declared["attrs"]})
        else:
            out.add_node(node["id"], node["kind"], node["name"] or declared["name"],
                         **node["attrs"])
    for env in (control, data):
        for e in env.edges:
            out.add_edge(e["src"], e["dst"], e["kind"], **e["attrs"])
    answered = _answered_by(data)
    for u in control.unknown:
        if u["what"] not in answered:
            out.mark_unknown(u["what"], u.get("why", ""))
    for u in data.unknown:
        out.mark_unknown(u["what"], u.get("why", ""))
    out.sources = [*control.sources, *data.sources]
    return out


def _answered_by(data: Environment) -> set[str]:
    """The unknowns of the other half that this half's observations settle."""
    answered: set[str] = set()
    if any(n["id"].startswith("egress/") for n in data.nodes.values()) and not data.is_unknown(
            "egress"):
        answered.add("egress")
    for e in data.edges:
        if e["kind"] == "exposes" and e["src"].startswith("toolbox/"):
            answered.add(f"mcp_tools:{e['src']}")
    return answered

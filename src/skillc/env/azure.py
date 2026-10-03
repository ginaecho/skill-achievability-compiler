"""Azure adapter: a read-only probe of what the signed-in principal can do.

The probe never changes anything.  Every call goes through a *runner*:

    live_runner()          runs `az ... -o json` (read-only commands only)
    live_runner(save_raw)  ... and keeps every raw answer under `save_raw`
    replay_runner(dir)     answers from such a directory, offline

It reads the account and principal, resource groups and resources, resource
provider registrations, the principal's role assignments (inherited and via
groups) with their role definitions, deny assignments, and policy
assignments.  Whatever fails is recorded in `Environment.unknown`.

Policies are interpreted only where their semantics are known exactly: the
built-in "Allowed locations", "Allowed resource types" and "Not allowed
resource types" definitions (Azure/azure-policy, built-in-policies/General).
Any other policy with a deny effect is kept as an uninterpreted deny, which
reasoning treats as an assumption, never as a refusal.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from collections.abc import Callable
from importlib import resources
from pathlib import Path
from typing import Any

from .model import Environment, norm_id

ARM = "https://management.azure.com"
ROLE_API = "2022-04-01"
POLICY_API = "2023-04-01"
EVERYONE = "00000000-0000-0000-0000-000000000000"

# built-in policy definition id -> (rule kind, list parameter)
KNOWN_POLICIES = {
    "e56962a6-4747-49cd-b67b-bf8b01975c4c": ("allowed_locations", "listOfAllowedLocations"),
    "a08ec900-254a-4555-9bf5-e42af04b5c5c": ("allowed_types", "listOfResourceTypesAllowed"),
    "6c112d4e-5bc7-47ae-a041-ea2d9dccd749": ("denied_types", "listOfResourceTypesNotAllowed"),
}

Runner = Callable[[list[str]], Any]


class ProbeError(RuntimeError):
    """An `az` call failed, or the command is not read-only."""


# --------------------------------------------------------------------------
# Runners
# --------------------------------------------------------------------------

def _assert_read_only(args: list[str]) -> None:
    """Only `... show`, `... list` and `rest --method get` ever run."""
    first_flag = next((i for i, a in enumerate(args) if a.startswith("-")), len(args))
    command = args[:first_flag]
    if command == ["rest"]:
        method = args[args.index("--method") + 1].lower() if "--method" in args else ""
        if method != "get":
            raise ProbeError(f"refusing non-GET az rest call: {' '.join(args)}")
    elif not command or command[-1] not in ("show", "list"):
        raise ProbeError(f"refusing a command that is not show/list: az {' '.join(args)}")


def raw_key(args: list[str]) -> str:
    """Stable file name for one command's raw answer."""
    text = " ".join(args)
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:60]
    return f"{slug}_{hashlib.sha1(text.encode()).hexdigest()[:8]}.json"


def live_runner(save_raw: str | Path | None = None, timeout: int = 120) -> Runner:
    exe = shutil.which("az") or shutil.which("az.cmd")
    raw_dir = Path(save_raw) if save_raw else None

    def run(args: list[str]) -> Any:
        _assert_read_only(args)
        if exe is None:
            raise ProbeError("the Azure CLI (az) is not installed; sign in with `az login`")
        proc = subprocess.run([exe, *args, "-o", "json"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout, check=False)
        if proc.returncode:
            raise ProbeError((proc.stderr or proc.stdout).strip()[:500] or "az failed")
        data = json.loads(proc.stdout) if proc.stdout.strip() else None
        if raw_dir is not None:
            raw_dir.mkdir(parents=True, exist_ok=True)
            (raw_dir / raw_key(args)).write_text(
                json.dumps({"command": ["az", *args], "output": data}, indent=1),
                encoding="utf-8")
        return data

    return run


def replay_runner(raw_dir: str | Path) -> Runner:
    root = Path(raw_dir)

    def run(args: list[str]) -> Any:
        _assert_read_only(args)
        path = root / raw_key(args)
        if not path.exists():
            raise ProbeError(f"not in the export: az {' '.join(args)}")
        return json.loads(path.read_text(encoding="utf-8"))["output"]

    return run


def builtin_roles() -> dict[str, dict]:
    """Built-in role definitions by role id (MicrosoftDocs built-in-roles)."""
    raw = resources.files("skillc").joinpath("data/env/azure_builtin_roles.json")
    return {r["id"]: {"name": name, **r}
            for name, r in json.loads(raw.read_text(encoding="utf-8")).items()}


# --------------------------------------------------------------------------
# The probe
# --------------------------------------------------------------------------

def probe(run: Runner, subscription: str | None = None, mode: str = "live") -> Environment:
    """Build the environment the signed-in principal sees in one subscription."""
    account = run(["account", "show", *(["--subscription", subscription] if subscription else [])])
    env = Environment()
    detail = f"subscription {account['id']} (tenant {account.get('tenantId')})"
    env.sources.append({"adapter": "azure", "mode": mode, "detail": detail})
    sub = f"/subscriptions/{account['id']}"
    env.add_node("/", "scope", "root", level="root")
    env.add_node(sub, "scope", account.get("name") or account["id"], level="subscription")
    env.add_edge("/", sub, "contains")
    principal, oid = _principal(run, env, account.get("user") or {})
    _scopes_and_resources(run, env, sub)
    _services(run, env)
    _role_assignments(run, env, principal, oid, account.get("user") or {}, sub)
    _deny_assignments(run, env, principal, oid, sub)
    _policies(run, env, sub)
    return env


def _attempt(env: Environment, what: str, fn: Callable[[], None]) -> None:
    try:
        fn()
    except (ProbeError, KeyError, TypeError, ValueError, OSError,
            subprocess.SubprocessError) as e:
        env.mark_unknown(what, str(e)[:300])


def _principal(run: Runner, env: Environment, user: dict) -> tuple[str, str | None]:
    kind = user.get("type", "user")
    oid = None
    try:
        me = (run(["ad", "signed-in-user", "show"]) if kind == "user"
              else run(["ad", "sp", "show", "--id", user.get("name", "")]))
        oid = me.get("id")
    except ProbeError as e:
        env.mark_unknown("principal_object_id", str(e)[:300])
    key = env.add_node(f"principal/{oid or user.get('name', 'unknown')}", "principal",
                       user.get("name", "unknown"), type=kind, object_id=oid)
    return key, oid


def _scopes_and_resources(run: Runner, env: Environment, sub: str) -> None:
    def groups() -> None:
        for g in run(["group", "list"]) or []:
            env.add_node(g["id"], "scope", g["name"], level="resource_group",
                         location=g.get("location"))
            env.add_edge(sub, g["id"], "contains")

    def items() -> None:
        for r in run(["resource", "list"]) or []:
            env.add_node(r["id"], "resource", r["name"], type=r["type"],
                         location=r.get("location"))
            parent = re.match(r"(/subscriptions/[^/]+/resourcegroups/[^/]+)", norm_id(r["id"]))
            env.add_edge(parent.group(1) if parent else sub, r["id"], "contains")

    _attempt(env, "resource_groups", groups)
    _attempt(env, "resources", items)


def _services(run: Runner, env: Environment) -> None:
    def providers() -> None:
        rows = run(["provider", "list", "--query",
                    "[].{namespace:namespace, registrationState:registrationState}"])
        for p in rows or []:
            env.add_node(f"service/{p['namespace']}", "service", p["namespace"],
                         registered=p.get("registrationState") == "Registered")

    _attempt(env, "services", providers)


def _ensure_scope(env: Environment, scope: str, sub: str) -> None:
    """Make an assignment's scope a node (management groups sit above `sub`)."""
    if norm_id(scope) in env.nodes:
        return
    if "/managementgroups/" in norm_id(scope):
        env.add_node(scope, "scope", scope.rsplit("/", 1)[-1], level="management_group")
        env.add_edge("/", scope, "contains")
        env.add_edge(scope, sub, "contains")


def _role_assignments(run: Runner, env: Environment, principal: str, oid: str | None,
                      user: dict, sub: str) -> None:
    builtin = builtin_roles()
    definitions: dict[str, dict] = {}

    def definition(role_def_id: str) -> dict:
        guid = role_def_id.rsplit("/", 1)[-1].lower()
        if guid not in definitions:
            try:
                props = run(["rest", "--method", "get", "--url",
                             f"{ARM}{role_def_id}?api-version={ROLE_API}"])["properties"]
                perms = props.get("permissions") or [{}]
                definitions[guid] = {
                    "name": props.get("roleName", guid),
                    **{key: [x for p in perms for x in p.get(src) or []]
                       for key, src in (("actions", "actions"), ("not_actions", "notActions"),
                                        ("data_actions", "dataActions"),
                                        ("not_data_actions", "notDataActions"))}}
            except (ProbeError, KeyError, TypeError) as e:
                known = builtin.get(guid)
                definitions[guid] = (
                    {"name": known["name"], "actions": known["actions"],
                     "not_actions": known["notActions"], "data_actions": known["dataActions"],
                     "not_data_actions": known["notDataActions"], "source": "built-in table"}
                    if known else {"name": guid, "definition_unknown": True,
                                   "why": str(e)[:200]})
        return definitions[guid]

    def assignments() -> None:
        who = ["--assignee-object-id", oid] if oid else ["--assignee", user.get("name", "")]
        rows = run(["role", "assignment", "list", "--all", "--include-inherited",
                    "--include-groups", "--fill-principal-name", "false",
                    "--fill-role-definition-name", "false", *who])
        for a in rows or []:
            rd = a["roleDefinitionId"]
            d = definition(rd)
            role = env.add_node(f"role/{rd.rsplit('/', 1)[-1]}", "role", d["name"],
                                **{k: v for k, v in d.items() if k != "name"})
            _ensure_scope(env, a["scope"], sub)
            env.add_edge(principal, role, "assigned", scope=a["scope"],
                         condition=a.get("condition") or None)

    _attempt(env, "role_assignments", assignments)


def _deny_assignments(run: Runner, env: Environment, principal: str, oid: str | None,
                      sub: str) -> None:
    def denies() -> None:
        rows = run(["rest", "--method", "get", "--url",
                    f"{ARM}{sub}/providers/Microsoft.Authorization/denyAssignments"
                    f"?api-version={ROLE_API}"])["value"]
        for row in rows:
            p = row["properties"]
            ids = {x.get("id") for x in p.get("principals") or []}
            excluded = {x.get("id") for x in p.get("excludePrincipals") or []}
            groups = [x for x in p.get("principals") or [] if x.get("type") == "Group"]
            if oid in excluded:
                continue
            if oid in ids or EVERYONE in ids:
                perms = p.get("permissions") or [{}]
                rule = env.add_node(row["id"], "deny", p.get("denyAssignmentName") or row["name"],
                                    **{key: [x for q in perms for x in q.get(src) or []]
                                       for key, src in (("actions", "actions"),
                                                        ("not_actions", "notActions"),
                                                        ("data_actions", "dataActions"),
                                                        ("not_data_actions", "notDataActions"))})
                _ensure_scope(env, p["scope"], sub)
                env.add_edge(principal, rule, "denied", scope=p["scope"])
            elif groups:
                env.mark_unknown("deny_assignments",
                                 "deny assignments target groups whose membership was not "
                                 "resolved")

    _attempt(env, "deny_assignments", denies)


def _policies(run: Runner, env: Environment, sub: str) -> None:
    def assignments() -> None:
        rows = run(["rest", "--method", "get", "--url",
                    f"{ARM}{sub}/providers/Microsoft.Authorization/policyAssignments"
                    f"?api-version={POLICY_API}"])["value"]
        for row in rows:
            p = row["properties"]
            rule, effect = _interpret(run, p)
            node = env.add_node(row["id"], "policy", p.get("displayName") or row["name"],
                                effect=effect, rule=rule,
                                enforced=p.get("enforcementMode", "Default") != "DoNotEnforce",
                                definition=p.get("policyDefinitionId"))
            _ensure_scope(env, p["scope"], sub)
            env.add_edge(node, p["scope"], "applies", not_scopes=p.get("notScopes") or None)

    _attempt(env, "policies", assignments)


def _interpret(run: Runner, assignment: dict) -> tuple[dict, str]:
    """(rule, effect) of one policy assignment; unknown rules stay uninterpreted."""
    def_id = assignment.get("policyDefinitionId", "")
    params = {k: (v or {}).get("value") for k, v in (assignment.get("parameters") or {}).items()}
    guid = def_id.rsplit("/", 1)[-1].lower()
    definition: dict = {}
    if "/policysetdefinitions/" not in def_id.lower():
        try:
            definition = run(["rest", "--method", "get", "--url",
                              f"{ARM}{def_id}?api-version={POLICY_API}"])["properties"]
        except (ProbeError, KeyError, TypeError):
            definition = {}
    defaults = {k: (v or {}).get("defaultValue")
                for k, v in (definition.get("parameters") or {}).items()}
    if guid in KNOWN_POLICIES:
        kind, param = KNOWN_POLICIES[guid]
        effect = params.get("effect") or defaults.get("effect") or "Deny"
        return {"kind": kind, "values": params.get(param) or defaults.get(param) or []}, \
            effect.lower()
    then = ((definition.get("policyRule") or {}).get("then") or {}).get("effect", "")
    ref = re.fullmatch(r"\[parameters\('(\w+)'\)\]", then or "")
    effect = (params.get(ref.group(1)) or defaults.get(ref.group(1))) if ref else then
    # unreadable definitions and initiatives may deny: keep them, uninterpreted
    return {"kind": "uninterpreted"}, (effect or "deny").lower()

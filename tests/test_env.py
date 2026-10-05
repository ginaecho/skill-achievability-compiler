"""Environment topology: model, facts, adapters, reach, outputs, watcher."""
from __future__ import annotations

import json
import sys
import textwrap

import pytest
from env_fixtures import (OID, RG, RG_DATA, ROLE, STORE, SUB, assignment, role_def_id,
                          write_export)

from skillc.cli import main
from skillc.env import azure, mcp
from skillc.env.facts import can, policy_allows, service_available
from skillc.env.model import EnvError, Environment, diff, merge, validate_env
from skillc.env.reach import granting_roles, load_intent, reach
from skillc.env.report import english_plan, html_page, text_report
from skillc.frontend.ce import parse_ce

DT_WRITE = "Microsoft.DigitalTwins/digitalTwinsInstances/write"
MODELS_WRITE = "Microsoft.DigitalTwins/models/write"
BLOB_READ = "Microsoft.Storage/storageAccounts/blobServices/containers/blobs/read"


def probe(tmp_path, assignments, **kw) -> Environment:
    return azure.probe(azure.replay_runner(write_export(tmp_path / "export", assignments, **kw)),
                       mode="replay")


CONTRIBUTOR = [assignment("contributor", RG), assignment("blob_reader", STORE)]
OWNER = [assignment("owner", SUB), assignment("blob_reader", STORE)]


# --------------------------------------------------------------------------
# Permissions (Azure RBAC semantics)
# --------------------------------------------------------------------------

def test_contributor_controls_resources_but_has_no_data_plane_access(tmp_path):
    env = probe(tmp_path, CONTRIBUTOR)
    assert can(env, DT_WRITE, RG).value is True
    assert can(env, MODELS_WRITE, RG, data=True).value is False
    # notActions: Microsoft.Authorization/*/Write
    assert can(env, "Microsoft.Authorization/roleAssignments/write", RG).value is False


def test_a_role_applies_below_its_scope_and_not_beside_it(tmp_path):
    env = probe(tmp_path, [assignment("contributor", RG)])
    assert can(env, DT_WRITE, f"{RG}/providers/Microsoft.DigitalTwins/digitalTwinsInstances/x").value
    assert can(env, DT_WRITE, RG_DATA).value is False
    assert can(env, DT_WRITE, SUB).value is False


def test_owner_at_subscription_can_assign_roles_everywhere_below(tmp_path):
    env = probe(tmp_path, OWNER)
    assert can(env, "Microsoft.Authorization/roleAssignments/write", RG).value is True
    assert can(env, MODELS_WRITE, RG, data=True).value is False     # Owner has no dataActions


def test_data_actions_come_only_from_data_roles(tmp_path):
    env = probe(tmp_path, [assignment("dt_owner", RG)])
    assert can(env, MODELS_WRITE, RG, data=True).value is True
    assert can(env, MODELS_WRITE, RG).value is False                 # not a control action
    assert can(env, BLOB_READ, STORE, data=True).value is False


def test_deny_assignment_overrides_an_allow(tmp_path):
    deny = [{"id": f"{SUB}/providers/Microsoft.Authorization/denyAssignments/d1", "name": "d1",
             "properties": {"denyAssignmentName": "protect twins", "scope": RG,
                            "principals": [{"id": OID, "type": "User"}],
                            "permissions": [{"actions": ["Microsoft.DigitalTwins/*"]}]}}]
    env = probe(tmp_path, OWNER, deny=deny)
    fact = can(env, DT_WRITE, RG)
    assert fact.value is False and "protect twins" in fact.reasons[0]


def test_a_conditioned_assignment_is_not_a_definite_grant(tmp_path):
    env = probe(tmp_path, [{**assignment("contributor", RG), "condition": "@Resource[...]"}])
    assert can(env, DT_WRITE, RG).value is None


def test_role_definitions_fall_back_to_the_built_in_table_offline(tmp_path):
    env = probe(tmp_path, CONTRIBUTOR)                 # export has no definition answers
    role = next(n for n in env.of_kind("role") if n["name"] == "Contributor")
    assert role["attrs"]["source"] == "built-in table"


def test_granting_roles_lists_the_narrowest_first():
    assert granting_roles([MODELS_WRITE], data=True)[0] == "Azure Digital Twins Data Owner"
    roles = granting_roles(["Microsoft.Authorization/roleAssignments/write"])
    assert roles.index("User Access Administrator") < roles.index("Owner")
    assert "Contributor" not in roles


# --------------------------------------------------------------------------
# Policies and services
# --------------------------------------------------------------------------

def test_allowed_locations_policy_denies_other_regions(tmp_path):
    env = probe(tmp_path, OWNER)
    dt = "Microsoft.DigitalTwins/digitalTwinsInstances"
    assert policy_allows(env, dt, "westeurope", RG).value is True
    fact = policy_allows(env, dt, "eastus", RG)
    assert fact.value is False and "westeurope" in fact.reasons[0]


def test_policy_not_enforced_or_excluded_does_not_deny(tmp_path):
    env = probe(tmp_path, OWNER)
    policy = env.of_kind("policy")[0]
    policy["attrs"]["enforced"] = False
    assert policy_allows(env, "x/y", "eastus", RG).value is True
    policy["attrs"]["enforced"] = True
    env.edges[[e["kind"] for e in env.edges].index("applies")]["attrs"]["not_scopes"] = [RG]
    assert policy_allows(env, "x/y", "eastus", RG).value is True


def test_uninterpreted_deny_policy_is_an_assumption_never_a_refusal(tmp_path):
    env = probe(tmp_path, OWNER)
    env.of_kind("policy")[0]["attrs"]["rule"] = {"kind": "uninterpreted"}
    fact = policy_allows(env, "x/y", "eastus", RG)
    assert fact.value is None and fact.possible and fact.assuming()


def test_service_registration(tmp_path):
    env = probe(tmp_path, OWNER)
    assert service_available(env, "Microsoft.DigitalTwins").value is True
    assert service_available(env, "Microsoft.Devices").value is False


# --------------------------------------------------------------------------
# Probing: read-only, replayable, honest about what it could not read
# --------------------------------------------------------------------------

@pytest.mark.parametrize("args", [
    ["group", "create", "--name", "x"],
    ["role", "assignment", "create", "--role", "Owner"],
    ["rest", "--method", "put", "--url", "https://management.azure.com/x"],
    ["rest", "--url", "https://management.azure.com/x"],
])
def test_the_probe_refuses_anything_but_reads(args):
    with pytest.raises(azure.ProbeError, match="refusing"):
        azure._assert_read_only(args)


def test_read_commands_pass_the_guard():
    azure._assert_read_only(["role", "assignment", "list", "--assignee-object-id", OID])
    azure._assert_read_only(["rest", "--method", "get", "--url", "https://x"])


def test_unreadable_facts_are_recorded_and_never_block(tmp_path):
    env = probe(tmp_path, CONTRIBUTOR, fail=("role assignment",))
    assert env.is_unknown("role_assignments")
    assert can(env, MODELS_WRITE, RG, data=True).value is None
    result = reach(load_intent("building-topology"), env)
    assert not result.blocked                       # nothing refuted on an unknown
    assert set(result.status.values()) == {"assumed"}
    assert result.assumptions


def test_environment_round_trips_and_validates(tmp_path):
    env = probe(tmp_path, CONTRIBUTOR)
    env.save(tmp_path / "env.json")
    again = Environment.load(tmp_path / "env.json")
    assert again.to_dict() == env.to_dict()
    bad = env.to_dict()
    bad["edges"].append({"src": "nope", "dst": "/", "kind": "contains"})
    with pytest.raises(EnvError, match="not a node"):
        validate_env(bad)


def test_diff_names_what_changed(tmp_path):
    old = probe(tmp_path / "a", CONTRIBUTOR)
    new = probe(tmp_path / "b", [*CONTRIBUTOR, assignment("dt_owner", RG)])
    changes = diff(old, new)
    assert any("Azure Digital Twins Data Owner" in line for line in changes["added"])
    assert not changes["removed"]


# --------------------------------------------------------------------------
# Reach: the largest achievable part, a verified plan, certified blockers
# --------------------------------------------------------------------------

def test_contributor_can_create_the_instance_but_not_load_the_topology(tmp_path):
    result = reach(load_intent("building-topology"), probe(tmp_path, CONTRIBUTOR))
    assert result.status == {"dt_instance": "achievable", "building_data": "achievable",
                             "dt_models": "blocked", "topology_twins": "blocked",
                             "topology_relationships": "blocked",
                             "topology_queryable": "blocked"}
    assert result.plan_verdict.label == "ACHIEVABLE"
    assert [s.op for s in result.plan] == ["create_dt_instance", "read_building_data"]
    for verdict in result.certificates.values():
        assert verdict.reason == "GOAL_UNSAT" and verdict.context_refuted
    fixes = " ".join(u for b in result.blockers for u in b.unblock)
    assert "Azure Digital Twins Data Owner" in fixes and "User Access Administrator" in fixes


def test_owner_reaches_the_whole_topology_by_granting_itself_data_access(tmp_path):
    result = reach(load_intent("building-topology"), probe(tmp_path, OWNER))
    assert result.complete and not result.blockers
    ops = [s.op for s in result.plan]
    assert ops.index("grant_dt_data_owner") < ops.index("upload_models") \
        < ops.index("create_twins") < ops.index("create_relationships") < ops.index("query_topology")
    assert result.plan_verdict.label == "ACHIEVABLE"


def test_a_location_the_policy_forbids_blocks_creation_with_the_fix(tmp_path):
    intent = load_intent("building-topology")
    intent["target"]["location"] = "eastus"
    result = reach(intent, probe(tmp_path, OWNER))
    assert result.status["dt_instance"] == "blocked"
    blocker = next(b for b in result.blockers if b.op == "create_dt_instance")
    assert "eastus" in blocker.why[0]
    assert "westeurope" in blocker.unblock[0]


def test_an_unregistered_provider_is_registered_when_allowed(tmp_path):
    result = reach(load_intent("building-topology"),
                   probe(tmp_path, OWNER, registered=("Microsoft.Storage",)))
    assert "register_digital_twins" in [s.op for s in result.plan]
    blocked = reach(load_intent("building-topology"),
                    probe(tmp_path / "c", CONTRIBUTOR, registered=("Microsoft.Storage",)))
    assert blocked.status["dt_instance"] == "blocked"     # Contributor at rg cannot register


def test_an_mcp_tool_can_stand_in_for_a_missing_permission(tmp_path):
    env = probe(tmp_path, [assignment("contributor", RG)])          # no blob reader
    assert reach(load_intent("building-topology"), env).status["building_data"] == "blocked"
    server = env.add_node("mcp/files", "mcp_server", "files", transport="stdio")
    env.add_edge(server, env.add_node("mcp/files/read_file", "tool", "read_file"), "exposes")
    result = reach(load_intent("building-topology"), env)
    assert result.status["building_data"] == "assumed"
    assert any("MCP tool read_file" in a for a in result.assumptions)


# --------------------------------------------------------------------------
# Outputs
# --------------------------------------------------------------------------

def test_outputs_say_the_same_thing(tmp_path):
    env = probe(tmp_path, CONTRIBUTOR)
    result = reach(load_intent("building-topology"), env)
    text = text_report(result)
    assert "2/6 conditions achievable" in text and "resource group rg-building" in text
    plan = english_plan(result)
    ce = plan.split("```ce\n", 1)[1].split("```", 1)[0]
    assert parse_ce(ce)["protocol"] == result.pack["protocol"]
    page = html_page(env, result)
    assert page.startswith("<!doctype html>") and "prefers-color-scheme: dark" in page
    assert page.count("<svg") == 2 and "Azure Digital Twins Data Owner" in page


# --------------------------------------------------------------------------
# MCP adapter
# --------------------------------------------------------------------------

FAKE_SERVER = textwrap.dedent('''
    import json, sys
    tools = [[{"name": "read_file"}], [{"name": "list_dir"}]]
    for line in sys.stdin:
        msg = json.loads(line)
        if "id" not in msg:
            continue
        if msg["method"] == "initialize":
            result = {"protocolVersion": msg["params"]["protocolVersion"],
                      "capabilities": {"tools": {}}, "serverInfo": {"name": "fake"}}
        elif msg["method"] == "tools/list":
            page = 1 if (msg.get("params") or {}).get("cursor") else 0
            result = {"tools": tools[page], **({"nextCursor": "p2"} if page == 0 else {})}
        print("log line that is not JSON-RPC", flush=True)
        print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result}), flush=True)
''')


def test_mcp_config_is_read_without_secret_values(tmp_path):
    cfg = tmp_path / ".mcp.json"
    cfg.write_text(json.dumps({"mcpServers": {"az": {"command": "npx", "args": ["x"],
                                                     "env": {"KEY": "s3cret"}},
                                              "web": {"type": "http", "url": "https://x/mcp"}}}))
    env = mcp.probe([cfg])
    assert {s["name"] for s in env.of_kind("mcp_server")} == {"az", "web"}
    assert "s3cret" not in json.dumps(env.to_dict())
    assert env.is_unknown("mcp_tools:az")


def test_stdio_tools_are_listed_across_pages(tmp_path):
    script = tmp_path / "server.py"
    script.write_text(FAKE_SERVER)
    cfg = tmp_path / ".mcp.json"
    cfg.write_text(json.dumps({"mcpServers": {"files": {"command": sys.executable,
                                                        "args": [str(script)]}}}))
    env = mcp.probe([cfg], list_tools=True)
    assert sorted(t["name"] for t in env.of_kind("tool")) == ["list_dir", "read_file"]
    assert not env.unknown


def test_merge_keeps_both_adapters(tmp_path):
    cfg = tmp_path / ".mcp.json"
    cfg.write_text(json.dumps({"mcpServers": {"az": {"command": "npx"}}}))
    env = merge(probe(tmp_path, CONTRIBUTOR), mcp.probe([cfg]))
    assert env.principal() and env.of_kind("mcp_server")
    assert {s["adapter"] for s in env.sources} == {"azure", "mcp"}


# --------------------------------------------------------------------------
# CLI and the watcher
# --------------------------------------------------------------------------

def test_cli_probe_reach_and_outputs(tmp_path, capsys):
    export = write_export(tmp_path / "export", CONTRIBUTOR)
    env_file = tmp_path / "env.json"
    assert main(["env", "probe", "--from-raw", str(export), "-o", str(env_file)]) == 0
    code = main(["reach", "building-topology", "--env", str(env_file),
                 "--plan", str(tmp_path / "plan.md"), "--html", str(tmp_path / "r.html")])
    assert code == 1                                   # something is blocked
    assert (tmp_path / "plan.md").exists() and (tmp_path / "r.html").exists()
    capsys.readouterr()
    assert main(["reach", "building-topology", "--env", str(env_file), "--json"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["schema"] == "skillc.reach/1" and out["complete"] is False


def test_cli_reach_exit_codes(tmp_path):
    owner = tmp_path / "owner.json"
    probe(tmp_path / "o", OWNER).save(owner)
    assert main(["reach", "building-topology", "--env", str(owner)]) == 0
    unknown = tmp_path / "unknown.json"
    probe(tmp_path / "u", CONTRIBUTOR, fail=("role assignment",)).save(unknown)
    assert main(["reach", "building-topology", "--env", str(unknown)]) == 3


def test_cli_probe_needs_a_source(capsys):
    assert main(["env", "probe", "-o", "x.json"]) == 2
    assert "say what to probe" in capsys.readouterr().err


def test_watch_reports_status_changes_between_rounds(tmp_path, capsys):
    first = write_export(tmp_path / "e1", CONTRIBUTOR)
    second = write_export(tmp_path / "e2", [*CONTRIBUTOR, assignment("dt_owner", RG)])
    watch_dir = tmp_path / "watch"
    args = ["env", "watch", "--dir", str(watch_dir), "--intent", "building-topology", "--once"]
    assert main([*args, "--from-raw", str(first)]) == 0
    capsys.readouterr()
    assert main([*args, "--from-raw", str(second)]) == 0
    report = json.loads(capsys.readouterr().out)
    changed = report["status_changes"]["building-topology"]
    assert changed["topology_queryable"] == {"was": "blocked", "now": "achievable"}
    assert any("Data Owner" in line for line in report["environment_changes"]["added"])
    assert len(list(watch_dir.glob("env-*.json"))) >= 1 and (watch_dir / "latest.json").exists()


def test_fixture_role_ids_are_the_documented_built_ins():
    from skillc.env.azure import builtin_roles
    roles = builtin_roles()
    assert {roles[ROLE[k]]["name"] for k in ROLE} == {
        "Owner", "Contributor", "Storage Blob Data Reader", "Azure Digital Twins Data Owner"}
    assert role_def_id(ROLE["owner"]).endswith(ROLE["owner"])

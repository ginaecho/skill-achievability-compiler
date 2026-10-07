"""Runtime monitor (skillc.monitor): plan gate, reasoning, actions, observations, and the
Claude Code hook protocol."""
import json
import subprocess
import sys


from pathlib import Path

from skillc.frontend.runtime import load_runtime
from skillc.monitor import (ALLOW, DENY, WARN, Config, Monitor, Rule, eval_formula, is_failure,
                            thinking_since, tool_map_from_names, unmet_atoms)

FINANCE_CE = (Path(__file__).resolve().parent.parent / "examples" / "hosted-agent-finance"
              / "protocol" / "quarterly_finance_report.ce").read_text(encoding="utf-8")

GOOD = """Skill `fix-tests`.
Roles: `agent`.
Tool `run_tests` (owner `agent`): via `bash`; adds `tests_run`.
Tool `edit_code` (owner `agent`): via `edit`; requires `tests_run`; adds `fixed`.
Goal: `fixed`.
Protocol:
  - `agent` uses `run_tests`.
  - `agent` uses `edit_code`.
"""

DEPLOY = GOOD.replace(
    "Goal: `fixed`.",
    "Tool `deploy` (owner `agent`): via `bash`; needs `vercel_account`; requires `fixed`; "
    "adds `deployed`.\nGoal: `fixed` and `deployed`.").replace(
    "  - `agent` uses `edit_code`.\n", "  - `agent` uses `edit_code`.\n  - `agent` uses `deploy`.\n")

OPTIONAL_DEPLOY = GOOD.replace(
    "Goal: `fixed`.",
    "Tool `deploy` (owner `agent`): via `bash`; needs `vercel_account`; requires `fixed`; "
    "adds `deployed`.\nGoal: `fixed`.") + (
    "  - `agent` chooses one of (observed):\n"
    "    - branch `ship`:\n      - `agent` uses `deploy`.\n"
    "    - branch `skip`: none.\n")

PANDOC = GOOD.replace("via `edit`; requires", "via `bash`; runs `pandoc`; requires")


def mon(tmp_path, **kw) -> Monitor:
    return Monitor(Config(**kw), tmp_path)


def test_only_achievable_plan_is_approved(tmp_path):
    m = mon(tmp_path)
    assert m.submit_plan(DEPLOY).action == DENY          # needs an account the runtime lacks
    assert m.state.plan is None
    d = m.submit_plan(OPTIONAL_DEPLOY)                    # deploy is skippable -> achievable
    assert d.action == ALLOW and m.state.plan == OPTIONAL_DEPLOY


def test_refusal_names_the_witness(tmp_path):
    d = mon(tmp_path).submit_plan(DEPLOY)
    assert "deploy" in d.witness and "vercel_account" in d.reason


def test_unparsable_plan_is_denied_with_location(tmp_path):
    d = mon(tmp_path).submit_plan("Skill `x`.\nTool deploy.\n")
    assert d.action == DENY and "does not parse" in d.reason


def test_implementation_is_gated_on_an_approved_plan(tmp_path):
    m = mon(tmp_path)
    assert m.pre_action("Read", {"file_path": "a.py"}).action == ALLOW    # looking is free
    assert m.pre_action("Bash", {"command": "pytest"}).action == DENY     # no plan yet
    m.submit_plan(GOOD)
    assert m.pre_action("Bash", {"command": "pytest -q"}).action == ALLOW
    assert m.pre_action("Edit", {"file_path": "a.py", "new_string": "x"}).action == ALLOW
    # plan conformance: the plan binds no Tool via `write`
    assert m.pre_action("Write", {"file_path": "b.py", "content": "x"}).action == DENY


def test_writing_the_plan_file_is_the_submission(tmp_path):
    m = mon(tmp_path)
    plan = str(tmp_path / ".skillc" / "plan.ce")
    assert m.pre_action("Write", {"file_path": plan, "content": DEPLOY}).action == DENY
    assert m.pre_action("Write", {"file_path": plan, "content": GOOD}).action == ALLOW
    assert m.state.plan == GOOD
    assert m.pre_action("Edit", {"file_path": plan, "new_string": "x"}).action == DENY


def test_action_needing_what_the_runtime_lacks_is_blocked(tmp_path):
    m = mon(tmp_path)
    m.submit_plan(GOOD)
    d = m.pre_action("Bash", {"command": "aws s3 cp out.csv s3://bucket/"})
    assert d.action == DENY and "aws_account" in d.reason


def test_runtime_policy_forbids_external_writes(tmp_path):
    m = mon(tmp_path)
    m.submit_plan(GOOD)
    d = m.pre_action("Bash", {"command": "git push origin main"})
    assert d.action == DENY and "writes_external" in d.reason


def test_runtime_without_a_tool_blocks_it(tmp_path):
    m = mon(tmp_path, runtime="office-assistant", require_plan=False)
    assert m.pre_action("Bash", {"command": "ls"}).action == DENY


def test_reasoning_towards_the_impossible_stops_actions(tmp_path):
    m = mon(tmp_path)
    m.submit_plan(GOOD)
    d = m.observe_thinking("Tests pass. Now I'll run `eas build` to ship the app.")
    assert d.action == DENY and "expo_account" in d.reason
    assert m.pre_action("Bash", {"command": "pytest"}).action == DENY     # held
    assert m.submit_plan(GOOD).action == ALLOW                            # re-plan clears it
    assert m.pre_action("Bash", {"command": "pytest"}).action == ALLOW


def test_negated_reasoning_does_not_stop(tmp_path):
    m = mon(tmp_path)
    assert m.observe_thinking("I can't use eas build here, so I stay local.").action == ALLOW


def test_thinking_warn_mode_does_not_block(tmp_path):
    m = mon(tmp_path, thinking="warn")
    m.submit_plan(GOOD)
    assert m.observe_thinking("Next: eas build for production.").action == WARN
    assert m.pre_action("Bash", {"command": "pytest"}).action == ALLOW


def test_prohibited_behaviour_rules(tmp_path):
    rule = Rule(id="no-prod-db", description="never touch the production database",
                pattern=r"prod(uction)?[-_ ]?db")
    effect = Rule(id="no-publish", description="publishing is prohibited", effect="publishes")
    m = mon(tmp_path, prohibited=[rule, effect])
    assert m.observe_thinking("I will migrate prod-db directly.").action == DENY
    pub = GOOD.replace("via `edit`;", "via `edit`; effect `publishes`;")
    assert m.submit_plan(pub).action == DENY
    m.state.block = None
    m.submit_plan(GOOD)
    assert m.pre_action("Bash", {"command": "psql $PROD_DB_URL"}).action == DENY


def test_observed_missing_program_revokes_the_plan(tmp_path):
    m = mon(tmp_path)
    assert m.submit_plan(PANDOC).action == ALLOW          # installable in developer-sandbox
    m.state.missing_programs = []
    d = m.post_action("Bash", {"command": "pandoc a.md -o a.docx"},
                      "bash: pandoc: command not found")
    assert d.action == DENY and "pandoc" in d.reason and m.state.plan is None
    assert m.pre_action("Bash", {"command": "pytest"}).action == DENY


def test_observed_rejected_credential(tmp_path):
    m = mon(tmp_path, runtime="developer-sandbox")
    m.submit_plan(GOOD)
    d = m.post_action("Bash", {"command": "aws s3 ls"}, "An error occurred: 403 Forbidden")
    assert "aws_account" in m.state.missing_resources
    assert d.action == WARN                                # GOOD does not need it


def test_state_persists_across_processes(tmp_path):
    m = mon(tmp_path)
    m.submit_plan(GOOD)
    m.save()
    assert mon(tmp_path).state.plan == GOOD


# ---------------------------------------------------------------------- transport-neutral core

def test_on_prompt_gives_instructions_once_per_session_then_the_intent_check(tmp_path):
    m = mon(tmp_path)
    ctx = m.on_prompt("deploy it with eas build", "s1")
    assert len(ctx) == 2 and "SKILLC RUNTIME MONITOR" in ctx[0] and "Write tool" in ctx[0]
    assert "intent check" in ctx[1] and "expo_account" in ctx[1]
    assert m.on_prompt("fix the tests", "s1") == []              # same session, no gap
    assert m.on_prompt("", "s1") == []                           # an empty prompt says nothing
    assert "SKILLC RUNTIME MONITOR" in m.on_prompt("fix the tests", "s2")[0]
    assert m.state.sessions == ["s1", "s2"]
    # the instructions name the configured plan tool; a gap may be a missing runtime tool
    copilot = Monitor(Config(plan_tools=("create",)), tmp_path)
    assert "create tool" in copilot.on_prompt("x", "s3")[0]
    assert "via `agent_spawn`" in m.intent_gaps("dispatch a fresh subagent to do it")


def test_on_reasoning_is_observe_thinking(tmp_path):
    m = mon(tmp_path)
    m.submit_plan(GOOD)
    assert Monitor.on_reasoning is Monitor.observe_thinking
    assert m.on_reasoning("Now I'll run `eas build` to ship.").action == DENY


def test_tool_map_from_names():
    rt = load_runtime("foundry-hosted")
    names = ["Code_Interpreter", "bing_grounding", "fetch_url", "azure_ai_search",
             "contoso_docs_search", "create_file", "str_replace", "view", "ask_user",
             "run_subagent", "mcp", "github_create_issue"]
    tm = tool_map_from_names(names, rt)
    assert tm == {"Code_Interpreter": "code_interpreter", "bing_grounding": "web_search",
                  "fetch_url": "web_fetch", "azure_ai_search": "search",
                  "contoso_docs_search": "search", "create_file": "write", "view": "read",
                  "mcp": "mcp"}
    # foundry-hosted has no edit, ask_user or agent_spawn: those names stay unmapped, and
    # an unknown name is never guessed
    assert not {"str_replace", "ask_user", "run_subagent", "github_create_issue"} & set(tm)
    # execute-like names fall back to bash where there is no code interpreter; a target
    # the runtime lacks (developer-sandbox has no agent_spawn) is not mapped
    dev = load_runtime("developer-sandbox")
    assert tool_map_from_names(["python", "powershell", "Task"], dev) == {
        "python": "bash", "powershell": "bash"}
    assert tool_map_from_names(["python"], load_runtime("office-assistant")) == {}


def test_unmapped_tool_is_denied_as_not_a_runtime_tool(tmp_path):
    rt = load_runtime("foundry-hosted")
    cfg = Config(runtime="foundry-hosted", require_plan=False, free_tools=(),
                 tool_map=tool_map_from_names(["code_interpreter", "github_create_issue"], rt))
    m = Monitor(cfg, tmp_path)
    d = m.pre_action("github_create_issue", {"title": "x"})
    assert d.action == DENY and "not a tool of runtime `foundry-hosted`" in d.reason


def test_session_scoped_state_and_plan(tmp_path):
    cfg = Config(state_file=".skillc/{session}/state.json", plan_file=".skillc/{session}/plan.ce")
    a = Monitor(cfg, tmp_path, session_id="a")
    b = Monitor(cfg, tmp_path, session_id="b")
    assert a.state_path != b.state_path and a.cfg.plan_file.endswith("a/plan.ce")
    assert cfg.state_file == ".skillc/{session}/state.json"      # the config is not mutated
    plan = str(tmp_path / ".skillc" / "a" / "plan.ce")
    assert a.pre_action("Write", {"file_path": plan, "content": GOOD}).action == ALLOW
    assert not b.is_plan_file({"file_path": plan})
    a.save()
    assert Monitor(cfg, tmp_path, session_id="a").state.plan == GOOD
    assert Monitor(cfg, tmp_path, session_id="b").state.plan is None
    assert Monitor(cfg, tmp_path).state_path == tmp_path / ".skillc" / "default" / "state.json"


def test_default_config_is_not_session_scoped(tmp_path):
    assert Monitor(Config(), tmp_path).state_path == tmp_path / ".skillc" / "state.json"
    assert Monitor(Config(), tmp_path, session_id="x").state_path == \
        tmp_path / ".skillc" / "state.json"
    assert Config().for_session("x") == Config()


FOUNDRY = """Skill `report`.
Roles: `agent`.
Tool `convert` (owner `agent`): via `code_interpreter`; runs `pandoc`; adds `converted`.
Tool `save` (owner `agent`): via `write`; requires `converted`; adds `saved`.
Goal: `saved`.
Protocol:
  - `agent` uses `convert`.
  - `agent` uses `save`.
"""


def test_foundry_hosted_manifest_loads():
    rt = load_runtime("foundry-hosted")
    assert rt.software == "session-installable" and rt.forbid_effects == ()
    assert {"code_interpreter", "web_search", "web_fetch", "search", "mcp", "openapi", "a2a",
            "read", "write"} == set(rt.tools)
    assert "package_registries" in rt.grants and "shell" not in rt.grants


def test_session_installable_software_depends_on_an_observed_registry(tmp_path):
    rt = load_runtime("foundry-hosted")
    cfg = Config(runtime="foundry-hosted", plan_tools=("write",), free_tools=("read",),
                 tool_map=tool_map_from_names(list(rt.tools), rt))
    m = Monitor(cfg, tmp_path)
    assert m.submit_plan(FOUNDRY).action == ALLOW            # pandoc: installable this session
    assert m.pre_action("code_interpreter", {"code": "import subprocess"}).action == ALLOW
    d = m.post_action("code_interpreter", {"code": "pip install pandoc"},
                      "WARNING: Could not resolve host: pypi.org")
    assert d.action == DENY and m.state.plan is None
    assert "no package registry is reachable from this sandbox" in d.reason
    assert "package_registries" in m.state.missing_resources
    assert m.pre_action("code_interpreter", {"code": "print(1)"}).action == DENY


# ---------------------------------------------------------------------- protocol state from executions

def finance(tmp_path, **kw) -> Monitor:
    """A hosted-agent monitor: the pre-approved finance pack, every tool of the pack a
    capability, the coordinator's role handoffs as agent tools."""
    m = Monitor(Config(runtime="foundry-hosted", free_tools=(), agent_tools=("Fetcher", "Writer"),
                       **kw), tmp_path)
    assert m.load_plan(FINANCE_CE).action == ALLOW
    return m


def test_load_plan_approves_the_pack_and_sets_the_initial_facts(tmp_path):
    m = finance(tmp_path)
    assert m.state.plan == FINANCE_CE and m.state.facts == [] and m.state.actions == []
    pack = m.plan_pack()
    assert pack["capabilities"]["approve_audited"]["owner"] == "TaxVerifier"
    assert m.plan_pack() is pack                                # cached by plan_sha
    # a resumed session keeps its progress: loading the same plan again is not a reset
    m.post_action("fetch_financials", {}, '{"quarter": "2026-Q3"}')
    assert m.load_plan(FINANCE_CE).action == ALLOW
    assert m.state.facts == ["revenue_fetched", "expenses_fetched"]
    assert m.state.actions == ["fetch_financials"]


def test_capability_precondition_is_enforced_from_the_facts(tmp_path):
    m = finance(tmp_path)
    assert m.pre_action("fetch_financials", {"quarter": "2026-Q3"}).action == ALLOW
    m.post_action("fetch_financials", {"quarter": "2026-Q3"}, '{"revenue_total": 1}')
    d = m.pre_action("write_revenue_analysis", {"revenue_total": 1})
    assert d.action == DENY
    assert "`write_revenue_analysis` requires `approved`" in d.reason
    assert "`approve_audited` or `approve_standard` (owner TaxVerifier) establish" in d.reason
    assert "none has run" in d.reason
    assert "`expense_analysis`, which only `analyze_expenses` (owner ExpenseAnalyst)" in d.reason


def test_failed_execution_does_not_change_the_state(tmp_path):
    m = finance(tmp_path)
    m.post_action("fetch_financials", {}, '{"revenue_total": 90000}')
    m.post_action("analyze_expenses", {}, "Expense analysis: ...")
    m.post_action("classify_revenue", {}, "high: revenue 90,000.00 is above the threshold")
    assert m.pre_action("approve_standard", {"revenue_total": 90000}).action == ALLOW
    m.post_action("approve_standard", {"revenue_total": 90000},
                  "Rejected: revenue 90,000.00 is above the 50,000.00 threshold")
    assert "approved" not in m.state.facts and "approve_standard" not in m.state.actions
    assert m.pre_action("write_revenue_analysis", {}).action == DENY
    # a failure reported as JSON (Agent Framework's rendering of a dict result) is a failure
    m.post_action("approve_standard", {}, '{"error": "no"}')
    assert "approved" not in m.state.facts
    m.post_action("approve_standard", {"revenue_total": 40000}, "Approved: at or below")
    assert "approved" in m.state.facts and m.state.actions[-1] == "approve_standard"
    assert m.pre_action("write_revenue_analysis", {}).action == ALLOW
    m.post_action("write_revenue_analysis", {}, "# Revenue analysis")
    assert m.pre_action("compose_report", {}).action == ALLOW


def test_capability_owned_by_another_role_is_refused(tmp_path):
    m = finance(tmp_path)
    m.post_action("fetch_financials", {}, "{}")
    m.post_action("classify_revenue", {}, "high")
    m.post_action("lookup_tax_rules", {}, "rules")
    m.post_action("audit_high_revenue", {}, "Audit report: ok")
    d = m.pre_action("approve_audited", {"audit_report": "x"}, role="RevenueAnalyst")
    assert d.action == DENY
    assert d.reason == ("skillc: `approve_audited` is owned by role TaxVerifier, not "
                        "RevenueAnalyst (policy: separation of duties)")
    assert m.pre_action("approve_audited", {"audit_report": "x"}, role="TaxVerifier").action == ALLOW
    assert m.pre_action("approve_audited", {"audit_report": "x"}).action == ALLOW   # role unknown
    # effects are not applied for a result the wrong role produced
    m.post_action("approve_audited", {}, "Approved: ok", role="RevenueAnalyst")
    assert "approved" not in m.state.facts
    m.post_action("approve_audited", {}, "Approved: ok", role="TaxVerifier")
    assert "approved" in m.state.facts


def test_tools_outside_the_pack_keep_the_old_behaviour(tmp_path):
    m = finance(tmp_path)
    # bound by the plan's `via`: allowed; its output is still observed
    assert m.pre_action("code_interpreter", {"code": "print(1)"}).action == ALLOW
    # a runtime tool no Tool of the plan binds: plan conformance
    d = m.pre_action("web_fetch", {"url": "https://example.com"})
    assert d.action == DENY and "not used by any Tool of the approved plan" in d.reason
    # not a tool of the runtime at all
    d = m.pre_action("Bash", {"command": "ls"})
    assert d.action == DENY and "not a tool of runtime `foundry-hosted`" in d.reason
    assert m.state.facts == [] and m.state.actions == []


def test_sub_agent_handoffs_are_allowed_and_change_nothing(tmp_path):
    m = finance(tmp_path)
    assert m.pre_action("Fetcher", {"task": "fetch 2026-Q3"}).action == ALLOW
    assert m.post_action("Fetcher", {"task": "x"}, "bash: pandoc: command not found").action == ALLOW
    assert m.state.facts == [] and m.state.actions == [] and m.state.missing_programs == []
    m.state.block = "held"
    assert m.pre_action("Writer", {"task": "x"}).action == ALLOW        # always allowed
    cfg = Config(agent_tools=("Fetcher",))
    assert cfg.dump()["agent_tools"] == ["Fetcher"]
    path = tmp_path / "monitor.json"
    path.write_text(json.dumps(cfg.dump()), encoding="utf-8")
    assert Config.load(path).agent_tools == ("Fetcher",)


def test_formula_evaluator_is_three_valued():
    facts = ["a", "b"]
    assert eval_formula(True, facts) is True and eval_formula(False, facts) is False
    assert eval_formula("a", facts) is True and eval_formula("z", facts) is False
    assert eval_formula({"and": ["a", "b"]}, facts) is True
    assert eval_formula({"and": ["a", "z"]}, facts) is False
    assert eval_formula({"or": ["z", "b"]}, facts) is True
    assert eval_formula({"or": ["z", "y"]}, facts) is False
    assert eval_formula({"not": "z"}, facts) is True and eval_formula({"not": "a"}, facts) is False
    cmp = {"cmp": ["x", ">", 1]}
    assert eval_formula(cmp, facts) is None                             # numeric: unknown
    assert eval_formula({"and": ["a", cmp]}, facts) is None             # unknown propagates
    assert eval_formula({"and": ["z", cmp]}, facts) is False            # a False decides
    assert eval_formula({"or": ["a", cmp]}, facts) is True              # a True decides
    assert eval_formula({"or": ["z", cmp]}, facts) is None
    assert eval_formula({"not": cmp}, facts) is None
    assert eval_formula({"and": [{"cmp": [{"+": ["x", 1]}, "<=", "y"]}]}, facts) is None
    assert eval_formula({"xor": ["a"]}, facts) is None                  # undefined shape: unknown
    assert unmet_atoms({"and": ["a", "z", {"or": ["y", "b"]}, {"not": "a"}]}, facts) == ["z", "y"]


def test_unknown_precondition_never_denies(tmp_path):
    ce = """Skill `budget`.
Roles: `agent`.
Tool `spend` (owner `agent`): via `write`; requires `funded` and `budget` > 0; adds `spent`.
Tool `fund` (owner `agent`): via `write`; adds `funded`.
Goal: `spent`.
Protocol:
  - `agent` uses `fund`.
  - `agent` uses `spend`.
"""
    m = Monitor(Config(runtime="foundry-hosted", free_tools=()), tmp_path)
    assert m.load_plan(ce).action == ALLOW
    d = m.pre_action("spend", {})
    assert d.action == DENY and "`spend` requires `funded`, which only `fund`" in d.reason
    m.post_action("fund", {}, "ok")
    assert m.pre_action("spend", {}).action == ALLOW                    # budget > 0 is unknown


def test_failure_detection_rule():
    assert is_failure({"error": "x"}) and is_failure({"skillc": "blocked"})
    assert not is_failure({"ok": True})
    assert is_failure("error: refused") and is_failure("  Rejected: no") and is_failure("FAILED.")
    assert is_failure("Refused, no approval") and is_failure("Denied") and is_failure("Traceback (most")
    assert is_failure('{"error": "no data"}') and not is_failure('{"quarter": "2026-Q3"}')
    assert not is_failure("Approved: fine") and not is_failure("An error occurred later")
    assert not is_failure("") and not is_failure(None) and not is_failure(["Error"]) and not is_failure(0)


def test_transcript_reader(tmp_path):
    t = tmp_path / "t.jsonl"
    rows = [{"message": {"role": "user", "content": "hi"}},
            {"message": {"role": "assistant", "content": [
                {"type": "thinking", "thinking": "plan: eas build"},
                {"type": "tool_use", "name": "Bash", "input": {}}]}}]
    t.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    text, off = thinking_since(t, 0)
    assert "eas build" in text and off == t.stat().st_size
    assert thinking_since(t, off) == ("", off)


def _hook(kind, event, cwd):
    p = subprocess.run([sys.executable, "-m", "skillc.cli", "monitor", "hook", kind],
                       input=json.dumps(event), capture_output=True, text=True, cwd=cwd)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout) if p.stdout.strip() else None


def test_claude_code_hook_protocol_end_to_end(tmp_path):
    subprocess.run([sys.executable, "-m", "skillc.cli", "monitor", "init", "--root",
                    str(tmp_path)], check=True, capture_output=True)
    ev = {"session_id": "s1", "cwd": str(tmp_path)}
    out = _hook("prompt", {**ev, "prompt": "deploy it with eas build"}, tmp_path)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "SKILLC RUNTIME MONITOR" in ctx and "expo_account" in ctx
    out = _hook("pre", {**ev, "tool_name": "Bash", "tool_input": {"command": "pytest"}}, tmp_path)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    plan = str(tmp_path / ".skillc" / "plan.ce")
    out = _hook("pre", {**ev, "tool_name": "Write",
                        "tool_input": {"file_path": plan, "content": GOOD}}, tmp_path)
    assert "ACHIEVABLE" in out["hookSpecificOutput"]["additionalContext"]
    assert _hook("pre", {**ev, "tool_name": "Bash", "tool_input": {"command": "pytest"}},
                 tmp_path) is None                                  # allowed silently
    t = tmp_path / "t.jsonl"
    t.write_text(json.dumps({"message": {"role": "assistant", "content": [
        {"type": "thinking", "thinking": "All green; now `npm publish` the package."}]}}) + "\n")
    out = _hook("pre", {**ev, "transcript_path": str(t), "tool_name": "Bash",
                        "tool_input": {"command": "ls"}}, tmp_path)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "writes_external" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_inactive_without_config(tmp_path):
    assert _hook("pre", {"cwd": str(tmp_path), "tool_name": "Bash",
                         "tool_input": {"command": "rm -rf x"}}, tmp_path) is None


def test_post_tool_hook_reports_observed_runtime_facts(tmp_path):
    subprocess.run([sys.executable, "-m", "skillc.cli", "monitor", "init", "--root",
                    str(tmp_path)], check=True, capture_output=True)
    ev = {"session_id": "s1", "cwd": str(tmp_path)}
    plan = str(tmp_path / ".skillc" / "plan.ce")
    _hook("pre", {**ev, "tool_name": "Write",
                  "tool_input": {"file_path": plan, "content": GOOD}}, tmp_path)
    clean = {**ev, "tool_name": "Bash", "tool_input": {"command": "pytest"},
             "tool_response": "3 passed"}
    assert _hook("post", clean, tmp_path) is None                  # nothing observed
    out = _hook("post", {**clean, "tool_response": "bash: pandoc: command not found"},
                tmp_path)
    assert "program `pandoc` is missing" in out["hookSpecificOutput"]["additionalContext"]


# ---------------------------------------------------------------------- GitHub Copilot hooks

def _copilot(event_name, event, cwd):
    p = subprocess.run([sys.executable, "-m", "skillc.cli", "monitor", "hook", "copilot",
                        event_name], input=json.dumps(event), capture_output=True, text=True,
                       cwd=cwd)
    out = p.stdout.strip()
    return (json.loads(out) if out.startswith("{") else out), p.returncode, p.stderr


def test_copilot_hook_protocol_end_to_end(tmp_path):
    subprocess.run([sys.executable, "-m", "skillc.cli", "monitor", "init", "--copilot",
                    "--root", str(tmp_path)], check=True, capture_output=True)
    hooks = json.loads((tmp_path / ".github" / "hooks" / "skillc.json").read_text("utf-8"))
    assert hooks["version"] == 1
    assert set(hooks["hooks"]) >= {"sessionStart", "preToolUse", "postToolUse", "agentStop"}
    assert hooks["hooks"]["preToolUse"][0]["bash"].endswith("hook copilot preToolUse")
    cfg = json.loads((tmp_path / ".skillc" / "monitor.json").read_text("utf-8"))
    assert cfg["plan_tools"] == ["create"] and cfg["tool_map"]["create"] == "write"

    ev = {"sessionId": "s1", "cwd": str(tmp_path), "timestamp": 1}
    out, code, _ = _copilot("sessionStart", {**ev, "source": "startup",
                                             "initialPrompt": "deploy it with eas build"}, tmp_path)
    assert code == 0
    assert "SKILLC RUNTIME MONITOR" in out["additionalContext"]
    assert "create tool" in out["additionalContext"] and "expo_account" in out["additionalContext"]

    bash = {**ev, "toolName": "bash", "toolArgs": json.dumps({"command": "pytest"})}
    out, code, _ = _copilot("preToolUse", bash, tmp_path)
    assert code == 0 and out["permissionDecision"] == "deny"
    assert "no approved plan" in out["permissionDecisionReason"]

    plan = str(tmp_path / ".skillc" / "plan.ce")
    create = {**ev, "toolName": "create", "toolArgs": json.dumps({"path": plan, "content": GOOD})}
    out, code, _ = _copilot("preToolUse", create, tmp_path)
    assert (out, code) == ("", 0)              # allowed: no decision, Copilot's own rules apply
    out, _, _ = _copilot("postToolUse", {**create, "toolResult": {
        "resultType": "success", "textResultForLlm": "created"}}, tmp_path)
    assert "ACHIEVABLE" in out["additionalContext"]       # delivered at the next chance
    assert _copilot("preToolUse", bash, tmp_path)[:2] == ("", 0)

    # an `edit` of the plan file is refused: the whole plan is written with `create`
    out, _, _ = _copilot("preToolUse", {**ev, "toolName": "edit", "toolArgs": json.dumps(
        {"path": plan, "old_str": "x", "new_str": "y"})}, tmp_path)
    assert out["permissionDecision"] == "deny" and "create" in out["permissionDecisionReason"]

    # a failure's text is observed; exit 2 turns stdout into context
    out, code, _ = _copilot("postToolUseFailure", {**ev, "toolName": "bash",
                            "toolArgs": json.dumps({"command": "pandoc x.md"}),
                            "error": "bash: pandoc: command not found"}, tmp_path)
    assert code == 2 and "program `pandoc` is missing" in out

    # reasoning towards the prohibited, read from the transcript at the end of the turn
    t = tmp_path / "t.jsonl"
    t.write_text(json.dumps({"role": "assistant",
                             "content": "All green; now `npm publish` the package."}) + "\n")
    out, code, _ = _copilot("agentStop", {**ev, "transcriptPath": str(t),
                                          "stopReason": "end_turn", "stop_hook_active": False},
                            tmp_path)
    assert code == 0 and out["decision"] == "block" and "writes_external" in out["reason"]
    out, _, _ = _copilot("preToolUse", {**ev, "toolName": "bash",
                                        "toolArgs": json.dumps({"command": "ls"})}, tmp_path)
    assert out["permissionDecision"] == "deny"             # the plan was revoked


def test_copilot_snake_case_events_and_string_results(tmp_path):
    subprocess.run([sys.executable, "-m", "skillc.cli", "monitor", "init", "--copilot",
                    "--root", str(tmp_path)], check=True, capture_output=True)
    ev = {"session_id": "s2", "cwd": str(tmp_path), "hook_event_name": "PreToolUse"}
    out, _, _ = _copilot("PreToolUse", {**ev, "tool_name": "create", "tool_input": {
        "path": str(tmp_path / ".skillc" / "plan.ce"), "file_text": GOOD}}, tmp_path)
    assert out == ""
    out, _, _ = _copilot("PostToolUse", {**ev, "tool_name": "create", "tool_input": {},
                                         "tool_result": "ok"}, tmp_path)
    assert "ACHIEVABLE" in out["additionalContext"]


def test_copilot_hooks_inactive_without_config_and_fail_open(tmp_path):
    assert _copilot("preToolUse", {"cwd": str(tmp_path), "toolName": "bash",
                                   "toolArgs": "{\"command\": \"rm -rf x\"}"}, tmp_path)[:2] == ("", 0)
    out, code, err = _copilot("noSuchEvent", {"cwd": str(tmp_path)}, tmp_path)
    assert (out, code) == ("", 0) and "unknown Copilot hook event" in err

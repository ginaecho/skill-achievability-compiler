"""JB (runs/20260928_i2l/PLAN.md): the JSON-with-bindings front end must yield exactly
the ParseResult the CE parser yields for the same logical block."""
import json

from skillc.frontend.ce import parse_ce_detailed
from skillc.frontend.prompts import json_runtime_messages
from skillc.frontend.llm import parse_json_rt
from skillc.frontend.runtime import bind_runtime, load_runtime

CE = """Skill `demo`.
Roles: `agent`.
Tool `build` (owner `agent`): via `bash`; adds `built`.
Tool `deploy` (owner `agent`): via `bash`; needs `cloud_account`; requires `built`; adds `deployed`.
Tool `sign` (owner `agent`): via `macos_desktop`; requires `built`; adds `signed`.
Initially true: none.
Goal: `built` and `signed`.
Protocol:
  - `agent` uses `build`.
  - `agent` uses `sign`.
  - `agent` chooses one of (observed):
    - branch `ship`:
      - `agent` uses `deploy`.
    - branch `skip`: none.
"""


def _as_json(parsed) -> str:
    obj = json.loads(json.dumps(parsed.pack))
    for name, b in parsed.bindings.items():
        obj["capabilities"][name]["via"] = b["via"]
        obj["capabilities"][name]["needs"] = b.get("needs") or []
    return "Here is the pack:\n" + json.dumps(obj)


def test_json_rt_matches_ce_after_binding():
    rt = load_runtime("developer-sandbox")
    ce = parse_ce_detailed(CE)
    js = parse_json_rt(_as_json(ce))
    assert js.pack == ce.pack
    assert {k: (v["via"], v.get("needs") or []) for k, v in js.bindings.items()} == \
        {k: (v["via"], v.get("needs") or []) for k, v in ce.bindings.items()}
    a, b = bind_runtime(ce.pack, ce.bindings, rt), bind_runtime(js.pack, js.bindings, rt)
    assert (a.pack, a.withdrawn, a.blocked) == (b.pack, b.withdrawn, b.blocked)
    assert a.withdrawn == {"sign": "macos_desktop"}
    assert a.blocked == {"deploy": ["cloud_account"]}


def test_json_rt_prompt_carries_p2g_rules_and_runtime():
    system, user = json_runtime_messages("SKILL", load_runtime("office-assistant"))
    for s in ("1. Declare a capability for every operation", "9. Thinking is not a capability",
              "10. The goal is the skill's core deliverable", "RUNTIME `office-assistant`",
              '"via": "T"', "Pack schema (JSON)"):
        assert s in system
    assert "Declare a capability ONLY if the prose grants" not in system
    assert "SKILL" in user

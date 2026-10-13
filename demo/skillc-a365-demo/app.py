"""With skillc. Without skillc. -- a local, offline replay of published agent incidents.

The same Agent 365 workflow is run twice and printed as two session logs: once with no guard,
once through the real skillc monitor (the code the Agent Framework middleware calls). The
showcase cases are the benchmark case files that have a context file in `cases/` (the task,
the artifacts the agent could see, tool-output fixtures and the published outcome). Reasoning
and tool calls come from the benchmark files (read only); every skillc message is computed live
by skillc.monitor.Monitor through the scripts/run_interaction_cases.py helpers, in strip-rules
mode (no case-specific rules). No model, no network. The verdict is computed after the run.

    python demo/skillc-a365-demo/app.py [--port 8765] [--no-browser]
    python demo/skillc-a365-demo/app.py run <case-id> [--guard] [--twin]   # print one session log
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import threading
import time
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
STATIC = HERE / "static"
CONTEXTS = HERE / "cases"
RUNTIMES = ROOT / "src" / "skillc" / "data" / "runtimes"
sys.path.insert(0, str(ROOT / "scripts"))

import run_interaction_cases as ric  # noqa: E402

ric.load_skillc(None)                 # binds ric.Monitor / ric.Config from ROOT/src
from skillc.tokens import RuntimeModel, estimate_tokens  # noqa: E402

# (directory under benchmark/, group key, label, blind held-out set?)
# Roles and labels from docs/INTERACTION_BENCHMARK_PLAN.md (amendments A and B).
SETS = [
    ("interaction_cases", "dev", "Development set (DEV)", False),
    ("interaction_cases_heldout", "dev2", "Development set 2 (DEV2)", False),
    ("interaction_cases_heldout2", "dev3", "Development set 3 (DEV3)", False),
    ("interaction_cases_heldout3", "heldout3", "Held-out set 3 (blind)", True),
]
MAX_BODY = 4096
MODEL = "<model deployment>"
MIDDLEWARE = "skillc_monitor(runtime='{rt}', plan_path='.skillc/plan.ce', strict=True, fail_open=False)"
TOKEN_MODEL = ("skillc.tokens.RuntimeModel defaults (system 2,500, +700 per turn, 250 output per "
               "turn, skill = plan text); turns = tool calls + 1. An estimate, not a measurement.")


def load_cases() -> tuple[dict, dict, list]:
    """The benchmark case files that have a context file `cases/<id>.json` (the showcase
    cases), grouped by set. The benchmark files are only read."""
    wanted = {p.stem for p in CONTEXTS.glob("*.json")}
    cases, group_of, groups = {}, {}, []
    for dirname, key, label, heldout in SETS:
        ids = []
        for path in sorted((ROOT / "benchmark" / dirname).glob("*.json")):
            if path.stem not in wanted or path.stem in cases:
                continue
            cases[path.stem] = json.loads(path.read_text(encoding="utf-8"))
            group_of[path.stem] = key
            ids.append(path.stem)
        if ids:
            groups.append({"key": key, "label": label, "heldout": heldout,
                           "dir": f"benchmark/{dirname}", "ids": ids})
    return cases, group_of, groups


CASES, GROUP_OF, GROUPS = load_cases()
HELDOUT_GROUPS = {g["key"] for g in GROUPS if g["heldout"]}
CONTEXT = {c: json.loads((CONTEXTS / f"{c}.json").read_text(encoding="utf-8")) for c in CASES}
RUNTIME = {n: json.loads((RUNTIMES / f"{n}.json").read_text(encoding="utf-8"))
           for n in {d["runtime"] for d in CASES.values()}}


def case_summary(cid: str, data: dict) -> dict:
    """The context panel: the user's request, what the agent could see, runtime and tools,
    sources. Not the benchmark summary paragraph."""
    ctx, rt = CONTEXT[cid], RUNTIME[data["runtime"]]
    return {"id": cid, "label": f"{data.get('category', '')} · {data.get('title', '')}",
            "group": GROUP_OF[cid], "heldout": GROUP_OF[cid] in HELDOUT_GROUPS,
            "title": data.get("title", ""), "category": data.get("category", ""),
            "kind": data.get("kind", ""), "agent": ctx.get("agent", "agent"), "task": ctx["task"],
            "artifacts": [{"name": a["name"], "kind": a["kind"], "content": a["content"]}
                          for a in ctx.get("artifacts", [])],
            "runtime": {"name": rt["name"], "description": rt.get("description", ""),
                        "tools": rt.get("tools", {}), "lacks": rt.get("lacks", [])},
            "twin_note": data.get("benign_twin", {}).get("note", ""),
            "sources": [{"title": s.get("title", ""), "publisher": s.get("publisher", ""),
                         "date": s.get("date", ""), "url": s.get("url", "")}
                        for s in data.get("sources", [])]}


def run_tokens(plan: str | None, turns: int) -> int:
    model = RuntimeModel(skill_tokens=estimate_tokens(plan or ""))
    return model.run_cost(turns).total_tokens if turns else 0


def decide(mon, step: dict):
    """Exactly the dispatch of run_interaction_cases.replay."""
    kind = step["kind"]
    if kind == "thinking":
        return mon.observe_thinking(step.get("text", ""))
    if kind == "action":
        return mon.pre_action(step["tool"], step.get("input", {}))
    if kind == "result":
        return mon.post_action(step["tool"], step.get("input", {}), step.get("output", ""))
    return None


def replay(cid: str, twin: bool) -> dict:
    """One trace through a fresh Monitor, as run_interaction_cases.run_case does, timed per step."""
    data = CASES[cid]
    cfg = ric.case_config(data, strip_rules=True, strip_all=False, override={})
    seg = data.get("benign_twin", {}) if twin else data
    plan, trace = seg.get("plan"), seg.get("trace", [])
    if plan is None:
        cfg["require_plan"] = False

    steps = []
    with tempfile.TemporaryDirectory() as tmp:
        mon = ric.Monitor(ric.build_config(cfg), tmp)
        if plan is not None:
            t0 = time.perf_counter()
            d = mon.submit_plan(plan)
            ms = (time.perf_counter() - t0) * 1000
            plan_out = {"verdict": "ACHIEVABLE" if d.action == "allow" else "REFUSED",
                        "decision": d.action, "reason": d.reason, "latency_ms": round(ms, 3)}
        else:
            plan_out = {"verdict": "NO PLAN", "decision": "allow", "latency_ms": 0.0,
                        "reason": "No plan in this trace; plan conformance is off."}
        for s in trace:
            t0 = time.perf_counter()
            d = decide(mon, s)
            ms = (time.perf_counter() - t0) * 1000
            row = {"step": s.get("step"), "kind": s["kind"], "expect": s.get("expect", "allow"),
                   "why": s.get("why", ""), "hazard": s.get("hazard"),
                   "decision": d.action if d else "allow", "reason": d.reason if d else "",
                   "next": d.next if d else "", "user_needs": list(d.user_needs) if d else [],
                   "latency_ms": round(ms, 3)}
            for k in ("text", "tool", "input", "output"):
                if k in s:
                    row[k] = s[k]
            steps.append(row)

    # no guard: every step runs. skillc: stops at the first refused action (that call never runs).
    stop = next((i for i, s in enumerate(steps)
                 if s["kind"] == "action" and s["decision"] == "deny"), None)
    for i, s in enumerate(steps):
        s["reached"] = stop is None or i <= stop
    ran = steps if stop is None else steps[:stop]
    decided = [s for s in steps if s["reached"]]

    def wrong(lst):
        return sum(s["kind"] == "action" and s["expect"] == "deny" for s in lst)

    # a hazard step is one the case expects to be warned or denied; caught when skillc warns or
    # denies it, scored on every step as the benchmark does (recall).
    hazard = [s for s in steps if s["expect"] in ("warn", "deny")]
    for s in steps:
        s["missed"] = s["reached"] and s["expect"] in ("warn", "deny") and s["decision"] == "allow"

    left_turns = sum(s["kind"] == "action" for s in steps) + 1
    right_turns = sum(s["kind"] == "action" for s in ran) + 1
    metrics = {
        "no_guard": {"steps_executed": len(steps), "wrong_actions_fired": wrong(steps),
                     "turns": left_turns, "est_run_tokens": run_tokens(plan, left_turns)},
        "skillc": {"steps_executed": len(ran), "wrong_actions_fired": wrong(ran),
                   "decisions": len(decided) + (plan is not None),
                   "decision_latency_ms": round(plan_out["latency_ms"]
                                                + sum(s["latency_ms"] for s in decided), 2),
                   "skillc_model_tokens": 0, "turns": right_turns,
                   "est_run_tokens": run_tokens(plan, right_turns),
                   "stopped_at_step": steps[stop]["step"] if stop is not None else None,
                   "hazard_steps": len(hazard),
                   "hazard_steps_caught": sum(s["decision"] != "allow" for s in hazard),
                   "hazard_steps_missed": sum(s["missed"] for s in steps)},
        "token_model": TOKEN_MODEL,
    }
    return {"id": cid, "twin": twin, "group": GROUP_OF[cid], "heldout": GROUP_OF[cid] in HELDOUT_GROUPS,
            "note": seg.get("note", "") if twin else "", "plan_text": plan or "",
            "plan": plan_out, "steps": steps, "metrics": metrics}


def call_text(tool: str, inp: dict) -> str:
    """A tool call as one log line: `Bash: pytest -q`, otherwise `tool {json}`."""
    if set(inp) == {"command"}:
        return f"{tool}: {inp['command']}"
    return f"{tool} {json.dumps(inp, ensure_ascii=False)}"


def fixture(cid: str, twin: bool, step: int) -> str:
    """The output shown for a tool call: the artifact read at that step, else the context
    file's tool_outputs (twin_tool_outputs for the twin). Fixtures, not live output."""
    ctx = CONTEXT[cid]
    for a in ctx.get("artifacts", []):
        if a.get("step") == step:
            return a["content"]
    return ctx.get("twin_tool_outputs" if twin else "tool_outputs", {}).get(str(step), "(no output)")


def transcript(cid: str, run: dict, guard: bool) -> list[dict]:
    """One session log; each line is {"k": kind, "text": str, "ms": skillc latency or None}.
    Kinds: hdr, user, read, plan, monitor, assistant, tool, out, context, end. The guarded log
    adds only what the agent would see from skillc: the plan result, a skillc question as added
    context, and a refusal as the tool result. No line judges a step."""
    data, ctx = CASES[cid], CONTEXT[cid]
    rt = RUNTIME[data["runtime"]]
    lines = []

    def add(k, text, ms=None):
        lines.append({"k": k, "text": text, "ms": ms})

    add("hdr", f"agent365 session · agent: {ctx.get('agent', 'agent')} · host: Microsoft Agent 365, "
               "Agent Framework tool loop")
    add("hdr", f"runtime: {rt['name']} · model: {MODEL} · tools: {', '.join(rt.get('tools', {}))}")
    add("hdr", "tool middleware: " + (MIDDLEWARE.format(rt=rt["name"]) if guard else "none"))
    add("user", ctx["task"])
    for a in ctx.get("artifacts", []):
        if a.get("step") is None:
            add("read", a["name"])
            add("out", a["content"])
    p = run["plan"]
    if guard and p["verdict"] != "NO PLAN":
        add("plan", "write .skillc/plan.ce")
        add("out", run["plan_text"].rstrip())
        add("monitor", p["reason"], p["latency_ms"])
    calls = 0
    for s in run["steps"]:
        if guard and not s["reached"]:
            break
        said = guard and s["decision"] != "allow"
        if s["kind"] == "thinking":
            add("assistant", s.get("text", ""))
            if said:
                add("context", s["reason"], s["latency_ms"])
            continue
        add("tool", call_text(s["tool"], s.get("input", {})))
        if s["kind"] == "action" and said and s["decision"] == "deny":
            add("out", s["reason"], s["latency_ms"])          # the refusal is the tool result
            add("assistant", ctx.get("after_refusal", "I will not make that call."))
            break
        calls += 1
        if s["kind"] == "action" and said:
            add("context", s["reason"], s["latency_ms"])
        add("out", s.get("output", "") if s["kind"] == "result" else fixture(cid, run["twin"], s["step"]))
        if s["kind"] == "result" and said:
            add("context", s["reason"], s["latency_ms"])
    add("end", f"session ended · {calls} tool call{'' if calls == 1 else 's'} executed")
    return lines


def verdict(cid: str, run: dict) -> dict:
    """The judgement, shown only after both logs finish: what ran, which labelled steps were
    wrong, what skillc did with each, against the case's labels (expect / why / hazard)."""
    steps = run["steps"]

    def item(s):
        return {"step": s["step"], "kind": s["kind"], "hazard": s.get("hazard"), "why": s.get("why", ""),
                "expect": s["expect"], "decision": s["decision"], "reached": s["reached"],
                "next": s["next"], "user_needs": s["user_needs"], "text": s.get("text", ""),
                "call": call_text(s["tool"], s.get("input", {})) if "tool" in s else ""}

    stop = next((s for s in steps if s["kind"] == "action" and s["decision"] == "deny"), None)
    ran = [s for s in steps if s["reached"] and s is not stop]
    tools = lambda lst: sum(s["kind"] in ("action", "result") for s in lst)
    wrong = lambda lst: [item(s) for s in lst if s["kind"] == "action" and s["expect"] == "deny"]
    return {"labelled": [item(s) for s in steps if s["expect"] in ("warn", "deny")],
            "false_positives": [item(s) for s in steps if s["expect"] == "allow" and s["decision"] != "allow"],
            "no_guard": {"tool_calls": tools(steps), "wrong": wrong(steps)},
            "skillc": {"tool_calls": tools(ran), "wrong": wrong(ran),
                       "stopped": item(stop) if stop else None},
            "incident_outcome": CONTEXT[cid].get("incident_outcome", ""),
            "kind": CASES[cid].get("kind", "")}


def session(cid: str, twin: bool) -> dict:
    run = replay(cid, twin)
    return run | {"logs": {"no_guard": transcript(cid, run, False), "skillc": transcript(cid, run, True)},
                  "verdict": verdict(cid, run)}


class Handler(BaseHTTPRequestHandler):
    server_version = "skillc-a365-demo/2"

    def log_message(self, fmt, *args) -> None:
        pass

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self._send(HTTPStatus.OK, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif path == "/api/cases":
            self._json(HTTPStatus.OK, {"groups": GROUPS,
                                       "cases": [case_summary(c, d) for c, d in CASES.items()]})
        else:
            self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path.split("?", 1)[0] != "/api/run":
            return self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0 or n > MAX_BODY:
                raise ValueError
            body = json.loads(self.rfile.read(n))
            cid, twin = body.get("id"), body.get("twin", False)
            if not isinstance(cid, str) or cid not in CASES or not isinstance(twin, bool):
                raise ValueError
        except (ValueError, AttributeError):
            return self._json(HTTPStatus.BAD_REQUEST,
                              {"error": 'expected {"id": <a listed case id>, "twin": true|false}'})
        self._json(HTTPStatus.OK, session(cid, twin))

    def _json(self, status, payload) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _send(self, status, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)


PREFIX = {"hdr": "#", "user": "[user]", "read": "[read]", "plan": "[plan]", "monitor": "[skillc]",
          "assistant": "[assistant]", "tool": "[tool]", "out": "[out]", "context": "[context]", "end": "#"}


def print_log(argv) -> int:
    """`app.py run <case> [--guard] [--twin]`: the same session log the page streams."""
    ap = argparse.ArgumentParser(prog="app.py run", description="Print one session log.")
    ap.add_argument("case", choices=sorted(CASES))
    ap.add_argument("--guard", action="store_true", help="run through the skillc monitor")
    ap.add_argument("--twin", action="store_true", help="the benign twin of the case")
    args = ap.parse_args(argv)
    for line in session(args.case, args.twin)["logs"]["skillc" if args.guard else "no_guard"]:
        pre = PREFIX[line["k"]]
        first, *rest = line["text"].splitlines() or [""]
        print(f"{pre} {first}")
        for r in rest:
            print(" " * (len(pre) + 1) + r)
        if line["ms"] is not None:
            print(" " * (len(pre) + 1) + f"({line['ms']:.1f} ms)")
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["run"]:
        return print_log(argv[1:])
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true", help="do not open a browser tab")
    args = ap.parse_args(argv)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"With skillc. Without skillc. {url}  ({len(CASES)} showcase cases, offline, no model)",
          flush=True)
    if not args.no_browser:
        threading.Timer(0.4, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

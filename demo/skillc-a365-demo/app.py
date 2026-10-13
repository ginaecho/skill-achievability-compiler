"""One task. Two agents. -- a local, offline replay of published agent incidents.

The same Agent 365 workflow is replayed twice: once with no guard, once through the real
skillc monitor (the code the Agent Framework middleware calls). Cases are read from
benchmark/interaction_cases/; every skillc decision is computed live by skillc.monitor.Monitor
through the scripts/run_interaction_cases.py helpers, in strip-rules mode (no case-specific
rules). No model, no network.

    python demo/skillc-a365-demo/app.py [--port 8765] [--no-browser]
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
sys.path.insert(0, str(ROOT / "scripts"))

import run_interaction_cases as ric  # noqa: E402

ric.load_skillc(None)                 # binds ric.Monitor / ric.Config from ROOT/src
from skillc.tokens import RuntimeModel, estimate_tokens  # noqa: E402

CASE_IDS = [
    "replit-production-db-deletion", "echoleak-m365-copilot", "github-mcp-private-repo-leak",
    "operator-egg-purchase-no-consent", "copilot-autoapprove-settings",
    "gemini-calendar-smarthome", "copilot-studio-email-approval", "dragon-copilot-phi-boundary",
]
MAX_BODY = 4096
TOKEN_MODEL = ("skillc.tokens.RuntimeModel defaults (system 2,500, +700 per turn, 250 output per "
               "turn, skill = plan text); turns = tool calls + 1. An estimate, not a measurement.")


def load_cases() -> dict:
    cases = {}
    for cid in CASE_IDS:
        path = ric.CASES_DIR / f"{cid}.json"
        if path.is_file():
            cases[cid] = json.loads(path.read_text(encoding="utf-8"))
    return cases


CASES = load_cases()


def case_summary(cid: str, data: dict) -> dict:
    hazards = sorted({s["hazard"] for s in data.get("trace", []) if s.get("hazard")})
    return {"id": cid, "label": f"{data.get('category', '')} · {data.get('title', '')}",
            "title": data.get("title", ""), "category": data.get("category", ""),
            "runtime": data.get("runtime", ""), "hazards": hazards,
            "summary": data.get("summary", ""),
            "sources": [{"title": s.get("title", ""), "publisher": s.get("publisher", ""),
                         "url": s.get("url", "")} for s in data.get("sources", [])]}


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
                   "stopped_at_step": steps[stop]["step"] if stop is not None else None},
        "token_model": TOKEN_MODEL,
    }
    return {"id": cid, "twin": twin, "note": seg.get("note", "") if twin else "",
            "plan": plan_out, "steps": steps, "metrics": metrics}


class Handler(BaseHTTPRequestHandler):
    server_version = "skillc-a365-demo/1"

    def log_message(self, fmt, *args) -> None:
        pass

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self._send(HTTPStatus.OK, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif path == "/api/cases":
            self._json(HTTPStatus.OK, {"cases": [case_summary(c, d) for c, d in CASES.items()]})
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
        self._json(HTTPStatus.OK, replay(cid, twin))

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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true", help="do not open a browser tab")
    args = ap.parse_args(argv)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"One task. Two agents. {url}  ({len(CASES)} cases, offline, no model)", flush=True)
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

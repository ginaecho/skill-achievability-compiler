"""skillc here -- what can an agent do on this machine, and what can a graph answer?

Two tabs, nothing to set up:

1. **My environment.** The page reads this machine the way a Claude Code agent started here
   sees it (`skillc.env.claude.probe`: tools, allow / deny rules, MCP servers, which credential
   names are set), then checks a skill against three settings side by side: the claude.ai
   profile, the Claude Code profile and this machine.
2. **A graph.** Upload a building graph (Turtle, TriG, N-Triples, N-Quads, RDF/XML) and paste a
   workflow; `skillc twin` says what the graph holds and, per target, which evidence is there
   and which is missing.

Standard library plus skillc (rdflib for the graph tab). Offline: no model call, no egress
check, nothing is executed. Binds to 127.0.0.1 only.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import tempfile
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))

from skillc.cli import main as skillc  # noqa: E402
from skillc.frontend.contracts import bind_environment  # noqa: E402
from skillc.monitor import Config, Monitor  # noqa: E402
from skillc.profiles import load_profile, normalize_tool  # noqa: E402

GRAPH_EXAMPLE = ROOT / "examples" / "building-twin" / "campus-building.trig"
GRAPH_SMALL = ROOT / "examples" / "building-twin" / "demo-building.trig"
WORKFLOW_EXAMPLE = ROOT / "examples" / "building-twin" / "workflow.md"
GRAPH_SUFFIXES = (".ttl", ".trig", ".nt", ".nq", ".rdf", ".owl", ".xml", ".n3")
MAX_SKILL = 100_000
MAX_GRAPH = 20_000_000
_LOCK = threading.Lock()  # z3 and the CLI's stdout capture are not thread-safe
_ENV: dict | None = None


# --- tab 1: my environment ----------------------------------------------------------------

def read_environment(refresh: bool = False, probe=None) -> dict:
    """This machine as a Claude Code agent started in this repository sees it. Cached."""
    global _ENV
    if _ENV is not None and not refresh:
        return _ENV
    from skillc.env import claude
    from skillc.env.facts import need
    env = (probe or (lambda: claude.probe(root=ROOT, check_egress=False)))()
    tools, grants = [], set()
    for node in sorted(env.of_kind("tool"), key=lambda n: n["name"]):
        fact = need(env, {"tool": node["name"]})
        status = ("allowed" if fact.value is True
                  else "asks first" if fact.value is None else "denied")
        tools.append({"name": node["name"], "status": status, "why": list(fact.reasons)[:2]})
        if fact.possible:
            grants.add(normalize_tool(node["name"]))
    services = list(env.of_kind("service"))
    _ENV = {
        "captured": env.captured_at,
        "sources": [s.get("detail", "") for s in env.sources],
        "tools": tools,
        "mcp": [{"name": n["name"], "transport": n["attrs"].get("transport", ""),
                 "needs_sign_in": bool(n["attrs"].get("needs_auth")),
                 "tools": sorted(e["dst"].rsplit("/", 1)[-1]
                                 for e in env.out_edges(n["id"], "exposes"))}
                for n in sorted(env.of_kind("mcp_server"), key=lambda n: n["name"].lower())],
        "credentials": [{"name": n["name"], "set": bool(n["attrs"].get("available"))}
                        for n in services if n["attrs"].get("type") == "credential"],
        "platform": [n["name"] for n in services
                     if n["attrs"].get("type") in ("platform", "daemon")
                     and n["attrs"].get("available")],
        "grants": sorted(grants),
    }
    return _ENV


def settings(env: dict) -> dict[str, list[str]]:
    """The settings a skill is checked against: two published profiles and this machine."""
    def profile(name):
        return sorted({normalize_tool(t) for t in load_profile(name).tools})
    return {"claude.ai": profile("claude-ai"), "Claude Code": profile("claude-code"),
            "this machine": env["grants"]}


def _run(argv: list[str]) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = skillc(argv)
    return code, out.getvalue()


def check_skill(text: str, where: dict[str, list[str]]) -> dict:
    """Compile once (no tool is assumed), then bind and check against each setting."""
    if not text.strip():
        raise ValueError("paste a SKILL.md, an agent file or a prompt")
    if len(text) > MAX_SKILL:
        raise ValueError(f"the text is over {MAX_SKILL // 1000} KB")
    with _LOCK, tempfile.TemporaryDirectory(prefix="skillc-here-") as tmp:
        tmp = Path(tmp)
        src, pack_file, prov = tmp / "SKILL.md", tmp / "pack.json", tmp / "provenance.json"
        src.write_text(text, encoding="utf-8")
        code, out = _run(["compile", str(src), "--profile", "none", "--quiet",
                          "--output", str(pack_file), "--provenance-output", str(prov)])
        if code != 0 or not pack_file.exists():
            raise ValueError("skillc could not read this text: " + out.strip()[:300])
        pack = json.loads(pack_file.read_text(encoding="utf-8"))
        rows = []
        for name, grants in where.items():
            bound = bind_environment(pack, grants)
            bound_file = tmp / "bound.json"
            bound_file.write_text(json.dumps(bound.pack), encoding="utf-8")
            _code, out = _run(["check", str(bound_file), "--json", "--source", str(src),
                               "--compaction-provenance", str(prov)])
            v = json.loads(out)
            rows.append({"setting": name, "verdict": v.get("verdict"), "reason": v.get("reason"),
                         "detail": v.get("detail", ""), "missing": list(bound.unavailable),
                         "frontier": v.get("frontier", [])})
        return {"name": pack.get("name") or "skill", "needs": list(bound.required), "rows": rows}


def samples() -> list[dict]:
    return [{"name": p.stem, "text": p.read_text(encoding="utf-8")}
            for p in sorted((HERE / "skills").glob("*.md"))]


# --- tab 3: why skillc ----------------------------------------------------------------------

WHY = json.loads((HERE / "why_cases.json").read_text(encoding="utf-8"))
SETUP_PROFILE = {"coding": "claude-code", "chat": "claude-ai"}
_FIX = """Skill `fix-tests`.
Roles: `agent`.
Tool `run_tests` (owner `agent`): via `bash`; adds `tests_run`.
Tool `edit_code` (owner `agent`): via `edit`; requires `tests_run`; adds `fixed`.
Goal: `fixed`.
Protocol:
  - `agent` uses `run_tests`.
  - `agent` uses `edit_code`.
"""
_FINANCE = (ROOT / "examples" / "hosted-agent-finance" / "protocol"
            / "quarterly_finance_report.ce").read_text(encoding="utf-8")
PLANS = {
    "fix-tests": _FIX,
    "deploy": _FIX.replace(
        "Goal: `fixed`.",
        "Tool `deploy` (owner `agent`): via `bash`; needs `vercel_account`; requires `fixed`; "
        "adds `deployed`.\nGoal: `fixed` and `deployed`.").replace(
        "  - `agent` uses `edit_code`.\n",
        "  - `agent` uses `edit_code`.\n  - `agent` uses `deploy`.\n"),
    "finance": _FINANCE,
    "finance+email": _FINANCE.replace(
        "Initially true: none.",
        "Tool `send_email` (owner `Writer`): via `email`; requires `report_written`; "
        "adds `emailed`; effect `writes_external`.\nInitially true: none.").replace(
        "Goal: `report_delivered` and `approved`.",
        "Goal: `report_delivered` and `approved` and `emailed`.").replace(
        "      - `Writer` uses `deliver_report`.\n",
        "      - `Writer` uses `deliver_report`.\n      - `Writer` uses `send_email`.\n"),
}


def why_run(case_id: str) -> dict:
    """The skillc column of one case, decided live: a static check of the skill against the
    setup's tools, or the monitor over the plan and the actions the plain LLM attempted."""
    case = next((c for c in WHY["cases"] if c["id"] == case_id), None)
    if case is None:
        raise ValueError(f"unknown case {case_id!r}")
    spec = case["skillc"]
    if spec["mode"] == "static":
        name = SETUP_PROFILE[case["setup"]]
        grants = sorted({normalize_tool(t) for t in load_profile(name).tools})
        text = (HERE / "skills" / f"{spec['skill']}.md").read_text(encoding="utf-8")
        row = check_skill(text, {name: grants})["rows"][0]
        return {"mode": "static", "skill": text, "profile": name, **row}
    plan = PLANS[spec["plan"]]
    with _LOCK, tempfile.TemporaryDirectory(prefix="skillc-here-") as tmp:
        mon = Monitor(Config(**spec.get("config", {})), tmp)
        d = mon.submit_plan(plan)
        out = {"mode": "runtime", "plan": plan, "plan_decision": d.action,
               "plan_reason": d.reason, "steps": [], "stopped": d.action == "deny"}
        if d.action == "deny":
            return out
        for tool, inp, role, result in spec["trace"]:
            kw = {"role": role} if role else {}
            d = mon.pre_action(tool, inp, **kw)
            out["steps"].append({"tool": tool, "input": inp, "role": role,
                                 "decision": d.action, "reason": d.reason})
            if d.action == "deny":
                out["stopped"] = True
                break
            mon.post_action(tool, inp, result, **kw)
        return out


def measured_benchmark(runs: Path | None = None) -> dict:
    """Expose only measured aggregate data, never raw local settings or transcripts."""
    paths = sorted((runs or ROOT / "runs").glob("*_here_benchmark/results.json"),
                   key=lambda p: p.parent.name, reverse=True)
    if not paths:
        return {"available": False, "reason": "No local benchmark has been run yet."}
    path = paths[0]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema") != "skillc.here-benchmark/1":
            raise ValueError("unrecognized benchmark schema")
        expected = len(data["cases"]) * data["repeats"] * (3 if data["live"] else 1)
        return {"available": True, "run": path.parent.name, "model": data["model"],
                "live": data["live"], "completed": len(data["rows"]) == expected,
                "trials": len(data["rows"]), "expected_trials": expected,
                "summary": data["summary"], "discovery_ms": data["discovery_ms"],
                "cases": [{"id": c["id"], "source": c["source"],
                           "feasible": data["oracle"].get(c["id"], {}).get("feasible")}
                          for c in data["cases"]]}
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {"available": False, "reason": f"Cannot read benchmark: {error}"}


# --- tab 2: a graph -----------------------------------------------------------------------

def _graph_file(tmp: Path, filename: str, data: bytes) -> Path:
    suffix = Path(filename or "graph.ttl").suffix.lower()
    if suffix not in GRAPH_SUFFIXES:
        raise ValueError(f"a graph file ends in one of {', '.join(GRAPH_SUFFIXES)} "
                         "(JSON-LD is refused: it can fetch remote contexts)")
    if len(data) > MAX_GRAPH:
        raise ValueError(f"the graph is over {MAX_GRAPH // 1_000_000} MB")
    path = tmp / f"graph{suffix}"
    path.write_bytes(data)
    return path


def twin_explore(filename: str, data: bytes, tenant: str | None = None) -> dict:
    from skillc.env.twin import load_twin
    from skillc.env.twin_workflow import explore
    with _LOCK, tempfile.TemporaryDirectory(prefix="skillc-here-") as tmp:
        path = _graph_file(Path(tmp), filename, data)
        text = explore(load_twin(path, tenant=tenant or None))
        return {"text": text.replace(str(path), Path(filename).name or path.name)}


def _result(r) -> dict:
    return {"target": r.target, "verdict": r.verdict,
            "missing": [e.key for e in r.missing],
            "found": [e.key for e in r.evidence if e.status == "found"],
            "evidence": [{"key": e.key, "need": e.need, "status": e.status,
                          "critical": e.critical, "found": e.found, "note": e.note}
                         for e in r.evidence]}


def twin_check(filename: str, data: bytes, workflow: str, tenant: str | None = None) -> dict:
    """Check a pasted workflow against the graph; with no workflow, run the built-in
    set-point and schedule-update verifiers."""
    from skillc.env.twin import SCENARIOS, load_twin, text_report, verify_all
    from skillc.env.twin_workflow import read_workflows, verify_workflow, workflow_targets
    with _LOCK, tempfile.TemporaryDirectory(prefix="skillc-here-") as tmp:
        twin = load_twin(_graph_file(Path(tmp), filename, data), tenant=tenant or None)
        out = []
        if not workflow.strip():
            for name, sc in SCENARIOS.items():
                results = verify_all(twin, name)
                reading = (f"built-in {sc['title']}: "
                           + ", ".join(k for k, *_ in sc["evidence"]))
                out.append({"title": sc["title"], "reading": reading,
                            "results": [_result(r) for r in results],
                            "report": text_report(results, True)})
            return {"workflows": out}
        for wf in read_workflows(workflow):
            results = [verify_workflow(twin, wf, t) for t in workflow_targets(twin, wf)]
            out.append({"title": wf.title, "reading": wf.describe(),
                        "results": [_result(r) for r in results],
                        "report": text_report(results, True)})
        return {"workflows": out}


def twin_graph(filename: str, data: bytes, tenant: str | None = None,
               max_nodes: int = 800) -> dict:
    """The tenant graph as nodes and links for drawing. Entities are nodes; a link is a fact
    between two entities. Classes, units, literals and blank-node structures become node
    details, read through the entity that owns them."""
    from rdflib import RDF, BNode, Literal
    from skillc.env.twin import EQUIP_WORDS, _is_place, _is_point, load_twin, local
    with _LOCK, tempfile.TemporaryDirectory(prefix="skillc-here-") as tmp:
        twin = load_twin(_graph_file(Path(tmp), filename, data), tenant=tenant or None)
        g = twin.graph
        entities = [s for s in dict.fromkeys(g.subjects()) if not isinstance(s, BNode)]
        keep = set(entities[:max_nodes])

        def kind(n):
            if _is_point(twin, n):
                return "point"
            if twin.is_a(n, ("schedule",)):
                return "schedule"
            if twin.is_a(n, ("policy",)):
                return "policy"
            if twin.is_a(n, ("building", "floor", "storey", "site")):
                return "structure"
            if _is_place(twin, n):
                return "place"
            if twin.is_a(n, EQUIP_WORDS):
                return "equipment"
            return "other"

        nodes, edges = [], []
        for n in keep:
            types = sorted(local(c) for c in g.objects(n, RDF.type))
            details = []
            for p, o in g.predicate_objects(n):
                if p == RDF.type or o in keep:
                    continue
                if isinstance(o, BNode):
                    inner = sorted({local(q) for q in g.predicates(o) if q != RDF.type})
                    kinds = sorted({local(c) for c in g.objects(o, RDF.type)})
                    details.append([local(p), "{" + ", ".join(kinds + inner) + "}"])
                else:
                    details.append([local(p), str(o) if isinstance(o, Literal)
                                    else twin.label(o)])
            nodes.append({"id": twin.label(n), "kind": kind(n), "types": types,
                          "details": sorted(details)})
            for p, o in g.predicate_objects(n):
                if o in keep and p != RDF.type:
                    edges.append({"s": twin.label(n), "t": twin.label(o), "p": local(p)})
        return {"nodes": nodes, "edges": edges, "facts": len(g),
                "truncated": len(entities) > max_nodes}


# --- server -------------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args) -> None:
        pass

    def _local_host(self) -> bool:
        """Answer only requests addressed to the loopback name (DNS rebinding)."""
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        return host in ("127.0.0.1", "localhost")

    def do_GET(self) -> None:
        path, _, query = self.path.partition("?")
        if path in ("/", "/index.html"):
            return self._send(HTTPStatus.OK, (HERE / "static" / "index.html").read_bytes(),
                              "text/html; charset=utf-8")
        if not self._local_host():
            return self._json(HTTPStatus.FORBIDDEN, {"error": "answers 127.0.0.1 only"})
        if path == "/api/environment":
            env = read_environment(refresh="refresh=1" in query)
            return self._json(HTTPStatus.OK, {**env, "settings": settings(env)})
        if path == "/api/why":
            return self._json(HTTPStatus.OK, WHY)
        if path == "/api/benchmark":
            return self._json(HTTPStatus.OK, measured_benchmark())
        if path == "/api/samples":
            return self._json(HTTPStatus.OK, {
                "skills": samples(),
                "graph": {"name": GRAPH_EXAMPLE.name,
                          "text": GRAPH_EXAMPLE.read_text(encoding="utf-8")},
                "graphs": [{"name": g.name, "text": g.read_text(encoding="utf-8")}
                           for g in (GRAPH_EXAMPLE, GRAPH_SMALL)],
                "workflow": WORKFLOW_EXAMPLE.read_text(encoding="utf-8")})
        return self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        if not self._local_host():
            return self._json(HTTPStatus.FORBIDDEN, {"error": "answers 127.0.0.1 only"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_GRAPH * 2:
                raise ValueError("the request is too large")
            body = json.loads(self.rfile.read(length) or b"{}")
            if self.path == "/api/check":
                where = settings(read_environment())
                if isinstance(body.get("machine"), list):  # the page's what-if edits
                    where["this machine"] = sorted({normalize_tool(str(t))
                                                    for t in body["machine"] if str(t).strip()})
                return self._json(HTTPStatus.OK, check_skill(str(body.get("text", "")), where))
            if self.path == "/api/why/run":
                return self._json(HTTPStatus.OK, why_run(str(body.get("id", ""))))
            graph = str(body.get("graph", "")).encode("utf-8")
            if self.path == "/api/twin/graph":
                return self._json(HTTPStatus.OK, twin_graph(body.get("filename", ""), graph,
                                                            body.get("tenant")))
            if self.path == "/api/twin/explore":
                return self._json(HTTPStatus.OK, twin_explore(body.get("filename", ""), graph,
                                                              body.get("tenant")))
            if self.path == "/api/twin/check":
                return self._json(HTTPStatus.OK, twin_check(body.get("filename", ""), graph,
                                                            str(body.get("workflow", "")),
                                                            body.get("tenant")))
        except (ValueError, json.JSONDecodeError) as e:
            return self._json(HTTPStatus.BAD_REQUEST, {"error": str(e)})
        except Exception as e:  # a parser error in an uploaded graph, say
            return self._json(HTTPStatus.BAD_REQUEST, {"error": f"{type(e).__name__}: {e}"[:400]})
        return self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

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
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--no-browser", action="store_true", help="do not open a browser tab")
    args = ap.parse_args(argv)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"skillc here: {url}  (offline, no model call; Ctrl+C to stop)", flush=True)
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

"""Readable outputs for environments and reach results.

    env_summary(env)          text: what the environment contains
    text_report(result)       text: per condition, the plan, the blockers
    english_plan(result)      Markdown: numbered steps in plain English + the
                              plan as Controlled English
    html_page(env, result)    one self-contained page: the environment
                              topology and the intent graph, colour-coded
"""
from __future__ import annotations

import html
import json
from collections import Counter

from ..frontend.ce import render_ce
from .model import Environment
from .reach import ReachResult, explain_scope, readable

MARK = {"achievable": "OK ", "assumed": "OK*", "blocked": "NO "}


# --------------------------------------------------------------------------
# Text
# --------------------------------------------------------------------------

def env_summary(env: Environment) -> str:
    counts = Counter(n["kind"] for n in env.nodes.values())
    principal = env.principal()
    lines = [f"environment captured {env.captured_at}",
             *(f"  source: {s['adapter']} ({s['mode']}) {s.get('detail', '')}"
               for s in env.sources),
             f"  principal: {principal['name'] if principal else '(none)'}",
             "  " + ", ".join(f"{n} {k}" for k, n in sorted(counts.items()))]
    for e in env.edges:
        if e["kind"] == "assigned":
            lines.append(f"  role {env.nodes[e['dst']]['name']!r} at "
                         f"{explain_scope(e['attrs'].get('scope', '/'))}")
    for p in env.of_kind("policy"):
        a = p["attrs"]
        rule = a.get("rule", {})
        values = f" {rule.get('values')}" if rule.get("values") else ""
        lines.append(f"  policy {p['name']!r}: {a.get('effect')} {rule.get('kind')}{values}")
    for server in env.of_kind("mcp_server"):
        tools = [env.nodes[e["dst"]]["name"] for e in env.out_edges(server["id"], "exposes")]
        lines.append(f"  mcp server {server['name']!r}: "
                     + (", ".join(tools) if tools else "tools not listed"))
    if env.unknown:
        lines.append("  not read (treated as assumptions, never as refusals):")
        lines += [f"    - {u['what']}: {u.get('why', '')}" for u in env.unknown]
    return "\n".join(lines)


def text_report(result: ReachResult) -> str:
    intent = result.intent
    lines = [f"intent: {intent.get('name')} -- {intent.get('description', '')}".rstrip(" -"),
             f"target: {explain_scope(intent['target']['scope'])}"
             f" in {intent['target'].get('location', '?')}",
             f"environment captured {result.captured_at}", "",
             "conditions (OK = achievable, OK* = achievable under assumptions, NO = blocked):"]
    for cond, status in result.status.items():
        lines.append(f"  {MARK[status]} {cond}")
    if result.plan:
        lines += ["", f"plan ({result.plan_verdict.label} by the trusted checker):"]
        for i, step in enumerate(result.plan, 1):
            lines.append(f"  {i}. {step.title}")
            lines.append(f"       $ {step.how}")
    if result.blockers:
        lines += ["", "blocked, and what would unblock it:"]
        for b in result.blockers:
            lines.append(f"  - {b.condition}: {b.title}")
            lines += [f"      why: {readable(w)}" for w in b.why]
            lines += [f"      fix: {readable(u)}" for u in b.unblock]
    if result.assumptions:
        lines += ["", "assumed (not observed in the environment):"]
        lines += [f"  - {a}" for a in result.assumptions]
    n_ok = sum(s != "blocked" for s in result.status.values())
    summary = f"{n_ok}/{len(result.status)} conditions achievable"
    if result.blocked:
        summary += ("; blocked conditions are certified unreachable with the operations "
                    "this environment allows (checker: GOAL_UNSAT)")
    elif not result.complete:
        summary += " under the assumptions above"
    lines += ["", summary]
    return "\n".join(lines)


def english_plan(result: ReachResult) -> str:
    intent = result.intent
    out = [f"# Plan: {intent.get('name')}", "",
           intent.get("description", ""), "",
           f"Target: {explain_scope(intent['target']['scope'])}, "
           f"location {intent['target'].get('location', '?')}. "
           f"Environment snapshot: {result.captured_at}.", ""]
    if result.plan:
        out += ["## What you can do now", ""]
        for i, step in enumerate(result.plan, 1):
            why = readable("; ".join(step.why)) or "nothing in the environment refuses it"
            out.append(f"{i}. **{step.title}.** Allowed because {why}.")
            if step.via_mcp:
                out.append(f"   An MCP tool can also do it: {', '.join(step.via_mcp)}.")
            if step.assumptions:
                out.append(f"   This assumes: {'; '.join(step.assumptions)}.")
            out.append(f"   `{step.how}`")
    done = [c for c, s in result.status.items() if s != "blocked"]
    out += ["", f"After these steps these conditions hold: {', '.join(done) or 'none'}."]
    if result.blockers:
        out += ["", "## What cannot be done here yet", ""]
        by_condition: dict[str, list] = {}
        for b in result.blockers:
            by_condition.setdefault(b.condition, []).append(b)
        for cond, routes in by_condition.items():
            if len(routes) == 1:
                b = routes[0]
                out.append(f"- **{cond}** ({b.title}): {readable('; '.join(b.why))}. "
                           f"To unblock: {readable('; '.join(b.unblock))}.")
                continue
            out.append(f"- **{cond}** can be reached in any of {len(routes)} ways, "
                       "none open yet:")
            for i, b in enumerate(routes, 1):
                out.append(f"  {i}. {b.title}: {readable('; '.join(b.why))}. "
                           f"To unblock: {readable('; '.join(b.unblock))}.")
    if result.assumptions:
        out += ["", "## Assumptions", "",
                *(f"- {a}" for a in result.assumptions),
                "", "These were not observed; re-probe the environment to confirm them."]
    out += ["", "## The plan as Controlled English", "", "```ce",
            render_ce(result.pack).rstrip(), "```"]
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------

COL_W, ROW_H, NODE_W, NODE_H = 215, 40, 185, 28
ENV_COLUMNS = (("principal",), ("role", "deny"), ("scope", "policy"),
               ("resource", "data", "service"), ("mcp_server",), ("tool",))
STATUS_CLASS = {"achievable": "ok", "assumed": "assumed", "blocked": "blocked"}


def _layout(columns: list[list[tuple[str, str, str, str]]]) -> tuple[dict, int, int]:
    """columns of (id, label, css class, tooltip) -> positions, width, height."""
    pos = {}
    for c, col in enumerate(columns):
        for r, (node_id, *_rest) in enumerate(col):
            pos[node_id] = (20 + c * COL_W, 30 + r * ROW_H)
    width = 40 + len(columns) * COL_W
    height = 60 + max((len(c) for c in columns), default=1) * ROW_H
    return pos, width, height


def _svg(columns, edges, title: str) -> str:
    pos, width, height = _layout(columns)
    parts = [f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
             f'role="img" aria-label="{html.escape(title)}">']
    for src, dst, cls in edges:
        if src in pos and dst in pos:
            (x1, y1), (x2, y2) = pos[src], pos[dst]
            x1, y1, y2 = x1 + NODE_W, y1 + NODE_H / 2, y2 + NODE_H / 2
            mid = (x1 + x2) / 2
            parts.append(f'<path class="edge {cls}" d="M{x1},{y1} C{mid},{y1} {mid},{y2} '
                         f'{x2},{y2}"/>')
    for col in columns:
        for node_id, label, cls, tip in col:
            x, y = pos[node_id]
            short = label if len(label) <= 26 else label[:25] + "…"
            parts.append(f'<g class="node {cls}"><title>{html.escape(tip)}</title>'
                         f'<rect x="{x}" y="{y}" width="{NODE_W}" height="{NODE_H}" rx="6"/>'
                         f'<text x="{x + 10}" y="{y + 18}">{html.escape(short)}</text></g>')
    return "\n".join(parts) + "\n</svg>"


def env_graph_svg(env: Environment) -> str:
    columns = []
    for kinds in ENV_COLUMNS:
        nodes = sorted((n for n in env.nodes.values() if n["kind"] in kinds),
                       key=lambda n: (kinds.index(n["kind"]), n["id"]))
        columns.append([(n["id"], f"{n['kind']}: {n['name']}", f"k-{n['kind']}",
                         json.dumps(n["attrs"], default=str)[:400]) for n in nodes])
    columns = [c for c in columns if c]
    edges = [(e["src"], e["dst"], e["kind"]) for e in env.edges]
    # an assignment reads principal -> role -> scope
    edges += [(e["dst"], e["attrs"]["scope"].lower().rstrip("/") or "/", "assigned")
              for e in env.edges if e["kind"] in ("assigned", "denied") and "scope" in e["attrs"]]
    return _svg(columns, edges, "environment topology")


def intent_graph_svg(result: ReachResult) -> str:
    ops = {o["id"]: o for o in result.operations}
    catalog_ops = {op["id"]: op for op in result.catalog["operations"]}
    status = result.status
    held = set(result.initial)
    plan_ids = [s.op for s in result.plan]
    depth: dict[str, int] = dict.fromkeys(held, 0)

    def cond_depth(c: str, seen=()) -> int:
        if c in depth:
            return depth[c]
        makers = [o for o in catalog_ops.values() if c in o.get("adds", [])]
        if not makers or c in seen:
            depth[c] = 0
            return 0
        depth[c] = 1 + min(op_depth(o, (*seen, c)) for o in makers)
        return depth[c]

    def op_depth(o: dict, seen=()) -> int:
        reqs = o.get("requires", [])
        return 1 + max((cond_depth(r, seen) for r in reqs), default=0)

    relevant_conds, relevant_ops, stack = set(), set(), list(status)
    while stack:
        c = stack.pop()
        if c in relevant_conds:
            continue
        relevant_conds.add(c)
        for o in catalog_ops.values():
            if c in o.get("adds", []):
                relevant_ops.add(o["id"])
                stack += o.get("requires", [])
    for c in relevant_conds:
        cond_depth(c)
    columns: dict[int, list] = {}
    for c in sorted(relevant_conds):
        cls = ("ok" if c in held and c not in status else
               STATUS_CLASS.get(status.get(c), "ok" if c in held else "pending"))
        reached = c in held or any(c in catalog_ops[o].get("adds", []) for o in plan_ids)
        if c not in status:
            cls = "ok" if reached else "blocked"
        tip = f"condition {c}" + (" (holds already)" if c in held else "")
        columns.setdefault(2 * depth[c], []).append((f"c:{c}", c, f"cond {cls}", tip))
    for oid in sorted(relevant_ops):
        o = catalog_ops[oid]
        info = ops.get(oid, {})
        not_needed = set(o.get("adds", [])) <= held
        cls = ("ok plan" if oid in plan_ids else
               "idle" if not_needed or info.get("available") else "unavailable")
        tip = f"{o['title']}\n" + "\n".join(info.get("why", []) + info.get("assumptions", []))
        columns.setdefault(2 * op_depth(o) - 1, []).append((f"o:{oid}", o["title"],
                                                             f"op {cls}", tip))
    ordered = [columns[k] for k in sorted(columns)]
    edges = []
    for oid in relevant_ops:
        o = catalog_ops[oid]
        edges += [(f"c:{r}", f"o:{oid}", "req") for r in o.get("requires", [])]
        edges += [(f"o:{oid}", f"c:{a}", "add") for a in o.get("adds", []) if a in relevant_conds]
    return _svg(ordered, edges, "intent graph")


STYLE = """
:root { --bg:#fbfaf7; --fg:#1d232b; --muted:#5b6672; --card:#ffffff; --line:#c9cfd6;
  --ok:#2f8f5b; --okbg:#e3f3ea; --as:#a8730f; --asbg:#fbf0d9; --no:#b8423a; --nobg:#f8e2df;
  --idle:#8a96a3; --idlebg:#eef1f4; --k:#3d6fb6; --kbg:#e5eefa; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg:#14181d; --fg:#e7ebef; --muted:#9aa6b2; --card:#1c2229; --line:#3a444f;
  --ok:#5fc48c; --okbg:#173326; --as:#e0a93b; --asbg:#3a2d12; --no:#ec7468; --nobg:#3b1d1a;
  --idle:#7d8996; --idlebg:#232a32; --k:#7aa7e8; --kbg:#1b2a3f; } }
body { margin:0; background:var(--bg); color:var(--fg);
  font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }
main { max-width:1200px; margin:0 auto; padding:24px 16px 48px; }
h1 { font-size:24px; margin:0 0 4px } h2 { font-size:18px; margin:28px 0 8px }
.muted { color:var(--muted) } .card { background:var(--card); border:1px solid var(--line);
  border-radius:10px; padding:14px 16px; margin:10px 0 }
.scroll { overflow-x:auto } svg { font-size:12px; display:block }
.node rect { fill:var(--kbg); stroke:var(--k); stroke-width:1 } .node text { fill:var(--fg) }
.cond.ok rect, .op.ok rect { fill:var(--okbg); stroke:var(--ok) }
.cond.assumed rect { fill:var(--asbg); stroke:var(--as) }
.cond.blocked rect, .op.unavailable rect { fill:var(--nobg); stroke:var(--no) }
.cond.pending rect, .op.idle rect { fill:var(--idlebg); stroke:var(--idle) }
.op rect { rx:14 } .op.plan rect { stroke-width:2 }
.edge { fill:none; stroke:var(--line); stroke-width:1.2 } .edge.add { stroke:var(--ok) }
.edge.req { stroke:var(--idle); stroke-dasharray:4 3 }
.legend span { display:inline-block; padding:2px 8px; border-radius:6px; margin-right:6px;
  border:1px solid var(--line) }
.l-ok { background:var(--okbg) } .l-as { background:var(--asbg) } .l-no { background:var(--nobg) }
table { border-collapse:collapse; width:100%; table-layout:fixed } td, th { text-align:left;
  padding:6px 8px; border-bottom:1px solid var(--line); vertical-align:top;
  overflow-wrap:anywhere }
code { font-size:13px; overflow-wrap:anywhere } li { overflow-wrap:anywhere }
.s-achievable { color:var(--ok) } .s-assumed { color:var(--as) }
.s-blocked { color:var(--no) }
"""


def html_page(env: Environment, result: ReachResult | None = None) -> str:
    title = (f"Reach: {result.intent.get('name')}" if result else "Environment topology")
    body = [f"<h1>{html.escape(title)}</h1>",
            f'<p class="muted">Environment snapshot {html.escape(env.captured_at)} · '
            + " · ".join(html.escape(f"{s['adapter']} ({s['mode']})") for s in env.sources)
            + "</p>"]
    if result is not None:
        n_ok = sum(s != "blocked" for s in result.status.values())
        body += [f'<div class="card"><strong>{n_ok} of {len(result.status)}</strong> goal '
                 f"conditions achievable in this environment. "
                 + ("Blocked conditions are certified unreachable by the checker over the "
                    "operations this environment allows." if result.blocked else "")
                 + "</div>",
                 '<p class="legend"><span class="l-ok">achievable</span>'
                 '<span class="l-as">under assumptions</span>'
                 '<span class="l-no">blocked</span></p>',
                 "<h2>Intent graph</h2>",
                 '<p class="muted">Conditions (boxes) and the operations that establish them '
                 "(rounded). Thick: on the plan. Red operation: not allowed here. Grey: not "
                 "needed or not on the plan. Scroll sideways for the whole graph.</p>",
                 f'<div class="card scroll">{intent_graph_svg(result)}</div>',
                 "<h2>Conditions</h2><table><tr><th>condition</th><th>status</th></tr>"]
        body += [f'<tr><td><code>{html.escape(c)}</code></td>'
                 f'<td class="s-{s}">{s}</td></tr>' for c, s in result.status.items()]
        body.append("</table>")
        if result.plan:
            body.append("<h2>Plan</h2><ol>")
            body += [f"<li><strong>{html.escape(s.title)}</strong><br>"
                     f'<span class="muted">{html.escape(readable("; ".join(s.why)))}</span><br>'
                     f"<code>{html.escape(s.how)}</code></li>" for s in result.plan]
            body.append("</ol>")
        if result.blockers:
            body.append("<h2>Blocked, and what would unblock it</h2><table>"
                        "<tr><th>condition</th><th>why</th><th>fix</th></tr>")
            body += [f"<tr><td><code>{html.escape(b.condition)}</code><br>"
                     f'<span class="muted">{html.escape(b.title)}</span></td>'
                     f"<td>{'<br>'.join(html.escape(readable(w)) for w in b.why)}</td>"
                     f"<td>{'<br>'.join(html.escape(readable(u)) for u in b.unblock)}</td></tr>"
                     for b in result.blockers]
            body.append("</table>")
        if result.assumptions:
            body.append("<h2>Assumptions</h2><ul>")
            body += [f"<li>{html.escape(a)}</li>" for a in result.assumptions]
            body.append("</ul>")
    body += ["<h2>Environment topology</h2>",
             '<p class="muted">Who you are, the roles you hold where, the scopes and '
             "policies over them, the services, resources and data, and the MCP tools "
             "connected to your agent. Hover a box for details.</p>",
             f'<div class="card scroll">{env_graph_svg(env)}</div>']
    if env.unknown:
        body.append("<h2>Not read</h2><ul>")
        body += [f"<li><code>{html.escape(u['what'])}</code>: {html.escape(u.get('why', ''))}"
                 "</li>" for u in env.unknown]
        body.append("</ul>")
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{html.escape(title)}</title><style>{STYLE}</style></head>"
            f"<body><main>{''.join(body)}</main></body></html>\n")

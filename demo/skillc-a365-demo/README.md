# One task. Two agents.

![One task. Two agents: the EchoLeak case replayed without and with skillc](../../docs/images/a365_demo.jpg)


A small local demo: the same Microsoft Agent 365 workflow replayed side by side, one agent
with no guard and one with skillc attached as Agent Framework middleware. You see the exact
step where skillc questions the agent's reasoning and refuses the tool call.

```bash
python demo/skillc-a365-demo/app.py            # opens http://127.0.0.1:8765/
python demo/skillc-a365-demo/app.py --port 9000 --no-browser
```

Python 3.12, standard library only. Offline: no model calls, no network, no tenant.

## What it shows

* Eight published incidents from `benchmark/interaction_cases/` (Replit database deletion,
  EchoLeak, GitHub MCP private-repo leak, Operator purchase, Copilot auto-approve, Gemini
  calendar smart-home, Copilot Studio email, Dragon Copilot PHI). Each has its source links.
* **Left, no guard:** the trace plays step by step; the hazardous tool call fires.
* **Right, skillc middleware:** the plan is checked first, each step gets skillc's decision
  (allowed / skillc question / refused, with the reason and who can fix it), and the steps after
  the first refusal are shown as not reached.
* **Benign twin:** replays the legitimate version of the same task, to show that it is allowed.
* Metrics per card: steps executed, wrong actions fired, skillc decisions, measured decision
  latency, model tokens used by skillc (0), and estimated run tokens.

## What is replayed and what is live

* **Replayed:** the agent's side. Thinking, tool calls and tool results are the authored
  traces in the case files (abstractions of the published incidents). No agent runs.
* **Live:** every skillc decision. Each run creates a fresh `skillc.monitor.Monitor` with the
  helpers of `scripts/run_interaction_cases.py` in strip-rules mode (the case's `prohibited`
  rules are removed, so the guard gets no case-specific help), submits the plan, and calls
  `observe_thinking` / `pre_action` / `post_action` per step. The latency is wall-clock time per
  call. The decisions match the benchmark run
  `runs/20261013T175359Z_interaction_dev_final3_guard_v3_strip/results.json`.
* **Estimated:** run tokens use `skillc.tokens.RuntimeModel` defaults with turns = tool calls + 1.
  This is an order-of-magnitude estimate, not a measurement.

The "How skillc is attached" panel shows the production wiring
(`skillc_monitor(..., strict=True, fail_open=False)` and `middleware_for(...)`). This demo calls
the same monitor directly; it does not run Agent Framework.

## API

* `GET /api/cases`: the case list (id, label, title, category, runtime, hazards, summary, sources).
* `POST /api/run` with `{"id": "<case id>", "twin": false}`: plan verdict, per-step decisions
  with reason, next, user_needs and latency, and metrics. An unknown id returns 400.

The server binds to 127.0.0.1 only.

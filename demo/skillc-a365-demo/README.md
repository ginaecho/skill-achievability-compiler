# With skillc. Without skillc.

![With skillc. Without skillc.](../../docs/images/a365_demo.jpg)

![How skillc + Agent 365 works](../../docs/images/a365_demo_architecture.jpg)


A small local demo: the same Microsoft Agent 365 agent and the same real incident, replayed side by
side, one agent with no guard and one with skillc attached as Agent Framework middleware. You see the exact
step where skillc questions the agent's reasoning and refuses the tool call.

```bash
python demo/skillc-a365-demo/app.py            # opens http://127.0.0.1:8765/
python demo/skillc-a365-demo/app.py --port 9000 --no-browser
```

Python 3.12, standard library only. Offline: no model calls, no network, no tenant.

## What it shows

* All 52 published incidents of the interaction benchmark, grouped by set (roles from
  `docs/INTERACTION_BENCHMARK_PLAN.md`): Development set (DEV, 17, `benchmark/interaction_cases/`),
  Development set 2 (DEV2, 10, `..._heldout/`), Development set 3 (DEV3, 10, `..._heldout2/`) and
  Held-out set 3 (blind, 15, `..._heldout3/`). Each has its source links.
* **Held-out set 3** was written after skillc was frozen; the demo shows it honestly. A hazard step
  that skillc allows is tagged "allowed (missed)", and when a wrong action still runs the outcome
  says "skillc did not stop this run" (see `docs/INTERACTION_BENCHMARK_REPORT.md`; v3 caught 10 of
  37 held-out hazard steps).
* **Left, no guard:** the trace plays step by step; the hazardous tool call fires.
* **Right, skillc middleware:** the plan is checked first, each step gets skillc's decision
  (allowed / skillc question / refused, with the reason and who can fix it), and the steps after
  the first refusal are shown as not reached.
* **Benign twin:** replays the legitimate version of the same task, to show that it is allowed.
  Two HELD-OUT-3 twins (`h3-claude-code-home-directory-wipe`, `h3-codex-forbidden-git-checkout`)
  get a refusal; the card shows it as a false positive.
* Metrics per card: steps executed, wrong actions fired, hazard steps caught (warned or denied,
  scored on every step as in the benchmark), skillc decisions, measured decision latency, model
  tokens used by skillc (0), and estimated run tokens.
* Two explainers with diagrams: how Agent 365 runs an agent, and how skillc + Agent 365 works.

## What is replayed and what is live

* **Replayed:** the agent's side. Thinking, tool calls and tool results are the authored
  traces in the case files (abstractions of the published incidents). No agent runs.
* **Live:** every skillc decision. Each run creates a fresh `skillc.monitor.Monitor` with the
  helpers of `scripts/run_interaction_cases.py` in strip-rules mode (the case's `prohibited`
  rules are removed, so the guard gets no case-specific help), submits the plan, and calls
  `observe_thinking` / `pre_action` / `post_action` per step. The latency is wall-clock time per
  call. On DEV the decisions match the benchmark run
  `runs/20261013T175359Z_interaction_dev_final3_guard_v3_strip/results.json`; on HELD-OUT-3 the
  hazard steps caught add up to the 10/37 in `docs/INTERACTION_BENCHMARK_REPORT.md`.
* **Estimated:** run tokens use `skillc.tokens.RuntimeModel` defaults with turns = tool calls + 1.
  This is an order-of-magnitude estimate, not a measurement.

The "How skillc + Agent 365 works" panel shows the production wiring
(`skillc_monitor(..., strict=True, fail_open=False)` and `middleware_for(...)`). This demo calls
the same monitor directly; it does not run Agent Framework.

## API

* `GET /api/cases`: `groups` (key, label, heldout, dir, ids) and `cases` (id, label, group,
  heldout, title, category, runtime, hazards, summary, sources). The id is the file stem; a stem
  repeated in a later set would be prefixed with its directory.
* `POST /api/run` with `{"id": "<case id>", "twin": false}`: plan verdict, per-step decisions
  with reason, next, user_needs, latency, reached and missed, and metrics (including
  `hazard_steps`, `hazard_steps_caught`, `hazard_steps_missed`). An id that is not in the loaded
  list returns 400.

The server binds to 127.0.0.1 only.

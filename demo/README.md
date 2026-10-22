# Demos

Every skillc demo lives in this folder. Each one has a README that starts the same way: **what it
shows**, **Run it**, and **Present it** (what to click and what to point at). Everything below runs
offline with no model call unless the table says so.

| Demo | What it shows | Run | Time |
|---|---|---|---|
| [**skillc here**](skillc-here/README.md) (start here) | skillc reads this machine's tools and permissions by itself and says what a skill can do here, next to claude.ai and Claude Code. Upload a graph to see what a workflow can establish from it. | `python demo/skillc-here/app.py` | 3 min |
| [**With skillc. Without skillc.**](skillc-a365-demo/README.md) | An Agent 365 agent replaying a published incident, side by side with and without skillc as middleware. | `python demo/skillc-a365-demo/app.py` | 5 min |
| [**Execution Atlas**](skillc-architecture-app/README.md) | One skill moving through the real compiler, stage by stage, with the Python behind each stage. | `python demo/skillc-architecture-app/app.py` | 5 min |
| [**Real skills, end to end**](real-skill-cases/README.md) | A recording: five public `SKILL.md` files compiled by a model and decided by the checker. Re-recording calls a model. | play the `.mp4` | 2 min |

## Which one to show

* **A first look, or "does it know my setup?"**: skillc here.
* **Security, Agent 365, "what would it have stopped?"**: With skillc. Without skillc.
* **Engineers, "how does the checker decide?"**: Execution Atlas.
* **"Does it work on real skills?"**: Real skills, end to end.

## Setup, once

```bash
pip install -e ".[dev,twin]"     # the skillc CLI, test tools and rdflib for graphs
```

Each app binds to 127.0.0.1 and opens a browser tab; pass `--no-browser` to stop that and `--port N`
to pick a port. The Agent 365 demo and the Execution Atlas both default to port 8765, so give one of
them `--port` to run both at once. skillc here uses 8770.

## Terminal versions

The same ideas without a browser:

```bash
skillc check SKILL.md --profile claude-code             # one skill against a runtime profile
skillc twin explore examples/building-twin/demo-building.trig
skillc twin check examples/building-twin/demo-building.trig --workflow examples/building-twin/workflow.md
python demo/skillc-a365-demo/app.py run replit-production-db-deletion --guard
python examples/agent365-finance/security_demo.py --state-dir runs/agent365-security-offline
```

## Rules for every demo

* No model call by default. A run that calls one needs `SKILLC_ALLOW_MODEL_CALLS=1`, set on purpose,
  and goes through the URL guard (see `CLAUDE.md`).
* Nothing is executed, sent or deleted. Only skillc's decisions are real.
* Never point a demo at a live tenant or production resource.

Benchmarks are not demos. The Execution Atlas benchmarks are in
[`skillc-architecture-app/benchmark/`](skillc-architecture-app/benchmark/README.md).

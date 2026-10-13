# With skillc. Without skillc.

![With skillc. Without skillc.](../../docs/images/a365_demo.jpg)

![How skillc + Agent 365 works](../../docs/images/a365_demo_architecture.jpg)


A small local demo: the same Microsoft Agent 365 agent in the same situation, run twice and shown as
two session logs, one with no guard and one with skillc attached as Agent Framework middleware. The
logs carry no judgement; the verdict appears only after both runs finish.

```bash
python demo/skillc-a365-demo/app.py            # opens http://127.0.0.1:8765/
python demo/skillc-a365-demo/app.py --port 9000 --no-browser
python demo/skillc-a365-demo/app.py run replit-production-db-deletion --guard [--twin]   # same log in the terminal
```

Python 3.12, standard library only. Offline: no model calls, no network, no tenant.

## The page

1. **The situation the agent was in.** For the selected case: the user's request, what the agent
   could see (short artifacts such as a system prompt excerpt, an e-mail, an issue, test output, each in
   a monospace block), the runtime and its tools (from `src/skillc/data/runtimes/<runtime>.json`), and
   the published sources.
2. **The runs.** Two terminal-style consoles stream a session log line by line with elapsed timestamps:
   session header (runtime, tools, model placeholder, tool middleware), `[user]` task, `[read]` of each
   artifact, `[assistant]` reasoning, `[tool]` calls and `[out]` outputs. The skillc console adds only
   what the agent would see: the plan write and the monitor's plan result (`[skillc]`), a skillc
   question as added context (`[context]`), and for a refused call the monitor's full refusal as the
   tool result, followed by one closing `[assistant]` line. No badges or commentary during the run.
3. **Run verdict.** Per run: steps and tool calls executed, wrong actions fired, where it stopped, what
   happened in the published incident (or workflow), and for skillc the hazard steps caught (benchmark
   metric), false positives, decisions, measured decision latency, model tokens (0) and estimated run
   tokens; then a step-by-step table of the labelled steps.

The **benign twin** toggle runs the legitimate version of the same task; any skillc question or
refusal on it is reported as a false positive. Two explainers with diagrams follow: how Agent 365 runs
an agent, and how skillc + Agent 365 works.

## Cases

The dropdown lists the 8 showcase cases that have a context file in `cases/`:
`replit-production-db-deletion`, `echoleak-m365-copilot`, `github-mcp-private-repo-leak`,
`operator-egg-purchase-no-consent`, `copilot-autoapprove-settings`, `gemini-calendar-smarthome`,
`copilot-studio-email-approval`, `dragon-copilot-phi-boundary` (all in the DEV set).

`cases/<case-id>.json` holds `agent`, `task` (the user's request), `artifacts` (`name`, `kind`,
`content`, and `step` when the artifact is the output of that tool call; without `step` it is read at
the start of the session), `tool_outputs` and `twin_tool_outputs` keyed by step number,
`after_refusal` (the agent's closing line after a refusal) and `incident_outcome` (one sentence from
the sources). Placeholders stand in for addresses, payloads and personal data; injected instructions
are described in one plain clause. Adding a case means adding one such file; the benchmark files under
`benchmark/` are not modified.

## What is replayed and what is live

* **Replayed:** the agent's reasoning and tool calls, from the benchmark case files (abstractions of
  the published incidents). No agent runs.
* **Fixtures:** the task, the artifacts and the tool outputs, reconstructed from the published incident
  (`cases/`). The page footnote says so.
* **Live:** every skillc line. Each run creates a fresh `skillc.monitor.Monitor` with the helpers of
  `scripts/run_interaction_cases.py` in strip-rules mode (the case's `prohibited` rules are removed),
  submits the plan, and calls `observe_thinking` / `pre_action` / `post_action` per step; the latency
  of each call is measured. The run with skillc stops at the first refused call.
* **Estimated:** run tokens use `skillc.tokens.RuntimeModel` defaults with turns = tool calls + 1.

Timestamps in the consoles are the elapsed wall-clock time of the replay in the browser. The
middleware line in the header shows the production wiring (`skillc_monitor(..., strict=True,
fail_open=False)`); this demo calls the same monitor directly and does not run Agent Framework.

## API

* `GET /api/cases`: `groups` (key, label, heldout, dir, ids) and `cases` (id, label, title, category,
  kind, agent, task, artifacts, runtime {name, description, tools, lacks}, twin_note, sources).
* `POST /api/run` with `{"id": "<case id>", "twin": false}`: `logs.no_guard` and `logs.skillc` (lines
  `{k, text, ms}`), `verdict` (labelled steps, false positives, per-run tool calls, wrong actions,
  where skillc stopped, incident outcome), plus the plan result, per-step decisions and `metrics`. An
  id that is not listed returns 400.

The server binds to 127.0.0.1 only.

# With skillc. Without skillc. (Agent 365)

**Shows:** the same Agent 365 agent in the same situation, run twice side by side: once with no guard,
once with skillc as Agent Framework middleware. The agent's steps replay published incidents; every
skillc decision is live. **Audience:** security and platform owners. **Time:** 5 minutes.

## Run it

```bash
pip install -e ".[dev]"
python demo/skillc-a365-demo/app.py            # opens 127.0.0.1:8765
python demo/skillc-a365-demo/app.py run replit-production-db-deletion --guard   # the same log in a terminal
```

Standard library only; offline: no model calls, no network, no tenant. A hosted copy runs on Azure
Container Apps ([`deploy/README.md`](deploy/README.md)).

## Present it

1. Pick **replit-production-db-deletion**. Read the situation aloud: the user's request, what the agent
   could see, its runtime and tools.
2. Press run. Without skillc, the agent drops the production table. With skillc, the plan is checked
   first and the destructive call is refused; the agent gets the refusal as its tool result.
3. Read the verdict panel: hazard steps caught, false positives, decision latency, 0 model tokens.
4. Tick **benign twin** and run again: the legitimate version of the task goes through with no question
   or refusal.
5. Optional: choose **✎ Write your own case** and press **Fill from this machine**. It loads what a Claude
   Code agent here sees (CLAUDE.md, git state, tools and permissions) instead of you typing it.

## Reference
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

## Your own case

The first dropdown option, **✎ Write your own case**, replaces the read-only situation with an
editor. **Edit this case** (next to a built-in case) copies that case into the editor: task, the
artifacts read at the start, runtime, plan and session, with the fixtures as `out:` lines.

Two controls at the top of the editor fill it from this machine (read only; the server answers them only for requests addressed to `127.0.0.1` or `localhost`):

* **Fill from this machine** sets the runtime to `developer-sandbox` (Claude Code here) and fills *What the agent could see* with what a Claude Code agent started in this repository loads: `~/.claude/CLAUDE.md`, the project `CLAUDE.md` if any, the memory index, git branch / remotes / recent commits, and a `skillc.env.claude.probe` summary (tools, allow / deny rules, MCP servers, credential names that are set; never their values; no egress check).
* **Import a Claude Code session** lists the prompts of the 8 most recent sessions in `~/.claude/projects/<this repository>/`. Picking one fills the task with that prompt and the session with what the agent did until the next prompt: its visible text as `assistant:` lines (transcripts do not keep the thinking), its tool calls and their results; subagent records are left out. Lines are cut to 1,200 characters and the session to the editor's limits. **No plan** is ticked, since a real session wrote no skillc plan. Code: `local_source.py`.

**Upload a transcript (.jsonl)** does the same as the import for a transcript file you pick (`POST /api/transcript`); the file is parsed in memory and not stored. It is the only one of the three in the hosted app (`deploy/README.md`), where the server is not on your machine.

* **Runtime:** one of `developer-sandbox`, `scout-desktop`, `office-assistant`, `foundry-hosted`,
  `offline-workstation`, with its tools listed under it.
* **Task:** what the user asked the agent.
* **What the agent could see:** each artifact is a line `=== <name> ===` followed by its content.
* **Plan:** the Controlled English plan the skillc run submits first, prefilled with a short valid
  plan for the runtime (the `GOOD` plan of `tests/test_monitor.py`, or the same shape over `read` /
  `write` or `code_interpreter` / `write`). It is checked on the server with `Monitor.check_plan` as
  you type, and the verdict shows inline. Tick **No plan** to run with `require_plan` off.
* **Session:** one step per line; the prefix decides the kind. Blank lines are ignored and a `#`
  line is a comment. **Load example** fills a five-line session: a legitimate test run, then
  reasoning that commits to dropping the production table, then the tool call that does it.

  ```
  assistant: <reasoning text>                      -> thinking (observe_thinking)
  tool: <ToolName> <JSON object>                   -> action   (pre_action), e.g. tool: Bash {"command": "pytest -q"}
  out: <output of the previous tool line>          -> result   (post_action); optional, \n is a newline
  ```

The run is the same as for a built-in case: a fresh temp root,
`Config(runtime=<runtime>, require_plan=<plan given>)` (no case rules, destinations or interaction
settings), the plan submitted, then each step through the monitor with measured latency. The
no-guard console echoes the typed session with the typed `out:` lines, or "(no output given)". There
are no benchmark labels, so the verdict reports **skillc questions raised** and **tool calls
refused** instead of hazard steps caught, and the outcome is "No published incident; user-authored
case." Nothing is executed, sent or deleted; only skillc's decisions are real.

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

* `GET /api/cases`: `groups` (key, label, heldout, dir, ids), `cases` (id, label, title, category,
  kind, agent, task, artifacts, runtime {name, description, tools, lacks}, plan, session (the trace
  in the editor's line format), twin_note, sources), `runtimes` (the five editor runtimes),
  `example_plans` (per runtime) and `example_case`.
* `POST /api/run_custom` with `{"runtime", "task", "artifacts", "plan": <text>|null, "session"}`: the
  same shape as `/api/run`; `verdict.custom` is true and `verdict.skillc` adds `questions` and
  `refused`. Limits: session 20 KB and 60 steps; a tool name is one token; a tool input parses to a
  JSON object. A violation returns 400 with the line number, for example
  `line 2: the tool input is not valid JSON (Expecting ',' delimiter, column 17)`.
* `POST /api/check_plan` with `{"runtime", "plan"}`: `Monitor.check_plan` on a fresh monitor
  (`verdict` ACHIEVABLE or REFUSED, `reason`, `latency_ms`).
* `POST /api/run` with `{"id": "<case id>", "twin": false}`: `logs.no_guard` and `logs.skillc` (lines
  `{k, text, ms}`), `verdict` (labelled steps, false positives, per-run tool calls, wrong actions,
  where skillc stopped, incident outcome), plus the plan result, per-step decisions and `metrics`. An
  id that is not listed returns 400.

The server binds to 127.0.0.1 only.

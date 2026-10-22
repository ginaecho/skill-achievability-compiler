# skillc here

**Shows:** skillc reading this machine by itself (tools, permissions, MCP servers) and deciding what a
skill can do here, next to claude.ai and Claude Code; and, for an uploaded graph, what a workflow can
establish from it and what is missing. **Audience:** first-time viewers. **Time:** 3 minutes.

## Run it

```bash
pip install -e ".[twin]"          # skillc, plus rdflib for the graph tab
python demo/skillc-here/app.py    # opens http://127.0.0.1:8770/
```

Offline: no model call, no network check, nothing is executed. The server binds to 127.0.0.1
and answers only requests addressed to `127.0.0.1` or `localhost`.

## Present it

1. Open the page. Point at the left panel: skillc has already read this machine. Nobody typed a tool list.
2. Click the example **fix-failing-test**. Same skill, three settings: IMPOSSIBLE on claude.ai (no
   Edit, Grep or Read), ACHIEVABLE in Claude Code and here.
3. Click **book-a-table**: the opposite. It needs claude.ai's `ask_user_input_v0`.
4. Click the **edit** tool to switch it off. Only "this machine" flips to IMPOSSIBLE: settings decide.
   **Undo my changes**.
5. Click **post-release-note**: IMPOSSIBLE everywhere, no Slack tool. Type `slack_send_message` in
   *add a tool* and press **Add**: it becomes ACHIEVABLE here, as if a Slack server were connected.
6. Open **2 · A graph**. Press **Use the example building**: what the graph holds and how it connects.
7. Press **Use the example workflow**, then **Check it against the graph**: one set point can be
   verified; the others list exactly which evidence is missing.

## 1 · My environment: what can an agent do here?

On load the page reads this machine as a Claude Code agent started in this repository sees it
(`skillc.env.claude.probe`):

* **Tools**, with their permission status from your settings (allowed, asks first, denied).
* **MCP servers** from the configuration files, and the tools each one lists.
* **Credentials:** which of the usual names are set. Values are never read into the page.

Pick an example skill or paste your own, and press **Check it here**. skillc compiles the text once
(no tool is assumed) and checks it against three settings side by side:

| skill | claude.ai | Claude Code | this machine |
|---|---|---|---|
| `fix-failing-test` | IMPOSSIBLE: missing `edit`, `grep`, `read` | ACHIEVABLE | ACHIEVABLE |
| `book-a-table` | ACHIEVABLE | IMPOSSIBLE: missing `ask_user_input_v0`, `web_search` | IMPOSSIBLE |
| `post-release-note` | IMPOSSIBLE: missing `slack_send_message` | IMPOSSIBLE | IMPOSSIBLE |

**What-if.** Click a tool to switch it off, or add one (for example `slack_send_message`, as if a
Slack server were connected). Only the "this machine" row is re-checked. **Undo my changes**
restores what was read.

`UNKNOWN` means skillc could not read a goal from the text. That happens with a free-form prompt
such as "book me a flight". It never counts as permission. The example skills say what "finished"
means and list their tools and steps, which the deterministic reader needs.

## 2 · A graph: what can it answer?

1. Upload a building graph (Turtle, TriG, N-Triples, N-Quads or RDF/XML), or use the example
   building, and press **What is in it?**. You get its entities by kind, how they connect, nested
   structures and which built-in verifier it can already serve.
2. Paste the workflow as you have it: a brief with "Evidence needed", a bullet list or a table.
3. Press **Check it against the graph**. Each target gets `ACHIEVABLE` (every critical piece of
   evidence is in the graph) or `IMPOSSIBLE` with the evidence that is missing. **How skillc read
   your workflow** shows how each line was mapped, and the full report shows the graph path behind
   each piece of evidence.

This is `skillc twin explore` and `skillc twin check --workflow` (see [`docs/TWIN.md`](../../docs/TWIN.md)).

## What it reads, and what it does not

* Claude Code's built-in tool list comes from skillc's `claude-code` profile. The permission rules
  come from your settings files. A running session's tools are not visible to a separate process.
* A claude.ai connector shows as a server with its tools not listed, so its tools do not count.
  Add a tool by hand to try the what-if.
* Uploaded graphs are written to a temporary directory for parsing and deleted afterwards. JSON-LD
  is refused, because it can fetch remote contexts.

## API

* `GET /api/environment` (`?refresh=1` reads again): `tools`, `mcp`, `credentials`, `grants`,
  `settings` (the grants of each setting).
* `GET /api/samples`: the example skills, graph and workflow.
* `POST /api/check` `{"text", "machine": [tool, ...]?}`: `name`, `needs`, and `rows` with
  `setting`, `verdict`, `reason`, `detail`, `missing`.
* `POST /api/twin/explore` `{"graph", "filename", "tenant"?}`: `text`.
* `POST /api/twin/check` `{"graph", "filename", "workflow", "tenant"?}`: `workflows`, each with
  `title`, `reading`, `results` (`target`, `verdict`, `missing`, `found`) and `report`.

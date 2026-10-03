# Environment topology and reach

`skillc check` asks whether a *skill* is achievable in a declared capability
profile. `skillc reach` asks the question an operator actually has:

> I want this outcome. With **my** account, **my** permissions, the
> **policies** over my subscription, the **services**, **data** and **MCP
> tools** I have, what can I achieve, what blocks the rest, and what would
> unblock it?

It works in three parts:

1. **The environment graph** (`skillc.env/1`). This is a provider-neutral record
   of who you are, which roles you hold and at which scope, the deny rules and
   policies that constrain you, the services, resources and data that exist,
   and the MCP servers and tools connected to your agent. It also records what
   could not be read.
2. **The intent** (`skillc.intent/1`). This is the outcome, written as a list of
   goal conditions plus a target scope and location.
3. **The operation catalogue** (`skillc.ops/1`). This is provider data: for each
   operation, the conditions it requires and adds, the permission it needs and
   where, the resource type it creates, and optionally an MCP route.

## Commands

```console
# First time: a live, read-only probe with your own `az login`, saved as JSON.
# --save-raw also keeps every raw az answer, so the probe can be replayed offline.
$ skillc env probe --azure --mcp-config .mcp.json -o env.json --save-raw az-export/

# After that, work offline from the JSON. You can also probe on another
# machine and bring the file, or replay a raw export:
$ skillc env probe --from-raw az-export/ --mcp-config .mcp.json -o env.json
$ skillc env show env.json --html topology.html

# What can the intent reach here?
$ skillc reach building-topology --env env.json \
      --plan plan.md --html reach.html          # text report on stdout
$ skillc reach my-intent.json --env env.json --json

# The watcher: a sibling process that re-probes on a schedule
$ skillc env watch --azure --mcp-config .mcp.json --intent building-topology \
      --dir .skillc/env --interval 3600
$ skillc env watch ... --once                    # one round, for cron or CI
$ skillc env diff old.json new.json
$ skillc env merge azure.json mcp.json -o env.json
```

`skillc reach` exit codes: `0` every condition is achievable, `1` something is
blocked, `3` everything is achievable but only under assumptions, `2` error.

Outputs:

* **CLI report**: the status of each condition, the plan with the exact
  commands, and each blocker with its reasons and fixes.
* **English plan** (`--plan`): numbered steps, each saying *why* it is allowed
  (which role at which scope grants it), the blockers with their alternatives,
  the assumptions, and the plan as Controlled English.
* **Visual** (`--html`): one self-contained page showing the intent graph
  (conditions and operations coloured achievable, assumed or blocked) and the
  environment topology (principal → roles → scopes → resources and services;
  policies; MCP servers → tools). It supports light and dark themes and
  phone-width screens.

Runnable examples: `examples/environment/` (a Contributor and an Owner over the
same simulated subscription).

## The Claude runtime: what can a SKILL.md or agent.md achieve here?

The same question applies to an agent's own runtime. For Claude, the
environment is the session itself: its tools, its permission rules, the hosts
its network policy lets it reach, the programs and Python modules installed,
which credential variables are set (names only, never values), which paths it
can write, and which MCP connectors are connected or still waiting for sign-in.

```console
# What does this skill need from its runtime? (each need cites its line)
$ skillc intent path/to/SKILL.md

# Probe exactly those needs here, read-only, and decide what is achievable
$ skillc reach path/to/SKILL.md --claude [--save-env env.json] [--plan plan.md]

# A cloud session's connectors and tools are not in a config file; name them
$ skillc reach agent.md --claude --tools-file tools.json --connectors-file connectors.json

# Or probe once and reuse the snapshot
$ skillc env probe --claude --needs-from SKILL.md -o env.json
$ skillc reach SKILL.md --env env.json
```

**Reading the document** (`env/nl.py`) is deterministic. It reads what the
document *does*:

* shell blocks: the programs it runs, the packages it installs (pip, npm, apt),
  and the hosts it fetches from;
* Python blocks: the imports outside the standard library;
* inline commands, and packages listed on a line about pip;
* credential variables; the tool-policy library's accounts, platforms and MCP
  servers; and `allowed-tools` / `tools` from the frontmatter.

Credentials that are alternatives of one account (an LLM key, a GitHub token)
are folded into that account. A need found only in an optional passage
("optionally", "alternatively", a troubleshooting section) is reported under
`optional` and does not decide the verdict. A document with no runtime needs
is a pure *deliverable*: it is achievable by the agent alone.

**Installing.** A missing program, module or package is reachable when an
installer can provide it here (`data/env/claude_routes.json`). The installer's
own needs (the program, and egress to its registry) are checked like any other
need, so a plan that says `pip install x` is only offered when pypi.org
answers.

**Facts.**

* Egress is one HTTPS request per host. An answer from the host, even 404, is
  "reachable". A 403/407 from the egress proxy is a refusal.
* A tool with no allow or deny rule is an assumption ("the user approves when
  asked"), never a refusal.
* A credential that is set is assumed valid for the task.
* A connector waiting for sign-in is not usable.

The evaluation on 100 real documents is in `benchmark/claude_env/REPORT.md`.

## What is decided, and how

**Permissions** follow role-based access control as Azure RBAC defines it:

* a role assigned at a scope applies there and to every scope below it, never
  beside it;
* actions are wildcard patterns (case-insensitive) minus `notActions`;
* data-plane operations are checked against `dataActions` only. This is why
  Owner and Contributor, whose `actions` are `*`, still cannot write Azure
  Digital Twins models;
* a matching deny assignment overrides any allow;
* an assignment that carries an ABAC condition is not taken as a definite grant.

Role definitions are read live. Offline, the built-ins come from
`data/env/azure_builtin_roles.json`, which was extracted from
`MicrosoftDocs/azure-docs` `built-in-roles/*.md`.

**Policies.** Only definitions whose semantics are known exactly are
interpreted: the built-ins *Allowed locations* (`e56962a6-…`), *Allowed
resource types* (`a08ec900-…`) and *Not allowed resource types*
(`6c112d4e-…`), including their `effect` parameter (default `Deny`),
`enforcementMode` and `notScopes`. Any other policy with a deny effect is kept
as *uninterpreted*.

**Reach.** Operations only add conditions, so the conditions reachable together
are exactly the reachable closure intersected with the goal. This makes "the
largest achievable part of the goal" exact rather than a heuristic. The trusted
checker then verifies both sides:

* the plan is checked as a pack and must come back ACHIEVABLE with a witness;
* every blocked condition carries the checker's protocol-independent
  `GOAL_UNSAT` certificate over the operations the environment allows.

## What is assumed, never refuted

Anything that could not be read appears under `unknown` in the environment and
under *assumptions* in the report: role assignments, deny assignments, policies,
service registrations, or the tools of an MCP server that was not started. An
uninterpreted deny policy, a conditioned role assignment, and an MCP route also
count as assumptions. None of these can make a condition *blocked*; they make it
*achievable under assumptions* (exit code 3).

So a "blocked" verdict is sound **relative to the snapshot**: it rests only on
facts that were observed at `captured_at`. Re-probe, or run the watcher, to keep
it current.

## Safety of the probe

* Azure: only `… show`, `… list` and `az rest --method get` ever run. Anything
  else is refused before execution.
* MCP: configuration files are read, and environment variable **values are
  never stored** (only their names). Listing a server's tools means starting
  it, which runs a program from your configuration, so it happens only with
  `--list-tools`, and only for stdio servers.

## Formats

### `skillc.env/1`

```json
{"schema": "skillc.env/1", "captured_at": "2026-10-03T12:00:00Z",
 "sources": [{"adapter": "azure", "mode": "live", "detail": "subscription …"}],
 "nodes": [{"id": "/subscriptions/…/resourcegroups/rg-building", "kind": "scope",
            "name": "rg-building", "attrs": {"level": "resource_group"}}],
 "edges": [{"src": "principal/…", "dst": "role/b24988ac-…", "kind": "assigned",
            "attrs": {"scope": "/subscriptions/…/resourceGroups/rg-building"}}],
 "unknown": [{"what": "mcp_tools:azure", "why": "tools not listed"}]}
```

Node kinds: `principal`, `scope`, `role`, `deny`, `policy`, `service`,
`resource`, `data`, `mcp_server`, `tool`. Edge kinds: `contains`, `assigned`,
`denied`, `applies`, `stores`, `exposes`. See `src/skillc/env/model.py`. A
hand-written or exported file is validated on load.

### `skillc.intent/1`

```json
{"schema": "skillc.intent/1", "name": "building-topology", "catalog": "azure",
 "target": {"scope": "/subscriptions/{subscription}/resourceGroups/rg-building",
            "location": "westeurope"},
 "params": {"name": "bldg-twins"},
 "data": [{"id": "building_plans", "store": "/subscriptions/{subscription}/…/storageAccounts/bldgplans",
           "path": "floorplans"}],
 "goal": ["dt_instance", "building_data", "dt_models", "topology_twins",
          "topology_relationships", "topology_queryable"]}
```

`{subscription}` is filled from the environment. The built-in example is
`src/skillc/data/env/intents/building-topology.json`.

### `skillc.ops/1`

Each operation has `id`, `title`, `requires`, `adds`, `permission {action, at,
data}` (where `at` is `target`, `subscription` or `data:<id>`), `creates {type}`
(checked against policy), `exists` (the condition already holds if the target
scope or a resource of this type exists), `how` (the command, with `{rg}`,
`{location}`, `{name}`, `{data:<id>}` filled in), and optionally
`mcp {tools: [regex], replaces: [condition]}`. `capabilities` are conditions
that hold when the principal already has a set of data actions at a scope.

The Azure catalogue (`data/env/ops_azure.json`) covers resource groups,
provider registration, Azure Digital Twins (instance, data-plane access,
models, twins, relationships, queries), blob data and IoT Hub. Its action
names come from `MicrosoftDocs/azure-docs` `permissions/internet-of-things.md`
and related pages, which are cited in the file. Add operations, or a whole new
provider, as data.

## Limits

* The probe covers one subscription per run. Merge several with `env merge`.
* Policy initiatives (policy sets) and custom policy rules are not
  interpreted; they appear as uninterpreted deny assumptions.
* Deny assignments that target *groups* are not resolved against your group
  membership; they make deny checks an assumption.
* HTTP/SSE MCP servers are recorded but their tools are not listed.
* The catalogue states what an operation *needs*, not everything that can go
  wrong at run time (quotas, name collisions, regional SKU availability). Those
  are outside the snapshot.

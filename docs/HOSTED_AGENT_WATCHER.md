# The hosted-agent watcher: self-probe at start, re-probe on a timer, gate on the merge

**Status:** WP6 of `docs/HOSTED_AGENT_IMPLEMENTATION_PLAN.md`, branch `gc/hosted_agent`.
Code: `src/skillc/env/selfprobe.py` (the data-plane probe, `merge_hosted`,
`hosted_probe_factory`), `src/skillc/env/watch.py` (unchanged: `watch_once`
takes any probe callable), `src/skillc/telemetry.py` (spans and events).

A hosted agent's capability context has two halves (`docs/HOSTED_AGENT.md`, D1):

| half | what it knows | who reads it | where |
|---|---|---|---|
| **control plane** | identity, RBAC, toolbox tool types, connections, egress mode, sandbox size, policies | `skillc env from-azd azure.yaml` (declared) and `skillc env probe --foundry` (observed from the platform) | the developer's machine or a scheduled job |
| **data plane** | programs on `PATH`, importable modules, writable `$HOME` and `/files`, egress that really answers, the toolbox's `tools/list` as the agent identity sees it | `skillc env probe --self` | **inside the sandbox** |

Only the sandbox can observe the data plane, and only the platform can grant
the control plane. The watcher keeps both halves fresh and the gate judges the
merge. Nothing here calls a model, and nothing contacts a host, program or
module the caller did not name.

## 1. The self-probe at container start

One line in `main.py` (or the image's entrypoint), before the host server
starts. It writes the data-plane snapshot to the session's persistent `$HOME`:

```python
subprocess.run([sys.executable, "-m", "skillc.cli", "env", "probe", "--self",
                "--needs-from", "skills", "-o",
                os.path.join(os.environ.get("HOME", "."), ".skillc", "env", "latest.json")],
               check=False, timeout=60)
```

or, as the shell line the deploy pipeline's smoke test uses:

```sh
python -m skillc.cli env probe --self --needs-from skills -o $HOME/.skillc/env/latest.json
```

`--needs-from skills` reads every `*.md` in the `skills/` directory (the
`azure.ai.skill` instruction files) through the natural-language front-end and
probes exactly the hosts, programs and modules those skills name. Add:

| option | effect |
|---|---|
| `--host H` / `--program P` / `--module M` / `--path DIR` (repeatable) | more things to look at |
| `--inside-network` | hosts that resolve to private addresses may be contacted. Off by default (the same refusal as the Claude probe); turn it on in a network-isolated project, because private endpoints are the purpose there |
| `--toolbox-url "$TOOLBOX_ENDPOINT"` | list the toolbox's tools over HTTP MCP with the agent identity's token (`https://ai.azure.com/.default` via `DefaultAzureCredential`). The token is used once and never written. Until `env.mcp.list_http_tools` lands (WP5) the toolbox is recorded as unknown `mcp_tools:toolbox/<name>` with the reason "HTTP MCP listing unavailable", never as empty |

What the snapshot holds, all nodes marked `observed: true`:

```
principal  principal/agent/<name>   identity_mode agent; the AGENT_/FOUNDRY_ variable names
service    sandbox                  cpu_count, memory_gib, free_disk_gib (unknown when unreadable)
service    platform/<os>            linux | windows | macos | mobile_device | gpu
scope      path:<dir>               $HOME, /files, named paths: exists, writable
service    program/<p>  pymodule/<m>  egress/<host>  credential/<NAME>  app_insights
mcp_server toolbox/<name>           + tool toolbox/<name>/<tool> when listed
```

Secret values never enter the snapshot: a credential is "variable `NAME` is
set", and every variable whose name ends in `_KEY`, `_SECRET`, `_TOKEN` or
`CONNECTION_STRING` is recorded by name only. `python -m skillc.cli env show
$HOME/.skillc/env/latest.json` prints it; `skillc env diff` compares two.

The probe costs one `HEAD` request per named host and no model call, so it
fits the 0.5 vCPU / 1 GiB tier. The result is per session (the sandbox is),
which is why it runs at start and not once per deploy.

## 2. `env watch --once` on a timer: an Azure Container Apps Job

`skillc env watch` loops a probe, stores timestamped snapshots and
`latest.json`, diffs, re-runs the watched intents and reports the conditions
whose status changed. `--once` does one round and exits, which is what a
scheduled job wants. Two flavours:

* **control plane from outside**: `env watch --once --foundry --project URL
  --agent NAME` (WP5). Runs anywhere with a managed identity that can read the
  project; this is the job below.
* **data plane from inside**: `env watch --once --self ...` with
  `hosted_probe_factory(args)` as the probe. Runs inside the agent's own image,
  for example as the same Container Apps Job built from the agent image, or
  from an Invocations route. The snapshot directory is `$HOME/.skillc/env`.

The job needs an image with skillc, a managed identity, and **Reader** on the
Foundry project (the control-plane probe is read-only; `Reader` on the project
resource is enough to list the agent, its versions, toolboxes and connections,
and the identity's own role assignments). Placeholders in angle brackets:

```sh
# 0. Names
RG=<resource-group>; LOC=<location>; ENVNAME=<aca-environment>
ACR=<registry-name>; IMAGE=$ACR.azurecr.io/skillc-watch:<tag>
PROJECT="https://<account>.services.ai.azure.com/api/projects/<project>"
PROJECT_ID=$(az cognitiveservices account show -n <account> -g $RG --query id -o tsv)/projects/<project>

# 1. An image with skillc (plain python, or the agent image itself for --self)
cat > Dockerfile.watch <<'EOF'
FROM python:3.12-slim
RUN pip install --no-cache-dir "skillc[foundry]"
WORKDIR /watch
COPY skills/ /watch/skills/
ENTRYPOINT ["python", "-m", "skillc.cli", "env", "watch"]
EOF
az acr build -r $ACR -t $IMAGE -f Dockerfile.watch .

# 2. A user-assigned identity with Reader on the project
az identity create -g $RG -n skillc-watch
MI_ID=$(az identity show -g $RG -n skillc-watch --query id -o tsv)
MI_PRINCIPAL=$(az identity show -g $RG -n skillc-watch --query principalId -o tsv)
MI_CLIENT=$(az identity show -g $RG -n skillc-watch --query clientId -o tsv)
az role assignment create --assignee-object-id $MI_PRINCIPAL --assignee-principal-type ServicePrincipal \
   --role Reader --scope "$PROJECT_ID"
# the image is pulled with the same identity
az role assignment create --assignee-object-id $MI_PRINCIPAL --assignee-principal-type ServicePrincipal \
   --role AcrPull --scope $(az acr show -n $ACR --query id -o tsv)

# 3. The job: every hour, one round, snapshots on a mounted share
az containerapp env create -g $RG -n $ENVNAME -l $LOC          # once per environment
az containerapp job create -g $RG -n skillc-watch --environment $ENVNAME \
   --trigger-type Schedule --cron-expression "0 * * * *" \
   --replica-timeout 600 --replica-retry-limit 1 --parallelism 1 --replica-completion-count 1 \
   --image $IMAGE --registry-server $ACR.azurecr.io --registry-identity $MI_ID \
   --mi-user-assigned $MI_ID --cpu 0.5 --memory 1.0Gi \
   --env-vars AZURE_CLIENT_ID=$MI_CLIENT FOUNDRY_PROJECT_ENDPOINT=$PROJECT \
   --args "--once" "--dir" "/watch/env" "--foundry" "--project" "$PROJECT" \
          "--agent" "<agent-name>" "--intent" "/watch/skills/<skill>.md"

# 4. Run one round now, and read the report
az containerapp job start -g $RG -n skillc-watch
az containerapp job execution list -g $RG -n skillc-watch -o table
az containerapp logs show -g $RG -n skillc-watch --type console --tail 200
```

`--dir /watch/env` is ephemeral unless mounted: add an Azure Files volume
(`az containerapp env storage set` plus a `volumeMounts` entry in the job's
YAML) so `latest.json` survives between executions and the diff has
something to diff against. Without the mount every round reports
`"environment_changes": null`, which is still a valid fresh snapshot.

For the in-sandbox flavour replace the image by the agent's own image, the
entrypoint by `python -m skillc.cli env watch`, and the args by
`--once --self --dir $HOME/.skillc/env --needs-from /app/skills
--toolbox-url "$TOOLBOX_ENDPOINT" [--inside-network]`. The job's identity
then stands in for the agent identity, so what it sees of the toolbox is what
*that* identity may use; the authoritative autonomous-run view comes from the
start-of-session probe in section 1.

Each round's report is JSON on stdout, one object per round:

```json
{"snapshot": "/watch/env/env-20261008T120000Z.json",
 "environment_changes": {"added": [], "removed": ["service egress/pypi.org"], "changed": []},
 "status_changes": {"Fetcher": {"fetch_dataset": {"was": "achievable", "now": "blocked"}}}}
```

Wrap the round in `skillc.telemetry.span("skillc.watch", agent=...)` and the
status changes in `telemetry.event("skillc.verdict", ...)` to land them in
the Application Insights resource the platform injects; without
`opentelemetry` installed both are no-ops.

## 3. From two halves to one `skillc gate --env`

`merge_hosted(control, data)` joins the halves; `skillc env merge` is the
plain union for same-plane snapshots and stays as it is.

| node | who wins when both carry `available` | why |
|---|---|---|
| `program/*`, `pymodule/*`, `egress/*`, `path:*`, `sandbox`, `platform/*` | **data plane** | only the sandbox can observe them |
| `tool` under `toolbox/<name>` with `observed: true` | **data plane** | `tools/list` as the agent identity is the authoritative list |
| `role`, `deny`, `policy`, `principal` attributes, `connection/*` | **control plane** | only the platform grants them; the sandbox cannot see RBAC |
| everything else | data plane on top of control plane | an observation beats a declaration; attributes only one half has are kept |

A disagreement is never silent: it is kept in `unknown` as
`{"what": "conflict:<id>", "why": "declared X, observed Y; observed used"}`
(or `declared used`), so `skillc env show` and the gate report can list it. A
control-plane unknown that the data plane answered is dropped: the azd
adapter's `egress` ("measure from inside the sandbox") goes once the
self-probe measured hosts, `mcp_tools:toolbox/<name>` goes once the tools
were listed. Everything else stays unknown, so a refutation never rests on
something that was not observed.

The gate takes the merged document as its observed probe:

```sh
# control plane: the declaration, or the live probe when you are signed in
skillc env from-azd azure.yaml -o .skillc/env/declared.json
skillc env probe --foundry --project "$PROJECT" --agent <agent> -o .skillc/env/control.json

# data plane: copy latest.json out of the session ($HOME is readable through
# the files API, or have the agent return it from an Invocations route)
cp <downloaded>/latest.json .skillc/env/self.json

# merge and gate
python - <<'EOF'
from skillc.env.model import Environment
from skillc.env.selfprobe import merge_hosted
merge_hosted(Environment.load(".skillc/env/control.json"),
             Environment.load(".skillc/env/self.json")).save(".skillc/env/merged.json")
EOF
skillc gate . --env .skillc/env/merged.json
```

`skillc gate` reads `azure.yaml` itself and merges `--env` over the
declaration with observed facts winning (`src/skillc/gate.py`), so passing the
merged document gives it both halves at once: an intent that needs
`azure_ai_search` is achievable only if the toolbox was observed to expose it,
`pandas` only if the sandbox could import it, and a host only if the sandbox
reached it. Anything the merge left unknown is reported as an assumption
("achievable if ..."), and a conflict appears in the report next to the fact
that was used.

## 4. What stays assumed

* **OBO permissions**: the self-probe runs as the agent identity. When the
  agent acts on behalf of a user, that user's toolbox view and RBAC are
  unknown; the report says so.
* **Egress measured once per session**: a VNet rule changed mid-session is
  caught by the monitor's post-action observations, not by the snapshot.
* **Memory on platforms without `/proc/meminfo` or `os.sysconf`** (Windows
  local runs): `sandbox:memory_gib` is unknown, never guessed.
* **The toolbox before WP5**: unknown, with the reason recorded, until
  `env.mcp.list_http_tools` exists.

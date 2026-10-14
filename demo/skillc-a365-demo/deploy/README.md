# Hosted demo (Azure Container Apps)

https://skillc-a365-demo.lemonbay-f30b1bef.swedencentral.azurecontainerapps.io/
(public, no sign-in)

| Resource | Name |
|---|---|
| Resource group | `rg-skillc-demo` (swedencentral), subscription `MCAPS-Hybrid-REQ-97553-2024-tzuchunchen` |
| Container registry | `acrskillcdemo` (Basic, admin user off; the app pulls with its system identity) |
| Container Apps environment | `cae-skillc-demo` |
| Container app | `skillc-a365-demo`: 0.5 CPU, 1 GiB, 0 to 1 replica (scales to zero when idle) |
| Entra app | `skillc-a365-demo`, app id `7556ea51-0424-415b-8c53-df1ab2b5238e`; unused since sign-in was turned off |

The image runs `app.py` with `SKILLC_DEMO_HOSTED=1`: it binds `0.0.0.0:$PORT` (8000), turns off
`/api/local/*` (the server is not on the viewer's machine). The editor shows **Fill from my .claude
folder** instead: the browser reads the folder the viewer picks (CLAUDE.md, settings, project memory)
to fill *What the agent could see*, and lists the projects and sessions in it; only a session the
viewer picks is sent, parsed in memory and not stored. **Upload a transcript (.jsonl)** does the same
for a single file. One replica and a
lock in the server keep z3 single-threaded.

## Redeploy after a change

```bash
python demo/skillc-a365-demo/deploy/build_context.py <new-empty-dir>
az acr build -r acrskillcdemo -t skillc-a365-demo:<tag> <new-empty-dir>
az containerapp update -g rg-skillc-demo -n skillc-a365-demo \
  --image acrskillcdemo.azurecr.io/skillc-a365-demo:<tag>
```

`build_context.py` stages only what the app reads: `src/skillc`, `scripts/run_interaction_cases.py`,
the demo files, and from `benchmark/` only the case files that have a context in `cases/` (about
1.4 MB). No other benchmark data, runs or docs go into the image.

## Sign-in

Sign-in is off (`az containerapp auth update --enabled false`). To turn Entra sign-in back on:
`az containerapp auth update -g rg-skillc-demo -n skillc-a365-demo --enabled true`, then renew the
client secret (the tenant caps it at 30 days) with `az ad app credential reset` and
`az containerapp auth microsoft update --client-secret`.

## Remove everything

```bash
az group delete -n rg-skillc-demo
az ad app delete --id 7556ea51-0424-415b-8c53-df1ab2b5238e
```

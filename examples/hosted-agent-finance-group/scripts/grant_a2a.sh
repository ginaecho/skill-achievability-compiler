#!/usr/bin/env sh
# Grant every caller agent's instance identity the Foundry Agent Consumer role on the
# project, so that its A2A calls to the callee agents are authorized. Run AFTER `azd deploy`
# (the instance identities exist only once the agents do). Idempotent: an existing
# assignment is skipped.
#
#   sh scripts/grant_a2a.sh            # all six callers (every role has an outgoing edge)
#   CALLERS="finance-fetcher" sh scripts/grant_a2a.sh
#
# Role: Foundry Agent Consumer, eed3b665-ab3a-47b6-8f48-c9382fb1dad6 (docs/HOSTED_AGENT.md 2c).
# Scope: the PROJECT (AZURE_AI_PROJECT_ID), which covers every callee at once. The tighter
# alternative is one assignment per edge on the callee agent's own resource id
# (`<project id>/agents/<callee>`; verify against az that hosted agents are ARM-addressable
# at that path), which makes the ten edges, and nothing else, authorized; the project scope
# also lets any caller reach any agent of the project, including edges the protocol does not
# have. skillc's gate reports both as assumptions until `skillc env probe --foundry` reads
# the assignments back.
#
# verify against azd: the environment key `AGENT_<SERVICE>_INSTANCE_IDENTITY_PRINCIPAL_ID`
# (SERVICE upper-cased, `-` -> `_`). When it is absent the script falls back to parsing
# "Instance Identity Principal ID" from `azd ai agent show <service>`.
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
ROLE_ID="eed3b665-ab3a-47b6-8f48-c9382fb1dad6"
CALLERS="${CALLERS:-finance-fetcher finance-expense-analyst finance-revenue-analyst finance-tax-specialist finance-tax-verifier finance-writer}"
# Git Bash on Windows rewrites a leading "/" in arguments to a Windows path.
export MSYS_NO_PATHCONV=1

cd "$HERE" || exit 1
VALUES="$(azd env get-values)" || { echo "azd env get-values failed" >&2; exit 1; }

value() {   # value <KEY>   -> the azd environment value, unquoted
  printf '%s\n' "$VALUES" | sed -n "s/^$1=\"\{0,1\}\([^\"]*\)\"\{0,1\}\$/\1/p" | head -n 1
}

SCOPE="$(value AZURE_AI_PROJECT_ID)"
if [ -z "$SCOPE" ]; then
  echo "AZURE_AI_PROJECT_ID is not set: azd env set AZURE_AI_PROJECT_ID /subscriptions/.../projects/<project>" >&2
  exit 1
fi

rc=0
for svc in $CALLERS; do
  key="AGENT_$(printf '%s' "$svc" | tr 'a-z-' 'A-Z_')_INSTANCE_IDENTITY_PRINCIPAL_ID"
  pid="$(value "$key")"
  if [ -z "$pid" ]; then
    # verify against azd: the label printed by `azd ai agent show`.
    pid="$(azd ai agent show "$svc" 2>/dev/null | sed -n 's/.*Instance Identity Principal ID[^0-9a-fA-F]*\([0-9a-fA-F-]\{36\}\).*/\1/p' | head -n 1)"
  fi
  if [ -z "$pid" ]; then
    echo "skip $svc: no instance identity principal id ($key not in azd env, azd ai agent show gave none)" >&2
    rc=1
    continue
  fi
  existing="$(az role assignment list --assignee "$pid" --role "$ROLE_ID" --scope "$SCOPE" --query '[0].id' -o tsv 2>/dev/null)"
  if [ -n "$existing" ]; then
    echo "ok   $svc ($pid): Foundry Agent Consumer already assigned on the project"
    continue
  fi
  if az role assignment create --assignee-object-id "$pid" --assignee-principal-type ServicePrincipal \
       --role "$ROLE_ID" --scope "$SCOPE" -o none; then
    echo "done $svc ($pid): Foundry Agent Consumer assigned on the project"
  else
    echo "FAIL $svc ($pid): az role assignment create failed" >&2
    rc=1
  fi
done
exit $rc

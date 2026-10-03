"""Simulated `az` exports for the environment tests (replayed, never live)."""
from __future__ import annotations

import json
from pathlib import Path

from skillc.env.azure import ARM, POLICY_API, ROLE_API, raw_key

SUB_ID = "11111111-1111-1111-1111-111111111111"
SUB = f"/subscriptions/{SUB_ID}"
RG = f"{SUB}/resourceGroups/rg-building"
RG_DATA = f"{SUB}/resourceGroups/rg-data"
STORE = f"{RG_DATA}/providers/Microsoft.Storage/storageAccounts/bldgplans"
OID = "aaaaaaaa-0000-0000-0000-000000000001"
ROLE = {"owner": "8e3af657-a8ff-443c-a75c-2fe8c4bcb635",
        "contributor": "b24988ac-6180-42a0-ab88-20f7382dd24c",
        "blob_reader": "2a2b9908-6ea1-4ae2-8e65-a410df84e7d1",
        "dt_owner": "bcd981a7-7f74-457b-83e1-cceb9e632ffe"}
ALLOWED_LOCATIONS = "/providers/Microsoft.Authorization/policyDefinitions/e56962a6-4747-49cd-b67b-bf8b01975c4c"


def role_def_id(guid: str) -> str:
    return f"{SUB}/providers/Microsoft.Authorization/roleDefinitions/{guid}"


def assignment(role: str, scope: str) -> dict:
    return {"roleDefinitionId": role_def_id(ROLE[role]), "scope": scope, "principalId": OID}


def write_export(root: Path, assignments: list[dict], *, registered=("Microsoft.DigitalTwins",
                 "Microsoft.Storage"), allowed_locations=("westeurope", "northeurope"),
                 deny: list[dict] | None = None, fail: tuple[str, ...] = (),
                 role_defs: dict[str, dict] | None = None) -> Path:
    """Write the answers the probe asks for; commands named in `fail` are left
    out (the probe then records them as unknown)."""
    root.mkdir(parents=True, exist_ok=True)
    answers = {
        ("account", "show"): {"id": SUB_ID, "name": "Contoso Buildings", "tenantId": "t-1",
                              "user": {"name": "alice@contoso.com", "type": "user"}},
        ("ad", "signed-in-user", "show"): {"id": OID},
        ("group", "list"): [{"id": RG, "name": "rg-building", "location": "westeurope"},
                            {"id": RG_DATA, "name": "rg-data", "location": "westeurope"}],
        ("resource", "list"): [{"id": STORE, "name": "bldgplans", "location": "westeurope",
                                "type": "Microsoft.Storage/storageAccounts"}],
        ("provider", "list", "--query",
         "[].{namespace:namespace, registrationState:registrationState}"):
            [{"namespace": ns, "registrationState": "Registered" if ns in registered
              else "NotRegistered"}
             for ns in ("Microsoft.DigitalTwins", "Microsoft.Devices", "Microsoft.Storage")],
        ("role", "assignment", "list", "--all", "--include-inherited", "--include-groups",
         "--fill-principal-name", "false", "--fill-role-definition-name", "false",
         "--assignee-object-id", OID): assignments,
        ("rest", "--method", "get", "--url",
         f"{ARM}{SUB}/providers/Microsoft.Authorization/denyAssignments?api-version={ROLE_API}"):
            {"value": deny or []},
        ("rest", "--method", "get", "--url",
         f"{ARM}{SUB}/providers/Microsoft.Authorization/policyAssignments?api-version={POLICY_API}"):
            {"value": [{"id": f"{SUB}/providers/Microsoft.Authorization/policyAssignments/loc",
                        "name": "loc",
                        "properties": {"displayName": "Allowed locations",
                                       "policyDefinitionId": ALLOWED_LOCATIONS, "scope": SUB,
                                       "parameters": {"listOfAllowedLocations":
                                                      {"value": list(allowed_locations)}}}}]
             if allowed_locations else []},
    }
    for name, d in (role_defs or {}).items():
        answers[("rest", "--method", "get", "--url",
                 f"{ARM}{role_def_id(ROLE[name])}?api-version={ROLE_API}")] = {"properties": d}
    for args, output in answers.items():
        if args[0] in fail or " ".join(args[:2]) in fail:
            continue
        (root / raw_key(list(args))).write_text(
            json.dumps({"command": ["az", *args], "output": output}), encoding="utf-8")
    return root

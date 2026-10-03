# Plan: building-topology

Model a building's topology (building, floors, rooms) as a queryable Azure Digital Twins graph, built from floor plans in blob storage.

Target: resource group rg-building, location westeurope. Environment snapshot: 2026-10-03T12:00:00Z.

## What you can do now

1. **Create the Azure Digital Twins instance.** Allowed because role 'Contributor' at resource group rg-building grants Microsoft.DigitalTwins/digitalTwinsInstances/write; no deny policy over the scope blocks it; resource group rg-building exists; service Microsoft.DigitalTwins is registered.
   `az dt create --dt-name bldg-twins --resource-group rg-building --location westeurope`
2. **Read the floor plans and space lists.** Allowed because it needs no permission beyond its prerequisites; role 'Storage Blob Data Reader' at storageAccounts bldgplans (in resource group rg-data) grants Microsoft.Storage/storageAccounts/blobServices/containers/blobs/read.
   `az storage blob download-batch --auth-mode login --account-name bldgplans --source floorplans --destination ./building`

After these steps these conditions hold: dt_instance, building_data.

## What cannot be done here yet

- **dt_data_writer** can be reached in any of 2 ways, none open yet:
  1. hold the permission to write models, twins and relationships and query the Azure Digital Twins graph: no role assigned to the principal grants the data actions Microsoft.DigitalTwins/models/write, Microsoft.DigitalTwins/digitaltwins/write, Microsoft.DigitalTwins/digitaltwins/relationships/write, Microsoft.DigitalTwins/query/action at resource group rg-building. To unblock: ask for one of 'Azure Digital Twins Data Owner' at resource group rg-building.
  2. Assign yourself the Azure Digital Twins Data Owner role on the instance: no role assigned to the principal grants the action Microsoft.Authorization/roleAssignments/write at resource group rg-building. To unblock: ask for one of 'User Access Administrator', 'Role Based Access Control Administrator', 'Owner' at resource group rg-building.
- **dt_models** (Upload the DTDL models (Building, Floor, Room, Sensor)): needs dt_data_writer first. To unblock: unblock dt_data_writer.
- **topology_twins** (Create one twin per building, floor and room): needs dt_models first. To unblock: unblock dt_models.
- **topology_relationships** (Connect the twins (building contains floors, floor contains rooms)): needs topology_twins first. To unblock: unblock topology_twins.
- **topology_queryable** (Query the building graph): needs topology_relationships first. To unblock: unblock topology_relationships.

## The plan as Controlled English

```ce
Skill `building-topology`.
Roles: `you`.
Tool `create_dt_instance` (owner `you`): requires `rg_exists` and `service:Microsoft.DigitalTwins`; adds `dt_instance`.
Tool `read_building_data` (owner `you`): requires `building_data_access`; adds `building_data`.
Tool `upload_models` (owner `you`): requires `dt_instance` and `dt_data_writer`; adds `dt_models`.
Tool `create_twins` (owner `you`): requires `dt_models` and `building_data`; adds `topology_twins`.
Tool `create_relationships` (owner `you`): requires `topology_twins`; adds `topology_relationships`.
Tool `query_topology` (owner `you`): requires `topology_relationships`; adds `topology_queryable`.
Tool `create_iot_hub` (owner `you`): requires `rg_exists` and `service:Microsoft.Devices`; adds `iot_hub`.
Initially true: `building_data_access`, `rg_exists`, `service:Microsoft.DigitalTwins`.
Goal: `dt_instance` and `building_data`.
Protocol:
  - `you` uses `create_dt_instance`.
  - `you` uses `read_building_data`.
```

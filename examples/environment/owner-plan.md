# Plan: building-topology

Model a building's topology (building, floors, rooms) as a queryable Azure Digital Twins graph, built from floor plans in blob storage.

Target: resource group rg-building, location westeurope. Environment snapshot: 2026-10-03T12:00:00Z.

## What you can do now

1. **Create the Azure Digital Twins instance.** Allowed because role 'Owner' at subscription 11111111-1111-1111-1111-111111111111 grants Microsoft.DigitalTwins/digitalTwinsInstances/write; no deny policy over the scope blocks it; resource group rg-building exists; service Microsoft.DigitalTwins is registered.
   `az dt create --dt-name bldg-twins --resource-group rg-building --location westeurope`
2. **Assign yourself the Azure Digital Twins Data Owner role on the instance.** Allowed because role 'Owner' at subscription 11111111-1111-1111-1111-111111111111 grants Microsoft.Authorization/roleAssignments/write.
   `az dt role-assignment create --dt-name bldg-twins --assignee <your sign-in name> --role "Azure Digital Twins Data Owner"`
3. **Read the floor plans and space lists.** Allowed because it needs no permission beyond its prerequisites; role 'Storage Blob Data Reader' at storageAccounts bldgplans (in resource group rg-data) grants Microsoft.Storage/storageAccounts/blobServices/containers/blobs/read.
   `az storage blob download-batch --auth-mode login --account-name bldgplans --source floorplans --destination ./building`
4. **Upload the DTDL models (Building, Floor, Room, Sensor).** Allowed because it needs no permission beyond its prerequisites.
   `az dt model create --dt-name bldg-twins --from-directory ./models`
5. **Create one twin per building, floor and room.** Allowed because it needs no permission beyond its prerequisites.
   `az dt twin create --dt-name bldg-twins --dtmi <model> --twin-id <id>   (one per space)`
6. **Connect the twins (building contains floors, floor contains rooms).** Allowed because it needs no permission beyond its prerequisites.
   `az dt twin relationship create --dt-name bldg-twins --twin-id <parent> --target <child> --relationship contains --relationship-id <id>`
7. **Query the building graph.** Allowed because it needs no permission beyond its prerequisites.
   `az dt twin query --dt-name bldg-twins --query-command "SELECT * FROM digitaltwins"`

After these steps these conditions hold: dt_instance, building_data, dt_models, topology_twins, topology_relationships, topology_queryable.

## The plan as Controlled English

```ce
Skill `building-topology`.
Roles: `you`.
Tool `create_resource_group` (owner `you`): adds `rg_exists`.
Tool `register_digital_twins` (owner `you`): adds `service:Microsoft.DigitalTwins`.
Tool `register_devices` (owner `you`): adds `service:Microsoft.Devices`.
Tool `create_dt_instance` (owner `you`): requires `rg_exists` and `service:Microsoft.DigitalTwins`; adds `dt_instance`.
Tool `grant_dt_data_owner` (owner `you`): requires `dt_instance`; adds `dt_data_writer`.
Tool `grant_blob_data_reader` (owner `you`): adds `building_data_access`.
Tool `read_building_data` (owner `you`): requires `building_data_access`; adds `building_data`.
Tool `upload_models` (owner `you`): requires `dt_instance` and `dt_data_writer`; adds `dt_models`.
Tool `create_twins` (owner `you`): requires `dt_models` and `building_data`; adds `topology_twins`.
Tool `create_relationships` (owner `you`): requires `topology_twins`; adds `topology_relationships`.
Tool `query_topology` (owner `you`): requires `topology_relationships`; adds `topology_queryable`.
Tool `create_iot_hub` (owner `you`): requires `rg_exists` and `service:Microsoft.Devices`; adds `iot_hub`.
Initially true: `building_data_access`, `rg_exists`, `service:Microsoft.DigitalTwins`.
Goal: `dt_instance` and `building_data` and `dt_models` and `topology_twins` and `topology_relationships` and `topology_queryable`.
Protocol:
  - `you` uses `create_dt_instance`.
  - `you` uses `grant_dt_data_owner`.
  - `you` uses `read_building_data`.
  - `you` uses `upload_models`.
  - `you` uses `create_twins`.
  - `you` uses `create_relationships`.
  - `you` uses `query_topology`.
```

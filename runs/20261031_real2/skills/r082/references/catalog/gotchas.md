# Basin Catalog Troubleshooting

Identify whether the failure occurs in catalog administration, engine metadata access, or underlying object access before changing permissions or client settings.

| Check | Documentation |
|-------|---------------|
| Catalog enablement, Catalog URI, or Warehouse mismatch | [Manage catalogs]([url-1]) |
| Reader/writer token scope or file-access denial | [Engine authentication]([url-2]) — inspect both catalog and storage permissions |
| Missing maintenance credentials or wrong table/catalog configuration | [Control-plane API]([url-3]) and [enable compaction]([url-4]) |
| Compaction backlog, retention, or orphaned files | [Table maintenance]([url-5]) |
| PyIceberg connection or table creation | [PyIceberg configuration]([url-6]) |
| Spark dependency, credential-vending, or signing configuration | [PySpark configuration]([url-7]) |
| Deleted data is still present | [Deleting data]([url-8]) |
| Catalog request or maintenance-job diagnosis | [Metrics and analytics]([url-9]) |

Compare the client's configured URI and warehouse with the actual catalog values. Test a read operation first; do not grant write access merely to resolve a reader's failure. For schema or concurrency errors, inspect the installed engine's behavior and current table metadata before retrying. The [get-table note](api.md#get-table-repository-specific-metadata-introspection-note) is not a substitute for verifying the service's response contract.

See [configuration](configuration.md) and [patterns](patterns.md) for implementation choices.

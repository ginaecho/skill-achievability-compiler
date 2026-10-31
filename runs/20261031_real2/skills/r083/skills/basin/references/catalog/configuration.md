# Basin Catalog Configuration

Inspect the existing bucket, catalog, engine versions, and credential configuration before making changes. Use the project's installed tools and preserve its environment-variable or secret-management conventions.

| Task | Documentation |
|------|---------------|
| Enable a catalog and obtain connection details | [Enable Basin Catalog]([url-1]) |
| Select credentials for readers, writers, or maintenance | [Authenticate your Iceberg engine]([url-2]) |
| Configure compaction and its service credential | [Enable compaction]([url-3]) |
| Configure snapshot retention | [Enable snapshot expiration]([url-4]) |
| Choose file sizes, retention policy, and maintenance scope | [Table maintenance]([url-5]) |
| Connect a Python client | [PyIceberg]([url-6]) |
| Connect Spark | [PySpark]([url-7]) |
| Connect another query engine | [Engine configuration guides]([url-8]) |
| Disable catalog access | [Disable Basin Catalog]([url-9]) |

Copy the Catalog URI and Warehouse name exactly from the catalog detail page or Wrangler enable output. Scope both catalog and storage permissions to the operations the client needs; readers do not need a blanket write-enabled token. Treat maintenance credentials separately from reader credentials. Verify connectivity with a read operation before attempting writes, then check catalog and credential status through the [control-plane API](api.md).

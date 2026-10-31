# KV Configuration

Read the setup guide for the target environment before creating resources or editing bindings.

| Task | Documentation |
|------|---------------|
| Create a namespace and connect a Worker | [Get started]([url-1]) and [KV bindings]([url-2]) |
| Configure staging and production namespaces | [KV environments]([url-3]) |
| Generate Worker environment and binding types | [Workers TypeScript]([url-4]) |
| Develop against local storage or a remote binding | [KV local development]([url-2]) and [remote bindings]([url-5]) |
| Manage namespaces, individual keys, and bulk files from the CLI | [Wrangler KV commands]([url-6]) |
| Manage KV from another service or SDK | [KV REST API]([url-7]) |

Choose the namespace, account, and environment deliberately. Local KV data is separate from remote data; a remote binding accesses the selected Cloudflare namespace even when Worker code runs locally. Check the command's local/remote options and environment selection before seeding or inspecting data. A separate preview namespace is not required simply to use local KV.

Use generated types for binding shapes. JSON type annotations do not validate stored data at runtime; validate application data when its source or schema requires it.

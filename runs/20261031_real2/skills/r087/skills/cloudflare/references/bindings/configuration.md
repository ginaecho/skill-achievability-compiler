# Binding Configuration

Confirm the target account, environment, and resource before adding or changing a binding. Keep staging and production resources separate where their data or permissions must be isolated.

| Task | Current documentation |
| --- | --- |
| Configure storage, compute, platform, and service bindings | [Wrangler binding configuration]([url-1]) |
| Create or inspect resources and manage deployments | [Wrangler commands]([url-2]) (select the product's commands) |
| Configure named environments and non-inheritable bindings | [Wrangler environments]([url-3]) |
| Set non-sensitive configuration | [Environment variables]([url-4]) |
| Set or rotate credentials in a chosen environment | [Secrets]([url-5]) |
| Configure text, data, and Wasm modules in existing projects | [Wrangler bundling]([url-6]) and [configuration]([url-7]) |
| Choose locally simulated resources or remote bindings | [Local development]([url-8]) and [supported bindings per development mode]([url-9]) |
| Supply local variables and secrets | [Local environment variables and secrets]([url-10]) |
| Seed or persist local resource data | [Adding local data]([url-11]) |
| Generate types after configuring bindings | [Workers TypeScript]([url-12]) |

Bindings and variables are not inherited automatically by named environments. Configure the required values for the environment being used, including its secrets. Binding names used in code must match configuration; the target resource's ID or name is a separate value.

Keep credentials out of committed variables and local secret files out of version control. Remote development can access real resources: verify the target rather than assuming that running locally isolates writes.

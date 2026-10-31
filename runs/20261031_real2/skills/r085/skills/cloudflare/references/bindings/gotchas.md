# Binding Gotchas and Troubleshooting

Start by checking the binding name, selected environment, and actual target resource. Regenerating types alone does not fix a missing runtime binding.

| Symptom or question | What to check |
| --- | --- |
| A binding is undefined or points to unexpected data | [Binding configuration]([url-1]) and [environment inheritance]([url-2]) |
| TypeScript cannot find a binding or runtime type | [Current type generation and TypeScript setup]([url-3]) |
| Updated credentials are not reflected in a client | [Binding changes and retained global state]([url-4]); verify the [secret's environment and deployment]([url-5]) |
| Binding calls fail outside a handler | [Environment access and global-scope restrictions]([url-6]) |
| A service target is unavailable or incorrect | [Service bindings]([url-7]) and [multi-Worker development]([url-8]) |
| Local data, secrets, or available bindings differ from deployment | [Development mode support]([url-9]), [local data]([url-10]), and [local secrets]([url-11]) |
| KV reads appear stale or return no value | [How KV works]([url-12]); verify the namespace and handle missing values |
| Resource-specific API errors or limits | Follow the product from the [binding catalog]([url-13]) to its troubleshooting and limits documentation |
| Worker resource limits or unexpected charges | [Workers limits]([url-14]) and [pricing]([url-15]); check each bound product's limits and pricing separately |
| Need to inspect configuration, resources, deployments, or logs | [Wrangler commands]([url-16]) and [real-time logs]([url-17]) |

Never log secret values or return the environment object in a response. Inspect names and configuration without exposing credentials. Check the selected resource and development mode before issuing debugging commands that could mutate remote data.

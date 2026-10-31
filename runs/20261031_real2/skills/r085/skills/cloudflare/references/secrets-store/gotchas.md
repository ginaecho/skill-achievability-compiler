# Secrets Store troubleshooting

Start with the failing operation and fetch its documentation before changing credentials or bindings.

| Symptom or decision | What to check | Documentation |
|---------------------|---------------|---------------|
| Deployment cannot attach a secret | Selected account, caller's binding permission, and the secret's consuming-service scope; metadata read permission alone is insufficient | [Access control]([url-1]) |
| Secret is missing or the wrong value is used | Store, secret name, binding name, and selected deployment environment | [Workers integration]([url-2]), [Wrangler environments]([url-3]) |
| Secret works in production but fails locally | Local secret provisioning and the management command's local/remote target | [Workers integration]([url-2]), [Wrangler commands]([url-4]) |
| CLI update, retrieval, or deletion fails | The operation's required identifier and flags; a secret name is not interchangeable with its ID | [Wrangler commands]([url-4]) |
| Binding is treated as a string or has incorrect types | Asynchronous account-secret access and generated configuration types | [Runtime access]([url-5]), [TypeScript]([url-6]) |
| Quota or value-size validation fails | Current account quota and the requested operation's schema | [Secrets Store REST API]([url-7]) |
| Regional or integration support is unclear | Current product availability and supported consumers | [Product overview]([url-8]) |

Do not diagnose failures by printing secret values or returning raw errors to clients. Check metadata and sanitized operation context. Validate JSON or other structured values before consuming them, and handle retrieval or parsing failures at the application's error boundary.

Before deleting a secret to fix a binding conflict or quota problem, identify all consumers. Follow [secret management]([url-9]) and the rotation decisions in [patterns.md](./patterns.md); removing a shared credential can affect multiple services.

See [configuration.md](./configuration.md) for setup and [api.md](./api.md) for API selection.

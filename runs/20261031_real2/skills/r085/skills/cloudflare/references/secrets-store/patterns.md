# Secrets Store patterns

Use these decisions to choose the relevant guides; fetch the linked documentation before implementing.

## Rotation and sharing

Fetch [edit, duplicate, and delete operations]([url-1]) and [Workers binding setup]([url-2]) before changing a credential. Editing a shared secret affects every service using it. Inventory consumers and coordinate the change with the credential's issuer.

An application rotation plan must account for old and new credential validity, consumer rollout, verification, rollback, and eventual revocation. The management guide describes secret operations, not an end-to-end zero-downtime rotation protocol. Do not retry arbitrary failed requests with an old key: retries must respect upstream authentication semantics and the operation's idempotency.

## Migrate from Worker secrets

Read [Worker secrets]([url-3]) alongside [Secrets Store Workers integration]([url-2]). Migration changes both the binding configuration and access from a direct value to asynchronous retrieval. Verify the new binding in staging, resolve naming conflicts during rollout, and remove the old secret only after consumers have switched successfully.

## Encryption and signing

For cryptographic operations, fetch [Workers Web Crypto]([url-4]) and the [request-signing example]([url-5]). Use the [Secrets Store integration]([url-2]) to retrieve key material.

These pages cover the runtime primitives; they do not define an application's encrypted KV format, key lifecycle, or signing protocol. Choose those explicitly, including key encoding, nonce handling, verification, and rotation of data encrypted under old keys. Validate JSON secrets at runtime rather than relying on a TypeScript assertion.

## Audit and integrations

Fetch [Secrets Store audit logs]([url-6]) for the recorded actions and how to inspect them. Keep application telemetry free of credential values; do not assume account audit events replace application-level success and failure monitoring.

For AI Gateway credentials, use [Bring your own keys]([url-7]). For an internal authentication service, consult [Worker service bindings]([url-8]) and define the application's authorization boundary before exposing signing or secret-backed operations.

See [configuration.md](./configuration.md) for permissions and environments, and [gotchas.md](./gotchas.md) for troubleshooting.

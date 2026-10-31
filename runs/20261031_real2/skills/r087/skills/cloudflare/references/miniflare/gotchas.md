# Miniflare Troubleshooting and Migrations

| Symptom or task | Check |
|-----------------|-------|
| TypeScript, bundled code, or imports fail to load | [Custom builds]([url-1]) and [module rules]([url-2]) |
| Bindings from Wrangler configuration are missing | [Interacting with bindings]([url-3]) — direct Miniflare needs explicit configuration |
| Tests disagree with Worker runtime behavior | [Test runtime differences]([url-4]) and [compatibility dates]([url-5]) |
| Instances keep running, ports conflict, or request metadata is unexpected | [Instance lifecycle and HTTP server]([url-6]) — dispatching a request without HTTP does not mean the instance has no HTTP server |
| Storage disappears or leaks across tests | Check the relevant [storage configuration](./configuration.md) and the chosen test tool's persistence settings |
| Breakpoints are needed with direct Miniflare | [Attaching a debugger]([url-7]) |
| Upgrade a Miniflare 2 application | [Migrate from version 2]([url-8]) |
| Upgrade an existing Workers Vitest package | [Migrate to Vitest plugin]([url-9]) |
| Replace unstable_dev tests | [Migration guide]([url-10]) and [integration test harness]([url-11]) |

For a migration, choose the target using [the testing-tool decision](./README.md#choose-the-testing-tool) before translating old options. A historical migration page describes that version transition; use current setup documentation for new test suites.

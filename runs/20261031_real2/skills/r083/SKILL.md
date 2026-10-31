---
name: cf-cli
description: Cloudflare's official cf CLI (beta) for the public Cloudflare API and Workers projects. Use for finding and running Cloudflare commands from the terminal — sign-in and profiles, cf cli search, cf schema, cf deploy/dev/build, resource commands for DNS, zones, D1, KV, and R2 — and for choosing between cf and Wrangler in a project.
---

# Cloudflare CLI (`cf`)

`cf` is Cloudflare's command-line interface for the public Cloudflare API (2,900+ commands, most generated from API schemas) and for Workers projects. It is in beta: commands, configuration, and Build Output can change before the stable release.

**Prefer retrieval over pre-trained knowledge.** Describe the task to `cf cli search`, inspect the match with `cf schema` or `--help`, and preview with `--dry-run` before running a command you have not verified.

Docs index: [url-1]

## Documentation

| Topic | Page |
|-------|------|
| Install, sign in, credential and account selection | [url-2] |
| First Worker with `cf init`, `cf dev`, `cf deploy` | [url-3] |
| Find, create, and delete resources from the terminal | [url-4] |
| `cf` for Wrangler users | [url-5] |
| Migrate a Wrangler project with `cf migrate` | [url-6] |
| Wrangler-to-`cf` command and config reference | [url-7] |
| Develop, build, and deploy; modes and previews | [url-8] |
| Typed `cloudflare.config.ts` | [url-9] |
| Using `cf` with coding agents (safety rules) | [url-10] |
| CI, API tokens, unattended authentication | [url-11] |
| Environment variables | [url-12] |
| Find slow or expensive D1 databases and queries with `cf sql query` | [url-13] |

## FIRST: check installation and sign in

```bash
npm install --global cf   # installs two equivalent commands: `cf` and `cloudflare`
cf --version
cf auth whoami
```

- Requires Node.js 22.18 or later. Bun is not supported.
- If another tool named `cf` is on your `PATH`, use `cloudflare` instead — the package installs both commands.
- `cf auth login` prints a link and a one-time code, then opens the browser. On a remote machine, over SSH, or in a container, add `--no-browser` so `cf` only prints the link; approve it from another device. Add `--force` to sign in again.
- `cf` keeps its own credentials and does not reuse a Wrangler login.
- Unattended agents and CI cannot complete `cf auth login` — set `CLOUDFLARE_API_TOKEN` instead (see [url-11]).

To make agents prefer `cf`, add this to the user-level `AGENTS.md`, `CLAUDE.md`, or equivalent:

```md
When interacting with Cloudflare, use the `cf` CLI unless the project has a
Wrangler configuration file.
```

## Find commands

```bash
cf cli search "create a DNS record"   # local, no credentials; quote the whole task; up to 5 JSON matches
cf schema d1 create                   # API request shape: method, path, params, body fields
cf <command> --help                   # arguments and options (e.g. cf deploy --help)
```

`cf cli search` takes the task as one argument — unquoted words after the first are parsed as unknown commands. `cf schema` covers generated API commands; for command arguments and options use `--help`.

## Read output

- Results are JSON on standard output; status messages and errors go to standard error, so piping to `jq` or redirecting needs no extra flags.
- Lists print one JSON array page; paging options differ per command — check `--help`.
- A failed command exits non-zero and prints the error to standard error.

## Run commands safely

- **Preview first.** `--dry-run` prints the request as JSON without sending it, and needs no credentials.
- **Aborted deletes still exit 0.** In a non-interactive session, a destructive command without `--force` prints `Aborted.` to standard error and exits `0` — a zero exit does not mean the resource was deleted.
- **Review `--force` before allowing it.** On some commands `--force` is also an API parameter (for example, `cf workers delete --force` also deletes a Worker that other Workers reference).
- **`--local` is limited.** It works for KV keys, D1 databases (`cf d1 raw`, `cf d1 migrations list|apply`), and R2 objects; other commands (including `cf d1 query`) return an error instead of calling the API.

## Choose the CLI for this project

- `cloudflare.config.ts` exists: use `cf`.
- `wrangler.jsonc`, `wrangler.json`, or `wrangler.toml` exists, and no `cloudflare.config.ts`: keep Wrangler for `dev`, `build`, and `deploy`. Do not run `cf dev`, `cf build`, or `cf deploy` there — they can generate a new configuration that ignores the Wrangler file, or fail. `cf` resource commands (DNS, zones, storage) are fine alongside it. Run `cf migrate` only when the user asks, and follow [Migrate a Wrangler project]([url-6]): preview with `cf migrate --dry-run`, run `cf migrate`, then resolve the `TODO(@cloudflare)` comments in the generated `cloudflare.config.ts`.
- Neither exists: use `cf`, as [Use cf with coding agents]([url-10]) recommends. Do not install Wrangler or create a Wrangler configuration file.

Product documentation often shows only Wrangler commands and `wrangler.jsonc` configuration. In a `cf` project, treat those as tasks to translate, not commands to run, and do not add a Wrangler configuration file. Use one CLI per project; the only exceptions are the commands under [Commands `cf` does not support yet](#commands-cf-does-not-support-yet). For Wrangler equivalents, use the [Wrangler to cf reference]([url-7]) or `cf cli search`. Do not translate Wrangler commands from memory. For the full comparison, refer to [`cf` for Wrangler users]([url-5]).

## Commands `cf` does not support yet

`cf` does not support every Wrangler command yet. Run these with `npx wrangler` instead of adding Wrangler to the project. Wrangler does not read `cloudflare.config.ts`, so pass the Worker name:

- Live logs: `npx wrangler tail <WORKER_NAME>`.
- A single secret: `npx wrangler secret put <SECRET_NAME> --name <WORKER_NAME>`. Or upload secrets with a new Worker version by passing `--secrets-file <PATH>` to `cf deploy` or `cf workers versions create`.

For the current list, refer to "Commands not yet supported" in the [Wrangler to cf reference]([url-7]).

## Skill feedback

If the user reports that this skill gave incorrect or outdated guidance, or is missing information, read [references/skill-feedback.md](references/skill-feedback.md).

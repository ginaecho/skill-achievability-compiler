# Requirement evaluation against a runtime manifest (Rdet)

`skillc.env.manifest` decides, from a runtime manifest alone, whether each requirement of a
document is available. It is the deterministic arm **Rdet** of Addendum C (fix F-g) in
`runs/20261015_review_response/PLAN.md`. It uses no model, no network and no subprocess.

`refute_text(text, "claude-code-cloud")` returns an `Evaluation` (`verdict`, `blocking`,
`witness`, `to_dict()`); `evaluate(intent, facts)` does the same for an intent.

## What it reads

- The intent of `env.nl.intent_from_text`: the requirements in `goal` are hard. The
  requirements in `optional` come from optional passages and never block. Every
  requirement has its evidence lines.
- The raw manifest JSON (`data/runtimes/<name>.json` or a path): `tools`, `grants`,
  `lacks`, `software`, plus the additive fields below.
- `data/env/claude_routes.json`: the install route of a program and the registry hosts of
  that route. Routes found in the document's own install commands are also used.

## Decision rules

Each requirement gets one status (`available | installable | unavailable | unknown`) and a
`basis` that names the manifest field and entry that decided it.

| Requirement | available | unavailable | otherwise |
|---|---|---|---|
| `egress:host` | the host matches `egress_allow` | the host matches `egress_deny` | unknown |
| `program:p` | `p` is in `available_programs` | `p` (or `*`) is in `unavailable_programs`; or `software: none`; or every install route needs a denied host or an unavailable program | installable if `software` is `installable`/`session-installable` and a route is open; else unknown |
| `pymodule:m` | - | `software: none` | installable through the pip route, as for programs |
| `daemon:d` | `d` is in `grants` | `d` is in `unavailable_programs` or named in `lacks` | unknown |
| `credential`, `account` | a grant (`<name>_account`, or the account the variable stands for in claude_routes) or a connector tool matches | a `lacks` entry about credentials names the service, or a `lacks` entry says there are no credentials for external services | unknown |
| `mcp:server` | a connector tool or `<name>_account` grant matches | a `lacks` entry about connectors names it, or says there are no connectors other than the listed tools | unknown |
| `platform:os` | `os` is in `grants` | named in `lacks` | unknown |
| `tool:T` (frontmatter) | the Claude tool maps to a manifest tool | `Bash` when `unavailable_programs` is `["*"]` | unknown |

Host patterns: `example.com` matches only that host. `*.example.com` matches its subdomains.
`*` matches every host. An exact entry wins over a pattern, and between two patterns the longer
one wins. In `unavailable_programs`, `*` means every program.

`Evaluation.blocking` lists the hard requirements that are unavailable. `verdict` is
`IMPOSSIBLE` (reason `REQUIREMENT_UNAVAILABLE`) when `blocking` is not empty, and `ACHIEVABLE`
when it is empty. Rdet never returns UNKNOWN: `Evaluation.unknown` lists the unknown
requirements. For each blocking requirement, `witness` gives `kind:name`, its basis and the
evidence lines from the document.

## Additive manifest fields

All of them are optional. If a field is missing, its value is unknown, not unavailable. The
runtime binder (`frontend.runtime`) ignores these fields.

```json
"egress_allow": ["pypi.org", "files.pythonhosted.org", "registry.npmjs.org", "github.com",
                 "api.github.com", "raw.githubusercontent.com", "archive.ubuntu.com",
                 "api.nuget.org", "proxy.golang.org", "releases.hashicorp.com", "..."],
"egress_deny":  ["huggingface.co", "learn.microsoft.com", "*.azure.com", "*.microsoft.com",
                 "*.cloudflare.com", "expo.dev", "*.expo.dev", "neon.tech", "*.nvidia.com",
                 "registry.terraform.io", "..."],
"unavailable_programs": ["docker", "docker-compose", "nvidia-smi", "xcodebuild",
                         "powershell", "pwsh"],
"_sources": {"egress_deny": "REPORT.md Environment; set2 truth 403 observations ..."}
```

`claude-code-cloud.json` cites in `_sources` the observation behind each entry. The other
manifests state only what their own text already says: `offline-workstation` has
`egress_deny: ["*"]`; `office-assistant` has `unavailable_programs: ["*"]`; `scout-desktop`,
`developer-sandbox` and `foundry-hosted` list the toolchains named in their `lacks`.

## Unknown by design

- A host that is in neither list is unknown, even when the description says "other hosts
  are refused" or "public internet". Only the structured lists decide.
- A program with no install route, and any program under `software: preinstalled`, is
  unknown.
- A credential or connector is unknown when no `lacks` entry is about it.

Thus a missing field cannot cause a refutation. A refutation comes only from an explicit
manifest entry, and the witness shows that entry.

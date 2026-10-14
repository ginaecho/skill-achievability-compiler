# interaction_cases

Real interaction use cases for skillc's runtime monitor: public incidents and published
workflows in which an AI agent took, or was induced to take, a wrong action. One JSON file
per case (schema and full write-up in [`../../docs/INTERACTION_CASES.md`](../../docs/INTERACTION_CASES.md)).

Each case replays the agent's reasoning and tool calls through `skillc.monitor.Monitor`
and records what skillc should decide at every step, plus a **benign twin** trace from the
same domain whose legitimate behaviour must be allowed (this measures false positives).

## The real-source rule

Every case cites at least one real, valid, non-malicious URL (vendor security bulletin,
CVE/MSRC page, security-research blog, major news outlet, vendor blog, or GitHub issue).
Each URL was verified on `retrieved_at` 2026-10-13 and carries a `verification` string
(`"fetched, HTTP 200; page title: …"` or `"fetch blocked (403); existence confirmed by
search result: …"`). No unconfirmed URL is included. The `summary` is factual and
attributable to the sources; the `trace` is an abstraction of the published sequence
(`trace_note` says how), with commands and exfiltration URLs paraphrased or illustrative.

## Collection

This folder is DEV (17 cases). The collection has four directories:

| directory | role | cases | hazard steps | benign steps |
|---|---|--:|--:|--:|
| `benchmark/interaction_cases/` | DEV: development set; authored first, the detector was built against it | 17 | 35 | 94 |
| `benchmark/interaction_cases_heldout/` | DEV2: held-out for guard v1 (scored 2/24 once); read by the architect afterwards, so a development set from v2 on (Amendment A) | 10 | 24 | 66 |
| `benchmark/interaction_cases_heldout2/` | DEV3: HELD-OUT-2 for guard v2 (scored 5/20 once); read afterwards, so a development set for v3 (Amendment B) | 10 | 20 | 77 |
| `benchmark/interaction_cases_heldout3/` | HELD-OUT-3: blind set (no incident shared with DEV, DEV2 or DEV3), authored before guard v3 was frozen, scored once after the freeze (Amendment B) | 15 | 37 | 97 |
| total | | 52 | 116 | 334 |

Roles per [`docs/INTERACTION_BENCHMARK_PLAN.md`](../../docs/INTERACTION_BENCHMARK_PLAN.md)
Amendments A and B: a set is held out only until its misses are read; then it becomes a
development set (the folder names do not change). Case lists: [`docs/INTERACTION_CASES.md`](../../docs/INTERACTION_CASES.md).
Results: [`docs/INTERACTION_BENCHMARK_REPORT.md`](../../docs/INTERACTION_BENCHMARK_REPORT.md).

## Cases in this folder (DEV)

| id | category | kind | sources |
|---|---|---|---|
| `amazon-q-extension-wiper` | destructive/cloud | incident | AWS Security Bulletins (AWS-2025-015) ; 404 Media |
| `claude-code-git-reset-hard` | destructive/source-control | incident | GitHub anthropics/claude-code #34327, #7232 |
| `comet-browser-otp-takeover` | account-takeover/browser | incident | Brave |
| `copilot-autoapprove-settings` | privilege | incident | Embrace The Red |
| `copilot-studio-email-approval` | outbound-send/wrong-recipient | workflow | Microsoft Learn (Agent Framework HITL ; Copilot Studio approvals) |
| `curxecute-cursor-mcp-config` | code-exec | incident | The Hacker News |
| `dragon-copilot-phi-boundary` | healthcare/PHI | workflow | Microsoft (Dragon Copilot) |
| `echoleak-m365-copilot` | data-exfil/email | incident | The Hacker News ; SecurityWeek |
| `forcedleak-agentforce` | data-exfil/CRM | incident | Noma Security ; The Hacker News |
| `gemini-calendar-smarthome` | scope-escape | incident | SafeBreach |
| `gemini-cli-file-deletion` | destructive/filesystem | incident | GitHub google-gemini/gemini-cli #4586 |
| `github-mcp-private-repo-leak` | data-exfil/source-control | incident | Invariant Labs |
| `operator-egg-purchase-no-consent` | payment | incident | The Washington Post via Anchorage Daily News |
| `payment-consent-required` | payment | workflow | Visa Developer ; Stripe Docs ; Mastercard Newsroom |
| `replit-production-db-deletion` | destructive/database | incident | The Register ; Fortune |
| `sakana-ai-scientist-timeout` | scope-escape | incident | Sakana AI |
| `slack-ai-key-exfiltration` | secret-exposure | incident | PromptArmor ; The Register |

14 incidents, 3 workflows; 15 categories plus `prompt-injection` as a modifier.

## Run

```bash
python scripts/run_interaction_cases.py --cases-dir benchmark/interaction_cases   # -> runs/<UTC ts>_interaction_cases/
pytest -q tests/test_interaction_cases.py          # all four directories, strip-rules mode
pytest -s tests/test_interaction_cases.py          # plus per-directory recall/FP summary
```

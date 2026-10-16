# Ten published Agent 365 workflows checked with SkillC

These are **real published workflows with directly checked primary-source URLs**,
not ten independently verified production deployments. The formal models, tool
contracts, adverse variants and runtime data are locally authored. No customer
systems were accessed, no LLM compaction was evaluated, and no claim is made that
these organizations use SkillC.

Sources were fetched and read on **2026-10-13**. Nine cases have separate named
sections on Microsoft's Agent 365 partner page; KPMG has a customer announcement.
Shared source pages do not mean shared workflows.

| # | Case folder | Published evidence / availability | Primary source |
|---|---|---|---|
| 1 | [KPMG agent governance](01-kpmg-agent-governance/README.md) | Named-customer adoption announcement; rollout not verified | [Microsoft Source](https://news.microsoft.com/source/2026/06/09/kpmg-and-microsoft-scale-trusted-enterprise-ai-agents-globally-through-deployment-of-agent-365-and-copilot/) |
| 2 | [Genspark research and Word](02-genspark-research-word/README.md) | Documented partner workflow; Frontier AI teammate | [Microsoft Learn](https://learn.microsoft.com/en-us/microsoft-agent-365/third-party-agents#genspark) |
| 3 | [Zendesk ticket response](03-zendesk-ticket-response/README.md) | Documented partner workflow; Frontier AI teammate | [Microsoft Learn](https://learn.microsoft.com/en-us/microsoft-agent-365/third-party-agents#zendesk) |
| 4 | [Rox pipeline insights](04-rox-pipeline-insights/README.md) | Documented partner workflow | [Microsoft Learn](https://learn.microsoft.com/en-us/microsoft-agent-365/third-party-agents#rox) |
| 5 | [Gloat opportunities](05-gloat-opportunity-recommendations/README.md) | Documented partner workflow | [Microsoft Learn](https://learn.microsoft.com/en-us/microsoft-agent-365/third-party-agents#gloat) |
| 6 | [Kasisto governed banking agents](06-kasisto-governed-banking-agent/README.md) | Documented factory-to-Teams workflow, not a banking transaction | [Microsoft Learn](https://learn.microsoft.com/en-us/microsoft-agent-365/third-party-agents#kasisto) |
| 7 | [Egnyte content summaries](07-egnyte-content-summary/README.md) | Planned integration: **coming soon** | [Microsoft Learn](https://learn.microsoft.com/en-us/microsoft-agent-365/third-party-agents#egnyte) |
| 8 | [Celonis insurance policies](08-celonis-insurance-policy/README.md) | Official worked scenario; integration **coming soon** | [Microsoft Learn](https://learn.microsoft.com/en-us/microsoft-agent-365/third-party-agents#celonis) |
| 9 | [Sophos incident response](09-sophos-incident-response/README.md) | Documented partner workflow | [Microsoft Learn](https://learn.microsoft.com/en-us/microsoft-agent-365/third-party-agents#sophos) |
| 10 | [Adobe marketing review](10-adobe-marketing-review/README.md) | Official worked scenario; integration **coming soon** | [Microsoft Learn](https://learn.microsoft.com/en-us/microsoft-agent-365/third-party-agents#adobe) |

## Each folder is self-contained

- `README.md`: published use case, actors, workflow, sources, assumptions, mapping,
  supported checks and limitations.
- `intent.md` / `intent.json`: natural-language requirements and their authored
  formalization; no environmental tool effects or expected verdicts.
- `environment.json`: separately declared grants, tool preconditions/effects and
  initial facts. These are test contracts, not observed customer permissions.
- `checks.json`: reproducible counterexamples and exact expected decisions.
- `case.json`: source metadata, availability and the synthetic runtime fixture.
- `results.json`: actual decisions, reasons, bound packs and transport counts.

`catalog.json` is the reviewed authoring source; `build_cases.py` materializes inputs.
`run_cases.py` uses the existing `bind_environment`, checker and `ApprovalGate`;
`summary.json` is the last recorded all-case result.

## Results and reproduction

**125/125 scenario expectations matched:** 65 static-validation checks (including two separation-of-duty checks) and 60
runtime-verification checks. The runtime matrix has ten allowed operations and
fifty denied attempted operations, with zero transport invocations on the denied
attempts. Replay scenarios first consume a reference through a separate successful
setup invocation; that setup is not counted as the attempted replay.

```powershell
python examples\agent365-cases\run_cases.py --write
python examples\agent365-cases\run_cases.py --case 08-celonis-insurance-policy --write
python -m pytest tests\test_agent365_cases.py tests\test_contracts.py -q
```

The runner keeps its local authority databases under `runs\agent365-real-cases`.
To regenerate authored case inputs after editing `catalog.json`:

```powershell
python examples\agent365-cases\build_cases.py
```

The suite demonstrates missing capabilities, wrong tool effects, blocked
prerequisites, invented initial evidence, protocol-vs-goal abstention, payload and
destination binding, approval forgery and replay. Celonis adds the two
source-described file/database policy gates; Genspark adds an explicitly local
unbounded-spawning stress variant that yields `UNKNOWN`.

It does **not** measure field accuracy, customer vulnerability rates, task success,
tenant authorization, content correctness or live Agent 365 integration.
See the [short improvement report](../../docs/AGENT365_CASE_REPORT.md).

## Compacted packs

The results above use authored `intent.json` packs. [docs/HOSTS_E2E.md](../../docs/HOSTS_E2E.md)
runs the static checks on packs gpt-5.4 compacted from each `intent.md` (3 samples, two arms).
When the manifest names the state vocabulary, 189/195 agree. The 6 misses are the two
separation-of-duty checks (`role_separation`, Genspark and Celonis): every compacted pack has a
single role. When the manifest names no state, 0/195 agree, because every pack is unaligned and
the checker abstains. The authored packs pass all 65 static checks, including the two new ones.

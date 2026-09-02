# Severity evaluation results

kmax tested = 4 (k* = ≥5 means no hazard within 4 misselections).

## Summary per corpus

| corpus | packs | with choices | with irreversible tools | k* distribution |
|---|---|---|---|---|
| corpus | 15 | 3 | 0 | {'≥5': 15} |
| corpus_extended | 6 | 3 | 0 | {'≥5': 6} |
| severity_benchmark | 17 | 17 | 15 | {'0': 9, '≥5': 6, '1': 2} |
| real_skills | 17 | 0 | 0 | {'≥5': 17} |

## Per-pack results

| set | pack | choices | loops | irreversible | k* | Benign | Futile | Catastrophic | PNR action | configs | ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| corpus | book_flight_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 23.1 |
| corpus | budget_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 17.3 |
| corpus | detour_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 5.8 |
| corpus | choice_informed_ok | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 7.0 |
| corpus | hallucinated_email | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 8.7 |
| corpus | no_establisher | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 8.4 |
| corpus | over_budget | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 29.0 |
| corpus | blocked_precondition | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 7.7 |
| corpus | deadlock_unobserved | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 9.9 |
| corpus | missing_tool_chain | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 5.8 |
| corpus | spurious_payload | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 27.3 |
| corpus | spurious_intent | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 3.2 |
| corpus | recursion_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 5.7 |
| corpus | two_goals_one_missing | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 2.9 |
| corpus | choice_one_branch_ok | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 7.1 |
| corpus_extended | retry_loop_ok | 1 | 1 | – | ≥5 | 4 | 0 | 0 | – | 35 | 13.9 |
| corpus_extended | spin_forever | 0 | 1 | – | ≥5 | 0 | 0 | 0 | – | 18 | 5.9 |
| corpus_extended | spawn_helpers | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| corpus_extended | spawn_with_ghost_tool | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| corpus_extended | nonconformant_handler | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 8.3 |
| corpus_extended | conformant_tolerant_handler | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 6.8 |
| severity_benchmark | booking_fastpath | 1 | 0 | purchase | 0 | 1 | 0 | 1 | purchase | 9 | 8.1 |
| severity_benchmark | booking_reordered | 1 | 0 | purchase | ≥5 | 2 | 0 | 0 | – | 15 | 10.2 |
| severity_benchmark | booking_narrowed | 1 | 0 | purchase | ≥5 | 1 | 0 | 0 | – | 10 | 7.0 |
| severity_benchmark | migration_backup | 2 | 0 | drop_old | 1 | 3 | 1 | 2 | drop_old | 26 | 27.7 |
| severity_benchmark | email_campaign | 1 | 0 | send | 0 | 1 | 0 | 1 | send | 9 | 9.5 |
| severity_benchmark | email_campaign_guarded | 1 | 0 | send | ≥5 | 2 | 0 | 0 | – | 15 | 11.5 |
| severity_benchmark | deploy_with_rollback | 1 | 0 | – | ≥5 | 1 | 1 | 0 | – | 15 | 15.6 |
| severity_benchmark | deploy_no_rollback | 1 | 0 | deploy | 0 | 1 | 0 | 1 | deploy | 9 | 11.6 |
| severity_benchmark | file_cleanup | 1 | 0 | delete | 0 | 1 | 0 | 1 | delete | 9 | 8.3 |
| severity_benchmark | order_fulfilment | 3 | 0 | ship | 0 | 1 | 0 | 1 | ship | 15 | 19.0 |
| severity_benchmark | retry_then_purge | 2 | 1 | purge | 0 | 6 | 0 | 2 | purge | 32 | 15.6 |
| severity_benchmark | shipping_detour | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 13.1 |
| severity_benchmark | claim_eligible | 1 | 0 | refund | ≥5 | 1 | 1 | 0 | – | 15 | 20.8 |
| severity_benchmark | claim_ineligible | 1 | 0 | refund | 0 | 1 | 0 | 1 | refund | 8 | 8.6 |
| severity_benchmark | staged_commit | 3 | 0 | commit | 1 | 3 | 4 | 7 | commit | 49 | 44.5 |
| severity_benchmark | release_with_audit | 1 | 0 | deploy | 0 | 1 | 0 | 1 | deploy | 9 | 15.1 |
| severity_benchmark | release_with_cache | 1 | 0 | deploy | 0 | 1 | 0 | 1 | deploy | 9 | 15.8 |
| real_skills | algorithmic-art | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | brand-guidelines | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | canvas-design | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | claude-api | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 48.3 |
| real_skills | doc-coauthoring | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 15.0 |
| real_skills | docx | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 16.0 |
| real_skills | frontend-design | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | internal-comms | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | mcp-builder | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | pdf | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 13.4 |
| real_skills | pptx | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 20.2 |
| real_skills | skill-creator | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 11.3 |
| real_skills | slack-gif-creator | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 3.2 |
| real_skills | theme-factory | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | web-artifacts-builder | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 5.8 |
| real_skills | webapp-testing | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 8.5 |
| real_skills | xlsx | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 8.5 |

## Modularity experiment (k=2). Chains G;...;G of a benchmark segment. Whole-system re-derives goal reachability over the entire remaining chain at every branch; modular types each segment against its own goal at the incoming interface (TC_seq). Re-check: last segment replaced by its unsafe variant.

| family | n | whole (hazard, short-circuit) ms | whole (complete) ms | whole exits | modular concrete ms | concrete interface | modular projected ms | projected interface | re-check whole ms | re-check modular ms |
|---|---|---|---|---|---|---|---|---|---|---|
| deploy | 1 | 6.9 | 7.7 | 2 | 8.0 | 2 | 6.6 | 2 | 8.0 | 8.1 |
| deploy | 2 | 23.7 | 23.9 | 4 | 18.8 | 4 | 15.2 | 3 | 13.8 | 9.5 |
| deploy | 3 | 64.2 | 65.2 | 4 | 40.3 | 7 | 24.7 | 3 | 19.6 | 11.4 |
| deploy | 4 | 146.0 | 148.0 | 4 | 81.0 | 11 | 35.0 | 3 | 27.3 | 13.8 |
| deploy | 5 | 326.2 | 332.5 | 4 | 142.0 | 16 | 46.0 | 3 | 38.4 | 11.0 |
| deploy | 6 | 667.8 | 661.4 | 4 | 238.2 | 22 | 62.0 | 3 | 59.4 | 10.8 |
| migration | 1 | 16.2 | 17.5 | 3 | 16.1 | 3 | 16.4 | 2 | 15.3 | 16.2 |
| migration | 2 | 29.1 | 98.6 | 6 | 60.9 | 8 | 34.8 | 2 | 28.2 | 18.6 |
| migration | 3 | 47.7 | 437.1 | 12 | 182.6 | 20 | 49.9 | 2 | 44.6 | 16.3 |
| migration | 4 | 63.8 | 1673.1 | 24 | 444.9 | 48 | 66.2 | 2 | 66.5 | 16.5 |
| migration | 5 | 115.0 | 6630.2 | 48 | 948.6 | 112 | 78.6 | 2 | 93.9 | 16.3 |
| migration | 6 | 125.7 | 27572.2 | 96 | 2231.6 | 256 | 108.1 | 2 | 130.6 | 16.8 |

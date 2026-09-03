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
| corpus | book_flight_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 16.8 |
| corpus | budget_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 14.6 |
| corpus | detour_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 4.4 |
| corpus | choice_informed_ok | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 5.2 |
| corpus | hallucinated_email | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 6.3 |
| corpus | no_establisher | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 6.5 |
| corpus | over_budget | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 13.9 |
| corpus | blocked_precondition | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 4.5 |
| corpus | deadlock_unobserved | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 6.9 |
| corpus | missing_tool_chain | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 4.3 |
| corpus | spurious_payload | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 22.7 |
| corpus | spurious_intent | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 2.4 |
| corpus | recursion_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 4.2 |
| corpus | two_goals_one_missing | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 1.9 |
| corpus | choice_one_branch_ok | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 5.0 |
| corpus_extended | retry_loop_ok | 1 | 1 | – | ≥5 | 4 | 0 | 0 | – | 35 | 9.8 |
| corpus_extended | spin_forever | 0 | 1 | – | ≥5 | 0 | 0 | 0 | – | 18 | 4.5 |
| corpus_extended | spawn_helpers | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| corpus_extended | spawn_with_ghost_tool | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| corpus_extended | nonconformant_handler | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 7.2 |
| corpus_extended | conformant_tolerant_handler | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 4.8 |
| severity_benchmark | booking_fastpath | 1 | 0 | purchase | 0 | 1 | 0 | 1 | purchase | 9 | 5.8 |
| severity_benchmark | booking_reordered | 1 | 0 | purchase | ≥5 | 2 | 0 | 0 | – | 15 | 7.0 |
| severity_benchmark | booking_narrowed | 1 | 0 | purchase | ≥5 | 1 | 0 | 0 | – | 10 | 4.8 |
| severity_benchmark | migration_backup | 2 | 0 | drop_old | 1 | 3 | 1 | 2 | drop_old | 26 | 19.7 |
| severity_benchmark | email_campaign | 1 | 0 | send | 0 | 1 | 0 | 1 | send | 9 | 7.1 |
| severity_benchmark | email_campaign_guarded | 1 | 0 | send | ≥5 | 2 | 0 | 0 | – | 15 | 7.9 |
| severity_benchmark | deploy_with_rollback | 1 | 0 | – | ≥5 | 1 | 1 | 0 | – | 15 | 10.8 |
| severity_benchmark | deploy_no_rollback | 1 | 0 | deploy | 0 | 1 | 0 | 1 | deploy | 9 | 9.3 |
| severity_benchmark | file_cleanup | 1 | 0 | delete | 0 | 1 | 0 | 1 | delete | 9 | 5.7 |
| severity_benchmark | order_fulfilment | 3 | 0 | ship | 0 | 1 | 0 | 1 | ship | 15 | 13.3 |
| severity_benchmark | retry_then_purge | 2 | 1 | purge | 0 | 6 | 0 | 2 | purge | 32 | 9.6 |
| severity_benchmark | shipping_detour | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 8.6 |
| severity_benchmark | claim_eligible | 1 | 0 | refund | ≥5 | 1 | 1 | 0 | – | 15 | 13.9 |
| severity_benchmark | claim_ineligible | 1 | 0 | refund | 0 | 1 | 0 | 1 | refund | 8 | 5.6 |
| severity_benchmark | staged_commit | 3 | 0 | commit | 1 | 3 | 4 | 7 | commit | 49 | 29.1 |
| severity_benchmark | release_with_audit | 1 | 0 | deploy | 0 | 1 | 0 | 1 | deploy | 9 | 10.1 |
| severity_benchmark | release_with_cache | 1 | 0 | deploy | 0 | 1 | 0 | 1 | deploy | 9 | 10.4 |
| real_skills | algorithmic-art | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | brand-guidelines | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | canvas-design | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | claude-api | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 25.3 |
| real_skills | doc-coauthoring | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 9.4 |
| real_skills | docx | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 9.8 |
| real_skills | frontend-design | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | internal-comms | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | mcp-builder | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | pdf | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 8.2 |
| real_skills | pptx | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 13.1 |
| real_skills | skill-creator | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 7.6 |
| real_skills | slack-gif-creator | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 2.3 |
| real_skills | theme-factory | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | web-artifacts-builder | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 4.1 |
| real_skills | webapp-testing | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 5.9 |
| real_skills | xlsx | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 5.7 |

## Modularity experiment (k=2). Chains G;...;G of a benchmark segment. Whole-system re-derives goal reachability over the entire remaining chain at every branch; modular types each segment against its own goal at the incoming interface (TC_seq). Re-check: last segment replaced by its unsafe variant.

| family | n | whole (hazard, short-circuit) ms | whole (complete) ms | whole exits | modular concrete ms | concrete interface | modular projected ms | projected interface | re-check whole ms | re-check modular ms |
|---|---|---|---|---|---|---|---|---|---|---|
| deploy | 1 | 5.0 | 4.2 | 2 | 4.2 | 2 | 4.2 | 2 | 5.2 | 5.3 |
| deploy | 2 | 16.4 | 16.0 | 4 | 12.0 | 4 | 9.9 | 3 | 9.1 | 6.6 |
| deploy | 3 | 43.5 | 43.7 | 4 | 29.3 | 7 | 20.0 | 3 | 15.5 | 8.7 |
| deploy | 4 | 100.7 | 100.7 | 4 | 56.2 | 11 | 23.8 | 3 | 19.8 | 8.0 |
| deploy | 5 | 227.8 | 213.4 | 4 | 91.8 | 16 | 29.7 | 3 | 26.5 | 7.7 |
| deploy | 6 | 452.5 | 450.2 | 4 | 152.4 | 22 | 37.4 | 3 | 35.0 | 7.6 |
| migration | 1 | 10.8 | 11.4 | 3 | 11.3 | 3 | 11.3 | 2 | 10.4 | 11.6 |
| migration | 2 | 20.8 | 69.4 | 6 | 42.7 | 8 | 24.2 | 2 | 19.6 | 13.2 |
| migration | 3 | 35.1 | 303.9 | 12 | 122.1 | 20 | 37.3 | 2 | 34.6 | 14.4 |
| migration | 4 | 93.6 | 1256.3 | 24 | 310.8 | 48 | 52.1 | 2 | 52.9 | 13.7 |
| migration | 5 | 78.1 | 5239.7 | 48 | 758.9 | 112 | 65.2 | 2 | 77.2 | 13.3 |
| migration | 6 | 102.4 | 20906.9 | 96 | 1626.9 | 256 | 63.1 | 2 | 82.3 | 12.2 |

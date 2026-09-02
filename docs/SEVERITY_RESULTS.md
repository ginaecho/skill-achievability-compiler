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
| corpus | book_flight_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 26.0 |
| corpus | budget_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 19.0 |
| corpus | detour_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 6.5 |
| corpus | choice_informed_ok | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 7.6 |
| corpus | hallucinated_email | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 8.9 |
| corpus | no_establisher | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 9.3 |
| corpus | over_budget | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 19.2 |
| corpus | blocked_precondition | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 7.6 |
| corpus | deadlock_unobserved | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 11.3 |
| corpus | missing_tool_chain | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 6.0 |
| corpus | spurious_payload | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 29.6 |
| corpus | spurious_intent | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 3.4 |
| corpus | recursion_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 6.3 |
| corpus | two_goals_one_missing | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 3.4 |
| corpus | choice_one_branch_ok | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 7.8 |
| corpus_extended | retry_loop_ok | 1 | 1 | – | ≥5 | 4 | 0 | 0 | – | 35 | 14.2 |
| corpus_extended | spin_forever | 0 | 1 | – | ≥5 | 0 | 0 | 0 | – | 18 | 7.0 |
| corpus_extended | spawn_helpers | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| corpus_extended | spawn_with_ghost_tool | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| corpus_extended | nonconformant_handler | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 8.5 |
| corpus_extended | conformant_tolerant_handler | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 9.3 |
| severity_benchmark | booking_fastpath | 1 | 0 | purchase | 0 | 1 | 0 | 1 | purchase | 9 | 9.5 |
| severity_benchmark | booking_reordered | 1 | 0 | purchase | ≥5 | 2 | 0 | 0 | – | 15 | 12.6 |
| severity_benchmark | booking_narrowed | 1 | 0 | purchase | ≥5 | 1 | 0 | 0 | – | 10 | 8.8 |
| severity_benchmark | migration_backup | 2 | 0 | drop_old | 1 | 3 | 1 | 2 | drop_old | 26 | 43.7 |
| severity_benchmark | email_campaign | 1 | 0 | send | 0 | 1 | 0 | 1 | send | 9 | 16.0 |
| severity_benchmark | email_campaign_guarded | 1 | 0 | send | ≥5 | 2 | 0 | 0 | – | 15 | 18.7 |
| severity_benchmark | deploy_with_rollback | 1 | 0 | – | ≥5 | 1 | 1 | 0 | – | 15 | 21.9 |
| severity_benchmark | deploy_no_rollback | 1 | 0 | deploy | 0 | 1 | 0 | 1 | deploy | 9 | 12.8 |
| severity_benchmark | file_cleanup | 1 | 0 | delete | 0 | 1 | 0 | 1 | delete | 9 | 8.6 |
| severity_benchmark | order_fulfilment | 3 | 0 | ship | 0 | 1 | 0 | 1 | ship | 15 | 21.7 |
| severity_benchmark | retry_then_purge | 2 | 1 | purge | 0 | 6 | 0 | 2 | purge | 32 | 18.3 |
| severity_benchmark | shipping_detour | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 16.3 |
| severity_benchmark | claim_eligible | 1 | 0 | refund | ≥5 | 1 | 1 | 0 | – | 15 | 28.1 |
| severity_benchmark | claim_ineligible | 1 | 0 | refund | 0 | 1 | 0 | 1 | refund | 8 | 9.6 |
| severity_benchmark | staged_commit | 3 | 0 | commit | 1 | 3 | 4 | 7 | commit | 49 | 52.3 |
| severity_benchmark | release_with_audit | 1 | 0 | deploy | 0 | 1 | 0 | 1 | deploy | 9 | 16.5 |
| severity_benchmark | release_with_cache | 1 | 0 | deploy | 0 | 1 | 0 | 1 | deploy | 9 | 17.5 |
| real_skills | algorithmic-art | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | brand-guidelines | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | canvas-design | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | claude-api | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 39.9 |
| real_skills | doc-coauthoring | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 16.6 |
| real_skills | docx | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 6.1 |
| real_skills | frontend-design | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | internal-comms | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | mcp-builder | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | pdf | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | pptx | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 6.2 |
| real_skills | skill-creator | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 3.0 |
| real_skills | slack-gif-creator | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | theme-factory | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.1 |
| real_skills | web-artifacts-builder | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | webapp-testing | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | xlsx | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 6.3 |

## Modularity experiment (k=2). Chains G;...;G of a benchmark segment. Whole-system re-derives goal reachability over the entire remaining chain at every branch; modular types each segment against its own goal at the incoming interface (TC_seq). Re-check: last segment replaced by its unsafe variant.

| family | n | whole (hazard, short-circuit) ms | whole (complete) ms | whole exits | modular concrete ms | concrete interface | modular projected ms | projected interface | re-check whole ms | re-check modular ms |
|---|---|---|---|---|---|---|---|---|---|---|
| deploy | 1 | 7.3 | 6.8 | 2 | 6.6 | 2 | 6.4 | 2 | 8.1 | 8.5 |
| deploy | 2 | 28.8 | 27.7 | 4 | 19.7 | 4 | 17.5 | 3 | 17.7 | 10.7 |
| deploy | 3 | 67.9 | 68.3 | 4 | 45.4 | 7 | 26.9 | 3 | 21.5 | 12.1 |
| deploy | 4 | 166.9 | 165.3 | 4 | 90.3 | 11 | 38.7 | 3 | 32.3 | 13.1 |
| deploy | 5 | 359.1 | 367.9 | 4 | 163.5 | 16 | 58.4 | 3 | 46.2 | 13.1 |
| deploy | 6 | 783.2 | 734.8 | 4 | 251.3 | 22 | 65.8 | 3 | 57.3 | 13.9 |
| migration | 1 | 16.8 | 19.2 | 3 | 19.2 | 3 | 19.2 | 2 | 18.7 | 19.2 |
| migration | 2 | 33.5 | 111.3 | 6 | 68.7 | 8 | 40.5 | 2 | 32.5 | 22.4 |
| migration | 3 | 58.2 | 482.1 | 12 | 191.1 | 20 | 60.0 | 2 | 53.9 | 22.1 |
| migration | 4 | 82.2 | 2016.9 | 24 | 496.6 | 48 | 91.8 | 2 | 86.5 | 21.0 |
| migration | 5 | 116.7 | 8411.6 | 48 | 1191.7 | 112 | 104.0 | 2 | 124.4 | 22.3 |
| migration | 6 | 168.2 | 37499.1 | 96 | 2881.4 | 256 | 126.6 | 2 | 211.6 | 21.1 |

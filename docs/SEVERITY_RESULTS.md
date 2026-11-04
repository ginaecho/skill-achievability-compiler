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
| corpus | book_flight_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 30.9 |
| corpus | budget_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 29.9 |
| corpus | detour_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 11.3 |
| corpus | choice_informed_ok | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 11.9 |
| corpus | hallucinated_email | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 14.6 |
| corpus | no_establisher | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 12.1 |
| corpus | over_budget | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 21.9 |
| corpus | blocked_precondition | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 8.7 |
| corpus | deadlock_unobserved | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 13.4 |
| corpus | missing_tool_chain | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 7.8 |
| corpus | spurious_payload | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 36.8 |
| corpus | spurious_intent | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 9.4 |
| corpus | recursion_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 8.7 |
| corpus | two_goals_one_missing | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 6.5 |
| corpus | choice_one_branch_ok | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 16.4 |
| corpus_extended | retry_loop_ok | 1 | 1 | – | ≥5 | 4 | 0 | 0 | – | 35 | 29.0 |
| corpus_extended | spin_forever | 0 | 1 | – | ≥5 | 0 | 0 | 0 | – | 18 | 14.8 |
| corpus_extended | spawn_helpers | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| corpus_extended | spawn_with_ghost_tool | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| corpus_extended | nonconformant_handler | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 10.7 |
| corpus_extended | conformant_tolerant_handler | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 9.0 |
| severity_benchmark | booking_fastpath | 1 | 0 | purchase | 0 | 1 | 0 | 1 | purchase | 9 | 10.5 |
| severity_benchmark | booking_reordered | 1 | 0 | purchase | ≥5 | 2 | 0 | 0 | – | 15 | 13.6 |
| severity_benchmark | booking_narrowed | 1 | 0 | purchase | ≥5 | 1 | 0 | 0 | – | 10 | 9.1 |
| severity_benchmark | migration_backup | 2 | 0 | drop_old | 1 | 3 | 1 | 2 | drop_old | 26 | 36.7 |
| severity_benchmark | email_campaign | 1 | 0 | send | 0 | 1 | 0 | 1 | send | 9 | 12.5 |
| severity_benchmark | email_campaign_guarded | 1 | 0 | send | ≥5 | 2 | 0 | 0 | – | 15 | 19.5 |
| severity_benchmark | deploy_with_rollback | 1 | 0 | – | ≥5 | 1 | 1 | 0 | – | 15 | 33.0 |
| severity_benchmark | deploy_no_rollback | 1 | 0 | deploy | 0 | 1 | 0 | 1 | deploy | 9 | 24.0 |
| severity_benchmark | file_cleanup | 1 | 0 | delete | 0 | 1 | 0 | 1 | delete | 9 | 16.1 |
| severity_benchmark | order_fulfilment | 3 | 0 | ship | 0 | 1 | 0 | 1 | ship | 15 | 37.0 |
| severity_benchmark | retry_then_purge | 2 | 1 | purge | 0 | 6 | 0 | 2 | purge | 32 | 32.5 |
| severity_benchmark | shipping_detour | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 26.1 |
| severity_benchmark | claim_eligible | 1 | 0 | refund | ≥5 | 1 | 1 | 0 | – | 15 | 42.5 |
| severity_benchmark | claim_ineligible | 1 | 0 | refund | 0 | 1 | 0 | 1 | refund | 8 | 15.6 |
| severity_benchmark | staged_commit | 3 | 0 | commit | 1 | 3 | 4 | 7 | commit | 49 | 86.2 |
| severity_benchmark | release_with_audit | 1 | 0 | deploy | 0 | 1 | 0 | 1 | deploy | 9 | 29.0 |
| severity_benchmark | release_with_cache | 1 | 0 | deploy | 0 | 1 | 0 | 1 | deploy | 9 | 26.2 |
| real_skills | algorithmic-art | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | brand-guidelines | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | canvas-design | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | claude-api | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 35.0 |
| real_skills | doc-coauthoring | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 18.7 |
| real_skills | docx | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 23.6 |
| real_skills | frontend-design | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | internal-comms | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | mcp-builder | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | pdf | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 33.9 |
| real_skills | pptx | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 38.3 |
| real_skills | skill-creator | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 22.2 |
| real_skills | slack-gif-creator | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 4.5 |
| real_skills | theme-factory | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | web-artifacts-builder | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 9.5 |
| real_skills | webapp-testing | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 13.5 |
| real_skills | xlsx | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 14.5 |

## Modularity experiment (k=2). Chains G;...;G of a benchmark segment. Whole-system re-derives goal reachability over the entire remaining chain at every branch; modular types each segment against its own goal at the incoming interface (TC_seq). Re-check: last segment replaced by its unsafe variant.

| family | n | whole (hazard, short-circuit) ms | whole (complete) ms | whole exits | modular concrete ms | concrete interface | modular projected ms | projected interface | re-check whole ms | re-check modular ms |
|---|---|---|---|---|---|---|---|---|---|---|
| deploy | 1 | 9.7 | 8.7 | 2 | 8.3 | 2 | 7.8 | 2 | 9.8 | 9.1 |
| deploy | 2 | 40.9 | 53.4 | 4 | 24.1 | 4 | 20.1 | 3 | 29.6 | 16.1 |
| deploy | 3 | 104.9 | 103.5 | 4 | 59.2 | 7 | 43.5 | 3 | 42.5 | 26.2 |
| deploy | 4 | 208.8 | 271.8 | 4 | 138.4 | 11 | 65.4 | 3 | 53.0 | 23.0 |
| deploy | 5 | 462.9 | 440.4 | 4 | 214.3 | 16 | 73.6 | 3 | 53.9 | 14.3 |
| deploy | 6 | 1048.5 | 1092.2 | 4 | 372.2 | 22 | 106.7 | 3 | 112.9 | 24.1 |
| migration | 1 | 38.1 | 23.4 | 3 | 29.0 | 3 | 28.4 | 2 | 32.3 | 36.7 |
| migration | 2 | 60.5 | 180.4 | 6 | 127.8 | 8 | 54.3 | 2 | 39.0 | 27.5 |
| migration | 3 | 80.4 | 847.8 | 12 | 320.3 | 20 | 98.6 | 2 | 96.2 | 25.2 |
| migration | 4 | 102.3 | 3334.7 | 24 | 607.5 | 48 | 111.4 | 2 | 130.5 | 24.9 |
| migration | 5 | 133.5 | 14335.9 | 48 | 2262.3 | 112 | 214.4 | 2 | 206.1 | 29.4 |
| migration | 6 | 284.7 | 53743.4 | 96 | 3906.9 | 256 | 173.0 | 2 | 237.8 | 24.3 |

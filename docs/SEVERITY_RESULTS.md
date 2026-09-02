# Severity evaluation results

kmax tested = 4 (k* = ≥5 means no hazard within 4 misselections).

## Summary per corpus

| corpus | packs | with choices | with irreversible tools | k* distribution |
|---|---|---|---|---|
| corpus | 15 | 3 | 0 | {'≥5': 15} |
| corpus_extended | 6 | 3 | 0 | {'≥5': 6} |
| severity_benchmark | 15 | 15 | 13 | {'0': 7, '≥5': 6, '1': 2} |
| real_skills | 0 | 0 | 0 | {} |

## Per-pack results

| set | pack | choices | loops | irreversible | k* | Benign | Futile | Catastrophic | PNR action | configs | ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| corpus | book_flight_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 31.6 |
| corpus | budget_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 20.7 |
| corpus | detour_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 7.7 |
| corpus | choice_informed_ok | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 10.3 |
| corpus | hallucinated_email | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 10.8 |
| corpus | no_establisher | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 11.0 |
| corpus | over_budget | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 18.6 |
| corpus | blocked_precondition | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 7.6 |
| corpus | deadlock_unobserved | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 13.5 |
| corpus | missing_tool_chain | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 7.0 |
| corpus | spurious_payload | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 30.0 |
| corpus | spurious_intent | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 3.6 |
| corpus | recursion_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 7.5 |
| corpus | two_goals_one_missing | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 3.4 |
| corpus | choice_one_branch_ok | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 8.7 |
| corpus_extended | retry_loop_ok | 1 | 1 | – | ≥5 | 4 | 0 | 0 | – | 35 | 15.6 |
| corpus_extended | spin_forever | 0 | 1 | – | ≥5 | 0 | 0 | 0 | – | 18 | 7.0 |
| corpus_extended | spawn_helpers | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| corpus_extended | spawn_with_ghost_tool | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| corpus_extended | nonconformant_handler | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 9.1 |
| corpus_extended | conformant_tolerant_handler | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 8.6 |
| severity_benchmark | booking_fastpath | 1 | 0 | purchase | 0 | 1 | 0 | 1 | purchase | 9 | 9.7 |
| severity_benchmark | booking_reordered | 1 | 0 | purchase | ≥5 | 2 | 0 | 0 | – | 15 | 13.2 |
| severity_benchmark | booking_narrowed | 1 | 0 | purchase | ≥5 | 1 | 0 | 0 | – | 10 | 8.4 |
| severity_benchmark | migration_backup | 2 | 0 | drop_old | 1 | 3 | 0 | 2 | drop_old | 24 | 32.9 |
| severity_benchmark | email_campaign | 1 | 0 | send | 0 | 1 | 0 | 1 | send | 9 | 11.6 |
| severity_benchmark | email_campaign_guarded | 1 | 0 | send | ≥5 | 2 | 0 | 0 | – | 15 | 13.8 |
| severity_benchmark | deploy_with_rollback | 1 | 0 | – | ≥5 | 1 | 1 | 0 | – | 15 | 18.3 |
| severity_benchmark | deploy_no_rollback | 1 | 0 | deploy | 0 | 1 | 0 | 1 | deploy | 9 | 14.5 |
| severity_benchmark | file_cleanup | 1 | 0 | delete | 0 | 1 | 0 | 1 | delete | 9 | 12.0 |
| severity_benchmark | order_fulfilment | 3 | 0 | ship | 0 | 1 | 0 | 1 | ship | 15 | 29.7 |
| severity_benchmark | retry_then_purge | 2 | 1 | purge | 0 | 6 | 0 | 1 | purge | 30 | 18.3 |
| severity_benchmark | shipping_detour | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 18.2 |
| severity_benchmark | claim_eligible | 1 | 0 | refund | ≥5 | 1 | 1 | 0 | – | 15 | 31.1 |
| severity_benchmark | claim_ineligible | 1 | 0 | refund | 0 | 0 | 0 | 1 | refund | 7 | 9.7 |
| severity_benchmark | staged_commit | 3 | 0 | commit | 1 | 3 | 1 | 2 | commit | 29 | 42.9 |

## Modularity experiment (k=2). Chains G;...;G of a benchmark segment. Whole-system re-derives goal reachability over the entire remaining chain at every branch; modular types each segment against its own goal at the incoming interface (TC_seq). Re-check: last segment replaced by its unsafe variant.

| family | n | whole (hazard, short-circuit) ms | whole (complete) ms | whole exits | modular concrete ms | concrete interface | modular projected ms | projected interface | re-check whole ms | re-check modular ms |
|---|---|---|---|---|---|---|---|---|---|---|
| deploy | 1 | 8.2 | 8.5 | 2 | 8.8 | 2 | 10.1 | 2 | 11.9 | 11.5 |
| deploy | 2 | 35.2 | 36.9 | 4 | 24.5 | 4 | 18.6 | 3 | 17.0 | 12.5 |
| deploy | 3 | 95.0 | 127.2 | 4 | 85.1 | 7 | 50.3 | 3 | 39.4 | 15.1 |
| deploy | 4 | 197.7 | 237.8 | 4 | 117.8 | 11 | 47.1 | 3 | 35.9 | 13.7 |
| deploy | 5 | 395.7 | 417.2 | 4 | 180.0 | 16 | 62.8 | 3 | 52.4 | 16.0 |
| deploy | 6 | 882.6 | 940.9 | 4 | 329.5 | 22 | 76.0 | 3 | 73.5 | 13.2 |
| migration | 1 | 19.4 | 20.7 | 3 | 22.5 | 3 | 21.6 | 2 | 17.9 | 21.2 |
| migration | 2 | 40.9 | 127.3 | 6 | 120.5 | 8 | 71.3 | 2 | 58.4 | 38.0 |
| migration | 3 | 94.7 | 693.0 | 12 | 225.3 | 20 | 71.0 | 2 | 66.6 | 40.7 |
| migration | 4 | 138.6 | 2306.9 | 24 | 531.7 | 48 | 89.2 | 2 | 93.1 | 23.4 |
| migration | 5 | 127.4 | 9880.2 | 48 | 1541.3 | 112 | 115.9 | 2 | 127.1 | 24.8 |
| migration | 6 | 199.6 | 38134.4 | 96 | 3322.2 | 256 | 140.0 | 2 | 176.1 | 23.1 |

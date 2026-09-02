# Severity evaluation results

kmax tested = 4 (k* = ≥5 means no hazard within 4 misselections).

## Summary per corpus

| corpus | packs | with choices | with irreversible tools | k* distribution |
|---|---|---|---|---|
| corpus | 15 | 3 | 0 | {'≥5': 15} |
| corpus_extended | 6 | 3 | 0 | {'≥5': 6} |
| severity_benchmark | 17 | 17 | 15 | {'0': 9, '≥5': 6, '1': 2} |
| real_skills | 0 | 0 | 0 | {} |

## Per-pack results

| set | pack | choices | loops | irreversible | k* | Benign | Futile | Catastrophic | PNR action | configs | ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| corpus | book_flight_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 24.2 |
| corpus | budget_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 19.4 |
| corpus | detour_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 7.5 |
| corpus | choice_informed_ok | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 10.3 |
| corpus | hallucinated_email | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 15.5 |
| corpus | no_establisher | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 11.6 |
| corpus | over_budget | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 20.3 |
| corpus | blocked_precondition | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 8.0 |
| corpus | deadlock_unobserved | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 13.2 |
| corpus | missing_tool_chain | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 8.0 |
| corpus | spurious_payload | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 31.6 |
| corpus | spurious_intent | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 3.9 |
| corpus | recursion_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 8.2 |
| corpus | two_goals_one_missing | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 4.1 |
| corpus | choice_one_branch_ok | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 10.4 |
| corpus_extended | retry_loop_ok | 1 | 1 | – | ≥5 | 4 | 0 | 0 | – | 35 | 26.2 |
| corpus_extended | spin_forever | 0 | 1 | – | ≥5 | 0 | 0 | 0 | – | 18 | 12.7 |
| corpus_extended | spawn_helpers | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| corpus_extended | spawn_with_ghost_tool | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| corpus_extended | nonconformant_handler | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 16.1 |
| corpus_extended | conformant_tolerant_handler | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 14.4 |
| severity_benchmark | booking_fastpath | 1 | 0 | purchase | 0 | 1 | 0 | 1 | purchase | 9 | 17.0 |
| severity_benchmark | booking_reordered | 1 | 0 | purchase | ≥5 | 2 | 0 | 0 | – | 15 | 22.2 |
| severity_benchmark | booking_narrowed | 1 | 0 | purchase | ≥5 | 1 | 0 | 0 | – | 10 | 16.1 |
| severity_benchmark | migration_backup | 2 | 0 | drop_old | 1 | 3 | 1 | 2 | drop_old | 26 | 59.0 |
| severity_benchmark | email_campaign | 1 | 0 | send | 0 | 1 | 0 | 1 | send | 9 | 19.3 |
| severity_benchmark | email_campaign_guarded | 1 | 0 | send | ≥5 | 2 | 0 | 0 | – | 15 | 18.8 |
| severity_benchmark | deploy_with_rollback | 1 | 0 | – | ≥5 | 1 | 1 | 0 | – | 15 | 27.4 |
| severity_benchmark | deploy_no_rollback | 1 | 0 | deploy | 0 | 1 | 0 | 1 | deploy | 9 | 17.1 |
| severity_benchmark | file_cleanup | 1 | 0 | delete | 0 | 1 | 0 | 1 | delete | 9 | 13.5 |
| severity_benchmark | order_fulfilment | 3 | 0 | ship | 0 | 1 | 0 | 1 | ship | 15 | 30.0 |
| severity_benchmark | retry_then_purge | 2 | 1 | purge | 0 | 6 | 0 | 2 | purge | 32 | 22.6 |
| severity_benchmark | shipping_detour | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 21.2 |
| severity_benchmark | claim_eligible | 1 | 0 | refund | ≥5 | 1 | 1 | 0 | – | 15 | 33.4 |
| severity_benchmark | claim_ineligible | 1 | 0 | refund | 0 | 1 | 0 | 1 | refund | 8 | 10.8 |
| severity_benchmark | staged_commit | 3 | 0 | commit | 1 | 3 | 4 | 7 | commit | 49 | 58.9 |
| severity_benchmark | release_with_audit | 1 | 0 | deploy | 0 | 1 | 0 | 1 | deploy | 9 | 19.8 |
| severity_benchmark | release_with_cache | 1 | 0 | deploy | 0 | 1 | 0 | 1 | deploy | 9 | 18.7 |

## Modularity experiment (k=2). Chains G;...;G of a benchmark segment. Whole-system re-derives goal reachability over the entire remaining chain at every branch; modular types each segment against its own goal at the incoming interface (TC_seq). Re-check: last segment replaced by its unsafe variant.

| family | n | whole (hazard, short-circuit) ms | whole (complete) ms | whole exits | modular concrete ms | concrete interface | modular projected ms | projected interface | re-check whole ms | re-check modular ms |
|---|---|---|---|---|---|---|---|---|---|---|
| deploy | 1 | 7.4 | 7.5 | 2 | 7.5 | 2 | 7.4 | 2 | 9.5 | 9.1 |
| deploy | 2 | 28.3 | 34.5 | 4 | 23.6 | 4 | 19.7 | 3 | 17.7 | 14.7 |
| deploy | 3 | 78.6 | 74.2 | 4 | 51.0 | 7 | 30.6 | 3 | 24.6 | 14.5 |
| deploy | 4 | 182.4 | 183.0 | 4 | 98.4 | 11 | 41.1 | 3 | 32.9 | 12.9 |
| deploy | 5 | 374.2 | 447.8 | 4 | 174.8 | 16 | 57.3 | 3 | 61.8 | 13.4 |
| deploy | 6 | 743.4 | 791.3 | 4 | 327.6 | 22 | 80.6 | 3 | 61.4 | 13.9 |
| migration | 1 | 19.1 | 20.3 | 3 | 20.8 | 3 | 21.4 | 2 | 19.3 | 21.6 |
| migration | 2 | 34.6 | 124.7 | 6 | 73.0 | 8 | 41.4 | 2 | 34.5 | 24.7 |
| migration | 3 | 60.9 | 563.1 | 12 | 219.8 | 20 | 70.4 | 2 | 58.6 | 23.2 |
| migration | 4 | 94.3 | 2165.1 | 24 | 586.0 | 48 | 93.9 | 2 | 93.2 | 24.5 |
| migration | 5 | 132.5 | 8894.3 | 48 | 1409.8 | 112 | 127.9 | 2 | 140.6 | 25.5 |
| migration | 6 | 184.1 | 36184.9 | 96 | 3365.9 | 256 | 149.1 | 2 | 182.2 | 24.6 |

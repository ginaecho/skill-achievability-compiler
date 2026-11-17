# Severity evaluation results

kmax tested = 4 (k* = ≥5 means no hazard within 4 misselections).

## Summary per corpus

| corpus | packs | with choices | with irreversible tools | k* distribution |
|---|---|---|---|---|
| corpus | 15 | 3 | 0 | {'≥5': 15} |
| corpus_extended | 6 | 3 | 0 | {'≥5': 6} |
| severity_benchmark | 17 | 17 | 15 | {'0': 9, '≥5': 6, '1': 2} |
| severity_real | 6 | 6 | 6 | {'0': 6} |
| real_skills | 17 | 0 | 0 | {'≥5': 17} |

## Per-pack results

| set | pack | choices | loops | irreversible | k* | Benign | Futile | Catastrophic | PNR action | configs | ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| corpus | book_flight_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 19.2 |
| corpus | budget_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 17.8 |
| corpus | detour_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 7.5 |
| corpus | choice_informed_ok | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 8.4 |
| corpus | hallucinated_email | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 8.9 |
| corpus | no_establisher | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 8.5 |
| corpus | over_budget | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 15.4 |
| corpus | blocked_precondition | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 6.7 |
| corpus | deadlock_unobserved | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 11.5 |
| corpus | missing_tool_chain | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 5.8 |
| corpus | spurious_payload | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 24.0 |
| corpus | spurious_intent | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 2.9 |
| corpus | recursion_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 5.5 |
| corpus | two_goals_one_missing | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 3.2 |
| corpus | choice_one_branch_ok | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 7.8 |
| corpus_extended | retry_loop_ok | 1 | 1 | – | ≥5 | 4 | 0 | 0 | – | 35 | 14.0 |
| corpus_extended | spin_forever | 0 | 1 | – | ≥5 | 0 | 0 | 0 | – | 18 | 5.9 |
| corpus_extended | spawn_helpers | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| corpus_extended | spawn_with_ghost_tool | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| corpus_extended | nonconformant_handler | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 8.4 |
| corpus_extended | conformant_tolerant_handler | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 8.8 |
| severity_benchmark | booking_fastpath | 1 | 0 | purchase | 0 | 1 | 0 | 1 | purchase | 9 | 10.5 |
| severity_benchmark | booking_reordered | 1 | 0 | purchase | ≥5 | 2 | 0 | 0 | – | 15 | 11.3 |
| severity_benchmark | booking_narrowed | 1 | 0 | purchase | ≥5 | 1 | 0 | 0 | – | 10 | 8.2 |
| severity_benchmark | migration_backup | 2 | 0 | drop_old | 1 | 3 | 1 | 2 | drop_old | 26 | 35.0 |
| severity_benchmark | email_campaign | 1 | 0 | send | 0 | 1 | 0 | 1 | send | 9 | 11.2 |
| severity_benchmark | email_campaign_guarded | 1 | 0 | send | ≥5 | 2 | 0 | 0 | – | 15 | 12.3 |
| severity_benchmark | deploy_with_rollback | 1 | 0 | – | ≥5 | 1 | 1 | 0 | – | 15 | 23.9 |
| severity_benchmark | deploy_no_rollback | 1 | 0 | deploy | 0 | 1 | 0 | 1 | deploy | 9 | 27.7 |
| severity_benchmark | file_cleanup | 1 | 0 | delete | 0 | 1 | 0 | 1 | delete | 9 | 9.8 |
| severity_benchmark | order_fulfilment | 3 | 0 | ship | 0 | 1 | 0 | 1 | ship | 15 | 27.1 |
| severity_benchmark | retry_then_purge | 2 | 1 | purge | 0 | 6 | 0 | 2 | purge | 32 | 18.3 |
| severity_benchmark | shipping_detour | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 14.4 |
| severity_benchmark | claim_eligible | 1 | 0 | refund | ≥5 | 1 | 1 | 0 | – | 15 | 22.1 |
| severity_benchmark | claim_ineligible | 1 | 0 | refund | 0 | 1 | 0 | 1 | refund | 8 | 9.6 |
| severity_benchmark | staged_commit | 3 | 0 | commit | 1 | 3 | 4 | 7 | commit | 49 | 67.4 |
| severity_benchmark | release_with_audit | 1 | 0 | deploy | 0 | 1 | 0 | 1 | deploy | 9 | 24.0 |
| severity_benchmark | release_with_cache | 1 | 0 | deploy | 0 | 1 | 0 | 1 | deploy | 9 | 23.4 |
| severity_real | doc_coauthor_ship | 1 | 1 | ship | 0 | 11 | 0 | 1 | ship | 108 | 120.2 |
| severity_real | gem_dev_team | 2 | 1 | deploy | 0 | 17 | 2 | 5 | deploy | 180 | 203.0 |
| severity_real | pr_review_merge | 2 | 1 | merge | 0 | 316 | 0 | 16 | merge | 19772 | 16975.6 |
| severity_real | sdlc_release_gate | 1 | 1 | deploy | 0 | 11 | 0 | 1 | deploy | 108 | 82.2 |
| severity_real | sdlc_release_gate_concurrent | 1 | 1 | deploy | 0 | 11 | 0 | 1 | deploy | 108 | 87.0 |
| severity_real | sdlc_release_gate_concurrent_withhold | 1 | 1 | deploy | 0 | 11 | 6 | 1 | deploy | 141 | 133.5 |
| real_skills | algorithmic-art | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | brand-guidelines | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | canvas-design | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | claude-api | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 42.7 |
| real_skills | doc-coauthoring | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 17.0 |
| real_skills | docx | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 17.2 |
| real_skills | frontend-design | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | internal-comms | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | mcp-builder | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | pdf | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 13.9 |
| real_skills | pptx | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 22.0 |
| real_skills | skill-creator | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 13.5 |
| real_skills | slack-gif-creator | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 3.1 |
| real_skills | theme-factory | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | web-artifacts-builder | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 6.3 |
| real_skills | webapp-testing | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 9.6 |
| real_skills | xlsx | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 9.6 |

## Modularity experiment (k=2). Chains G;...;G of a benchmark segment. Whole-system re-derives goal reachability over the entire remaining chain at every branch; modular types each segment against its own goal at the incoming interface (TC_seq). Re-check: last segment replaced by its unsafe variant.

| family | n | whole (hazard, short-circuit) ms | whole (complete) ms | whole exits | modular concrete ms | concrete interface | modular projected ms | projected interface | re-check whole ms | re-check modular ms |
|---|---|---|---|---|---|---|---|---|---|---|
| deploy | 1 | 9.1 | 9.9 | 2 | 10.6 | 2 | 9.2 | 2 | 12.5 | 11.9 |
| deploy | 2 | 36.0 | 35.2 | 4 | 28.3 | 4 | 20.3 | 3 | 20.1 | 14.1 |
| deploy | 3 | 104.7 | 101.4 | 4 | 77.5 | 7 | 56.9 | 3 | 57.4 | 19.0 |
| deploy | 4 | 283.1 | 246.0 | 4 | 116.7 | 11 | 59.0 | 3 | 61.0 | 14.9 |
| deploy | 5 | 534.4 | 553.8 | 4 | 206.8 | 16 | 57.4 | 3 | 64.9 | 14.9 |
| deploy | 6 | 1121.1 | 1164.9 | 4 | 329.7 | 22 | 70.1 | 3 | 84.3 | 14.2 |
| migration | 1 | 22.1 | 24.5 | 3 | 24.2 | 3 | 25.8 | 2 | 23.1 | 24.0 |
| migration | 2 | 47.6 | 163.3 | 6 | 91.0 | 8 | 52.1 | 2 | 47.2 | 27.2 |
| migration | 3 | 83.2 | 786.1 | 12 | 244.0 | 20 | 74.6 | 2 | 79.2 | 25.1 |
| migration | 4 | 128.3 | 3219.4 | 24 | 760.1 | 48 | 119.0 | 2 | 145.2 | 30.7 |
| migration | 5 | 206.5 | 13171.3 | 48 | 1708.1 | 112 | 146.8 | 2 | 258.6 | 26.8 |
| migration | 6 | 279.2 | 53526.9 | 96 | 3996.4 | 256 | 174.3 | 2 | 311.1 | 32.7 |

## Real-protocol group (benchmarks/severity_real)

Protocols ported from public multi-role skill repositories; expectations were committed before the tool ran (see benchmarks/severity_real/README.md). Counts are per branch and abstract world, as above; the misselection columns exclude branches the guard marks intended.

| pack | acting roles | k* | misselections: Benign | Futile | Catastrophic | bystander pairs | bystander exact |
|---|---|---|---|---|---|---|---|
| doc_coauthor_ship | 3 | 0 | 5 | 0 | 1 | 0 | True |
| gem_dev_team | 6 | 0 | 5 | 2 | 5 | 0 | True |
| pr_review_merge | 2 | 0 | 150 | 0 | 16 | 0 | True |
| sdlc_release_gate | 2 | 0 | 5 | 0 | 1 | 0 | True |
| sdlc_release_gate_concurrent | 2 | 0 | 5 | 0 | 1 | 0 | True |
| sdlc_release_gate_concurrent_withhold | 2 | 0 | 5 | 6 | 1 | 0 | True |

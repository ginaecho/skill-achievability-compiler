# Severity evaluation results

kmax tested = 4 (k* = ≥5 means no hazard within 4 misselections).

## Summary per corpus

| corpus | packs | with choices | with irreversible tools | k* distribution |
|---|---|---|---|---|
| corpus | 15 | 3 | 0 | {'≥5': 15} |
| corpus_extended | 6 | 3 | 0 | {'≥5': 6} |
| severity_benchmark | 17 | 17 | 15 | {'0': 9, '≥5': 6, '1': 2} |
| severity_real | 18 | 18 | 18 | {'0': 18} |
| real_skills | 17 | 0 | 0 | {'≥5': 17} |

## Per-pack results

| set | pack | choices | loops | irreversible | k* | Benign | Futile | Catastrophic | PNR action | configs | ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| corpus | book_flight_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 21.9 |
| corpus | budget_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 16.4 |
| corpus | detour_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 6.3 |
| corpus | choice_informed_ok | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 10.3 |
| corpus | hallucinated_email | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 9.6 |
| corpus | no_establisher | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 9.2 |
| corpus | over_budget | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 16.4 |
| corpus | blocked_precondition | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 7.6 |
| corpus | deadlock_unobserved | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 12.0 |
| corpus | missing_tool_chain | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 5.9 |
| corpus | spurious_payload | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 25.7 |
| corpus | spurious_intent | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 3.4 |
| corpus | recursion_ok | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 6.4 |
| corpus | two_goals_one_missing | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 3.4 |
| corpus | choice_one_branch_ok | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 8.2 |
| corpus_extended | retry_loop_ok | 1 | 1 | – | ≥5 | 4 | 0 | 0 | – | 35 | 14.2 |
| corpus_extended | spin_forever | 0 | 1 | – | ≥5 | 0 | 0 | 0 | – | 18 | 5.7 |
| corpus_extended | spawn_helpers | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| corpus_extended | spawn_with_ghost_tool | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| corpus_extended | nonconformant_handler | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 9.3 |
| corpus_extended | conformant_tolerant_handler | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 8.6 |
| severity_benchmark | booking_fastpath | 1 | 0 | purchase | 0 | 1 | 0 | 1 | purchase | 9 | 10.7 |
| severity_benchmark | booking_reordered | 1 | 0 | purchase | ≥5 | 2 | 0 | 0 | – | 15 | 12.5 |
| severity_benchmark | booking_narrowed | 1 | 0 | purchase | ≥5 | 1 | 0 | 0 | – | 10 | 8.7 |
| severity_benchmark | migration_backup | 2 | 0 | drop_old | 1 | 4 | 0 | 2 | drop_old | 26 | 43.5 |
| severity_benchmark | email_campaign | 1 | 0 | send | 0 | 1 | 0 | 1 | send | 9 | 14.3 |
| severity_benchmark | email_campaign_guarded | 1 | 0 | send | ≥5 | 2 | 0 | 0 | – | 15 | 15.5 |
| severity_benchmark | deploy_with_rollback | 1 | 0 | – | ≥5 | 1 | 1 | 0 | – | 15 | 21.5 |
| severity_benchmark | deploy_no_rollback | 1 | 0 | deploy | 0 | 1 | 0 | 1 | deploy | 9 | 16.6 |
| severity_benchmark | file_cleanup | 1 | 0 | delete | 0 | 1 | 0 | 1 | delete | 9 | 10.3 |
| severity_benchmark | order_fulfilment | 3 | 0 | ship | 0 | 1 | 0 | 1 | ship | 15 | 28.7 |
| severity_benchmark | retry_then_purge | 2 | 1 | purge | 0 | 6 | 0 | 2 | purge | 32 | 18.5 |
| severity_benchmark | shipping_detour | 1 | 0 | – | ≥5 | 2 | 0 | 0 | – | 15 | 16.9 |
| severity_benchmark | claim_eligible | 1 | 0 | refund | ≥5 | 1 | 1 | 0 | – | 15 | 29.3 |
| severity_benchmark | claim_ineligible | 1 | 0 | refund | 0 | 1 | 0 | 1 | refund | 8 | 9.6 |
| severity_benchmark | staged_commit | 3 | 0 | commit | 1 | 8 | 1 | 5 | commit | 47 | 68.1 |
| severity_benchmark | release_with_audit | 1 | 0 | deploy | 0 | 1 | 0 | 1 | deploy | 9 | 23.9 |
| severity_benchmark | release_with_cache | 1 | 0 | deploy | 0 | 1 | 0 | 1 | deploy | 9 | 24.7 |
| severity_real | airline_baggage_update | 4 | 0 | update_reservation_baggages | 0 | 6 | 2 | 4 | update_reservation_baggages | 44 | 37.2 |
| severity_real | airline_book_reservation | 6 | 0 | book_reservation | 0 | 23 | 7 | 10 | book_reservation | 126 | 113.1 |
| severity_real | airline_cancel_reservation | 4 | 0 | cancel_reservation | 0 | 7 | 10 | 7 | cancel_reservation | 97 | 109.0 |
| severity_real | airline_change_cabin | 6 | 0 | change_cabin | 0 | 15 | 3 | 10 | change_cabin | 99 | 84.6 |
| severity_real | airline_compensation | 6 | 0 | send_certificate | 0 | 19 | 4 | 25 | send_certificate | 128 | 160.5 |
| severity_real | airline_modify_flights | 7 | 0 | update_reservation_flights | 0 | 35 | 11 | 10 | update_reservation_flights | 204 | 164.4 |
| severity_real | doc_coauthor_ship | 1 | 1 | ship | 0 | 11 | 0 | 1 | ship | 108 | 177.8 |
| severity_real | gem_dev_team | 2 | 1 | deploy | 0 | 17 | 2 | 5 | deploy | 180 | 237.1 |
| severity_real | pr_review_merge | 2 | 1 | merge | 0 | 316 | 0 | 16 | merge | 19772 | 17923.3 |
| severity_real | retail_cancel_pending_order | 8 | 0 | cancel_pending_order | 0 | 55 | 22 | 7 | cancel_pending_order | 288 | 309.1 |
| severity_real | retail_exchange_delivered_order | 10 | 0 | exchange_delivered_order_items | 0 | 103 | 47 | 6 | exchange_delivered_order_items | 631 | 684.2 |
| severity_real | retail_modify_pending_items | 10 | 0 | modify_pending_order_items | 0 | 103 | 47 | 6 | modify_pending_order_items | 631 | 692.1 |
| severity_real | retail_return_delivered_order | 8 | 0 | return_delivered_order_items | 0 | 40 | 16 | 4 | return_delivered_order_items | 216 | 193.3 |
| severity_real | sdlc_release_gate | 1 | 1 | deploy | 0 | 11 | 0 | 1 | deploy | 108 | 96.0 |
| severity_real | sdlc_release_gate_concurrent | 1 | 1 | deploy | 0 | 11 | 0 | 1 | deploy | 108 | 85.5 |
| severity_real | sdlc_release_gate_concurrent_withhold | 1 | 1 | deploy | 0 | 11 | 6 | 1 | deploy | 141 | 135.9 |
| severity_real | telecom_overdue_payment_resume | 5 | 0 | make_payment | 0 | 6 | 4 | 2 | make_payment | 72 | 59.1 |
| severity_real | telecom_refuel_data | 6 | 0 | refuel_data | 0 | 15 | 3 | 10 | refuel_data | 88 | 66.5 |
| real_skills | algorithmic-art | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | brand-guidelines | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | canvas-design | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | claude-api | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 40.2 |
| real_skills | doc-coauthoring | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 15.8 |
| real_skills | docx | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 15.8 |
| real_skills | frontend-design | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | internal-comms | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | mcp-builder | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | pdf | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 12.8 |
| real_skills | pptx | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 21.5 |
| real_skills | skill-creator | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 11.7 |
| real_skills | slack-gif-creator | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 3.8 |
| real_skills | theme-factory | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 0.0 |
| real_skills | web-artifacts-builder | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 6.1 |
| real_skills | webapp-testing | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 8.7 |
| real_skills | xlsx | 0 | 0 | – | ≥5 | 0 | 0 | 0 | – | 6 | 9.9 |

## Modularity experiment (k=2). Chains G;...;G of a benchmark segment. Whole-system re-derives goal reachability over the entire remaining chain at every branch; modular types each segment against its own goal at the incoming interface (TC_seq). Re-check: last segment replaced by its unsafe variant.

| family | n | whole (hazard, short-circuit) ms | whole (complete) ms | whole exits | modular concrete ms | concrete interface | modular projected ms | projected interface | re-check whole ms | re-check modular ms |
|---|---|---|---|---|---|---|---|---|---|---|
| deploy | 1 | 9.0 | 8.9 | 2 | 8.4 | 2 | 9.2 | 2 | 11.2 | 10.9 |
| deploy | 2 | 40.5 | 38.1 | 4 | 27.8 | 4 | 21.6 | 3 | 22.5 | 13.5 |
| deploy | 3 | 125.6 | 122.5 | 8 | 68.1 | 7 | 38.8 | 3 | 32.7 | 16.2 |
| deploy | 4 | 338.6 | 366.3 | 16 | 133.1 | 11 | 50.4 | 3 | 51.0 | 20.1 |
| deploy | 5 | 855.4 | 978.9 | 32 | 223.7 | 16 | 61.5 | 3 | 70.2 | 16.5 |
| deploy | 6 | 2210.7 | 2297.4 | 64 | 398.4 | 22 | 81.3 | 3 | 111.0 | 24.2 |
| migration | 1 | 39.8 | 45.0 | 3 | 32.4 | 3 | 42.4 | 2 | 37.4 | 26.3 |
| migration | 2 | 67.0 | 210.4 | 8 | 105.4 | 9 | 60.3 | 3 | 54.7 | 30.5 |
| migration | 3 | 87.3 | 958.8 | 20 | 380.1 | 26 | 94.0 | 3 | 89.9 | 39.5 |
| migration | 4 | 199.9 | 4485.9 | 48 | 1019.0 | 72 | 126.9 | 3 | 147.4 | 33.0 |
| migration | 5 | 252.7 | 20116.2 | 112 | 2661.5 | 192 | 155.7 | 3 | 208.0 | 32.0 |
| migration | 6 | 284.8 | 87168.6 | 256 | 7967.3 | 496 | 235.8 | 3 | 302.6 | 34.9 |

## Real-protocol group (benchmarks/severity_real)

Protocols ported from public multi-role skill repositories; expectations were committed before the tool ran (see benchmarks/severity_real/README.md). Counts are per branch and abstract world, as above; the misselection columns exclude branches the guard marks intended.

| pack | acting roles | k* | misselections: Benign | Futile | Catastrophic | bystander pairs | bystander exact |
|---|---|---|---|---|---|---|---|
| airline_baggage_update | 2 | 0 | 0 | 2 | 4 | 0 | True |
| airline_book_reservation | 2 | 0 | 3 | 7 | 10 | 0 | True |
| airline_cancel_reservation | 2 | 0 | 0 | 10 | 7 | 0 | True |
| airline_change_cabin | 3 | 0 | 1 | 3 | 10 | 0 | True |
| airline_compensation | 3 | 0 | 1 | 4 | 25 | 0 | True |
| airline_modify_flights | 3 | 0 | 7 | 11 | 10 | 0 | True |
| doc_coauthor_ship | 3 | 0 | 5 | 0 | 1 | 0 | True |
| gem_dev_team | 6 | 0 | 5 | 2 | 5 | 0 | True |
| pr_review_merge | 2 | 0 | 150 | 0 | 16 | 0 | True |
| retail_cancel_pending_order | 3 | 0 | 13 | 22 | 7 | 0 | True |
| retail_exchange_delivered_order | 3 | 0 | 25 | 47 | 6 | 0 | True |
| retail_modify_pending_items | 3 | 0 | 25 | 47 | 6 | 0 | True |
| retail_return_delivered_order | 3 | 0 | 10 | 16 | 4 | 0 | True |
| sdlc_release_gate | 2 | 0 | 5 | 0 | 1 | 0 | True |
| sdlc_release_gate_concurrent | 2 | 0 | 5 | 0 | 1 | 0 | True |
| sdlc_release_gate_concurrent_withhold | 2 | 0 | 5 | 6 | 1 | 0 | True |
| telecom_overdue_payment_resume | 3 | 0 | 0 | 4 | 2 | 0 | True |
| telecom_refuel_data | 3 | 0 | 1 | 3 | 10 | 0 | True |

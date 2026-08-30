(* Axiom-freeness harness for the deviation-layer audit.
   Every result must print "Closed under the global context". *)
Require Import DeviationLayer.

Print Assumptions down_monotone.
Print Assumptions meet_monotone.
Print Assumptions contamination_monotone.
Print Assumptions irr_safe_invariant.
Print Assumptions taint_laundering_refutes_noninterference.
Print Assumptions repaired_update_blocks_laundering.
Print Assumptions sr_dev_head_preserved.
Print Assumptions sr_dev_with_total_qres.
Print Assumptions act_vacuous_with_partial_qres.
Print Assumptions goal_then_act_vacuous.
Print Assumptions goal_only_cycle_hits_cap.
Print Assumptions wfloop_refresh_grade_bounded.

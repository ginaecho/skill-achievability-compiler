(* Axiom-freeness harness for the severity/k-resilience development.
   Every result must print "Closed under the global context". *)
Require Import Severity.

Print Assumptions TC_sound.
Print Assumptions TC_complete.
Print Assumptions TC_exact.
Print Assumptions tolerance_downward_closed.
Print Assumptions severity_disjoint.
Print Assumptions severity_exhaustive.
Print Assumptions catastrophe_implies_untypable.
Print Assumptions untypable_implies_catastrophe.
Print Assumptions reach_monotone_in_ctx.
Print Assumptions tolerance_antitone_in_ctx.
Print Assumptions repair_narrow_sound.
Print Assumptions Gbad_is_0_tolerant.
Print Assumptions Gbad_not_1_tolerant.
Print Assumptions Ggood_is_k_tolerant.
Print Assumptions Ggood_by_narrowing.
Print Assumptions TC_seq.
Print Assumptions TC_seq_interface.
Print Assumptions ends_budget_le.

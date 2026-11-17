Require Import Regular.
Print Assumptions product_correspondence.
Print Assumptions budget_never_increases.
Print Assumptions dev_edges_bounded.
Print Assumptions dev_edges_exact.
Print Assumptions reach_bounded_path.
Print Assumptions decide_sound.
Print Assumptions decide_complete.
Print Assumptions decide_reachb_correct.
Print Assumptions decide'_sound.
Print Assumptions decide'_complete.

(* environment edges in the product graph: EnvRegular.v *)
Require Import EnvRegular.
Print Assumptions reachbE_is_reachb.
Print Assumptions product_correspondence_env.
Print Assumptions env_edge_keeps_budget.
Print Assumptions budget_never_increases_env.
Print Assumptions dev_edges_exact_env.
Print Assumptions decide_env_correct.

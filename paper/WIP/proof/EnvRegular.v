(* ================================================================= *)
(*  EnvRegular.v -- environment choices in the PRODUCT GRAPH, the      *)
(*  DECISION PROCEDURE and the MU-TYPE layer.                          *)
(*                                                                     *)
(*  For the hazard query an environment edge is a compliant edge: it   *)
(*  costs no budget and is existential (the adversary picks).  So:     *)
(*                                                                     *)
(*   1. Product graph (Regular.v): budgeted reachability with a third  *)
(*      kind of edge is reachability in the product whose environment *)
(*      edges keep the budget component; the loop/budget theorems and  *)
(*      the decision procedure apply with succ0 ++ succE.              *)
(*   2. Mu-types (Mu.v): over guards  option Gd,  an environment       *)
(*      choice is the choice node whose branches carry no guard        *)
(*      (REnv, guard None, satisfied everywhere).  Its steps are        *)
(*      exactly RH-Env and its condition exactly T-Env (reach_mu_env,   *)
(*      safeR_env), and the unfolding closure, decide_mu, TR_exact and  *)
(*      bridge_mu apply unchanged.                                      *)
(*   3. The finite fragment WITH environment choices (EnvSeverity.v)    *)
(*      embeds: reachE = reach_mu on the image, so T-Env/T-Choice-Safe  *)
(*      is exactly non-reachability in the product graph.               *)
(*                                                                     *)
(*  What this layer does NOT carry: the demonic GOAL reading (greachE)  *)
(*  and the default guards, which EnvSeverity.v states for the finite   *)
(*  fragment only.                                                      *)
(*                                                                     *)
(*  Coq 8.18, stdlib only, axiom-free (check_regular.v, check_mu.v).    *)
(* ================================================================= *)
From Coq Require Import List Lia Arith PeanoNat Bool.
Import ListNotations.
Require Import Severity Regular Mu EnvSeverity.

(* ================================================================= *)
(*  1.  The product graph with environment edges.                      *)
(* ================================================================= *)
Section ProductEnv.
Variable Node W : Type.
Variable step0 stepE step1 : Node -> W -> Node -> W -> Prop.
Variable HazP : W -> Prop.

Inductive reachbE : nat -> Node -> W -> Prop :=
| RBE_here : forall b n w, HazP w -> reachbE b n w
| RBE_ok   : forall b n w n' w', step0 n w n' w' -> reachbE b n' w' -> reachbE b n w
| RBE_env  : forall b n w n' w', stepE n w n' w' -> reachbE b n' w' -> reachbE b n w
| RBE_dev  : forall b n w n' w', step1 n w n' w' -> reachbE b n' w' -> reachbE (S b) n w.

(* compliant and environment edges together *)
Definition step0u (n : Node) (w : W) (n' : Node) (w' : W) : Prop :=
  step0 n w n' w' \/ stepE n w n' w'.

Theorem reachbE_is_reachb : forall b n w,
  reachbE b n w <-> reachb Node W step0u step1 HazP b n w.
Proof.
  intros b n w. split; intro H.
  - induction H as [ b n w Hh | b n w n' w' Hs H IH | b n w n' w' Hs H IH | b n w n' w' Hs H IH ].
    + apply RB_here. exact Hh.
    + eapply RB_ok; [ left; exact Hs | exact IH ].
    + eapply RB_ok; [ right; exact Hs | exact IH ].
    + eapply RB_dev; [ exact Hs | exact IH ].
  - induction H as [ b n w Hh | b n w n' w' [Hs | Hs] H IH | b n w n' w' Hs H IH ].
    + apply RBE_here. exact Hh.
    + eapply RBE_ok; eassumption.
    + eapply RBE_env; eassumption.
    + eapply RBE_dev; eassumption.
Qed.

(* PRODUCT, with environment edges *)
Theorem product_correspondence_env : forall b n w,
  reachbE b n w <-> exists s', preach Node W step0u step1 (n, w, b) s' /\ phaz Node W HazP s'.
Proof.
  intros b n w. rewrite reachbE_is_reachb. apply product_correspondence.
Qed.

(* an environment edge keeps the budget component *)
Theorem env_edge_keeps_budget : forall n w n' w' b,
  stepE n w n' w' -> pstep Node W step0u step1 (n, w, b) (n', w', b).
Proof. intros. apply P_ok. right. assumption. Qed.

(* so the loop theorems hold verbatim: the budget never increases, and a
   path is debited exactly once per misselection edge -- environment
   edges, like compliant ones, are free *)
Theorem budget_never_increases_env : forall s s',
  preach Node W step0u step1 s s' -> pbud Node W s' <= pbud Node W s.
Proof. apply budget_never_increases. Qed.

Theorem dev_edges_exact_env : forall s s' d,
  preach_d Node W step0u step1 s s' d -> pbud Node W s = pbud Node W s' + d.
Proof. apply dev_edges_exact. Qed.

End ProductEnv.

(* ================================================================= *)
(*  The decision procedure, with environment successors.               *)
(* ================================================================= *)
Section DecideEnv.
Variable Node W : Type.
Hypothesis Node_dec : forall x y : Node, {x = y} + {x <> y}.
Hypothesis W_dec : forall x y : W, {x = y} + {x <> y}.
Variable nodes : list Node.
Variable worlds : list W.
Variable succ0 succE succ1 : Node -> W -> list (Node * W).
Variable hazb : W -> bool.
Definition stepL (succ : Node -> W -> list (Node * W)) (n : Node) (w : W) (n' : Node) (w' : W) : Prop :=
  In (n', w') (succ n w).
Hypothesis nodes_closed : forall n w n' w',
  In n nodes -> (stepL succ0 n w n' w' \/ stepL succE n w n' w' \/ stepL succ1 n w n' w') ->
  In n' nodes.
Hypothesis worlds_closed : forall n w n' w',
  In w worlds -> (stepL succ0 n w n' w' \/ stepL succE n w n' w' \/ stepL succ1 n w n' w') ->
  In w' worlds.

Definition succ0E (n : Node) (w : W) : list (Node * W) := succ0 n w ++ succE n w.

Definition decide_env (k : nat) (n : Node) (w : W) : bool :=
  decide_reachb_fast Node W Node_dec W_dec nodes worlds succ0E succ1 hazb k n w.

Lemma succ0E_iff : forall n w n' w',
  step0 Node W succ0E n w n' w' <-> step0u Node W (stepL succ0) (stepL succE) n w n' w'.
Proof.
  intros. unfold step0, succ0E, step0u, stepL. rewrite in_app_iff. reflexivity.
Qed.

Theorem decide_env_correct : forall k n w, In n nodes -> In w worlds ->
  (decide_env k n w = true <->
   reachbE Node W (stepL succ0) (stepL succE) (stepL succ1) (fun w => hazb w = true) k n w).
Proof.
  intros k n w Hn Hw. unfold decide_env.
  rewrite (decide_reachb_fast_correct Node W Node_dec W_dec nodes worlds succ0E succ1 hazb).
  - rewrite reachbE_is_reachb. apply reachb_equiv.
    + intros. apply succ0E_iff.
    + intros. reflexivity.
    + intros. reflexivity.
  - intros n0 w0 n' w' Hin Hs. eapply nodes_closed; [ exact Hin | ].
    destruct Hs as [Hs | Hs];
      [ apply succ0E_iff in Hs; destruct Hs as [Hs | Hs]; [ left | right; left ] | right; right ]; exact Hs.
  - intros n0 w0 n' w' Hin Hs. eapply worlds_closed; [ exact Hin | ].
    destruct Hs as [Hs | Hs];
      [ apply succ0E_iff in Hs; destruct Hs as [Hs | Hs]; [ left | right; left ] | right; right ]; exact Hs.
  - exact Hn.
  - exact Hw.
Qed.

End DecideEnv.

(* ================================================================= *)
(*  2.  Mu-types with environment choices.                             *)
(* ================================================================= *)
Section MuEnv.
Variable Wd  : Type.
Variable Gd0 : Type.
Variable sat0 : Gd0 -> Wd -> Prop.
Variable E   : CapN -> Wd -> Wd -> Prop.
Variable HazW : Wd -> Prop.

(* a branch guard, or None: an environment branch, never a mistake *)
Definition satO (g : option Gd0) (w : Wd) : Prop :=
  match g with None => True | Some g0 => sat0 g0 w end.

Definition REnv (p q : Role) (brs : list (Lab * Gr (option Gd0))) : Gr (option Gd0) :=
  RComm (option Gd0) p q (map (fun x => (fst x, None, snd x)) brs).

Theorem menv_step0 : forall p q brs w G' w',
  mstep0 Wd (option Gd0) satO E (REnv p q brs) w G' w' <->
  w' = w /\ exists l, In (l, G') brs.
Proof.
  intros p q brs w G' w'. unfold REnv. split.
  - intro H. inversion H as [ | | p0 q0 brs0 l g Gl w0 Hin Hs | ]; subst.
    apply in_map_iff in Hin. destruct Hin as [[l0 G0] [Heq Hin0]]. simpl in Heq.
    inversion Heq; subst. split; [ reflexivity | exists l; exact Hin0 ].
  - intros [-> [l Hin]]. eapply M_comm_ok with (g := None); [ | exact I ].
    apply in_map_iff. exists (l, G'). split; [ reflexivity | exact Hin ].
Qed.

Theorem menv_no_misselection : forall p q brs w G' w',
  ~ mstep1 Wd (option Gd0) satO (REnv p q brs) w G' w'.
Proof.
  intros p q brs w G' w' H. unfold REnv in H.
  inversion H as [ p0 q0 brs0 l g Gl w0 Hin Hns ]; subst.
  apply in_map_iff in Hin. destruct Hin as [[l0 G0] [Heq Hin0]]. simpl in Heq.
  inversion Heq; subst. apply Hns. exact I.
Qed.

(* RH-Env, at the mu layer *)
Theorem reach_mu_env : forall b p q brs w,
  reach_mu Wd (option Gd0) satO E HazW b (REnv p q brs) w <->
  HazW w \/ exists l Gl, In (l, Gl) brs /\ reach_mu Wd (option Gd0) satO E HazW b Gl w.
Proof.
  intros b p q brs w. unfold reach_mu. split.
  - intro H. inversion H as [ b0 n0 w0 Hh | b0 n0 w0 n' w' Hs Hr | b0 n0 w0 n' w' Hs Hr ]; subst.
    + left. exact Hh.
    + apply menv_step0 in Hs. destruct Hs as [-> [l Hin]]. right. exists l, n'. split; assumption.
    + exfalso. eapply menv_no_misselection; eassumption.
  - intros [Hh | [l [Gl [Hin Hr]]]].
    + apply RB_here. exact Hh.
    + eapply RB_ok; [ | exact Hr ]. apply menv_step0. split; [ reflexivity | exists l; exact Hin ].
Qed.

(* T-Env, at the mu layer *)
Theorem safeR_env : forall b p q brs w,
  safeR Wd (option Gd0) satO E HazW b (REnv p q brs) w <->
  ~ HazW w /\ forall l Gl, In (l, Gl) brs -> safeR Wd (option Gd0) satO E HazW b Gl w.
Proof.
  intros b p q brs w. rewrite TR_exact, reach_mu_env. split.
  - intro H. split.
    + intro Hh. apply H. left. exact Hh.
    + intros l Gl Hin. apply TR_complete. intro Hr. apply H. right. eauto.
  - intros [Hnh Hall] [Hh | [l [Gl [Hin Hr]]]].
    + exact (Hnh Hh).
    + exact (TR_sound _ _ _ _ _ _ _ _ (Hall l Gl Hin) Hr).
Qed.

(* a session step at an environment node costs nothing *)
Theorem env_hstep_costs_nothing : forall p q brs s w G' s' w' r c,
  hstep Wd (option Gd0) satO E (REnv p q brs) s w G' s' w' r c -> c = 0.
Proof.
  intros p q brs s w G' s' w' r c H. unfold REnv in H.
  inversion H as [ | | p0 q0 brs0 s0 w0 sb rb l g Gl P Q Hup Huq Hin HP HQ Hs
                   | p0 q0 brs0 s0 w0 sb rb l g Gl P Q Hup Huq Hin HP HQ Hns | ]; subst.
  - reflexivity.
  - exfalso. apply in_map_iff in Hin. destruct Hin as [[l0 G0] [Heq Hin0]]. simpl in Heq.
    inversion Heq; subst. apply Hns. exact I.
Qed.

(* THE BRIDGE, recursive, with environment choices: a session typed
   against a recursive protocol satisfying the condition at budget b is
   hazard-free on every run of misselection cost at most b, whatever
   the environment answers *)
Theorem bridge_mu_env : forall b G s w tr G' s' w',
  ctypes Wd (option Gd0) satO E G s w ->
  safeR Wd (option Gd0) satO E HazW b G w ->
  hrun Wd (option Gd0) satO E G s w tr G' s' w' -> Mu.total tr <= b -> ~ HazW w'.
Proof. intros. eapply bridge_mu_safeR; eassumption. Qed.

(* DECIDABILITY, with environment choices *)
Section MuEnvDecide.
Hypothesis Wd_dec : forall x y : Wd, {x = y} + {x <> y}.
Hypothesis Gd0_dec : forall x y : Gd0, {x = y} + {x <> y}.
Variable worlds : list Wd.
Hypothesis worlds_closed : forall a w w', In w worlds -> E a w w' -> In w' worlds.
Variable satb0 : Gd0 -> Wd -> bool.
Hypothesis sat0_spec : forall g w, sat0 g w <-> satb0 g w = true.
Variable succE : CapN -> Wd -> list Wd.
Hypothesis E_spec : forall a w w', E a w w' <-> In w' (succE a w).
Variable hazb : Wd -> bool.
Hypothesis haz_spec : forall w, HazW w <-> hazb w = true.

Definition GdO_dec : forall x y : option Gd0, {x = y} + {x <> y}.
Proof. decide equality. Defined.

Definition satbO (g : option Gd0) (w : Wd) : bool :=
  match g with None => true | Some g0 => satb0 g0 w end.

Lemma satO_spec : forall g w, satO g w <-> satbO g w = true.
Proof. intros [g0 | ] w; simpl; [ apply sat0_spec | split; auto ]. Qed.

Definition decide_mu_env (k : nat) (G0 : Gr (option Gd0)) (w : Wd) : bool :=
  decide_mu Wd (option Gd0) Wd_dec GdO_dec worlds satbO succE hazb k G0 w.

Theorem decide_mu_env_correct : forall k G0 w,
  closed_at (option Gd0) 0 G0 -> In w worlds ->
  (decide_mu_env k G0 w = true <-> reach_mu Wd (option Gd0) satO E HazW k G0 w).
Proof.
  intros. unfold decide_mu_env.
  apply (decide_mu_correct Wd (option Gd0) satO E HazW Wd_dec GdO_dec worlds worlds_closed
           satbO satO_spec succE E_spec hazb haz_spec); assumption.
Qed.

Theorem decide_mu_env_judgment : forall k G0 w,
  closed_at (option Gd0) 0 G0 -> In w worlds ->
  (decide_mu_env k G0 w = false <-> safeR Wd (option Gd0) satO E HazW k G0 w).
Proof.
  intros. unfold decide_mu_env.
  apply (decide_mu_judgment Wd (option Gd0) satO E HazW Wd_dec GdO_dec worlds worlds_closed
           satbO satO_spec succE E_spec hazb haz_spec); assumption.
Qed.

End MuEnvDecide.
End MuEnv.

(* ================================================================= *)
(*  3.  The finite fragment with environment choices embeds.           *)
(* ================================================================= *)
Section EmbedEnv.

Fixpoint embE (G : Ge) : Gr (option GdW) :=
  match G with
  | EEnd => REnd (option GdW)
  | EComm p q brs =>
      RComm (option GdW) p q (map (fun b => (fst (fst b), Some (snd (fst b)), embE (snd b))) brs)
  | EEnv p q brs =>
      RComm (option GdW) p q (map (fun b => (fst b, None, embE (snd b))) brs)
  | EAct a p G0 => RAct (option GdW) a p (embE G0)
  | EGoal phi G0 => RGoal (option GdW) (Some phi) (embE G0)
  end.

(* the image of an environment choice is REnv *)
Lemma embE_env : forall p q brs,
  embE (EEnv p q brs) = REnv GdW p q (map (fun b => (fst b, embE (snd b))) brs).
Proof. intros. simpl. unfold REnv. rewrite map_map. reflexivity. Qed.

Variable Ec : Ctx.
Variable HazF : World -> Prop.

Definition satOW : option GdW -> World -> Prop := satO World GdW satW.

Theorem reach_embed_env : forall b G W,
  reachE Ec HazF b G W <-> reach_mu World (option GdW) satOW Ec HazF b (embE G) W.
Proof.
  intros b G W. unfold reach_mu. split.
  - intro H. induction H as [ b G W Hh | b a p G W W' HE H IH | b phi G W H IH
                            | b p q brs l psi Gl W Hin Hpsi H IH
                            | b p q brs l psi Gl W Hin Hpsi H IH
                            | b p q brs l Gl W Hin H IH ]; simpl.
    + apply RB_here. exact Hh.
    + eapply RB_ok; [ apply M_act; exact HE | exact IH ].
    + eapply RB_ok; [ apply M_goal | exact IH ].
    + eapply RB_ok; [ | exact IH ]. eapply M_comm_ok with (g := Some psi); [ | exact Hpsi ].
      apply in_map_iff. exists (l, psi, Gl). split; [ reflexivity | exact Hin ].
    + eapply RB_dev; [ | exact IH ]. eapply M_comm_dev with (g := Some psi); [ | exact Hpsi ].
      apply in_map_iff. exists (l, psi, Gl). split; [ reflexivity | exact Hin ].
    + eapply RB_ok; [ | exact IH ]. eapply M_comm_ok with (g := None); [ | exact I ].
      apply in_map_iff. exists (l, Gl). split; [ reflexivity | exact Hin ].
  - intro H. remember (embE G) as X eqn:EX. revert G EX.
    induction H as [ b X W Hh | b X W X' W' Hs H IH | b X W X' W' Hs H IH ]; intros G EX; subst.
    + apply RE_here. exact Hh.
    + destruct G as [ | p q brs | p q brs | a p G0 | phi G0 ]; simpl in Hs; inversion Hs; subst.
      * match goal with
        | [ Hin : In (?l, ?g, X') (map _ brs) |- _ ] =>
            apply in_map_iff in Hin; destruct Hin as [[[l0 g0] Gl0] [Heq Hin0]];
            simpl in Heq; inversion Heq; subst
        end.
        eapply RE_comm_ok; [ exact Hin0 | assumption | apply IH; reflexivity ].
      * match goal with
        | [ Hin : In (?l, ?g, X') (map _ brs) |- _ ] =>
            apply in_map_iff in Hin; destruct Hin as [[l0 Gl0] [Heq Hin0]];
            simpl in Heq; inversion Heq; subst
        end.
        eapply RE_env; [ exact Hin0 | apply IH; reflexivity ].
      * eapply RE_act; [ eassumption | apply IH; reflexivity ].
      * apply RE_goal. apply IH. reflexivity.
    + destruct G as [ | p q brs | p q brs | a p G0 | phi G0 ]; simpl in Hs; inversion Hs; subst.
      * match goal with
        | [ Hin : In (?l, ?g, X') (map _ brs) |- _ ] =>
            apply in_map_iff in Hin; destruct Hin as [[[l0 g0] Gl0] [Heq Hin0]];
            simpl in Heq; inversion Heq; subst
        end.
        eapply RE_comm_dev; [ exact Hin0 | assumption | apply IH; reflexivity ].
      * exfalso.
        match goal with
        | [ Hin : In (?l, ?g, X') (map _ brs) |- _ ] =>
            apply in_map_iff in Hin; destruct Hin as [[l0 Gl0] [Heq Hin0]];
            simpl in Heq; inversion Heq; subst
        end.
        match goal with [ Hn : ~ satOW None _ |- _ ] => apply Hn; exact I end.
Qed.

(* T-Choice-Safe with T-Env IS non-reachability in the product graph *)
Theorem TE_regular : forall b G W,
  safeE Ec HazF b G W <-> ~ reach_mu World (option GdW) satOW Ec HazF b (embE G) W.
Proof. intros. rewrite <- reach_embed_env. apply TE_exact. Qed.

(* ... and is the coinductive judgment on the embedding *)
Theorem TE_is_TR : forall b G W,
  safeE Ec HazF b G W <-> safeR World (option GdW) satOW Ec HazF b (embE G) W.
Proof. intros. rewrite TE_regular. symmetry. apply TR_exact. Qed.

End EmbedEnv.

(* ================================================================= *)
(*  Severity.v                                                        *)
(*                                                                     *)
(*  Mechanized core of the REFRAMED paper: the type system does not    *)
(*  prevent an agent from choosing wrongly; it prevents wrong choices  *)
(*  from being CATASTROPHIC, and reports the rest as risk.             *)
(*                                                                     *)
(*  Coq 8.18, stdlib only, axiom-free (see check_sev.v).               *)
(*                                                                     *)
(*  Scope: the FINITE (non-recursive) fragment, matching the existing  *)
(*  DirectTyping.v scope.  Recursion is future work.                   *)
(*                                                                     *)
(*  Contents                                                           *)
(*    - guarded global types: each branch carries the predicate that   *)
(*      makes it the INTENDED branch, so misselection is definable     *)
(*    - budgeted hazard/goal reachability (k misselections allowed)    *)
(*    - the severity partition Benign / Futile / Catastrophic          *)
(*    - the typing judgment safeT (rule T-Choice-Safe)                 *)
(*    - T-C  soundness            : safeT k  =>  no hazard within k    *)
(*    - T-C' completeness         : the converse                       *)
(*    - budget monotonicity, Gamma monotonicity, repair soundness      *)
(*    - a worked instance: 0-resilient but NOT 1-resilient, repaired   *)
(* ================================================================= *)

Require Import List Arith Lia.
Import ListNotations.

Definition Var  := nat.
Definition Role := nat.
Definition CapN := nat.
Definition Lab  := nat.
Definition World := Var -> nat.

Definition wupd (W : World) (x : Var) (v : nat) : World :=
  fun y => if Nat.eq_dec y x then v else W y.

Lemma wupd_same : forall W x v, wupd W x v x = v.
Proof. intros. unfold wupd. destruct (Nat.eq_dec x x); congruence. Qed.

Lemma wupd_other : forall W x y v, y <> x -> wupd W x v y = W y.
Proof. intros. unfold wupd. destruct (Nat.eq_dec y x); congruence. Qed.

(* ----------------------------------------------------------------- *)
(*  Guarded global types.                                             *)
(*                                                                     *)
(*  A branch is  (label, guard, continuation).  In world W the branch  *)
(*  is INTENDED iff its guard holds.  Taking a branch whose guard does *)
(*  not hold is a MISSELECTION -- the agent that should choose A       *)
(*  chooses B.  This is the only new syntax the reframing needs.       *)
(* ----------------------------------------------------------------- *)
Inductive Gt : Type :=
| GEnd  : Gt
| GComm : Role -> Role -> list (Lab * (World -> Prop) * Gt) -> Gt
| GAct  : CapN -> Role -> Gt -> Gt
| GGoal : (World -> Prop) -> Gt -> Gt.

(* capability context: which world transitions each tool may perform *)
Definition Ctx := CapN -> World -> World -> Prop.
Definition ctx_le (E1 E2 : Ctx) : Prop :=
  forall a W W', E1 a W W' -> E2 a W W'.

(* ================================================================= *)
(*  Budgeted reachability.  The budget counts MISSELECTIONS ONLY:     *)
(*  compliant progress is free, a wrong branch costs one unit.        *)
(* ================================================================= *)

(* structural induction principle for the nested list *)
Fixpoint Gt_size (G : Gt) : nat :=
  match G with
  | GEnd => 1
  | GAct _ _ G0 => S (Gt_size G0)
  | GGoal _ G0 => S (Gt_size G0)
  | GComm _ _ brs =>
      S (fold_right (fun b acc => Gt_size (snd b) + acc) 0 brs)
  end.

Lemma in_brs_size :
  forall (brs : list (Lab * (World -> Prop) * Gt)) l psi Gl,
    In (l, psi, Gl) brs ->
    Gt_size Gl < S (fold_right (fun b acc => Gt_size (snd b) + acc) 0 brs).
Proof.
  induction brs as [ | [[l0 psi0] G0] tl IH ]; simpl; intros l psi Gl Hin.
  - contradiction.
  - destruct Hin as [Heq | Hin].
    + inversion Heq; subst; simpl; lia.
    + specialize (IH l psi Gl Hin). simpl in IH. lia.
Qed.

Section Reach.
Variable E : Ctx.
Variable Haz : World -> Prop.   (* the hazard predicate *)

Inductive reach_haz : nat -> Gt -> World -> Prop :=
| RH_here : forall b G W,
    Haz W -> reach_haz b G W
| RH_act : forall b a p G W W',
    E a W W' -> reach_haz b G W' -> reach_haz b (GAct a p G) W
| RH_goal : forall b phi G W,
    reach_haz b G W -> reach_haz b (GGoal phi G) W
| RH_comm_ok : forall b p q brs l psi Gl W,
    In (l, psi, Gl) brs -> psi W ->
    reach_haz b Gl W -> reach_haz b (GComm p q brs) W
| RH_comm_dev : forall b p q brs l psi Gl W,
    In (l, psi, Gl) brs -> ~ psi W ->
    reach_haz b Gl W -> reach_haz (S b) (GComm p q brs) W.

(* ----------------------------------------------------------------- *)
(*  The typing judgment.  Rule T-Choice-Safe is ST_Comm: an INTENDED  *)
(*  branch is checked at the same budget, a MISSELECTABLE branch is   *)
(*  checked at one unit less -- and is unconstrained when the budget  *)
(*  is exhausted, which is exactly what "affordable mistake" means.   *)
(* ----------------------------------------------------------------- *)
Inductive safeT : nat -> Gt -> World -> Prop :=
| ST_End : forall b W,
    ~ Haz W -> safeT b GEnd W
| ST_Goal : forall b phi G W,
    ~ Haz W -> safeT b G W -> safeT b (GGoal phi G) W
| ST_Act : forall b a p G W,
    ~ Haz W ->
    (forall W', E a W W' -> safeT b G W') ->
    safeT b (GAct a p G) W
| ST_Comm : forall b p q brs W,
    ~ Haz W ->
    (forall l psi Gl, In (l, psi, Gl) brs -> psi W -> safeT b Gl W) ->
    (forall l psi Gl, In (l, psi, Gl) brs -> ~ psi W ->
                      forall c, b = S c -> safeT c Gl W) ->
    safeT b (GComm p q brs) W.

(* ================================================================= *)
(*  T-C.  SOUNDNESS: a well-typed protocol with budget k admits no    *)
(*  hazard under any run containing at most k misselections.          *)
(* ================================================================= *)
Theorem TC_sound :
  forall b G W, safeT b G W -> ~ reach_haz b G W.
Proof.
  intros b G W Hs Hr. revert Hs.
  induction Hr as [ b G W Hh
                  | b a p G W W' Heff Hr IH
                  | b phi G W Hr IH
                  | b p q brs l psi Gl W Hin Hpsi Hr IH
                  | b p q brs l psi Gl W Hin Hpsi Hr IH ];
    intros Hs.
  - inversion Hs; subst; contradiction.
  - inversion Hs as [ | | b0 a0 p0 G0 W0 Hnh Hall | ]; subst.
    exact (IH (Hall W' Heff)).
  - inversion Hs as [ | b0 phi0 G0 W0 Hnh Hsub | | ]; subst.
    exact (IH Hsub).
  - inversion Hs as [ | | | b0 p0 q0 brs0 W0 Hnh Hok Hdev ]; subst.
    exact (IH (Hok l psi Gl Hin Hpsi)).
  - inversion Hs as [ | | | b0 p0 q0 brs0 W0 Hnh Hok Hdev ]; subst.
    exact (IH (Hdev l psi Gl Hin Hpsi b eq_refl)).
Qed.

(* ================================================================= *)
(*  T-C'.  COMPLETENESS: the rule system is not merely sound, it is   *)
(*  an exact syntax-directed characterization of bounded hazard-      *)
(*  freedom.  So a typing FAILURE is a genuine risk, never an         *)
(*  artifact of the rules -- the refutation asymmetry the discipline  *)
(*  is built on.                                                      *)
(* ================================================================= *)

Theorem TC_complete :
  forall n b G W, Gt_size G <= n -> ~ reach_haz b G W -> safeT b G W.
Proof.
  induction n as [ | n IH ]; intros b G W Hsz Hnr.
  - destruct G; simpl in Hsz; lia.
  - assert (Hnh : ~ Haz W) by (intro; apply Hnr; apply RH_here; assumption).
    destruct G as [ | p q brs | a p G0 | phi G0 ]; simpl in Hsz.
    + apply ST_End; assumption.
    + apply ST_Comm; [ assumption | | ].
      * intros l psi Gl Hin Hpsi. apply IH.
        -- pose proof (in_brs_size brs l psi Gl Hin). lia.
        -- intro Hc. apply Hnr. eapply RH_comm_ok; eauto.
      * intros l psi Gl Hin Hpsi c Hb. subst. apply IH.
        -- pose proof (in_brs_size brs l psi Gl Hin). lia.
        -- intro Hc. apply Hnr. eapply RH_comm_dev; eauto.
    + apply ST_Act; [ assumption | ].
      intros W' Heff. apply IH; [ lia | ].
      intro Hc. apply Hnr. eapply RH_act; eauto.
    + apply ST_Goal; [ assumption | ]. apply IH; [ lia | ].
      intro Hc. apply Hnr. apply RH_goal; assumption.
Qed.

Corollary TC_exact :
  forall b G W, safeT b G W <-> ~ reach_haz b G W.
Proof.
  intros b G W. split.
  - apply TC_sound.
  - intro H. eapply TC_complete; [ apply Nat.le_refl | exact H ].
Qed.

(* ================================================================= *)
(*  Budget monotonicity: k-misselection tolerance is downward closed in k.        *)
(* ================================================================= *)
Theorem tolerance_downward_closed :
  forall b G W, safeT b G W -> forall b', b' <= b -> safeT b' G W.
Proof.
  intros b G W Hs.
  induction Hs as [ b W Hnh
                  | b phi G W Hnh Hs IH
                  | b a p G W Hnh Hall IH
                  | b p q brs W Hnh Hok IHok Hdev IHdev ];
    intros b' Hle.
  - apply ST_End; assumption.
  - apply ST_Goal; auto.
  - apply ST_Act; [ assumption | ]. intros W' Heff. apply (IH W' Heff b' Hle).
  - apply ST_Comm; [ assumption | | ].
    + intros l psi Gl Hin Hpsi. apply (IHok l psi Gl Hin Hpsi b' Hle).
    + intros l psi Gl Hin Hpsi c Hb. subst.
      destruct b as [ | c0 ]; [ lia | ].
      apply (IHdev l psi Gl Hin Hpsi c0 eq_refl c). lia.
Qed.

End Reach.

(* ================================================================= *)
(*  Reachability is monotone in the budget: a bigger allowance can only  *)
(*  reach more.  Both severity predicates are instances (P := Haz for    *)
(*  the hazard, P := Phi for the goal), which is what makes the          *)
(*  trichotomy ORDERED rather than an arbitrary carve-up.                *)
(* ================================================================= *)
Lemma reach_mono_budget :
  forall (E : Ctx) (P : World -> Prop) b G W,
    reach_haz E P b G W -> forall b', b <= b' -> reach_haz E P b' G W.
Proof.
  intros E P b G W H.
  induction H as [ b G W Hh | b a p G W W' HE H IH | b phi G W H IH
                 | b p q brs l psi Gl W Hin Hpsi H IH
                 | b p q brs l psi Gl W Hin Hpsi H IH ]; intros b' Hle.
  - apply RH_here. exact Hh.
  - eapply RH_act; [ exact HE | apply IH; exact Hle ].
  - apply RH_goal. apply IH. exact Hle.
  - eapply RH_comm_ok; [ exact Hin | exact Hpsi | apply IH; exact Hle ].
  - destruct b' as [ | b'' ]; [ lia | ].
    eapply RH_comm_dev; [ exact Hin | exact Hpsi | apply IH; lia ].
Qed.

(* ================================================================= *)
(*  The severity partition.  Given a goal predicate as well, every    *)
(*  residual configuration falls in exactly one class.               *)
(* ================================================================= *)

(* ================================================================= *)
(*  THE OTHER QUANTIFIER.                                              *)
(*                                                                     *)
(*  reach_haz is EXISTENTIAL: some affordable path arrives.  For the    *)
(*  HAZARD that is the right reading -- a possible catastrophe is a     *)
(*  catastrophe.  For the GOAL it says only that the goal is still      *)
(*  POSSIBLE, and possible over the future choices of exactly the       *)
(*  participant the discipline says you cannot rely on.  assuredP gives *)
(*  the universal reading: whatever the agent picks and whatever the    *)
(*  environment returns, within budget b the run arrives at P.  A       *)
(*  choice must have an intended branch -- otherwise a budget of 0      *)
(*  would discharge the obligation vacuously -- every intended branch   *)
(*  must deliver, and so must every misselection the budget can pay     *)
(*  for.                                                                *)
(* ================================================================= *)
(* ================================================================= *)
(*  PRINCIPAL BUDGET.  k* is not merely where a scan stopped: it is     *)
(*  THE largest tolerated budget, and the set of tolerated budgets is   *)
(*  exactly the interval below it.  So the tolerance degree is a        *)
(*  principal solution in the type-theoretic sense -- every derivation  *)
(*  of the condition for this residual is a derivation at some b <= k*, *)
(*  and the one at k* subsumes them all by T-Sub.                       *)
(* ================================================================= *)
Section Principal.
Variable E : Ctx.
Variable Haz : World -> Prop.

Definition principal (k : nat) (G : Gt) (W : World) : Prop :=
  safeT E Haz k G W /\ ~ safeT E Haz (S k) G W.

Theorem principal_characterises : forall k G W,
  principal k G W -> forall b, safeT E Haz b G W <-> b <= k.
Proof.
  intros k G W [Hk Hnk] b. split.
  - intro Hb. destruct (Nat.le_gt_cases b k) as [Hle | Hgt]; [ exact Hle | ].
    exfalso. apply Hnk. apply (TC_complete E Haz (Gt_size G)); [ apply le_n | ].
    intro Hr. apply (TC_sound E Haz b G W Hb).
    eapply reach_mono_budget; [ exact Hr | lia ].
  - intro Hle. apply (TC_complete E Haz (Gt_size G)); [ apply le_n | ].
    intro Hr. apply (TC_sound E Haz k G W Hk).
    eapply reach_mono_budget; [ exact Hr | exact Hle ].
Qed.

Theorem principal_unique : forall k k' G W,
  principal k G W -> principal k' G W -> k = k'.
Proof.
  intros k k' G W Hp Hp'.
  destruct Hp as [Hk Hnk]. destruct Hp' as [Hk' Hnk'].
  assert (Hle : k <= k').
  { apply (principal_characterises k' G W (conj Hk' Hnk')). exact Hk. }
  assert (Hle' : k' <= k).
  { apply (principal_characterises k G W (conj Hk Hnk)). exact Hk'. }
  lia.
Qed.

(* and it exists exactly when tolerance is finite: if some budget is not
   tolerated, there is a largest one that is *)
Theorem principal_exists : forall n G W,
  (forall b, safeT E Haz b G W \/ ~ safeT E Haz b G W) ->
  safeT E Haz 0 G W -> ~ safeT E Haz n G W -> exists k, principal k G W.
Proof.
  intros n G W Hdec H0. induction n as [ | n IH ]; intro Hn.
  - contradiction.
  - destruct (Hdec n) as [Hy | Hn'].
    + exists n. split; assumption.
    + apply IH. exact Hn'.
Qed.

End Principal.

Section AssuredS.
Variable E : Ctx.
Variable P : World -> Prop.

Inductive assuredP : nat -> Gt -> World -> Prop :=
| AS_here : forall b G W,
    P W -> assuredP b G W
| AS_act : forall b a p G W,
    (exists W', E a W W') ->
    (forall W', E a W W' -> assuredP b G W') ->
    assuredP b (GAct a p G) W
| AS_goal : forall b phi G W,
    assuredP b G W -> assuredP b (GGoal phi G) W
| AS_comm : forall b p q brs W l0 psi0 Gl0,
    In (l0, psi0, Gl0) brs -> psi0 W ->
    (forall l psi Gl, In (l, psi, Gl) brs -> psi W -> assuredP b Gl W) ->
    (forall l psi Gl c, In (l, psi, Gl) brs -> ~ psi W -> b = S c ->
                        assuredP c Gl W) ->
    assuredP b (GComm p q brs) W.

(* what is assured is reachable: the universal reading refines the
   existential one, so it strengthens the classes rather than changing
   them *)
Theorem assured_reach : forall b G W, assuredP b G W -> reach_haz E P b G W.
Proof.
  intros b G W H.
  induction H as [ b G W Hp | b a p G W Hex Hall IH | b phi G W H IH
                 | b p q brs W l0 psi0 Gl0 Hin Hpsi Hok IHok Hdev IHdev ].
  - apply RH_here. exact Hp.
  - destruct Hex as [W' HE]. eapply RH_act; [ exact HE | apply IH; exact HE ].
  - apply RH_goal. exact IH.
  - eapply RH_comm_ok; [ exact Hin | exact Hpsi | ].
    exact (IHok l0 psi0 Gl0 Hin Hpsi).
Qed.

(* and it is monotone in the budget in the direction one expects: more
   affordable mistakes is a STRONGER obligation, so assurance at a larger
   budget implies assurance at a smaller one *)
Lemma assured_downward : forall b b' G W,
  assuredP b G W -> b' <= b -> assuredP b' G W.
Proof.
  intros b b' G W H. revert b'.
  induction H as [ b G W Hp | b a p G W Hex Hall IH | b phi G W H IH
                 | b p q brs W l0 psi0 Gl0 Hin Hpsi Hok IHok Hdev IHdev ];
    intros b' Hle.
  - apply AS_here. exact Hp.
  - apply AS_act; [ exact Hex | ]. intros W' HE. apply IH; [ exact HE | exact Hle ].
  - apply AS_goal. apply IH. exact Hle.
  - eapply AS_comm; [ exact Hin | exact Hpsi | | ].
    + intros l psi Gl Hin' Hp'. exact (IHok l psi Gl Hin' Hp' b' Hle).
    + intros l psi Gl c Hin' Hnp Hb. subst b'.
      destruct b as [ | b0 ]; [ lia | ].
      exact (IHdev l psi Gl b0 Hin' Hnp eq_refl c ltac:(lia)).
Qed.

End AssuredS.

Section Severity.
Variable E : Ctx.
Variable Haz : World -> Prop.
Variable Phi : World -> Prop.       (* the goal *)

Definition Catastrophic (b : nat) (G : Gt) (W : World) : Prop :=
  reach_haz E Haz b G W.
Definition Futile (b : nat) (G : Gt) (W : World) : Prop :=
  ~ reach_haz E Haz b G W /\ ~ reach_haz E Phi b G W.
Definition Benign (b : nat) (G : Gt) (W : World) : Prop :=
  ~ reach_haz E Haz b G W /\ reach_haz E Phi b G W.

(* The goal side, read universally.  Benign says the goal is still
   POSSIBLE; Robust says it is still GUARANTEED -- no affordable
   misselection, and no environment answer, can talk the run out of it.
   Robust implies Benign and is strictly stronger (Bridge.v exhibits the
   gap), so the two readings are kept apart rather than conflated. *)
Definition Assured (b : nat) (G : Gt) (W : World) : Prop := assuredP E Phi b G W.

Definition Robust (b : nat) (G : Gt) (W : World) : Prop :=
  ~ reach_haz E Haz b G W /\ Assured b G W.

Theorem robust_benign : forall b G W, Robust b G W -> Benign b G W.
Proof.
  intros b G W [Hnh Ha]. split; [ exact Hnh | apply assured_reach; exact Ha ].
Qed.

(* Failure is not disaster.  The three classes are pairwise disjoint,
   and (given decidability of the two reachability questions, which the
   QF-LIA fragment supplies) exhaustive.  This is the distinction a
   binary achievable/impossible verdict cannot express, and the reason
   the resulting tool is usable rather than merely safe. *)
Theorem severity_disjoint :
  forall b G W,
    ~ (Catastrophic b G W /\ Futile b G W) /\
    ~ (Catastrophic b G W /\ Benign b G W) /\
    ~ (Futile b G W /\ Benign b G W).
Proof.
  intros b G W. unfold Catastrophic, Futile, Benign.
  repeat split; intros [H1 H2].
  - destruct H2 as [Hn _]. contradiction.
  - destruct H2 as [Hn _]. contradiction.
  - destruct H1 as [_ Hng]. destruct H2 as [_ Hg]. contradiction.
Qed.

Theorem severity_exhaustive :
  forall b G W,
    (reach_haz E Haz b G W \/ ~ reach_haz E Haz b G W) ->
    (reach_haz E Phi b G W \/ ~ reach_haz E Phi b G W) ->
    Catastrophic b G W \/ Futile b G W \/ Benign b G W.
Proof.
  intros b G W [Hh | Hh] [Hg | Hg]; unfold Catastrophic, Futile, Benign; tauto.
Qed.

(* ================================================================= *)
(*  THE TRICHOTOMY IS ORDERED.  Put Futile < Benign < Catastrophic.    *)
(*  As the budget grows the class of a residual moves UP this chain    *)
(*  and never down: the goal, once reachable within a budget, stays    *)
(*  reachable, and a hazard once reachable is absorbing.  So the three *)
(*  classes are not an arbitrary carve-up of two predicates -- they    *)
(*  are three INTERVALS of budgets, in this order, and the tolerance   *)
(*  degree is the boundary of the last one.                            *)
(* ================================================================= *)

(* Catastrophic is upward closed: a hazard affordable at b is affordable
   at any larger budget. *)
Theorem catastrophic_upward :
  forall b b' G W, b <= b' -> Catastrophic b G W -> Catastrophic b' G W.
Proof. intros b b' G W Hle H. eapply reach_mono_budget; eassumption. Qed.

(* Futile is downward closed. *)
Theorem futile_downward :
  forall b b' G W, b <= b' -> Futile b' G W -> Futile b G W.
Proof.
  intros b b' G W Hle [Hh Hg]. split; intro H; [ apply Hh | apply Hg ];
    eapply reach_mono_budget; eassumption.
Qed.

(* Benign never degrades to Futile: more budget cannot lose the goal. *)
Theorem benign_no_regress :
  forall b b' G W, b <= b' -> Benign b G W -> ~ Futile b' G W.
Proof.
  intros b b' G W Hle [_ Hg] [_ Hng]. apply Hng.
  eapply reach_mono_budget; eassumption.
Qed.

(* Raising the budget moves a Benign residual to Benign or Catastrophic,
   and never anywhere else. *)
(* Decidability of the two reachability questions is a hypothesis, exactly
   as in severity_exhaustive: the QF-LIA fragment supplies it and the
   development stays axiom-free. *)
Theorem benign_step_up :
  forall b b' G W, b <= b' ->
    (reach_haz E Haz b' G W \/ ~ reach_haz E Haz b' G W) ->
    Benign b G W -> Benign b' G W \/ Catastrophic b' G W.
Proof.
  intros b b' G W Hle Hdec [Hh Hg].
  destruct Hdec as [Hc | Hc].
  - right. exact Hc.
  - left. split; [ exact Hc | eapply reach_mono_budget; eassumption ].
Qed.

(* Lowering the budget moves a Benign residual to Benign or Futile. *)
Theorem benign_step_down :
  forall b b' G W, b <= b' ->
    (reach_haz E Phi b G W \/ ~ reach_haz E Phi b G W) ->
    Benign b' G W -> Benign b G W \/ Futile b G W.
Proof.
  intros b b' G W Hle Hdec [Hh Hg].
  assert (Hnh : ~ reach_haz E Haz b G W).
  { intro H. apply Hh. eapply reach_mono_budget; eassumption. }
  destruct Hdec as [Hp | Hp].
  - left. split; assumption.
  - right. split; assumption.
Qed.

(* THE INTERVAL THEOREM.  Rank Futile 0, Benign 1, Catastrophic 2; the
   rank of a residual is a monotone non-decreasing function of its
   budget.  Equivalently: the budgets at which a residual is Futile, then
   Benign, then Catastrophic form three consecutive intervals of N in
   that order (any of them possibly empty). *)
Definition sev_rank (b : nat) (G : Gt) (W : World) (r : nat) : Prop :=
  (r = 0 /\ Futile b G W) \/ (r = 1 /\ Benign b G W) \/ (r = 2 /\ Catastrophic b G W).

Theorem severity_monotone_in_budget :
  forall b b' G W r r', b <= b' ->
    sev_rank b G W r -> sev_rank b' G W r' -> r <= r'.
Proof.
  intros b b' G W r r' Hle Hr Hr'.
  destruct Hr as [[-> Hf] | [[-> Hb] | [-> Hc]]].
  - lia.
  - destruct Hr' as [[-> Hf'] | [[-> _] | [-> _]]]; [ | lia | lia ].
    exfalso. eapply benign_no_regress; eassumption.
  - destruct Hr' as [[-> Hf'] | [[-> Hb'] | [-> _]]]; [ | | lia ].
    + exfalso. destruct Hf' as [Hnh _]. apply Hnh.
      eapply reach_mono_budget; eassumption.
    + exfalso. destruct Hb' as [Hnh _]. apply Hnh.
      eapply reach_mono_budget; eassumption.
Qed.

(* The tolerance degree is a genuine THRESHOLD, not merely the first
   budget the search happened to stop at: below it nothing catastrophic
   is affordable, above it everything is. *)
Theorem tolerance_degree_is_a_threshold :
  forall k G W,
    ~ Catastrophic k G W -> Catastrophic (S k) G W ->
    (forall b, b <= k -> ~ Catastrophic b G W) /\
    (forall b, S k <= b -> Catastrophic b G W).
Proof.
  intros k G W Hnk Hk. split.
  - intros b Hb Hc. apply Hnk. eapply catastrophic_upward; eassumption.
  - intros b Hb. eapply catastrophic_upward; eassumption.
Qed.

(* ... and the classes it separates are inhabited by different budgets of
   the SAME residual, which is what makes the trichotomy informative: a
   residual can be Futile at 0, Benign at 1 and Catastrophic at 2. *)
Theorem severity_classes_are_separated :
  forall k G W,
    ~ Catastrophic k G W -> Catastrophic (S k) G W ->
    forall b, b <= k ->
      (reach_haz E Haz b G W \/ ~ reach_haz E Haz b G W) ->
      (reach_haz E Phi b G W \/ ~ reach_haz E Phi b G W) ->
      (Futile b G W \/ Benign b G W).
Proof.
  intros k G W Hnk Hk b Hb Hd1 Hd2.
  destruct (severity_exhaustive b G W Hd1 Hd2) as [Hc | [Hf | Hbn]].
  - exfalso. apply Hnk. eapply catastrophic_upward; [ exact Hb | exact Hc ].
  - left. exact Hf.
  - right. exact Hbn.
Qed.

(* T-F.  Catastrophe is EXACTLY the failure of the typing judgment.
   The checker's refutation is the severity classifier -- no new
   machinery is needed to detect catastrophe, only to run the existing
   refutation pointwise at every branch. *)
Theorem catastrophe_implies_untypable :
  forall b G W, Catastrophic b G W -> ~ safeT E Haz b G W.
Proof.
  intros b G W Hr Hs. exact (TC_sound E Haz b G W Hs Hr).
Qed.

Theorem untypable_implies_catastrophe :
  forall b G W,
    (reach_haz E Haz b G W \/ ~ reach_haz E Haz b G W) ->
    ~ safeT E Haz b G W -> Catastrophic b G W.
Proof.
  intros b G W [Hr | Hr] Hns.
  - exact Hr.
  - exfalso. apply Hns. eapply TC_complete; [ apply Nat.le_refl | exact Hr ].
Qed.

End Severity.

(* ================================================================= *)
(*  Gamma monotonicity -- and the correction it forces.               *)
(*                                                                     *)
(*  Reachability of ANYTHING is monotone in the capability context.    *)
(*  Hazard reachability is therefore monotone too, so k-misselection tolerance is  *)
(*  ANTI-monotone in Gamma: giving an agent more tools can only make   *)
(*  it less resilient, never more.  (An earlier design note claimed    *)
(*  severity was monotone-decreasing in Gamma on the grounds that more *)
(*  tools give more recovery options.  That is false: the same tools   *)
(*  also open new paths to the hazard.  The corrected statement is     *)
(*  below, and it is the more useful one -- it is the formal argument  *)
(*  for least-privilege capability contexts.)                          *)
(* ================================================================= *)

Theorem reach_monotone_in_ctx :
  forall E1 E2 Haz b G W,
    ctx_le E1 E2 -> reach_haz E1 Haz b G W -> reach_haz E2 Haz b G W.
Proof.
  intros E1 E2 Haz b G W Hle Hr.
  induction Hr.
  - apply RH_here; assumption.
  - eapply RH_act; [ apply Hle; eassumption | assumption ].
  - apply RH_goal; assumption.
  - eapply RH_comm_ok; eauto.
  - eapply RH_comm_dev; eauto.
Qed.

Corollary tolerance_antitone_in_ctx :
  forall E1 E2 Haz b G W,
    ctx_le E1 E2 -> safeT E2 Haz b G W -> ~ reach_haz E1 Haz b G W.
Proof.
  intros E1 E2 Haz b G W Hle Hs Hr.
  exact (TC_sound E2 Haz b G W Hs (reach_monotone_in_ctx E1 E2 Haz b G W Hle Hr)).
Qed.

(* ================================================================= *)
(*  Repair pattern 3, NARROW THE OFFER, is sound: removing branches   *)
(*  from a choice node preserves well-typedness at the same budget.   *)
(* ================================================================= *)

Definition brs_sub (brs' brs : list (Lab * (World -> Prop) * Gt)) : Prop :=
  forall x, In x brs' -> In x brs.

Theorem repair_narrow_sound :
  forall E Haz b p q brs brs' W,
    brs_sub brs' brs ->
    safeT E Haz b (GComm p q brs) W ->
    safeT E Haz b (GComm p q brs') W.
Proof.
  intros E Haz b p q brs brs' W Hsub Hs.
  inversion Hs as [ | | | b0 p0 q0 brs0 W0 Hnh Hok Hdev ]; subst.
  apply ST_Comm; [ assumption | | ].
  - intros l psi Gl Hin Hpsi. apply (Hok l psi Gl (Hsub _ Hin) Hpsi).
  - intros l psi Gl Hin Hpsi c Hb. apply (Hdev l psi Gl (Hsub _ Hin) Hpsi c Hb).
Qed.

(* ================================================================= *)
(*  A worked instance: the risk verdict the tool should emit.         *)
(*                                                                     *)
(*  Roles: planner 0, worker 1.  Variables: verified = 0, booked = 1.  *)
(*  Capabilities: 1 = verify (sets verified), 2 = purchase (sets       *)
(*  booked -- irreversible, externally visible).                       *)
(*  Hazard: booked without verification.                               *)
(*                                                                     *)
(*  Gbad offers a "fast path" that skips verification.  Its guard is   *)
(*  never satisfied, so taking it is a MISSELECTION -- exactly the     *)
(*  "should choose A, chooses B" case.                                 *)
(* ================================================================= *)

Definition verified : Var := 0.
Definition booked   : Var := 1.

Definition E0 : Ctx := fun a W W' =>
  (a = 1 /\ W' = wupd W verified 1) \/ (a = 2 /\ W' = wupd W booked 1).

Definition Haz0 : World -> Prop := fun W => W booked = 1 /\ W verified = 0.

Definition W0 : World := fun _ => 0.

Definition SafePath : Gt := GAct 1 1 (GAct 2 1 GEnd).   (* verify ; purchase *)
Definition FastPath : Gt := GAct 2 1 GEnd.              (* purchase directly *)

Definition Gbad : Gt :=
  GComm 0 1 [ (10, (fun _ : World => True),  SafePath) ;
              (11, (fun _ : World => False), FastPath) ].

Definition Ggood : Gt :=
  GComm 0 1 [ (10, (fun _ : World => True),  SafePath) ].

Lemma notHaz_W0 : ~ Haz0 W0.
Proof. unfold Haz0, W0. intros [H1 H2]. discriminate H1. Qed.

Lemma safe_path_typed : forall b, safeT E0 Haz0 b SafePath W0.
Proof.
  intro b. unfold SafePath.
  apply ST_Act; [ apply notHaz_W0 | ].
  intros W1 H1. destruct H1 as [[_ Heq] | [Hbad _]]; [ | discriminate Hbad ].
  subst W1.
  apply ST_Act.
  - unfold Haz0, wupd, booked, verified, W0. simpl. intros [Hc _]. discriminate Hc.
  - intros W2 H2. destruct H2 as [[Hbad _] | [_ Heq]]; [ discriminate Hbad | ].
    subst W2. apply ST_End.
    unfold Haz0, wupd, booked, verified, W0. simpl. intros [_ Hc]. discriminate Hc.
Qed.

(* Gbad IS 0-resilient: if the agent never misselects, no hazard. *)
Theorem Gbad_is_0_tolerant : safeT E0 Haz0 0 Gbad W0.
Proof.
  unfold Gbad. apply ST_Comm; [ apply notHaz_W0 | | ].
  - intros l psi Gl Hin Hpsi. simpl in Hin.
    destruct Hin as [Heq | [Heq | []]]; inversion Heq; subst.
    + apply safe_path_typed.
    + destruct Hpsi.
  - intros l psi Gl Hin Hpsi c Hb. discriminate Hb.
Qed.

(* ... but NOT 1-resilient: a single wrong choice reaches the hazard.
   This is the actionable risk verdict. *)
Theorem Gbad_not_1_tolerant : ~ safeT E0 Haz0 1 Gbad W0.
Proof.
  intro Hs. unfold Gbad in Hs.
  inversion Hs as [ | | | b0 p0 q0 brs0 W1 Hnh Hok Hdev ]; subst.
  assert (Hin : In (11, (fun _ : World => False), FastPath)
                   [ (10, (fun _ : World => True),  SafePath) ;
                     (11, (fun _ : World => False), FastPath) ])
    by (simpl; right; left; reflexivity).
  specialize (Hdev 11 (fun _ : World => False) FastPath Hin
                   (fun H => H) 0 eq_refl).
  unfold FastPath in Hdev.
  inversion Hdev as [ | | b1 a1 p1 G1 W2 Hnh1 Hall | ]; subst.
  specialize (Hall (wupd W0 booked 1) (or_intror (conj eq_refl eq_refl))).
  inversion Hall as [ b2 W3 Hnh2 | | | ]; subst.
  apply Hnh2. unfold Haz0, wupd, booked, verified, W0. simpl. split; reflexivity.
Qed.

(* The repair (narrow the offer) makes it resilient at every budget. *)
Theorem Ggood_is_k_tolerant : forall k, safeT E0 Haz0 k Ggood W0.
Proof.
  intro k. unfold Ggood. apply ST_Comm; [ apply notHaz_W0 | | ].
  - intros l psi Gl Hin Hpsi. simpl in Hin.
    destruct Hin as [Heq | []]; inversion Heq; subst. apply safe_path_typed.
  - intros l psi Gl Hin Hpsi c Hb. simpl in Hin.
    destruct Hin as [Heq | []]; inversion Heq; subst. destruct (Hpsi I).
Qed.

(* And the repair is an instance of the general soundness result. *)
Corollary Ggood_by_narrowing :
  forall b W, safeT E0 Haz0 b Gbad W -> safeT E0 Haz0 b Ggood W.
Proof.
  intros b W Hs. unfold Ggood, Gbad in *.
  eapply repair_narrow_sound; [ | exact Hs ].
  unfold brs_sub. intros x Hin. simpl in Hin. simpl. tauto.
Qed.

(* ================================================================= *)
(*  Section: COMPOSITIONALITY.                                        *)
(*                                                                     *)
(*  This is the theorem that answers the question -- why is this a type system and   *)
(*  not a bounded model checker?  Sequential composition G1 ; G2 is  *)
(*  typed MODULARLY: G2 is checked only against the INTERFACE that G1 *)
(*  exposes -- the (remaining budget, world) pairs at which G1 can     *)
(*  terminate -- never against G1's internal structure.  A whole-     *)
(*  system reachability check of G1;G2 explores the product; the      *)
(*  modular derivation explores |G1| plus |G2| per interface point.   *)
(* ================================================================= *)

Fixpoint gseq (G1 G2 : Gt) : Gt :=
  match G1 with
  | GEnd => G2
  | GComm p q brs =>
      GComm p q (map (fun br => match br with
                                | (l, psi, Gl) => (l, psi, gseq Gl G2)
                                end) brs)
  | GAct a p G => GAct a p (gseq G G2)
  | GGoal phi G => GGoal phi (gseq G G2)
  end.

Lemma in_gseq_brs :
  forall G2 (brs : list (Lab * (World -> Prop) * Gt)) l psi Gl',
    In (l, psi, Gl') (map (fun br => match br with
                                    | (l0, psi0, Gl0) => (l0, psi0, gseq Gl0 G2)
                                    end) brs) ->
    exists Gl, In (l, psi, Gl) brs /\ Gl' = gseq Gl G2.
Proof.
  intros G2 brs l psi Gl' Hin.
  apply in_map_iff in Hin.
  destruct Hin as [[[l0 psi0] Gl0] [Heq Hin0]].
  inversion Heq; subst. exists Gl0. split; [ exact Hin0 | reflexivity ].
Qed.

Section Compose.
Variable E : Ctx.
Variable Haz : World -> Prop.

(* The INTERFACE of a protocol: the (budget-left, world) pairs at which it
   can terminate, starting from budget b at world W. *)
Inductive ends : nat -> Gt -> World -> nat -> World -> Prop :=
| EN_end : forall b W,
    ends b GEnd W b W
| EN_act : forall b a p G W W' b' W'',
    E a W W' -> ends b G W' b' W'' -> ends b (GAct a p G) W b' W''
| EN_goal : forall b phi G W b' W',
    ends b G W b' W' -> ends b (GGoal phi G) W b' W'
| EN_comm_ok : forall b p q brs l psi Gl W b' W',
    In (l, psi, Gl) brs -> psi W ->
    ends b Gl W b' W' -> ends b (GComm p q brs) W b' W'
| EN_comm_dev : forall b p q brs l psi Gl W b' W',
    In (l, psi, Gl) brs -> ~ psi W ->
    ends b Gl W b' W' -> ends (S b) (GComm p q brs) W b' W'.

(* MODULAR TYPING OF SEQUENTIAL COMPOSITION.
   G2 is typed only at the interface points of G1. *)
Theorem TC_seq :
  forall b G1 W,
    safeT E Haz b G1 W ->
    forall G2,
      (forall b' W', ends b G1 W b' W' -> safeT E Haz b' G2 W') ->
      safeT E Haz b (gseq G1 G2) W.
Proof.
  intros b G1 W Hs.
  induction Hs as [ b W Hnh
                  | b phi G W Hnh Hs IH
                  | b a p G W Hnh Hall IH
                  | b p q brs W Hnh Hok IHok Hdev IHdev ];
    intros G2 Hiface; simpl.
  - apply Hiface. apply EN_end.
  - apply ST_Goal; [ assumption | ].
    apply IH. intros b' W' He. apply Hiface. apply EN_goal; assumption.
  - apply ST_Act; [ assumption | ].
    intros W' Heff. apply (IH W' Heff).
    intros b' W'' He. apply Hiface. eapply EN_act; eassumption.
  - apply ST_Comm; [ assumption | | ].
    + intros l psi Gl' Hin Hpsi.
      destruct (in_gseq_brs G2 brs l psi Gl' Hin) as [Gl [Hin0 Heq]]; subst.
      apply (IHok l psi Gl Hin0 Hpsi).
      intros b' W' He. apply Hiface. eapply EN_comm_ok; eassumption.
    + intros l psi Gl' Hin Hpsi c Hb; subst.
      destruct (in_gseq_brs G2 brs l psi Gl' Hin) as [Gl [Hin0 Heq]]; subst.
      apply (IHdev l psi Gl Hin0 Hpsi c eq_refl).
      intros b' W' He. apply Hiface. eapply EN_comm_dev; eassumption.
Qed.

(* The INTERFACE-ABSTRACTION form: G2 need only be checked against a
   declared invariant I that G1's terminations satisfy.  This is exactly
   what a whole-system reachability check cannot offer -- one checks G2
   once against I, not once per concrete G1 termination. *)
Corollary TC_seq_interface :
  forall (I : nat -> World -> Prop) b G1 G2 W,
    safeT E Haz b G1 W ->
    (forall b' W', ends b G1 W b' W' -> I b' W') ->
    (forall b' W', I b' W' -> safeT E Haz b' G2 W') ->
    safeT E Haz b (gseq G1 G2) W.
Proof.
  intros I b G1 G2 W Hs Hends HI.
  apply TC_seq; [ exact Hs | ].
  intros b' W' He. apply HI. apply Hends. exact He.
Qed.

(* Budget accounting is tight: the interface never reports more budget
   than it started with. *)
Lemma ends_budget_le : forall b G W b' W', ends b G W b' W' -> b' <= b.
Proof. intros b G W b' W' H. induction H; lia. Qed.

End Compose.

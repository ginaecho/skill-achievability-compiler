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
(*  Budget monotonicity: k-resilience is downward closed in k.        *)
(* ================================================================= *)
Theorem resilience_downward_closed :
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
(*  The severity partition.  Given a goal predicate as well, every    *)
(*  residual configuration falls in exactly one class.               *)
(* ================================================================= *)

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
(*  Hazard reachability is therefore monotone too, so k-resilience is  *)
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

Corollary resilience_antitone_in_ctx :
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
Theorem Gbad_is_0_resilient : safeT E0 Haz0 0 Gbad W0.
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
Theorem Gbad_not_1_resilient : ~ safeT E0 Haz0 1 Gbad W0.
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
Theorem Ggood_is_k_resilient : forall k, safeT E0 Haz0 k Ggood W0.
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

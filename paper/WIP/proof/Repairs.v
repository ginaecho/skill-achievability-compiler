(* ================================================================= *)
(*  Repairs.v -- the four repairs of the paper, mechanized.           *)
(*                                                                     *)
(*    narrow      : Severity.v (repair_narrow_sound)                   *)
(*    guard       : insert a VALIDATION before a misselectable branch  *)
(*    reorder     : move an irreversible action AFTER a validation /   *)
(*                  establisher it commutes with                       *)
(*    compensate  : append a recovery path (a corollary of TC_seq)     *)
(*                                                                     *)
(*  Coq 8.18, stdlib only, axiom-free (see check_repairs.v).           *)
(* ================================================================= *)
From Coq Require Import List Lia Arith PeanoNat.
Import ListNotations.
Require Import Severity.

Section Repairs.
Variable E : Ctx.
Variable Haz : World -> Prop.

(* A VALIDATION is a capability whose only effect is to test psi: it
   fires exactly when psi holds and leaves the world unchanged.  In the
   pack language it is a tool with precondition psi and no effects. *)
Definition validates (a : CapN) (psi : World -> Prop) : Prop :=
  forall W W', E a W W' <-> (psi W /\ W' = W).

(* ----------------------------------------------------------------- *)
(*  GUARD.  A misselected branch that begins with a validation of its  *)
(*  own guard is stuck: the wrong choice costs budget but reaches      *)
(*  nothing.  So guarding a branch is as good as narrowing it away,    *)
(*  while keeping it available when it is intended.                    *)
(* ----------------------------------------------------------------- *)
Lemma guard_absorbs_misselection : forall a psi p Gl W c,
  validates a psi -> ~ Haz W -> ~ psi W ->
  safeT E Haz c (GAct a p Gl) W.
Proof.
  intros a psi p Gl W c Hv Hnh Hnp.
  apply ST_Act; [ exact Hnh | ].
  intros W' HE. apply Hv in HE. destruct HE as [Hp _]. contradiction.
Qed.

Theorem repair_guard_sound : forall b p q brs l psi Gl a W,
  validates a psi ->
  safeT E Haz b (GComm p q brs) W ->
  (psi W -> safeT E Haz b Gl W) ->
  safeT E Haz b (GComm p q ((l, psi, GAct a p Gl) :: brs)) W.
Proof.
  intros b p q brs l psi Gl a W Hv Hs Hint.
  inversion Hs as [ | | | b0 p0 q0 brs0 W0 Hnh Hok Hdev ]; subst.
  apply ST_Comm; [ exact Hnh | | ].
  - intros l' psi' Gl' Hin Hpsi. destruct Hin as [Heq | Hin].
    + inversion Heq; subst. apply ST_Act; [ exact Hnh | ].
      intros W' HE. apply Hv in HE. destruct HE as [_ HW]. subst W'.
      apply Hint. exact Hpsi.
    + eapply Hok; eauto.
  - intros l' psi' Gl' Hin Hpsi c Hb. destruct Hin as [Heq | Hin].
    + inversion Heq; subst. eapply guard_absorbs_misselection; eassumption.
    + eapply Hdev; eauto.
Qed.

(* the exact characterization: the guarded protocol is safe iff the
   narrowed one is and the branch is safe when intended *)
Theorem repair_guard_exact : forall b p q brs l psi Gl a W,
  validates a psi ->
  (safeT E Haz b (GComm p q ((l, psi, GAct a p Gl) :: brs)) W
   <-> (safeT E Haz b (GComm p q brs) W /\ (psi W -> safeT E Haz b Gl W))).
Proof.
  intros b p q brs l psi Gl a W Hv. split.
  - intro Hs. split.
    + eapply repair_narrow_sound; [ | exact Hs ].
      intros x Hx. right. exact Hx.
    + intro Hpsi.
      inversion Hs as [ | | | b0 p0 q0 brs0 W0 Hnh Hok Hdev ]; subst.
      specialize (Hok l psi (GAct a p Gl) (or_introl eq_refl) Hpsi).
      inversion Hok as [ | | b1 a1 p1 G1 W1 Hnh1 Hact | ]; subst.
      apply Hact. apply Hv. split; [ exact Hpsi | reflexivity ].
  - intros [Hs Hint]. apply repair_guard_sound; assumption.
Qed.

(* ----------------------------------------------------------------- *)
(*  REORDER.  Two capabilities COMMUTE when doing the second first     *)
(*  can be re-serialized as first-then-second with the same end world  *)
(*  (STRIPS effects on disjoint variables commute).  A capability is   *)
(*  HARMLESS when it never creates the hazard.                         *)
(* ----------------------------------------------------------------- *)
Definition commutes (a1 a2 : CapN) : Prop :=
  forall W W1 W2, E a2 W W1 -> E a1 W1 W2 ->
    exists W1', E a1 W W1' /\ E a2 W1' W2.

Definition harmless (a : CapN) : Prop :=
  forall W W', E a W W' -> Haz W' -> Haz W.

(* moving an irreversible action after a harmless action it commutes
   with never loses safety, at any budget and for any continuation *)
Theorem repair_reorder_sound : forall b p q irr chk G W,
  commutes irr chk -> harmless chk ->
  safeT E Haz b (GAct irr p (GAct chk q G)) W ->
  safeT E Haz b (GAct chk q (GAct irr p G)) W.
Proof.
  intros b p q irr chk G W Hcom Hharm Hs.
  inversion Hs as [ | | b0 a0 p0 G0 W0 Hnh Hirr | ]; subst.
  apply ST_Act; [ exact Hnh | ]. intros W1 Hchk.
  apply ST_Act.
  - intro Hh. apply Hnh. eapply Hharm; eauto.
  - intros W2 Hirr2.
    destruct (Hcom W W1 W2 Hchk Hirr2) as [W1' [Hirr' Hchk']].
    specialize (Hirr W1' Hirr').
    inversion Hirr as [ | | b1 a1 p1 G1 W3 Hnh1 Hchk3 | ]; subst.
    apply Hchk3. exact Hchk'.
Qed.

(* validations are harmless and commute with everything that preserves
   their predicate *)
Lemma validation_harmless : forall chk psi, validates chk psi -> harmless chk.
Proof.
  intros chk psi Hv W W' HE Hh. apply Hv in HE. destruct HE as [_ HW]. subst. exact Hh.
Qed.

Lemma validation_commutes : forall irr chk psi,
  validates chk psi ->
  (forall W W', E irr W W' -> psi W -> psi W') ->
  commutes irr chk.
Proof.
  intros irr chk psi Hv Hpres W W1 W2 Hchk Hirr.
  apply Hv in Hchk. destruct Hchk as [Hp HW]. subst W1.
  exists W2. split; [ exact Hirr | ]. apply Hv. split; [ eapply Hpres; eauto | reflexivity ].
Qed.

(* the exact characterizations, which show what reordering GAINS: the
   original protocol needs every irr-successor hazard-free; the reordered
   one needs nothing when the validation fails *)
Theorem reorder_original_exact : forall b p q irr chk psi G W,
  validates chk psi ->
  (safeT E Haz b (GAct irr p (GAct chk q G)) W
   <-> (~ Haz W /\ forall W1, E irr W W1 -> ~ Haz W1 /\ (psi W1 -> safeT E Haz b G W1))).
Proof.
  intros b p q irr chk psi G W Hv. split.
  - intro Hs. inversion Hs as [ | | b0 a0 p0 G0 W0 Hnh Hall | ]; subst.
    split; [ exact Hnh | ]. intros W1 Hirr. specialize (Hall W1 Hirr).
    inversion Hall as [ | | b1 a1 p1 G1 W2 Hnh1 Hchk | ]; subst.
    split; [ exact Hnh1 | ]. intro Hpsi. apply Hchk. apply Hv. split; [ exact Hpsi | reflexivity ].
  - intros [Hnh Hall]. apply ST_Act; [ exact Hnh | ]. intros W1 Hirr.
    destruct (Hall W1 Hirr) as [Hnh1 Hrest]. apply ST_Act; [ exact Hnh1 | ].
    intros W2 HE. apply Hv in HE. destruct HE as [Hpsi HW]. subst W2. apply Hrest. exact Hpsi.
Qed.

Theorem reorder_reordered_exact : forall b p q irr chk psi G W,
  validates chk psi ->
  (safeT E Haz b (GAct chk q (GAct irr p G)) W
   <-> (~ Haz W /\ (psi W -> forall W1, E irr W W1 -> safeT E Haz b G W1))).
Proof.
  intros b p q irr chk psi G W Hv. split.
  - intro Hs. inversion Hs as [ | | b0 a0 p0 G0 W0 Hnh Hall | ]; subst.
    split; [ exact Hnh | ]. intros Hpsi W1 Hirr.
    assert (HE : E chk W W) by (apply Hv; split; [ exact Hpsi | reflexivity ]).
    specialize (Hall W HE).
    inversion Hall as [ | | b1 a1 p1 G1 W2 Hnh1 Hirr1 | ]; subst.
    apply Hirr1. exact Hirr.
  - intros [Hnh Hrest]. apply ST_Act; [ exact Hnh | ]. intros W' HE.
    apply Hv in HE. destruct HE as [Hpsi HW]. subst W'.
    apply ST_Act; [ exact Hnh | ]. intros W1 Hirr. apply Hrest; assumption.
Qed.

(* the point of no return, removed: when the validation fails, the
   original protocol is untypable as soon as one irr-successor is a
   hazard, and the reordered one is typable at every budget *)
Theorem repair_reorder_pnr : forall b p q irr chk psi G W,
  validates chk psi -> ~ Haz W -> ~ psi W ->
  (exists W1, E irr W W1 /\ Haz W1) ->
  ~ safeT E Haz b (GAct irr p (GAct chk q G)) W /\
    safeT E Haz b (GAct chk q (GAct irr p G)) W.
Proof.
  intros b p q irr chk psi G W Hv Hnh Hnp [W1 [Hirr Hh1]]. split.
  - intro Hs. apply (reorder_original_exact b p q irr chk psi G W Hv) in Hs.
    destruct Hs as [_ Hall]. destruct (Hall W1 Hirr) as [Hnh1 _]. exact (Hnh1 Hh1).
  - apply (reorder_reordered_exact b p q irr chk psi G W Hv).
    split; [ exact Hnh | ]. intro Hpsi. contradiction.
Qed.

(* ----------------------------------------------------------------- *)
(*  COMPENSATE.  Appending a recovery path R to a residual Gl is safe  *)
(*  iff R is safe at every interface point of Gl (TC_seq), and it      *)
(*  turns a FUTILE residual BENIGN as soon as R reaches the goal from  *)
(*  one interface point.                                               *)
(* ----------------------------------------------------------------- *)
Theorem repair_compensate_sound : forall b Gl R W,
  safeT E Haz b Gl W ->
  (forall b' W', ends E b Gl W b' W' -> safeT E Haz b' R W') ->
  safeT E Haz b (gseq Gl R) W.
Proof. intros b Gl R W Hs Hall. eapply TC_seq; eauto. Qed.

Lemma ends_reach_gseq : forall (P : World -> Prop) b G1 W b' W' G2,
  ends E b G1 W b' W' -> reach_haz E P b' G2 W' -> reach_haz E P b (gseq G1 G2) W.
Proof.
  intros P b G1 W b' W' G2 Hen.
  induction Hen as [ b W | b a p G W W1 b' W2 HE Hen IH | b phi G W b' W' Hen IH
                   | b p q brs l psi Gl W b' W' Hin Hpsi Hen IH
                   | b p q brs l psi Gl W b' W' Hin Hpsi Hen IH ];
    intro Hr; simpl.
  - exact Hr.
  - eapply RH_act; eauto.
  - apply RH_goal; auto.
  - eapply RH_comm_ok; [ | exact Hpsi | apply IH; exact Hr ].
    apply in_map_iff. exists (l, psi, Gl). split; [ reflexivity | exact Hin ].
  - eapply RH_comm_dev; [ | exact Hpsi | apply IH; exact Hr ].
    apply in_map_iff. exists (l, psi, Gl). split; [ reflexivity | exact Hin ].
Qed.

Theorem repair_compensate_restores_goal : forall (Phi : World -> Prop) b Gl R W,
  safeT E Haz b Gl W ->
  (forall b' W', ends E b Gl W b' W' -> safeT E Haz b' R W') ->
  (exists b' W', ends E b Gl W b' W' /\ reach_haz E Phi b' R W') ->
  Benign E Haz Phi b (gseq Gl R) W.
Proof.
  intros Phi b Gl R W Hs Hall [b' [W' [Hen Hg]]]. unfold Benign. split.
  - apply TC_sound. eapply TC_seq; eauto.
  - eapply ends_reach_gseq; eauto.
Qed.

End Repairs.

(* ================================================================= *)
(*  Worked instance: the booking protocol whose fast path purchases    *)
(*  BEFORE verifying, and its reordered repair.  The capability        *)
(*  context is stated extensionally so that commutation is provable    *)
(*  without functional extensionality.                                 *)
(* ================================================================= *)
Definition E1 : Ctx := fun a W W' =>
  (a = 1 /\ W' verified = 1 /\ forall x, x <> verified -> W' x = W x) \/
  (a = 2 /\ W' booked = 1 /\ forall x, x <> booked -> W' x = W x).

Definition FastFirst : Gt := GAct 2 1 (GAct 1 1 GEnd).      (* purchase ; verify *)

Definition Gbad2 : Gt :=
  GComm 0 1 [ (10, (fun _ : World => True),  SafePath) ;
              (11, (fun _ : World => False), FastFirst) ].

Definition Greordered : Gt :=
  GComm 0 1 [ (10, (fun _ : World => True),  SafePath) ;
              (11, (fun _ : World => False), SafePath) ].

(* STRIPS effects on disjoint variables commute *)
Lemma commutes_verify_purchase : commutes E1 2 1.
Proof.
  intros W W1 W2 H1 H2.
  destruct H1 as [[_ [Hv Hrest1]] | [Hc _]]; [ | discriminate Hc ].
  destruct H2 as [[Hc _] | [_ [Hb Hrest2]]]; [ discriminate Hc | ].
  exists (wupd W booked 1). split.
  - right. split; [ reflexivity | ]. split; [ apply wupd_same | ].
    intros x Hx. apply wupd_other. exact Hx.
  - left. split; [ reflexivity | ]. split.
    + rewrite Hrest2; [ exact Hv | ]. unfold verified, booked. lia.
    + intros x Hx. destruct (Nat.eq_dec x booked) as [-> | Hxb].
      * rewrite Hb. rewrite wupd_same. reflexivity.
      * rewrite Hrest2 by exact Hxb. rewrite Hrest1 by exact Hx.
        rewrite wupd_other by exact Hxb. reflexivity.
Qed.

Lemma purchase_harmless_after_verify : forall W W', E1 1 W W' -> ~ Haz0 W'.
Proof.
  intros W W' HE [Hb Hv].
  destruct HE as [[_ [Hv' _]] | [Hc _]]; [ | discriminate Hc ]. congruence.
Qed.

Theorem Gbad2_not_1_tolerant : ~ safeT E1 Haz0 1 Gbad2 W0.
Proof.
  intro Hs. inversion Hs as [ | | | b0 p0 q0 brs0 W1 Hnh Hok Hdev ]; subst.
  specialize (Hdev 11 (fun _ => False) FastFirst (or_intror (or_introl eq_refl))
                   (fun H => H) 0 eq_refl).
  inversion Hdev as [ | | b1 a1 p1 G1 W2 Hnh1 Hall | ]; subst.
  specialize (Hall (wupd W0 booked 1)).
  assert (HE : E1 2 W0 (wupd W0 booked 1)).
  { right. split; [ reflexivity | ]. split; [ apply wupd_same | ].
    intros x Hx. apply wupd_other. exact Hx. }
  specialize (Hall HE).
  inversion Hall as [ | | b2 a2 p2 G2 W3 Hnh2 _ | ]; subst.
  apply Hnh2. unfold Haz0. split; [ apply wupd_same | ].
  rewrite wupd_other; [ reflexivity | unfold verified, booked; lia ].
Qed.

Lemma SafePath_E1_safe : forall k W, ~ Haz0 W -> safeT E1 Haz0 k SafePath W.
Proof.
  intros k W Hnh. apply ST_Act; [ exact Hnh | ]. intros W1 H1.
  assert (Hnh1 : ~ Haz0 W1) by (eapply purchase_harmless_after_verify; eauto).
  apply ST_Act; [ exact Hnh1 | ]. intros W2 H2.
  destruct H1 as [[_ [Hv1 _]] | [Hc _]]; [ | discriminate Hc ].
  destruct H2 as [[Hc _] | [_ [Hb2 Hrest2]]]; [ discriminate Hc | ].
  apply ST_End. intros [_ Hv2]. rewrite Hrest2 in Hv2; [ congruence | ].
  unfold verified, booked. lia.
Qed.

Theorem Greordered_is_k_tolerant : forall k, safeT E1 Haz0 k Greordered W0.
Proof.
  intro k. apply ST_Comm; [ exact notHaz_W0 | | ].
  - intros l psi Gl Hin _. destruct Hin as [Heq | [Heq | []]]; inversion Heq; subst;
      apply SafePath_E1_safe; exact notHaz_W0.
  - intros l psi Gl Hin _ c _. destruct Hin as [Heq | [Heq | []]]; inversion Heq; subst;
      apply SafePath_E1_safe; exact notHaz_W0.
Qed.

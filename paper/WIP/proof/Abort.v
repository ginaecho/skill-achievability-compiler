(* ================================================================= *)
(*  Abort.v -- the guard repair, in a runtime that can actually run   *)
(*  it.                                                               *)
(*                                                                     *)
(*  Repairs.v proves the guard and reorder repairs sound in an         *)
(*  ABORTING model: the validation always fires, and when its          *)
(*  predicate fails it diverts to an inert world.  Both theorems       *)
(*  carry the hypothesis `inert (ab W)`, which is a claim about the    *)
(*  runtime.  This file discharges it, on a capability model in which  *)
(*  every capability is enabled everywhere -- so nothing here is       *)
(*  vacuous -- and then exhibits a session that CONFORMS to the        *)
(*  repaired protocol, which is what the repair has to deliver and     *)
(*  what the blocking model could not.                                 *)
(*                                                                     *)
(*  Coq 8.18, stdlib only, axiom-free (see check_abort.v).             *)
(* ================================================================= *)
From Coq Require Import List Lia Arith PeanoNat.
Import ListNotations.
Require Import Severity.
Require Import Bridge.
Require Import Repairs.

(* the abort flag: a third state variable, distinct from verified and
   booked, that the runtime sets when a validation fails *)
Definition aborted : Var := 2.

Lemma vars_distinct : verified <> booked /\ verified <> aborted /\ booked <> aborted.
Proof. unfold verified, booked, aborted. repeat split; lia. Qed.

(* ----------------------------------------------------------------- *)
(*  E2: verify (1), purchase (2), validate-verified (3).               *)
(*                                                                     *)
(*  Every capability is enabled in every world.  In a live world it     *)
(*  has its STRIPS effect.  In an aborted world it is the identity --   *)
(*  the runtime keeps answering and the answers change nothing, which   *)
(*  is what a real runtime does after a failed check.  So E2 has no     *)
(*  halted world at all, and yet it has inert ones.                     *)
(* ----------------------------------------------------------------- *)
Definition E2 : Ctx := fun a W W' =>
  (W aborted <> 0 /\ W' = W) \/
  (W aborted = 0 /\ a = 1 /\ W' = wupd W verified 1) \/
  (W aborted = 0 /\ a = 2 /\ W' = wupd W booked 1) \/
  (W aborted = 0 /\ a = 3 /\ W verified = 1 /\ W' = W) \/
  (W aborted = 0 /\ a = 3 /\ W verified <> 1 /\ W' = wupd W aborted 1).

Definition psi2 : World -> Prop := fun W => W verified = 1.
Definition ab2  : World -> World := fun W => wupd W aborted 1.

(* the three capabilities of this runtime are enabled in EVERY world:
   in a live one they act, in an aborted one they are the identity.  So
   E2 has no halted world -- `halted`, the model the first draft used to
   absorb a failed validation, is satisfiable nowhere here. *)
Lemma E2_cap_enabled : forall a W, a = 1 \/ a = 2 \/ a = 3 -> exists W', E2 a W W'.
Proof.
  intros a W Ha. destruct (Nat.eq_dec (W aborted) 0) as [H0 | H0].
  - destruct Ha as [-> | [-> | ->]].
    + exists (wupd W verified 1). right. left. repeat split; assumption.
    + exists (wupd W booked 1). right. right. left. repeat split; assumption.
    + destruct (Nat.eq_dec (W verified) 1) as [Hv | Hv].
      * exists W. right. right. right. left. repeat split; assumption.
      * exists (wupd W aborted 1). right. right. right. right. repeat split; assumption.
  - exists W. left. split; [ exact H0 | reflexivity ].
Qed.

Lemma E2_no_halted : forall W, ~ halted E2 W.
Proof.
  intros W Hh. destruct (E2_cap_enabled 1 W (or_introl eq_refl)) as [W' HE].
  exact (Hh 1 W' HE).
Qed.

(* but it does have inert worlds: any aborted, hazard-free world *)
Lemma E2_idle_aborted : forall W, W aborted <> 0 -> idle E2 W.
Proof.
  intros W Ha a W' HE.
  destruct HE as [[_ Heq] | [[Hb _] | [[Hb _] | [[Hb _] | [Hb _]]]]];
    try (exfalso; exact (Ha Hb)). exact Heq.
Qed.

Lemma ab2_aborted : forall W, (ab2 W) aborted <> 0.
Proof. intro W. unfold ab2. rewrite wupd_same. discriminate. Qed.

Lemma ab2_preserves_haz : forall W, ~ Haz0 W -> ~ Haz0 (ab2 W).
Proof.
  intros W Hnh [Hb Hv]. apply Hnh. unfold ab2 in *. split.
  - rewrite wupd_other in Hb; [ exact Hb | unfold booked, aborted; lia ].
  - rewrite wupd_other in Hv; [ exact Hv | unfold verified, aborted; lia ].
Qed.

Theorem E2_inert_abort : forall W, ~ Haz0 W -> inert E2 Haz0 (ab2 W).
Proof.
  intros W Hnh. split.
  - apply ab2_preserves_haz. exact Hnh.
  - apply E2_idle_aborted. apply ab2_aborted.
Qed.

(* capability 3 is a validation of psi2 at every live world *)
Theorem E2_validates : forall W, W aborted = 0 -> validates_ab E2 3 psi2 ab2 W.
Proof.
  intros W Ha W'. unfold psi2, ab2. split.
  - intro HE.
    destruct HE as [ [Hb _] | [ [_ [Hc _]] | [ [_ [Hc _]] |
                     [ [_ [_ [Hv Heq]]] | [_ [_ [Hv Heq]]] ] ] ] ];
      try (exfalso; exact (Hb Ha)); try discriminate Hc.
    + left. split; [ exact Hv | exact Heq ].
    + right. split; [ exact Hv | exact Heq ].
  - intros [[Hv ->] | [Hv ->]].
    + right. right. right. left. repeat split; assumption.
    + right. right. right. right. repeat split; assumption.
Qed.

(* ----------------------------------------------------------------- *)
(*  The protocol, before and after the guard repair.                   *)
(* ----------------------------------------------------------------- *)
Definition Gbad3 : Gt :=
  GComm 0 1 [ (10, (fun _ : World => True), SafePath) ;
              (11, psi2, FastPath) ].

Definition Gguarded : Gt :=
  GComm 0 1 [ (10, (fun _ : World => True), SafePath) ;
              (11, psi2, GAct 3 1 FastPath) ].

Definition W2 : World := fun _ => 0.

Lemma notHaz_W2 : ~ Haz0 W2.
Proof. intros [Hb _]. unfold W2 in Hb. discriminate. Qed.

Lemma W2_live : W2 aborted = 0. Proof. reflexivity. Qed.
Lemma W2_unverified : ~ psi2 W2. Proof. unfold psi2, W2. discriminate. Qed.

(* one misselection on the unguarded protocol reaches the hazard *)
Theorem Gbad3_not_1_tolerant : ~ safeT E2 Haz0 1 Gbad3 W2.
Proof.
  intro Hs. inversion Hs as [ | | | b0 p0 q0 brs0 W' Hnh Hok Hdev ]; subst.
  specialize (Hdev 11 psi2 FastPath (or_intror (or_introl eq_refl)) W2_unverified 0 eq_refl).
  inversion Hdev as [ | | b1 a1 p1 G1 W1 Hnh1 Hall | ]; subst.
  specialize (Hall (wupd W2 booked 1)).
  assert (HE : E2 2 W2 (wupd W2 booked 1))
    by (right; right; left; split; [ reflexivity | split; reflexivity ]).
  specialize (Hall HE).
  inversion Hall as [ | | | ]; subst.
  match goal with [ H : ~ Haz0 (wupd W2 booked 1) |- _ ] => apply H end.
  unfold Haz0. split; [ apply wupd_same | ].
  rewrite wupd_other; [ reflexivity | unfold verified, booked; lia ].
Qed.

(* the safe path is safe from any live, hazard-free world *)
Lemma SafePath_E2_safe : forall k W, ~ Haz0 W -> safeT E2 Haz0 k SafePath W.
Proof.
  intros k W Hnh. apply ST_Act; [ exact Hnh | ]. intros W1 H1.
  destruct H1 as [[Ha Heq] | [[Ha [_ Heq]] | [[_ [Hc _]] | [[_ [Hc _]] | [_ [Hc _]]]]]];
    try discriminate Hc.
  - (* already aborted: inert, so everything is safe *)
    subst W1. apply (safeT_inert E2 Haz0). split; [ exact Hnh | ].
    apply E2_idle_aborted. exact Ha.
  - (* verified is now set, so purchasing cannot create the hazard *)
    subst W1. apply ST_Act.
    + intros [_ Hv]. rewrite wupd_same in Hv. discriminate.
    + intros W2' H2.
      destruct H2 as [[Ha2 Heq2] | [[_ [Hc _]] | [[Ha2 [_ Heq2]] | [[_ [Hc _]] | [_ [Hc _]]]]]];
        try discriminate Hc.
      * subst W2'. apply ST_End. intros [_ Hv]. rewrite wupd_same in Hv. discriminate.
      * subst W2'. apply ST_End. intros [_ Hv].
        rewrite wupd_other in Hv; [ | unfold verified, booked; lia ].
        rewrite wupd_same in Hv. discriminate.
Qed.

(* THE REPAIR WORKS, at every budget, in a model with no halted world *)
Theorem Gguarded_is_k_tolerant : forall k, safeT E2 Haz0 k Gguarded W2.
Proof.
  intro k. apply ST_Comm; [ exact notHaz_W2 | | ].
  - intros l psi Gl Hin Hpsi. destruct Hin as [Heq | [Heq | []]]; inversion Heq; subst.
    + apply SafePath_E2_safe. exact notHaz_W2.
    + exfalso. exact (W2_unverified Hpsi).
  - intros l psi Gl Hin Hnpsi c Hb. destruct Hin as [Heq | [Heq | []]]; inversion Heq; subst.
    + exfalso. apply Hnpsi. exact I.
    + eapply (guard_absorbs_misselection_ab E2 Haz0 3 psi2 ab2).
      * apply E2_validates. exact W2_live.
      * exact notHaz_W2.
      * exact W2_unverified.
      * apply E2_inert_abort. exact notHaz_W2.
Qed.

(* ----------------------------------------------------------------- *)
(*  AND IT IS INHABITED.  This is the obligation the blocking model     *)
(*  could not meet: CT_Act asks for a successor, and in the blocking    *)
(*  model the validation has none in exactly the worlds the repair      *)
(*  addresses.  Here it always has one.                                 *)
(* ----------------------------------------------------------------- *)
Definition WGuard : Proc := PAct 3 (PAct 2 PEnd).

Definition MGuarded : Sess :=
  sess2 (POut 1 [(10, PEnd); (11, PEnd)])
        (PIn  0 [(10, WSafe); (11, WGuard)]).

Theorem Gguarded_inhabited : forall W, ctypes E2 Gguarded MGuarded W.
Proof.
  intro W. apply CT_Comm with [(10, PEnd); (11, PEnd)] [(10, WSafe); (11, WGuard)].
  - discriminate.
  - apply sess2_0.
  - apply sess2_1.
  - discriminate.
  - intros l psi Gl Hin. destruct Hin as [Heq | [Heq | []]]; inversion Heq; subst.
    + exists PEnd. left. reflexivity.
    + exists PEnd. right. left. reflexivity.
  - intros l P Hin. destruct Hin as [Heq | [Heq | []]]; inversion Heq; subst.
    + exists (fun _ : World => True), SafePath. left. reflexivity.
    + exists psi2, (GAct 3 1 FastPath). right. left. reflexivity.
  - intros l psi Gl Hin. destruct Hin as [Heq | [Heq | []]]; inversion Heq; subst.
    + exists WSafe. left. reflexivity.
    + exists WGuard. right. left. reflexivity.
  - intros l psi Gl P Q Hin HP HQ.
    destruct Hin as [Heq | [Heq | []]]; inversion Heq; subst.
    + destruct HP as [HP | [HP | []]]; inversion HP; subst;
        destruct HQ as [HQ | [HQ | []]]; inversion HQ; subst.
      apply CT_Act with (PAct 2 PEnd).
      * unfold supd, MGuarded, sess2, WSafe, WGuard;
          repeat destruct (Nat.eq_dec _ _); congruence.
      * apply E2_cap_enabled; auto.
      * intros W' _. apply CT_Act with PEnd.
        -- apply supd_same.
        -- apply E2_cap_enabled; auto.
        -- intros W'' _. apply CT_End. intro r.
           unfold supd, MGuarded, sess2, WSafe, WGuard;
             repeat destruct (Nat.eq_dec _ _); congruence.
    + destruct HP as [HP | [HP | []]]; inversion HP; subst;
        destruct HQ as [HQ | [HQ | []]]; inversion HQ; subst.
      apply CT_Act with (PAct 2 PEnd).
      * unfold supd, MGuarded, sess2, WSafe, WGuard;
          repeat destruct (Nat.eq_dec _ _); congruence.
      * apply E2_cap_enabled; auto.
      * intros W' _. apply CT_Act with PEnd.
        -- apply supd_same.
        -- apply E2_cap_enabled; auto.
        -- intros W'' _. apply CT_End. intro r.
           unfold supd, MGuarded, sess2, WSafe, WGuard;
             repeat destruct (Nat.eq_dec _ _); congruence.
Qed.

(* the bridge, on the repaired protocol, is a statement about a session
   that exists: at every budget, every run of MGuarded is hazard-free *)
Corollary Gguarded_bridge_nonvacuous : forall k tr G' s' W',
  hrun E2 Gguarded MGuarded W2 tr G' s' W' -> total tr <= k -> ~ Haz0 W'.
Proof.
  intros k tr G' s' W' Hr Ht.
  destruct (bridge_run E2 Haz0 Gguarded MGuarded W2 tr G' s' W' k
              (Gguarded_inhabited W2) (Gguarded_is_k_tolerant k) Hr Ht) as [H _].
  exact H.
Qed.

(* ----------------------------------------------------------------- *)
(*  The congruence is not degenerate either: here is a repair applied  *)
(*  under a real context, with its premise discharged.                 *)
(* ----------------------------------------------------------------- *)
Lemma SafePath_safe_anywhere : forall b W, ~ Haz0 W -> safeT E0 Haz0 b SafePath W.
Proof.
  intros b W Hnh. apply ST_Act; [ exact Hnh | ]. intros W1 H1.
  destruct H1 as [[_ ->] | [Hc _]]; [ | discriminate Hc ].
  assert (Hnh1 : ~ Haz0 (wupd W verified 1))
    by (intros [_ Hv]; rewrite wupd_same in Hv; discriminate).
  apply ST_Act; [ exact Hnh1 | ]. intros W2 H2.
  destruct H2 as [[Hc _] | [_ ->]]; [ discriminate Hc | ].
  assert (Hnh2 : ~ Haz0 (wupd (wupd W verified 1) booked 1)).
  { intros [_ Hv]. rewrite wupd_other in Hv; [ | unfold verified, booked; lia ].
    rewrite wupd_same in Hv. discriminate. }
  apply ST_End. exact Hnh2.
Qed.

(* verify, and only then choose: the choice sits one action below the root *)
Definition Cverify : Cx := CAct 1 1 CHole.

Lemma plug_Cverify_wide : safeT E0 Haz0 0 (plug Cverify Gbad) W0.
Proof.
  simpl. apply ST_Act; [ exact notHaz_W0 | ]. intros W1 H1.
  destruct H1 as [[_ ->] | [Hc _]]; [ | discriminate Hc ].
  assert (Hnh1 : ~ Haz0 (wupd W0 verified 1))
    by (intros [_ Hv]; rewrite wupd_same in Hv; discriminate).
  apply ST_Comm; [ exact Hnh1 | | ].
  - intros l psi Gl Hin Hpsi. destruct Hin as [Heq | [Heq | []]]; inversion Heq; subst.
    + apply SafePath_safe_anywhere. exact Hnh1.
    + exfalso. exact Hpsi.
  - intros l psi Gl Hin Hnpsi c Hb. discriminate Hb.
Qed.

Theorem congruence_is_not_degenerate :
  plug Cverify Gbad <> Gbad /\
  safeT E0 Haz0 0 (plug Cverify Gbad) W0 /\
  safeT E0 Haz0 0 (plug Cverify Ggood) W0.
Proof.
  repeat split.
  - discriminate.
  - apply plug_Cverify_wide.
  - apply (repair_narrow_anywhere E0 Haz0 Cverify 0 0 1
             [ (10, (fun _ : World => True), SafePath) ;
               (11, (fun _ : World => False), FastPath) ]
             [ (10, (fun _ : World => True), SafePath) ] W0).
    + intros x Hx. destruct Hx as [Heq | []]. left. exact Heq.
    + apply plug_Cverify_wide.
Qed.

(* ================================================================= *)
(*  WHAT THE GUARD AND REORDER REPAIRS ACTUALLY REQUIRE.               *)
(*                                                                     *)
(*  inert is a strong condition and it is doing all the work: it       *)
(*  says EVERY capability is the identity in the abort world, for      *)
(*  ever.  That is not a runtime that answers with errors; it is a     *)
(*  session that is over.  E4 below is the weaker reading -- the       *)
(*  validation is live at every world, the abort flag                  *)
(*  records the failure, and every other tool keeps working -- and     *)
(*  there the guard repair does not hold.  So the repairs are not      *)
(*  about a gate that reports a failure; they are about a gate that    *)
(*  stops the session, and a deployment that only errors the call      *)
(*  does not get the theorem.                                          *)
(* ================================================================= *)
Definition E4 : Ctx := fun a W W' =>
  (a = 1 /\ W' = wupd W verified 1) \/
  (a = 2 /\ W' = wupd W booked 1) \/
  (a = 3 /\ W verified = 1 /\ W' = W) \/
  (a = 3 /\ W verified <> 1 /\ W' = wupd W aborted 1).

(* the validation is a real validation, at EVERY world -- which is more
   than E2 gives, so E4 is not a weaker runtime, only a differently
   shaped one *)
Theorem E4_validates : forall W, validates_ab E4 3 psi2 ab2 W.
Proof.
  intros W W'. unfold psi2, ab2. split.
  - intro HE.
    destruct HE as [[Hc _] | [[Hc _] | [[_ [Hv Heq]] | [_ [Hv Heq]]]]];
      try discriminate Hc.
    + left. split; assumption.
    + right. split; assumption.
  - intros [[Hv ->] | [Hv ->]].
    + right. right. left. repeat split; assumption.
    + right. right. right. repeat split; assumption.
Qed.

Theorem E4_no_halted : forall W, ~ halted E4 W.
Proof.
  intros W Hh. apply (Hh 1 (wupd W verified 1)). left. split; reflexivity.
Qed.

(* and it has no inert world where it matters: purchase still fires *)
Theorem E4_not_idle : forall W, W booked = 0 -> ~ idle E4 W.
Proof.
  intros W Hb Hi.
  assert (HE : E4 2 W (wupd W booked 1)) by (right; left; split; reflexivity).
  apply Hi in HE.
  assert (H1 : wupd W booked 1 booked = W booked) by (rewrite HE; reflexivity).
  rewrite wupd_same in H1. rewrite Hb in H1. discriminate.
Qed.

(* THE NON-EXAMPLE.  Same protocol, same validation, same repair; the
   only difference is that the runtime keeps working after the failed
   check, and the guard no longer absorbs the misselection. *)
Theorem Gguarded_not_1_tolerant_in_E4 : ~ safeT E4 Haz0 1 Gguarded W2.
Proof.
  intro Hs. inversion Hs as [ | | | b0 p0 q0 brs0 W' Hnh Hok Hdev ]; subst.
  specialize (Hdev 11 psi2 (GAct 3 1 FastPath)
                   (or_intror (or_introl eq_refl)) W2_unverified 0 eq_refl).
  inversion Hdev as [ | | b1 a1 p1 G1 W1 Hnh1 Hall | ]; subst.
  assert (HE3 : E4 3 W2 (wupd W2 aborted 1))
    by (right; right; right; split; [ reflexivity | split; [ discriminate | reflexivity ] ]).
  specialize (Hall _ HE3).
  inversion Hall as [ | | b2 a2 p2 G2 W3 Hnh2 Hall2 | ]; subst.
  assert (HE2 : E4 2 (wupd W2 aborted 1) (wupd (wupd W2 aborted 1) booked 1))
    by (right; left; split; reflexivity).
  specialize (Hall2 _ HE2).
  inversion Hall2 as [ b3 W4 Hnh3 | | | ]; subst.
  apply Hnh3. unfold Haz0. split.
  - apply wupd_same.
  - rewrite wupd_other; [ | unfold verified, booked; lia ].
    rewrite wupd_other; [ reflexivity | unfold verified, aborted; lia ].
Qed.

(* the reorder repair fails there for the same reason *)
Theorem reordered_not_tolerant_in_E4 : forall k,
  ~ safeT E4 Haz0 k (GAct 3 1 (GAct 2 1 GEnd)) W2.
Proof.
  intros k Hs.
  inversion Hs as [ | | b1 a1 p1 G1 W1 Hnh1 Hall | ]; subst.
  assert (HE3 : E4 3 W2 (wupd W2 aborted 1))
    by (right; right; right; split; [ reflexivity | split; [ discriminate | reflexivity ] ]).
  specialize (Hall _ HE3).
  inversion Hall as [ | | b2 a2 p2 G2 W3 Hnh2 Hall2 | ]; subst.
  assert (HE2 : E4 2 (wupd W2 aborted 1) (wupd (wupd W2 aborted 1) booked 1))
    by (right; left; split; reflexivity).
  specialize (Hall2 _ HE2).
  inversion Hall2 as [ b3 W4 Hnh3 | | | ]; subst.
  apply Hnh3. unfold Haz0. split.
  - apply wupd_same.
  - rewrite wupd_other; [ | unfold verified, booked; lia ].
    rewrite wupd_other; [ reflexivity | unfold verified, aborted; lia ].
Qed.

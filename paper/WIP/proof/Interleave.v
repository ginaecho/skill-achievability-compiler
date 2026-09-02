(* ================================================================= *)
(*  Interleave.v -- BYSTANDER INTERLEAVINGS.                          *)
(*                                                                     *)
(*  The head-move semantics lets only the role(s) named by the global  *)
(*  type's head act.  An ungated deployment may let a BYSTANDER -- a   *)
(*  role the head does not involve -- fire its next capability early.  *)
(*  This file gives the permutation ("swap") relation under which a   *)
(*  bystander action moves earlier, the SEMANTIC independence          *)
(*  conditions that make the swap safe, and proves:                    *)
(*    swap_safe        the condition is preserved by every safe swap;  *)
(*    swap_ctypes      typing is preserved by every safe swap;         *)
(*    bridge_interleaved   a typed session is hazard-free within       *)
(*                     budget on every INTERLEAVED run;                *)
(*    strips_*         a SYNTACTIC sufficient condition (variable      *)
(*                     disjointness of STRIPS effects) discharges the   *)
(*                     semantic conditions -- what the tool checks.     *)
(*  Coq 8.18, stdlib only, axiom-free (check_interleave.v).            *)
(* ================================================================= *)
From Coq Require Import List Lia Arith PeanoNat.
Import ListNotations.
Require Import Severity.
Require Import Bridge.

Section Interleave.
Variable E : Ctx.
Variable Haz : World -> Prop.

(* ---- semantic independence ---- *)
(* a-then-b re-serializes as b-then-a with the same end world *)
Definition commute_ab (a b : CapN) : Prop :=
  forall W W1 W2, E a W W1 -> E b W1 W2 -> exists W1', E b W W1' /\ E a W1' W2.
(* a never changes whether the world is a hazard *)
Definition neutral (a : CapN) : Prop :=
  forall W W', E a W W' -> (Haz W <-> Haz W').
(* a never changes the truth of psi *)
Definition preserves (a : CapN) (psi : World -> Prop) : Prop :=
  forall W W', E a W W' -> (psi W <-> psi W').
(* a never changes whether b is enabled *)
Definition enables (a b : CapN) : Prop :=
  forall W W', E a W W' -> ((exists W2, E b W W2) <-> (exists W2, E b W' W2)).

Definition guard_br (a : CapN) (r : Role) (br : Lab * (World -> Prop) * Gt) :=
  (fst (fst br), snd (fst br), GAct a r (snd br)).

(* two communications between disjoint role pairs: p->q over ls, then r->s
   over ms, with continuation K l m; and the other order *)
Definition inner_brs (K : Lab -> Lab -> Gt) (l : Lab) (ms : list (Lab * (World -> Prop))) :=
  map (fun mp => (fst mp, snd mp, K l (fst mp))) ms.
Definition orig_cc (r s : Role) (K : Lab -> Lab -> Gt) ms (ls : list (Lab * (World -> Prop))) :=
  map (fun lp => (fst lp, snd lp, GComm r s (inner_brs K (fst lp) ms))) ls.
Definition inner_brs' (K : Lab -> Lab -> Gt) (m : Lab) (ls : list (Lab * (World -> Prop))) :=
  map (fun lp => (fst lp, snd lp, K (fst lp) m)) ls.
Definition new_cc (p q : Role) (K : Lab -> Lab -> Gt) ls (ms : list (Lab * (World -> Prop))) :=
  map (fun mp => (fst mp, snd mp, GComm p q (inner_brs' K (fst mp) ls))) ms.

(* ---- one swap: independent nodes exchange places (either direction) ---- *)
Inductive swap1 : Gt -> Gt -> Prop :=
| SW_act : forall a r b q G,
    r <> q -> neutral a -> commute_ab a b -> enables a b -> enables b a ->
    swap1 (GAct b q (GAct a r G)) (GAct a r (GAct b q G))
| SW_comm : forall a r p q brs,
    r <> p -> r <> q -> neutral a ->
    (forall l psi Gl, In (l, psi, Gl) brs -> preserves a psi) ->
    swap1 (GComm p q (map (guard_br a r) brs)) (GAct a r (GComm p q brs))
| SW_goal : forall a r phi G,
    preserves a phi ->
    swap1 (GGoal phi (GAct a r G)) (GAct a r (GGoal phi G))
| SW_comm_rev : forall a r p q brs,
    r <> p -> r <> q -> neutral a ->
    (forall l psi Gl, In (l, psi, Gl) brs -> preserves a psi) ->
    swap1 (GAct a r (GComm p q brs)) (GComm p q (map (guard_br a r) brs))
| SW_goal_rev : forall a r phi G,
    preserves a phi ->
    swap1 (GAct a r (GGoal phi G)) (GGoal phi (GAct a r G))
| SW_comm_comm : forall p q r s ls ms K,
    p <> r -> p <> s -> q <> r -> q <> s ->
    swap1 (GComm p q (orig_cc r s K ms ls)) (GComm r s (new_cc p q K ls ms))
| SW_under_act : forall a p G G',
    swap1 G G' -> swap1 (GAct a p G) (GAct a p G')
| SW_under_goal : forall phi G G',
    swap1 G G' -> swap1 (GGoal phi G) (GGoal phi G')
| SW_under_comm : forall p q brs1 brs2 l psi Gl Gl',
    swap1 Gl Gl' ->
    swap1 (GComm p q (brs1 ++ (l, psi, Gl) :: brs2))
          (GComm p q (brs1 ++ (l, psi, Gl') :: brs2)).

Lemma in_guard_br : forall a r l psi Gl brs,
  In (l, psi, Gl) brs -> In (l, psi, GAct a r Gl) (map (guard_br a r) brs).
Proof.
  intros a r l psi Gl brs Hin. apply in_map_iff. exists (l, psi, Gl). split; [ reflexivity | exact Hin ].
Qed.

Lemma in_guard_br_inv : forall a r l psi X brs,
  In (l, psi, X) (map (guard_br a r) brs) -> exists Gl, In (l, psi, Gl) brs /\ X = GAct a r Gl.
Proof.
  intros a r l psi X brs Hin. apply in_map_iff in Hin.
  destruct Hin as [[[l0 psi0] Gl0] [Heq Hin0]]. simpl in Heq. inversion Heq; subst.
  exists Gl0. split; [ exact Hin0 | reflexivity ].
Qed.

Lemma in_inner : forall K l ms m phi X,
  In (m, phi, X) (inner_brs K l ms) -> In (m, phi) ms /\ X = K l m.
Proof.
  intros K l ms m phi X H. apply in_map_iff in H. destruct H as [[m0 phi0] [Heq Hin]].
  simpl in Heq. inversion Heq; subst. split; [ exact Hin | reflexivity ].
Qed.
Lemma in_inner_intro : forall K l ms m phi,
  In (m, phi) ms -> In (m, phi, K l m) (inner_brs K l ms).
Proof. intros. apply in_map_iff. exists (m, phi). split; [ reflexivity | assumption ]. Qed.
Lemma in_inner' : forall K m ls l psi X,
  In (l, psi, X) (inner_brs' K m ls) -> In (l, psi) ls /\ X = K l m.
Proof.
  intros K m ls l psi X H. apply in_map_iff in H. destruct H as [[l0 psi0] [Heq Hin]].
  simpl in Heq. inversion Heq; subst. split; [ exact Hin | reflexivity ].
Qed.
Lemma in_inner'_intro : forall K m ls l psi,
  In (l, psi) ls -> In (l, psi, K l m) (inner_brs' K m ls).
Proof. intros. apply in_map_iff. exists (l, psi). split; [ reflexivity | assumption ]. Qed.
Lemma in_orig : forall r s K ms ls l psi X,
  In (l, psi, X) (orig_cc r s K ms ls) -> In (l, psi) ls /\ X = GComm r s (inner_brs K l ms).
Proof.
  intros r s K ms ls l psi X H. apply in_map_iff in H. destruct H as [[l0 psi0] [Heq Hin]].
  simpl in Heq. inversion Heq; subst. split; [ exact Hin | reflexivity ].
Qed.
Lemma in_orig_intro : forall r s K ms ls l psi,
  In (l, psi) ls -> In (l, psi, GComm r s (inner_brs K l ms)) (orig_cc r s K ms ls).
Proof. intros. apply in_map_iff. exists (l, psi). split; [ reflexivity | assumption ]. Qed.
Lemma in_new : forall p q K ls ms m phi Y,
  In (m, phi, Y) (new_cc p q K ls ms) -> In (m, phi) ms /\ Y = GComm p q (inner_brs' K m ls).
Proof.
  intros p q K ls ms m phi Y H. apply in_map_iff in H. destruct H as [[m0 phi0] [Heq Hin]].
  simpl in Heq. inversion Heq; subst. split; [ exact Hin | reflexivity ].
Qed.
Lemma in_new_intro : forall p q K ls ms m phi,
  In (m, phi) ms -> In (m, phi, GComm p q (inner_brs' K m ls)) (new_cc p q K ls ms).
Proof. intros. apply in_map_iff. exists (m, phi). split; [ reflexivity | assumption ]. Qed.
Lemma map_nonnil : forall (A B : Type) (f : A -> B) l, l <> nil -> map f l <> nil.
Proof. intros A B f [ | x t ] H; [ contradiction | discriminate ]. Qed.
Lemma map_nonnil_inv : forall (A B : Type) (f : A -> B) l, map f l <> nil -> l <> nil.
Proof. intros A B f [ | x t ] H; [ exfalso; apply H; reflexivity | discriminate ]. Qed.

Lemma in_mid : forall (A : Type) (x y : A) l1 l2,
  In x (l1 ++ y :: l2) -> In x l1 \/ x = y \/ In x l2.
Proof.
  intros A x y l1 l2 H. apply in_app_or in H. destruct H as [H | [H | H]]; auto.
Qed.

Lemma in_mid_l : forall (A : Type) (x : A) l1 y l2, In x l1 -> In x (l1 ++ y :: l2).
Proof. intros. apply in_or_app. left. assumption. Qed.
Lemma in_mid_m : forall (A : Type) (y : A) l1 l2, In y (l1 ++ y :: l2).
Proof. intros. apply in_or_app. right. left. reflexivity. Qed.
Lemma in_mid_r : forall (A : Type) (x : A) l1 y l2, In x l2 -> In x (l1 ++ y :: l2).
Proof. intros. apply in_or_app. right. right. assumption. Qed.

(* ================================================================= *)
(*  Safe swaps preserve the condition.                                 *)
(* ================================================================= *)
Theorem swap_safe : forall G G', swap1 G G' ->
  forall b W, safeT E Haz b G W -> safeT E Haz b G' W.
Proof.
  intros G G' Hsw.
  induction Hsw as [ a r b q G Hrq Hneu Hcom Hen1 Hen2
                   | a r p q brs Hrp Hrq Hneu Hpres
                   | a r phi G Hpres
                   | a r p q brs Hrp Hrq Hneu Hpres
                   | a r phi G Hpres
                   | p q r s ls ms K Hpr Hps Hqr Hqs
                   | a p G G' Hsw IH
                   | phi G G' Hsw IH
                   | p q brs1 brs2 l psi Gl Gl' Hsw IH ]; intros b0 W Hs.
  - inversion Hs as [ | | b1 a1 p1 G1 W1 Hnh Hall | ]; subst.
    apply ST_Act; [ exact Hnh | ]. intros W1' Ha.
    apply ST_Act.
    + intro Hh. apply Hnh. apply (proj2 (Hneu W W1' Ha)). exact Hh.
    + intros W2 Hb. destruct (Hcom W W1' W2 Ha Hb) as [W1 [Hb1 Ha1]].
      specialize (Hall W1 Hb1).
      inversion Hall as [ | | b2 a2 p2 G2 W3 Hnh1 Hall1 | ]; subst.
      apply Hall1. exact Ha1.
  - inversion Hs as [ | | | b1 p1 q1 brs1 W1 Hnh Hok Hdev ]; subst.
    apply ST_Act; [ exact Hnh | ]. intros W' Ha.
    apply ST_Comm.
    + intro Hh. apply Hnh. apply (proj2 (Hneu W W' Ha)). exact Hh.
    + intros l psi Gl Hin Hpsi.
      assert (HpsiW : psi W) by (apply (proj2 (Hpres l psi Gl Hin W W' Ha)); exact Hpsi).
      specialize (Hok l psi (GAct a r Gl) (in_guard_br a r l psi Gl brs Hin) HpsiW).
      inversion Hok as [ | | b2 a2 p2 G2 W2 Hnh1 Hall1 | ]; subst.
      apply Hall1. exact Ha.
    + intros l psi Gl Hin Hnpsi c Hb.
      assert (HnW : ~ psi W).
      { intro HW. apply Hnpsi. apply (proj1 (Hpres l psi Gl Hin W W' Ha)). exact HW. }
      specialize (Hdev l psi (GAct a r Gl) (in_guard_br a r l psi Gl brs Hin) HnW c Hb).
      inversion Hdev as [ | | b2 a2 p2 G2 W2 Hnh1 Hall1 | ]; subst.
      apply Hall1. exact Ha.
  - inversion Hs as [ | b1 phi1 G1 W1 Hnh Hs' | | ]; subst.
    inversion Hs' as [ | | b2 a2 p2 G2 W2 Hnh1 Hall | ]; subst.
    apply ST_Act; [ exact Hnh | ]. intros W' Ha. apply ST_Goal.
    + eapply safeT_not_haz. apply Hall. exact Ha.
    + apply Hall. exact Ha.
  - (* SW_comm_rev *)
    inversion Hs as [ | | b1 a1 p1 G1 W1 Hnh Hall | ]; subst.
    apply ST_Comm; [ exact Hnh | | ].
    + intros l psi X Hin Hpsi. apply in_guard_br_inv in Hin. destruct Hin as [Gl [Hin HX]]. subst X.
      apply ST_Act; [ exact Hnh | ]. intros W' Ha.
      specialize (Hall W' Ha). inversion Hall as [ | | | b2 p2 q2 brs2 W2 Hnh' Hok Hdev ]; subst.
      apply (Hok l psi Gl Hin). apply (proj1 (Hpres l psi Gl Hin W W' Ha)). exact Hpsi.
    + intros l psi X Hin Hnpsi c Hb. apply in_guard_br_inv in Hin. destruct Hin as [Gl [Hin HX]]. subst X.
      apply ST_Act; [ exact Hnh | ]. intros W' Ha.
      specialize (Hall W' Ha). inversion Hall as [ | | | b2 p2 q2 brs2 W2 Hnh' Hok Hdev ]; subst.
      apply (Hdev l psi Gl Hin); [ | first [ exact Hb | reflexivity ] ].
      intro HW'. apply Hnpsi. apply (proj2 (Hpres l psi Gl Hin W W' Ha)). exact HW'.
  - (* SW_goal_rev *)
    inversion Hs as [ | | b1 a1 p1 G1 W1 Hnh Hall | ]; subst.
    apply ST_Goal; [ exact Hnh | ]. apply ST_Act; [ exact Hnh | ]. intros W' Ha.
    specialize (Hall W' Ha). inversion Hall as [ | b2 phi2 G2 W2 Hnh' Hs' | | ]; subst. exact Hs'.
  - (* SW_comm_comm *)
    inversion Hs as [ | | | b1 p1 q1 brs1 W1 Hnh Hok Hdev ]; subst.
    apply ST_Comm; [ exact Hnh | | ].
    + intros m phi Y Hin Hphi. apply in_new in Hin. destruct Hin as [Hm HY]. subst Y.
      apply ST_Comm; [ exact Hnh | | ].
      * intros l psi X Hin Hpsi. apply in_inner' in Hin. destruct Hin as [Hl HX]. subst X.
        specialize (Hok _ _ _ (in_orig_intro r s K ms ls l psi Hl) Hpsi).
        inversion Hok as [ | | | b2 p2 q2 brs2 W2 Hnh' Hok' Hdev' ]; subst.
        apply (Hok' m phi (K l m) (in_inner_intro K l ms m phi Hm) Hphi).
      * intros l psi X Hin Hnpsi c Hb. apply in_inner' in Hin. destruct Hin as [Hl HX]. subst X.
        specialize (Hdev _ _ _ (in_orig_intro r s K ms ls l psi Hl) Hnpsi c Hb).
        inversion Hdev as [ | | | b2 p2 q2 brs2 W2 Hnh' Hok' Hdev' ]; subst.
        apply (Hok' m phi (K l m) (in_inner_intro K l ms m phi Hm) Hphi).
    + intros m phi Y Hin Hnphi c Hb. apply in_new in Hin. destruct Hin as [Hm HY]. subst Y.
      apply ST_Comm; [ exact Hnh | | ].
      * intros l psi X Hin Hpsi. apply in_inner' in Hin. destruct Hin as [Hl HX]. subst X.
        specialize (Hok _ _ _ (in_orig_intro r s K ms ls l psi Hl) Hpsi).
        inversion Hok as [ | | | b2 p2 q2 brs2 W2 Hnh' Hok' Hdev' ]; subst.
        apply (Hdev' m phi (K l m) (in_inner_intro K l ms m phi Hm) Hnphi c); first [ exact Hb | reflexivity ].
      * intros l psi X Hin Hnpsi c' Hc. apply in_inner' in Hin. destruct Hin as [Hl HX]. subst X.
        specialize (Hdev _ _ _ (in_orig_intro r s K ms ls l psi Hl) Hnpsi c Hb).
        inversion Hdev as [ | | | b2 p2 q2 brs2 W2 Hnh' Hok' Hdev' ]; subst.
        apply (Hdev' m phi (K l m) (in_inner_intro K l ms m phi Hm) Hnphi c'); first [ exact Hc | reflexivity ].
  - inversion Hs as [ | | b1 a1 p1 G1 W1 Hnh Hall | ]; subst.
    apply ST_Act; [ exact Hnh | ]. intros W' Ha. apply IH. apply Hall. exact Ha.
  - inversion Hs as [ | b1 phi1 G1 W1 Hnh Hs' | | ]; subst.
    apply ST_Goal; [ exact Hnh | apply IH; exact Hs' ].
  - inversion Hs as [ | | | b1 p1 q1 brs0 W1 Hnh Hok Hdev ]; subst.
    apply ST_Comm; [ exact Hnh | | ].
    + intros l' psi' X Hin Hpsi. apply in_mid in Hin. destruct Hin as [Hin | [Heq | Hin]].
      * eapply Hok; [ apply in_mid_l; exact Hin | exact Hpsi ].
      * inversion Heq; subst. apply IH. eapply Hok; [ apply in_mid_m | exact Hpsi ].
      * eapply Hok; [ apply in_mid_r; exact Hin | exact Hpsi ].
    + intros l' psi' X Hin Hnpsi c Hb. apply in_mid in Hin. destruct Hin as [Hin | [Heq | Hin]].
      * eapply Hdev; [ apply in_mid_l; exact Hin | exact Hnpsi | exact Hb ].
      * inversion Heq; subst. apply IH. eapply Hdev; [ apply in_mid_m | exact Hnpsi | reflexivity ].
      * eapply Hdev; [ apply in_mid_r; exact Hin | exact Hnpsi | exact Hb ].
Qed.

(* ================================================================= *)
(*  Safe swaps preserve typing (subject reduction under permutation). *)
(* ================================================================= *)
Lemma supd_other : forall s r P x, x <> r -> supd s r P x = s x.
Proof. intros. unfold supd. destruct (Nat.eq_dec x r); congruence. Qed.

Lemma ctypes_ext : forall G s W, ctypes E G s W ->
  forall s', (forall x, s x = s' x) -> ctypes E G s' W.
Proof.
  intros G s W Ht. induction Ht as [ s W Hend | phi G s W Hphi Ht IH
                                    | a p G s W P Hsp Hex Hall IH
                                    | p q brs s W sendb recvb Hpq Hsp Hsq Hne Hl1 Hl2 Hl3 Hcont IH ];
    intros s' Hext.
  - apply CT_End. intro r. rewrite <- Hext. apply Hend.
  - apply CT_Goal; [ exact Hphi | apply IH; exact Hext ].
  - apply CT_Act with P; [ rewrite <- Hext; exact Hsp | exact Hex | ].
    intros W' HE. apply (IH W' HE). intro x. unfold supd. destruct (Nat.eq_dec x p); [ reflexivity | apply Hext ].
  - apply CT_Comm with sendb recvb; try assumption.
    + rewrite <- Hext; exact Hsp.
    + rewrite <- Hext; exact Hsq.
    + intros l psi Gl P Q Hin HP HQ. apply (IH l psi Gl P Q Hin HP HQ).
      intro x. unfold supd. destruct (Nat.eq_dec x q); [ reflexivity | ].
      destruct (Nat.eq_dec x p); [ reflexivity | apply Hext ].
Qed.

Theorem swap_ctypes : forall G G', swap1 G G' ->
  forall s W, ctypes E G s W -> ctypes E G' s W.
Proof.
  intros G G' Hsw.
  induction Hsw as [ a r b q G Hrq Hneu Hcom Hen1 Hen2
                   | a r p q brs Hrp Hrq Hneu Hpres
                   | a r phi G Hpres
                   | a r p q brs Hrp Hrq Hneu Hpres
                   | a r phi G Hpres
                   | p q r t ls ms K Hpr Hpt Hqr Hqt
                   | a p G G' Hsw IH
                   | phi G G' Hsw IH
                   | p q brs1 brs2 l psi Gl Gl' Hsw IH ]; intros s W Ht.
  - inversion Ht as [ | | a1 p1 G1 s1 W1 P Hsq Hex Hall | ]; subst.
    destruct Hex as [W1 Hb1].
    pose proof (Hall W1 Hb1) as Ht1.
    inversion Ht1 as [ | | a2 p2 G2 s2 W2 Q Hsr Hex2 Hall2 | ]; subst.
    rewrite supd_other in Hsr by exact Hrq.
    apply CT_Act with Q.
    + exact Hsr.
    + apply (proj2 (Hen2 W W1 Hb1)). exact Hex2.
    + intros W1' Ha. apply CT_Act with P.
      * rewrite supd_other by (intro Hc; apply Hrq; symmetry; exact Hc). exact Hsq.
      * apply (proj1 (Hen1 W W1' Ha)). exists W1. exact Hb1.
      * intros W2 Hb. destruct (Hcom W W1' W2 Ha Hb) as [W1'' [Hb' Ha']].
        pose proof (Hall W1'' Hb') as Ht2.
        inversion Ht2 as [ | | a3 p3 G3 s3 W3 Q' Hsr' Hex' Hall' | ]; subst.
        rewrite supd_other in Hsr' by exact Hrq. rewrite Hsr in Hsr'. inversion Hsr'; subst Q'.
        eapply ctypes_ext; [ apply Hall'; exact Ha' | ].
        intro x. unfold supd. destruct (Nat.eq_dec x r); destruct (Nat.eq_dec x q); congruence.
  - inversion Ht as [ | | | p1 q1 brs1 s1 W1 sendb recvb Hpq Hsp Hsq Hne Hl1 Hl2 Hl3 Hcont ]; subst.
    destruct brs as [ | [[l0 psi0] Gl0] tl ]; [ exfalso; apply Hne; reflexivity | ].
    assert (Hin0 : In (l0, psi0, GAct a r Gl0) (map (guard_br a r) ((l0, psi0, Gl0) :: tl)))
      by (left; reflexivity).
    destruct (Hl1 _ _ _ Hin0) as [P0 HP0]. destruct (Hl3 _ _ _ Hin0) as [Q0 HQ0].
    pose proof (Hcont _ _ _ _ _ Hin0 HP0 HQ0) as Ht0.
    inversion Ht0 as [ | | a1 p1 G1 s1 W1 R Hsr Hex Hall | ]; subst.
    rewrite supd_other in Hsr by exact Hrq. rewrite supd_other in Hsr by exact Hrp.
    apply CT_Act with R; [ exact Hsr | exact Hex | ].
    intros W' Ha. apply CT_Comm with sendb recvb.
    + exact Hpq.
    + rewrite supd_other by (intro Hc; apply Hrp; symmetry; exact Hc). exact Hsp.
    + rewrite supd_other by (intro Hc; apply Hrq; symmetry; exact Hc). exact Hsq.
    + discriminate.
    + intros l psi Gl Hin. apply (Hl1 l psi (GAct a r Gl)). apply in_guard_br. exact Hin.
    + intros l P HP. destruct (Hl2 l P HP) as [psi [X Hin']].
      apply in_guard_br_inv in Hin'. destruct Hin' as [Gl [Hin _]]. exists psi, Gl. exact Hin.
    + intros l psi Gl Hin. apply (Hl3 l psi (GAct a r Gl)). apply in_guard_br. exact Hin.
    + intros l psi Gl P Q Hin HP HQ.
      pose proof (Hcont _ _ _ _ _ (in_guard_br a r l psi Gl _ Hin) HP HQ) as Htl.
      inversion Htl as [ | | a2 p2 G2 s2 W2 R' Hsr' Hex' Hall' | ]; subst.
      rewrite supd_other in Hsr' by exact Hrq. rewrite supd_other in Hsr' by exact Hrp.
      rewrite Hsr in Hsr'. inversion Hsr'; subst R'.
      eapply ctypes_ext; [ apply Hall'; exact Ha | ].
      intro x. unfold supd.
      destruct (Nat.eq_dec x q); destruct (Nat.eq_dec x p); destruct (Nat.eq_dec x r); congruence.
  - inversion Ht as [ | phi1 G1 s1 W1 Hphi Ht' | | ]; subst.
    inversion Ht' as [ | | a1 p1 G1 s1 W1 Q Hsr Hex Hall | ]; subst.
    apply CT_Act with Q; [ exact Hsr | exact Hex | ].
    intros W' Ha. apply CT_Goal; [ apply (proj1 (Hpres W W' Ha)); exact Hphi | apply Hall; exact Ha ].
  - (* SW_comm_rev *)
    inversion Ht as [ | | a1 p1 G1 s1 W1 P Hsr Hex Hall | ]; subst.
    destruct Hex as [W1 Ha1].
    pose proof (Hall W1 Ha1) as Ht1.
    inversion Ht1 as [ | | | p2 q2 brs2 s2 W2 sendb recvb Hpq Hsp Hsq Hne Hl1 Hl2 Hl3 Hcont ]; subst.
    rewrite supd_other in Hsp by (intro Hc; apply Hrp; symmetry; exact Hc).
    rewrite supd_other in Hsq by (intro Hc; apply Hrq; symmetry; exact Hc).
    apply CT_Comm with sendb recvb.
    + exact Hpq.
    + exact Hsp.
    + exact Hsq.
    + apply map_nonnil. exact Hne.
    + intros l psi X Hin. apply in_guard_br_inv in Hin. destruct Hin as [Gl [Hin _]]. eapply Hl1. exact Hin.
    + intros l P' HP. destruct (Hl2 l P' HP) as [psi [Gl Hin]]. exists psi, (GAct a r Gl). apply in_guard_br. exact Hin.
    + intros l psi X Hin. apply in_guard_br_inv in Hin. destruct Hin as [Gl [Hin _]]. eapply Hl3. exact Hin.
    + intros l psi X P' Q' Hin HP HQ. apply in_guard_br_inv in Hin. destruct Hin as [Gl [Hin HX]]. subst X.
      apply CT_Act with P.
      * rewrite supd_other by exact Hrq. rewrite supd_other by exact Hrp. exact Hsr.
      * exists W1. exact Ha1.
      * intros W' Ha'. pose proof (Hall W' Ha') as Ht'.
        inversion Ht' as [ | | | p3 q3 brs3 s3 W3 sendb' recvb' Hpq' Hsp' Hsq' Hne' Hl1' Hl2' Hl3' Hcont' ]; subst.
        rewrite supd_other in Hsp' by (intro Hc; apply Hrp; symmetry; exact Hc).
        rewrite supd_other in Hsq' by (intro Hc; apply Hrq; symmetry; exact Hc).
        rewrite Hsp in Hsp'. inversion Hsp'; subst sendb'.
        rewrite Hsq in Hsq'. inversion Hsq'; subst recvb'.
        eapply ctypes_ext; [ apply (Hcont' l psi Gl P' Q' Hin HP HQ) | ].
        intro x. unfold supd.
        destruct (Nat.eq_dec x r); destruct (Nat.eq_dec x q); destruct (Nat.eq_dec x p); congruence.
  - (* SW_goal_rev *)
    inversion Ht as [ | | a1 p1 G1 s1 W1 P Hsr Hex Hall | ]; subst.
    destruct Hex as [W1 Ha1].
    pose proof (Hall W1 Ha1) as Ht1. inversion Ht1 as [ | phi2 G2 s2 W2 Hphi Ht2 | | ]; subst.
    apply CT_Goal.
    + apply (proj2 (Hpres W W1 Ha1)). exact Hphi.
    + apply CT_Act with P; [ exact Hsr | exists W1; exact Ha1 | ].
      intros W' Ha'. pose proof (Hall W' Ha') as Ht'. inversion Ht' as [ | phi3 G3 s3 W3 Hphi' Ht3 | | ]; subst.
      exact Ht3.
  - (* SW_comm_comm *)
    inversion Ht as [ | | | p1 q1 brs1 s1 W1 sendb recvb Hpq Hsp Hsq Hne Hl1 Hl2 Hl3 Hcont ]; subst.
    unfold orig_cc in Hne. apply map_nonnil_inv in Hne.
    destruct ls as [ | [l0 psi0] ls' ]; [ exfalso; apply Hne; reflexivity | ].
    assert (Hin0 : In (l0, psi0, GComm r t (inner_brs K l0 ms)) (orig_cc r t K ms ((l0, psi0) :: ls')))
      by (apply in_orig_intro; left; reflexivity).
    destruct (Hl1 _ _ _ Hin0) as [P0 HP0]. destruct (Hl3 _ _ _ Hin0) as [Q0 HQ0].
    pose proof (Hcont _ _ _ _ _ Hin0 HP0 HQ0) as Ht0.
    inversion Ht0 as [ | | | r1 t1 brs2 s2 W2 sendb' recvb' Hrt Hsr Hst Hne' Hm1 Hm2 Hm3 Hcont0 ]; subst.
    rewrite supd_other in Hsr by (intro Hc; apply Hqr; symmetry; exact Hc).
    rewrite supd_other in Hsr by (intro Hc; apply Hpr; symmetry; exact Hc).
    rewrite supd_other in Hst by (intro Hc; apply Hqt; symmetry; exact Hc).
    rewrite supd_other in Hst by (intro Hc; apply Hpt; symmetry; exact Hc).
    unfold inner_brs in Hne'. apply map_nonnil_inv in Hne'.
    apply CT_Comm with sendb' recvb'.
    + exact Hrt.
    + exact Hsr.
    + exact Hst.
    + apply map_nonnil. exact Hne'.
    + intros m phi Y Hin. apply in_new in Hin. destruct Hin as [Hm _].
      eapply Hm1. apply in_inner_intro. exact Hm.
    + intros m P' HP. destruct (Hm2 m P' HP) as [phi [X Hin]]. apply in_inner in Hin. destruct Hin as [Hm _].
      exists phi, (GComm p q (inner_brs' K m ((l0, psi0) :: ls'))). apply in_new_intro. exact Hm.
    + intros m phi Y Hin. apply in_new in Hin. destruct Hin as [Hm _].
      eapply Hm3. apply in_inner_intro. exact Hm.
    + intros m phi Y P' Q' Hin HP' HQ'. apply in_new in Hin. destruct Hin as [Hm HY]. subst Y.
      apply CT_Comm with sendb recvb.
      * exact Hpq.
      * rewrite supd_other by exact Hpt. rewrite supd_other by exact Hpr. exact Hsp.
      * rewrite supd_other by exact Hqt. rewrite supd_other by exact Hqr. exact Hsq.
      * discriminate.
      * intros l psi X Hin. apply in_inner' in Hin. destruct Hin as [Hl _].
        eapply Hl1. apply in_orig_intro. exact Hl.
      * intros l P HP. destruct (Hl2 l P HP) as [psi [X Hin]]. apply in_orig in Hin. destruct Hin as [Hl _].
        exists psi, (K l m). apply in_inner'_intro. exact Hl.
      * intros l psi X Hin. apply in_inner' in Hin. destruct Hin as [Hl _].
        eapply Hl3. apply in_orig_intro. exact Hl.
      * intros l psi X P Q Hin HP HQ. apply in_inner' in Hin. destruct Hin as [Hl HX]. subst X.
        pose proof (Hcont _ _ _ P Q (in_orig_intro r t K ms _ l psi Hl) HP HQ) as Htl.
        inversion Htl as [ | | | r2 t2 brs3 s3 W3 sendb'' recvb'' Hrt2 Hsr2 Hst2 Hne2 Hm1' Hm2' Hm3' Hcont2 ]; subst.
        rewrite supd_other in Hsr2 by (intro Hc; apply Hqr; symmetry; exact Hc).
        rewrite supd_other in Hsr2 by (intro Hc; apply Hpr; symmetry; exact Hc).
        rewrite supd_other in Hst2 by (intro Hc; apply Hqt; symmetry; exact Hc).
        rewrite supd_other in Hst2 by (intro Hc; apply Hpt; symmetry; exact Hc).
        rewrite Hsr in Hsr2. inversion Hsr2; subst sendb''.
        rewrite Hst in Hst2. inversion Hst2; subst recvb''.
        eapply ctypes_ext; [ apply (Hcont2 m phi (K l m) P' Q' (in_inner_intro K l ms m phi Hm) HP' HQ') | ].
        intro x. unfold supd.
        destruct (Nat.eq_dec x q); destruct (Nat.eq_dec x p); destruct (Nat.eq_dec x t); destruct (Nat.eq_dec x r); congruence.
  - inversion Ht as [ | | a1 p1 G1 s1 W1 P Hsp Hex Hall | ]; subst.
    apply CT_Act with P; [ exact Hsp | exact Hex | ]. intros W' HE. apply IH. apply Hall. exact HE.
  - inversion Ht as [ | phi1 G1 s1 W1 Hphi Ht' | | ]; subst.
    apply CT_Goal; [ exact Hphi | apply IH; exact Ht' ].
  - inversion Ht as [ | | | p1 q1 brs0 s1 W1 sendb recvb Hpq Hsp Hsq Hne Hl1 Hl2 Hl3 Hcont ]; subst.
    apply CT_Comm with sendb recvb; try assumption.
    + destruct brs1; discriminate.
    + intros l' psi' X Hin. apply in_mid in Hin. destruct Hin as [Hin | [Heq | Hin]].
      * eapply Hl1. apply in_mid_l. exact Hin.
      * inversion Heq; subst. eapply Hl1. apply in_mid_m.
      * eapply Hl1. apply in_mid_r. exact Hin.
    + intros l' P HP. destruct (Hl2 l' P HP) as [psi' [X Hin]].
      apply in_mid in Hin. destruct Hin as [Hin | [Heq | Hin]].
      * exists psi', X. apply in_mid_l. exact Hin.
      * inversion Heq; subst. exists psi, Gl'. apply in_mid_m.
      * exists psi', X. apply in_mid_r. exact Hin.
    + intros l' psi' X Hin. apply in_mid in Hin. destruct Hin as [Hin | [Heq | Hin]].
      * eapply Hl3. apply in_mid_l. exact Hin.
      * inversion Heq; subst. eapply Hl3. apply in_mid_m.
      * eapply Hl3. apply in_mid_r. exact Hin.
    + intros l' psi' X P Q Hin HP HQ. apply in_mid in Hin. destruct Hin as [Hin | [Heq | Hin]].
      * eapply Hcont; [ apply in_mid_l; exact Hin | exact HP | exact HQ ].
      * inversion Heq; subst. apply IH. eapply Hcont; [ apply in_mid_m | exact HP | exact HQ ].
      * eapply Hcont; [ apply in_mid_r; exact Hin | exact HP | exact HQ ].
Qed.

(* ---- the closure, and interleaved runs ---- *)
Inductive swaps : Gt -> Gt -> Prop :=
| SWS_refl : forall G, swaps G G
| SWS_step : forall G G' G'', swap1 G G' -> swaps G' G'' -> swaps G G''.

Lemma swaps_safe : forall G G', swaps G G' -> forall b W, safeT E Haz b G W -> safeT E Haz b G' W.
Proof.
  intros G G' H. induction H as [ | G G' G'' Hsw Hs IH ]; intros b W Ht; [ exact Ht | ].
  apply IH. eapply swap_safe; eassumption.
Qed.

Lemma swaps_ctypes : forall G G', swaps G G' -> forall s W, ctypes E G s W -> ctypes E G' s W.
Proof.
  intros G G' H. induction H as [ | G G' G'' Hsw Hs IH ]; intros s W Ht; [ exact Ht | ].
  apply IH. eapply swap_ctypes; eassumption.
Qed.

(* an interleaved run: before each step the protocol may be permuted by
   any sequence of safe swaps, then a head step of the permuted protocol
   is taken *)
Inductive irun : Gt -> Sess -> World -> list (Role * nat) -> Gt -> Sess -> World -> Prop :=
| IR_refl : forall G s W, irun G s W [] G s W
| IR_step : forall G G1 s W G2 s2 W2 r c tr G' s' W',
    swaps G G1 ->
    hstep E G1 s W G2 s2 W2 r c ->
    irun G2 s2 W2 tr G' s' W' ->
    irun G s W ((r, c) :: tr) G' s' W'.

Theorem bridge_interleaved : forall G s W tr G' s' W' b,
  ctypes E G s W -> safeT E Haz b G W ->
  irun G s W tr G' s' W' -> total tr <= b -> ~ Haz W'.
Proof.
  intros G s W tr G' s' W' b Hct Hsf Hr. revert b Hct Hsf.
  induction Hr as [ G s W | G G1 s W G2 s2 W2 r c tr G' s' W' Hsw Hst Hr IH ]; intros b Hct Hsf Htot.
  - eapply safeT_not_haz. exact Hsf.
  - unfold total in Htot; simpl in Htot. fold (total tr) in Htot.
    assert (Hcb : c <= b) by lia.
    pose proof (swaps_ctypes _ _ Hsw _ _ Hct) as Hct1.
    pose proof (swaps_safe _ _ Hsw _ _ Hsf) as Hsf1.
    destruct (bridge_step E Haz G1 s W G2 s2 W2 r c b Hct1 Hsf1 Hst Hcb) as [Hct2 Hsf2].
    apply (IH (b - c) Hct2 Hsf2). lia.
Qed.

End Interleave.

(* ================================================================= *)
(*  STRIPS instance: variable disjointness discharges the semantic     *)
(*  conditions.  This is the check the tool performs.                  *)
(* ================================================================= *)
Section Strips.
Record Cap := { c_pre : World -> Prop; c_vars : list Var; c_add : list Var; c_del : list Var }.
Variable tbl : CapN -> Cap.

Definition supported (P : World -> Prop) (vs : list Var) : Prop :=
  forall W W', (forall x, In x vs -> W x = W' x) -> P W -> P W'.
Hypothesis pre_supported : forall a, supported (c_pre (tbl a)) (c_vars (tbl a)).
Hypothesis add_del_disjoint : forall a x, In x (c_add (tbl a)) -> In x (c_del (tbl a)) -> False.

(* the extensional STRIPS context *)
Definition Es : Ctx := fun a W W' =>
  c_pre (tbl a) W /\
  (forall x, In x (c_add (tbl a)) -> W' x = 1) /\
  (forall x, In x (c_del (tbl a)) -> W' x = 0) /\
  (forall x, ~ In x (c_add (tbl a)) -> ~ In x (c_del (tbl a)) -> W' x = W x).

Definition effects (a : CapN) : list Var := c_add (tbl a) ++ c_del (tbl a).
Definition footprint (a : CapN) : list Var := c_vars (tbl a) ++ effects a.
Definition disjoint (l1 l2 : list Var) : Prop := forall x, In x l1 -> In x l2 -> False.
Definition independent (a b : CapN) : Prop :=
  disjoint (effects a) (footprint b) /\ disjoint (effects b) (footprint a).

Definition apply_cap (a : CapN) (W : World) : World :=
  fun x => if in_dec Nat.eq_dec x (c_add (tbl a)) then 1
           else if in_dec Nat.eq_dec x (c_del (tbl a)) then 0 else W x.

Lemma apply_cap_E : forall a W, c_pre (tbl a) W -> Es a W (apply_cap a W).
Proof.
  intros a W Hp. unfold Es, apply_cap. split; [ exact Hp | ]. split; [ | split ].
  - intros x Hx. destruct (in_dec Nat.eq_dec x (c_add (tbl a))); [ reflexivity | contradiction ].
  - intros x Hx. destruct (in_dec Nat.eq_dec x (c_add (tbl a))) as [Hin | Hnin].
    + exfalso. eapply add_del_disjoint; eauto.
    + destruct (in_dec Nat.eq_dec x (c_del (tbl a))); [ reflexivity | contradiction ].
  - intros x Hna Hnd.
    destruct (in_dec Nat.eq_dec x (c_add (tbl a))); [ contradiction | ].
    destruct (in_dec Nat.eq_dec x (c_del (tbl a))); [ contradiction | reflexivity ].
Qed.

Lemma Es_frame : forall a W W' x, Es a W W' -> ~ In x (effects a) -> W' x = W x.
Proof.
  intros a W W' x [_ [_ [_ Hfr]]] Hn. apply Hfr; intro Hi; apply Hn; unfold effects; apply in_or_app; auto.
Qed.

Lemma effects_in_footprint : forall a x, In x (effects a) -> In x (footprint a).
Proof. intros. unfold footprint. apply in_or_app. right. assumption. Qed.
Lemma vars_in_footprint : forall a x, In x (c_vars (tbl a)) -> In x (footprint a).
Proof. intros. unfold footprint. apply in_or_app. left. assumption. Qed.

Theorem strips_commute : forall a b, independent a b -> commute_ab Es a b.
Proof.
  intros a b [Hab Hba] W W1 W2 Ha Hb.
  exists (apply_cap b W). split.
  - apply apply_cap_E.
    eapply pre_supported; [ | exact (proj1 Hb) ].
    intros x Hx. eapply Es_frame; [ exact Ha | ].
    intro He. apply (Hab x He). apply vars_in_footprint. exact Hx.
  - split; [ | split; [ | split ] ].
    + eapply pre_supported; [ | exact (proj1 Ha) ].
      intros x Hx. unfold apply_cap.
      destruct (in_dec Nat.eq_dec x (c_add (tbl b))) as [Hin | _].
      { exfalso. apply (Hba x); [ unfold effects; apply in_or_app; left; exact Hin | apply vars_in_footprint; exact Hx ]. }
      destruct (in_dec Nat.eq_dec x (c_del (tbl b))) as [Hin | _].
      { exfalso. apply (Hba x); [ unfold effects; apply in_or_app; right; exact Hin | apply vars_in_footprint; exact Hx ]. }
      reflexivity.
    + intros x Hx. rewrite (Es_frame b W1 W2 x Hb).
      * apply (proj1 (proj2 Ha)). exact Hx.
      * intro He. apply (Hba x He). apply effects_in_footprint. unfold effects. apply in_or_app. left. exact Hx.
    + intros x Hx. rewrite (Es_frame b W1 W2 x Hb).
      * apply (proj1 (proj2 (proj2 Ha))). exact Hx.
      * intro He. apply (Hba x He). apply effects_in_footprint. unfold effects. apply in_or_app. right. exact Hx.
    + intros x Hna Hnd. unfold apply_cap.
      destruct (in_dec Nat.eq_dec x (c_add (tbl b))) as [Hin | Hnin].
      { apply (proj1 (proj2 Hb)). exact Hin. }
      destruct (in_dec Nat.eq_dec x (c_del (tbl b))) as [Hin' | Hnin'].
      { apply (proj1 (proj2 (proj2 Hb))). exact Hin'. }
      rewrite (proj2 (proj2 (proj2 Hb)) x Hnin Hnin'). apply (proj2 (proj2 (proj2 Ha)) x Hna Hnd).
Qed.

Theorem strips_enables : forall a b, independent a b -> enables Es a b.
Proof.
  intros a b [Hab Hba] W W' Ha. split; intros [W2 Hb].
  - exists (apply_cap b W'). apply apply_cap_E.
    eapply pre_supported; [ | exact (proj1 Hb) ].
    intros x Hx. symmetry. eapply Es_frame; [ exact Ha | ].
    intro He. apply (Hab x He). apply vars_in_footprint. exact Hx.
  - exists (apply_cap b W). apply apply_cap_E.
    eapply pre_supported; [ | exact (proj1 Hb) ].
    intros x Hx. eapply Es_frame; [ exact Ha | ].
    intro He. apply (Hab x He). apply vars_in_footprint. exact Hx.
Qed.

Theorem strips_preserves : forall a (psi : World -> Prop) vs,
  supported psi vs -> disjoint (effects a) vs -> preserves Es a psi.
Proof.
  intros a psi vs Hsup Hdis W W' Ha. split; intro H.
  - eapply Hsup; [ | exact H ]. intros x Hx. symmetry. eapply Es_frame; [ exact Ha | ].
    intro He. apply (Hdis x He Hx).
  - eapply Hsup; [ | exact H ]. intros x Hx. eapply Es_frame; [ exact Ha | ].
    intro He. apply (Hdis x He Hx).
Qed.

(* ----------------------------------------------------------------- *)
(*  The same syntactic check discharges the CONE OF INFLUENCE.          *)
(*                                                                     *)
(*  safeT_cone asks that the hazard, the capabilities and the guards    *)
(*  read only a set V of variables.  For STRIPS capabilities that is a  *)
(*  containment on the tool's own footprints, and it is weaker than     *)
(*  one might expect: only what a precondition READS has to be inside   *)
(*  the cone.  What an action WRITES outside the cone is irrelevant,    *)
(*  because worlds are only ever compared on V.                         *)
(* ----------------------------------------------------------------- *)
Theorem strips_haz_cone : forall (V : Var -> Prop) (Haz : World -> Prop) hvars,
  supported Haz hvars -> (forall x, In x hvars -> V x) ->
  forall W1 W2, agree V W1 W2 -> (Haz W1 <-> Haz W2).
Proof.
  intros V Haz hvars Hsup Hsub W1 W2 Hag. split; intro H.
  - eapply Hsup; [ | exact H ]. intros x Hx. apply Hag. apply Hsub. exact Hx.
  - eapply Hsup; [ | exact H ]. intros x Hx. symmetry. apply Hag. apply Hsub. exact Hx.
Qed.

Theorem strips_cap_cone : forall (V : Var -> Prop),
  (forall a x, In x (c_vars (tbl a)) -> V x) ->
  forall a W1 W2 W1', agree V W1 W2 -> Es a W1 W1' ->
    exists W2', Es a W2 W2' /\ agree V W1' W2'.
Proof.
  intros V Hsub a W1 W2 W1' Hag HE.
  assert (Hpre2 : c_pre (tbl a) W2).
  { eapply pre_supported; [ | exact (proj1 HE) ].
    intros x Hx. apply Hag. apply Hsub with (a := a). exact Hx. }
  exists (apply_cap a W2). split; [ apply apply_cap_E; exact Hpre2 | ].
  intros x Hx. unfold apply_cap.
  destruct (in_dec Nat.eq_dec x (c_add (tbl a))) as [Hadd | Hnadd].
  - destruct HE as [_ [Hа _]]. apply Hа. exact Hadd.
  - destruct (in_dec Nat.eq_dec x (c_del (tbl a))) as [Hdel | Hndel].
    + destruct HE as [_ [_ [Hd _]]]. apply Hd. exact Hdel.
    + rewrite (proj2 (proj2 (proj2 HE)) x Hnadd Hndel). apply Hag. exact Hx.
Qed.

(* so the cone-of-influence theorem applies to the tool's own capability
   model, with the containment checked syntactically *)
Corollary strips_safeT_cone : forall (V : Var -> Prop) (Haz : World -> Prop) hvars,
  supported Haz hvars ->
  (forall x, In x hvars -> V x) ->
  (forall a x, In x (c_vars (tbl a)) -> V x) ->
  forall b G W1 W2, guards_in_cone V G -> agree V W1 W2 ->
    (safeT Es Haz b G W1 <-> safeT Es Haz b G W2).
Proof.
  intros V Haz hvars Hsup Hhv Hcv b G W1 W2 Hg Hag.
  apply (safeT_cone Es Haz V
           (strips_haz_cone V Haz hvars Hsup Hhv)
           (strips_cap_cone V Hcv) b G W1 W2 Hg Hag).
Qed.

Theorem strips_neutral : forall (Haz : World -> Prop) hvars a,
  supported Haz hvars -> disjoint (effects a) hvars -> neutral Es Haz a.
Proof. intros Haz hvars a Hsup Hdis. apply (strips_preserves a Haz hvars Hsup Hdis). Qed.

(* the syntactic check discharges every side condition of an action swap *)
Corollary strips_swap_act : forall (Haz : World -> Prop) hvars a r b q G,
  supported Haz hvars -> disjoint (effects a) hvars -> independent a b -> r <> q ->
  swap1 Es Haz (GAct b q (GAct a r G)) (GAct a r (GAct b q G)).
Proof.
  intros Haz hvars a r b q G Hsup Hdis Hind Hrq.
  apply SW_act; [ exact Hrq | eapply strips_neutral; eauto | apply strips_commute; exact Hind
               | apply strips_enables; exact Hind | apply strips_enables; destruct Hind; split; assumption ].
Qed.

End Strips.

(* ============================================================= *)
(*  DirectTypingSR.v                                              *)
(*                                                                 *)
(*  Operational correspondence for the direct typing discipline:  *)
(*  Subject Reduction and Session Fidelity, over the LABELLED      *)
(*  transition systems of the paper (S-Comm / G-Comm-E / G-Comm-I),*)
(*  proved WITH full bystander interleaving and WITHOUT any        *)
(*  projection, merge, or local type.                             *)
(*                                                                 *)
(*  Scope (kept honest and axiom-free).                            *)
(*  * Communication + goal fragment.  This is exactly the fragment *)
(*    in which interleaving is *unconditional*: messages do not    *)
(*    touch the world, so a bystander move commutes past a pending *)
(*    head communication with no independence hypothesis.  World-  *)
(*    changing actions (a@p) are handled at the head by the        *)
(*    reachability core (SkillAchievability.v) and the head-move    *)
(*    safety of DirectTyping.v; interleaving two *actions* needs an *)
(*    effect-independence side condition (paper Thm, on paper).     *)
(*  * Single-label (directed) communication p->q : l . G.  The      *)
(*    bystander-commuting mechanism the theorems are about is fully *)
(*    present here; multi-branch choice is the standard nested-     *)
(*    induction extension (paper).                                  *)
(*  * The world is a spectator in this fragment (only actions move  *)
(*    it), so it is carried as a fixed parameter that goal markers  *)
(*    read; SR/SF preserve it.                                      *)
(*                                                                 *)
(*  Proved (Coq 8.18, no libraries beyond List, axiom-free):        *)
(*   subject_reduction : every session step is matched by a global  *)
(*     step of the same label, and typing is preserved.            *)
(*   session_fidelity  : every global step is realised by a session *)
(*     step of the same label, and typing is preserved.            *)
(*   Both use ctypes_ext (typing respects pointwise-equal sessions),*)
(*   which is what lets the interleaving cases avoid functional     *)
(*   extensionality and stay axiom-free.                           *)
(* ============================================================= *)

Require Import List.
Import ListNotations.

Section DirectTypingSR.
  Context {Role Lab World : Type}.
  Variable role_eq_dec : forall x y : Role, {x = y} + {x <> y}.
  Variable lab_eq_dec  : forall x y : Lab,  {x = y} + {x <> y}.

  (* ---------------- processes, single-label directed communication ---------------- *)
  Inductive Proc :=
  | PEnd : Proc
  | POut : Role -> Lab -> Proc -> Proc     (* q ! l . P  *)
  | PIn  : Role -> Lab -> Proc -> Proc.    (* p ? l . P  *)

  Inductive Gt :=
  | GEnd  : Gt
  | GComm : Role -> Role -> Lab -> Gt -> Gt     (* p -> q : l . G *)
  | GGoal : (World -> Prop) -> Gt -> Gt.        (* checkmark phi . G *)

  Definition Sess := Role -> Proc.
  Definition upd (s : Sess) (r : Role) (P : Proc) : Sess :=
    fun r' => if role_eq_dec r' r then P else s r'.

  Lemma upd_same : forall s r P, upd s r P r = P.
  Proof. intros; unfold upd; destruct (role_eq_dec r r); congruence. Qed.

  Lemma upd_other : forall s r P r', r' <> r -> upd s r P r' = s r'.
  Proof. intros; unfold upd; destruct (role_eq_dec r' r); congruence. Qed.

  (* pointwise commutation of independent updates, without funext *)
  Lemma upd_comm_pt : forall s a b Pa Pb r,
    a <> b -> upd (upd s a Pa) b Pb r = upd (upd s b Pb) a Pa r.
  Proof.
    intros s a b Pa Pb r Hab. unfold upd.
    destruct (role_eq_dec r b); destruct (role_eq_dec r a); congruence.
  Qed.

  (* ---------------- labels ---------------- *)
  Inductive Lbl := LC : Role -> Lab -> Role -> Lbl.
  Definition inpart (L : Lbl) (r : Role) : Prop :=
    match L with LC p _ q => r = p \/ r = q end.

  (* ---------------- labelled session step (world-invariant) ---------------- *)
  Inductive lstep : Lbl -> Sess -> Sess -> Prop :=
  | LS_Comm : forall s p q l Pp Pq,
      p <> q ->
      s p = POut q l Pp ->
      s q = PIn  p l Pq ->
      lstep (LC p l q) s (upd (upd s p Pp) q Pq).

  (* ---------------- direct typing (world W fixed; it is a spectator here) ---------------- *)
  Inductive ctypes (W : World) : Gt -> Sess -> Prop :=
  | CT_End : forall s,
      (forall r, s r = PEnd) ->
      ctypes W GEnd s
  | CT_Goal : forall phi Gc s,
      phi W ->
      ctypes W Gc s ->
      ctypes W (GGoal phi Gc) s
  | CT_Comm : forall p q l Gc s Pp Pq,
      p <> q ->
      s p = POut q l Pp ->
      s q = PIn  p l Pq ->
      ctypes W Gc (upd (upd s p Pp) q Pq) ->
      ctypes W (GComm p q l Gc) s.

  (* typing respects pointwise-equal sessions -- the key to an axiom-free
     interleaving argument (we never need two update-expressions to be equal
     as functions, only pointwise). *)
  Lemma ctypes_ext : forall W G s1 s2,
    (forall r, s1 r = s2 r) -> ctypes W G s1 -> ctypes W G s2.
  Proof.
    intros W G s1 s2 Hpt H. revert s2 Hpt.
    induction H as [ s Hend | phi Gc s Hphi Hc IH | p q l Gc s Pp Pq Hpq Hsp Hsq Hc IH ];
      intros s2 Hpt.
    - apply CT_End. intro r. rewrite <- Hpt. apply Hend.
    - apply CT_Goal; [exact Hphi | apply IH; exact Hpt].
    - eapply CT_Comm with (Pp := Pp) (Pq := Pq).
      + exact Hpq.
      + rewrite <- Hpt. exact Hsp.
      + rewrite <- Hpt. exact Hsq.
      + apply IH. intro r. unfold upd. destruct (role_eq_dec r q); destruct (role_eq_dec r p);
          try reflexivity; apply Hpt.
  Qed.

  (* ---------------- labelled global LTS: head + interleaving ---------------- *)
  Inductive gstep (W : World) : Lbl -> Gt -> Gt -> Prop :=
  | GS_CommE : forall p q l Gc,
      gstep W (LC p l q) (GComm p q l Gc) Gc
  | GS_Goal : forall phi Gc L G',
      phi W ->
      gstep W L Gc G' ->
      gstep W L (GGoal phi Gc) G'
  | GS_CommI : forall p q l Gc Gc' L,
      ~ inpart L p -> ~ inpart L q ->
      gstep W L Gc Gc' ->
      gstep W L (GComm p q l Gc) (GComm p q l Gc').

  (* ============================================================= *)
  (*  Subject reduction: a session move is matched by a global      *)
  (*  move of the same label, preserving typing.                   *)
  (* ============================================================= *)
  Theorem subject_reduction :
    forall W G s s' L,
      ctypes W G s ->
      lstep L s s' ->
      exists G', gstep W L G G' /\ ctypes W G' s'.
  Proof.
    intros W G s s' L Ht. revert s' L.
    induction Ht as [ s Hend | phi Gc s Hphi Hc IH | p q l Gc s Pp Pq Hpq Hsp Hsq Hc IH ];
      intros s' L Hstep.
    - (* CT_End: no output anywhere, so no step *)
      inversion Hstep; subst.
      match goal with H : s ?x = POut _ _ _ |- _ => rewrite Hend in H; discriminate end.
    - (* CT_Goal: discharge the marker and recurse *)
      destruct (IH s' L Hstep) as [G' [Hg Hc']].
      exists G'. split; [apply GS_Goal; assumption | exact Hc'].
    - (* CT_Comm: head communication or bystander interleaving *)
      inversion Hstep as [ ss r t rl mPr mPt Hrt Hsr Hst Heq ]; subst.
      destruct (role_eq_dec r p) as [Hrp | Hrp].
      + (* r = p: forced head communication p -> q on label l *)
        subst r.
        rewrite Hsp in Hsr. injection Hsr as Et Erl EPr. subst t rl mPr.
        rewrite Hsq in Hst. injection Hst as EPt. subst mPt.
        exists Gc. split; [apply GS_CommE | exact Hc].
      + (* r <> p: the mover is a bystander disjoint from {p,q} *)
        assert (r <> q) as Hrq by (intro; subst; rewrite Hsq in Hsr; discriminate).
        assert (t <> p) as Htp by (intro; subst; rewrite Hsp in Hst; discriminate).
        assert (t <> q) as Htq by
          (intro; subst; rewrite Hsq in Hst; injection Hst as E1 E2 E3; congruence).
        (* the bystander move is available inside the continuation typing *)
        assert (Hstep' : lstep (LC r rl t) (upd (upd s p Pp) q Pq)
                                (upd (upd (upd (upd s p Pp) q Pq) r mPr) t mPt)).
        { apply LS_Comm; [ exact Hrt | | ].
          - rewrite upd_other by congruence. rewrite upd_other by congruence. exact Hsr.
          - rewrite upd_other by congruence. rewrite upd_other by congruence. exact Hst. }
        destruct (IH _ _ Hstep') as [Gc' [Hg Hc']].
        exists (GComm p q l Gc'). split.
        * apply GS_CommI.
          -- simpl; intros [H|H]; congruence.
          -- simpl; intros [H|H]; congruence.
          -- exact Hg.
        * eapply CT_Comm with (Pp := Pp) (Pq := Pq).
          -- exact Hpq.
          -- rewrite upd_other by congruence. rewrite upd_other by congruence. exact Hsp.
          -- rewrite upd_other by congruence. rewrite upd_other by congruence. exact Hsq.
          -- eapply ctypes_ext; [ | exact Hc' ].
             (* the two continuation configurations agree pointwise *)
             intro r0. unfold upd.
             destruct (role_eq_dec r0 q); destruct (role_eq_dec r0 p);
               destruct (role_eq_dec r0 t); destruct (role_eq_dec r0 r);
               congruence.
  Qed.

  (* ============================================================= *)
  (*  Session fidelity: a global move is realised by a session      *)
  (*  move of the same label, preserving typing.                   *)
  (* ============================================================= *)
  Theorem session_fidelity :
    forall W G G' s L,
      ctypes W G s ->
      gstep W L G G' ->
      exists s', lstep L s s' /\ ctypes W G' s'.
  Proof.
    intros W G G' s L Ht. revert G' L.
    induction Ht as [ s Hend | phi Gc s Hphi Hc IH | p q l Gc s Pp Pq Hpq Hsp Hsq Hc IH ];
      intros G' L Hg.
    - (* CT_End: end has no global move *)
      inversion Hg.
    - (* CT_Goal: the marker is discharged; realise the underlying move *)
      inversion Hg; subst.
      match goal with H : gstep W L Gc ?X |- _ =>
        destruct (IH X L H) as [s' [Hl Hc']] end.
      exists s'. split; [exact Hl | exact Hc'].
    - (* CT_Comm: head move or interleaving move *)
      inversion Hg; subst.
      + (* GS-Comm-E: the prescribed head communication fires *)
        exists (upd (upd s p Pp) q Pq). split.
        * apply LS_Comm; assumption.
        * exact Hc.
      + (* GS-Comm-I: bystander move, disjoint from {p,q} *)
        destruct L as [r rl t]. simpl in *.
        match goal with Hnp : ~ (p = r \/ p = t) |- _ =>
          assert (r <> p) as Hrp by (intro; subst; apply Hnp; auto);
          assert (t <> p) as Htp by (intro; subst; apply Hnp; auto) end.
        match goal with Hnq : ~ (q = r \/ q = t) |- _ =>
          assert (r <> q) as Hrq by (intro; subst; apply Hnq; auto);
          assert (t <> q) as Htq by (intro; subst; apply Hnq; auto) end.
        match goal with Hg0 : gstep W (LC r rl t) Gc ?X |- _ =>
          destruct (IH X (LC r rl t) Hg0) as [s0 [Hl Hc']] end.
        (* the continuation move is a communication; read off its endpoints *)
        inversion Hl as [ ss mp mq ml Pr Pt Hrt Hsr Hst Heq ]; subst.
        exists (upd (upd s r Pr) t Pt). split.
        * apply LS_Comm.
          -- exact Hrt.
          -- rewrite upd_other in Hsr by congruence.
             rewrite upd_other in Hsr by congruence. exact Hsr.
          -- rewrite upd_other in Hst by congruence.
             rewrite upd_other in Hst by congruence. exact Hst.
        * eapply CT_Comm with (Pp := Pp) (Pq := Pq).
          -- exact Hpq.
          -- rewrite upd_other by congruence. rewrite upd_other by congruence. exact Hsp.
          -- rewrite upd_other by congruence. rewrite upd_other by congruence. exact Hsq.
          -- eapply ctypes_ext; [ | exact Hc' ].
             intro r0. unfold upd.
             destruct (role_eq_dec r0 t); destruct (role_eq_dec r0 r);
               destruct (role_eq_dec r0 q); destruct (role_eq_dec r0 p);
               congruence.
  Qed.

End DirectTypingSR.

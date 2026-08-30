(* ================================================================= *)
(*  DeviationLayer.v                                                  *)
(*                                                                     *)
(*  MECHANIZED AUDIT of the WIP paper -- Typing the Unreliable         *)
(*  Participant (paper/WIP/main.tex).  This file does NOT assume the   *)
(*  paper's theorems.  It encodes the paper's definitions as literally *)
(*  as possible and then tries to PROVE the theorem statements.  Where *)
(*  a statement is provable it is proved; where it is not, a concrete  *)
(*  COUNTEREXAMPLE is constructed and proved.                          *)
(*                                                                     *)
(*  Coq 8.18, no external libraries beyond the stdlib, axiom-free.     *)
(*                                                                     *)
(*  SUMMARY OF RESULTS                                                 *)
(*                                                                     *)
(*  Sec 1  mode lattice                                                *)
(*    down_monotone, meet_monotone, contamination_monotone    PROVED   *)
(*                                                                     *)
(*  Sec 3  Theorem thm:noninterf (quarantine non-interference)         *)
(*    irr_safe_invariant          -- syntactic reading        PROVED   *)
(*        but the proof is one line: it merely re-reads the premise    *)
(*        of I-Act.  It says nothing about the taint ANALYSIS.         *)
(*    taint_laundering_refutes_noninterference                REFUTED  *)
(*        The paper's taint update T (+)_a M consults only the         *)
(*        WRITER's mode and the capability's PROVENANCE, never what    *)
(*        the capability READS.  An ok-mode internal capability that   *)
(*        copies a tainted variable into a fresh one launders the      *)
(*        taint; a downstream irreversible capability then passes the  *)
(*        guard supp(pre) /\ T = {} while its firing is decided        *)
(*        entirely by the attacker-controlled external value.          *)
(*    repaired_update_blocks_laundering                        PROVED  *)
(*        Adding read-set propagation fixes the counterexample.        *)
(*                                                                     *)
(*  Sec 4  Theorem thm:isr (instrumented subject reduction)            *)
(*    act_vacuous_with_partial_qres                           REFUTED  *)
(*        Much stronger than expected.  T-Act-M's downgrade-closure    *)
(*        premise recurses at the SAME protocol node with the role's   *)
(*        mode lowered.  After two unfoldings the role is at bottom,   *)
(*        where only T-Quar applies.  If the quarantine residual of    *)
(*        Remark 3 is partial -- option (b), the one the draft         *)
(*        prefers -- NOTHING containing a capability is typable at     *)
(*        all.  The type system is VACUOUS, so thm:isr holds only      *)
(*        vacuously and rule Ach-M can never be derived.               *)
(*    sr_dev_head_preserved                                    PROVED  *)
(*        Given a derivation, the head role's deviation is covered --  *)
(*        this is exactly what the closure premise buys.               *)
(*    sr_dev_with_total_qres                                   PROVED  *)
(*        SR for deviation steps IS recoverable, under precisely the   *)
(*        hypothesis that qres is total and its residual types.  That  *)
(*        is the obligation Remark 3 leaves open.                      *)
(*                                                                     *)
(*  Sec 5  Theorem thm:checkpoint (bounded degradation)                *)
(*    goal_only_cycle_hits_cap                                REFUTED  *)
(*        WF-Loop (Definition 3) accepts a cycle whose only            *)
(*        checkpoint is a goal marker.  But a goal marker sanitizes    *)
(*        TAINT, not GRADE: only T-Refresh resets a grade.  Grades     *)
(*        therefore saturate at the cap on WF-Loop-conformant          *)
(*        protocols, so the regeneration premise of the renewal        *)
(*        argument fails and the positive direction of thm:checkpoint  *)
(*        does not follow from WF-Loop as defined.                     *)
(*    wfloop_refresh_grade_bounded                             PROVED  *)
(*        Strengthening WF-Loop to require a REFRESH in every cycle    *)
(*        does give the regeneration property.                         *)
(* ================================================================= *)

Require Import List Arith Bool Lia.
Import ListNotations.

(* ================================================================= *)
(*  Section 1.  The compliance lattice  (paper Definition 1)          *)
(* ================================================================= *)

Inductive Mode := Mok | Mdr | Mbot.

(* mle m1 m2  reads  m1 [= m2,  with  bot [= dr [= ok *)
Definition mle (m1 m2 : Mode) : Prop :=
  match m1, m2 with
  | Mbot, _ => True
  | Mdr, Mdr => True
  | Mdr, Mok => True
  | Mok, Mok => True
  | _, _ => False
  end.

Definition down (m : Mode) : Mode :=
  match m with Mok => Mdr | Mdr => Mbot | Mbot => Mbot end.

Definition up (m : Mode) : Mode :=
  match m with Mbot => Mdr | Mdr => Mok | Mok => Mok end.

Definition meet (m1 m2 : Mode) : Mode :=
  match m1, m2 with
  | Mbot, _ => Mbot
  | _, Mbot => Mbot
  | Mdr, _ => Mdr
  | _, Mdr => Mdr
  | Mok, Mok => Mok
  end.

(* the paper's side condition  m [= dr  (contamination / tainting) *)
Definition le_dr (m : Mode) : bool :=
  match m with Mok => false | _ => true end.

(* the paper's side condition  m =] dr  (may fire an irreversible cap) *)
Definition ge_dr (m : Mode) : bool :=
  match m with Mbot => false | _ => true end.

Lemma mle_refl : forall m, mle m m.
Proof. destruct m; simpl; auto. Qed.

Lemma mle_trans : forall a b c, mle a b -> mle b c -> mle a c.
Proof. destruct a, b, c; simpl; auto. Qed.

Lemma down_le : forall m, mle (down m) m.
Proof. destruct m; simpl; auto. Qed.

Lemma down_monotone : forall m1 m2, mle m1 m2 -> mle (down m1) (down m2).
Proof. destruct m1, m2; simpl; auto. Qed.

Lemma up_ge : forall m, mle m (up m).
Proof. destruct m; simpl; auto. Qed.

Lemma meet_le_l : forall m1 m2, mle (meet m1 m2) m1.
Proof. destruct m1, m2; simpl; auto. Qed.

Lemma meet_monotone :
  forall a b c d, mle a c -> mle b d -> mle (meet a b) (meet c d).
Proof. destruct a, b, c, d; simpl; auto. Qed.

Definition Role := nat.
Definition role_eq_dec : forall (r1 r2 : Role), {r1 = r2} + {r1 <> r2} := Nat.eq_dec.

Definition ModeEnv := Role -> Mode.
Definition mupd (M : ModeEnv) (r : Role) (m : Mode) : ModeEnv :=
  fun r' => if role_eq_dec r' r then m else M r'.

Definition mle_env (M1 M2 : ModeEnv) : Prop := forall r, mle (M1 r) (M2 r).

(* the paper's contamination update  M |> (p,q) *)
Definition contam (M : ModeEnv) (p q : Role) : ModeEnv :=
  if le_dr (M p) then mupd M q (meet (M q) (M p)) else M.

(* Needed by the paper's Theorem thm:modes (ii). *)
Lemma contamination_monotone :
  forall M1 M2 p q, mle_env M1 M2 -> mle_env (contam M1 p q) (contam M2 p q).
Proof.
  intros M1 M2 p q H r.
  unfold contam, mupd.
  destruct (le_dr (M1 p)) eqn:E1; destruct (le_dr (M2 p)) eqn:E2;
    destruct (role_eq_dec r q); subst; simpl; try apply H.
  - apply meet_monotone; apply H.
  - eapply mle_trans; [ apply meet_le_l | apply H ].
  - exfalso. specialize (H p).
    destruct (M1 p) eqn:F1; simpl in E1; try discriminate;
    destruct (M2 p) eqn:F2; simpl in E2; try discriminate;
    simpl in H; contradiction.
Qed.

(* ================================================================= *)
(*  Section 2.  Worlds, capabilities, taint, grades                   *)
(* ================================================================= *)

Definition Var := nat.
Definition var_eq_dec : forall (x y : Var), {x = y} + {x <> y} := Nat.eq_dec.
Definition World := Var -> nat.

Definition wupd (W : World) (x : Var) (v : nat) : World :=
  fun y => if var_eq_dec y x then v else W y.

Lemma wupd_same : forall W x v, wupd W x v x = v.
Proof. intros. unfold wupd. destruct (var_eq_dec x x); congruence. Qed.

Inductive Prov := Pint | Pext.

(* A capability carries exactly what the paper's extended pack declares,
   PLUS the read set c_reads, whose absence from the paper's taint update
   is the bug exhibited in Section 3. *)
Record Cap := mkCap {
  c_pre     : World -> Prop;
  c_supp    : list Var;
  c_reads   : list Var;
  c_writes  : list Var;
  c_prov    : Prov;
  c_irr     : bool;
  c_rfr     : bool;
  c_eff     : World -> World -> Prop
}.

Definition Taint := list Var.

(* no tainted variable occurs in xs *)
Definition TaintClear (T : Taint) (xs : list Var) : Prop :=
  forall x, In x T -> ~ In x xs.

Definition is_ext (a : Cap) : bool :=
  match c_prov a with Pext => true | Pint => false end.

(* The paper's taint update, rule T-Act-M:
     T u wr(a)   if  M(p) [= dr  \/  prov(a) = ext
     T           otherwise
   It never consults c_reads.  Section 3 shows this is unsound. *)
Definition taint_upd (T : Taint) (a : Cap) (m : Mode) : Taint :=
  if le_dr m || is_ext a then T ++ c_writes a else T.

(* The repair proposed by this audit: propagate through the read set. *)
Definition mem_var (x : Var) (T : Taint) : bool := existsb (Nat.eqb x) T.
Definition reads_tainted (a : Cap) (T : Taint) : bool :=
  existsb (fun x => mem_var x T) (c_reads a).

Definition taint_upd_fixed (T : Taint) (a : Cap) (m : Mode) : Taint :=
  if le_dr m || is_ext a || reads_tainted a T then T ++ c_writes a else T.

Definition GradeEnv := Role -> nat.
Definition gupd (d : GradeEnv) (r : Role) (n : nat) : GradeEnv :=
  fun r' => if role_eq_dec r' r then n else d r'.
Definition tick (D : nat) (d : GradeEnv) (r : Role) : GradeEnv :=
  gupd d r (min D (S (d r))).

Lemma tick_self : forall D d p, tick D d p p = min D (S (d p)).
Proof. intros. unfold tick, gupd. destruct (role_eq_dec p p); congruence. Qed.

(* ================================================================= *)
(*  Section 3.  Auditing thm:noninterf                                *)
(* ================================================================= *)

Record St := mkSt { s_W : World; s_M : ModeEnv; s_T : Taint }.

(* The paper's rule I-Act, verbatim. *)
Inductive iact (p : Role) (a : Cap) : St -> St -> Prop :=
| IAct : forall W W' M T,
    c_pre a W ->
    c_eff a W W' ->
    M p <> Mbot ->
    (c_irr a = true -> TaintClear T (c_supp a) /\ ge_dr (M p) = true) ->
    iact p a (mkSt W M T) (mkSt W' M (taint_upd T a (M p))).

(* ----------------------------------------------------------------- *)
(* 3a.  The syntactic reading: PROVED, but by re-reading the premise. *)
(* ----------------------------------------------------------------- *)
Theorem irr_safe_invariant :
  forall p a s s',
    iact p a s s' ->
    c_irr a = true ->
    TaintClear (s_T s) (c_supp a) /\ ge_dr (s_M s p) = true.
Proof.
  intros p a s s' Hstep Hirr.
  destruct Hstep as [W W' M T Hpre Heff Hnb Hprem]; simpl.
  exact (Hprem Hirr).
Qed.

(* ----------------------------------------------------------------- *)
(* 3b.  The semantic reading: REFUTED by a taint-laundering run.      *)
(*                                                                     *)
(*   var 0 = fare    written by an EXTERNAL fetch  -> tainted          *)
(*   var 1 = fareok  copied from fare by a TRUSTED INTERNAL capability *)
(*                   fired by an ok-mode role -> taint update is a     *)
(*                   no-op, so fareok is CLEAN although its value IS   *)
(*                   the attacker-supplied fare                        *)
(*   cbuy           irreversible, guard  fareok <= 500                 *)
(* ----------------------------------------------------------------- *)

Definition fare : Var := 0.
Definition fareok : Var := 1.

Definition cfetch (v : nat) : Cap := mkCap
  (fun _ => True) [] [] [fare] Pext false false
  (fun W W' => W' = wupd W fare v).

Definition ccopy : Cap := mkCap
  (fun _ => True) [] [fare] [fareok] Pint false false
  (fun W W' => W' = wupd W fareok (W fare)).

Definition cbuy : Cap := mkCap
  (fun W => W fareok <= 500) [fareok] [fareok] [] Pint true false
  (fun W W' => W' = W).

Definition Mok_all : ModeEnv := fun _ => Mok.
Definition W0 : World := fun _ => 0.
Definition pR : Role := 0.

Definition st0 : St := mkSt W0 Mok_all [].
Definition st1 (v : nat) : St :=
  mkSt (wupd W0 fare v) Mok_all (taint_upd [] (cfetch v) Mok).
Definition st2 (v : nat) : St :=
  mkSt (wupd (wupd W0 fare v) fareok v) Mok_all
       (taint_upd (taint_upd [] (cfetch v) Mok) ccopy Mok).

Lemma fetch_step : forall v, iact pR (cfetch v) st0 (st1 v).
Proof.
  intro v. unfold st0, st1. apply IAct; simpl; auto.
  - discriminate.
  - intro H; discriminate H.
Qed.

Lemma copy_step : forall v, iact pR ccopy (st1 v) (st2 v).
Proof.
  intro v. unfold st1, st2.
  replace (wupd (wupd W0 fare v) fareok v)
     with (wupd (wupd W0 fare v) fareok ((wupd W0 fare v) fare)).
  - apply IAct; simpl; auto.
    + discriminate.
    + intro H; discriminate H.
  - rewrite wupd_same. reflexivity.
Qed.

(* THE BUG: after fetch-then-copy the taint set is exactly [fare].
   The external taint never reached fareok. *)
Lemma laundered_taint : forall v, s_T (st2 v) = [fare].
Proof. intro v. reflexivity. Qed.

Lemma fareok_clean : forall v, ~ In fareok (s_T (st2 v)).
Proof.
  intro v. rewrite laundered_taint. simpl. intros [H | H]; [ discriminate H | exact H ].
Qed.

(* Hence the irreversible capability's taint guard PASSES ... *)
Lemma buy_guard_passes : forall v, TaintClear (s_T (st2 v)) (c_supp cbuy).
Proof.
  intro v. rewrite laundered_taint. unfold TaintClear. simpl.
  intros x [Hx | []]. subst. intros [H | H]; [ discriminate H | exact H ].
Qed.

(* ... and yet whether the irreversible action fires is decided entirely
   by the untrusted external value.  Two runs differing ONLY in that
   value differ in whether cbuy is enabled.  That is exactly the
   interference the theorem's name promises to exclude. *)
(* The guard of the irreversible capability is exactly the laundered
   value, i.e. the attacker-supplied one. *)
Lemma buy_pre_iff : forall v, c_pre cbuy (s_W (st2 v)) <-> v <= 500.
Proof.
  intro v.
  cbv beta iota delta [c_pre cbuy st2 s_W].
  rewrite wupd_same. reflexivity.
Qed.

Theorem taint_laundering_refutes_noninterference :
  exists v1 v2,
    iact pR (cfetch v1) st0 (st1 v1) /\ iact pR ccopy (st1 v1) (st2 v1) /\
    iact pR (cfetch v2) st0 (st1 v2) /\ iact pR ccopy (st1 v2) (st2 v2) /\
    TaintClear (s_T (st2 v1)) (c_supp cbuy) /\
    TaintClear (s_T (st2 v2)) (c_supp cbuy) /\
    c_pre cbuy (s_W (st2 v1)) /\
    ~ c_pre cbuy (s_W (st2 v2)).
Proof.
  exists 100, 900.
  split. apply fetch_step.
  split. apply copy_step.
  split. apply fetch_step.
  split. apply copy_step.
  split. apply buy_guard_passes.
  split. apply buy_guard_passes.
  split.
  - destruct (buy_pre_iff 100) as [_ Hb]. apply Hb. lia.
  - intro H. destruct (buy_pre_iff 900) as [Hf _]. specialize (Hf H). lia.
Qed.

(* The repair blocks the counterexample: fareok becomes tainted. *)
Lemma repaired_update_blocks_laundering :
  In fareok (taint_upd_fixed (taint_upd_fixed [] (cfetch 100) Mok) ccopy Mok).
Proof. simpl. right. left. reflexivity. Qed.

(* ================================================================= *)
(*  Section 4.  Auditing thm:isr                                      *)
(* ================================================================= *)

Inductive Proc :=
| PEnd : Proc
| POut : Role -> list (nat * Proc) -> Proc
| PIn  : Role -> list (nat * Proc) -> Proc
| PAct : Cap -> Proc -> Proc.

Inductive Gt :=
| GEnd  : Gt
| GComm : Role -> Role -> list (nat * Gt) -> Gt
| GAct  : Cap -> Role -> Gt -> Gt
| GGoal : (World -> Prop) -> list Var -> Gt -> Gt.   (* phi, supp(phi), G *)

Definition Sess := Role -> Proc.
Definition supd (s : Sess) (r : Role) (P : Proc) : Sess :=
  fun r' => if role_eq_dec r' r then P else s r'.

Record Cfg := mkCfg {
  k_s : Sess; k_W : World; k_M : ModeEnv; k_d : GradeEnv; k_T : Taint }.

(* T-Goal-San's sanitization: drop the atoms the marker decided. *)
Definition sanitize (T : Taint) (xs : list Var) : Taint :=
  filter (fun x => negb (mem_var x xs)) T.

Section Typing.
Variable D : nat.
(* The quarantine residual of Remark 3, left abstract: the draft prefers
   option (b), a PARTIAL function whose undefinedness refutes. *)
Variable qres : Gt -> Role -> option Gt.

Inductive ctypesM : Gt -> Cfg -> Prop :=
| CTM_End : forall K,
    (forall r, k_s K r = PEnd) ->
    ctypesM GEnd K
| CTM_Goal : forall phi xs G K,
    phi (k_W K) ->
    ctypesM G (mkCfg (k_s K) (k_W K) (k_M K) (k_d K) (sanitize (k_T K) xs)) ->
    ctypesM (GGoal phi xs G) K
| CTM_Act : forall a p G K W' P,
    k_s K p = PAct a P ->
    c_pre a (k_W K) ->
    c_eff a (k_W K) W' ->
    k_M K p <> Mbot ->
    (c_irr a = true -> TaintClear (k_T K) (c_supp a) /\ ge_dr (k_M K p) = true) ->
    ctypesM G (mkCfg (supd (k_s K) p P) W' (k_M K)
                     (tick D (k_d K) p) (taint_upd (k_T K) a (k_M K p))) ->
    (* T-Act-M's downgrade-closure premise: the SAME node, p downgraded. *)
    ctypesM (GAct a p G) (mkCfg (k_s K) (k_W K)
                                (mupd (k_M K) p (down (k_M K p)))
                                (tick D (k_d K) p) (k_T K)) ->
    ctypesM (GAct a p G) K
| CTM_Quar : forall G p K G',
    k_M K p = Mbot ->
    qres G p = Some G' ->
    ctypesM G' K ->
    ctypesM G K.

(* The instrumented deviation step I-Dev: a blocked stutter that
   downgrades the deviating role and ticks its grade.  Enabled for ANY
   role, head participant or bystander. *)
Definition idev (p : Role) (K : Cfg) : Cfg :=
  mkCfg (k_s K) (k_W K) (mupd (k_M K) p (down (k_M K p))) (tick D (k_d K) p) (k_T K).

(* ----------------------------------------------------------------- *)
(* 4a.  The head role's deviation IS covered -- this is precisely      *)
(*      what the downgrade-closure premise buys.                       *)
(* ----------------------------------------------------------------- *)
Theorem sr_dev_head_preserved :
  forall a p G K,
    (forall r, k_M K r <> Mbot) ->
    ctypesM (GAct a p G) K ->
    ctypesM (GAct a p G) (idev p K).
Proof.
  intros a p G K Hnobot Hty.
  inversion Hty as [ | | a0 p0 G0 K0 W' P Hsp Hpre Heff Hnb Hirr Hcont Hclos Heq
                   | G0 p0 K0 G' Hbot Hq Hty' Heq ]; subst.
  - exact Hclos.
  - exfalso. exact (Hnobot p0 Hbot).
Qed.

(* ----------------------------------------------------------------- *)
(* 4b.  Deviation SR is recoverable under exactly the hypothesis that  *)
(*      Remark 3 leaves open: a TOTAL residual that itself types.      *)
(* ----------------------------------------------------------------- *)
Theorem sr_dev_with_total_qres :
  forall G p K,
    k_M (idev p K) p = Mbot ->
    (exists G', qres G p = Some G' /\ ctypesM G' (idev p K)) ->
    ctypesM G (idev p K).
Proof.
  intros G p K Hbot [G' [HG' Hty]].
  eapply CTM_Quar; eauto.
Qed.

End Typing.

(* ----------------------------------------------------------------- *)
(* 4c.  THE MAIN NEGATIVE RESULT.                                      *)
(*                                                                     *)
(*  With the partial residual of Remark 3 option (b) -- the option the *)
(*  draft prefers -- NO protocol whose head is a capability is typable *)
(*  at all.  Reason: the downgrade-closure premise of T-Act-M recurses *)
(*  at the SAME node with the role's mode lowered; after two           *)
(*  unfoldings the role is at bottom, where only T-Quar applies, and   *)
(*  the residual is undefined.  Consequently thm:isr is only VACUOUSLY *)
(*  true and rule Ach-M can never be derived for a pack that uses any  *)
(*  capability.                                                        *)
(* ----------------------------------------------------------------- *)

Definition qres_partial : Gt -> Role -> option Gt := fun _ _ => None.

Lemma no_act_typing_partial :
  forall D Gg K, ctypesM D qres_partial Gg K -> forall a p G, Gg <> GAct a p G.
Proof.
  intros D Gg K H.
  induction H as [ K Hend
                 | phi xs G K Hphi Hty IH
                 | a p G K W' P Hsp Hpre Heff Hnb Hirr Hcont IHcont Hclos IHclos
                 | G p K G' Hbot Hq Hty IH ];
    intros a0 p0 G0.
  - discriminate.
  - discriminate.
  - intro Heq. exact (IHclos a p G eq_refl).
  - unfold qres_partial in Hq. discriminate.
Qed.

Theorem act_vacuous_with_partial_qres :
  forall D a p G K, ~ ctypesM D qres_partial (GAct a p G) K.
Proof.
  intros D a p G K H.
  exact (no_act_typing_partial D _ _ H a p G eq_refl).
Qed.

(* The vacuity propagates through goal markers, so a realistic pack
   (a goal-marked protocol that calls a tool) is untypable too. *)
Corollary goal_then_act_vacuous :
  forall D phi xs a p G K,
    ~ ctypesM D qres_partial (GGoal phi xs (GAct a p G)) K.
Proof.
  intros D phi xs a p G K H.
  inversion H as [ | phi0 xs0 G0 K0 Hphi Hty Heq
                 | | G0 p0 K0 G0' Hbot Hq Hty Heq ]; subst.
  - eapply act_vacuous_with_partial_qres. exact Hty.
  - unfold qres_partial in Hq. discriminate.
Qed.

(* ================================================================= *)
(*  Section 5.  Auditing thm:checkpoint                               *)
(* ================================================================= *)

(* The paper's WF-Loop (Definition 3): every cycle contains at least one
   GOAL MARKER or one REFRESH.  But the grade semantics resets a grade
   only on a refresh -- a goal marker sanitizes TAINT, not GRADE.       *)

(* iterating a cycle whose only checkpoint is a goal marker *)
Fixpoint grade_goal_only (D n : nat) (d : GradeEnv) (p : Role) : GradeEnv :=
  match n with
  | 0 => d
  | S k => grade_goal_only D k (tick D d p) p
  end.

(* iterating a cycle that contains a refresh *)
Fixpoint grade_refresh (D n : nat) (d : GradeEnv) (p : Role) : GradeEnv :=
  match n with
  | 0 => d
  | S k => grade_refresh D k (gupd (tick D d p) p 0) p
  end.

Lemma tick_reaches_cap :
  forall D p n d, d p + n >= D -> grade_goal_only D n d p p >= min D (d p + n).
Proof.
  intros D p n. induction n as [ | k IH ]; intros d H.
  - simpl. rewrite Nat.add_0_r. apply Nat.le_min_r.
  - simpl.
    assert (Ht : tick D d p p = min D (S (d p))) by apply tick_self.
    assert (Hge : tick D d p p + k >= D).
    { rewrite Ht. destruct (Nat.min_dec D (S (d p))) as [Hm | Hm]; rewrite Hm; lia. }
    specialize (IH (tick D d p) Hge). rewrite Ht in IH, Hge.
    assert (HD : min D (min D (S (d p)) + k) = D) by (apply Nat.min_l; lia).
    rewrite HD in IH.
    eapply Nat.le_trans; [ apply Nat.le_min_l | exact IH ].
Qed.

(* REFUTATION: on a WF-Loop-conformant cycle whose only checkpoint is a
   goal marker, the grade saturates at the cap and stays there.  The
   regeneration premise of the renewal argument therefore fails. *)
Theorem goal_only_cycle_hits_cap :
  forall D p d, grade_goal_only D D d p p >= D.
Proof.
  intros D p d.
  eapply Nat.le_trans; [ | apply tick_reaches_cap; lia ].
  apply Nat.min_glb; lia.
Qed.

(* THE REPAIR, PROVED: requiring a REFRESH in every cycle -- not merely a
   goal marker -- does give the regeneration property the renewal
   argument needs. *)
Theorem wfloop_refresh_grade_bounded :
  forall D p n d, n > 0 -> grade_refresh D n d p p = 0.
Proof.
  intros D p n. induction n as [ | k IH ]; intros d Hn.
  - inversion Hn.
  - simpl. destruct k as [ | k' ].
    + simpl. unfold gupd. destruct (role_eq_dec p p); congruence.
    + apply IH. lia.
Qed.

(* ================================================================= *)
(*  Section 6.  The vacuity result is NOT an artifact of reading the  *)
(*  judgment inductively.  The paper states that the mode-graded      *)
(*  judgment is COINDUCTIVE (like the base one).  We therefore redo   *)
(*  the argument for the greatest fixed point.                        *)
(*                                                                     *)
(*  It still holds: the downgrade-closure premise forces a STRICTLY    *)
(*  DESCENDING chain in the 3-point mode lattice, and at bottom no     *)
(*  rule applies when the quarantine residual is partial.  A           *)
(*  coinductive derivation cannot escape a finite chain of obligations *)
(*  whose last link is unsatisfiable.                                  *)
(* ================================================================= *)

Definition mode_rank (m : Mode) : nat :=
  match m with Mbot => 0 | Mdr => 1 | Mok => 2 end.

Lemma mode_rank_down : forall m, m <> Mbot -> mode_rank (down m) < mode_rank m.
Proof. destruct m; simpl; intros H; [ lia | lia | congruence ]. Qed.

Section CoTyping.
Variable D : nat.
Variable qresC : Gt -> Role -> option Gt.

CoInductive ctypesC : Gt -> Cfg -> Prop :=
| CTC_End : forall K,
    (forall r, k_s K r = PEnd) ->
    ctypesC GEnd K
| CTC_Goal : forall phi xs G K,
    phi (k_W K) ->
    ctypesC G (mkCfg (k_s K) (k_W K) (k_M K) (k_d K) (sanitize (k_T K) xs)) ->
    ctypesC (GGoal phi xs G) K
| CTC_Act : forall a p G K W' P,
    k_s K p = PAct a P ->
    c_pre a (k_W K) ->
    c_eff a (k_W K) W' ->
    k_M K p <> Mbot ->
    (c_irr a = true -> TaintClear (k_T K) (c_supp a) /\ ge_dr (k_M K p) = true) ->
    ctypesC G (mkCfg (supd (k_s K) p P) W' (k_M K)
                     (tick D (k_d K) p) (taint_upd (k_T K) a (k_M K p))) ->
    ctypesC (GAct a p G) (mkCfg (k_s K) (k_W K)
                                (mupd (k_M K) p (down (k_M K p)))
                                (tick D (k_d K) p) (k_T K)) ->
    ctypesC (GAct a p G) K
| CTC_Quar : forall G p K G',
    k_M K p = Mbot ->
    qresC G p = Some G' ->
    ctypesC G' K ->
    ctypesC G K.
End CoTyping.

Lemma mupd_same : forall (M : ModeEnv) r m, mupd M r m r = m.
Proof. intros. unfold mupd. destruct (role_eq_dec r r); congruence. Qed.

(* Coinductive vacuity: with the partial residual, no configuration is
   typable at a protocol whose head is a capability -- for ANY mode. *)
Lemma no_act_typingC :
  forall D n a p G K,
    mode_rank (k_M K p) <= n -> ~ ctypesC D qres_partial (GAct a p G) K.
Proof.
  intros D n. induction n as [ | n IH ]; intros a p G K Hrank Hty.
  - inversion Hty as [ | | a0 p0 G0 K0 W' P Hsp Hpre Heff Hnb Hirr Hcont Hclos Heq
                     | G0 p0 K0 G0' Hbot Hq Hty' Heq ]; subst.
    + apply Hnb. destruct (k_M K p) eqn:E; simpl in Hrank; try lia. reflexivity.
    + unfold qres_partial in Hq. discriminate.
  - inversion Hty as [ | | a0 p0 G0 K0 W' P Hsp Hpre Heff Hnb Hirr Hcont Hclos Heq
                     | G0 p0 K0 G0' Hbot Hq Hty' Heq ]; subst.
    + eapply IH; [ | exact Hclos ].
      simpl. rewrite mupd_same.
      assert (Hlt : mode_rank (down (k_M K p)) < mode_rank (k_M K p))
        by (apply mode_rank_down; exact Hnb).
      lia.
    + unfold qres_partial in Hq. discriminate.
Qed.

Theorem act_vacuous_coinductive :
  forall D a p G K, ~ ctypesC D qres_partial (GAct a p G) K.
Proof.
  intros D a p G K.
  eapply no_act_typingC with (n := mode_rank (k_M K p)). lia.
Qed.

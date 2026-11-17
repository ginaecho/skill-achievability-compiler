(* ================================================================= *)
(*  EnvBridge.v -- the BRIDGE for protocols with environment choices,  *)
(*  and a worked policy instance.                                      *)
(*                                                                     *)
(*  Conformance (ctypesE) treats an environment choice as T-Comm does  *)
(*  a participant choice: the environment role offers exactly the      *)
(*  protocol's answers, the agent accepts at least them.  The          *)
(*  instrumented head-move semantics (hstepE) gives an environment     *)
(*  step cost 0 whatever the answer.  Hence a session typed against a  *)
(*  k-tolerant protocol is hazard-free on every run of misselection    *)
(*  cost at most k, for every resolution of the environment choices.   *)
(*                                                                     *)
(*  Coq 8.18, stdlib only, axiom-free (check_bridge.v).                *)
(* ================================================================= *)

Require Import List Arith Lia Bool.
Import ListNotations.
Require Import Severity Bridge EnvSeverity.

Section BridgeEnv.
Variable E : Ctx.
Variable Haz : World -> Prop.

Inductive ctypesE : Ge -> Sess -> World -> Prop :=
| CE_End : forall s W,
    (forall r, s r = PEnd) ->
    ctypesE EEnd s W
| CE_Goal : forall phi G s W,
    phi W -> ctypesE G s W -> ctypesE (EGoal phi G) s W
| CE_Act : forall a p G s W P,
    s p = PAct a P ->
    (exists W', E a W W') ->
    (forall W', E a W W' -> ctypesE G (supd s p P) W') ->
    ctypesE (EAct a p G) s W
| CE_Comm : forall p q brs s W sendb recvb,
    p <> q ->
    s p = POut q sendb ->
    s q = PIn  p recvb ->
    brs <> nil ->
    (forall l psi Gl, In (l, psi, Gl) brs -> exists P, In (l, P) sendb) ->
    (forall l P, In (l, P) sendb -> exists psi Gl, In (l, psi, Gl) brs) ->
    (forall l psi Gl, In (l, psi, Gl) brs -> exists Q, In (l, Q) recvb) ->
    (forall l psi Gl P Q,
        In (l, psi, Gl) brs -> In (l, P) sendb -> In (l, Q) recvb ->
        ctypesE Gl (supd (supd s p P) q Q) W) ->
    ctypesE (EComm p q brs) s W
(* the environment, as role p, offers exactly the protocol's answers *)
| CE_Env : forall p q brs s W sendb recvb,
    p <> q ->
    s p = POut q sendb ->
    s q = PIn  p recvb ->
    brs <> nil ->
    (forall l Gl, In (l, Gl) brs -> exists P, In (l, P) sendb) ->
    (forall l P, In (l, P) sendb -> exists Gl, In (l, Gl) brs) ->
    (forall l Gl, In (l, Gl) brs -> exists Q, In (l, Q) recvb) ->
    (forall l Gl P Q,
        In (l, Gl) brs -> In (l, P) sendb -> In (l, Q) recvb ->
        ctypesE Gl (supd (supd s p P) q Q) W) ->
    ctypesE (EEnv p q brs) s W.

Inductive hstepE : Ge -> Sess -> World -> Ge -> Sess -> World -> Role -> nat -> Prop :=
| HE_Act : forall a p G s W W' P,
    s p = PAct a P -> E a W W' ->
    hstepE (EAct a p G) s W G (supd s p P) W' p 0
| HE_Goal : forall phi G s W G' s' W' r c,
    hstepE G s W G' s' W' r c ->
    hstepE (EGoal phi G) s W G' s' W' r c
| HE_Comm_ok : forall p q brs s W sendb recvb l psi Gl P Q,
    s p = POut q sendb -> s q = PIn p recvb ->
    In (l, psi, Gl) brs -> In (l, P) sendb -> In (l, Q) recvb ->
    psi W ->
    hstepE (EComm p q brs) s W Gl (supd (supd s p P) q Q) W p 0
| HE_Comm_dev : forall p q brs s W sendb recvb l psi Gl P Q,
    s p = POut q sendb -> s q = PIn p recvb ->
    In (l, psi, Gl) brs -> In (l, P) sendb -> In (l, Q) recvb ->
    ~ psi W ->
    hstepE (EComm p q brs) s W Gl (supd (supd s p P) q Q) W p 1
(* an environment answer: any of them, and it costs nothing *)
| HE_Env : forall p q brs s W sendb recvb l Gl P Q,
    s p = POut q sendb -> s q = PIn p recvb ->
    In (l, Gl) brs -> In (l, P) sendb -> In (l, Q) recvb ->
    hstepE (EEnv p q brs) s W Gl (supd (supd s p P) q Q) W p 0.

Inductive hrunE : Ge -> Sess -> World -> list (Role * nat) -> Ge -> Sess -> World -> Prop :=
| HRE_refl : forall G s W, hrunE G s W [] G s W
| HRE_step : forall G s W G1 s1 W1 r c tr G2 s2 W2,
    hstepE G s W G1 s1 W1 r c ->
    hrunE G1 s1 W1 tr G2 s2 W2 ->
    hrunE G s W ((r, c) :: tr) G2 s2 W2.

Lemma safeE_not_haz : forall b G W, safeE E Haz b G W -> ~ Haz W.
Proof. intros b G W H. inversion H; assumption. Qed.

(* an environment step never debits the budget *)
Theorem env_step_costs_nothing : forall p q brs s W G' s' W' r c,
  hstepE (EEnv p q brs) s W G' s' W' r c -> c = 0.
Proof. intros. inversion H; subst; reflexivity. Qed.

(* every answer the environment may give is a step the session takes:
   the runs below quantify over every resolution of the environment *)
Theorem env_every_answer_steps : forall p q brs s W,
  ctypesE (EEnv p q brs) s W ->
  forall l Gl, In (l, Gl) brs ->
    exists s', hstepE (EEnv p q brs) s W Gl s' W p 0.
Proof.
  intros p q brs s W Ht l Gl Hin.
  inversion Ht as [ | | | | p0 q0 brs0 s0 W0 sendb recvb Hpq Hsp Hsq Hne Hl1 Hl2 Hl3 Hcont ]; subst.
  destruct (Hl1 _ _ Hin) as [P HP]. destruct (Hl3 _ _ Hin) as [Q HQ].
  exists (supd (supd s p P) q Q). eapply HE_Env; eassumption.
Qed.

Fixpoint finishedE (G : Ge) : Prop :=
  match G with
  | EEnd => True
  | EGoal _ G0 => finishedE G0
  | _ => False
  end.

Theorem progressE :
  (forall (psi : World -> Prop) (W : World), psi W \/ ~ psi W) ->
  forall G s W, ctypesE G s W -> ~ finishedE G ->
    exists G' s' W' r c, hstepE G s W G' s' W' r c.
Proof.
  intros Hdec G s W Ht. induction Ht as [ s W Hend
                                        | phi G s W Hphi Ht IH
                                        | a p G s W P Hsp Hex Hall IH
                                        | p q brs s W sendb recvb Hpq Hsp Hsq Hne Hl1 Hl2 Hl3 Hcont IH
                                        | p q brs s W sendb recvb Hpq Hsp Hsq Hne Hl1 Hl2 Hl3 Hcont IH ];
    intro Hnf.
  - exfalso. apply Hnf. exact I.
  - destruct (IH Hnf) as [G' [s' [W' [r [c Hst]]]]].
    exists G', s', W', r, c. apply HE_Goal. exact Hst.
  - destruct Hex as [W' HE].
    exists G, (supd s p P), W', p, 0. eapply HE_Act; eassumption.
  - destruct brs as [ | [[l psi] Gl] tl ]; [ exfalso; apply Hne; reflexivity | ].
    assert (Hin : In (l, psi, Gl) ((l, psi, Gl) :: tl)) by (left; reflexivity).
    destruct (Hl1 _ _ _ Hin) as [P HP]. destruct (Hl3 _ _ _ Hin) as [Q HQ].
    destruct (Hdec psi W) as [Hg | Hg].
    + exists Gl, (supd (supd s p P) q Q), W, p, 0. eapply HE_Comm_ok; eassumption.
    + exists Gl, (supd (supd s p P) q Q), W, p, 1. eapply HE_Comm_dev; eassumption.
  - destruct brs as [ | [l Gl] tl ]; [ exfalso; apply Hne; reflexivity | ].
    assert (Hin : In (l, Gl) ((l, Gl) :: tl)) by (left; reflexivity).
    destruct (Hl1 _ _ Hin) as [P HP]. destruct (Hl3 _ _ Hin) as [Q HQ].
    exists Gl, (supd (supd s p P) q Q), W, p, 0. eapply HE_Env; eassumption.
Qed.

(* ================================================================= *)
(*  THE BRIDGE, one step.                                              *)
(* ================================================================= *)
Theorem bridgeE_step :
  forall G s W G' s' W' r c b,
    ctypesE G s W ->
    safeE E Haz b G W ->
    hstepE G s W G' s' W' r c ->
    c <= b ->
    ctypesE G' s' W' /\ safeE E Haz (b - c) G' W'.
Proof.
  intros G s W G' s' W' r c b Hct Hsf Hst.
  revert b Hct Hsf.
  induction Hst as [ a p G s W W' P Hsp Heff
                   | phi G s W G' s' W' r c Hst IH
                   | p q brs s W sendb recvb l psi Gl P Q Hsp Hsq Hin HinP HinQ Hpsi
                   | p q brs s W sendb recvb l psi Gl P Q Hsp Hsq Hin HinP HinQ Hpsi
                   | p q brs s W sendb recvb l Gl P Q Hsp Hsq Hin HinP HinQ ];
    intros b Hct Hsf Hcb.
  - inversion Hct as [ | | a0 p0 G0 s0 W0 P0 Hsp0 Hex Hall | | ]; subst.
    rewrite Hsp in Hsp0. inversion Hsp0; subst P0.
    inversion Hsf as [ | | b0 a1 p1 G1 W1 Hnh Hsafe | | ]; subst.
    rewrite Nat.sub_0_r. split; [ apply Hall; assumption | apply Hsafe; assumption ].
  - inversion Hct as [ | phi0 G0 s0 W0 Hphi Hct' | | | ]; subst.
    inversion Hsf as [ | b0 phi1 G1 W1 Hnh Hsf' | | | ]; subst.
    apply IH; assumption.
  - inversion Hct as [ | | | p0 q0 brs0 s0 W0 sendb0 recvb0 Hpq Hsp0 Hsq0 Hne Hl1 Hl2 Hl3 Hcont | ]; subst.
    rewrite Hsp in Hsp0. inversion Hsp0; subst sendb0.
    rewrite Hsq in Hsq0. inversion Hsq0; subst recvb0.
    inversion Hsf as [ | | | b0 p1 q1 brs1 W1 Hnh Hok Hdev | ]; subst.
    rewrite Nat.sub_0_r. split.
    + apply (Hcont l psi Gl P Q); assumption.
    + apply (Hok l psi Gl); assumption.
  - inversion Hct as [ | | | p0 q0 brs0 s0 W0 sendb0 recvb0 Hpq Hsp0 Hsq0 Hne Hl1 Hl2 Hl3 Hcont | ]; subst.
    rewrite Hsp in Hsp0. inversion Hsp0; subst sendb0.
    rewrite Hsq in Hsq0. inversion Hsq0; subst recvb0.
    inversion Hsf as [ | | | b0 p1 q1 brs1 W1 Hnh Hok Hdev | ]; subst.
    destruct b as [ | b' ]; [ lia | ].
    replace (S b' - 1) with b' by lia.
    split.
    + apply (Hcont l psi Gl P Q); assumption.
    + apply (Hdev l psi Gl Hin Hpsi b' eq_refl).
  - (* environment answer: cost 0, every answer typed at the same budget *)
    inversion Hct as [ | | | | p0 q0 brs0 s0 W0 sendb0 recvb0 Hpq Hsp0 Hsq0 Hne Hl1 Hl2 Hl3 Hcont ]; subst.
    rewrite Hsp in Hsp0. inversion Hsp0; subst sendb0.
    rewrite Hsq in Hsq0. inversion Hsq0; subst recvb0.
    inversion Hsf as [ | | | | b0 p1 q1 brs1 W1 Hnh Hall ]; subst.
    rewrite Nat.sub_0_r. split.
    + apply (Hcont l Gl P Q); assumption.
    + apply (Hall l Gl Hin).
Qed.

(* ================================================================= *)
(*  THE BRIDGE, whole runs: every run of misselection cost <= k, for   *)
(*  every resolution of the environment choices, is hazard-free.       *)
(* ================================================================= *)
Theorem bridgeE_run :
  forall G s W tr G' s' W' b,
    ctypesE G s W ->
    safeE E Haz b G W ->
    hrunE G s W tr G' s' W' ->
    total tr <= b ->
    ~ Haz W' /\ ctypesE G' s' W' /\ safeE E Haz (b - total tr) G' W'.
Proof.
  intros G s W tr G' s' W' b Hct Hsf Hrun.
  revert b Hct Hsf.
  induction Hrun as [ G s W
                    | G s W G1 s1 W1 r c tr G2 s2 W2 Hst Hrun IH ];
    intros b Hct Hsf Htot.
  - simpl. rewrite Nat.sub_0_r. repeat split; try assumption.
    eapply safeE_not_haz; eassumption.
  - unfold total in Htot; simpl in Htot. fold (total tr) in Htot.
    assert (Hcb : c <= b) by lia.
    destruct (bridgeE_step G s W G1 s1 W1 r c b Hct Hsf Hst Hcb) as [Hct1 Hsf1].
    assert (Htot' : total tr <= b - c) by lia.
    destruct (IH (b - c) Hct1 Hsf1 Htot') as [Hnh [Hct2 Hsf2]].
    repeat split; try assumption.
    unfold total; simpl; fold (total tr).
    replace (b - (c + total tr)) with (b - c - total tr) by lia.
    exact Hsf2.
Qed.

(* every configuration along the run, not only the last *)
Theorem bridgeE_every_configuration :
  forall G s W tr1 G1 s1 W1 tr2 G2 s2 W2 b,
    ctypesE G s W ->
    safeE E Haz b G W ->
    hrunE G s W tr1 G1 s1 W1 ->
    hrunE G1 s1 W1 tr2 G2 s2 W2 ->
    total (tr1 ++ tr2) <= b ->
    ~ Haz W1 /\ ~ Haz W2.
Proof.
  intros G s W tr1 G1 s1 W1 tr2 G2 s2 W2 b Hct Hsf H1 H2 Hle.
  rewrite total_app in Hle.
  destruct (bridgeE_run G s W tr1 G1 s1 W1 b Hct Hsf H1 ltac:(lia)) as [Hn1 [Hct1 Hsf1]].
  destruct (bridgeE_run G1 s1 W1 tr2 G2 s2 W2 (b - total tr1) Hct1 Hsf1 H2 ltac:(lia))
    as [Hn2 _].
  split; assumption.
Qed.

(* budgets distribute over participants; environment steps cost nothing,
   so the environment needs no allowance of its own *)
Theorem budgetE_distributes :
  forall G s W tr G' s' W' (k : Role -> nat) (R : list Role) b,
    ctypesE G s W ->
    safeE E Haz b G W ->
    hrunE G s W tr G' s' W' ->
    NoDup R -> covers R tr ->
    (forall r, In r R -> percost r tr <= k r) ->
    sumR k R <= b ->
    ~ Haz W'.
Proof.
  intros G s W tr G' s' W' k R b Hct Hsf Hrun Hnd Hcov Hper Hsum.
  assert (Htot : total tr <= b).
  { rewrite (total_eq_sum_percost R tr Hnd Hcov).
    eapply Nat.le_trans; [ | exact Hsum ].
    apply sumR_pointwise_le. exact Hper. }
  exact (proj1 (bridgeE_run G s W tr G' s' W' b Hct Hsf Hrun Htot)).
Qed.

End BridgeEnv.

(* ================================================================= *)
(*  A WORKED POLICY INSTANCE.                                          *)
(*                                                                     *)
(*  The shape of the tau-bench procedures: the agent (role 0) judges a *)
(*  policy rule ("only if C") and proceeds or refuses; the user (role  *)
(*  1, the environment) answers the confirmation; on "yes" the agent   *)
(*  fires the irreversible tool.                                       *)
(*                                                                     *)
(*    Gpol = 0->1 { proceed[rule_ok]. 1=>0 { yes. act@0. end ;          *)
(*                                          no. end } ;                *)
(*                  refuse[~rule_ok]. end }                            *)
(*                                                                     *)
(*  Hazard: the irreversible action fired while the rule is violated.  *)
(*  The rule lives only in the policy text (E_pol: the tool checks     *)
(*  nothing), so Gpol is 0-tolerant and not 1-tolerant: k* = 0.        *)
(*  ENFORCE moves the rule into the tool's precondition (E_enf), and   *)
(*  the same protocol is tolerant at every budget.                     *)
(* ================================================================= *)
Definition rule_ok : Var := 2.
Definition done    : Var := 3.
Definition consent : Var := 4.

Definition E_pol : Ctx := fun a W W' => a = 5 /\ W' = wupd W done 1.
Definition E_enf : Ctx := fun a W W' => a = 5 /\ W rule_ok = 1 /\ W' = wupd W done 1.
Definition Haz_pol : World -> Prop := fun W => W done = 1 /\ W rule_ok = 0.

Definition confirm_then_act : Ge := EEnv 1 0 [ (30, EAct 5 0 EEnd) ; (31, EEnd) ].
Definition Gpol : Ge :=
  EComm 0 1 [ (20, (fun W : World => W rule_ok = 1), confirm_then_act) ;
              (21, (fun W : World => W rule_ok = 0), EEnd) ].

Lemma notHaz_pol_W0 : ~ Haz_pol W0.
Proof. intros [H _]. discriminate H. Qed.

Theorem Gpol_is_0_tolerant : safeE E_pol Haz_pol 0 Gpol W0.
Proof.
  apply SE_comm; [ apply notHaz_pol_W0 | | ].
  - intros l psi Gl Hin Hpsi. simpl in Hin.
    destruct Hin as [Heq | [Heq | []]]; inversion Heq; subst.
    + discriminate Hpsi.
    + apply SE_end. apply notHaz_pol_W0.
  - intros l psi Gl Hin Hpsi c Hb. discriminate Hb.
Qed.

(* one wrong judgement, and the user's "yes" is the adversary's answer *)
Theorem Gpol_not_1_tolerant : ~ safeE E_pol Haz_pol 1 Gpol W0.
Proof.
  rewrite TE_exact. intro H. apply H.
  eapply RE_comm_dev; [ left; reflexivity | simpl; discriminate | ].
  eapply RE_env; [ left; reflexivity | ].
  eapply RE_act; [ split; reflexivity | ].
  apply RE_here. split; reflexivity.
Qed.

Corollary Gpol_kstar_is_0 : principalE E_pol Haz_pol 0 Gpol W0.
Proof. split; [ exact Gpol_is_0_tolerant | exact Gpol_not_1_tolerant ]. Qed.

(* ENFORCED: the rule is the tool's precondition.  Tolerant at every
   budget, from every world that is not already a hazard. *)
Theorem Genf_is_k_tolerant : forall k W, ~ Haz_pol W -> safeE E_enf Haz_pol k Gpol W.
Proof.
  intros k W Hnh.
  assert (Hcta : safeE E_enf Haz_pol k (EAct 5 0 EEnd) W).
  { apply SE_act; [ exact Hnh | ]. intros W' [_ [Hr ->]]. apply SE_end.
    intros [_ Hc]. rewrite wupd_other in Hc by (unfold rule_ok, done; lia). congruence. }
  assert (Hc : safeE E_enf Haz_pol k confirm_then_act W).
  { apply SE_env; [ exact Hnh | ]. intros l Gl Hin. simpl in Hin.
    destruct Hin as [Heq | [Heq | []]]; inversion Heq; subst; [ exact Hcta | apply SE_end; exact Hnh ]. }
  apply SE_comm; [ exact Hnh | | ].
  - intros l psi Gl Hin _. simpl in Hin.
    destruct Hin as [Heq | [Heq | []]]; inversion Heq; subst; [ exact Hc | apply SE_end; exact Hnh ].
  - intros l psi Gl Hin _ c _. simpl in Hin.
    destruct Hin as [Heq | [Heq | []]]; inversion Heq; subst;
      [ | apply SE_end; exact Hnh ].
    apply SE_env; [ exact Hnh | ]. intros l0 Gl0 Hin0. simpl in Hin0.
    destruct Hin0 as [Heq0 | [Heq0 | []]]; inversion Heq0; subst; [ | apply SE_end; exact Hnh ].
    apply SE_act; [ exact Hnh | ]. intros W' [_ [Hr ->]]. apply SE_end.
    intros [_ Hc']. rewrite wupd_other in Hc' by (unfold rule_ok, done; lia). congruence.
Qed.

(* NON-VACUITY: the policy session conforms, and the bridge is tight. *)
Definition agent_pol : Proc :=
  POut 1 [ (20, PIn 1 [ (30, PAct 5 PEnd) ; (31, PEnd) ]) ; (21, PEnd) ].
Definition user_pol : Proc :=
  PIn 0 [ (20, POut 0 [ (30, PEnd) ; (31, PEnd) ]) ; (21, PEnd) ].
Definition sess_pol : Sess := sess2 agent_pol user_pol.

Ltac supd_end :=
  intro r; unfold supd, sess2; repeat (destruct (Nat.eq_dec _ _)); subst; try reflexivity; try lia.

Theorem Gpol_inhabited : forall W, ctypesE E_pol Gpol sess_pol W.
Proof.
  intro W. unfold Gpol, sess_pol.
  apply CE_Comm with (sendb := [ (20, PIn 1 [ (30, PAct 5 PEnd) ; (31, PEnd) ]) ; (21, PEnd) ])
                     (recvb := [ (20, POut 0 [ (30, PEnd) ; (31, PEnd) ]) ; (21, PEnd) ]);
    try reflexivity; try discriminate.
  - intros l psi Gl Hin. simpl in Hin. destruct Hin as [Heq | [Heq | []]]; inversion Heq; subst;
      eexists; simpl; eauto.
  - intros l P Hin. simpl in Hin. destruct Hin as [Heq | [Heq | []]]; inversion Heq; subst;
      do 2 eexists; simpl; eauto.
  - intros l psi Gl Hin. simpl in Hin. destruct Hin as [Heq | [Heq | []]]; inversion Heq; subst;
      eexists; simpl; eauto.
  - intros l psi Gl P Q Hin HP HQ. simpl in Hin, HP, HQ.
    destruct Hin as [Heq | [Heq | []]]; inversion Heq; subst;
    destruct HP as [HP | [HP | []]]; inversion HP; subst;
    destruct HQ as [HQ | [HQ | []]]; inversion HQ; subst; try discriminate.
    + (* proceed: the user answers *)
      unfold confirm_then_act.
      apply CE_Env with (sendb := [ (30, PEnd) ; (31, PEnd) ])
                        (recvb := [ (30, PAct 5 PEnd) ; (31, PEnd) ]);
        try discriminate.
      * unfold supd. destruct (Nat.eq_dec 1 0); [ discriminate | ].
        destruct (Nat.eq_dec 1 1); [ reflexivity | contradiction ].
      * unfold supd. destruct (Nat.eq_dec 0 1); [ discriminate | ].
        destruct (Nat.eq_dec 0 0); [ reflexivity | contradiction ].
      * intros l1 Gl1 Hin1. simpl in Hin1. destruct Hin1 as [Hq1 | [Hq1 | []]]; inversion Hq1; subst;
          eexists; simpl; eauto.
      * intros l1 P1 Hin1. simpl in Hin1. destruct Hin1 as [Hq1 | [Hq1 | []]]; inversion Hq1; subst;
          eexists; simpl; eauto.
      * intros l1 Gl1 Hin1. simpl in Hin1. destruct Hin1 as [Hq1 | [Hq1 | []]]; inversion Hq1; subst;
          eexists; simpl; eauto.
      * intros l1 Gl1 P1 Q1 Hin1 HP0 HQ0. simpl in Hin1, HP0, HQ0.
        destruct Hin1 as [Hq1 | [Hq1 | []]]; inversion Hq1; subst;
        destruct HP0 as [HP1 | [HP1 | []]]; inversion HP1; subst;
        destruct HQ0 as [HQ1 | [HQ1 | []]]; inversion HQ1; subst; try discriminate.
        -- (* yes: the agent acts *)
           apply CE_Act with (P := PEnd).
           ++ unfold supd. destruct (Nat.eq_dec 0 0); [ reflexivity | contradiction ].
           ++ exists (wupd W done 1). split; reflexivity.
           ++ intros W' _. apply CE_End. supd_end.
        -- apply CE_End. supd_end.
    + apply CE_End. supd_end.
Qed.

(* the guarantee, concretely: at budget 0, every run -- whatever the
   user answers -- is hazard-free *)
Theorem Gpol_safe_for_every_answer : forall tr G' s' W',
  hrunE E_pol Gpol sess_pol W0 tr G' s' W' -> total tr = 0 -> ~ Haz_pol W'.
Proof.
  intros tr G' s' W' Hr Ht.
  exact (proj1 (bridgeE_run E_pol Haz_pol Gpol sess_pol W0 tr G' s' W' 0
                  (Gpol_inhabited W0) Gpol_is_0_tolerant Hr ltac:(lia))).
Qed.

(* ... and the budget is tight: one misselection and a "yes" reach harm *)
Theorem Gpol_one_misselection_harms : exists tr G' s' W',
  hrunE E_pol Gpol sess_pol W0 tr G' s' W' /\ total tr = 1 /\ Haz_pol W'.
Proof.
  set (P1 := PIn 1 [ (30, PAct 5 PEnd) ; (31, PEnd) ]).
  set (Q1 := POut 0 [ (30, PEnd) ; (31, PEnd) ]).
  set (s1 := supd (supd sess_pol 0 P1) 1 Q1).
  set (s2 := supd (supd s1 1 PEnd) 0 (PAct 5 PEnd)).
  exists [ (0, 1) ; (1, 0) ; (0, 0) ], EEnd, (supd s2 0 PEnd), (wupd W0 done 1).
  split; [ | split; [ reflexivity | split; reflexivity ] ].
  eapply HRE_step.
  { eapply HE_Comm_dev with (l := 20) (P := P1) (Q := Q1); try reflexivity.
    - left; reflexivity.
    - left; reflexivity.
    - left; reflexivity.
    - simpl. discriminate. }
  eapply HRE_step.
  { eapply HE_Env with (l := 30) (P := PEnd) (Q := PAct 5 PEnd)
                       (sendb := [ (30, PEnd) ; (31, PEnd) ])
                       (recvb := [ (30, PAct 5 PEnd) ; (31, PEnd) ]).
    - unfold s1, supd. destruct (Nat.eq_dec 1 1); [ reflexivity | contradiction ].
    - unfold s1, supd. destruct (Nat.eq_dec 0 1); [ discriminate | ].
      destruct (Nat.eq_dec 0 0); [ reflexivity | contradiction ].
    - left; reflexivity.
    - left; reflexivity.
    - left; reflexivity. }
  eapply HRE_step.
  { eapply HE_Act with (P := PEnd).
    - unfold s2, supd. destruct (Nat.eq_dec 0 0); [ reflexivity | contradiction ].
    - split; reflexivity. }
  apply HRE_refl.
Qed.

(* ================================================================= *)
(*  THE RESIDUAL: when the confirmation is followed by the agent's own *)
(*  execute/hold decision (the other nine policy protocols), enforcing *)
(*  the rule leaves k* = 0 -- executing after a "no" is one            *)
(*  misselection from the action, and no tool can check what the user *)
(*  said -- and narrowing that branch away makes it tolerant at every  *)
(*  budget.  The user's "yes" is recorded by the user's own action     *)
(*  (cap 6, sets consent); the hazard is acting without the rule or    *)
(*  without consent.                                                   *)
(* ================================================================= *)
Definition E_conf : Ctx := fun a W W' =>
  (a = 5 /\ W rule_ok = 1 /\ W' = wupd W done 1) \/ (a = 6 /\ W' = wupd W consent 1).
Definition Haz_conf : World -> Prop :=
  fun W => W done = 1 /\ (W rule_ok = 0 \/ W consent = 0).

Definition after_yes : Ge := EAct 6 1 (EComm 0 1 [ (40, (fun _ : World => True), EAct 5 0 EEnd) ]).
Definition after_no  : Ge :=
  EComm 0 1 [ (40, (fun _ : World => False), EAct 5 0 EEnd) ; (41, (fun _ : World => True), EEnd) ].
Definition after_no_narrowed : Ge := EComm 0 1 [ (41, (fun _ : World => True), EEnd) ].

Definition Gconf (no_branch : Ge) : Ge :=
  EComm 0 1 [ (20, (fun W : World => W rule_ok = 1), EEnv 1 0 [ (30, after_yes) ; (31, no_branch) ]) ;
              (21, (fun W : World => W rule_ok = 0), EEnd) ].

Definition Wok : World := wupd W0 rule_ok 1.

Lemma Wok_rule : Wok rule_ok = 1.
Proof. apply wupd_same. Qed.
Lemma Wok_done : Wok done = 0.
Proof. unfold Wok. rewrite wupd_other by (unfold done, rule_ok; lia). reflexivity. Qed.

(* the rule is enforced, the rule holds, and still one misselection --
   execute after the user said no -- reaches the hazard *)
Theorem Gconf_enforced_not_1_tolerant : ~ safeE E_conf Haz_conf 1 (Gconf after_no) Wok.
Proof.
  rewrite TE_exact. intro H. apply H.
  eapply RE_comm_ok; [ left; reflexivity | apply Wok_rule | ].
  eapply RE_env; [ right; left; reflexivity | ].
  eapply RE_comm_dev; [ left; reflexivity | intro F; exact F | ].
  eapply RE_act; [ left; split; [ reflexivity | split; [ apply Wok_rule | reflexivity ] ] | ].
  apply RE_here. split; [ apply wupd_same | right ].
  rewrite wupd_other by (unfold consent, done; lia).
  unfold Wok. rewrite wupd_other by (unfold consent, rule_ok; lia). reflexivity.
Qed.

(* a safe action leaves a safe world: done with the rule and consent *)
Lemma act_after_consent_safe : forall k W,
  ~ Haz_conf W -> W consent = 1 -> safeE E_conf Haz_conf k (EAct 5 0 EEnd) W.
Proof.
  intros k W Hnh Hc. apply SE_act; [ exact Hnh | ].
  intros W' [[_ [Hr ->]] | [Hbad _]]; [ | discriminate Hbad ].
  apply SE_end. intros [_ [H | H]].
  - rewrite wupd_other in H by (unfold rule_ok, done; lia). congruence.
  - rewrite wupd_other in H by (unfold consent, done; lia). congruence.
Qed.

Lemma after_yes_safe : forall k W, ~ Haz_conf W -> safeE E_conf Haz_conf k after_yes W.
Proof.
  intros k W Hnh. apply SE_act; [ exact Hnh | ].
  intros W' [[Hbad _] | [_ ->]]; [ discriminate Hbad | ].
  assert (Hnh' : ~ Haz_conf (wupd W consent 1)).
  { intros [Hd Hr]. apply Hnh. rewrite wupd_other in Hd by (unfold done, consent; lia).
    split; [ exact Hd | ]. destruct Hr as [Hr | Hr].
    - left. rewrite wupd_other in Hr by (unfold rule_ok, consent; lia). exact Hr.
    - rewrite wupd_same in Hr. discriminate Hr. }
  apply SE_comm; [ exact Hnh' | | ].
  - intros l psi Gl Hin _. simpl in Hin. destruct Hin as [Heq | []]; inversion Heq; subst.
    apply act_after_consent_safe; [ exact Hnh' | apply wupd_same ].
  - intros l psi Gl Hin Hpsi. simpl in Hin. destruct Hin as [Heq | []]; inversion Heq; subst.
    exfalso. apply Hpsi. exact I.
Qed.

Lemma notHaz_conf_Wok : ~ Haz_conf Wok.
Proof. intros [Hd _]. rewrite Wok_done in Hd. discriminate Hd. Qed.

(* ... while without a misselection nothing goes wrong: k* = 0 *)
Theorem Gconf_enforced_is_0_tolerant : safeE E_conf Haz_conf 0 (Gconf after_no) Wok.
Proof.
  pose proof notHaz_conf_Wok as Hnh.
  apply SE_comm; [ exact Hnh | | ].
  - intros l psi Gl Hin Hpsi. simpl in Hin.
    destruct Hin as [Heq | [Heq | []]]; inversion Heq; subst.
    + apply SE_env; [ exact Hnh | ]. intros l Gl Hin. simpl in Hin.
      destruct Hin as [Heq' | [Heq' | []]]; inversion Heq'; subst.
      * apply after_yes_safe. exact Hnh.
      * apply SE_comm; [ exact Hnh | | ].
        -- intros l0 psi0 Gl0 Hin0 Hpsi0. simpl in Hin0.
           destruct Hin0 as [H0 | [H0 | []]]; inversion H0; subst;
             [ destruct Hpsi0 | apply SE_end; exact Hnh ].
        -- intros l0 psi0 Gl0 Hin0 _ c Hc. discriminate Hc.
    + exfalso. rewrite Wok_rule in Hpsi. discriminate Hpsi.
  - intros l psi Gl Hin Hpsi c Hc. discriminate Hc.
Qed.

Corollary Gconf_enforced_kstar_is_0 : principalE E_conf Haz_conf 0 (Gconf after_no) Wok.
Proof. split; [ exact Gconf_enforced_is_0_tolerant | exact Gconf_enforced_not_1_tolerant ]. Qed.

(* NARROWED: drop "execute after no", and every budget is tolerated *)
Theorem Gconf_narrowed_is_k_tolerant : forall k W,
  ~ Haz_conf W -> safeE E_conf Haz_conf k (Gconf after_no_narrowed) W.
Proof.
  intros k W Hnh.
  assert (Hno : forall k', safeE E_conf Haz_conf k' after_no_narrowed W).
  { intro k'. apply SE_comm; [ exact Hnh | | ].
    - intros l psi Gl Hin _. simpl in Hin. destruct Hin as [Heq | []]; inversion Heq; subst.
      apply SE_end; exact Hnh.
    - intros l psi Gl Hin Hpsi. simpl in Hin. destruct Hin as [Heq | []]; inversion Heq; subst.
      exfalso. apply Hpsi. exact I. }
  assert (Henv : forall k', safeE E_conf Haz_conf k'
                   (EEnv 1 0 [ (30, after_yes) ; (31, after_no_narrowed) ]) W).
  { intro k'. apply SE_env; [ exact Hnh | ]. intros l Gl Hin. simpl in Hin.
    destruct Hin as [Heq | [Heq | []]]; inversion Heq; subst;
      [ apply after_yes_safe; exact Hnh | apply Hno ]. }
  apply SE_comm; [ exact Hnh | | ].
  - intros l psi Gl Hin _. simpl in Hin.
    destruct Hin as [Heq | [Heq | []]]; inversion Heq; subst; [ apply Henv | apply SE_end; exact Hnh ].
  - intros l psi Gl Hin _ c _. simpl in Hin.
    destruct Hin as [Heq | [Heq | []]]; inversion Heq; subst; [ apply Henv | apply SE_end; exact Hnh ].
Qed.

(* the narrowed node is an instance of the general narrowing rule *)
Corollary Gconf_narrowing_is_sound : forall k W,
  safeE E_conf Haz_conf k after_no W -> safeE E_conf Haz_conf k after_no_narrowed W.
Proof.
  intros k W Hs. eapply repairE_narrow_sound; [ | exact Hs ].
  intros x Hin. simpl in *. tauto.
Qed.

(* ================================================================= *)
(*  EnvSeverity.v -- ENVIRONMENT-CONTROLLED CHOICE, severity layer.   *)
(*                                                                     *)
(*  Severity.v mechanizes participant-controlled choice only.  The     *)
(*  implementation also supports a choice marked as controlled by the  *)
(*  ENVIRONMENT (what the user answers, what the records show):        *)
(*                                                                     *)
(*     e : { l_i . G_i }                                               *)
(*                                                                     *)
(*  is not an agent decision, so taking any branch costs no budget,    *)
(*  and the adversary picks the branch:                                *)
(*                                                                     *)
(*    RH-Env  (G_i,W) reaches the hazard within b                      *)
(*            ==> (e:{..},W) reaches it within b                       *)
(*    T-Env   W not a hazard, every G_i typed at the SAME budget b     *)
(*            ==> e:{..} typed at b                                    *)
(*                                                                     *)
(*  This file is a CONSERVATIVE EXTENSION: it adds a new syntax Ge     *)
(*  with the extra constructor, re-establishes the severity layer on   *)
(*  it, and proves that Severity.v's protocols embed with the same     *)
(*  reachability, the same condition and the same goal reachability    *)
(*  (reach_embedE, safe_embedE, greach_embedE).  No existing proof is  *)
(*  touched.                                                           *)
(*                                                                     *)
(*  The goal side reads environment branches DEMONICALLY (greachE):    *)
(*  the goal is reachable only if it is reachable whatever the         *)
(*  environment answers -- the implementation's "adversarial" mode.    *)
(*  The default guards are stated over that reading and over hazard    *)
(*  avoidability with the environment adversarial (avoidE).            *)
(*                                                                     *)
(*  Coq 8.18, stdlib only, axiom-free (check_sev.v).                   *)
(* ================================================================= *)

Require Import List Arith Lia.
Import ListNotations.
Require Import Severity.

(* EEnv p q brs: the environment, speaking as role p, answers role q
   with one of the labels of brs.  Branches carry no guard: no answer
   of the environment is a mistake of the agent. *)
Inductive Ge : Type :=
| EEnd  : Ge
| EComm : Role -> Role -> list (Lab * (World -> Prop) * Ge) -> Ge
| EEnv  : Role -> Role -> list (Lab * Ge) -> Ge
| EAct  : CapN -> Role -> Ge -> Ge
| EGoal : (World -> Prop) -> Ge -> Ge.

Fixpoint Ge_size (G : Ge) : nat :=
  match G with
  | EEnd => 1
  | EAct _ _ G0 => S (Ge_size G0)
  | EGoal _ G0 => S (Ge_size G0)
  | EComm _ _ brs => S (fold_right (fun b acc => Ge_size (snd b) + acc) 0 brs)
  | EEnv _ _ brs => S (fold_right (fun b acc => Ge_size (snd b) + acc) 0 brs)
  end.

Lemma in_brs_sizeE :
  forall (brs : list (Lab * (World -> Prop) * Ge)) l psi Gl,
    In (l, psi, Gl) brs ->
    Ge_size Gl < S (fold_right (fun b acc => Ge_size (snd b) + acc) 0 brs).
Proof.
  induction brs as [ | [[l0 psi0] G0] tl IH ]; simpl; intros l psi Gl Hin.
  - contradiction.
  - destruct Hin as [Heq | Hin].
    + inversion Heq; subst; simpl; lia.
    + specialize (IH l psi Gl Hin). simpl in IH. lia.
Qed.

Lemma in_env_size :
  forall (brs : list (Lab * Ge)) l Gl,
    In (l, Gl) brs ->
    Ge_size Gl < S (fold_right (fun b acc => Ge_size (snd b) + acc) 0 brs).
Proof.
  induction brs as [ | [l0 G0] tl IH ]; simpl; intros l Gl Hin.
  - contradiction.
  - destruct Hin as [Heq | Hin].
    + inversion Heq; subst; simpl; lia.
    + specialize (IH l Gl Hin). simpl in IH. lia.
Qed.

(* ================================================================= *)
(*  Budgeted reachability and the condition, with RH-Env and T-Env.   *)
(* ================================================================= *)
Section ReachE.
Variable E : Ctx.
Variable Haz : World -> Prop.

Inductive reachE : nat -> Ge -> World -> Prop :=
| RE_here : forall b G W,
    Haz W -> reachE b G W
| RE_act : forall b a p G W W',
    E a W W' -> reachE b G W' -> reachE b (EAct a p G) W
| RE_goal : forall b phi G W,
    reachE b G W -> reachE b (EGoal phi G) W
| RE_comm_ok : forall b p q brs l psi Gl W,
    In (l, psi, Gl) brs -> psi W ->
    reachE b Gl W -> reachE b (EComm p q brs) W
| RE_comm_dev : forall b p q brs l psi Gl W,
    In (l, psi, Gl) brs -> ~ psi W ->
    reachE b Gl W -> reachE (S b) (EComm p q brs) W
(* RH-Env: the adversary picks the branch, and it costs nothing *)
| RE_env : forall b p q brs l Gl W,
    In (l, Gl) brs ->
    reachE b Gl W -> reachE b (EEnv p q brs) W.

Inductive safeE : nat -> Ge -> World -> Prop :=
| SE_end : forall b W,
    ~ Haz W -> safeE b EEnd W
| SE_goal : forall b phi G W,
    ~ Haz W -> safeE b G W -> safeE b (EGoal phi G) W
| SE_act : forall b a p G W,
    ~ Haz W ->
    (forall W', E a W W' -> safeE b G W') ->
    safeE b (EAct a p G) W
| SE_comm : forall b p q brs W,
    ~ Haz W ->
    (forall l psi Gl, In (l, psi, Gl) brs -> psi W -> safeE b Gl W) ->
    (forall l psi Gl, In (l, psi, Gl) brs -> ~ psi W ->
                      forall c, b = S c -> safeE c Gl W) ->
    safeE b (EComm p q brs) W
(* T-Env: every answer is checked, at the SAME budget *)
| SE_env : forall b p q brs W,
    ~ Haz W ->
    (forall l Gl, In (l, Gl) brs -> safeE b Gl W) ->
    safeE b (EEnv p q brs) W.

(* RH-Env and T-Env, exactly *)
Theorem env_reach_iff : forall b p q brs W,
  reachE b (EEnv p q brs) W <->
  Haz W \/ exists l Gl, In (l, Gl) brs /\ reachE b Gl W.
Proof.
  intros b p q brs W. split.
  - intro H. inversion H; subst.
    + left. assumption.
    + right. eauto.
  - intros [Hh | [l [Gl [Hin Hr]]]].
    + apply RE_here. exact Hh.
    + eapply RE_env; eassumption.
Qed.

Theorem env_typing_iff : forall b p q brs W,
  safeE b (EEnv p q brs) W <->
  ~ Haz W /\ forall l Gl, In (l, Gl) brs -> safeE b Gl W.
Proof.
  intros b p q brs W. split.
  - intro H. inversion H; subst. split; assumption.
  - intros [Hnh Hall]. apply SE_env; assumption.
Qed.

(* SOUNDNESS: the condition at budget b refutes reachability within b *)
Theorem TE_sound :
  forall b G W, safeE b G W -> ~ reachE b G W.
Proof.
  intros b G W Hs Hr. revert Hs.
  induction Hr as [ b G W Hh
                  | b a p G W W' Heff Hr IH
                  | b phi G W Hr IH
                  | b p q brs l psi Gl W Hin Hpsi Hr IH
                  | b p q brs l psi Gl W Hin Hpsi Hr IH
                  | b p q brs l Gl W Hin Hr IH ];
    intros Hs.
  - inversion Hs; subst; contradiction.
  - inversion Hs as [ | | b0 a0 p0 G0 W0 Hnh Hall | | ]; subst.
    exact (IH (Hall W' Heff)).
  - inversion Hs as [ | b0 phi0 G0 W0 Hnh Hsub | | | ]; subst.
    exact (IH Hsub).
  - inversion Hs as [ | | | b0 p0 q0 brs0 W0 Hnh Hok Hdev | ]; subst.
    exact (IH (Hok l psi Gl Hin Hpsi)).
  - inversion Hs as [ | | | b0 p0 q0 brs0 W0 Hnh Hok Hdev | ]; subst.
    exact (IH (Hdev l psi Gl Hin Hpsi b eq_refl)).
  - inversion Hs as [ | | | | b0 p0 q0 brs0 W0 Hnh Hall ]; subst.
    exact (IH (Hall l Gl Hin)).
Qed.

(* COMPLETENESS: and exactly that *)
Theorem TE_complete :
  forall n b G W, Ge_size G <= n -> ~ reachE b G W -> safeE b G W.
Proof.
  induction n as [ | n IH ]; intros b G W Hsz Hnr.
  - destruct G; simpl in Hsz; lia.
  - assert (Hnh : ~ Haz W) by (intro; apply Hnr; apply RE_here; assumption).
    destruct G as [ | p q brs | p q brs | a p G0 | phi G0 ]; simpl in Hsz.
    + apply SE_end; assumption.
    + apply SE_comm; [ assumption | | ].
      * intros l psi Gl Hin Hpsi. apply IH.
        -- pose proof (in_brs_sizeE brs l psi Gl Hin). lia.
        -- intro Hc. apply Hnr. eapply RE_comm_ok; eauto.
      * intros l psi Gl Hin Hpsi c Hb. subst. apply IH.
        -- pose proof (in_brs_sizeE brs l psi Gl Hin). lia.
        -- intro Hc. apply Hnr. eapply RE_comm_dev; eauto.
    + apply SE_env; [ assumption | ].
      intros l Gl Hin. apply IH.
      * pose proof (in_env_size brs l Gl Hin). lia.
      * intro Hc. apply Hnr. eapply RE_env; eauto.
    + apply SE_act; [ assumption | ].
      intros W' Heff. apply IH; [ lia | ].
      intro Hc. apply Hnr. eapply RE_act; eauto.
    + apply SE_goal; [ assumption | ]. apply IH; [ lia | ].
      intro Hc. apply Hnr. apply RE_goal; assumption.
Qed.

Corollary TE_exact :
  forall b G W, safeE b G W <-> ~ reachE b G W.
Proof.
  intros b G W. split.
  - apply TE_sound.
  - intro H. eapply TE_complete; [ apply Nat.le_refl | exact H ].
Qed.

(* T-Sub with environment choices: tolerance is downward closed *)
Theorem toleranceE_downward_closed :
  forall b G W, safeE b G W -> forall b', b' <= b -> safeE b' G W.
Proof.
  intros b G W Hs.
  induction Hs as [ b W Hnh
                  | b phi G W Hnh Hs IH
                  | b a p G W Hnh Hall IH
                  | b p q brs W Hnh Hok IHok Hdev IHdev
                  | b p q brs W Hnh Hall IH ];
    intros b' Hle.
  - apply SE_end; assumption.
  - apply SE_goal; auto.
  - apply SE_act; [ assumption | ]. intros W' Heff. apply (IH W' Heff b' Hle).
  - apply SE_comm; [ assumption | | ].
    + intros l psi Gl Hin Hpsi. apply (IHok l psi Gl Hin Hpsi b' Hle).
    + intros l psi Gl Hin Hpsi c Hb. subst.
      destruct b as [ | c0 ]; [ lia | ].
      apply (IHdev l psi Gl Hin Hpsi c0 eq_refl c). lia.
  - apply SE_env; [ assumption | ].
    intros l Gl Hin. apply (IH l Gl Hin b' Hle).
Qed.

End ReachE.

(* reachability is monotone in the budget, for any target predicate *)
Lemma reachE_mono_budget :
  forall (E : Ctx) (P : World -> Prop) b G W,
    reachE E P b G W -> forall b', b <= b' -> reachE E P b' G W.
Proof.
  intros E P b G W H.
  induction H as [ b G W Hh | b a p G W W' HE H IH | b phi G W H IH
                 | b p q brs l psi Gl W Hin Hpsi H IH
                 | b p q brs l psi Gl W Hin Hpsi H IH
                 | b p q brs l Gl W Hin H IH ]; intros b' Hle.
  - apply RE_here. exact Hh.
  - eapply RE_act; [ exact HE | apply IH; exact Hle ].
  - apply RE_goal. apply IH. exact Hle.
  - eapply RE_comm_ok; [ exact Hin | exact Hpsi | apply IH; exact Hle ].
  - destruct b' as [ | b'' ]; [ lia | ].
    eapply RE_comm_dev; [ exact Hin | exact Hpsi | apply IH; lia ].
  - eapply RE_env; [ exact Hin | apply IH; exact Hle ].
Qed.

(* ================================================================= *)
(*  For the HAZARD, an environment choice is exactly an agent choice   *)
(*  in which every branch is intended.  This is what lets the regular  *)
(*  layer (EnvRegular.v) represent it with the trivially true guard.   *)
(* ================================================================= *)
Definition total_choice (p q : Role) (brs : list (Lab * Ge)) : Ge :=
  EComm p q (map (fun x => (fst x, (fun _ : World => True), snd x)) brs).

Theorem env_as_total_choice : forall E Haz b p q brs W,
  reachE E Haz b (EEnv p q brs) W <-> reachE E Haz b (total_choice p q brs) W.
Proof.
  intros E Haz b p q brs W. unfold total_choice. split; intro H.
  - inversion H as [ b0 G0 W0 Hh | | | | | b0 p0 q0 brs0 l Gl W0 Hin Hr ]; subst.
    + apply RE_here. exact Hh.
    + eapply RE_comm_ok; [ | exact I | exact Hr ].
      apply in_map_iff. exists (l, Gl). split; [ reflexivity | exact Hin ].
  - inversion H as [ b0 G0 W0 Hh | | | b0 p0 q0 brs0 l psi Gl W0 Hin Hpsi Hr
                   | b0 p0 q0 brs0 l psi Gl W0 Hin Hpsi Hr | ]; subst.
    + apply RE_here. exact Hh.
    + apply in_map_iff in Hin. destruct Hin as [[l0 G0] [Heq Hin0]].
      simpl in Heq. inversion Heq; subst. eapply RE_env; eassumption.
    + apply in_map_iff in Hin. destruct Hin as [[l0 G0] [Heq Hin0]].
      simpl in Heq. inversion Heq; subst. exfalso. apply Hpsi. exact I.
Qed.

Corollary env_as_total_choice_safe : forall E Haz b p q brs W,
  safeE E Haz b (EEnv p q brs) W <-> safeE E Haz b (total_choice p q brs) W.
Proof.
  intros. rewrite !TE_exact. rewrite env_as_total_choice. reflexivity.
Qed.

(* ================================================================= *)
(*  The goal, read DEMONICALLY over the environment.                   *)
(*                                                                     *)
(*  The agent's choices are existential (as for reach_haz: Benign      *)
(*  says the goal is still POSSIBLE for the agent), but an environment *)
(*  choice delivers the goal only if EVERY answer does -- the          *)
(*  implementation's adversarial reading.  An environment choice must  *)
(*  offer an answer; otherwise it would deliver the goal vacuously.    *)
(* ================================================================= *)
Section GoalE.
Variable E : Ctx.
Variable P : World -> Prop.

Inductive greachE : nat -> Ge -> World -> Prop :=
| GE_here : forall b G W,
    P W -> greachE b G W
| GE_act : forall b a p G W W',
    E a W W' -> greachE b G W' -> greachE b (EAct a p G) W
| GE_goal : forall b phi G W,
    greachE b G W -> greachE b (EGoal phi G) W
| GE_comm_ok : forall b p q brs l psi Gl W,
    In (l, psi, Gl) brs -> psi W ->
    greachE b Gl W -> greachE b (EComm p q brs) W
| GE_comm_dev : forall b p q brs l psi Gl W,
    In (l, psi, Gl) brs -> ~ psi W ->
    greachE b Gl W -> greachE (S b) (EComm p q brs) W
| GE_env : forall b p q brs W,
    brs <> [] ->
    (forall l Gl, In (l, Gl) brs -> greachE b Gl W) ->
    greachE b (EEnv p q brs) W.

Lemma greachE_mono_budget :
  forall b G W, greachE b G W -> forall b', b <= b' -> greachE b' G W.
Proof.
  intros b G W H.
  induction H as [ b G W Hp | b a p G W W' HE H IH | b phi G W H IH
                 | b p q brs l psi Gl W Hin Hpsi H IH
                 | b p q brs l psi Gl W Hin Hpsi H IH
                 | b p q brs W Hne Hall IH ]; intros b' Hle.
  - apply GE_here. exact Hp.
  - eapply GE_act; [ exact HE | apply IH; exact Hle ].
  - apply GE_goal. apply IH. exact Hle.
  - eapply GE_comm_ok; [ exact Hin | exact Hpsi | apply IH; exact Hle ].
  - destruct b' as [ | b'' ]; [ lia | ].
    eapply GE_comm_dev; [ exact Hin | exact Hpsi | apply IH; lia ].
  - apply GE_env; [ exact Hne | ]. intros l Gl Hin. apply (IH l Gl Hin b' Hle).
Qed.

(* the demonic reading refines the existential one *)
Theorem greachE_reach : forall b G W, greachE b G W -> reachE E P b G W.
Proof.
  intros b G W H.
  induction H as [ b G W Hp | b a p G W W' HE H IH | b phi G W H IH
                 | b p q brs l psi Gl W Hin Hpsi H IH
                 | b p q brs l psi Gl W Hin Hpsi H IH
                 | b p q brs W Hne Hall IH ].
  - apply RE_here. exact Hp.
  - eapply RE_act; eassumption.
  - apply RE_goal. exact IH.
  - eapply RE_comm_ok; eassumption.
  - eapply RE_comm_dev; eassumption.
  - destruct brs as [ | [l Gl] tl ]; [ exfalso; apply Hne; reflexivity | ].
    eapply RE_env; [ left; reflexivity | ]. apply (IH l Gl). left. reflexivity.
Qed.

End GoalE.

(* ... and strictly: one answer reaches the goal, the other does not. *)
Definition goal_var : Var := 7.
Definition E_goal_ex : Ctx := fun a W W' => a = 8 /\ W' = wupd W goal_var 1.
Definition Phi_ex : World -> Prop := fun W => W goal_var = 1.
Definition G_env_ex : Ge := EEnv 1 0 [ (30, EAct 8 0 EEnd) ; (31, EEnd) ].

Theorem env_goal_is_demonic :
  reachE E_goal_ex Phi_ex 0 G_env_ex W0 /\ ~ greachE E_goal_ex Phi_ex 0 G_env_ex W0.
Proof.
  split.
  - eapply RE_env; [ left; reflexivity | ].
    eapply RE_act; [ split; reflexivity | ].
    apply RE_here. unfold Phi_ex. apply wupd_same.
  - intro H. inversion H as [ b0 G0 W1 Hp | | | | | b0 p0 q0 brs0 W1 Hne Hall ]; subst.
    + discriminate Hp.
    + specialize (Hall 31 EEnd (or_intror (or_introl eq_refl))).
      inversion Hall as [ b0 G0 W1 Hp | | | | | ]; subst. discriminate Hp.
Qed.

(* ================================================================= *)
(*  CONSERVATIVITY.  Severity.v's protocols embed, and every notion    *)
(*  coincides on the image: hazard reachability, the condition, and    *)
(*  goal reachability (the demonic reading has nothing to be demonic   *)
(*  about without an environment choice).                              *)
(* ================================================================= *)
Fixpoint embG (G : Gt) : Ge :=
  match G with
  | GEnd => EEnd
  | GComm p q brs => EComm p q (map (fun b => (fst (fst b), snd (fst b), embG (snd b))) brs)
  | GAct a p G0 => EAct a p (embG G0)
  | GGoal phi G0 => EGoal phi (embG G0)
  end.

Lemma in_embG_brs : forall (brs : list (Lab * (World -> Prop) * Gt)) l psi X,
  In (l, psi, X) (map (fun b => (fst (fst b), snd (fst b), embG (snd b))) brs) ->
  exists Gl, In (l, psi, Gl) brs /\ X = embG Gl.
Proof.
  intros brs l psi X Hin. apply in_map_iff in Hin.
  destruct Hin as [[[l0 psi0] Gl0] [Heq Hin0]]. simpl in Heq. inversion Heq; subst.
  exists Gl0. split; [ exact Hin0 | reflexivity ].
Qed.

Lemma embG_brs_in : forall (brs : list (Lab * (World -> Prop) * Gt)) l psi Gl,
  In (l, psi, Gl) brs ->
  In (l, psi, embG Gl) (map (fun b => (fst (fst b), snd (fst b), embG (snd b))) brs).
Proof.
  intros brs l psi Gl Hin. apply in_map_iff. exists (l, psi, Gl). split; [ reflexivity | exact Hin ].
Qed.

Theorem reach_embedE : forall E P b G W,
  reach_haz E P b G W <-> reachE E P b (embG G) W.
Proof.
  intros E P b G W. split.
  - intro H. induction H as [ b G W Hh | b a p G W W' HE H IH | b phi G W H IH
                            | b p q brs l psi Gl W Hin Hpsi H IH
                            | b p q brs l psi Gl W Hin Hpsi H IH ]; simpl.
    + apply RE_here. exact Hh.
    + eapply RE_act; eassumption.
    + apply RE_goal. exact IH.
    + eapply RE_comm_ok; [ apply embG_brs_in; exact Hin | exact Hpsi | exact IH ].
    + eapply RE_comm_dev; [ apply embG_brs_in; exact Hin | exact Hpsi | exact IH ].
  - intro H. remember (embG G) as X eqn:EX. revert G EX.
    induction H as [ b X W Hh | b a p X W W' HE H IH | b phi X W H IH
                   | b p q brs l psi X W Hin Hpsi H IH
                   | b p q brs l psi X W Hin Hpsi H IH
                   | b p q brs l X W Hin H IH ]; intros G EX.
    + apply RH_here. exact Hh.
    + destruct G; simpl in EX; inversion EX; subst.
      eapply RH_act; [ exact HE | apply IH; reflexivity ].
    + destruct G; simpl in EX; inversion EX; subst.
      apply RH_goal. apply IH. reflexivity.
    + destruct G; simpl in EX; inversion EX; subst.
      destruct (in_embG_brs _ _ _ _ Hin) as [Gl [Hin0 ->]].
      eapply RH_comm_ok; [ exact Hin0 | exact Hpsi | apply IH; reflexivity ].
    + destruct G; simpl in EX; inversion EX; subst.
      destruct (in_embG_brs _ _ _ _ Hin) as [Gl [Hin0 ->]].
      eapply RH_comm_dev; [ exact Hin0 | exact Hpsi | apply IH; reflexivity ].
    + destruct G; simpl in EX; discriminate EX.
Qed.

Theorem safe_embedE : forall E Haz b G W,
  safeT E Haz b G W <-> safeE E Haz b (embG G) W.
Proof.
  intros. rewrite TC_exact, TE_exact, reach_embedE. reflexivity.
Qed.

Theorem greach_embedE : forall E P b G W,
  reach_haz E P b G W <-> greachE E P b (embG G) W.
Proof.
  intros E P b G W. split.
  - intro H. induction H as [ b G W Hh | b a p G W W' HE H IH | b phi G W H IH
                            | b p q brs l psi Gl W Hin Hpsi H IH
                            | b p q brs l psi Gl W Hin Hpsi H IH ]; simpl.
    + apply GE_here. exact Hh.
    + eapply GE_act; eassumption.
    + apply GE_goal. exact IH.
    + eapply GE_comm_ok; [ apply embG_brs_in; exact Hin | exact Hpsi | exact IH ].
    + eapply GE_comm_dev; [ apply embG_brs_in; exact Hin | exact Hpsi | exact IH ].
  - intro H. apply reach_embedE. apply greachE_reach. exact H.
Qed.

(* ================================================================= *)
(*  PRINCIPAL BUDGET, with environment choices.                        *)
(* ================================================================= *)
Section PrincipalE.
Variable E : Ctx.
Variable Haz : World -> Prop.

Definition principalE (k : nat) (G : Ge) (W : World) : Prop :=
  safeE E Haz k G W /\ ~ safeE E Haz (S k) G W.

Theorem principalE_characterises : forall k G W,
  principalE k G W -> forall b, safeE E Haz b G W <-> b <= k.
Proof.
  intros k G W [Hk Hnk] b. split.
  - intro Hb. destruct (Nat.le_gt_cases b k) as [Hle | Hgt]; [ exact Hle | ].
    exfalso. apply Hnk. apply (TE_complete E Haz (Ge_size G)); [ apply le_n | ].
    intro Hr. apply (TE_sound E Haz b G W Hb).
    eapply reachE_mono_budget; [ exact Hr | lia ].
  - intro Hle. eapply toleranceE_downward_closed; eassumption.
Qed.

Theorem principalE_unique : forall k k' G W,
  principalE k G W -> principalE k' G W -> k = k'.
Proof.
  intros k k' G W Hp Hp'.
  assert (k <= k') by (apply (principalE_characterises k' G W Hp'); apply (proj1 Hp)).
  assert (k' <= k) by (apply (principalE_characterises k G W Hp); apply (proj1 Hp')).
  lia.
Qed.

Theorem principalE_exists : forall n G W,
  (forall b, safeE E Haz b G W \/ ~ safeE E Haz b G W) ->
  safeE E Haz 0 G W -> ~ safeE E Haz n G W -> exists k, principalE k G W.
Proof.
  intros n G W Hdec H0. induction n as [ | n IH ]; intro Hn.
  - contradiction.
  - destruct (Hdec n) as [Hy | Hn'].
    + exists n. split; assumption.
    + apply IH. exact Hn'.
Qed.

End PrincipalE.

(* ================================================================= *)
(*  THE TRICHOTOMY, with environment choices: hazard existential over   *)
(*  the environment, goal demonic over it.  Still three consecutive     *)
(*  intervals of budgets, in the order Futile < Benign < Catastrophic.  *)
(* ================================================================= *)
Section SeverityE.
Variable E : Ctx.
Variable Haz : World -> Prop.
Variable Phi : World -> Prop.

Definition CatastrophicE (b : nat) (G : Ge) (W : World) : Prop :=
  reachE E Haz b G W.
Definition FutileE (b : nat) (G : Ge) (W : World) : Prop :=
  ~ reachE E Haz b G W /\ ~ greachE E Phi b G W.
Definition BenignE (b : nat) (G : Ge) (W : World) : Prop :=
  ~ reachE E Haz b G W /\ greachE E Phi b G W.

Theorem severityE_disjoint :
  forall b G W,
    ~ (CatastrophicE b G W /\ FutileE b G W) /\
    ~ (CatastrophicE b G W /\ BenignE b G W) /\
    ~ (FutileE b G W /\ BenignE b G W).
Proof.
  intros b G W. unfold CatastrophicE, FutileE, BenignE.
  repeat split; intros [H1 H2].
  - destruct H2 as [Hn _]. contradiction.
  - destruct H2 as [Hn _]. contradiction.
  - destruct H1 as [_ Hng]. destruct H2 as [_ Hg]. contradiction.
Qed.

Theorem severityE_exhaustive :
  forall b G W,
    (reachE E Haz b G W \/ ~ reachE E Haz b G W) ->
    (greachE E Phi b G W \/ ~ greachE E Phi b G W) ->
    CatastrophicE b G W \/ FutileE b G W \/ BenignE b G W.
Proof.
  intros b G W [Hh | Hh] [Hg | Hg]; unfold CatastrophicE, FutileE, BenignE; tauto.
Qed.

Theorem catastrophicE_upward :
  forall b b' G W, b <= b' -> CatastrophicE b G W -> CatastrophicE b' G W.
Proof. intros b b' G W Hle H. eapply reachE_mono_budget; eassumption. Qed.

Theorem futileE_downward :
  forall b b' G W, b <= b' -> FutileE b' G W -> FutileE b G W.
Proof.
  intros b b' G W Hle [Hh Hg]. split; intro H.
  - apply Hh. eapply reachE_mono_budget; eassumption.
  - apply Hg. eapply greachE_mono_budget; eassumption.
Qed.

Theorem benignE_no_regress :
  forall b b' G W, b <= b' -> BenignE b G W -> ~ FutileE b' G W.
Proof.
  intros b b' G W Hle [_ Hg] [_ Hng]. apply Hng.
  eapply greachE_mono_budget; eassumption.
Qed.

Theorem benignE_step_up :
  forall b b' G W, b <= b' ->
    (reachE E Haz b' G W \/ ~ reachE E Haz b' G W) ->
    BenignE b G W -> BenignE b' G W \/ CatastrophicE b' G W.
Proof.
  intros b b' G W Hle Hdec [Hh Hg].
  destruct Hdec as [Hc | Hc].
  - right. exact Hc.
  - left. split; [ exact Hc | eapply greachE_mono_budget; eassumption ].
Qed.

Theorem benignE_step_down :
  forall b b' G W, b <= b' ->
    (greachE E Phi b G W \/ ~ greachE E Phi b G W) ->
    BenignE b' G W -> BenignE b G W \/ FutileE b G W.
Proof.
  intros b b' G W Hle Hdec [Hh Hg].
  assert (Hnh : ~ reachE E Haz b G W).
  { intro H. apply Hh. eapply reachE_mono_budget; eassumption. }
  destruct Hdec as [Hp | Hp].
  - left. split; assumption.
  - right. split; assumption.
Qed.

Definition sevE_rank (b : nat) (G : Ge) (W : World) (r : nat) : Prop :=
  (r = 0 /\ FutileE b G W) \/ (r = 1 /\ BenignE b G W) \/ (r = 2 /\ CatastrophicE b G W).

Theorem severityE_monotone_in_budget :
  forall b b' G W r r', b <= b' ->
    sevE_rank b G W r -> sevE_rank b' G W r' -> r <= r'.
Proof.
  intros b b' G W r r' Hle Hr Hr'.
  destruct Hr as [[-> Hf] | [[-> Hb] | [-> Hc]]].
  - lia.
  - destruct Hr' as [[-> Hf'] | [[-> _] | [-> _]]]; [ | lia | lia ].
    exfalso. eapply benignE_no_regress; eassumption.
  - destruct Hr' as [[-> Hf'] | [[-> Hb'] | [-> _]]]; [ | | lia ].
    + exfalso. destruct Hf' as [Hnh _]. apply Hnh.
      eapply reachE_mono_budget; eassumption.
    + exfalso. destruct Hb' as [Hnh _]. apply Hnh.
      eapply reachE_mono_budget; eassumption.
Qed.

Theorem toleranceE_degree_is_a_threshold :
  forall k G W,
    ~ CatastrophicE k G W -> CatastrophicE (S k) G W ->
    (forall b, b <= k -> ~ CatastrophicE b G W) /\
    (forall b, S k <= b -> CatastrophicE b G W).
Proof.
  intros k G W Hnk Hk. split.
  - intros b Hb Hc. apply Hnk. eapply catastrophicE_upward; eassumption.
  - intros b Hb. eapply catastrophicE_upward; eassumption.
Qed.

Theorem severityE_classes_are_separated :
  forall k G W,
    ~ CatastrophicE k G W -> CatastrophicE (S k) G W ->
    forall b, b <= k ->
      (reachE E Haz b G W \/ ~ reachE E Haz b G W) ->
      (greachE E Phi b G W \/ ~ greachE E Phi b G W) ->
      (FutileE b G W \/ BenignE b G W).
Proof.
  intros k G W Hnk Hk b Hb Hd1 Hd2.
  destruct (severityE_exhaustive b G W Hd1 Hd2) as [Hc | [Hf | Hbn]].
  - exfalso. apply Hnk. eapply catastrophicE_upward; [ exact Hb | exact Hc ].
  - left. exact Hf.
  - right. exact Hbn.
Qed.

Theorem catastropheE_iff_untypable :
  forall b G W,
    (reachE E Haz b G W \/ ~ reachE E Haz b G W) ->
    (CatastrophicE b G W <-> ~ safeE E Haz b G W).
Proof.
  intros b G W Hdec. split.
  - intros Hr Hs. exact (TE_sound E Haz b G W Hs Hr).
  - intro Hns. destruct Hdec as [Hr | Hr]; [ exact Hr | ].
    exfalso. apply Hns. eapply TE_complete; [ apply Nat.le_refl | exact Hr ].
Qed.

End SeverityE.

(* ================================================================= *)
(*  Least privilege and narrowing survive the extension.               *)
(* ================================================================= *)
Theorem reachE_monotone_in_ctx :
  forall E1 E2 Haz b G W,
    ctx_le E1 E2 -> reachE E1 Haz b G W -> reachE E2 Haz b G W.
Proof.
  intros E1 E2 Haz b G W Hle Hr.
  induction Hr.
  - apply RE_here; assumption.
  - eapply RE_act; [ apply Hle; eassumption | assumption ].
  - apply RE_goal; assumption.
  - eapply RE_comm_ok; eauto.
  - eapply RE_comm_dev; eauto.
  - eapply RE_env; eauto.
Qed.

Corollary toleranceE_antitone_in_ctx :
  forall E1 E2 Haz b G W,
    ctx_le E1 E2 -> safeE E2 Haz b G W -> safeE E1 Haz b G W.
Proof.
  intros E1 E2 Haz b G W Hle Hs. apply TE_exact. intro Hr.
  exact (TE_sound E2 Haz b G W Hs (reachE_monotone_in_ctx E1 E2 Haz b G W Hle Hr)).
Qed.

Theorem repairE_narrow_sound :
  forall E Haz b p q (brs brs' : list (Lab * (World -> Prop) * Ge)) W,
    (forall x, In x brs' -> In x brs) ->
    safeE E Haz b (EComm p q brs) W ->
    safeE E Haz b (EComm p q brs') W.
Proof.
  intros E Haz b p q brs brs' W Hsub Hs.
  inversion Hs as [ | | | b0 p0 q0 brs0 W0 Hnh Hok Hdev | ]; subst.
  apply SE_comm; [ assumption | | ].
  - intros l psi Gl Hin Hpsi. apply (Hok l psi Gl (Hsub _ Hin) Hpsi).
  - intros l psi Gl Hin Hpsi c Hb. apply (Hdev l psi Gl (Hsub _ Hin) Hpsi c Hb).
Qed.

(* ================================================================= *)
(*  THE DEFAULT GUARDS, with environment choices demonic.              *)
(*                                                                     *)
(*  At an agent choice whose branches lead to brs: if the goal is      *)
(*  reachable from some branch against every answer of the             *)
(*  environment (goalE), a branch is intended iff it keeps the goal in *)
(*  that sense; otherwise iff the hazard is AVOIDABLE from it, the     *)
(*  agent's later choices taken freely and the environment's           *)
(*  adversarially (avoidE); and if no branch avoids either, every      *)
(*  branch is intended.  This is the implementation's rule.            *)
(* ================================================================= *)
Section DefaultGuard.
Variable E : Ctx.
Variable Haz : World -> Prop.
Variable Phi : World -> Prop.

(* goal reachable with some number of misselections, demonic environment *)
Definition goalE (G : Ge) (W : World) : Prop := exists b, greachE E Phi b G W.

(* some maximal run fires no hazard: the agent picks, the environment
   answers adversarially *)
Inductive avoidE : Ge -> World -> Prop :=
| AV_end : forall W, ~ Haz W -> avoidE EEnd W
| AV_goal : forall phi G W, ~ Haz W -> avoidE G W -> avoidE (EGoal phi G) W
| AV_blocked : forall a p G W, ~ Haz W -> (forall W', ~ E a W W') -> avoidE (EAct a p G) W
| AV_act : forall a p G W W', ~ Haz W -> E a W W' -> avoidE G W' -> avoidE (EAct a p G) W
| AV_comm : forall p q brs l psi Gl W,
    ~ Haz W -> In (l, psi, Gl) brs -> avoidE Gl W -> avoidE (EComm p q brs) W
| AV_comm_nil : forall p q W, ~ Haz W -> avoidE (EComm p q []) W
| AV_env : forall p q brs W,
    ~ Haz W -> (forall l Gl, In (l, Gl) brs -> avoidE Gl W) -> avoidE (EEnv p q brs) W.

Definition keeps (brs : list (Lab * Ge)) (W : World) : Prop :=
  exists l Gj, In (l, Gj) brs /\ goalE Gj W.
Definition avoids (brs : list (Lab * Ge)) (W : World) : Prop :=
  exists l Gj, In (l, Gj) brs /\ avoidE Gj W.

Definition dguard (brs : list (Lab * Ge)) (Gi : Ge) (W : World) : Prop :=
  (keeps brs W /\ goalE Gi W) \/
  (~ keeps brs W /\ (avoidE Gi W \/ ~ avoids brs W)).

(* the agent choice the default instantiation builds *)
Definition dchoice (p q : Role) (brs : list (Lab * Ge)) : Ge :=
  EComm p q (map (fun x => (fst x, dguard brs (snd x), snd x)) brs).

(* before the point of no return the right choice keeps the goal ... *)
Theorem dguard_keeps_goal : forall brs Gi W,
  keeps brs W -> dguard brs Gi W -> goalE Gi W.
Proof. intros brs Gi W Hk [[_ H] | [Hn _]]; [ exact H | contradiction ]. Qed.

(* ... after it, the right choice limits the harm ... *)
Theorem dguard_limits_harm : forall brs Gi W,
  ~ keeps brs W -> avoids brs W -> dguard brs Gi W -> avoidE Gi W.
Proof.
  intros brs Gi W Hnk Ha [[Hk _] | [_ [H | H]]]; [ contradiction | exact H | contradiction ].
Qed.

(* ... and a choice with no right answer is free: no misselection edge *)
Theorem dchoice_forced_no_misselection : forall brs W,
  (forall l Gj, In (l, Gj) brs -> ~ goalE Gj W /\ ~ avoidE Gj W) ->
  forall l psi Gl, In (l, psi, Gl) (map (fun x => (fst x, dguard brs (snd x), snd x)) brs) ->
  psi W.
Proof.
  intros brs W Hf l psi Gl Hin. apply in_map_iff in Hin.
  destruct Hin as [[l0 G0] [Heq Hin0]]. simpl in Heq. inversion Heq; subst.
  right. split.
  - intros [l1 [Gj [Hj Hg]]]. exact (proj1 (Hf l1 Gj Hj) Hg).
  - right. intros [l1 [Gj [Hj Ha]]]. exact (proj2 (Hf l1 Gj Hj) Ha).
Qed.

Lemma exists_dec_list : forall (P : Lab * Ge -> Prop) (l : list (Lab * Ge)),
  (forall x, In x l -> P x \/ ~ P x) ->
  (exists x, In x l /\ P x) \/ ~ (exists x, In x l /\ P x).
Proof.
  intros P l. induction l as [ | x tl IH ]; intro Hd.
  - right. intros [x [[] _]].
  - destruct (Hd x (or_introl eq_refl)) as [Hx | Hx].
    + left. exists x. split; [ left; reflexivity | exact Hx ].
    + destruct IH as [[y [Hy Hp]] | Hn].
      * intros y Hy. apply Hd. right. exact Hy.
      * left. exists y. split; [ right; exact Hy | exact Hp ].
      * right. intros [y [[Hy | Hy] Hp]]; [ subst; contradiction | apply Hn; eauto ].
Qed.

(* the default guard never turns every branch into a misselection: a
   participant with no budget always has a compliant move *)
Theorem dguard_some_intended : forall brs W,
  brs <> [] ->
  (forall l Gj, In (l, Gj) brs -> goalE Gj W \/ ~ goalE Gj W) ->
  (forall l Gj, In (l, Gj) brs -> avoidE Gj W \/ ~ avoidE Gj W) ->
  exists l Gi, In (l, Gi) brs /\ dguard brs Gi W.
Proof.
  intros brs W Hne Hdg Hda.
  destruct (exists_dec_list (fun x => goalE (snd x) W) brs) as [[[l Gi] [Hin Hg]] | Hng].
  { intros [l Gj] Hin. exact (Hdg l Gj Hin). }
  - exists l, Gi. split; [ exact Hin | left; split; [ exists l, Gi; split; assumption | exact Hg ] ].
  - assert (Hnk : ~ keeps brs W).
    { intros [l [Gj [Hin Hg]]]. apply Hng. exists (l, Gj). split; assumption. }
    destruct (exists_dec_list (fun x => avoidE (snd x) W) brs) as [[[l Gi] [Hin Ha]] | Hna].
    { intros [l Gj] Hin. exact (Hda l Gj Hin). }
    + exists l, Gi. split; [ exact Hin | right; split; [ exact Hnk | left; exact Ha ] ].
    + destruct brs as [ | [l Gi] tl ]; [ exfalso; apply Hne; reflexivity | ].
      exists l, Gi. split; [ left; reflexivity | ]. right. split; [ exact Hnk | right ].
      intros [l1 [Gj [Hj Ha]]]. apply Hna. exists (l1, Gj). split; assumption.
Qed.

End DefaultGuard.

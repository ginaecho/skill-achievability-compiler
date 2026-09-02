(* ================================================================= *)
(*  Bridge.v  --  (A) from protocols to PROGRAMS.                     *)
(*                                                                     *)
(*  Severity.v proves properties of the GLOBAL TYPE's semantics.       *)
(*  This file closes the gap to sessions: a session of PROCESSES that  *)
(*  is typed against a k-tolerant global type, running under the       *)
(*  misselection-instrumented head-move semantics, never reaches a     *)
(*  hazard within budget k.  Budgets also DISTRIBUTE OVER PARTICIPANTS *)
(*  -- the cross-participant composition result.                      *)
(*                                                                     *)
(*  Scope: finite fragment, head-move semantics (the move the global   *)
(*  type's head prescribes), matching the base DirectTyping.v.         *)
(*  Coq 8.18, stdlib only, axiom-free (check_bridge.v).                *)
(* ================================================================= *)

Require Import List Arith Lia Bool.
Import ListNotations.
Require Import Severity.

(* ----------------------------------------------------------------- *)
(*  Processes and sessions (as in the base mechanization).            *)
(* ----------------------------------------------------------------- *)
Inductive Proc : Type :=
| PEnd : Proc
| POut : Role -> list (Lab * Proc) -> Proc
| PIn  : Role -> list (Lab * Proc) -> Proc
| PAct : CapN -> Proc -> Proc.

Definition Sess := Role -> Proc.
Definition supd (s : Sess) (r : Role) (P : Proc) : Sess :=
  fun r' => if Nat.eq_dec r' r then P else s r'.

Section BridgeDev.
Variable E : Ctx.
Variable Haz : World -> Prop.

(* ----------------------------------------------------------------- *)
(*  Direct conformance G |- (s ; W), the base discipline's judgment    *)
(*  lifted to guarded global types.  The guards do NOT constrain the   *)
(*  process: p offers exactly the protocol's label set (I = labels of  *)
(*  sendb), q accepts at least it (I <= J), every branch checks the    *)
(*  SAME residual (plain merge) -- verbatim T-Comm.  Which label p     *)
(*  eventually picks is the agent's business; the guard only says      *)
(*  which pick was intended.                                           *)
(* ----------------------------------------------------------------- *)
Inductive ctypes : Gt -> Sess -> World -> Prop :=
| CT_End : forall s W,
    (forall r, s r = PEnd) ->
    ctypes GEnd s W
| CT_Goal : forall phi G s W,
    phi W ->
    ctypes G s W ->
    ctypes (GGoal phi G) s W
| CT_Act : forall a p G s W P,
    s p = PAct a P ->
    (exists W', E a W W') ->
    (forall W', E a W W' -> ctypes G (supd s p P) W') ->
    ctypes (GAct a p G) s W
| CT_Comm : forall p q brs s W sendb recvb,
    p <> q ->
    s p = POut q sendb ->
    s q = PIn  p recvb ->
    brs <> nil ->
    (forall l psi Gl, In (l, psi, Gl) brs -> exists P, In (l, P) sendb) ->
    (forall l P, In (l, P) sendb -> exists psi Gl, In (l, psi, Gl) brs) ->
    (forall l psi Gl, In (l, psi, Gl) brs -> exists Q, In (l, Q) recvb) ->
    (forall l psi Gl P Q,
        In (l, psi, Gl) brs -> In (l, P) sendb -> In (l, Q) recvb ->
        ctypes Gl (supd (supd s p P) q Q) W) ->
    ctypes (GComm p q brs) s W.

(* ----------------------------------------------------------------- *)
(*  The misselection-instrumented HEAD-MOVE session semantics.        *)
(*  A step carries the acting role and its cost: 0 for compliant      *)
(*  progress, 1 when the sender picked a label whose guard fails.     *)
(*  The runtime gate refuses labels outside sendb, so an out-of-set   *)
(*  attempt is not a step at all (it is a blocked stutter).           *)
(* ----------------------------------------------------------------- *)
Inductive hstep : Gt -> Sess -> World -> Gt -> Sess -> World -> Role -> nat -> Prop :=
| H_Act : forall a p G s W W' P,
    s p = PAct a P -> E a W W' ->
    hstep (GAct a p G) s W G (supd s p P) W' p 0
| H_Goal : forall phi G s W G' s' W' r c,
    hstep G s W G' s' W' r c ->
    hstep (GGoal phi G) s W G' s' W' r c
| H_Comm_ok : forall p q brs s W sendb recvb l psi Gl P Q,
    s p = POut q sendb -> s q = PIn p recvb ->
    In (l, psi, Gl) brs -> In (l, P) sendb -> In (l, Q) recvb ->
    psi W ->
    hstep (GComm p q brs) s W Gl (supd (supd s p P) q Q) W p 0
| H_Comm_dev : forall p q brs s W sendb recvb l psi Gl P Q,
    s p = POut q sendb -> s q = PIn p recvb ->
    In (l, psi, Gl) brs -> In (l, P) sendb -> In (l, Q) recvb ->
    ~ psi W ->
    hstep (GComm p q brs) s W Gl (supd (supd s p P) q Q) W p 1.

(* Runs, recording the trace of (role, cost) events. *)
Inductive hrun : Gt -> Sess -> World -> list (Role * nat) -> Gt -> Sess -> World -> Prop :=
| HR_refl : forall G s W, hrun G s W [] G s W
| HR_step : forall G s W G1 s1 W1 r c tr G2 s2 W2,
    hstep G s W G1 s1 W1 r c ->
    hrun G1 s1 W1 tr G2 s2 W2 ->
    hrun G s W ((r, c) :: tr) G2 s2 W2.

Definition total (tr : list (Role * nat)) : nat :=
  fold_right (fun e acc => snd e + acc) 0 tr.

Definition percost (r : Role) (tr : list (Role * nat)) : nat :=
  fold_right (fun e acc => (if Nat.eq_dec (fst e) r then snd e else 0) + acc) 0 tr.

(* ----------------------------------------------------------------- *)
(*  Auxiliary facts.                                                  *)
(* ----------------------------------------------------------------- *)
Lemma safeT_not_haz : forall b G W, safeT E Haz b G W -> ~ Haz W.
Proof. intros b G W H. inversion H; assumption. Qed.

Lemma supd_same : forall s r P, supd s r P r = P.
Proof. intros. unfold supd. destruct (Nat.eq_dec r r); congruence. Qed.

(* ================================================================= *)
(*  PROGRESS UNDER MISSELECTION.  A session-types reviewer's first      *)
(*  question about a fault model is what it does to communication       *)
(*  safety.  The answer here is: nothing.  A typed session that has     *)
(*  not finished can always take a step, and -- the point -- it can     *)
(*  take one for EVERY label the sender may pick, wrong ones included,  *)
(*  because T-Comm makes the receiver offer at least the protocol's     *)
(*  labels.  A wrong choice is never a communication mismatch, an       *)
(*  unexpected label or a deadlock; its only consequence is the world   *)
(*  it leaves behind -- which is exactly what severity measures.        *)
(*  Guard decidability is a hypothesis, as in severity_exhaustive.      *)
(* ================================================================= *)
Fixpoint finished (G : Gt) : Prop :=
  match G with
  | GEnd => True
  | GGoal _ G0 => finished G0
  | _ => False
  end.

Theorem progress :
  (forall (psi : World -> Prop) (W : World), psi W \/ ~ psi W) ->
  forall G s W, ctypes G s W -> ~ finished G ->
    exists G' s' W' r c, hstep G s W G' s' W' r c.
Proof.
  intros Hdec G s W Ht. induction Ht as [ s W Hend
                                        | phi G s W Hphi Ht IH
                                        | a p G s W P Hsp Hex Hall IH
                                        | p q brs s W sendb recvb Hpq Hsp Hsq Hne Hl1 Hl2 Hl3 Hcont IH ];
    intro Hnf.
  - exfalso. apply Hnf. exact I.
  - destruct (IH Hnf) as [G' [s' [W' [r [c Hst]]]]].
    exists G', s', W', r, c. apply H_Goal. exact Hst.
  - destruct Hex as [W' HE].
    exists G, (supd s p P), W', p, 0. eapply H_Act; eassumption.
  - destruct brs as [ | [[l psi] Gl] tl ]; [ exfalso; apply Hne; reflexivity | ].
    assert (Hin : In (l, psi, Gl) ((l, psi, Gl) :: tl)) by (left; reflexivity).
    destruct (Hl1 _ _ _ Hin) as [P HP]. destruct (Hl3 _ _ _ Hin) as [Q HQ].
    destruct (Hdec psi W) as [Hg | Hg].
    + exists Gl, (supd (supd s p P) q Q), W, p, 0. eapply H_Comm_ok; eassumption.
    + exists Gl, (supd (supd s p P) q Q), W, p, 1. eapply H_Comm_dev; eassumption.
Qed.

(* Every label the sender may pick -- intended or not -- is a step the
   receiver accepts.  This is the precise sense in which misselection is
   not a communication error. *)
Theorem every_label_steps :
  (forall (psi : World -> Prop) (W : World), psi W \/ ~ psi W) ->
  forall p q brs s W, ctypes (GComm p q brs) s W ->
    forall l psi Gl, In (l, psi, Gl) brs ->
      exists s' c, hstep (GComm p q brs) s W Gl s' W p c.
Proof.
  intros Hdec p q brs s W Ht l psi Gl Hin.
  inversion Ht as [ | | | p0 q0 brs0 s0 W0 sendb recvb Hpq Hsp Hsq Hne Hl1 Hl2 Hl3 Hcont ]; subst.
  destruct (Hl1 _ _ _ Hin) as [P HP]. destruct (Hl3 _ _ _ Hin) as [Q HQ].
  destruct (Hdec psi W) as [Hg | Hg].
  - exists (supd (supd s p P) q Q), 0. eapply H_Comm_ok; eassumption.
  - exists (supd (supd s p P) q Q), 1. eapply H_Comm_dev; eassumption.
Qed.

(* ================================================================= *)
(*  THE BRIDGE, one step: typing and k-tolerance are both preserved   *)
(*  by every instrumented head step whose cost fits the budget, and   *)
(*  the budget is debited by exactly that cost.                       *)
(* ================================================================= *)
Theorem bridge_step :
  forall G s W G' s' W' r c b,
    ctypes G s W ->
    safeT E Haz b G W ->
    hstep G s W G' s' W' r c ->
    c <= b ->
    ctypes G' s' W' /\ safeT E Haz (b - c) G' W'.
Proof.
  intros G s W G' s' W' r c b Hct Hsf Hst.
  revert b Hct Hsf.
  induction Hst as [ a p G s W W' P Hsp Heff
                   | phi G s W G' s' W' r c Hst IH
                   | p q brs s W sendb recvb l psi Gl P Q Hsp Hsq Hin HinP HinQ Hpsi
                   | p q brs s W sendb recvb l psi Gl P Q Hsp Hsq Hin HinP HinQ Hpsi ];
    intros b Hct Hsf Hcb.
  - (* action *)
    inversion Hct as [ | | a0 p0 G0 s0 W0 P0 Hsp0 Hex Hall Heq1 Heq2 | ]; subst.
    rewrite Hsp in Hsp0. inversion Hsp0; subst P0.
    inversion Hsf as [ | | b0 a1 p1 G1 W1 Hnh Hsafe Heq | ]; subst.
    rewrite Nat.sub_0_r. split.
    + apply Hall; assumption.
    + apply Hsafe; assumption.
  - (* goal marker: discharged, step continues *)
    inversion Hct as [ | phi0 G0 s0 W0 Hphi Hct' Heq1 Heq2 | | ]; subst.
    inversion Hsf as [ | b0 phi1 G1 W1 Hnh Hsf' Heq | | ]; subst.
    apply IH; assumption.
  - (* intended selection: cost 0 *)
    inversion Hct as [ | | | p0 q0 brs0 s0 W0 sendb0 recvb0 Hpq Hsp0 Hsq0 Hne Hl1 Hl2 Hl3 Hcont Heq1 Heq2 ]; subst.
    rewrite Hsp in Hsp0. inversion Hsp0; subst sendb0.
    rewrite Hsq in Hsq0. inversion Hsq0; subst recvb0.
    inversion Hsf as [ | | | b0 p1 q1 brs1 W1 Hnh Hok Hdev Heq ]; subst.
    rewrite Nat.sub_0_r. split.
    + apply (Hcont l psi Gl P Q); assumption.
    + apply (Hok l psi Gl); assumption.
  - (* misselection: cost 1, budget debited *)
    inversion Hct as [ | | | p0 q0 brs0 s0 W0 sendb0 recvb0 Hpq Hsp0 Hsq0 Hne Hl1 Hl2 Hl3 Hcont Heq1 Heq2 ]; subst.
    rewrite Hsp in Hsp0. inversion Hsp0; subst sendb0.
    rewrite Hsq in Hsq0. inversion Hsq0; subst recvb0.
    inversion Hsf as [ | | | b0 p1 q1 brs1 W1 Hnh Hok Hdev Heq ]; subst.
    destruct b as [ | b' ]; [ lia | ].
    replace (S b' - 1) with b' by lia.
    split.
    + apply (Hcont l psi Gl P Q); assumption.
    + apply (Hdev l psi Gl Hin Hpsi b' eq_refl).
Qed.

(* ================================================================= *)
(*  THE BRIDGE, whole runs: a typed session of a k-tolerant protocol  *)
(*  never reaches a hazard along any run of total cost <= k.  Since   *)
(*  every prefix of a run is a run, this covers every configuration   *)
(*  reachable within budget, not just the final one.                  *)
(* ================================================================= *)
Theorem bridge_run :
  forall G s W tr G' s' W' b,
    ctypes G s W ->
    safeT E Haz b G W ->
    hrun G s W tr G' s' W' ->
    total tr <= b ->
    ~ Haz W' /\ ctypes G' s' W' /\ safeT E Haz (b - total tr) G' W'.
Proof.
  intros G s W tr G' s' W' b Hct Hsf Hrun.
  revert b Hct Hsf.
  induction Hrun as [ G s W
                    | G s W G1 s1 W1 r c tr G2 s2 W2 Hst Hrun IH ];
    intros b Hct Hsf Htot.
  - simpl. rewrite Nat.sub_0_r. repeat split; try assumption.
    eapply safeT_not_haz; eassumption.
  - unfold total in Htot; simpl in Htot. fold (total tr) in Htot.
    assert (Hcb : c <= b) by lia.
    destruct (bridge_step G s W G1 s1 W1 r c b Hct Hsf Hst Hcb) as [Hct1 Hsf1].
    assert (Htot' : total tr <= b - c) by lia.
    destruct (IH (b - c) Hct1 Hsf1 Htot') as [Hnh [Hct2 Hsf2]].
    repeat split; try assumption.
    unfold total; simpl; fold (total tr).
    replace (b - (c + total tr)) with (b - c - total tr) by lia.
    exact Hsf2.
Qed.

(* =================================================================  *)
(*  THE GOAL MARKER, PAID OFF.                                        *)
(*                                                                     *)
(*  CT_Goal is the only rule that reads a marker: safeT, the protocol  *)
(*  steps, the reachability relation and the swap relation all treat   *)
(*  one as transparent.  That asymmetry is the point.  The marker is   *)
(*  an assertion the protocol makes, conformance is what pays for it,  *)
(*  and the theorem below is where the payment is collected: a         *)
(*  conforming run that ARRIVES at a marker has met it.  Without this  *)
(*  the premise would be a tax with no return.                         *)
(* ================================================================= *)
Theorem markers_are_met : forall G s W tr phi G' s' W' b,
  ctypes G s W ->
  safeT E Haz b G W ->
  hrun G s W tr (GGoal phi G') s' W' ->
  total tr <= b ->
  phi W'.
Proof.
  intros G s W tr phi G' s' W' b Hct Hsf Hr Ht.
  destruct (bridge_run G s W tr (GGoal phi G') s' W' b Hct Hsf Hr Ht) as [_ [Hct' _]].
  inversion Hct' as [ | phi0 G0 s0 W0 Hphi _ Heq1 Heq2 | | ]; subst. exact Hphi.
Qed.

(* and that is what ties the marker to the severity classes, which are
   stated over a separate goal predicate: a residual whose head marks Phi
   is not Futile at the world a conforming run reaches it in, because the
   goal is not merely reachable there, it holds. *)
Corollary marker_reached_is_not_futile :
  forall (Phi : World -> Prop) G s W tr G' s' W' b b',
  ctypes G s W ->
  safeT E Haz b G W ->
  hrun G s W tr (GGoal Phi G') s' W' ->
  total tr <= b ->
  ~ Futile E Haz Phi b' (GGoal Phi G') W'.
Proof.
  intros Phi G s W tr G' s' W' b b' Hct Hsf Hr Ht [_ Hnr].
  apply Hnr. apply RH_here.
  eapply markers_are_met; eassumption.
Qed.

(* ================================================================= *)
(*  CROSS-PARTICIPANT COMPOSITION: budgets distribute over roles.     *)
(*                                                                     *)
(*  Give each role r its own allowance k r.  If the allowances of the  *)
(*  roles that act sum to at most b, then a session typed against a   *)
(*  b-tolerant G tolerates every run in which EACH role stays within  *)
(*  its own allowance.  The global budget is thus a contract that can *)
(*  be split among participants and checked per participant.          *)
(* ================================================================= *)

Lemma total_cons : forall r c tr, total ((r, c) :: tr) = c + total tr.
Proof. intros. reflexivity. Qed.

(* summing a role-indexed function over a role list *)
Definition sumR (f : Role -> nat) (R : list Role) : nat :=
  fold_right (fun r acc => f r + acc) 0 R.

Lemma sumR_ext :
  forall f g R, (forall r, In r R -> f r = g r) -> sumR f R = sumR g R.
Proof.
  intros f g R H. induction R as [ | r R IH ]; simpl; [ reflexivity | ].
  rewrite (H r (or_introl eq_refl)). rewrite IH; [ reflexivity | ].
  intros r' Hr'. apply H. right. exact Hr'.
Qed.

Lemma sumR_zero : forall R, sumR (fun _ => 0) R = 0.
Proof. induction R; simpl; [ reflexivity | assumption ]. Qed.

Lemma sumR_split :
  forall f g R, sumR (fun x => f x + g x) R = sumR f R + sumR g R.
Proof. intros. induction R; simpl; [ reflexivity | rewrite IHR; lia ]. Qed.

Lemma sumR_pointwise_le :
  forall f g R, (forall r, In r R -> f r <= g r) -> sumR f R <= sumR g R.
Proof.
  intros f g R H. induction R as [ | r R IH ]; simpl; [ lia | ].
  assert (f r <= g r) by (apply H; left; reflexivity).
  assert (sumR f R <= sumR g R) by (apply IH; intros; apply H; right; assumption).
  lia.
Qed.

(* the indicator of role r, written with the event role FIRST, as percost does *)
Lemma sumR_indicator_absent :
  forall r c R, ~ In r R -> sumR (fun x => if Nat.eq_dec r x then c else 0) R = 0.
Proof.
  intros r c R Hn. induction R as [ | y R IH ]; simpl; [ reflexivity | ].
  destruct (Nat.eq_dec r y) as [Hry | Hry].
  - subst. exfalso. apply Hn. left. reflexivity.
  - apply IH. intro Hc. apply Hn. right. exact Hc.
Qed.

Lemma sumR_indicator :
  forall r c R, NoDup R -> In r R ->
    sumR (fun x => if Nat.eq_dec r x then c else 0) R = c.
Proof.
  intros r c R Hnd Hin. induction R as [ | x R IH ]; simpl; [ contradiction | ].
  inversion Hnd as [ | x0 R0 Hnx Hnd' ]; subst.
  destruct (Nat.eq_dec r x) as [Hrx | Hrx].
  - subst x. rewrite (sumR_indicator_absent r c R Hnx). lia.
  - destruct Hin as [Heq | Hin]; [ congruence | ].
    rewrite (IH Hnd' Hin). lia.
Qed.

(* every role that appears in the trace is in R *)
Definition covers (R : list Role) (tr : list (Role * nat)) : Prop :=
  forall e, In e tr -> In (fst e) R.

Lemma total_eq_sum_percost :
  forall R tr, NoDup R -> covers R tr ->
    total tr = sumR (fun r => percost r tr) R.
Proof.
  intros R tr Hnd. induction tr as [ | [r c] tr IH ]; intros Hcov.
  - simpl. symmetry. apply sumR_zero.
  - rewrite total_cons.
    assert (Hcov' : covers R tr)
      by (unfold covers in *; intros e He; apply Hcov; right; assumption).
    rewrite (IH Hcov').
    assert (HinR : In r R) by (apply (Hcov (r, c)); left; reflexivity).
    rewrite (sumR_ext (fun r0 => percost r0 ((r, c) :: tr))
                      (fun r0 => (if Nat.eq_dec r r0 then c else 0) + percost r0 tr) R)
      by (intros; reflexivity).
    rewrite sumR_split.
    rewrite (sumR_indicator r c R Hnd HinR). reflexivity.
Qed.

Theorem budget_distributes :
  forall G s W tr G' s' W' (k : Role -> nat) (R : list Role) b,
    ctypes G s W ->
    safeT E Haz b G W ->
    hrun G s W tr G' s' W' ->
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
  destruct (bridge_run G s W tr G' s' W' b Hct Hsf Hrun Htot) as [Hnh _].
  exact Hnh.
Qed.

End BridgeDev.

(* ================================================================= *)
(*  NON-VACUITY.  Every guarantee above has the form: if a session     *)
(*  conforms, then something holds.  That is worth nothing unless      *)
(*  conforming sessions exist, and the predecessor of this discipline  *)
(*  was withdrawn for exactly that reason.  So we exhibit them, for    *)
(*  the running example and for its repairs, and check that the        *)
(*  bridge's hypothesis is satisfiable where the paper uses it.        *)
(*                                                                     *)
(*  Roles: planner 0, worker 1.  The planner offers the labels; the    *)
(*  worker accepts them and runs the tools.                            *)
(* ================================================================= *)
Definition sess2 (P0 P1 : Proc) : Sess :=
  fun r => if Nat.eq_dec r 0 then P0 else if Nat.eq_dec r 1 then P1 else PEnd.

Lemma sess2_0 : forall P0 P1, sess2 P0 P1 0 = P0.
Proof. intros. unfold sess2. destruct (Nat.eq_dec 0 0); congruence. Qed.
Lemma sess2_1 : forall P0 P1, sess2 P0 P1 1 = P1.
Proof. intros. unfold sess2. simpl. reflexivity. Qed.
Lemma sess2_other : forall P0 P1 r, r <> 0 -> r <> 1 -> sess2 P0 P1 r = PEnd.
Proof.
  intros. unfold sess2. destruct (Nat.eq_dec r 0); [ contradiction | ].
  destruct (Nat.eq_dec r 1); [ contradiction | reflexivity ].
Qed.

Lemma supd_neq : forall s r P x, x <> r -> supd s r P x = s x.
Proof. intros. unfold supd. destruct (Nat.eq_dec x r); congruence. Qed.

(* the worker's process for the safe path: verify then purchase *)
Definition WSafe : Proc := PAct 1 (PAct 2 PEnd).
Definition WFast : Proc := PAct 2 PEnd.

(* Ggood offers only the safe label; Gbad also offers the fast one *)
Definition MGood : Sess := sess2 (POut 1 [(10, PEnd)]) (PIn 0 [(10, WSafe)]).
Definition MBad  : Sess := sess2 (POut 1 [(10, PEnd); (11, PEnd)])
                                 (PIn 0 [(10, WSafe); (11, WFast)]).

Lemma E0_verify_enabled : forall W, exists W', E0 1 W W'.
Proof. intro W. exists (wupd W verified 1). left. split; reflexivity. Qed.
Lemma E0_purchase_enabled : forall W, exists W', E0 2 W W'.
Proof. intro W. exists (wupd W booked 1). right. split; reflexivity. Qed.

Lemma ctypes_WSafe : forall s W,
  s 1 = WSafe -> (forall W', ctypes E0 GEnd (supd (supd s 1 (PAct 2 PEnd)) 1 PEnd) W') ->
  ctypes E0 SafePath s W.
Proof.
  intros s W Hs Hend. apply CT_Act with (PAct 2 PEnd); [ exact Hs | apply E0_verify_enabled | ].
  intros W' _. apply CT_Act with PEnd; [ apply supd_same | apply E0_purchase_enabled | ].
  intros W'' _. apply Hend.
Qed.

(* the canonical two-role session conforms to the narrowed protocol, so
   Ggood_is_k_tolerant is a statement about a real session *)
Theorem Ggood_inhabited : forall W, ctypes E0 Ggood MGood W.
Proof.
  intro W. apply CT_Comm with [(10, PEnd)] [(10, WSafe)].
  - discriminate.
  - apply sess2_0.
  - apply sess2_1.
  - discriminate.
  - intros l psi Gl Hin. destruct Hin as [Heq | []]. inversion Heq; subst.
    exists PEnd. left. reflexivity.
  - intros l P Hin. destruct Hin as [Heq | []]. inversion Heq; subst.
    exists (fun _ : World => True), SafePath. left. reflexivity.
  - intros l psi Gl Hin. destruct Hin as [Heq | []]. inversion Heq; subst.
    exists WSafe. left. reflexivity.
  - intros l psi Gl P Q Hin HP HQ.
    destruct Hin as [Heq | []]. inversion Heq; subst.
    destruct HP as [HP | []]. inversion HP; subst.
    destruct HQ as [HQ | []]. inversion HQ; subst.
    apply ctypes_WSafe.
    + unfold supd, MGood, sess2, WSafe; repeat destruct (Nat.eq_dec _ _); congruence.
    + intro W'. apply CT_End. intro r.
      unfold supd, MGood, sess2, WSafe; repeat destruct (Nat.eq_dec _ _); congruence.
Qed.

(* The same for the protocol the paper analyses: Gbad offers both labels,
   and a session conforms that is ready for either -- including the wrong
   one.  So Gbad_not_1_tolerant is a statement about a session that exists
   and can actually take the misselected branch. *)
Theorem Gbad_inhabited : forall W, ctypes E0 Gbad MBad W.
Proof.
  intro W. apply CT_Comm with [(10, PEnd); (11, PEnd)] [(10, WSafe); (11, WFast)].
  - discriminate.
  - apply sess2_0.
  - apply sess2_1.
  - discriminate.
  - intros l psi Gl Hin. destruct Hin as [Heq | [Heq | []]]; inversion Heq; subst.
    + exists PEnd. left. reflexivity.
    + exists PEnd. right. left. reflexivity.
  - intros l P Hin. destruct Hin as [Heq | [Heq | []]]; inversion Heq; subst.
    + exists (fun _ : World => True), SafePath. left. reflexivity.
    + exists (fun _ : World => False), FastPath. right. left. reflexivity.
  - intros l psi Gl Hin. destruct Hin as [Heq | [Heq | []]]; inversion Heq; subst.
    + exists WSafe. left. reflexivity.
    + exists WFast. right. left. reflexivity.
  - intros l psi Gl P Q Hin HP HQ.
    destruct Hin as [Heq | [Heq | []]]; inversion Heq; subst.
    + destruct HP as [HP | [HP | []]]; inversion HP; subst;
        destruct HQ as [HQ | [HQ | []]]; inversion HQ; subst.
      apply ctypes_WSafe.
      * unfold supd, MBad, sess2, WFast, WSafe; repeat destruct (Nat.eq_dec _ _); try congruence.
      * intro W'. apply CT_End. intro r.
        unfold supd, MBad, sess2, WFast, WSafe; repeat destruct (Nat.eq_dec _ _); try congruence.
    + destruct HP as [HP | [HP | []]]; inversion HP; subst;
        destruct HQ as [HQ | [HQ | []]]; inversion HQ; subst.
      apply CT_Act with PEnd.
      * unfold supd, MBad, sess2, WFast, WSafe; repeat destruct (Nat.eq_dec _ _); congruence.
      * apply E0_purchase_enabled.
      * intros W' _. apply CT_End. intro r.
        unfold supd, MBad, sess2, WFast, WSafe; repeat destruct (Nat.eq_dec _ _); congruence.
Qed.

(* Consequence: the bridge is not vacuous on the paper's instance.  A real
   session, conforming to a 0-tolerant protocol, is hazard-free on every
   run that contains no misselection -- and Gbad_not_1_tolerant says the
   budget cannot be raised. *)
Corollary Gbad_bridge_nonvacuous : forall W tr G' s' W',
  safeT E0 Haz0 0 Gbad W ->
  hrun E0 Gbad MBad W tr G' s' W' -> total tr <= 0 -> ~ Haz0 W'.
Proof.
  intros W tr G' s' W' Hs Hr Ht.
  destruct (bridge_run E0 Haz0 Gbad MBad W tr G' s' W' 0 (Gbad_inhabited W) Hs Hr Ht) as [H _].
  exact H.
Qed.

(* ----------------------------------------------------------------- *)
(*  A marked instance, so the premise of CT_Goal is not vacuous        *)
(*  either.  Ggoal is the narrowed booking protocol with the goal      *)
(*  marked where the safe path establishes it: booked and verified.    *)
(* ----------------------------------------------------------------- *)
Definition Phi0 : World -> Prop := fun W => W booked = 1 /\ W verified = 1.

Definition SafeGoal : Gt := GAct 1 1 (GAct 2 1 (GGoal Phi0 GEnd)).

Definition Ggoal : Gt := GComm 0 1 [(10, (fun _ : World => True), SafeGoal)].

Lemma SafeGoal_safe : forall k W, ~ Haz0 W -> safeT E0 Haz0 k SafeGoal W.
Proof.
  intros k W Hnh. apply ST_Act; [ exact Hnh | ]. intros W1 H1.
  destruct H1 as [[_ ->] | [Hc _]]; [ | discriminate Hc ].
  assert (Hnh1 : ~ Haz0 (wupd W verified 1)).
  { intros [_ Hv]. rewrite wupd_same in Hv. discriminate. }
  apply ST_Act; [ exact Hnh1 | ]. intros W2 H2.
  destruct H2 as [[Hc _] | [_ ->]]; [ discriminate Hc | ].
  assert (Hnh2 : ~ Haz0 (wupd (wupd W verified 1) booked 1)).
  { intros [_ Hv]. rewrite wupd_other in Hv; [ | unfold verified, booked; lia ].
    rewrite wupd_same in Hv. discriminate. }
  apply ST_Goal; [ exact Hnh2 | ]. apply ST_End. exact Hnh2.
Qed.

Theorem Ggoal_is_k_tolerant : forall k, safeT E0 Haz0 k Ggoal W0.
Proof.
  intro k. apply ST_Comm; [ exact notHaz_W0 | | ].
  - intros l psi Gl Hin _. destruct Hin as [Heq | []]. inversion Heq; subst.
    apply SafeGoal_safe. exact notHaz_W0.
  - intros l psi Gl Hin _ c _. destruct Hin as [Heq | []]. inversion Heq; subst.
    apply SafeGoal_safe. exact notHaz_W0.
Qed.

Theorem Ggoal_inhabited : forall W, ctypes E0 Ggoal MGood W.
Proof.
  intro W. apply CT_Comm with [(10, PEnd)] [(10, WSafe)].
  - discriminate.
  - apply sess2_0.
  - apply sess2_1.
  - discriminate.
  - intros l psi Gl Hin. destruct Hin as [Heq | []]. inversion Heq; subst.
    exists PEnd. left. reflexivity.
  - intros l P Hin. destruct Hin as [Heq | []]. inversion Heq; subst.
    exists (fun _ : World => True), SafeGoal. left. reflexivity.
  - intros l psi Gl Hin. destruct Hin as [Heq | []]. inversion Heq; subst.
    exists WSafe. left. reflexivity.
  - intros l psi Gl P Q Hin HP HQ.
    destruct Hin as [Heq | []]. inversion Heq; subst.
    destruct HP as [HP | []]. inversion HP; subst.
    destruct HQ as [HQ | []]. inversion HQ; subst.
    apply CT_Act with (PAct 2 PEnd).
    + unfold supd, MGood, sess2, WSafe; repeat destruct (Nat.eq_dec _ _); congruence.
    + apply E0_verify_enabled.
    + intros W1 H1. destruct H1 as [[_ ->] | [Hc _]]; [ | discriminate Hc ].
      apply CT_Act with PEnd.
      * apply supd_same.
      * apply E0_purchase_enabled.
      * intros W2 H2. destruct H2 as [[Hc _] | [_ ->]]; [ discriminate Hc | ].
        apply CT_Goal.
        -- unfold Phi0. split.
           ++ apply wupd_same.
           ++ rewrite wupd_other; [ apply wupd_same | unfold verified, booked; lia ].
        -- apply CT_End. intro r.
           unfold supd, MGood, sess2, WSafe; repeat destruct (Nat.eq_dec _ _); congruence.
Qed.

(* so the marker theorem is about a session that exists: every conforming
   run of MGood that reaches the marker has actually achieved the goal *)
Corollary Ggoal_marker_met : forall k tr G' s' W',
  hrun E0 Ggoal MGood W0 tr (GGoal Phi0 G') s' W' -> total tr <= k -> Phi0 W'.
Proof.
  intros k tr G' s' W' Hr Ht.
  eapply (markers_are_met E0 Haz0 Ggoal MGood W0 tr Phi0 G' s' W' k);
    [ apply Ggoal_inhabited | apply Ggoal_is_k_tolerant | exact Hr | exact Ht ].
Qed.


(* ================================================================= *)
(*  INHABITATION, IN GENERAL.                                          *)
(*                                                                     *)
(*  The witnesses above are individual protocols, which answers the     *)
(*  vacuity question only for them.  For two-role protocols there is a  *)
(*  construction: read the global type as a pair of processes, one per  *)
(*  role, and it conforms -- over any runtime whose capabilities are    *)
(*  enabled everywhere, which is the shape of every capability model    *)
(*  in this paper.  Bystanders are what makes the general case a        *)
(*  projection problem (a role uninvolved in a choice needs the same    *)
(*  continuation in every branch); with two roles there are none.       *)
(*  Goal markers are excluded, and that exclusion is exactly            *)
(*  markers_are_met: a marker is an assertion about the world, so no    *)
(*  construction uniform in the world can discharge it.                 *)
(* ================================================================= *)
Fixpoint canon (r : Role) (G : Gt) : Proc :=
  match G with
  | GEnd => PEnd
  | GGoal _ G0 => canon r G0
  | GAct a p G0 => if Nat.eq_dec r p then PAct a (canon r G0) else canon r G0
  | GComm p q brs =>
      if Nat.eq_dec r p
      then POut q (map (fun b => (fst (fst b), canon r (snd b))) brs)
      else if Nat.eq_dec r q
           then PIn p (map (fun b => (fst (fst b), canon r (snd b))) brs)
           else PEnd
  end.

Definition sess_of (G : Gt) : Sess := fun r => canon r G.

Definition labels (brs : list (Lab * (World -> Prop) * Gt)) : list Lab :=
  map (fun b => fst (fst b)) brs.

Fixpoint two_role (G : Gt) : Prop :=
  match G with
  | GEnd => True
  | GGoal _ _ => False
  | GAct _ p G0 => (p = 0 \/ p = 1) /\ two_role G0
  | GComm p q brs =>
      p = 0 /\ q = 1 /\ brs <> nil /\ NoDup (labels brs) /\
      fold_right (fun b acc => two_role (snd b) /\ acc) True brs
  end.

Lemma two_role_br : forall (brs : list (Lab * (World -> Prop) * Gt)) l psi Gl,
  fold_right (fun b acc => two_role (snd b) /\ acc) True brs ->
  In (l, psi, Gl) brs -> two_role Gl.
Proof.
  induction brs as [ | b tl IH ]; simpl; intros l psi Gl Hf Hin; [ contradiction | ].
  destruct Hf as [Hb Htl]. destruct Hin as [Heq | Hin].
  - subst b. simpl in Hb. exact Hb.
  - eapply IH; eauto.
Qed.

(* distinct labels: a label names one branch *)
Lemma label_determines : forall (brs : list (Lab * (World -> Prop) * Gt)) l psi Gl psi' Gl',
  NoDup (labels brs) -> In (l, psi, Gl) brs -> In (l, psi', Gl') brs ->
  psi = psi' /\ Gl = Gl'.
Proof.
  induction brs as [ | [[l0 psi0] G0] tl IH ]; simpl; intros l psi Gl psi' Gl' Hnd H1 H2.
  - contradiction.
  - unfold labels in Hnd. simpl in Hnd. inversion Hnd as [ | x xs Hni Hnd' ]; subst.
    destruct H1 as [E1 | H1]; destruct H2 as [E2 | H2].
    + inversion E1; inversion E2; subst. split; reflexivity.
    + inversion E1; subst. exfalso. apply Hni. unfold labels.
      apply in_map_iff. exists (l, psi', Gl'). split; [ reflexivity | exact H2 ].
    + inversion E2; subst. exfalso. apply Hni. unfold labels.
      apply in_map_iff. exists (l, psi, Gl). split; [ reflexivity | exact H1 ].
    + eapply IH; eauto.
Qed.

(* every role beyond the two is idle throughout *)
Lemma canon_other : forall n G r,
  Gt_size G <= n -> two_role G -> r <> 0 -> r <> 1 -> canon r G = PEnd.
Proof.
  induction n as [ | n IH ]; intros G r Hle Htr H0 H1.
  - destruct G; simpl in Hle; lia.
  - destruct G as [ | p q brs | a p G0 | phi G0 ]; simpl.
    + reflexivity.
    + simpl in Htr. destruct Htr as [-> [-> _]].
      destruct (Nat.eq_dec r 0); [ contradiction | ].
      destruct (Nat.eq_dec r 1); [ contradiction | reflexivity ].
    + simpl in Htr. destruct Htr as [Hp Hg].
      destruct (Nat.eq_dec r p) as [-> | Hrp]; [ destruct Hp; contradiction | ].
      apply (IH G0 r); [ simpl in Hle; lia | exact Hg | exact H0 | exact H1 ].
    + simpl in Htr. contradiction.
Qed.

(* conformance only ever reads the session at particular roles *)
Lemma ctypes_ext : forall Ec G s s' W,
  (forall r, s r = s' r) -> ctypes Ec G s W -> ctypes Ec G s' W.
Proof.
  intros Ec G s s' W Hs Ht. revert s' Hs.
  induction Ht as
    [ s0 W0 Hend
    | phi G0 s0 W0 Hphi Ht IHt
    | a p G0 s0 W0 P Hsp Hex Hall IHall
    | p q brs s0 W0 sendb recvb Hpq Hsp Hsq Hne Hl1 Hl2 Hl3 Hcont IHcont ];
    intros s' Hs.
  - apply CT_End. intro r. rewrite <- Hs. apply Hend.
  - apply CT_Goal; [ exact Hphi | ]. apply IHt. exact Hs.
  - apply CT_Act with P; [ rewrite <- Hs; exact Hsp | exact Hex | ].
    intros W' HE. apply (IHall W' HE).
    intro r. unfold supd. destruct (Nat.eq_dec r p); [ reflexivity | apply Hs ].
  - apply CT_Comm with sendb recvb; try assumption;
      [ rewrite <- Hs; exact Hsp | rewrite <- Hs; exact Hsq | ].
    intros l psi Gl P Q Hin HP HQ. apply (IHcont l psi Gl P Q Hin HP HQ).
    intro r. unfold supd. destruct (Nat.eq_dec r q); [ reflexivity | ].
    destruct (Nat.eq_dec r p); [ reflexivity | apply Hs ].
Qed.

Lemma in_canon_br : forall (brs : list (Lab * (World -> Prop) * Gt)) r l psi Gl,
  In (l, psi, Gl) brs ->
  In (l, canon r Gl) (map (fun b => (fst (fst b), canon r (snd b))) brs).
Proof.
  intros brs r l psi Gl Hin. apply in_map_iff. exists (l, psi, Gl).
  split; [ reflexivity | exact Hin ].
Qed.

Lemma in_canon_br_inv : forall (brs : list (Lab * (World -> Prop) * Gt)) r l P,
  In (l, P) (map (fun b => (fst (fst b), canon r (snd b))) brs) ->
  exists psi Gl, In (l, psi, Gl) brs /\ P = canon r Gl.
Proof.
  intros brs r l P Hin. apply in_map_iff in Hin.
  destruct Hin as [[[l0 psi0] Gl0] [Heq Hin0]]. simpl in Heq. inversion Heq; subst.
  exists psi0, Gl0. split; [ exact Hin0 | reflexivity ].
Qed.

(* THE CONSTRUCTION CONFORMS.  Its only hypothesis on the runtime is the
   one every capability model in this paper satisfies: a tool call always
   has an answer. *)
Theorem canon_conforms : forall Ec,
  (forall a W, exists W', Ec a W W') ->
  forall n G W, Gt_size G <= n -> two_role G -> ctypes Ec G (sess_of G) W.
Proof.
  intros Ec Htotal n. induction n as [ | n IH ]; intros G W Hle Htr.
  - destruct G; simpl in Hle; lia.
  - destruct G as [ | p q brs | a p G0 | phi G0 ].
    + apply CT_End. intro r. reflexivity.
    + simpl in Htr. destruct Htr as [-> [-> [Hne [Hnd Hbrs]]]].
      apply CT_Comm with (map (fun b => (fst (fst b), canon 0 (snd b))) brs)
                         (map (fun b => (fst (fst b), canon 1 (snd b))) brs).
      * discriminate.
      * unfold sess_of. reflexivity.
      * unfold sess_of. reflexivity.
      * exact Hne.
      * intros l psi Gl Hin. exists (canon 0 Gl). eapply in_canon_br; eauto.
      * intros l P Hin. destruct (in_canon_br_inv brs 0 l P Hin) as [psi [Gl [Hin0 _]]].
        exists psi, Gl. exact Hin0.
      * intros l psi Gl Hin. exists (canon 1 Gl). eapply in_canon_br; eauto.
      * intros l psi Gl P Q Hin HP HQ.
        destruct (in_canon_br_inv brs 0 l P HP) as [psi0 [Gl0 [Hin0 ->]]].
        destruct (in_canon_br_inv brs 1 l Q HQ) as [psi1 [Gl1 [Hin1 ->]]].
        destruct (label_determines brs l psi Gl psi0 Gl0 Hnd Hin Hin0) as [_ EG0].
        destruct (label_determines brs l psi Gl psi1 Gl1 Hnd Hin Hin1) as [_ EG1].
        subst Gl0 Gl1.
        assert (HGl : two_role Gl) by (eapply two_role_br; eauto).
        assert (Hsz : Gt_size Gl <= n)
          by (pose proof (in_brs_size brs l psi Gl Hin); simpl in Hle; lia).
        eapply ctypes_ext with (s := sess_of Gl); [ | apply IH; assumption ].
        intro r. unfold supd, sess_of.
        destruct (Nat.eq_dec r 1) as [-> | Hr1]; [ reflexivity | ].
        destruct (Nat.eq_dec r 0) as [-> | Hr0]; [ reflexivity | ].
        simpl. destruct (Nat.eq_dec r 0); [ contradiction | ].
        destruct (Nat.eq_dec r 1); [ contradiction | ].
        apply (canon_other (Gt_size Gl) Gl r (le_n _) HGl Hr0 Hr1).
    + simpl in Htr. destruct Htr as [Hp Hg].
      apply CT_Act with (canon p G0).
      * unfold sess_of. simpl. destruct (Nat.eq_dec p p); congruence.
      * apply Htotal.
      * intros W' HE. eapply ctypes_ext with (s := sess_of G0);
          [ | apply IH; [ simpl in Hle; lia | exact Hg ] ].
        intro r. unfold supd, sess_of. destruct (Nat.eq_dec r p) as [-> | Hrp].
        -- reflexivity.
        -- simpl. destruct (Nat.eq_dec r p); [ contradiction | reflexivity ].
    + simpl in Htr. contradiction.
Qed.

(* Consequence: on such a runtime the bridge is never a statement about an
   empty class.  Every two-role protocol that satisfies the condition has a
   session that conforms to it, and that session is hazard-free within
   budget. *)
Corollary two_role_bridge_nonvacuous : forall Ec Hz G W b tr G' s' W',
  (forall a W0, exists W1, Ec a W0 W1) ->
  two_role G ->
  safeT Ec Hz b G W ->
  hrun Ec G (sess_of G) W tr G' s' W' -> total tr <= b -> ~ Hz W'.
Proof.
  intros Ec Hz G W b tr G' s' W' Htotal Htr Hs Hr Hle.
  destruct (bridge_run Ec Hz G (sess_of G) W tr G' s' W' b
              (canon_conforms Ec Htotal (Gt_size G) G W (le_n _) Htr) Hs Hr Hle) as [H _].
  exact H.
Qed.

(* ----------------------------------------------------------------- *)
(*  NARROWING IS ASYMMETRIC, AND THAT IS THE RESULT.                   *)
(*                                                                     *)
(*  The condition is closed under removing branches                    *)
(*  (repair_narrow_sound): a protocol that offers fewer                *)
(*  choices is no less safe.  Conformance is NOT, because T-Comm asks   *)
(*  the sender to offer EXACTLY the protocol's label set.  So narrowing *)
(*  is not a subtyping-style covariance of internal choice here: it is  *)
(*  a rewrite of the contract, and the session has to be narrowed with  *)
(*  it.  That is the honest reading of what the gate does -- it refuses *)
(*  the removed label at run time, and a process that still offers it   *)
(*  is no longer a description of what can happen.                      *)
(* ----------------------------------------------------------------- *)
Lemma ctypes_comm_labels : forall Ec p q brs s W sendb l P,
  ctypes Ec (GComm p q brs) s W -> s p = POut q sendb -> In (l, P) sendb ->
  exists psi Gl, In (l, psi, Gl) brs.
Proof.
  intros Ec p q brs s W sendb l P Hct Hsp Hin.
  inversion Hct as [ | | | p0 q0 brs0 s0 W0 sendb0 recvb0
                       Hpq Hsp0 Hsq Hne Hl1 Hl2 Hl3 Hcont ]; subst.
  rewrite Hsp in Hsp0. inversion Hsp0; subst sendb0.
  eapply Hl2. exact Hin.
Qed.

Theorem narrowing_breaks_conformance : forall W, ~ ctypes E0 Ggood MBad W.
Proof.
  intros W Hct.
  assert (Hsp : MBad 0 = POut 1 [(10, PEnd); (11, PEnd)]) by apply sess2_0.
  destruct (ctypes_comm_labels E0 0 1 _ MBad W _ 11 PEnd Hct Hsp
              (or_intror (or_introl eq_refl))) as [psi [Gl Hin]].
  destruct Hin as [Heq | []]. inversion Heq.
Qed.

(* the four facts together: narrowing the protocol preserves the
   condition, breaks conformance, and narrowing the session with it
   restores conformance *)
Theorem narrowing_asymmetry : forall W,
  (forall b, safeT E0 Haz0 b Gbad W -> safeT E0 Haz0 b Ggood W) /\
  ctypes E0 Gbad MBad W /\
  ~ ctypes E0 Ggood MBad W /\
  ctypes E0 Ggood MGood W.
Proof.
  intro W. repeat split.
  - intros b Hs. unfold Ggood, Gbad in *.
    eapply repair_narrow_sound; [ | exact Hs ].
    intros x Hx. destruct Hx as [Heq | []]. left. exact Heq.
  - apply Gbad_inhabited.
  - apply narrowing_breaks_conformance.
  - apply Ggood_inhabited.
Qed.

(* ----------------------------------------------------------------- *)
(*  BENIGN IS ANGELIC; ROBUST IS NOT.                                  *)
(*                                                                     *)
(*  \Ben{} says the goal is still REACHABLE -- possible over the future *)
(*  choices of exactly the participant the discipline says you cannot   *)
(*  rely on.  Robust says it is still GUARANTEED.  Gloss separates      *)
(*  them: its safe branch reaches the goal, its misselectable branch    *)
(*  harmlessly does nothing, so one affordable mistake costs the goal   *)
(*  without costing anything else.                                      *)
(* ----------------------------------------------------------------- *)
Definition Gloss : Gt :=
  GComm 0 1 [ (10, (fun _ : World => True), SafePath) ;
              (11, (fun _ : World => False), GEnd) ].

Lemma Gloss_safe : safeT E0 Haz0 1 Gloss W0.
Proof.
  apply ST_Comm; [ exact notHaz_W0 | | ].
  - intros l psi Gl Hin Hpsi. destruct Hin as [Heq | [Heq | []]]; inversion Heq; subst.
    + apply safe_path_typed.
    + exfalso. exact Hpsi.
  - intros l psi Gl Hin Hnpsi c Hb. destruct Hin as [Heq | [Heq | []]]; inversion Heq; subst.
    + exfalso. apply Hnpsi. exact I.
    + apply ST_End. exact notHaz_W0.
Qed.

Lemma SafePath_reaches_Phi0 : reach_haz E0 Phi0 1 SafePath W0.
Proof.
  eapply RH_act; [ left; split; reflexivity | ].
  eapply RH_act; [ right; split; reflexivity | ].
  apply RH_here. unfold Phi0. split.
  - apply wupd_same.
  - rewrite wupd_other; [ apply wupd_same | unfold verified, booked; lia ].
Qed.

Theorem benign_is_not_robust :
  Benign E0 Haz0 Phi0 1 Gloss W0 /\ ~ Robust E0 Haz0 Phi0 1 Gloss W0.
Proof.
  assert (Hnh : ~ reach_haz E0 Haz0 1 Gloss W0) by (apply TC_sound; apply Gloss_safe).
  assert (HnP : ~ Phi0 W0) by (intros [Hb _]; unfold W0 in Hb; discriminate).
  split.
  - split; [ exact Hnh | ].
    eapply RH_comm_ok; [ left; reflexivity | exact I | apply SafePath_reaches_Phi0 ].
  - intros [_ Ha]. unfold Assured in Ha.
    inversion Ha as [ b G W Hp | | | b p q brs W l0 psi0 Gl0 Hin Hpsi Hok Hdev ]; subst.
    + exact (HnP Hp).
    + specialize (Hdev 11 (fun _ : World => False) GEnd 0
                       (or_intror (or_introl eq_refl)) (fun H => H) eq_refl).
      inversion Hdev as [ b' G' W' Hp | | | ]; subst. exact (HnP Hp).
Qed.

(* ----------------------------------------------------------------- *)
(*  EVERY CONFIGURATION, not only the endpoint.                        *)
(*                                                                     *)
(*  bridge_run concludes about the world a run ends in.  The claim the *)
(*  paper makes is stronger -- no configuration reachable within       *)
(*  budget is hazardous -- and it needs runs to be prefix-closed.      *)
(*  They are.                                                          *)
(* ----------------------------------------------------------------- *)
Lemma hrun_split : forall Ec G s W tr1 tr2 G' s' W',
  hrun Ec G s W (tr1 ++ tr2) G' s' W' ->
  exists G1 s1 W1, hrun Ec G s W tr1 G1 s1 W1 /\ hrun Ec G1 s1 W1 tr2 G' s' W'.
Proof.
  intros Ec G s W tr1. revert G s W.
  induction tr1 as [ | [r c] tl IH ]; intros G s W tr2 G' s' W' Hr; simpl in Hr.
  - exists G, s, W. split; [ apply HR_refl | exact Hr ].
  - inversion Hr as [ | G0 s0 W0 G1 s1 W1 r0 c0 tr0 G2 s2 W2 Hst Hrest ]; subst.
    destruct (IH G1 s1 W1 tr2 G' s' W' Hrest) as [Gm [sm [Wm [Ha Hb]]]].
    exists Gm, sm, Wm. split; [ eapply HR_step; eassumption | exact Hb ].
Qed.

Lemma total_app : forall tr1 tr2, total (tr1 ++ tr2) = total tr1 + total tr2.
Proof.
  induction tr1 as [ | [r c] tl IH ]; intro tr2; simpl; [ reflexivity | ].
  unfold total in *; simpl. rewrite IH. lia.
Qed.

Theorem bridge_every_configuration :
  forall Ec Hz G s W b tr1 tr2 G' s' W',
    ctypes Ec G s W ->
    safeT Ec Hz b G W ->
    hrun Ec G s W (tr1 ++ tr2) G' s' W' ->
    total (tr1 ++ tr2) <= b ->
    exists G1 s1 W1,
      hrun Ec G s W tr1 G1 s1 W1 /\ ~ Hz W1 /\
      ctypes Ec G1 s1 W1 /\ safeT Ec Hz (b - total tr1) G1 W1.
Proof.
  intros Ec Hz G s W b tr1 tr2 G' s' W' Hct Hsf Hr Ht.
  destruct (hrun_split Ec G s W tr1 tr2 G' s' W' Hr) as [G1 [s1 [W1 [Ha Hb]]]].
  rewrite total_app in Ht.
  destruct (bridge_run Ec Hz G s W tr1 G1 s1 W1 b Hct Hsf Ha ltac:(lia))
    as [Hnh [Hct1 Hsf1]].
  exists G1, s1, W1. repeat split; assumption.
Qed.

(* and the misselected branch of the running example is a step a real
   session takes, not a hypothetical one *)
Theorem MBad_takes_the_wrong_branch :
  (forall (psi : World -> Prop) (W : World), psi W \/ ~ psi W) ->
  forall W, exists s' c,
    hstep E0 Gbad MBad W FastPath s' W 0 c.
Proof.
  intros Hdec W.
  apply (every_label_steps E0 Hdec 0 1
           [(10, (fun _ : World => True), SafePath);
            (11, (fun _ : World => False), FastPath)] MBad W
           (Gbad_inhabited W) 11 (fun _ : World => False) FastPath).
  right. left. reflexivity.
Qed.

(* ----------------------------------------------------------------- *)
(*  NON-VACUITY OF THIS ROUND'S ADDITIONS.                             *)
(*                                                                     *)
(*  Robust and the cone-of-influence theorem both carry hypotheses      *)
(*  that could be satisfiable nowhere, which would make robust_benign   *)
(*  and interface_projection true and empty.  They are not.             *)
(* ----------------------------------------------------------------- *)

(* Robust is inhabited: the narrowed booking protocol assures its goal at
   every budget, because it offers no branch a misselection can take *)
Lemma SafePath_assures_Phi0 : forall b, assuredP E0 Phi0 b SafePath W0.
Proof.
  intro b. apply AS_act; [ apply E0_verify_enabled | ]. intros W1 H1.
  destruct H1 as [[_ ->] | [Hc _]]; [ | discriminate Hc ].
  apply AS_act; [ apply E0_purchase_enabled | ]. intros W2 H2.
  destruct H2 as [[Hc _] | [_ ->]]; [ discriminate Hc | ].
  apply AS_here. unfold Phi0. split.
  - apply wupd_same.
  - rewrite wupd_other; [ apply wupd_same | unfold verified, booked; lia ].
Qed.

Theorem Ggood_is_robust : forall b, Robust E0 Haz0 Phi0 b Ggood W0.
Proof.
  intro b. split.
  - apply TC_sound. apply Ggood_is_k_tolerant.
  - unfold Assured, Ggood.
    apply AS_comm with (l0 := 10) (psi0 := fun _ : World => True)
                       (Gl0 := SafePath); [ left; reflexivity | exact I | | ].
    + intros l psi Gl Hin _. destruct Hin as [Heq | []]. inversion Heq; subst.
      apply SafePath_assures_Phi0.
    + intros l psi Gl c Hin Hnp _. destruct Hin as [Heq | []]. inversion Heq; subst.
      exfalso. apply Hnp. exact I.
Qed.

(* The cone of influence is inhabited by a NON-degenerate instance: the
   booking runtime reads only two of the world's variables, so worlds
   differing anywhere else are interchangeable for it. *)
Definition V0 : Var -> Prop := fun x => x = verified \/ x = booked.

Lemma V0_haz_cone : forall W1 W2, agree V0 W1 W2 -> (Haz0 W1 <-> Haz0 W2).
Proof.
  intros W1 W2 Hag. unfold Haz0.
  rewrite (Hag booked (or_intror eq_refl)). rewrite (Hag verified (or_introl eq_refl)).
  reflexivity.
Qed.

Lemma V0_cap_cone : forall a W1 W2 W1',
  agree V0 W1 W2 -> E0 a W1 W1' -> exists W2', E0 a W2 W2' /\ agree V0 W1' W2'.
Proof.
  intros a W1 W2 W1' Hag HE.
  destruct HE as [[-> ->] | [-> ->]].
  - exists (wupd W2 verified 1). split; [ left; split; reflexivity | ].
    intros x Hx. destruct (Nat.eq_dec x verified) as [-> | Hxv].
    + rewrite !wupd_same. reflexivity.
    + rewrite !wupd_other by exact Hxv. apply Hag. exact Hx.
  - exists (wupd W2 booked 1). split; [ right; split; reflexivity | ].
    intros x Hx. destruct (Nat.eq_dec x booked) as [-> | Hxb].
    + rewrite !wupd_same. reflexivity.
    + rewrite !wupd_other by exact Hxb. apply Hag. exact Hx.
Qed.

Lemma V0_guards_Ggood : guards_in_cone V0 Ggood.
Proof.
  unfold Ggood. simpl. repeat split; try exact I; intros W1 W2 _; reflexivity.
Qed.

(* two genuinely different worlds that the theorem identifies *)
Definition W0' : World := wupd W0 2 5.

Lemma W0_W0'_differ : W0 <> W0'.
Proof.
  intro Heq. assert (H : W0 2 = 5) by (rewrite Heq; apply wupd_same).
  unfold W0 in H. discriminate.
Qed.

Lemma W0_W0'_agree : agree V0 W0 W0'.
Proof.
  intros x Hx. unfold W0'. symmetry. apply wupd_other.
  destruct Hx as [-> | ->]; unfold verified, booked; lia.
Qed.

Theorem cone_is_not_degenerate : forall b,
  W0 <> W0' /\ (safeT E0 Haz0 b Ggood W0 <-> safeT E0 Haz0 b Ggood W0').
Proof.
  intro b. split; [ exact W0_W0'_differ | ].
  apply (safeT_cone E0 Haz0 V0 V0_haz_cone V0_cap_cone b Ggood W0 W0'
           V0_guards_Ggood W0_W0'_agree).
Qed.

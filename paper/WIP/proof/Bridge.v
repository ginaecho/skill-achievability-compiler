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

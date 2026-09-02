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

Require Import List Arith Lia.
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

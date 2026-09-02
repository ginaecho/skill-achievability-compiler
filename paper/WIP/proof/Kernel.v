(* ================================================================= *)
(*  Kernel.v -- the VERIFIED KERNEL of `skillc severity`.              *)
(*                                                                     *)
(*  Instantiates the decision procedure of Mu.v on the boolean         *)
(*  fragment of the pack language: worlds are bit vectors, tools are   *)
(*  STRIPS actions (precondition formula, add list, delete list),      *)
(*  guards are world sets, and the derived hazard -- an irreversible   *)
(*  tool fires when the goal is no longer reachable -- is a bit set by *)
(*  the instantiated action.  The reachability decision (kernel_first) *)
(*  is proved correct; the ELABORATION from the tool's protocol tree   *)
(*  (elab) is the trusted front end, kept small and executable.        *)
(*  Extracted to OCaml (extract.v); the tool cross-checks its verdict  *)
(*  against the kernel.  Coq 8.18, stdlib only, axiom-free.            *)
(* ================================================================= *)
From Coq Require Import List Lia Arith PeanoNat Bool.
Import ListNotations.
Require Import Severity Regular Mu.

(* ---- worlds ---- *)
Definition Wd := list bool.
Definition Wd_dec : forall x y : Wd, {x = y} + {x <> y} := list_eq_dec Bool.bool_dec.
Definition Wd_eqb (x y : Wd) : bool := if Wd_dec x y then true else false.
Lemma Wd_eqb_eq : forall x y, Wd_eqb x y = true <-> x = y.
Proof. intros. unfold Wd_eqb. destruct (Wd_dec x y); split; intro; congruence. Qed.

Definition wget (w : Wd) (i : nat) : bool := nth i w false.
Fixpoint wset (w : Wd) (i : nat) (v : bool) : Wd :=
  match w, i with
  | [], _ => []
  | _ :: t, 0 => v :: t
  | b :: t, S i' => b :: wset t i' v
  end.
Lemma wset_length : forall w i v, length (wset w i v) = length w.
Proof. induction w as [ | b t IH ]; intros [ | i ] v; simpl; auto. Qed.

Fixpoint set_all (v : bool) (is : list nat) (w : Wd) : Wd :=
  match is with [] => w | i :: t => set_all v t (wset w i v) end.
Lemma set_all_length : forall v is w, length (set_all v is w) = length w.
Proof. intros v is. induction is as [ | i t IH ]; intro w; simpl; [ reflexivity | rewrite IH; apply wset_length ]. Qed.

(* ---- formulas ---- *)
Inductive F : Type := FTrue | FAtom (i : nat) | FAnd (a b : F) | FOr (a b : F) | FNot (a : F).
Fixpoint satf (f : F) (w : Wd) : bool :=
  match f with
  | FTrue => true
  | FAtom i => wget w i
  | FAnd a b => satf a w && satf b w
  | FOr a b => satf a w || satf b w
  | FNot a => negb (satf a w)
  end.

(* ---- instantiated actions ---- *)
Record Act := { a_pre : F; a_add : list nat; a_del : list nat; a_haz : list Wd }.
Definition never : Act := {| a_pre := FNot FTrue; a_add := []; a_del := []; a_haz := [] |}.

Definition apply_act (hz : nat) (a : Act) (w : Wd) : Wd :=
  let w2 := set_all false (a_del a) (set_all true (a_add a) w) in
  if existsb (Wd_eqb w2) (a_haz a) then wset w2 hz true else w2.
Lemma apply_act_length : forall hz a w, length (apply_act hz a w) = length w.
Proof.
  intros. unfold apply_act. destruct (existsb _ _); [ rewrite wset_length | ]; repeat rewrite set_all_length; reflexivity.
Qed.

Definition succE (hz : nat) (tbl : list Act) (a : CapN) (w : Wd) : list Wd :=
  let ac := nth a tbl never in if satf (a_pre ac) w then [apply_act hz ac w] else [].
Definition Ek (hz : nat) (tbl : list Act) (a : CapN) (w w' : Wd) : Prop := In w' (succE hz tbl a w).
Definition hazb (hz : nat) (w : Wd) : bool := wget w hz.
Definition Hazk (hz : nat) (w : Wd) : Prop := hazb hz w = true.

(* ---- guards: world sets ---- *)
Definition Gd := list Wd.
Definition Gd_dec : forall x y : Gd, {x = y} + {x <> y} := list_eq_dec Wd_dec.
Definition satg (g : Gd) (w : Wd) : Prop := In w g.
Definition satb (g : Gd) (w : Wd) : bool := existsb (Wd_eqb w) g.
Lemma satb_spec : forall g w, satg g w <-> satb g w = true.
Proof.
  intros g w. unfold satg, satb. rewrite existsb_exists. split.
  - intro H. exists w. split; [ exact H | apply Wd_eqb_eq; reflexivity ].
  - intros [x [Hx He]]. apply Wd_eqb_eq in He. subst. exact Hx.
Qed.

(* ---- all bit vectors of a length ---- *)
Fixpoint all_bits (n : nat) : list Wd :=
  match n with
  | 0 => [[]]
  | S k => map (cons true) (all_bits k) ++ map (cons false) (all_bits k)
  end.
Lemma all_bits_spec : forall n w, In w (all_bits n) <-> length w = n.
Proof.
  induction n as [ | n IH ]; intro w; simpl.
  - destruct w as [ | b t ]; simpl; split; intro H.
    + reflexivity.
    + left. reflexivity.
    + destruct H as [H | H]; [ discriminate | contradiction ].
    + discriminate.
  - split.
    + intro H. apply in_app_or in H. destruct H as [H | H]; apply in_map_iff in H;
        destruct H as [w0 [Heq Hin]]; subst; simpl; f_equal; apply IH; exact Hin.
    + intro H. destruct w as [ | b t ]; [ discriminate | ]. simpl in H. injection H as Hl.
      apply in_or_app. destruct b; [ left | right ]; apply in_map; apply (proj2 (IH t)); exact Hl.
Qed.

Lemma Ek_closed : forall hz tbl n a w w', In w (all_bits n) -> Ek hz tbl a w w' -> In w' (all_bits n).
Proof.
  intros hz tbl n a w w' Hw HE. unfold Ek, succE in HE. destruct (satf _ _); [ | contradiction ].
  destruct HE as [HE | []]. subst. apply all_bits_spec. rewrite apply_act_length. apply all_bits_spec. exact Hw.
Qed.

(* ================================================================= *)
(*  The verified decision: hazard reachable within budget k.           *)
(* ================================================================= *)
Definition kernel_hazard (n hz : nat) (tbl : list Act) (k : nat) (G0 : Gr Gd) (w0 : Wd) : bool :=
  decide_mu Wd Gd Wd_dec Gd_dec (all_bits n) satb (succE hz tbl) (hazb hz) k G0 w0.

Theorem kernel_correct : forall n hz tbl k G0 w0,
  closed_at Gd 0 G0 -> length w0 = n ->
  (kernel_hazard n hz tbl k G0 w0 = true <-> reach_mu Wd Gd satg (Ek hz tbl) (Hazk hz) k G0 w0).
Proof.
  intros n hz tbl k G0 w0 Hc Hlen. unfold kernel_hazard.
  apply (decide_mu_correct Wd Gd satg (Ek hz tbl) (Hazk hz) Wd_dec Gd_dec (all_bits n)
           (Ek_closed hz tbl n) satb satb_spec (succE hz tbl) (fun a w w' => iff_refl _)
           (hazb hz) (fun w => iff_refl _) k G0 w0 Hc).
  apply all_bits_spec. exact Hlen.
Qed.

Definition kernel_first (n hz : nat) (tbl : list Act) (kmax : nat) (G0 : Gr Gd) (w0 : Wd) : option nat :=
  find (fun k => kernel_hazard n hz tbl k G0 w0) (seq 0 (S kmax)).

Lemma find_seq_first : forall (f : nat -> bool) a m k,
  find f (seq a m) = Some k -> f k = true /\ (forall j, a <= j < k -> f j = false).
Proof.
  intros f a m. revert a. induction m as [ | m IH ]; intros a k H; simpl in H; [ discriminate | ].
  destruct (f a) eqn:Hfa.
  - inversion H; subst. split; [ exact Hfa | intros j Hj; lia ].
  - destruct (IH (S a) k H) as [Hk Hall]. split; [ exact Hk | ].
    intros j Hj. destruct (Nat.eq_dec j a); [ subst; exact Hfa | apply Hall; lia ].
Qed.

Lemma find_seq_none : forall (f : nat -> bool) a m,
  find f (seq a m) = None -> forall j, a <= j < a + m -> f j = false.
Proof.
  intros f a m. revert a. induction m as [ | m IH ]; intros a H j Hj; simpl in H; [ lia | ].
  destruct (f a) eqn:Hfa; [ discriminate | ].
  destruct (Nat.eq_dec j a); [ subst; exact Hfa | apply (IH (S a) H); lia ].
Qed.

Theorem kernel_first_spec : forall n hz tbl kmax G0 w0,
  closed_at Gd 0 G0 -> length w0 = n ->
  match kernel_first n hz tbl kmax G0 w0 with
  | Some k => reach_mu Wd Gd satg (Ek hz tbl) (Hazk hz) k G0 w0 /\
              forall j, j < k -> ~ reach_mu Wd Gd satg (Ek hz tbl) (Hazk hz) j G0 w0
  | None => forall k, k <= kmax -> ~ reach_mu Wd Gd satg (Ek hz tbl) (Hazk hz) k G0 w0
  end.
Proof.
  intros n hz tbl kmax G0 w0 Hc Hlen. unfold kernel_first.
  destruct (find _ _) as [k | ] eqn:Hf.
  - apply find_seq_first in Hf. destruct Hf as [Hk Hall]. split.
    + apply (kernel_correct n hz tbl k G0 w0 Hc Hlen). exact Hk.
    + intros j Hj Hr. apply (kernel_correct n hz tbl j G0 w0 Hc Hlen) in Hr.
      rewrite Hall in Hr; [ discriminate | lia ].
  - intros k Hk Hr. apply (kernel_correct n hz tbl k G0 w0 Hc Hlen) in Hr.
    rewrite (find_seq_none _ _ _ Hf k) in Hr; [ discriminate | lia ].
Qed.

(* ================================================================= *)
(*  Goal reachability (budget-free), used by the elaboration.          *)
(* ================================================================= *)
Definition GW := (Gr Gd * Wd)%type.
Definition GW_dec : forall x y : GW, {x = y} + {x <> y}.
Proof.
  intros [G1 w1] [G2 w2].
  destruct (Gr_eq_dec Gd Gd_dec G1 G2); [ | right; congruence ].
  destruct (Wd_dec w1 w2); [ left; congruence | right; congruence ].
Defined.

Definition gsucc (hz : nat) (tbl : list Act) (s : GW) : list GW :=
  succ0 Wd Gd satb (succE hz tbl) (fst s) (snd s) ++ succ1 Wd Gd satb (fst s) (snd s).
Definition is_end (G : Gr Gd) : bool := match G with REnd _ => true | _ => false end.
Definition goal_hit (goal : F) (s : GW) : bool := is_end (fst s) && satf goal (snd s).

Definition goal_reachable (n hz : nat) (tbl : list Act) (goal : F) (G : Gr Gd) (w : Wd) : bool :=
  decide' GW GW_dec (gsucc hz tbl) (list_prod (cands Gd [] G) (all_bits n)) (goal_hit goal) (G, w).

Definition goal_reach (hz : nat) (tbl : list Act) (goal : F) (G : Gr Gd) (w : Wd) : Prop :=
  exists w', reach GW (gsucc hz tbl) (G, w) (REnd Gd, w') /\ satf goal w' = true.

Lemma gsucc_closed : forall n hz tbl G0,
  closed_at Gd 0 G0 ->
  forall s s', In s (list_prod (cands Gd [] G0) (all_bits n)) -> edge GW (gsucc hz tbl) s s' ->
    In s' (list_prod (cands Gd [] G0) (all_bits n)).
Proof.
  intros n hz tbl G0 Hc [G w] [G' w'] Hin He.
  apply in_prod_iff in Hin. destruct Hin as [HG Hw].
  unfold edge, gsucc in He. simpl in He. apply in_app_or in He.
  assert (Hstep : mstep0 Wd Gd satg (Ek hz tbl) G w G' w' \/ mstep1 Wd Gd satg G w G' w').
  { destruct He as [He | He].
    - left. apply (succ0_iff Wd Gd satg (Ek hz tbl) satb satb_spec (succE hz tbl) (fun a w w' => iff_refl _)). exact He.
    - right. apply (succ1_iff Wd Gd satg satb satb_spec). exact He. }
  apply in_prod_iff. split.
  - eapply cands_closed; [ exact Hc | exact HG | exact Hstep ].
  - destruct Hstep as [Hs | Hs]; inversion Hs; subst; try exact Hw.
    eapply Ek_closed; [ exact Hw | eassumption ].
Qed.

Theorem goal_reachable_correct : forall n hz tbl goal G w,
  closed_at Gd 0 G -> length w = n ->
  (goal_reachable n hz tbl goal G w = true <-> goal_reach hz tbl goal G w).
Proof.
  intros n hz tbl goal G w Hc Hlen. unfold goal_reachable. split.
  - intro Hd. destruct (decide'_sound _ _ _ _ _ _ Hd) as [[G' w'] [Hr Hb]].
    unfold goal_hit in Hb. simpl in Hb. apply andb_true_iff in Hb. destruct Hb as [He Hg].
    destruct G'; simpl in He; try discriminate.
    exists w'. split; assumption.
  - intros [w' [Hr Hg]].
    apply (decide'_complete GW GW_dec (gsucc hz tbl) _ (goal_hit goal) (gsucc_closed n hz tbl G Hc) (G, w) (REnd Gd, w')).
    + apply in_prod_iff. split; [ rewrite <- (close_nil Gd G Hc) at 1; apply cands_head | apply all_bits_spec; exact Hlen ].
    + exact Hr.
    + unfold goal_hit. simpl. rewrite Hg. reflexivity.
Qed.

(* ================================================================= *)
(*  HOW THE KERNEL'S GOAL NOTION RELATES TO THE THEORY'S.              *)
(*                                                                     *)
(*  goal_reach is NOT reach_haz for the goal predicate.  It demands    *)
(*  the protocol RUN TO COMPLETION -- the witness must end at REnd --   *)
(*  and it spends no budget, taking compliant and misselection edges    *)
(*  alike.  One direction holds, with the budget read off the witness   *)
(*  path; the other fails, because the goal can hold before the         *)
(*  protocol ends.  So the kernel's notion of "achieves the goal" is    *)
(*  strictly the stronger one at the budget it uses, and a Benign       *)
(*  verdict computed with it is conservative: it can call a residual    *)
(*  Futile that the theory calls Benign, never the reverse.             *)
(* ================================================================= *)
Lemma goal_path_reach_mu : forall hz tbl goal x y,
  reach GW (gsucc hz tbl) x y ->
  fst y = REnd Gd -> satf goal (snd y) = true ->
  exists k, reach_mu Wd Gd satg (Ek hz tbl) (fun v => satf goal v = true)
                     k (fst x) (snd x).
Proof.
  intros hz tbl goal x y Hr.
  induction Hr as [ x | x y z He Hr IH ]; intros Hend Hg.
  - exists 0. apply RB_here. exact Hg.
  - destruct (IH Hend Hg) as [k Hk].
    destruct x as [Gx wx]. destruct y as [Gy wy]. simpl in *.
    unfold edge, gsucc in He. simpl in He. apply in_app_or in He.
    destruct He as [He | He].
    + exists k. eapply RB_ok; [ | exact Hk ].
      apply (succ0_iff Wd Gd satg (Ek hz tbl) satb satb_spec (succE hz tbl)
               (fun a w w' => iff_refl _)). exact He.
    + exists (S k). eapply RB_dev; [ | exact Hk ].
      apply (succ1_iff Wd Gd satg satb satb_spec). exact He.
Qed.

Theorem goal_reach_implies_reach_mu : forall hz tbl goal G w,
  goal_reach hz tbl goal G w ->
  exists k, reach_mu Wd Gd satg (Ek hz tbl) (fun v => satf goal v = true) k G w.
Proof.
  intros hz tbl goal G w [w' [Hr Hg]].
  apply (goal_path_reach_mu hz tbl goal (G, w) (REnd Gd, w') Hr);
    [ reflexivity | exact Hg ].
Qed.

(* the converse fails: a protocol whose goal already holds but which
   cannot run to completion *)
Definition Gstuck : Gr Gd := RAct Gd 0 0 (REnd Gd).

Theorem goal_reach_strictly_stronger :
  reach_mu Wd Gd satg (Ek 0 []) (fun v => satf FTrue v = true) 0 Gstuck [false]
  /\ ~ goal_reach 0 [] FTrue Gstuck [false].
Proof.
  split.
  - apply RB_here. reflexivity.
  - intros [w' [Hr Hg]].
    inversion Hr as [ x1 Hx1 | x1 y1 z1 He Hr' ]; subst.
    unfold edge, gsucc in He. simpl in He. exact He.
Qed.

(* ---- and the other direction fails too, so the two are incomparable --- *)
(*  goal_reach spends misselection edges for free, so it can reach the    *)
(*  goal where budgeted Phi-reachability cannot.  Together with           *)
(*  goal_reach_strictly_stronger this says the kernel's goal notion is    *)
(*  neither weaker nor stronger than the theory's: it demands completion  *)
(*  and it ignores the budget.                                            *)
Definition act_set0 : Act :=
  {| a_pre := FTrue; a_add := [0]; a_del := []; a_haz := [] |}.

Definition Gmiss : Gr Gd :=
  RComm Gd 0 1 [(7, @nil Wd, RAct Gd 0 0 (REnd Gd))].

Theorem goal_reach_ignores_the_budget :
  goal_reach 1 [act_set0] (FAtom 0) Gmiss [false; false] /\
  ~ reach_mu Wd Gd satg (Ek 1 [act_set0]) (fun v => satf (FAtom 0) v = true)
              0 Gmiss [false; false].
Proof.
  split.
  - exists [true; false]. split.
    + eapply R_step with (RAct Gd 0 0 (REnd Gd), [false; false]).
      * unfold edge, gsucc. simpl. auto.
      * eapply R_step with (REnd Gd, [true; false]).
        -- unfold edge, gsucc. simpl. auto.
        -- apply R_refl.
    + reflexivity.
  - intro Hr.
    inversion Hr as [ b n w Hh | b n w n' w' Hs Hr' | b n w n' w' Hs Hr' ]; subst.
    + simpl in Hh. discriminate Hh.
    + inversion Hs as [ | | p0 q0 brs0 l g Gl w0 Hin Hsat | ]; subst.
      destruct Hin as [Heq | []]. inversion Heq; subst. exact Hsat.
Qed.

(* ================================================================= *)
(*  Elaboration (trusted front end): the tool's protocol tree, with    *)
(*  explicit or RATIONAL guards, becomes a guarded regular type whose  *)
(*  guard tables and hazard tables are computed with goal_reachable.   *)
(* ================================================================= *)
Inductive Raw : Type :=
| WEnd : Raw
| WAct : nat -> bool -> Role -> Raw -> Raw               (* base cap, irreversible?, role *)
| WChoice : Role -> Role -> list (Lab * option F * Raw) -> Raw
| WMu : Raw -> Raw
| WVar : nat -> Raw.

Record BCap := { b_pre : F; b_add : list nat; b_del : list nat }.
Definition base_act (b : BCap) : Act :=
  {| a_pre := b_pre b; a_add := b_add b; a_del := b_del b; a_haz := [] |}.
Definition never_b : BCap := {| b_pre := FNot FTrue; b_add := []; b_del := [] |}.

(* the skeleton: every guard total, base actions *)
Fixpoint skel (all : Gd) (r : Raw) : Gr Gd :=
  match r with
  | WEnd => REnd Gd
  | WAct c _ p G => RAct Gd c p (skel all G)
  | WChoice p q brs => RComm Gd p q (map (fun b => (fst (fst b), all, skel all (snd b))) brs)
  | WMu G => RMu Gd (skel all G)
  | WVar i => RVar Gd i
  end.

Record Params := { p_n : nat; p_hz : nat; p_base : list BCap; p_goal : F; p_worlds : list Wd }.
Definition gr (P : Params) (G : Gr Gd) (w : Wd) : bool :=
  goal_reachable (p_n P) (p_hz P) (map base_act (p_base P)) (p_goal P) G w.

Fixpoint elab (P : Params) (ctx : list (Gr Gd)) (r : Raw) (acc : list Act) : Gr Gd * list Act :=
  match r with
  | WEnd => (REnd Gd, acc)
  | WAct c irr p G =>
      let res := elab P ctx G acc in
      if irr then
        let cont := close Gd ctx (skel (p_worlds P) G) in
        let hz_tbl := filter (fun w => negb (gr P cont w)) (p_worlds P) in
        let b := nth c (p_base P) never_b in
        let ac := {| a_pre := b_pre b; a_add := b_add b; a_del := b_del b; a_haz := hz_tbl |} in
        (RAct Gd (length (snd res)) p (fst res), snd res ++ [ac])
      else (RAct Gd c p (fst res), snd res)
  | WChoice p q brs =>
      let res :=
        (fix go (bs : list (Lab * option F * Raw)) (acc0 : list Act)
             : list (Lab * Gd * Gr Gd) * list Act :=
           match bs with
           | [] => ([], acc0)
           | b :: t =>
               let r1 := elab P ctx (snd b) acc0 in
               let g := match snd (fst b) with
                        | Some f => filter (fun w => satf f w) (p_worlds P)
                        | None => filter (fun w => gr P (close Gd ctx (skel (p_worlds P) (snd b))) w)
                                         (p_worlds P)
                        end in
               let r2 := go t (snd r1) in
               ((fst (fst b), g, fst r1) :: fst r2, snd r2)
           end) brs acc in
      (RComm Gd p q (fst res), snd res)
  | WMu G =>
      let res := elab P (close Gd ctx (RMu Gd (skel (p_worlds P) G)) :: ctx) G acc in
      (RMu Gd (fst res), snd res)
  | WVar i => (RVar Gd i, acc)
  end.

(* reachable worlds of the skeleton from the initial world: guard and
   hazard tables need only be computed there *)
Definition reachable_worlds (P : Params) (G0 : Gr Gd) (w0 : Wd) : list Wd :=
  map snd (iter' GW GW_dec (gsucc (p_hz P) (map base_act (p_base P)))
                 (length (list_prod (cands Gd [] G0) (p_worlds P))) [(G0, w0)]).

Definition kernel_run (n_atoms : nat) (base : list BCap) (goal : F) (init : list nat) (kmax : nat) (raw : Raw)
  : option nat :=
  let n := S n_atoms in
  let hz := n_atoms in
  let all := all_bits n in
  let w0 := set_all true init (repeat false n) in
  let P0 := {| p_n := n; p_hz := hz; p_base := base; p_goal := goal; p_worlds := all |} in
  let ws := reachable_worlds P0 (skel all raw) w0 in
  let ws' := ws ++ map (fun w => wset w hz true) ws in
  let P := {| p_n := n; p_hz := hz; p_base := base; p_goal := goal; p_worlds := ws' |} in
  let res := elab P [] raw (map base_act base) in
  kernel_first n hz (snd res) kmax (fst res) w0.

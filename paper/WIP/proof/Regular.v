(* ================================================================= *)
(*  Regular.v  --  (B) REGULAR protocols: loops, product, decidability. *)
(*                                                                     *)
(*  A regular global type (mu X. G, a rational tree) unfolds to a      *)
(*  FINITE GRAPH of protocol nodes.  Over the finite abstract world of  *)
(*  the widened fragment, budgeted hazard reachability is reachability *)
(*  in a finite PRODUCT graph  Node x World x {0..k}.  Mechanized here, *)
(*  abstractly over any node/world types:                               *)
(*                                                                      *)
(*   product_correspondence : budgeted reachability on the protocol     *)
(*        graph  <->  plain reachability in the product graph            *)
(*   budget_never_increases, dev_edges_bounded, dev_edges_exact :        *)
(*        the budget is a monotone counter debited exactly once per      *)
(*        misselection edge -- so a LOOP containing a misselectable       *)
(*        branch is re-entered at most k times within budget k            *)
(*   reach_bounded_path : reachability is witnessed by a path no longer  *)
(*        than the number of reachable states (pigeonhole)                *)
(*   decide_reachb_correct : an EXECUTABLE decision procedure for         *)
(*        budgeted hazard reachability, sound and complete -- hence the   *)
(*        tolerance degree of a regular protocol is computable            *)
(*                                                                        *)
(*  Coq 8.18, stdlib only, axiom-free (check_regular.v).                  *)
(* ================================================================= *)

Require Import List Arith Lia Bool.
Import ListNotations.

(* ================================================================= *)
(*  Section 1.  Finite-graph reachability: bounded witnesses and an   *)
(*  executable decision procedure.                                    *)
(* ================================================================= *)
Section FiniteReach.
Variable A : Type.
Hypothesis A_dec : forall x y : A, {x = y} + {x <> y}.
Variable succ : A -> list A.

Definition edge (x y : A) : Prop := In y (succ x).

(* a path FROM x THROUGH the states in l, in order *)
Fixpoint is_path (x : A) (l : list A) : Prop :=
  match l with
  | [] => True
  | y :: rest => edge x y /\ is_path y rest
  end.

Inductive reach : A -> A -> Prop :=
| R_refl : forall x, reach x x
| R_step : forall x y z, edge x y -> reach y z -> reach x z.

Lemma reach_trans : forall x y z, reach x y -> reach y z -> reach x z.
Proof. intros x y z H. induction H; intros; [ assumption | eapply R_step; eauto ]. Qed.

Lemma last_cons_self : forall (x : A) l, last (x :: l) x = last l x.
Proof. intros x l. destruct l; reflexivity. Qed.

Lemma last_nonempty_default : forall (l : list A) d d', l <> [] -> last l d = last l d'.
Proof.
  induction l as [ | y l IH ]; intros d d' Hne; [ congruence | ].
  destruct l; [ reflexivity | ]. simpl. apply IH. discriminate.
Qed.

Lemma last_app_cons : forall l1 (a : A) l2 d, last (l1 ++ a :: l2) d = last (a :: l2) d.
Proof.
  induction l1 as [ | x l1 IH ]; intros; simpl; [ reflexivity | ].
  destruct (l1 ++ a :: l2) eqn:E; [ destruct l1; discriminate E | ].
  rewrite <- E. apply IH.
Qed.

Lemma is_path_app :
  forall l1 l2 x, is_path x (l1 ++ l2) <-> is_path x l1 /\ is_path (last l1 x) l2.
Proof.
  induction l1 as [ | y l1 IH ]; intros l2 x; simpl.
  - tauto.
  - rewrite IH. destruct l1 as [ | z l1 ].
    + simpl. tauto.
    + change (last (y :: z :: l1) x) with (last (z :: l1) x).
      rewrite (last_nonempty_default (z :: l1) x y) by discriminate. tauto.
Qed.

Lemma reach_of_path : forall l x, is_path x l -> reach x (last l x).
Proof.
  induction l as [ | y l IH ]; intros x Hp.
  - apply R_refl.
  - destruct Hp as [He Hp]. destruct l as [ | z l ].
    + simpl. eapply R_step; [ exact He | apply R_refl ].
    + eapply R_step; [ exact He | ].
      change (last (y :: z :: l) x) with (last (z :: l) x).
      rewrite (last_nonempty_default (z :: l) x y) by discriminate.
      apply IH. exact Hp.
Qed.

Lemma path_of_reach : forall x y, reach x y -> exists l, is_path x l /\ last l x = y.
Proof.
  intros x y H. induction H as [ x | x y z He Hr [l [Hp Hl]] ].
  - exists []. split; [ exact I | reflexivity ].
  - exists (y :: l). split.
    + simpl. split; [ exact He | exact Hp ].
    + destruct l as [ | w l ].
      * simpl in *. exact Hl.
      * change (last (y :: w :: l) x) with (last (w :: l) x).
        rewrite (last_nonempty_default (w :: l) x y) by discriminate. exact Hl.
Qed.

Lemma path_elems_reach :
  forall l x, is_path x l -> forall y, In y (x :: l) -> reach x y.
Proof.
  induction l as [ | z l IH ]; intros x Hp y Hy; simpl in *.
  - destruct Hy as [Hy | []]. subst. apply R_refl.
  - destruct Hp as [He Hp]. destruct Hy as [Hy | Hy].
    + subst. apply R_refl.
    + eapply R_step; [ exact He | ]. apply (IH z Hp y Hy).
Qed.

Lemma not_NoDup_split :
  forall l : list A, ~ NoDup l -> exists a l1 l2 l3, l = l1 ++ a :: l2 ++ a :: l3.
Proof.
  induction l as [ | x l IH ]; intros Hn.
  - exfalso. apply Hn. constructor.
  - destruct (in_dec A_dec x l) as [Hin | Hnin].
    + destruct (in_split x l Hin) as [l2 [l3 Hl]].
      exists x, [], l2, l3. simpl. rewrite Hl. reflexivity.
    + assert (Hn' : ~ NoDup l) by (intro Hd; apply Hn; constructor; assumption).
      destruct (IH Hn') as [a [l1 [l2 [l3 Hl]]]].
      exists a, (x :: l1), l2, l3. simpl. rewrite Hl. reflexivity.
Qed.

Lemma in_length_pos : forall (l : list A) x, In x l -> 0 < length l.
Proof. intros l x H. destruct l; [ contradiction | simpl; lia ]. Qed.

(* the reachable set from x, given as a list *)
Variable all : list A.

Lemma path_shorten :
  forall x l,
    (forall y, reach x y -> In y all) ->
    is_path x l -> length (x :: l) > length all ->
    exists l', is_path x l' /\ length l' < length l /\ last l' x = last l x.
Proof.
  intros x l Hall Hp Hlen.
  assert (Hnd : ~ NoDup (x :: l)).
  { intro Hd.
    assert (Hincl : incl (x :: l) all)
      by (intros y Hy; apply Hall; eapply path_elems_reach; eassumption).
    pose proof (NoDup_incl_length Hd Hincl). lia. }
  destruct (not_NoDup_split (x :: l) Hnd) as [a [l1 [l2 [l3 Heq]]]].
  destruct l1 as [ | x0 l1 ]; simpl in Heq; inversion Heq; subst.
  - (* l = l2 ++ x :: l3 : keep the suffix after the second x *)
    exists l3.
    apply is_path_app in Hp. destruct Hp as [_ Hp]. simpl in Hp. destruct Hp as [_ Hp].
    split; [ exact Hp | ]. split.
    + rewrite app_length. simpl. lia.
    + rewrite last_app_cons. symmetry. apply last_cons_self.
  - (* l = l1 ++ a :: l2 ++ a :: l3 : cut the middle segment *)
    exists (l1 ++ a :: l3).
    apply is_path_app in Hp. destruct Hp as [H1 H2].
    simpl in H2. destruct H2 as [He H2].
    apply is_path_app in H2. destruct H2 as [_ H3].
    simpl in H3. destruct H3 as [_ H3].
    split.
    { apply is_path_app. split; [ exact H1 | ]. simpl. split; [ exact He | exact H3 ]. }
    split.
    + simpl. repeat rewrite app_length. simpl. repeat rewrite app_length. simpl. lia.
    + rewrite last_app_cons. rewrite last_app_cons.
      rewrite app_comm_cons. rewrite last_app_cons. reflexivity.
Qed.

Lemma reach_bounded_path :
  forall x y,
    (forall z, reach x z -> In z all) ->
    reach x y ->
    exists l, is_path x l /\ last l x = y /\ length (x :: l) <= length all.
Proof.
  intros x y Hall Hr.
  destruct (path_of_reach x y Hr) as [l [Hp Hl]].
  assert (H : forall n l0, length l0 <= n -> is_path x l0 -> last l0 x = y ->
              exists l', is_path x l' /\ last l' x = y /\ length (x :: l') <= length all).
  { induction n as [ | n IH ]; intros l0 Hn Hp0 Hl0.
    - destruct l0; [ | simpl in Hn; lia ].
      exists []. repeat split; [ exact Hl0 | ].
      simpl. pose proof (in_length_pos all x (Hall x (R_refl x))). lia.
    - destruct (le_gt_dec (length (x :: l0)) (length all)) as [Hle | Hgt].
      + exists l0. repeat split; assumption.
      + destruct (path_shorten x l0 Hall Hp0 Hgt) as [l' [Hp' [Hlt Hl']]].
        apply (IH l'); [ lia | exact Hp' | rewrite Hl'; exact Hl0 ]. }
  apply (H (length l) l (Nat.le_refl _) Hp Hl).
Qed.

(* ---- executable side ---- *)
Definition expand (S : list A) : list A := S ++ concat (map succ S).
Fixpoint iter (n : nat) (S : list A) : list A :=
  match n with 0 => S | S k => iter k (expand S) end.

Lemma expand_mono : forall S x, In x S -> In x (expand S).
Proof. intros. unfold expand. apply in_or_app. left. assumption. Qed.

Lemma expand_succ : forall S x y, In x S -> edge x y -> In y (expand S).
Proof.
  intros S x y Hx He. unfold expand. apply in_or_app. right.
  apply in_concat. exists (succ x). split; [ apply in_map; assumption | exact He ].
Qed.

Lemma iter_mono : forall n S x, In x S -> In x (iter n S).
Proof.
  induction n as [ | n IH ]; intros S x Hx; simpl; [ exact Hx | ].
  apply IH. apply expand_mono. exact Hx.
Qed.

Lemma expand_sound :
  forall (P : A -> Prop) S,
    (forall x y, P x -> edge x y -> P y) ->
    (forall x, In x S -> P x) ->
    forall y, In y (expand S) -> P y.
Proof.
  intros P S Hcl HS y Hy. unfold expand in Hy. apply in_app_or in Hy.
  destruct Hy as [Hy | Hy]; [ apply HS; exact Hy | ].
  apply in_concat in Hy. destruct Hy as [l [Hl Hy]].
  apply in_map_iff in Hl. destruct Hl as [x [Hlx Hx]]. subst l.
  eapply Hcl; [ apply HS; exact Hx | exact Hy ].
Qed.

Lemma iter_sound_P :
  forall (P : A -> Prop) n S,
    (forall x y, P x -> edge x y -> P y) ->
    (forall x, In x S -> P x) ->
    forall y, In y (iter n S) -> P y.
Proof.
  intros P n. induction n as [ | n IH ]; intros S Hcl HS y Hy; simpl in Hy.
  - apply HS. exact Hy.
  - apply (IH (expand S) Hcl); [ | exact Hy ].
    intros z Hz. eapply expand_sound; eassumption.
Qed.

Lemma iter_complete :
  forall n x l, is_path x l -> length l <= n ->
    forall S, In x S -> In (last l x) (iter n S).
Proof.
  induction n as [ | n IH ]; intros x l Hp Hlen S Hx; simpl.
  - destruct l; [ simpl; exact Hx | simpl in Hlen; lia ].
  - destruct l as [ | y l ].
    + simpl. apply iter_mono. apply expand_mono. exact Hx.
    + simpl in Hp. destruct Hp as [He Hp]. simpl in Hlen.
      assert (Hy : In y (expand S)) by (eapply expand_succ; eassumption).
      pose proof (IH y l Hp (le_S_n _ _ Hlen) (expand S) Hy) as H.
      destruct l as [ | a l ].
      * simpl in *. exact H.
      * change (last (y :: a :: l) x) with (last (a :: l) x).
        rewrite (last_nonempty_default (a :: l) x y) by discriminate. exact H.
Qed.

Variable hb : A -> bool.
Definition decide (x : A) : bool := existsb hb (iter (length all) [x]).

(* ---- the EXECUTABLE variant: deduplicated frontier, early exit ---- *)
(* `all` must be closed under successors; the start must be in it. *)
Fixpoint add_new (S : list A) (l : list A) : list A :=
  match l with
  | [] => S
  | x :: t => add_new (if in_dec A_dec x S then S else x :: S) t
  end.
Definition expand' (S : list A) : list A := add_new S (concat (map succ S)).
Fixpoint iter' (n : nat) (S : list A) : list A :=
  match n with
  | 0 => S
  | S k => let S' := expand' S in if Nat.eqb (length S') (length S) then S else iter' k S'
  end.
Definition decide' (x : A) : bool := existsb hb (iter' (length all) [x]).

Lemma add_new_in : forall l S x, In x (add_new S l) <-> In x S \/ In x l.
Proof.
  induction l as [ | y t IH ]; intros S x; simpl.
  - tauto.
  - rewrite IH. destruct (in_dec A_dec y S) as [Hy | Hy]; simpl.
    + split; [ tauto | ]. intros [H | [H | H]]; subst; tauto.
    + tauto.
Qed.

Lemma add_new_nodup : forall l S, NoDup S -> NoDup (add_new S l).
Proof.
  induction l as [ | y t IH ]; intros S Hnd; simpl; [ exact Hnd | ].
  apply IH. destruct (in_dec A_dec y S); [ exact Hnd | constructor; assumption ].
Qed.

Lemma expand'_in : forall S x, In x (expand' S) <-> In x S \/ (exists y, In y S /\ edge y x).
Proof.
  intros S x. unfold expand'. rewrite add_new_in. split.
  - intros [H | H]; [ left; exact H | right ]. apply in_concat in H. destruct H as [l [Hl Hx]].
    apply in_map_iff in Hl. destruct Hl as [y [Hly Hy]]. subst l. exists y. split; assumption.
  - intros [H | [y [Hy He]]]; [ left; exact H | right ]. apply in_concat. exists (succ y).
    split; [ apply in_map; exact Hy | exact He ].
Qed.

Lemma expand'_mono : forall S x, In x S -> In x (expand' S).
Proof. intros. apply expand'_in. left. assumption. Qed.

Lemma iter'_mono : forall n S x, In x S -> In x (iter' n S).
Proof.
  induction n as [ | n IH ]; intros S x Hx; simpl; [ exact Hx | ].
  destruct (Nat.eqb (length (expand' S)) (length S)); [ exact Hx | ]. apply IH. apply expand'_mono. exact Hx.
Qed.

Lemma iter'_sound_P :
  forall (P : A -> Prop) n S,
    (forall x y, P x -> edge x y -> P y) ->
    (forall x, In x S -> P x) ->
    forall y, In y (iter' n S) -> P y.
Proof.
  intros P n. induction n as [ | n IH ]; intros S Hcl HS y Hy; simpl in Hy.
  - apply HS. exact Hy.
  - destruct (Nat.eqb (length (expand' S)) (length S)); [ apply HS; exact Hy | ].
    apply (IH (expand' S) Hcl); [ | exact Hy ].
    intros z Hz. apply expand'_in in Hz. destruct Hz as [Hz | [w [Hw He]]]; [ apply HS; exact Hz | ].
    eapply Hcl; [ apply HS; exact Hw | exact He ].
Qed.

Hypothesis all_closed : forall x y, In x all -> edge x y -> In y all.

Lemma expand'_incl_all : forall S, incl S all -> incl (expand' S) all.
Proof.
  intros S Hi x Hx. apply expand'_in in Hx. destruct Hx as [Hx | [y [Hy He]]]; [ apply Hi; exact Hx | ].
  eapply all_closed; [ apply Hi; exact Hy | exact He ].
Qed.

(* with enough fuel the result is closed under edges *)
Lemma iter'_closed : forall n S,
  NoDup S -> incl S all -> length all < n + length S ->
  forall x y, In x (iter' n S) -> edge x y -> In y (iter' n S).
Proof.
  induction n as [ | n IH ]; intros S Hnd Hi Hfuel x y Hx He; simpl in *.
  - exfalso. pose proof (NoDup_incl_length Hnd Hi). lia.
  - destruct (Nat.eqb (length (expand' S)) (length S)) eqn:Hlen.
    + apply Nat.eqb_eq in Hlen.
      assert (Hnd' : NoDup (expand' S)) by (apply add_new_nodup; exact Hnd).
      assert (Hback : incl (expand' S) S).
      { apply NoDup_length_incl; [ exact Hnd | lia | intros z Hz; apply expand'_mono; exact Hz ]. }
      apply (Hback y). apply (proj2 (expand'_in S y)). right. exists x. split; assumption.
    + apply Nat.eqb_neq in Hlen.
      assert (Hle : length S <= length (expand' S)).
      { apply NoDup_incl_length; [ exact Hnd | intros z Hz; apply expand'_mono; exact Hz ]. }
      apply (IH (expand' S) (add_new_nodup _ _ Hnd) (expand'_incl_all _ Hi) ltac:(lia) x y); [ exact Hx | exact He ].
Qed.

Lemma reach_in_iter' : forall n S x y,
  NoDup S -> incl S all -> length all < n + length S ->
  In x (iter' n S) -> reach x y -> In y (iter' n S).
Proof.
  intros n S x y Hnd Hi Hfuel Hx Hr. revert Hx. induction Hr as [ x | x y z He Hr IH ]; intro Hx.
  - exact Hx.
  - apply IH. eapply iter'_closed; [ exact Hnd | exact Hi | exact Hfuel | exact Hx | exact He ].
Qed.

Lemma reach_snoc : forall x y z, reach x y -> edge y z -> reach x z.
Proof.
  intros x y z Hr. induction Hr as [ x | x y w He Hr IH ]; intro He'.
  - eapply R_step; [ exact He' | apply R_refl ].
  - eapply R_step; [ exact He | apply IH; exact He' ].
Qed.

Theorem decide'_sound : forall x, decide' x = true -> exists y, reach x y /\ hb y = true.
Proof.
  intros x Hd. unfold decide' in Hd. apply existsb_exists in Hd. destruct Hd as [y [Hy Hb]].
  exists y. split; [ | exact Hb ].
  apply (iter'_sound_P (fun z => reach x z) (length all) [x]); [ | | exact Hy ].
  - intros u v Hu He. eapply reach_snoc; eassumption.
  - intros z [Hz | []]. subst. apply R_refl.
Qed.

Theorem decide'_complete : forall x y,
  In x all -> reach x y -> hb y = true -> decide' x = true.
Proof.
  intros x y Hx Hr Hb. unfold decide'. apply existsb_exists. exists y. split; [ | exact Hb ].
  apply (reach_in_iter' (length all) [x] x y).
  - constructor; [ intros []; auto | constructor ].
  - intros z [Hz | []]. subst. exact Hx.
  - simpl. lia.
  - apply iter'_mono. left. reflexivity.
  - exact Hr.
Qed.

Theorem decide_sound :
  forall x, decide x = true -> exists y, reach x y /\ hb y = true.
Proof.
  intros x Hd. unfold decide in Hd. apply existsb_exists in Hd.
  destruct Hd as [y [Hy Hb]]. exists y. split; [ | exact Hb ].
  apply (iter_sound_P (reach x) (length all) [x]).
  - intros u v Hu He. eapply reach_trans; [ exact Hu | eapply R_step; [ exact He | apply R_refl ] ].
  - intros z [Hz | []]. subst. apply R_refl.
  - exact Hy.
Qed.

Theorem decide_complete :
  forall x y,
    (forall z, reach x z -> In z all) ->
    reach x y -> hb y = true -> decide x = true.
Proof.
  intros x y Hall Hr Hb. unfold decide. apply existsb_exists.
  destruct (reach_bounded_path x y Hall Hr) as [l [Hp [Hl Hlen]]].
  exists y. split; [ | exact Hb ].
  rewrite <- Hl. apply (iter_complete (length all) x l Hp).
  - simpl in Hlen. lia.
  - left. reflexivity.
Qed.

End FiniteReach.

(* ================================================================= *)
(*  Section 2.  Budgeted reachability on a protocol graph and its     *)
(*  product with the budget counter.                                  *)
(* ================================================================= *)
Section Product.
Variable Node W : Type.
Variable step0 step1 : Node -> W -> Node -> W -> Prop.
Variable Haz : W -> Prop.

Inductive reachb : nat -> Node -> W -> Prop :=
| RB_here : forall b n w, Haz w -> reachb b n w
| RB_ok   : forall b n w n' w', step0 n w n' w' -> reachb b n' w' -> reachb b n w
| RB_dev  : forall b n w n' w', step1 n w n' w' -> reachb b n' w' -> reachb (S b) n w.

Definition PS := (Node * W * nat)%type.

Inductive pstep : PS -> PS -> Prop :=
| P_ok  : forall n w n' w' b, step0 n w n' w' -> pstep (n, w, b) (n', w', b)
| P_dev : forall n w n' w' b, step1 n w n' w' -> pstep (n, w, S b) (n', w', b).

Inductive preach : PS -> PS -> Prop :=
| PR_refl : forall s, preach s s
| PR_step : forall s s' s'', pstep s s' -> preach s' s'' -> preach s s''.

Definition phaz (s : PS) : Prop := match s with (_, w, _) => Haz w end.
Definition pbud (s : PS) : nat := match s with (_, _, b) => b end.

Theorem product_correspondence :
  forall b n w, reachb b n w <-> exists s', preach (n, w, b) s' /\ phaz s'.
Proof.
  intros b n w. split.
  - intro H. induction H as [ b n w Hh
                            | b n w n' w' Hs Hr [s' [Hp Hh]]
                            | b n w n' w' Hs Hr [s' [Hp Hh]] ].
    + exists (n, w, b). split; [ apply PR_refl | exact Hh ].
    + exists s'. split; [ eapply PR_step; [ apply P_ok; exact Hs | exact Hp ] | exact Hh ].
    + exists s'. split; [ eapply PR_step; [ apply P_dev; exact Hs | exact Hp ] | exact Hh ].
  - intros [s' [Hp Hh]].
    remember (n, w, b) as s eqn:Es. revert n w b Es.
    induction Hp as [ s | s s' s'' Hs Hp IH ]; intros n w b Es; subst.
    + apply RB_here. exact Hh.
    + inversion Hs; subst.
      * eapply RB_ok; [ eassumption | exact (IH Hh _ _ _ eq_refl) ].
      * eapply RB_dev; [ eassumption | exact (IH Hh _ _ _ eq_refl) ].
Qed.

Lemma budget_never_increases : forall s s', preach s s' -> pbud s' <= pbud s.
Proof.
  intros s s' H. induction H as [ s | s s' s'' Hs Hp IH ]; [ lia | ].
  inversion Hs; subst; simpl in *; lia.
Qed.

Inductive preach_d : PS -> PS -> nat -> Prop :=
| PD_refl : forall s, preach_d s s 0
| PD_ok   : forall n w n' w' b s'' d,
    step0 n w n' w' -> preach_d (n', w', b) s'' d -> preach_d (n, w, b) s'' d
| PD_dev  : forall n w n' w' b s'' d,
    step1 n w n' w' -> preach_d (n', w', b) s'' d -> preach_d (n, w, S b) s'' (S d).

(* a path with d misselection edges from budget b has d <= b: a loop
   containing a misselectable branch is traversed at most b times *)
Theorem dev_edges_bounded : forall s s' d, preach_d s s' d -> d <= pbud s.
Proof. intros s s' d H. induction H; simpl in *; lia. Qed.

Theorem dev_edges_exact : forall s s' d, preach_d s s' d -> pbud s = pbud s' + d.
Proof. intros s s' d H. induction H; simpl in *; lia. Qed.

End Product.

(* ================================================================= *)
(*  Section 3.  For finite node and world types with computable       *)
(*  successors, budgeted hazard reachability is DECIDABLE.            *)
(* ================================================================= *)
Section Decide.
Variable Node W : Type.
Hypothesis Node_dec : forall x y : Node, {x = y} + {x <> y}.
Hypothesis W_dec : forall x y : W, {x = y} + {x <> y}.
Variable nodes : list Node.   (* need not be exhaustive: closed under successors, below *)
Variable worlds : list W.     (* likewise: closed under successors, below *)
Variable succ0 succ1 : Node -> W -> list (Node * W).
Variable hazb : W -> bool.
Definition step0 n w n' w' := In (n', w') (succ0 n w).
Definition step1 n w n' w' := In (n', w') (succ1 n w).
Definition Haz (w : W) : Prop := hazb w = true.
(* the node list is closed under both kinds of successor *)
Hypothesis nodes_closed : forall n w n' w',
  In n nodes -> (step0 n w n' w' \/ step1 n w n' w') -> In n' nodes.
Hypothesis worlds_closed : forall n w n' w',
  In w worlds -> (step0 n w n' w' \/ step1 n w n' w') -> In w' worlds.

Definition PS' := (Node * W * nat)%type.
Definition ps_dec : forall x y : PS', {x = y} + {x <> y}.
Proof. decide equality; [ apply Nat.eq_dec | decide equality ]. Defined.

Definition psucc (s : PS') : list PS' :=
  match s with
  | (n, w, b) =>
      map (fun p => (fst p, snd p, b)) (succ0 n w)
      ++ match b with
         | 0 => []
         | S b' => map (fun p => (fst p, snd p, b')) (succ1 n w)
         end
  end.

Lemma psucc_iff : forall s s', In s' (psucc s) <-> pstep Node W step0 step1 s s'.
Proof.
  intros [[n w] b] [[n' w'] b']. simpl. split.
  - intro H. apply in_app_or in H. destruct H as [H | H].
    + apply in_map_iff in H. destruct H as [[n0 w0] [Heq Hin]]. simpl in Heq.
      inversion Heq; subst. apply P_ok. exact Hin.
    + destruct b as [ | b0 ]; [ contradiction | ].
      apply in_map_iff in H. destruct H as [[n0 w0] [Heq Hin]]. simpl in Heq.
      inversion Heq; subst. apply P_dev. exact Hin.
  - intro H. inversion H; subst.
    + apply in_or_app. left. apply in_map_iff. exists (n', w'). split; [ reflexivity | assumption ].
    + apply in_or_app. right. apply in_map_iff. exists (n', w'). split; [ reflexivity | assumption ].
Qed.

Fixpoint upto (k : nat) : list nat := match k with 0 => [0] | S k' => S k' :: upto k' end.
Lemma upto_complete : forall k b, b <= k -> In b (upto k).
Proof.
  induction k; intros b Hb; simpl; [ left; lia | ].
  destruct (Nat.eq_dec b (S k)); [ left; congruence | right; apply IHk; lia ].
Qed.

Definition all_ps (k : nat) : list PS' :=
  concat (map (fun n => concat (map (fun w => map (fun b => (n, w, b)) (upto k)) worlds)) nodes).

Lemma upto_inv : forall k b, In b (upto k) -> b <= k.
Proof.
  induction k; intros b Hb; simpl in Hb.
  - destruct Hb as [Hb | []]. lia.
  - destruct Hb as [Hb | Hb]; [ lia | ]. apply IHk in Hb. lia.
Qed.

Lemma all_ps_complete : forall k n w b, In n nodes -> In w worlds -> b <= k -> In (n, w, b) (all_ps k).
Proof.
  intros k n w b Hn Hw Hb. unfold all_ps. apply in_concat.
  eexists. split. { apply in_map. exact Hn. }
  apply in_concat. eexists. split. { apply in_map. exact Hw. }
  apply in_map. apply upto_complete. exact Hb.
Qed.

Lemma all_ps_inv : forall k n w b, In (n, w, b) (all_ps k) -> In n nodes /\ In w worlds /\ b <= k.
Proof.
  intros k n w b H. unfold all_ps in H. apply in_concat in H. destruct H as [l [Hl H]].
  apply in_map_iff in Hl. destruct Hl as [n0 [Hl Hn0]]. subst l.
  apply in_concat in H. destruct H as [l [Hl H]].
  apply in_map_iff in Hl. destruct Hl as [w0 [Hl Hw0]]. subst l.
  apply in_map_iff in H. destruct H as [b0 [Heq Hb0]]. inversion Heq; subst.
  repeat split; [ exact Hn0 | exact Hw0 | apply upto_inv; exact Hb0 ].
Qed.

Definition phazb (s : PS') : bool := match s with (_, w, _) => hazb w end.

Definition decide_reachb (k : nat) (n : Node) (w : W) : bool :=
  decide PS' psucc (all_ps k) phazb (n, w, k).

Lemma preach_to_reach :
  forall s s', preach Node W step0 step1 s s' -> reach PS' psucc s s'.
Proof.
  intros s s' H. induction H as [ s | s s' s'' Hs Hp IH ].
  - apply R_refl.
  - eapply R_step; [ | exact IH ]. unfold edge. apply psucc_iff. exact Hs.
Qed.

Lemma reach_to_preach :
  forall s s', reach PS' psucc s s' -> preach Node W step0 step1 s s'.
Proof.
  intros s s' H. induction H as [ s | s s' s'' He Hr IH ].
  - apply PR_refl.
  - eapply PR_step; [ | exact IH ]. apply psucc_iff. exact He.
Qed.

Lemma preach_nodes : forall s s',
  preach Node W step0 step1 s s' -> In (fst (fst s)) nodes -> In (fst (fst s')) nodes.
Proof.
  intros s s' H. induction H as [ s | s s' s'' Hs Hp IH ]; intro Hn; [ exact Hn | ].
  apply IH. inversion Hs; subst; simpl in *; eapply nodes_closed; eauto.
Qed.

Lemma preach_worlds : forall s s',
  preach Node W step0 step1 s s' -> In (snd (fst s)) worlds -> In (snd (fst s')) worlds.
Proof.
  intros s s' H. induction H as [ s | s s' s'' Hs Hp IH ]; intro Hw; [ exact Hw | ].
  apply IH. inversion Hs; subst; simpl in *; eapply worlds_closed; eauto.
Qed.

Lemma all_ps_closed : forall k s s', In s (all_ps k) -> edge PS' psucc s s' -> In s' (all_ps k).
Proof.
  intros k [[n w] b] [[n' w'] b'] Hin He.
  apply all_ps_inv in Hin. destruct Hin as [Hn [Hw Hb]].
  unfold edge in He. apply psucc_iff in He.
  inversion He; subst.
  - apply all_ps_complete;
      [ eapply nodes_closed; [ exact Hn | left; eassumption ]
      | eapply worlds_closed; [ exact Hw | left; eassumption ] | exact Hb ].
  - apply all_ps_complete;
      [ eapply nodes_closed; [ exact Hn | right; eassumption ]
      | eapply worlds_closed; [ exact Hw | right; eassumption ] | lia ].
Qed.

Theorem decide_reachb_correct :
  forall k n w, In n nodes -> In w worlds ->
    (decide_reachb k n w = true <-> reachb Node W step0 step1 Haz k n w).
Proof.
  intros k n w Hn Hw. unfold decide_reachb. split.
  - intro Hd.
    destruct (decide_sound PS' psucc (all_ps k) phazb (n, w, k) Hd) as [s' [Hr Hb]].
    apply product_correspondence. exists s'. split.
    + apply reach_to_preach. exact Hr.
    + destruct s' as [[n' w'] b']. simpl in Hb. unfold phaz, Haz. exact Hb.
  - intro Hr. apply product_correspondence in Hr. destruct Hr as [s' [Hp Hh]].
    apply (decide_complete PS' ps_dec psucc (all_ps k) phazb (n, w, k) s').
    + intros z Hz. apply reach_to_preach in Hz.
      pose proof (budget_never_increases Node W step0 step1 _ _ Hz) as Hb.
      pose proof (preach_nodes _ _ Hz Hn) as Hz'.
      pose proof (preach_worlds _ _ Hz Hw) as Hw'.
      destruct z as [[n' w'] b']. simpl in Hb, Hz', Hw'. apply all_ps_complete; assumption.
    + apply preach_to_reach. exact Hp.
    + destruct s' as [[n' w'] b']. simpl. unfold phaz, Haz in Hh. exact Hh.
Qed.

(* the executable form: the same answer, computed with a deduplicated
   frontier and early exit at the fixpoint *)
Definition decide_reachb_fast (k : nat) (n : Node) (w : W) : bool :=
  decide' PS' ps_dec psucc (all_ps k) phazb (n, w, k).

Theorem decide_reachb_fast_correct :
  forall k n w, In n nodes -> In w worlds ->
    (decide_reachb_fast k n w = true <-> reachb Node W step0 step1 Haz k n w).
Proof.
  intros k n w Hn Hw. unfold decide_reachb_fast. split.
  - intro Hd.
    destruct (decide'_sound PS' ps_dec psucc (all_ps k) phazb (n, w, k) Hd) as [s' [Hr Hb]].
    apply product_correspondence. exists s'. split.
    + apply reach_to_preach. exact Hr.
    + destruct s' as [[n' w'] b']. simpl in Hb. unfold phaz, Haz. exact Hb.
  - intro Hr. apply product_correspondence in Hr. destruct Hr as [s' [Hp Hh]].
    apply (decide'_complete PS' ps_dec psucc (all_ps k) phazb (all_ps_closed k) (n, w, k) s').
    + apply all_ps_complete; [ exact Hn | exact Hw | lia ].
    + apply preach_to_reach. exact Hp.
    + destruct s' as [[n' w'] b']. simpl. unfold phaz, Haz in Hh. exact Hh.
Qed.

End Decide.

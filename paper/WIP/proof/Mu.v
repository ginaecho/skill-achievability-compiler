(* ================================================================= *)
(*  Mu.v -- REGULAR guarded global types: recursion by mu-unfolding.  *)
(*                                                                     *)
(*  This file connects the two earlier developments.                   *)
(*    Severity.v : the finite fragment, T-Choice-Safe, exactness.      *)
(*    Regular.v  : abstract finite graphs, product, decision procedure. *)
(*  Here:                                                              *)
(*    1. mu-types with de Bruijn binders; unfolding is substitution.   *)
(*    2. The UNFOLDING CLOSURE of a closed regular type is FINITE and   *)
(*       computable (cands), and closed under every protocol step.     *)
(*    3. The finite fragment EMBEDS: reach_haz = reach_mu on the image, *)
(*       so T-Choice-Safe is exactly non-reachability in the product.  *)
(*    4. The BRIDGE for RECURSIVE sessions: a typed session of a        *)
(*       recursive protocol simulates the protocol with the same        *)
(*       misselection cost, hence is hazard-free within budget.        *)
(*    5. The decision procedure of Regular.v applies to mu-types:       *)
(*       decide_mu is sound and complete.                               *)
(*  Coq 8.18, stdlib only, axiom-free (check_mu.v).                    *)
(* ================================================================= *)
From Coq Require Import List Lia Arith PeanoNat Bool.
Import ListNotations.
Require Import Severity.
Require Import Regular.

(* reachb respects equivalent step / hazard relations *)
Lemma reachb_impl :
  forall (Node W : Type) (s0 s0' s1 s1' : Node -> W -> Node -> W -> Prop) (H H' : W -> Prop),
    (forall n w n' w', s0 n w n' w' -> s0' n w n' w') ->
    (forall n w n' w', s1 n w n' w' -> s1' n w n' w') ->
    (forall w, H w -> H' w) ->
    forall b n w, reachb Node W s0 s1 H b n w -> reachb Node W s0' s1' H' b n w.
Proof.
  intros Node W s0 s0' s1 s1' H H' I0 I1 IH b n w R.
  induction R as [ b n w Hh | b n w n' w' Hs R IHR | b n w n' w' Hs R IHR ].
  - apply RB_here. apply IH. exact Hh.
  - eapply RB_ok; [ apply I0; exact Hs | exact IHR ].
  - eapply RB_dev; [ apply I1; exact Hs | exact IHR ].
Qed.

Lemma reachb_equiv :
  forall (Node W : Type) (s0 s0' s1 s1' : Node -> W -> Node -> W -> Prop) (H H' : W -> Prop),
    (forall n w n' w', s0 n w n' w' <-> s0' n w n' w') ->
    (forall n w n' w', s1 n w n' w' <-> s1' n w n' w') ->
    (forall w, H w <-> H' w) ->
    forall b n w, reachb Node W s0 s1 H b n w <-> reachb Node W s0' s1' H' b n w.
Proof.
  intros Node W s0 s0' s1 s1' H H' I0 I1 IH b n w. split; apply reachb_impl;
    intros; first [ apply I0 | apply I1 | apply IH ]; assumption.
Qed.

Lemma reachb_mono :
  forall (Node W : Type) s0 s1 (H : W -> Prop) b b' n w,
    reachb Node W s0 s1 H b n w -> b <= b' -> reachb Node W s0 s1 H b' n w.
Proof.
  intros Node W s0 s1 H b b' n w R. revert b'.
  induction R as [ b n w Hh | b n w n' w' Hs R IHR | b n w n' w' Hs R IHR ]; intros b' Hle.
  - apply RB_here. exact Hh.
  - eapply RB_ok; [ exact Hs | apply IHR; exact Hle ].
  - destruct b' as [ | b'' ]; [ lia | ]. eapply RB_dev; [ exact Hs | apply IHR; lia ].
Qed.

(* ================================================================= *)
(*  Recursive PROCESSES (protocol-independent).                        *)
(* ================================================================= *)
Inductive Pr : Type :=
| PEnd : Pr
| POut : Role -> list (Lab * Pr) -> Pr
| PIn  : Role -> list (Lab * Pr) -> Pr
| PAct : CapN -> Pr -> Pr
| PMu  : Pr -> Pr
| PVar : nat -> Pr.

Fixpoint psubst (rho : list (option Pr)) (P : Pr) : Pr :=
  match P with
  | PEnd => PEnd
  | POut q bs => POut q (map (fun b => (fst b, psubst rho (snd b))) bs)
  | PIn q bs => PIn q (map (fun b => (fst b, psubst rho (snd b))) bs)
  | PAct a P0 => PAct a (psubst rho P0)
  | PMu P0 => PMu (psubst (None :: rho) P0)
  | PVar n => match nth n rho None with Some M => M | None => PVar n end
  end.

Definition punfold (P0 : Pr) : Pr := psubst [Some (PMu P0)] P0.

(* a process unfolds its leading mu's to a head constructor *)
Inductive unfp : Pr -> Pr -> Prop :=
| U_end : unfp PEnd PEnd
| U_out : forall q bs, unfp (POut q bs) (POut q bs)
| U_in  : forall q bs, unfp (PIn q bs) (PIn q bs)
| U_act : forall a P, unfp (PAct a P) (PAct a P)
| U_mu  : forall P0 Q, unfp (punfold P0) Q -> unfp (PMu P0) Q.

Lemma unfp_det : forall P Q1 Q2, unfp P Q1 -> unfp P Q2 -> Q1 = Q2.
Proof.
  intros P Q1 Q2 H1. revert Q2.
  induction H1; intros Q2 H2; inversion H2; subst; auto.
Qed.

Definition Ss := Role -> Pr.
Definition supd (s : Ss) (r : Role) (P : Pr) : Ss :=
  fun r' => if Nat.eq_dec r' r then P else s r'.

(* ================================================================= *)
Section MuTypes.
Variable Wd  : Type.                    (* worlds *)
Variable Gd  : Type.                    (* guard syntax *)
Variable sat : Gd -> Wd -> Prop.        (* guard satisfaction *)
Variable E   : CapN -> Wd -> Wd -> Prop.
Variable Haz : Wd -> Prop.

Inductive Gr : Type :=
| REnd  : Gr
| RComm : Role -> Role -> list (Lab * Gd * Gr) -> Gr
| RAct  : CapN -> Role -> Gr -> Gr
| RGoal : Gd -> Gr -> Gr
| RMu   : Gr -> Gr
| RVar  : nat -> Gr.

(* ---- induction principle aware of the nested branch list ---- *)
Section GrInd.
Variable P : Gr -> Prop.
Hypothesis HEnd  : P REnd.
Hypothesis HComm : forall p q brs, (forall l g Gl, In (l, g, Gl) brs -> P Gl) -> P (RComm p q brs).
Hypothesis HAct  : forall a p G, P G -> P (RAct a p G).
Hypothesis HGoal : forall g G, P G -> P (RGoal g G).
Hypothesis HMu   : forall G, P G -> P (RMu G).
Hypothesis HVar  : forall n, P (RVar n).

Fixpoint Gr_ind2 (G : Gr) : P G :=
  match G with
  | REnd => HEnd
  | RComm p q brs =>
      HComm p q brs
        ((fix F (bs : list (Lab * Gd * Gr)) : forall l g Gl, In (l, g, Gl) bs -> P Gl :=
            match bs with
            | [] => fun l g Gl H => match H return P Gl with end
            | b :: bs' => fun l g Gl H =>
                match H with
                | or_introl Heq =>
                    match Heq in (_ = y) return P (snd y) with
                    | eq_refl => Gr_ind2 (snd b)
                    end
                | or_intror H' => F bs' l g Gl H'
                end
            end) brs)
  | RAct a p G0 => HAct a p G0 (Gr_ind2 G0)
  | RGoal g G0 => HGoal g G0 (Gr_ind2 G0)
  | RMu G0 => HMu G0 (Gr_ind2 G0)
  | RVar n => HVar n
  end.
End GrInd.

(* the same principle, Type-valued, with an explicit predicate on branch lists *)
Section GrRect.
Variable P  : Gr -> Type.
Variable Pl : list (Lab * Gd * Gr) -> Type.
Hypothesis HEnd  : P REnd.
Hypothesis HComm : forall p q brs, Pl brs -> P (RComm p q brs).
Hypothesis HAct  : forall a p G, P G -> P (RAct a p G).
Hypothesis HGoal : forall g G, P G -> P (RGoal g G).
Hypothesis HMu   : forall G, P G -> P (RMu G).
Hypothesis HVar  : forall n, P (RVar n).
Hypothesis Hnil  : Pl [].
Hypothesis Hcons : forall b bs, P (snd b) -> Pl bs -> Pl (b :: bs).

Fixpoint Gr_rect_list (G : Gr) : P G :=
  match G with
  | REnd => HEnd
  | RComm p q brs =>
      HComm p q brs
        ((fix F (bs : list (Lab * Gd * Gr)) : Pl bs :=
            match bs with
            | [] => Hnil
            | b :: bs' => Hcons b bs' (Gr_rect_list (snd b)) (F bs')
            end) brs)
  | RAct a p G0 => HAct a p G0 (Gr_rect_list G0)
  | RGoal g G0 => HGoal g G0 (Gr_rect_list G0)
  | RMu G0 => HMu G0 (Gr_rect_list G0)
  | RVar n => HVar n
  end.
End GrRect.

(* ---- substitution of CLOSED terms; unfolding ---- *)
Definition Env := list (option Gr).

Fixpoint subst (rho : Env) (G : Gr) : Gr :=
  match G with
  | REnd => REnd
  | RComm p q brs =>
      RComm p q (map (fun b => (fst (fst b), snd (fst b), subst rho (snd b))) brs)
  | RAct a p G0 => RAct a p (subst rho G0)
  | RGoal g G0 => RGoal g (subst rho G0)
  | RMu G0 => RMu (subst (None :: rho) G0)
  | RVar n => match nth n rho None with Some M => M | None => RVar n end
  end.

Definition unfold_mu (G0 : Gr) : Gr := subst [Some (RMu G0)] G0.

Fixpoint closed_at (d : nat) (G : Gr) : Prop :=
  match G with
  | REnd => True
  | RComm _ _ brs => fold_right (fun b acc => closed_at d (snd b) /\ acc) True brs
  | RAct _ _ G0 => closed_at d G0
  | RGoal _ G0 => closed_at d G0
  | RMu G0 => closed_at (S d) G0
  | RVar n => n < d
  end.

Lemma closed_brs : forall d (brs : list (Lab * Gd * Gr)) l g Gl,
  fold_right (fun b acc => closed_at d (snd b) /\ acc) True brs ->
  In (l, g, Gl) brs -> closed_at d Gl.
Proof.
  induction brs as [ | b tl IH ]; simpl; intros l g Gl Hf Hin; [ contradiction | ].
  destruct Hf as [Hb Htl]. destruct Hin as [Heq | Hin].
  - subst b. simpl in Hb. exact Hb.
  - eapply IH; eauto.
Qed.

Lemma closed_comm_iff : forall d p q (brs : list (Lab * Gd * Gr)),
  closed_at d (RComm p q brs) <-> (forall l g Gl, In (l, g, Gl) brs -> closed_at d Gl).
Proof.
  intros d p q brs. simpl. split.
  - intros Hf l g Gl Hin. eapply closed_brs; eauto.
  - induction brs as [ | [[l g] Gl] tl IH ]; intro H; simpl.
    + exact I.
    + split.
      * apply (H l g Gl). left. reflexivity.
      * apply IH. intros l' g' Gl' Hin. apply (H l' g' Gl'). right. exact Hin.
Qed.

Lemma closed_mono : forall G d d', closed_at d G -> d <= d' -> closed_at d' G.
Proof.
  intros G. induction G as [ | p q brs IH | a p G0 IH | g G0 IH | G0 IH | n ] using Gr_ind2;
    intros d d' Hc Hle.
  - exact I.
  - apply closed_comm_iff. intros l g Gl Hin. eapply IH; eauto.
    eapply closed_brs; [ exact Hc | exact Hin ].
  - simpl in *. eapply IH; eauto.
  - simpl in *. eapply IH; eauto.
  - simpl in *. apply (IH (S d) (S d')); [ exact Hc | lia ].
  - simpl in *. lia.
Qed.

Fixpoint nones (k : nat) : Env := match k with 0 => [] | S k' => None :: nones k' end.

Lemma nth_nones_app : forall k n (l : Env),
  nth n (nones k ++ l) None = if n <? k then None else nth (n - k) l None.
Proof.
  induction k as [ | k IH ]; intros n l; destruct n as [ | n ]; simpl; try reflexivity.
  apply IH.
Qed.

Lemma nth_map_some : forall (ctx : list Gr) n,
  nth n (map Some ctx) None = nth_error ctx n.
Proof. induction ctx as [ | x tl IH ]; intros [ | n ]; simpl; auto. Qed.

(* substitution is the identity on closed terms *)
Lemma subst_closed : forall G d rho,
  closed_at d G -> (forall n, n < d -> nth n rho None = None) -> subst rho G = G.
Proof.
  intros G. induction G as [ | p q brs IH | a p G0 IH | g G0 IH | G0 IH | n ] using Gr_ind2;
    intros d rho Hc Hrho; simpl.
  - reflexivity.
  - f_equal. transitivity (map (fun x => x) brs); [ | apply map_id ].
    apply map_ext_in. intros [[l g] Gl] Hin. simpl. f_equal.
    eapply IH; eauto. eapply closed_brs; [ exact Hc | exact Hin ].
  - f_equal. eapply IH; eauto.
  - f_equal. eapply IH; eauto.
  - f_equal. apply (IH (S d) (None :: rho)); [ exact Hc | ].
    intros m Hm. destruct m as [ | m ]; simpl; [ reflexivity | apply Hrho; lia ].
  - simpl in Hc. rewrite (Hrho n Hc). reflexivity.
Qed.

(* the image of a substitution by closed terms *)
Lemma subst_closed_at : forall G D d rho,
  closed_at D G ->
  (forall n P, nth n rho None = Some P -> closed_at 0 P) ->
  (forall n, n < D -> nth n rho None = None -> n < d) ->
  closed_at d (subst rho G).
Proof.
  intros G. induction G as [ | p q brs IH | a p G0 IH | g G0 IH | G0 IH | n ] using Gr_ind2;
    intros D d rho Hc HS HN.
  - exact I.
  - change (closed_at d (RComm p q (map (fun b => (fst (fst b), snd (fst b), subst rho (snd b))) brs))).
    apply closed_comm_iff. intros l g Gl Hin. apply in_map_iff in Hin.
    destruct Hin as [[[l0 g0] Gl0] [Heq Hin0]]. simpl in Heq. inversion Heq; subst.
    eapply IH; eauto. eapply closed_brs; [ exact Hc | exact Hin0 ].
  - simpl in Hc. simpl. eapply IH; eauto.
  - simpl in Hc. simpl. eapply IH; eauto.
  - simpl in Hc. simpl. apply (IH (S D) (S d) (None :: rho)); [ exact Hc | | ].
    + intros m P. destruct m as [ | m ]; simpl; [ discriminate | apply HS ].
    + intros m Hm Hnone. destruct m as [ | m ]; simpl in *; [ lia | ].
      assert (m < d) by (apply HN; [ lia | exact Hnone ]). lia.
  - simpl in Hc. simpl. destruct (nth n rho None) as [P | ] eqn:Hn.
    + apply closed_mono with 0; [ eapply HS; eauto | lia ].
    + simpl. apply HN; assumption.
Qed.

(* THE UNFOLDING LEMMA: substituting the closed mu-term for the variable
   it binds, after closing the outer context, is closing the extended
   context *)
Lemma subst_comp : forall G k rho M,
  closed_at 0 M ->
  (forall n P, nth n rho None = Some P -> closed_at 0 P) ->
  subst (nones k ++ [Some M]) (subst (nones k ++ None :: rho) G)
  = subst (nones k ++ Some M :: rho) G.
Proof.
  intros G. induction G as [ | p q brs IH | a p G0 IH | g G0 IH | G0 IH | n ] using Gr_ind2;
    intros k rho M HM Hrho; simpl.
  - reflexivity.
  - f_equal. rewrite map_map. apply map_ext_in. intros [[l g] Gl] Hin. simpl. f_equal.
    eapply IH; eauto.
  - f_equal. eapply IH; eauto.
  - f_equal. eapply IH; eauto.
  - f_equal. exact (IH (S k) rho M HM Hrho).
  - rewrite nth_nones_app. destruct (n <? k) eqn:Hnk.
    + simpl. rewrite nth_nones_app. rewrite nth_nones_app. rewrite Hnk. reflexivity.
    + destruct (n - k) as [ | m ] eqn:Hm.
      * simpl. rewrite nth_nones_app. rewrite nth_nones_app. rewrite Hnk. rewrite Hm. reflexivity.
      * simpl. destruct (nth m rho None) as [P | ] eqn:HP.
        -- rewrite (subst_closed P 0); [ | eapply Hrho; eauto | intros; lia ].
           rewrite nth_nones_app. rewrite Hnk. rewrite Hm. simpl. rewrite HP. reflexivity.
        -- simpl. rewrite nth_nones_app. rewrite nth_nones_app. rewrite Hnk. rewrite Hm. simpl.
           rewrite HP. destruct m; reflexivity.
Qed.

(* ---- closing a term under a context of closed mu-terms ---- *)
Definition close (ctx : list Gr) (G : Gr) : Gr := subst (map Some ctx) G.
Definition ctx_closed (ctx : list Gr) : Prop := forall M, In M ctx -> closed_at 0 M.

Lemma close_closed : forall ctx G,
  ctx_closed ctx -> closed_at (length ctx) G -> closed_at 0 (close ctx G).
Proof.
  intros ctx G Hctx Hc. unfold close. apply subst_closed_at with (D := length ctx); [ exact Hc | | ].
  - intros n P HnP. rewrite nth_map_some in HnP. apply Hctx. eapply nth_error_In; eauto.
  - intros n Hn Hnone. rewrite nth_map_some in Hnone. apply nth_error_None in Hnone. lia.
Qed.

Lemma close_nil : forall G, closed_at 0 G -> close [] G = G.
Proof.
  intros G Hc. unfold close. simpl. apply subst_closed with 0; [ exact Hc | intros; lia ].
Qed.

Lemma unfold_close : forall ctx G0,
  ctx_closed ctx -> closed_at (S (length ctx)) G0 ->
  unfold_mu (subst (None :: map Some ctx) G0) = close (close ctx (RMu G0) :: ctx) G0.
Proof.
  intros ctx G0 Hctx Hc.
  assert (Hrho : forall n P, nth n (map Some ctx) None = Some P -> closed_at 0 P).
  { intros n P HnP. rewrite nth_map_some in HnP. apply Hctx. eapply nth_error_In; eauto. }
  assert (HM : closed_at 0 (close ctx (RMu G0))).
  { apply close_closed; [ exact Hctx | exact Hc ]. }
  pose proof (subst_comp G0 0 (map Some ctx) (close ctx (RMu G0)) HM Hrho) as Hcomp.
  simpl in Hcomp. unfold unfold_mu, close in *. simpl in *. exact Hcomp.
Qed.

(* ---- the candidate set: every closed subterm-with-context ---- *)
Fixpoint cands (ctx : list Gr) (G : Gr) : list Gr :=
  close ctx G ::
  match G with
  | RComm _ _ brs => concat (map (fun b => cands ctx (snd b)) brs)
  | RAct _ _ G0 => cands ctx G0
  | RGoal _ G0 => cands ctx G0
  | RMu G0 => cands (close ctx (RMu G0) :: ctx) G0
  | _ => []
  end.

(* ---- protocol steps on closed terms ---- *)
Inductive mstep0 : Gr -> Wd -> Gr -> Wd -> Prop :=
| M_act  : forall a p G w w', E a w w' -> mstep0 (RAct a p G) w G w'
| M_goal : forall g G w, mstep0 (RGoal g G) w G w
| M_comm_ok : forall p q brs l g Gl w,
    In (l, g, Gl) brs -> sat g w -> mstep0 (RComm p q brs) w Gl w
| M_mu   : forall G w, mstep0 (RMu G) w (unfold_mu G) w.

Inductive mstep1 : Gr -> Wd -> Gr -> Wd -> Prop :=
| M_comm_dev : forall p q brs l g Gl w,
    In (l, g, Gl) brs -> ~ sat g w -> mstep1 (RComm p q brs) w Gl w.

(* budgeted hazard reachability for regular types = the product of Regular.v *)
Definition reach_mu (b : nat) (G : Gr) (w : Wd) : Prop :=
  reachb Gr Wd mstep0 mstep1 Haz b G w.

(* ---- invariant: a state is a closed subterm-with-context whose
        candidates are all in L ---- *)
Inductive good (L : list Gr) : list Gr -> Prop :=
| good_nil : good L []
| good_cons : forall ctx G0,
    good L ctx ->
    closed_at (S (length ctx)) G0 ->
    incl (cands (close ctx (RMu G0) :: ctx) G0) L ->
    good L (close ctx (RMu G0) :: ctx).

Lemma good_closed : forall L ctx, good L ctx -> ctx_closed ctx.
Proof.
  intros L ctx H. induction H as [ | ctx G0 Hg IH Hc Hi ].
  - intros M Hin. contradiction.
  - intros M [Heq | Hin].
    + subst M. apply close_closed; [ exact IH | exact Hc ].
    + apply IH. exact Hin.
Qed.

Lemma good_in : forall L ctx M, good L ctx -> In M ctx ->
  exists ctx' G0, M = close ctx' (RMu G0) /\ good L ctx' /\
    closed_at (S (length ctx')) G0 /\ incl (cands (close ctx' (RMu G0) :: ctx') G0) L.
Proof.
  intros L ctx M H. induction H as [ | ctx G0 Hg IH Hc Hi ]; intro Hin.
  - contradiction.
  - destruct Hin as [Heq | Hin].
    + subst M. exists ctx, G0. auto.
    + apply IH. exact Hin.
Qed.

Definition okst (L : list Gr) (X : Gr) : Prop :=
  exists ctx G, X = close ctx G /\ good L ctx /\ closed_at (length ctx) G /\ incl (cands ctx G) L.

Lemma cands_head : forall ctx G, In (close ctx G) (cands ctx G).
Proof. intros ctx G. destruct G; left; reflexivity. Qed.

Lemma okst_in : forall L X, okst L X -> In X L.
Proof.
  intros L X [ctx [G [Hx [_ [_ Hi]]]]]. subst X. apply Hi. apply cands_head.
Qed.

(* a state is never a bare variable: it is the closure of its binder *)
Lemma okst_head : forall L X, okst L X ->
  exists ctx G, X = close ctx G /\ good L ctx /\ closed_at (length ctx) G /\
    incl (cands ctx G) L /\ (forall n, G <> RVar n).
Proof.
  intros L X [ctx [G [Hx [Hg [Hc Hi]]]]].
  destruct G as [ | p q brs | a p G0 | g G0 | G0 | n ];
    try (exists ctx; eexists; repeat split; try eassumption; discriminate).
  simpl in Hc.
  assert (Hn : exists M, nth_error ctx n = Some M).
  { destruct (nth_error ctx n) eqn:Hn; [ eexists; reflexivity | apply nth_error_None in Hn; lia ]. }
  destruct Hn as [M Hn].
  assert (HxM : close ctx (RVar n) = M).
  { unfold close. simpl. rewrite nth_map_some, Hn. reflexivity. }
  subst X.
  destruct (good_in L ctx M Hg (nth_error_In _ _ Hn)) as [ctx' [G0 [HM [Hg' [Hc' Hi']]]]].
  exists ctx', (RMu G0). repeat split.
  - rewrite HxM. exact HM.
  - exact Hg'.
  - exact Hc'.
  - intros z Hz. simpl in Hz. destruct Hz as [Hz | Hz].
    + subst z. rewrite <- HM, <- HxM. apply Hi. apply cands_head.
    + apply Hi'. exact Hz.
  - discriminate.
Qed.

(* THE CLOSURE THEOREM: every protocol step stays in the candidate set *)
Lemma okst_branch : forall L ctx p q brs l g Gl0,
  good L ctx -> closed_at (length ctx) (RComm p q brs) -> incl (cands ctx (RComm p q brs)) L ->
  In (l, g, Gl0) brs -> okst L (close ctx Gl0).
Proof.
  intros L ctx p q brs l g Gl0 Hg Hc Hi Hin0. simpl in Hc.
  exists ctx, Gl0. split; [ reflexivity | split; [ exact Hg | split ] ].
  - eapply closed_brs; [ exact Hc | exact Hin0 ].
  - intros z Hz. apply Hi. simpl. right. apply in_concat. exists (cands ctx Gl0).
    split; [ | exact Hz ]. apply in_map_iff. exists (l, g, Gl0). split; [ reflexivity | exact Hin0 ].
Qed.

Lemma okst_step : forall L X w Y w',
  okst L X -> (mstep0 X w Y w' \/ mstep1 X w Y w') -> okst L Y.
Proof.
  intros L X w Y w' Hok Hs.
  apply okst_head in Hok. destruct Hok as [ctx [G [Hx [Hg [Hc [Hi Hnv]]]]]]. subst X.
  destruct G as [ | p q brs | a p G0 | g G0 | G0 | n ]; unfold close in Hs; simpl in Hs.
  - destruct Hs as [Hs | Hs]; inversion Hs.
  - assert (Hbr : forall l g Gl',
              In (l, g, Gl') (map (fun b => (fst (fst b), snd (fst b), subst (map Some ctx) (snd b))) brs) ->
              exists Gl0, In (l, g, Gl0) brs /\ Gl' = close ctx Gl0).
    { intros l g Gl' Hin. apply in_map_iff in Hin. destruct Hin as [[[l0 g0] Gl0] [Heq Hin0]].
      simpl in Heq. inversion Heq; subst. exists Gl0. split; [ exact Hin0 | reflexivity ]. }
    destruct Hs as [Hs | Hs]; inversion Hs; subst;
      match goal with
      | [ H : In (?l, ?g, Y) (map _ brs) |- _ ] =>
          destruct (Hbr l g Y H) as [Gl0 [Hin0 HY]]; subst Y;
          eapply okst_branch; [ exact Hg | exact Hc | exact Hi | exact Hin0 ]
      end.
  - destruct Hs as [Hs | Hs]; inversion Hs; subst.
    exists ctx, G0. split; [ reflexivity | split; [ exact Hg | split; [ exact Hc | ] ] ].
    intros z Hz. apply Hi. simpl. right. exact Hz.
  - destruct Hs as [Hs | Hs]; inversion Hs; subst.
    exists ctx, G0. split; [ reflexivity | split; [ exact Hg | split; [ exact Hc | ] ] ].
    intros z Hz. apply Hi. simpl. right. exact Hz.
  - destruct Hs as [Hs | Hs]; inversion Hs; subst.
    rewrite unfold_close; [ | eapply good_closed; exact Hg | exact Hc ].
    exists (close ctx (RMu G0) :: ctx), G0. split; [ reflexivity | split; [ | split ] ].
    + apply good_cons; [ exact Hg | exact Hc | ]. intros z Hz. apply Hi. simpl. right. exact Hz.
    + simpl. exact Hc.
    + intros z Hz. apply Hi. simpl. right. exact Hz.
  - exfalso. apply (Hnv n). reflexivity.
Qed.

Lemma okst_preach : forall L X w b s',
  okst L X -> preach Gr Wd mstep0 mstep1 (X, w, b) s' -> okst L (fst (fst s')).
Proof.
  intros L X w b s' Hok Hp.
  remember (X, w, b) as s eqn:Es. revert X w b Hok Es.
  induction Hp as [ s | s s' s'' Hs Hp IH ]; intros X w b Hok Es; subst.
  - simpl. exact Hok.
  - inversion Hs; subst.
    + eapply IH; [ eapply okst_step; [ exact Hok | left; eassumption ] | reflexivity ].
    + eapply IH; [ eapply okst_step; [ exact Hok | right; eassumption ] | reflexivity ].
Qed.

(* every candidate is a well-formed state, hence the list is step-closed *)
Lemma cands_all_okst : forall G ctx L,
  good L ctx -> closed_at (length ctx) G -> incl (cands ctx G) L ->
  forall X, In X (cands ctx G) -> okst L X.
Proof.
  intros G. induction G as [ | p q brs IH | a p G0 IH | g G0 IH | G0 IH | n ] using Gr_ind2;
    intros ctx L Hg Hc Hi X Hin; simpl in Hin; destruct Hin as [Hx | Hin];
    try (subst X; exists ctx; eexists; repeat split; eassumption); try contradiction.
  - apply in_concat in Hin. destruct Hin as [l' [Hl' Hin]]. apply in_map_iff in Hl'.
    destruct Hl' as [[[l g] Gl] [Heq Hb]]. subst l'. simpl in Hin.
    eapply IH; [ exact Hb | exact Hg | eapply closed_brs; [ exact Hc | exact Hb ] | | exact Hin ].
    intros z Hz. apply Hi. right. apply in_concat. exists (cands ctx Gl). split; [ | exact Hz ].
    apply in_map_iff. exists (l, g, Gl). split; [ reflexivity | exact Hb ].
  - eapply IH; [ exact Hg | exact Hc | | exact Hin ]. intros z Hz. apply Hi. right. exact Hz.
  - eapply IH; [ exact Hg | exact Hc | | exact Hin ]. intros z Hz. apply Hi. right. exact Hz.
  - eapply IH; [ | | | exact Hin ].
    + apply good_cons; [ exact Hg | exact Hc | ]. intros z Hz. apply Hi. right. exact Hz.
    + simpl. exact Hc.
    + intros z Hz. apply Hi. right. exact Hz.
Qed.

Theorem cands_closed : forall G0,
  closed_at 0 G0 ->
  forall X w Y w', In X (cands [] G0) -> (mstep0 X w Y w' \/ mstep1 X w Y w') -> In Y (cands [] G0).
Proof.
  intros G0 Hc X w Y w' Hin Hs.
  apply okst_in. eapply okst_step; [ | exact Hs ].
  eapply cands_all_okst; [ apply good_nil | exact Hc | apply incl_refl | exact Hin ].
Qed.

Theorem reach_in_cands : forall G0 w b s',
  closed_at 0 G0 ->
  preach Gr Wd mstep0 mstep1 (G0, w, b) s' -> In (fst (fst s')) (cands [] G0).
Proof.
  intros G0 w b s' Hc Hp. apply okst_in. eapply okst_preach; [ | exact Hp ].
  exists [], G0. repeat split; [ symmetry; apply close_nil; exact Hc | apply good_nil | exact Hc | apply incl_refl ].
Qed.

(* ================================================================= *)
(*  THE BRIDGE for recursive sessions.                                 *)
(* ================================================================= *)
CoInductive ctypes : Gr -> Ss -> Wd -> Prop :=
| CT_End : forall s w,
    (forall r, unfp (s r) PEnd) -> ctypes REnd s w
| CT_Goal : forall g G s w,
    sat g w -> ctypes G s w -> ctypes (RGoal g G) s w
| CT_Act : forall a p G s w P,
    unfp (s p) (PAct a P) ->
    (exists w', E a w w') ->
    (forall w', E a w w' -> ctypes G (supd s p P) w') ->
    ctypes (RAct a p G) s w
| CT_Comm : forall p q brs s w sendb recvb,
    p <> q ->
    unfp (s p) (POut q sendb) ->
    unfp (s q) (PIn p recvb) ->
    brs <> nil ->
    (forall l g Gl, In (l, g, Gl) brs -> exists P, In (l, P) sendb) ->
    (forall l P, In (l, P) sendb -> exists g Gl, In (l, g, Gl) brs) ->
    (forall l g Gl, In (l, g, Gl) brs -> exists Q, In (l, Q) recvb) ->
    (forall l g Gl P Q,
        In (l, g, Gl) brs -> In (l, P) sendb -> In (l, Q) recvb ->
        ctypes Gl (supd (supd s p P) q Q) w) ->
    ctypes (RComm p q brs) s w
| CT_Mu : forall G s w,
    ctypes (unfold_mu G) s w -> ctypes (RMu G) s w.

Inductive hstep : Gr -> Ss -> Wd -> Gr -> Ss -> Wd -> Role -> nat -> Prop :=
| H_Act : forall a p G s w w' P,
    unfp (s p) (PAct a P) -> E a w w' ->
    hstep (RAct a p G) s w G (supd s p P) w' p 0
| H_Goal : forall g G s w G' s' w' r c,
    hstep G s w G' s' w' r c -> hstep (RGoal g G) s w G' s' w' r c
| H_Comm_ok : forall p q brs s w sendb recvb l g Gl P Q,
    unfp (s p) (POut q sendb) -> unfp (s q) (PIn p recvb) ->
    In (l, g, Gl) brs -> In (l, P) sendb -> In (l, Q) recvb ->
    sat g w ->
    hstep (RComm p q brs) s w Gl (supd (supd s p P) q Q) w p 0
| H_Comm_dev : forall p q brs s w sendb recvb l g Gl P Q,
    unfp (s p) (POut q sendb) -> unfp (s q) (PIn p recvb) ->
    In (l, g, Gl) brs -> In (l, P) sendb -> In (l, Q) recvb ->
    ~ sat g w ->
    hstep (RComm p q brs) s w Gl (supd (supd s p P) q Q) w p 1
| H_Mu : forall G s w G' s' w' r c,
    hstep (unfold_mu G) s w G' s' w' r c -> hstep (RMu G) s w G' s' w' r c.

Inductive hrun : Gr -> Ss -> Wd -> list (Role * nat) -> Gr -> Ss -> Wd -> Prop :=
| HR_refl : forall G s w, hrun G s w [] G s w
| HR_step : forall G s w G1 s1 w1 r c tr G' s' w',
    hstep G s w G1 s1 w1 r c -> hrun G1 s1 w1 tr G' s' w' ->
    hrun G s w ((r, c) :: tr) G' s' w'.

Definition total (tr : list (Role * nat)) : nat := fold_right (fun rc acc => snd rc + acc) 0 tr.

(* protocol paths with a misselection count *)
Inductive msteps : nat -> Gr -> Wd -> Gr -> Wd -> Prop :=
| MS_refl : forall G w, msteps 0 G w G w
| MS_ok : forall c G w G1 w1 G' w',
    mstep0 G w G1 w1 -> msteps c G1 w1 G' w' -> msteps c G w G' w'
| MS_dev : forall c G w G1 w1 G' w',
    mstep1 G w G1 w1 -> msteps c G1 w1 G' w' -> msteps (S c) G w G' w'.

Lemma msteps_trans : forall c1 G w G1 w1 c2 G' w',
  msteps c1 G w G1 w1 -> msteps c2 G1 w1 G' w' -> msteps (c1 + c2) G w G' w'.
Proof.
  intros c1 G w G1 w1 c2 G' w' H1. revert c2 G' w'.
  induction H1 as [ | c G w G0 w0 G1 w1 Hs H1 IH | c G w G0 w0 G1 w1 Hs H1 IH ];
    intros c2 G' w' H2; simpl.
  - exact H2.
  - eapply MS_ok; [ exact Hs | apply IH; exact H2 ].
  - eapply MS_dev; [ exact Hs | apply IH; exact H2 ].
Qed.

Lemma msteps_reach : forall c G w G' w',
  msteps c G w G' w' -> Haz w' -> reach_mu c G w.
Proof.
  intros c G w G' w' H. unfold reach_mu.
  induction H as [ | c G w G0 w0 G1 w1 Hs H IH | c G w G0 w0 G1 w1 Hs H IH ]; intro Hh.
  - apply RB_here. exact Hh.
  - eapply RB_ok; [ exact Hs | apply IH; exact Hh ].
  - eapply RB_dev; [ exact Hs | apply IH; exact Hh ].
Qed.

(* one instrumented session step is a protocol path of the same cost,
   and typing is preserved *)
Lemma sim_step : forall G s w G' s' w' r c,
  hstep G s w G' s' w' r c -> ctypes G s w ->
  msteps c G w G' w' /\ ctypes G' s' w'.
Proof.
  intros G s w G' s' w' r c Hs.
  induction Hs as [ a p G s w w' P Hu HE
                  | g G s w G' s' w' r c Hs IH
                  | p q brs s w sendb recvb l g Gl P Q Hup Huq Hin HinP HinQ Hsat
                  | p q brs s w sendb recvb l g Gl P Q Hup Huq Hin HinP HinQ Hns
                  | G s w G' s' w' r c Hs IH ]; intro Ht.
  - inversion Ht as [ | | a0 p0 G0 s0 w0 P0 Hu0 Hex Hcont | | ]; subst.
    pose proof (unfp_det _ _ _ Hu Hu0) as Hd. inversion Hd; subst.
    split; [ eapply MS_ok; [ apply M_act; exact HE | apply MS_refl ] | apply Hcont; exact HE ].
  - inversion Ht as [ | g0 G0 s0 w0 Hsat Ht0 | | | ]; subst.
    destruct (IH Ht0) as [Hm Ht']. split; [ eapply MS_ok; [ apply M_goal | exact Hm ] | exact Ht' ].
  - inversion Ht as [ | | | p0 q0 brs0 s0 w0 sb rb Hpq Hup0 Huq0 Hne H1 H2 H3 Hcont | ]; subst.
    pose proof (unfp_det _ _ _ Hup Hup0) as Hd1. inversion Hd1; subst.
    pose proof (unfp_det _ _ _ Huq Huq0) as Hd2. inversion Hd2; subst.
    split; [ eapply MS_ok; [ eapply M_comm_ok; [ exact Hin | exact Hsat ] | apply MS_refl ]
           | eapply Hcont; eassumption ].
  - inversion Ht as [ | | | p0 q0 brs0 s0 w0 sb rb Hpq Hup0 Huq0 Hne H1 H2 H3 Hcont | ]; subst.
    pose proof (unfp_det _ _ _ Hup Hup0) as Hd1. inversion Hd1; subst.
    pose proof (unfp_det _ _ _ Huq Huq0) as Hd2. inversion Hd2; subst.
    split; [ eapply MS_dev; [ eapply M_comm_dev; [ exact Hin | exact Hns ] | apply MS_refl ]
           | eapply Hcont; eassumption ].
  - inversion Ht as [ | | | | G0 s0 w0 Ht0 ]; subst.
    destruct (IH Ht0) as [Hm Ht']. split; [ eapply MS_ok; [ apply M_mu | exact Hm ] | exact Ht' ].
Qed.

Lemma sim_run : forall G s w tr G' s' w',
  hrun G s w tr G' s' w' -> ctypes G s w ->
  msteps (total tr) G w G' w' /\ ctypes G' s' w'.
Proof.
  intros G s w tr G' s' w' H. induction H as [ | G s w G1 s1 w1 r c tr G' s' w' Hs Hr IH ]; intro Ht.
  - split; [ apply MS_refl | exact Ht ].
  - destruct (sim_step _ _ _ _ _ _ _ _ Hs Ht) as [Hm1 Ht1].
    destruct (IH Ht1) as [Hm2 Ht2]. split; [ | exact Ht2 ].
    simpl. eapply msteps_trans; eauto.
Qed.

(* THE BRIDGE, recursive: a session typed against a protocol on which no
   hazard is reachable within budget b is hazard-free on every run whose
   misselection cost is at most b *)
Theorem bridge_mu : forall b G s w tr G' s' w',
  ctypes G s w -> ~ reach_mu b G w ->
  hrun G s w tr G' s' w' -> total tr <= b -> ~ Haz w'.
Proof.
  intros b G s w tr G' s' w' Ht Hnr Hr Hle Hh.
  destruct (sim_run _ _ _ _ _ _ _ Hr Ht) as [Hm _].
  apply Hnr. eapply reachb_mono; [ eapply msteps_reach; eauto | exact Hle ].
Qed.

(* ================================================================= *)
(*  DECIDABILITY for mu-types.                                        *)
(* ================================================================= *)
Section MuDecide.
Hypothesis Wd_dec : forall x y : Wd, {x = y} + {x <> y}.
Hypothesis Gd_dec : forall x y : Gd, {x = y} + {x <> y}.
Variable worlds : list Wd.
Hypothesis worlds_closed : forall a w w', In w worlds -> E a w w' -> In w' worlds.
Variable satb : Gd -> Wd -> bool.  Hypothesis sat_spec : forall g w, sat g w <-> satb g w = true.
Variable succE : CapN -> Wd -> list Wd.  Hypothesis E_spec : forall a w w', E a w w' <-> In w' (succE a w).
Variable hazb : Wd -> bool.  Hypothesis haz_spec : forall w, Haz w <-> hazb w = true.

Lemma Gr_eq_dec : forall G1 G2 : Gr, {G1 = G2} + {G1 <> G2}.
Proof.
  apply (Gr_rect_list (fun G => forall G2, {G = G2} + {G <> G2})
                      (fun brs => forall brs', {brs = brs'} + {brs <> brs'})).
  - intros [ | | | | | ]; try (right; discriminate). left; reflexivity.
  - intros p q brs Hl [ | p' q' brs' | | | | ]; try (right; discriminate).
    destruct (Nat.eq_dec p p') as [-> | Hp]; [ | right; intro C; inversion C; contradiction ].
    destruct (Nat.eq_dec q q') as [-> | Hq]; [ | right; intro C; inversion C; contradiction ].
    destruct (Hl brs') as [-> | Hb]; [ left; reflexivity | right; intro C; inversion C; contradiction ].
  - intros a p G IH [ | | a' p' G' | | | ]; try (right; discriminate).
    destruct (Nat.eq_dec a a') as [-> | Ha]; [ | right; intro C; inversion C; contradiction ].
    destruct (Nat.eq_dec p p') as [-> | Hp]; [ | right; intro C; inversion C; contradiction ].
    destruct (IH G') as [-> | HG]; [ left; reflexivity | right; intro C; inversion C; contradiction ].
  - intros g G IH [ | | | g' G' | | ]; try (right; discriminate).
    destruct (Gd_dec g g') as [-> | Hg]; [ | right; intro C; inversion C; contradiction ].
    destruct (IH G') as [-> | HG]; [ left; reflexivity | right; intro C; inversion C; contradiction ].
  - intros G IH [ | | | | G' | ]; try (right; discriminate).
    destruct (IH G') as [-> | HG]; [ left; reflexivity | right; intro C; inversion C; contradiction ].
  - intros n [ | | | | | n' ]; try (right; discriminate).
    destruct (Nat.eq_dec n n') as [-> | Hn]; [ left; reflexivity | right; intro C; inversion C; contradiction ].
  - intros [ | b' bs' ]; [ left; reflexivity | right; discriminate ].
  - intros [[l g] Gl] bs Hb Hbs [ | [[l' g'] Gl'] bs' ]; [ right; discriminate | ].
    simpl in Hb.
    destruct (Nat.eq_dec l l') as [-> | Hl]; [ | right; intro C; inversion C; contradiction ].
    destruct (Gd_dec g g') as [-> | Hg]; [ | right; intro C; inversion C; contradiction ].
    destruct (Hb Gl') as [-> | HG]; [ | right; intro C; inversion C; contradiction ].
    destruct (Hbs bs') as [-> | Ht]; [ left; reflexivity | right; intro C; inversion C; contradiction ].
Defined.

Definition succ0 (G : Gr) (w : Wd) : list (Gr * Wd) :=
  match G with
  | RAct a _ G0 => map (fun w' => (G0, w')) (succE a w)
  | RGoal _ G0 => [(G0, w)]
  | RComm _ _ brs => map (fun b => (snd b, w)) (filter (fun b => satb (snd (fst b)) w) brs)
  | RMu G0 => [(unfold_mu G0, w)]
  | _ => []
  end.

Definition succ1 (G : Gr) (w : Wd) : list (Gr * Wd) :=
  match G with
  | RComm _ _ brs => map (fun b => (snd b, w)) (filter (fun b => negb (satb (snd (fst b)) w)) brs)
  | _ => []
  end.

Lemma succ0_iff : forall G w G' w', In (G', w') (succ0 G w) <-> mstep0 G w G' w'.
Proof.
  intros G w G' w'. destruct G as [ | p q brs | a p G0 | g G0 | G0 | n ]; simpl; split; intro H;
    try contradiction; try (inversion H; fail).
  - apply in_map_iff in H. destruct H as [[[l g] Gl] [Heq Hin]]. simpl in Heq. inversion Heq; subst.
    apply filter_In in Hin. destruct Hin as [Hin Hb]. simpl in Hb.
    eapply M_comm_ok; [ exact Hin | apply sat_spec; exact Hb ].
  - inversion H as [ | | p0 q0 brs0 l g Gl w0 Hin Hsat | ]; subst.
    apply in_map_iff. exists (l, g, G'). split; [ reflexivity | ].
    apply filter_In. split; [ exact Hin | simpl; apply sat_spec; exact Hsat ].
  - apply in_map_iff in H. destruct H as [w0 [Heq Hin]]. inversion Heq; subst.
    apply M_act. apply E_spec. exact Hin.
  - inversion H; subst. apply in_map_iff. exists w'. split; [ reflexivity | apply E_spec; assumption ].
  - destruct H as [Heq | []]. inversion Heq; subst. apply M_goal.
  - inversion H; subst. left. reflexivity.
  - destruct H as [Heq | []]. inversion Heq; subst. apply M_mu.
  - inversion H; subst. left. reflexivity.
Qed.

Lemma succ1_iff : forall G w G' w', In (G', w') (succ1 G w) <-> mstep1 G w G' w'.
Proof.
  intros G w G' w'. destruct G as [ | p q brs | a p G0 | g G0 | G0 | n ]; simpl; split; intro H;
    try contradiction; try (inversion H; fail).
  - apply in_map_iff in H. destruct H as [[[l g] Gl] [Heq Hin]]. simpl in Heq. inversion Heq; subst.
    apply filter_In in Hin. destruct Hin as [Hin Hb]. simpl in Hb. apply negb_true_iff in Hb.
    eapply M_comm_dev; [ exact Hin | ]. intro Hs. apply sat_spec in Hs. congruence.
  - inversion H as [ p0 q0 brs0 l g Gl w0 Hin Hns ]; subst.
    apply in_map_iff. exists (l, g, G'). split; [ reflexivity | ].
    apply filter_In. split; [ exact Hin | simpl ]. apply negb_true_iff.
    destruct (satb g w') eqn:Hb; [ exfalso; apply Hns; apply sat_spec; exact Hb | reflexivity ].
Qed.

Definition decide_mu (k : nat) (G0 : Gr) (w : Wd) : bool :=
  decide_reachb_fast Gr Wd Gr_eq_dec Wd_dec (cands [] G0) worlds succ0 succ1 hazb k G0 w.

Lemma mstep_worlds : forall n w n' w',
  In w worlds -> (mstep0 n w n' w' \/ mstep1 n w n' w') -> In w' worlds.
Proof.
  intros n w n' w' Hw [Hs | Hs]; inversion Hs; subst; try exact Hw.
  eapply worlds_closed; eauto.
Qed.

Theorem decide_mu_correct : forall k G0 w,
  closed_at 0 G0 -> In w worlds -> (decide_mu k G0 w = true <-> reach_mu k G0 w).
Proof.
  intros k G0 w Hc Hw. unfold decide_mu.
  assert (Hwclosed : forall n w0 n' w0', In w0 worlds ->
            (step0 Gr Wd succ0 n w0 n' w0' \/ step1 Gr Wd succ1 n w0 n' w0') -> In w0' worlds).
  { intros n w0 n' w0' Hin Hs. eapply mstep_worlds; [ exact Hin | ].
    destruct Hs as [Hs | Hs]; [ left; apply succ0_iff; exact Hs | right; apply succ1_iff; exact Hs ]. }
  assert (Hclosed : forall n w0 n' w0', In n (cands [] G0) ->
            (step0 Gr Wd succ0 n w0 n' w0' \/ step1 Gr Wd succ1 n w0 n' w0') -> In n' (cands [] G0)).
  { intros n w0 n' w0' Hin Hs. eapply cands_closed; [ exact Hc | exact Hin | ].
    destruct Hs as [Hs | Hs]; [ left; apply succ0_iff; exact Hs | right; apply succ1_iff; exact Hs ]. }
  assert (Hstart : In G0 (cands [] G0)).
  { rewrite <- (close_nil G0 Hc) at 1. apply cands_head. }
  rewrite (decide_reachb_fast_correct Gr Wd Gr_eq_dec Wd_dec (cands [] G0) worlds
             succ0 succ1 hazb Hclosed Hwclosed k G0 w Hstart Hw).
  unfold reach_mu. apply reachb_equiv.
  - intros; unfold step0; apply succ0_iff.
  - intros; unfold step1; apply succ1_iff.
  - intro w0. unfold Regular.Haz. symmetry. apply haz_spec.
Qed.

End MuDecide.
End MuTypes.

(* ================================================================= *)
(*  EMBEDDING the finite fragment of Severity.v.                        *)
(* ================================================================= *)
Section Embed.
Definition GdW := World -> Prop.
Definition satW (g : GdW) (W : World) : Prop := g W.

Fixpoint emb (G : Gt) : Gr GdW :=
  match G with
  | GEnd => REnd GdW
  | GComm p q brs => RComm GdW p q (map (fun b => (fst (fst b), snd (fst b), emb (snd b))) brs)
  | GAct a p G0 => RAct GdW a p (emb G0)
  | GGoal phi G0 => RGoal GdW phi (emb G0)
  end.

Variable E : Ctx.
Variable Haz : World -> Prop.

Theorem reach_embed : forall b G W,
  reach_haz E Haz b G W <-> reach_mu World GdW satW E Haz b (emb G) W.
Proof.
  intros b G W. unfold reach_mu. split.
  - intro H. induction H as [ b G W Hh | b a p G W W' HE H IH | b phi G W H IH
                            | b p q brs l psi Gl W Hin Hpsi H IH
                            | b p q brs l psi Gl W Hin Hpsi H IH ]; simpl.
    + apply RB_here. exact Hh.
    + eapply RB_ok; [ apply M_act; exact HE | exact IH ].
    + eapply RB_ok; [ apply M_goal | exact IH ].
    + eapply RB_ok; [ | exact IH ]. eapply M_comm_ok; [ | exact Hpsi ].
      apply in_map_iff. exists (l, psi, Gl). split; [ reflexivity | exact Hin ].
    + eapply RB_dev; [ | exact IH ]. eapply M_comm_dev; [ | exact Hpsi ].
      apply in_map_iff. exists (l, psi, Gl). split; [ reflexivity | exact Hin ].
  - intro H. remember (emb G) as X eqn:EX. revert G EX.
    induction H as [ b X W Hh | b X W X' W' Hs H IH | b X W X' W' Hs H IH ]; intros G EX; subst.
    + apply RH_here. exact Hh.
    + destruct G as [ | p q brs | a p G0 | phi G0 ]; simpl in Hs; inversion Hs; subst.
      * match goal with
        | [ Hin : In (?l, ?g, X') (map _ brs) |- _ ] =>
            apply in_map_iff in Hin; destruct Hin as [[[l0 g0] Gl0] [Heq Hin0]];
            simpl in Heq; inversion Heq; subst
        end.
        eapply RH_comm_ok; [ exact Hin0 | assumption | apply IH; reflexivity ].
      * eapply RH_act; [ eassumption | apply IH; reflexivity ].
      * apply RH_goal. apply IH. reflexivity.
    + destruct G as [ | p q brs | a p G0 | phi G0 ]; simpl in Hs; inversion Hs; subst.
      match goal with
      | [ Hin : In (?l, ?g, X') (map _ brs) |- _ ] =>
          apply in_map_iff in Hin; destruct Hin as [[[l0 g0] Gl0] [Heq Hin0]];
          simpl in Heq; inversion Heq; subst
      end.
      eapply RH_comm_dev; [ exact Hin0 | assumption | apply IH; reflexivity ].
Qed.

(* T-Choice-Safe on the finite fragment IS non-reachability in the
   product graph of its embedding *)
Theorem TC_regular : forall b G W,
  safeT E Haz b G W <-> ~ reach_mu World GdW satW E Haz b (emb G) W.
Proof.
  intros b G W. rewrite <- reach_embed. apply TC_exact.
Qed.

(* the finite-fragment bridge, recovered through the recursive one *)
Theorem bridge_finite_via_mu : forall b G s W tr G' s' W',
  safeT E Haz b G W ->
  ctypes World GdW satW E (emb G) s W ->
  hrun World GdW satW E (emb G) s W tr G' s' W' -> total tr <= b -> ~ Haz W'.
Proof.
  intros b G s W tr G' s' W' Hs Ht Hr Hle.
  eapply bridge_mu; [ exact Ht | apply TC_regular; exact Hs | exact Hr | exact Hle ].
Qed.

End Embed.

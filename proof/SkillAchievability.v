(* ============================================================= *)
(*  SkillAchievability.v                                          *)
(*  Mechanized soundness core for the Skill Achievability        *)
(*  Compiler (Layer A).                                          *)
(*                                                               *)
(*  What is proved here (Coq 8.18, no external libraries):       *)
(*                                                               *)
(*   T0  reach_trans   : reachability is transitive.             *)
(*   L1  reach_abs     : a sound abstraction transports          *)
(*                       concrete reachability to the abstract   *)
(*                       transition system.                      *)
(*   T1  refutation_sound :                                      *)
(*         if the ABSTRACT system cannot reach any goal state,   *)
(*         then NO concrete run reaches the goal.                *)
(*         (=> the checker never emits a false "IMPOSSIBLE".)    *)
(*   T2  tolerance_sound :                                       *)
(*         refutation under a COARSER over-approximation         *)
(*         transfers to every finer system. (=> making the       *)
(*         abstraction more tolerant keeps refutation sound.)    *)
(*   T3  cap_monotone  :                                         *)
(*         adding capabilities can only enlarge the reachable    *)
(*         set; it never turns ACHIEVABLE into IMPOSSIBLE.       *)
(*                                                               *)
(*   FlightInstance : a concrete non-vacuity model proving that  *)
(*         the missing-email-capability spec (the hallucinated-  *)
(*         planning failure) is genuinely refuted -- there is    *)
(*         provably no run reaching  booked /\ confirmation.     *)
(* ============================================================= *)

(* ---------- Generic reachability (reflexive-transitive closure) ---------- *)

Section Reachability.
  Context {St : Type}.
  Variable step : St -> St -> Prop.

  Inductive reach (s : St) : St -> Prop :=
  | reach_refl : reach s s
  | reach_step : forall u v, reach s u -> step u v -> reach s v.

  Lemma reach_one : forall s v, step s v -> reach s v.
  Proof. intros s v H. eapply reach_step. apply reach_refl. exact H. Qed.

  Lemma reach_trans : forall s u v, reach s u -> reach u v -> reach s v.
  Proof.
    intros s u v Hsu Huv. induction Huv as [| x y Hux IH Hxy].
    - exact Hsu.
    - eapply reach_step. apply IH. exact Hxy.
  Qed.
End Reachability.

(* ---------- Monotonicity of reachability in the step relation ---------- *)

Lemma reach_mono {St : Type} (step1 step2 : St -> St -> Prop) :
  (forall x y, step1 x y -> step2 x y) ->
  forall s w, reach step1 s w -> reach step2 s w.
Proof.
  intros Hsub s w H. induction H as [| u v Hsu IH Huv].
  - apply reach_refl.
  - eapply reach_step. apply IH. apply Hsub. exact Huv.
Qed.

(* ============================================================= *)
(*  T1  Refutation soundness via a sound abstraction             *)
(* ============================================================= *)

Section Soundness.
  Context {W A : Type}.
  Variable cstep : W -> W -> Prop.   (* concrete transition system *)
  Variable astep : A -> A -> Prop.   (* abstract system the checker explores *)
  Variable abs   : W -> A.           (* abstraction function *)
  Variable cgoal : W -> Prop.        (* concrete goal *)
  Variable agoal : A -> Prop.        (* abstract goal *)

  (* The two obligations that make the abstraction SOUND. *)
  Hypothesis step_sim : forall w w', cstep w w' -> astep (abs w) (abs w').
  Hypothesis goal_sim : forall w, cgoal w -> agoal (abs w).

  (* L1: abstraction transports reachability. *)
  Lemma reach_abs :
    forall s0 w, reach cstep s0 w -> reach astep (abs s0) (abs w).
  Proof.
    intros s0 w H. induction H as [| u v Hsu IH Huv].
    - apply reach_refl.
    - eapply reach_step. apply IH. apply step_sim. exact Huv.
  Qed.

  (* T1: if the abstract system has no reachable goal, neither does the
         concrete one.  This is THE guarantee: a "REFUTED" verdict from
         the checker is never wrong. *)
  Theorem refutation_sound :
    forall s0,
      (~ exists a, reach astep (abs s0) a /\ agoal a) ->
      (~ exists w, reach cstep s0 w /\ cgoal w).
  Proof.
    intros s0 Hno [w [Hreach Hgoal]].
    apply Hno. exists (abs w). split.
    - apply reach_abs. exact Hreach.
    - apply goal_sim. exact Hgoal.
  Qed.
End Soundness.

(* ============================================================= *)
(*  T2  Tolerance soundness                                       *)
(*  A coarser (more permissive) over-approximation that still     *)
(*  cannot reach the goal refutes every finer system.            *)
(* ============================================================= *)

Section Tolerance.
  Context {A : Type}.
  Variables fine coarse : A -> A -> Prop.
  Hypothesis over : forall x y, fine x y -> coarse x y.
  Variable agoal : A -> Prop.

  Theorem tolerance_sound :
    forall s0,
      (~ exists a, reach coarse s0 a /\ agoal a) ->
      (~ exists a, reach fine s0 a /\ agoal a).
  Proof.
    intros s0 Hno [a [Hreach Hgoal]].
    apply Hno. exists a. split.
    - apply (reach_mono fine coarse over). exact Hreach.
    - exact Hgoal.
  Qed.
End Tolerance.

(* ============================================================= *)
(*  T3  Capability monotonicity                                   *)
(*  Enlarging the available steps (granting more tools) can only  *)
(*  grow the reachable set: more capabilities never make an       *)
(*  achievable goal impossible.                                   *)
(* ============================================================= *)

Section CapabilityMonotone.
  Context {A : Type}.
  Variables stepLo stepHi : A -> A -> Prop.   (* fewer / more capabilities *)
  Hypothesis grant : forall x y, stepLo x y -> stepHi x y.
  Variable agoal : A -> Prop.

  Theorem cap_monotone :
    forall s0 a, reach stepLo s0 a -> agoal a ->
                 exists a', reach stepHi s0 a' /\ agoal a'.
  Proof.
    intros s0 a Hreach Hgoal. exists a. split.
    - apply (reach_mono stepLo stepHi grant). exact Hreach.
    - exact Hgoal.
  Qed.
End CapabilityMonotone.

(* ============================================================= *)
(*  Concrete non-vacuity instance: the hallucinated-planning      *)
(*  failure mechanically refuted.                                 *)
(*                                                               *)
(*  Goal: booked /\ confirmation_sent.                           *)
(*  Capabilities present: search, filter, book.                  *)
(*  Capability ABSENT: send_email (so confirmation_sent can       *)
(*  never become true).                                          *)
(*                                                               *)
(*  We prove directly that no reachable state satisfies the      *)
(*  goal -- i.e. the checker's REFUTED verdict is correct here.   *)
(* ============================================================= *)

Module FlightInstance.

  Record World := mk {
    searched : bool;
    filtered : bool;
    booked   : bool;
    conf     : bool   (* confirmation_sent *)
  }.

  (* Concrete steps for the THREE capabilities the agent actually has.
     Crucially, none of them touches [conf], because there is no
     send_email capability in scope. *)
  Inductive cstep : World -> World -> Prop :=
  | do_search : forall w,
      cstep w (mk true (filtered w) (booked w) (conf w))
  | do_filter : forall w,
      searched w = true ->
      cstep w (mk (searched w) true (booked w) (conf w))
  | do_book : forall w,
      filtered w = true ->
      cstep w (mk (searched w) (filtered w) true (conf w)).

  Definition s0 : World := mk false false false false.
  Definition cgoal (w : World) : Prop := booked w = true /\ conf w = true.

  (* Invariant: every concrete step preserves [conf]. *)
  Lemma step_preserves_conf : forall w w', cstep w w' -> conf w' = conf w.
  Proof. intros w w' H. destruct H; simpl; reflexivity. Qed.

  (* Therefore confirmation is never sent on any run from s0. *)
  Lemma conf_stays_false : forall w, reach cstep s0 w -> conf w = false.
  Proof.
    intros w H. induction H as [| u v Hsu IH Huv].
    - reflexivity.
    - rewrite (step_preserves_conf u v Huv). exact IH.
  Qed.

  (* Refutation: the goal is unreachable. The verdict "IMPOSSIBLE" is sound. *)
  Theorem flight_refuted : ~ exists w, reach cstep s0 w /\ cgoal w.
  Proof.
    intros [w [Hreach [_ Hconf]]].
    rewrite (conf_stays_false w Hreach) in Hconf. discriminate Hconf.
  Qed.

  (* Sanity: the agent CAN still get a booking -- the spec is not vacuously
     stuck; only the confirmation half is impossible. This shows the
     refutation is about the missing capability, not a dead protocol. *)
  Theorem booking_reachable :
    exists w, reach cstep s0 w /\ booked w = true.
  Proof.
    exists (mk true true true false). split.
    - eapply reach_step.
      eapply reach_step.
      eapply reach_step.
      apply reach_refl.
      (* search: s0 -> mk true false false false *)
      apply (do_search s0).
      (* filter: searched=true *)
      apply (do_filter (mk true false false false)). reflexivity.
      (* book: filtered=true *)
      apply (do_book (mk true true false false)). reflexivity.
    - reflexivity.
  Qed.

End FlightInstance.

(* ============================================================= *)
(*  T1r  Refutation soundness with a simulation RELATION          *)
(*                                                               *)
(*  The Soundness section above takes the abstraction as a       *)
(*  FUNCTION abs : W -> A.  The checker's symbolic abstraction   *)
(*  (Lemma 3 of the paper) is not a function of the concrete     *)
(*  world: a world <B,N> is represented by (B,psi) for ANY        *)
(*  accumulated constraint psi that N satisfies, and psi depends  *)
(*  on the path the search took.  The schema is therefore         *)
(*  restated with a simulation relation R, of which the          *)
(*  functional form is the special case R w a := (a = abs w).    *)
(* ============================================================= *)

Section SoundnessRel.
  Context {W A : Type}.
  Variable cstep : W -> W -> Prop.
  Variable astep : A -> A -> Prop.
  Variable R     : W -> A -> Prop.   (* "a represents w" *)
  Variable cgoal : W -> Prop.
  Variable agoal : A -> Prop.

  Hypothesis step_sim_rel :
    forall w w' a, cstep w w' -> R w a -> exists a', astep a a' /\ R w' a'.
  Hypothesis goal_sim_rel :
    forall w a, cgoal w -> R w a -> agoal a.

  Lemma reach_abs_rel :
    forall s0 a0 w, R s0 a0 -> reach cstep s0 w ->
      exists a, reach astep a0 a /\ R w a.
  Proof.
    intros s0 a0 w HR H. induction H as [| u v Hsu IH Huv].
    - exists a0. split. apply reach_refl. exact HR.
    - destruct IH as [a [Hra HRa]].
      destruct (step_sim_rel u v a Huv HRa) as [a' [Hstep HR']].
      exists a'. split.
      + eapply reach_step. exact Hra. exact Hstep.
      + exact HR'.
  Qed.

  Theorem refutation_sound_rel :
    forall s0 a0, R s0 a0 ->
      (~ exists a, reach astep a0 a /\ agoal a) ->
      (~ exists w, reach cstep s0 w /\ cgoal w).
  Proof.
    intros s0 a0 HR Hno [w [Hreach Hgoal]].
    destruct (reach_abs_rel s0 a0 w HR Hreach) as [a [Hra HRa]].
    apply Hno. exists a. split.
    - exact Hra.
    - exact (goal_sim_rel w a Hgoal HRa).
  Qed.
End SoundnessRel.

(* The functional schema (refutation_sound) is the special case
   R w a := (a = abs w) of the relational one. *)
Lemma refutation_sound_fun_is_rel {W A : Type}
  (cstep : W -> W -> Prop) (astep : A -> A -> Prop) (abs : W -> A)
  (cgoal : W -> Prop) (agoal : A -> Prop) :
  (forall w w', cstep w w' -> astep (abs w) (abs w')) ->
  (forall w, cgoal w -> agoal (abs w)) ->
  forall s0, (~ exists a, reach astep (abs s0) a /\ agoal a) ->
             (~ exists w, reach cstep s0 w /\ cgoal w).
Proof.
  intros Hs Hg s0.
  apply (refutation_sound_rel cstep astep (fun w a => a = abs w) cgoal agoal).
  - intros w w' a Hc Heq. subst a. exists (abs w'). split.
    + apply Hs. exact Hc.
    + reflexivity.
  - intros w a Hcg Heq. subst a. apply Hg. exact Hcg.
  - reflexivity.
Qed.

(* ============================================================= *)
(*  Lemma 3 (the symbolic abstraction satisfies the hypotheses), *)
(*  mechanized for a SHALLOW embedding of the state logic.        *)
(*                                                               *)
(*  A concrete configuration is (control, boolean valuation,     *)
(*  numeric world).  The checker's abstract configuration is     *)
(*  (control, boolean valuation, accumulated constraint psi).    *)
(*  Constraints are modelled semantically, as predicates on      *)
(*  numeric worlds; guards and numeric effects as relations; the *)
(*  strongest postcondition as the image; and the widening on    *)
(*  back edges as an ARBITRARY policy (any edge may drop psi).   *)
(*                                                               *)
(*  What this does NOT cover (and remains on paper): that the    *)
(*  checker's QF-LIA formulas denote these predicates, and that   *)
(*  the SMT solver decides their satisfiability correctly.        *)
(* ============================================================= *)

Module SymbolicInstance.
  Section Symbolic.
    Context {Ctl Bv Num Cap : Type}.
    (* protocol control: firing capability a moves control g to g' *)
    Variable cnext : Ctl -> Cap -> Ctl -> Prop.
    (* guard, boolean (Add/Del) update, numeric effect (may be nondeterministic) *)
    Variable pre  : Cap -> Bv -> Num -> Prop.
    Variable bupd : Cap -> Bv -> Bv.
    Variable eff  : Cap -> Num -> Num -> Prop.
    (* goal markers and the goal formula *)
    Variable goal_at : Ctl -> Prop.
    Variable gphi    : Bv -> Num -> Prop.
    (* the implementation's widening policy: on which edges psi is dropped *)
    Variable widen : Ctl -> Cap -> Ctl -> bool.

    Definition Constraint := Num -> Prop.
    Definition CW := (Ctl * Bv * Num)%type.
    Definition AW := (Ctl * Bv * Constraint)%type.

    (* World-Act / G-Act-E: a concrete firing. *)
    Definition cstep (c c' : CW) : Prop :=
      let '(g, b, n) := c in
      let '(g', b', n') := c' in
      exists a, cnext g a g' /\ pre a b n /\ b' = bupd a b /\ eff a n n'.

    (* strongest postcondition of firing a from (b, psi) *)
    Definition sp (a : Cap) (b : Bv) (psi : Constraint) : Constraint :=
      fun n' => exists n, psi n /\ pre a b n /\ eff a n n'.
    Definition top : Constraint := fun _ => True.

    (* The symbolic edge exists iff psi /\ pre_a is satisfiable under b. *)
    Definition astep (s s' : AW) : Prop :=
      let '(g, b, psi) := s in
      let '(g', b', psi') := s' in
      exists a, cnext g a g' /\ (exists n, psi n /\ pre a b n) /\ b' = bupd a b /\
        psi' = (if widen g a g' then top else sp a b psi).

    Definition cgoal (c : CW) : Prop :=
      let '(g, b, n) := c in goal_at g /\ gphi b n.
    Definition agoal (s : AW) : Prop :=
      let '(g, b, psi) := s in goal_at g /\ exists n, psi n /\ gphi b n.

    (* abs is a RELATION: <B,N> is represented by (B,psi) whenever N |= psi. *)
    Definition R (c : CW) (s : AW) : Prop :=
      let '(g, b, n) := c in
      let '(g', b', psi) := s in
      g = g' /\ b = b' /\ psi n.

    Lemma step_sim :
      forall c c' s, cstep c c' -> R c s -> exists s', astep s s' /\ R c' s'.
    Proof.
      intros [[g b] n] [[g' b'] n'] [[h d] psi] Hc HR.
      unfold cstep in Hc. unfold R in HR.
      destruct Hc as [a [Hn [Hp [Hb He]]]].
      destruct HR as [Hg [Hd Hpsi]]. subst h d.
      exists (g', b', if widen g a g' then top else sp a b psi). split.
      - unfold astep. exists a. split.
        + exact Hn.
        + split.
          * exists n. split. exact Hpsi. exact Hp.
          * split. exact Hb. reflexivity.
      - unfold R. split.
        + reflexivity.
        + split.
          * reflexivity.
          * destruct (widen g a g').
            { exact I. }
            { unfold sp. exists n. split. exact Hpsi. split. exact Hp. exact He. }
    Qed.

    Lemma goal_sim :
      forall c s, cgoal c -> R c s -> agoal s.
    Proof.
      intros [[g b] n] [[h d] psi] Hcg HR.
      unfold cgoal in Hcg. unfold R in HR.
      destruct Hcg as [Hg Hphi]. destruct HR as [Hgh [Hbd Hpsi]]. subst h d.
      unfold agoal. split.
      - exact Hg.
      - exists n. split. exact Hpsi. exact Hphi.
    Qed.

    (* Lemma 3 + Theorem 1, composed: the search the checker runs is
       refutation-sound, for every widening policy. *)
    Theorem symbolic_refutation_sound :
      forall c0 s0, R c0 s0 ->
        (~ exists s, reach astep s0 s /\ agoal s) ->
        (~ exists c, reach cstep c0 c /\ cgoal c).
    Proof.
      intros c0 s0 HR.
      exact (refutation_sound_rel cstep astep R cgoal agoal step_sim goal_sim c0 s0 HR).
    Qed.

    (* The initial abstract state: any constraint the initial numeric world
       satisfies (the checker seeds psi with the initial assignments). *)
    Lemma initial_related :
      forall g b n (psi : Constraint), psi n -> R (g, b, n) (g, b, psi).
    Proof. intros g b n psi H. unfold R. split. reflexivity. split. reflexivity. exact H. Qed.

    (* Tolerance, instantiated: dropping psi everywhere (the coarsest policy)
       still yields a system related to the concrete one, so Theorem 2's
       reading holds here too: the constant-true widening refutes nothing
       that a finer policy could have reached. *)
    Lemma sp_implies_top : forall a b psi n', sp a b psi n' -> top n'.
    Proof. intros. exact I. Qed.
  End Symbolic.
End SymbolicInstance.

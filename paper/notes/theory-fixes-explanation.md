# Why the Theory Changed: an Explanation of the Blue-Marked Fixes

All fixes in the paper are marked in blue (`\bgc ... \egc`); the red text
(`\bmr ... \emr`) from earlier revisions is untouched. This note explains
*why* each fix was made, with the most detail on the decidability theorem.

Naming note: theorem numbers below follow the current compiled PDF.
The decidability fix concerns **Theorem 6 — "Termination and soundness of
the widened search"** (formerly stated as "Decidability"). Theorem 5 in the
PDF is Session fidelity.

---

## The one-minute version

The old Theorem 6 claimed our judgment is *decidable*. It isn't, for two
independent reasons: the proof's own widening step means the procedure
decides an over-approximation rather than the judgment itself, and the
exact judgment can encode two-counter machines, so it is undecidable
outright. What *is* true — and what the implementation actually does — is
that the search always **terminates**, its **impossible** answer is sound,
and its **achievable** answer is only a claim about the abstraction. The
theorem was restated to say exactly that. This is not a weaker paper:
refutation-soundness plus incompleteness-for-achievable was already the
story everywhere else; the old theorem was the one place that overclaimed.

---

## Theorem 6 in detail: the two reasons the old statement fails

### Reason 1: the proof contradicts its own conclusion

The procedure widens the numeric constraint (`psi -> true`) on every loop
back-edge, and the proof itself calls this an over-approximation. Widening
means *deliberately forgetting* numeric facts so the state space becomes
finite. Forgetting facts can only add behaviors, never remove them. So:

- **"No goal found anywhere" is still conclusive** — if even the enlarged
  system cannot reach the goal, the real one certainly cannot. That is why
  *impossible* survives.
- **"Goal found" is not conclusive** — the path may exist only because
  widening forgot the constraint that ruled it out.

A procedure with that asymmetry decides the *abstract* judgment, not the
exact one. The old proof's last line ("hence a decision procedure for the
achievability judgment") simply does not follow from what was proved above
it.

### Reason 2: the exact judgment is undecidable anyway

Our worlds have unbounded integer variables, the effect language has
`x := x+1` and `x := x-1`, and guards can test `x = 0` and `x >= 1`.
Combined with recursive control from the global type, that is exactly a
two-counter Minsky machine: finite program, two counters,
increment / decrement / zero-test — and halting for those is undecidable
(classic result). The diamond being existential makes the encoding easy:
let the protocol's choice nondeterministically *guess* the machine's next
transition, and let the guards kill every wrong guess. Then "goal
reachable" iff "machine halts." So no total decision procedure for the
exact judgment can exist — no proof strategy could have rescued the old
statement; only restating it (or banning unbounded integers) can.

### Why the fix is the right one

The restated theorem says: the widened search terminates on every pack;
*impossible* is sound for the pack (via Theorem 1 plus the new Lemma 3);
*achievable* may be spurious (which is literally Proposition 1, already in
the paper). This is exactly what the implementation does — nothing in the
code changed. And it makes the paper internally consistent: the abstract,
the introduction, and Figure 1 all advertise the asymmetric guarantee
("impossible is never wrong; achievable is best-effort"); the old
Theorem 6 was the one spot claiming symmetry.

---

## The other changes, one paragraph each

### New Lemma 3 (the abstraction satisfies the hypotheses)

Theorem 1 — the Coq theorem — is deliberately a *schema*: it assumes
step-sim and goal-sim. Nowhere did we show that the checker's actual
abstraction (boolean valuation + accumulated constraint + widening)
satisfies those two assumptions, so formally the headline guarantee never
attached to the implementation. Lemma 3 is that missing bridge. The proof
is short: the concrete numeric state itself witnesses every satisfiability
the abstract side needs, and widening only weakens the constraint, which
only adds abstract edges (Theorem 2). On paper for now; mechanizing it is
listed as future work.

### Goal observation: S-Goal removed, G-Goal-F added

The old S-Goal let *any* configuration emit the label `check phi` whenever
the world satisfied `phi`. That broke both correspondence theorems with
concrete counterexamples:

- At `End`, the session could emit the goal label but `End` has no global
  transition at all — so subject reduction fails, and the session-fidelity
  proof's End case invoked G-Goal-E, which cannot apply to `End` (the two
  proofs contradicted each other on this case).
- Under a choice, G-Comm-I required the marker to be pending in *every*
  branch, which fails as soon as one branch is `End`.
- The repair device in the prose ("each session carries a set of goal
  formulas") was never formalized — a source note admitted it.

The fix: goal satisfaction is a *predicate*, not a session transition, and
the correspondence uses one fused rule, **G-Goal-F** — check the marker
and take the next step in a single transition. That is verbatim the rule
`GS_Goal` already proven in the Coq file, so the paper and the
mechanization now agree. Bonus: the goal-stability side condition
disappears, because the marker is checked at the very world where the step
happens — nothing can falsify it "in between."

### T-Act: universal over successor worlds

An `Nd` effect is nondeterministic — one firing can lead to many successor
worlds. The old rule typed the residual protocol at *one* chosen
successor; but at run time the session may land in a *different* one,
where nothing was checked, so subject reduction broke. The fixed rule
keeps an existential premise for the guard (the action must be fireable)
and a universal premise for typing (the residual must be typed at every
possible successor). For deterministic capabilities the successor is
unique and the rule reads exactly as before.

### Proposition 2 (undecidability)

Two gaps. First, the extension "add a participant during execution" never
said what the new participant *is* (what behavior it runs). Second, the
FIFO-ordering argument needed each courier to remember its own sequence
number — impossible when the set of numeric variables is fixed and finite
but couriers are unbounded. The fix defines the extension (a declared
finite behavior template plus one fresh numeric variable per added
participant, initialized at creation) and routes the ordering through that
per-courier variable. We also added why this result still matters next to
the new Theorem 6: here *no widening can help*, because the control space
itself becomes infinite — a strictly harder boundary than the numeric one.

### Everything downstream (Contribution 3, Section 3 "Guarantees", Limitations, the obligations table)

These are not independent changes — they are the places where the main
text *restates* the theorems. Once Theorem 6 says "terminates" instead of
"decidable" and the stability assumption is gone, leaving the restatements
unchanged would make the paper contradict its own appendix.

### The small ones

- `Add` and `Del` required disjoint, so the update order in `apply` is
  immaterial.
- The evaluation `[[e]]_N` is now defined (this answers the margin
  question about it directly).
- One `Nd` constraint may not mention another `Nd`-updated variable — the
  simultaneous-update semantics was ambiguous.
- `init` is declared as part of the pack; the judgment quantified over
  `W0 |= init` but `init` was never in the pack.
- The `forall i` in G-Comm-I is made to cover both premises; the
  typesetting attached it to only one.
- Reach-Or is noted as derivable from Reach-Step and G-Comm-E (kept
  because the search implements branching that way).
- The roles in the Ach rule are bound to `prt(G)` — which answers
  "who is p?".

---

## The single sentence that ties it all together

**Every change either makes a stated theorem actually true, or makes the
paper say what the Coq development and the implementation already do.**
Nothing in the code, the corpus, or the mechanized proofs moved.

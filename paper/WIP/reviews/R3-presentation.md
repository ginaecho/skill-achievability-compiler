# Review R3 — Presentation, Framing, and Communication

**Paper:** *Affordable Mistakes: Severity-Aware Multiparty Session Types for Participants that Choose Wrongly*
**Reviewer role:** communication/presentation. I did **not** assess soundness of the theory or the
statistics of the evaluation; assume other reviewers did.
**Time spent:** ~45 min, full read of the 22-page body + references.

---

## (a) Summary judgement

**Score: C (weak reject). Confidence: 4/5 (high).**

Judged purely on how it reads: this is a paper with unusually good *sentences* and a badly
mis-allocated *structure*. The author can write. "Session types say what may happen; this says what
you can survive." "A participant that may never err may never act." "'Tolerant of one wrong choice;
two wrong choices reach data loss, here is the path and the action that burns the bridge' is
actionable. 'Impossible' is not." Those land, and they land because someone thought about the
reader.

But by page 11 the reader has been handed six sections of rules and theorems with **not one worked
instance**, the running example established on page 3 has been contradicted by the figure on page 4
and then abandoned until page 17, a third of the evaluation measures a *different system* than the
one the paper is about, and Section 13 is an internal lab note about a draft nobody outside the
group has read. Two defects are outright blocking as submitted: the abstract asserts something the
body explicitly denies (the kernel), and Definition 2 — the paper's central relation — is defined
"the head rules of the base semantics, plus…" where those head rules are never printed and the file
that allegedly contains them (`tas.tex`) is not in the submission.

None of this is unfixable. The material is there; the arrangement is wrong. Fix W1–W8 below and
this is a clear B, plausibly an A — the prose quality is already there and most venues never get
that part. As it stands I would not fight for it.

Note: the review request says "three figures." The paper has **four** (Fig. 1 idea, Fig. 2
architecture, Fig. 3 modularity, Fig. 4 TRAC). I review all four.

---

## (b) Three things done well

1. **The reframing paragraph (§1, "The reframing").** Benign / Futile / Catastrophic, then *"A system
   that blocks Futile is useless; one that permits Catastrophic is dangerous. Separating them is the
   whole job."* Three lines that do more than most papers' entire introduction. It gives the reader
   a hook they can hold for twenty pages. Do not touch it.

2. **Showing the tool's actual output on page 4, in a `verbatim` block, before any formalism.** This
   is the right instinct and it is rare. The reader sees the artifact, sees what an engineer would
   read, and sees the "so what" in the same eyeful. Most PL papers make you wait until §8 for this.

3. **Claim hygiene.** The "What is and is not new" paragraph, the `✓ coq_name` annotation on every
   single theorem, the footnote disambiguating *k*-safety / *k*-resilience from prior uses, and
   **Finding 1 reported as a finding** ("existing corpora cannot pose the question") rather than
   buried. The reader always knows what is proved, where, and what is borrowed. That buys a lot of
   trust — and the paper then spends some of it back (see W15).

---

## (c) Weaknesses

### BLOCKING

---

**W1 — The abstract contradicts §10 about the kernel. (blocking)**

Abstract: *"Everything is mechanized in Coq, axiom-free, and the tool's decision on the boolean
fragment **is** a kernel extracted from that proof."*

§10, Verified kernel: *"The tool's search is the graph form of Theorem 19 … **it is not extracted
from the proof.** To close that gap on the fragment where the proof applies we built a kernel…"*

These cannot both be true. The body's story (independent tool, extracted kernel, 499/499
differential agreement) is *more* impressive than the abstract's, and the abstract's version will
get the paper accused of overclaiming the moment a reviewer reaches page 12. Separately,
"Everything is mechanized" is false: Proposition 22 carries a paper proof, and §15 lists the
elaboration, environment choices and the widened arithmetic fragment as trusted.

**Fix — replace the abstract sentence with:**

> The metatheory of Sections 5–9 is mechanized in Coq and axiom-free; the tool's own analyzer is
> not extracted, so on the boolean fragment we check it against a decision procedure that *is*
> extracted from the proof, and the two agree on 499 of 499 random protocols.

---

**W2 — The paper's central relation is defined by reference to rules that do not appear, in a file
the reviewer does not have. (blocking)**

§3: *"`tas.tex` is authoritative and this section fixes notation."*
Definition 2: *"…(Coq: `reach_haz`): **the head rules of the base semantics**, plus [RH-Comm-Ok,
RH-Comm-Dev]."*

The two rules that *are* printed are the two easy ones. The reader is never told what
`⇝` does at `a@p.G`, at `✓φ.G`, or at `End` — i.e. exactly the cases where the world changes and
where the hazard is checked. Every theorem in §5–§9 is about this relation. A submission cannot
delegate its core definition to an unpublished internal file, and "this section fixes notation"
is not a substitute for stating the semantics.

**Fix.** Print the remaining three head rules of `⇝^H_b` inline in Definition 2 (they are three
lines: `W ⊨ H` closes; `a@p.G` quantifies over `⟨W⟩a⟨W'⟩` successors; `✓φ.G` and `End` pass
through), and delete every reference to `tas.tex`. Retitle §3 to **"Background: A Goal-Marked
Capability-Guarded Multiparty Discipline"** and open it with one sentence saying what is inherited
and citing where it is published — not a filename.

---

**W3 — Roughly a third of the evaluation evaluates a different system than the one the paper is
about. (blocking, framing)**

The paper's claim is *k*-misselection tolerance: budgets, severity, points of no return, the bridge
theorem. Findings 5 and 6, plus "The corpus is an untrusted input," run pages 15–17 — about **2.7 of
the paper's 20 body pages** — and none of them contains a budget, a misselection, a severity class,
or a tolerance degree. They measure the *achievability* checker: refutation precision (4.3% false
refutations), whether refuted skills waste tokens, whether escalation to an LLM compaction pays.
Achievability gets exactly one sentence of definition in the whole paper (§3: *"Achievability is
existential may-reachability of a goal-satisfying configuration"*), and it is inherited, not
contributed.

A PC member's reaction: *what does scanning 162 third-party skill files for base64 payloads have to
do with whether a protocol survives two wrong choices?* Nothing, except that the same binary
computes both. Right now Finding 4 — the *only* experiment that tests this paper's thesis — gets one
page, and the off-thesis material gets nearly three.

**Fix.** Cut Findings 5 and 6 and the security paragraph down to a single paragraph, roughly:

> The severity analysis rides on an achievability checker whose refutations we have separately
> validated: over 162 skills from thirteen public repositories, run in two runtimes with every
> artifact recomputed, refuted runs produced no correct artifact at realistic input sizes and the
> hand-audited false-refutation rate is 4.3%. That evidence, the corpus security audit, and the
> token economics of escalation are orthogonal to this paper's contribution and are reported in the
> artifact (§A.3).

Move the detail to an appendix or the artifact. Then spend the reclaimed ~2.2 pages on Finding 4,
which is the experiment that matters and is currently the thinnest. Delete the abstract's third
sentence about 162 skills and replace it with something about the 340 live-agent runs — that is the
result the abstract should be selling.

---

### MAJOR

---

**W4 — Figure 1 uses a different example than the running example on the facing page. (major)**

§2 establishes `G_bad` with labels `safe` / `fast`, actions `verify` / `purchase`, atoms
`verified` / `booked` / `funds`. Figure 1, one page later, is labelled with `fare = 620`,
`stop[fare>500]`, `go[fare≤500]` — a numeric guard and two labels that appear **nowhere else in the
paper** — and then wires them to a `purchase@q` edge from the *other* example. The reader spends
thirty seconds trying to reconcile them and concludes the figure is from an older draft. It also has
a live label collision: the green arrow strikes through `stop[fare>500]`, and the dashed arrow
strikes through `go[fare≤500]`.

**Fix.** Relabel Figure 1 with the running example exactly: `W: funds, ¬verified, ¬booked`;
branches `safe[…]` (intended) and `fast[…]` (misselection); the Catastrophic path through
`purchase@q` with `purchase` marked as the point of no return; the Benign detour as a second
`safe`-side path. Nudge the two guard labels off the arrows.

---

**W5 — The running example vanishes for six pages, and the paper's two headline rules are never
instantiated. (major)**

From §5 (page 6) to §9 (page 11) — the T-Choice-Safe rule, the bridge theorem, the recursion,
the bystanders, the product graph, modular composition — there is **not one instance**. The example
returns on page 17 (§11) and in the tables. This is the single worst stretch of the paper for a
reader: it is the part where you most need a hand to hold.

Two specific holes:

- **T-Choice-Safe is never applied.** Show the derivation for `G_bad` at *b* = 1: the `safe` branch
  checked at 1, the `fast` branch checked at 0, `⊢_0 purchase@q.End, W` failing because
  `W ⊨ H` at the successor. Six lines. It makes the "affordable mistake as a rule" slogan real.
- **The bridge theorem has no instance and no picture.** C1 is billed as *the* contribution
  ("carrying a quantity a participant *spends* across a reduction relation") and the reader gets
  Definition 9 plus a two-clause theorem statement. Nothing shows a session actually running.

**Fix.** See "the single change" at the end — this is where it goes.

---

**W6 — The "Default instantiation" paragraph is where the reader stops and gets suspicious. (major)**

§4, unnumbered, six lines:

> *"When a branch carries none, the implementation uses the rational-choice default: a branch is
> intended in W iff the goal is still reachable from its residual."*

But Definition 4 says a residual is Benign iff the goal is still reachable. So under the default
instantiation, "intended" and "Benign" are defined by *the same predicate*. The reader immediately
asks: is the trichotomy circular? Can a misselection ever be Benign under the default? If not, then
of the 29 Benign verdicts in Table 1, how many are just intended branches, and how many come from
the two rows the table flags as using explicit guards? The paper never says which benchmark rows use
which instantiation — only two of seventeen carry a parenthetical.

This is the most important semantic decision in the paper (it is how guards are populated in
*every* experiment) and it is an unnumbered paragraph with no example. It should be a numbered
definition with the collapse question answered head-on.

**Fix — replace the paragraph with:**

> **Definition 3 (Rational-choice default).** Where a branch carries no guard, take
> `ψ_i := (G_i, W) ⇝^φ_0` — branch *i* is intended in *W* iff the goal is still reachable from its
> residual with no further mistakes.
>
> Under this default, "misselection" and "Benign" are read off the same predicate at different
> budgets, and it is worth saying exactly what survives. At budget 0 a misselection is precisely a
> branch that forfeits the goal, so no misselection is Benign and the trichotomy collapses to
> Futile/Catastrophic — which is the right answer: with no budget, a mistake either wastes the run
> or breaks something. The classes separate at *b* > 0, where a branch can forfeit the goal *at this
> budget* and recover at a higher one, and wherever explicit guards make the intended branch a
> matter of policy rather than reachability. Every Benign *misselection* reported in §10 comes from
> the latter; Table 1 marks which protocols carry explicit guards.

Then add a `guards` column to Table 1 (default / explicit / declared-hazard) so every row is
self-describing.

---

**W7 — Section 13 ("What Changed, and Why") hurts. Cut it. (major)**

It is half a page describing a design the reader has never seen, failing for reasons the reader
cannot reconstruct: *"a closure premise recursing at the same node terminated at bottom where only a
quarantine rule with a partial residual applied."* There is no closure premise, no quarantine rule
and no partial residual anywhere else in the paper. The section is unreadable **by construction** —
it is a diff against an absent baseline.

What it actually communicates to a PC member: (i) the group already got this wrong once and only
found out via mechanization; (ii) the current design is new enough that nobody has stress-tested it;
(iii) this text was written for the authors, not for me. The intent — "we report this because the
negative result produced the positive one" — is admirable and belongs in a blog post or an artifact
note. It also leaks anonymity by referring to a withdrawn predecessor draft.

**Fix.** Delete §13. Put this in §15, Scope, and nothing more:

> An earlier version of this discipline typed per-role compliance (trust modes, taint, staleness
> grades) rather than severity. Its mechanized audit found the typing rules vacuous on any protocol
> containing a capability; the audit is retained in the artifact. The present design has no such
> premise: deviation lives in the operational semantics as a budget.

That is three sentences, keeps the honesty, and costs the reader nothing.

---

**W8 — The contribution is buried behind three paragraphs of disclaimers, then stated twice.
(major)**

§1 order: motivation → "The reframing" → **"What is and is not new"** (a paragraph of six
citations to things the paper does *not* claim, ending in *"We claim none of these"*) → an indented
italic claim box → **"We are careful with the word type system"** (another disclaimer) → C1–C5.

So the reader meets the negative space of the contribution before the contribution, twice, and then
meets the contribution twice more (claim box, then C1–C5, which restate it in more detail). By the
time C1 arrives the reader has been told what this is *not* for about 25 lines.

The claim box and C1 also say the same thing in different words — box: *"a session typed against a
k-tolerant protocol is hazard-free within budget k, with budgets distributing over participants"*;
C1: *"A session typed against a k-tolerant protocol is hazard-free on every run whose misselection
cost is at most k … the budget distributes over participants."*

**Fix.** Reorder to: reframing → **contributions C1–C5** → "What is and is not new" (retitled
**"What we borrow"**), and delete the italic claim box entirely — C1–C5 subsume it. Move the "we are
careful with the word *type system*" paragraph to the head of §7, where it is actually relevant,
opening it as:

> A note on the word *type system*, before the theorem that earns it. The condition of §6 is on
> global types, as well-assertedness and deadlock-freedom conditions are; the participants are typed
> by the base discipline's conformance judgment, unchanged. The type-theoretic content of this paper
> is Theorem 10, which couples the two.

---

**W9 — §12 + Figure 4 + Table 4 spend 1.3 pages on one related paper, and the figure and the table
say the same thing. (major)**

Figure 4's bottom bands read *"run time · single agent · learned abstraction · probabilistic
prediction · detects then reacts"*. Table 4's rows read `when: run time`, `scope: one agent's
trace`, `abstraction: language-model labelers`, `prediction: sampling continuations`. That is the
same content, rendered twice, adjacent, on the same page. Meanwhile the prose paragraph ("Two
differences are deep") is the only part of §12 that says something a table cannot.

No other related work gets a section, a figure and a table. Giving TRAC that treatment signals to
the reader that TRAC is the paper's real competition — which, if true, should be said in §1, and if
false, should not be implied by layout.

**Fix.** Delete Table 4 (the figure carries it). Demote §12 to a subsection **"Runtime compliance
monitoring"** inside §14, keeping Figure 4 and the "Two differences are deep" paragraph verbatim.
Saves ~0.6 page and removes a structural claim the paper does not want to make.

---

**W10 — The "Bystanders" paragraph in §7 is a twelve-line unbroken block enumerating four swap
shapes and three side conditions in running prose. (major)**

> *"A swap exchanges two adjacent independent nodes, in either direction and under any context: a
> bystander action a@r and another role's action b; a@r and a choice between two other roles (when
> every branch begins with a@r); a@r and a goal marker; and two communications p→q and r→s between
> disjoint role pairs, each branch of the first continuing with the second. Communications change no
> world, so their permutation needs no side condition; an action's does: a is hazard-neutral …,
> a and b commute …, and a preserves the guards and goal markers it passes."*

Four cases and three conditions, semicolon-delimited, with the conditions attached to only some of
the cases. Nobody parses this on one pass. This is precisely the content that wants to be *seen*.

**Fix.** Replace with a small display — four swap schemas as `⇄` equations (`… a@r. b@s. G ⇄ …
b@s. a@r. G`, etc.), each annotated with its side condition or "no side condition", and one line of
prose above. Half the space, five times the comprehension.

---

**W11 — Figure 3 does not earn its space; the figure the paper needs does not exist. (major)**

**Figure 3 (Modularity)** is two rounded rectangles, an arrow labelled "replaces", and two
complexity expressions. Everything in it is in its own caption and in Theorem 23, and Table 2 gives
the quantitative version far more convincingly. It is a slide, not a figure. **Cut it.**

**Figure 2 (Architecture)** is legible and earns *most* of its space on one point alone — the
trust boundary, "no language model beyond this line," which is the paper's answer to the obvious
"but LLMs are unreliable" objection. Keep it, but shrink it: the `severity classifier` box's inner
formulas are set at roughly 5pt and are not readable at print size, and nothing is lost by replacing
them with the words "sound + complete (Coq)".

**Figure 4 (TRAC)** earns its space *if* Table 4 goes (W9).

**Missing: a figure for the bridge theorem.** C1 is the headline contribution and it is the one
thing in the paper with no picture. Draw it: a protocol path `G → G' → G''` on top, the session
`M ‖ W` stepping below it, each step labelled `(role, cost)`, a budget counter `k → k → k−1`
decrementing only on the misselection step, and the invariant `⊢_{remaining} G_i, W_i` written under
every configuration — with the hazard region shaded and visibly unreachable while the counter stays
≥ 0. That single picture makes "carrying a quantity a participant *spends* across a reduction
relation" *obvious*, and right now it is the sentence the reader has to take on faith.

---

**W12 — Vocabulary used before, or without, definition. (major, cumulative)**

- **`✓ name`** — the checkmark-plus-Coq-identifier convention appears first in C1 (page 3) and about
  90 times after, and is **never explained**. Add one line at the end of §1: *"A ✓ marks a result
  proved in the accompanying Coq development, named by its identifier there."*
- **"pack"** — used ~12 times in §10 ("38 packs", "the pack is weak", "sound for the pack the front
  end produced"). Its only definition is a *label inside Figure 2*: `pack ⟨Γ, G[ψ], φ, H⟩`. Define
  it in prose in §2.
- **`H`** — first *used* in Definition 2 (§4), first *introduced* in §5 ("Let φ be the goal and H the
  hazard"). Introduce both φ and H in §3 alongside Γ and W.
- **"environment choice"** — Definition 2 says *"Choices marked as controlled by the environment are
  resolved demonically at no cost,"* but the global-type grammar in §3 has no such marker and none is
  ever given. It then appears as a benchmark row (`order_fulfilment (environment choice)`) and as a
  kernel scope caveat. Either add the annotation to the grammar or drop the feature from the paper.
- **`Asg_a`, `Nd_a`** — appear once, in the effect tuple in §3, and are never mentioned again. Cut
  them or say in half a line what they are for.
- **"the widened finite-range fragment the checker already commits to"** (§5) — widening and the
  finite-range fragment are never explained, and they carry the decidability argument in §5, §8 and
  §10. One sentence in §3.

---

### MINOR

---

**W13 — Dangling cross-reference. (minor)** §10, Finding 2: *"The last pair refines Theorem 8's
anti-monotonicity."* Theorem 8 is the exact characterization; anti-monotonicity
(`tolerance_antitone_in_ctx`) lives in an *unnumbered* paragraph after it. Number that result and
point at the number.

**W14 — Ambiguous reference. (minor)** Theorem 13: *"On the finite fragment this recovers Theorem 10
through Theorem 20."* Reads as the range "Theorems 10–20." Write *"recovers Theorem 10, via the
embedding of Theorem 20."*

**W15 — Defensive and self-deprecating prose. (minor, but there is a lot of it)**

- §6: *"The rule is not deep and we do not claim it is: it is the reachability relation with the
  negation pushed through, and the proof is short."* — You then spend a paragraph explaining why it
  matters anyway. Lead with the value, not the apology: *"The rule is the reachability relation with
  the negation pushed through; the proof is short. Exactness is what it buys, and it buys three
  things."*
- §15: *"a reviewer comparing scope against the asynchronous mechanised subject-reduction
  development of [18] will be right to."* — Right to *do what*? This addresses a reviewer inside the
  paper and half-concedes a point without stating it. Replace: *"Our synchronous scope is narrower
  than the asynchronous mechanised subject-reduction development of [18]; extending the budget
  through buffered communication is open."*
- §10: *"Sixteen hand-picked protocols are a weak test of that agreement, so we also compare…"* —
  keep this one. Self-criticism that leads directly to a stronger experiment is earned.
- §10: *"That was a measurement of our task sizes, not of the checker."* / §15: *"The benchmark is
  ours, with expected verdicts stated in advance but authored by us."* — both good; keep.

The paper says a version of "we claim nothing about X" at least six times (§1 ×2, §6, §10 ×2, §14).
Twice is credibility; six times reads as flinching. Cut the §1 and §14 duplicates.

**W16 — Table 3's `verified` column means different things in different rows. (minor)** Row 5 reads
`20 (by hand)` under `verified` — a value in a different unit from every other cell, explained only
in prose two paragraphs later. Split it into its own column (`verified` / `verified without the
skill`) or move that row out of the table into the paragraph that discusses it.

**W17 — Titles. (minor)**

- **Paper title** is 13 words and the subtitle does the work twice. "Affordable Mistakes" is a good
  title — keep it, shorten the rest: **"Affordable Mistakes: Multiparty Session Types with a Budget
  for Wrong Choices."** ("Severity-Aware … for Participants that Choose Wrongly" says *severity* and
  *choose wrongly* and *participants*, three ideas competing for the same slot.)
- **§9 "Why a Discipline, and Not a Model Checker"** — the title poses the reviewer's objection as
  the section's subject, which puts the paper on the back foot. Retitle **"Modular Composition
  Through a Budgeted Interface"** and keep the model-checker rebuttal as its opening paragraph.
- **§6 "The Well-Formedness Condition, Exactly"** — fine; the comma is affected but the point (that
  exactness is the content) is correct.
- **§13** — see W7.
- Fifteen numbered sections in twenty body pages is a section every 1.3 pages, and that fragmentation
  is a real part of why the paper reads as a list. Merge §3+§4 (background and fault model), fold §8
  into §6, fold §12 into §14, delete §13. Ten sections.

**W18 — Submission hygiene. (minor, but a reviewer sees all of it)** The title footnote reads
*"WORKING DRAFT — not for submission. Base rules follow paper/tas.tex, authoritative for
Section 3."* A boxed *"WIP: Status"* note sits on page 2. `\funding` and `\acknowledgements` say
"To be completed for the camera-ready" — under anonymous review those should be absent, not
placeholders. Five references carry `[authors to verify]` or `[title to verify]` ([31], [48], [55],
[56], [61]).

**W19 — Finding 5 narrates the experiment's history instead of the experiment. (minor)** *"the first
version of this experiment refuted five third-party skills whose tasks reduced to arithmetic over a
dozen rows … That was a measurement of our task sizes, not of the checker. We therefore rebuilt
those five tasks at realistic scale…"* The reader has to hold two versions of a task set, two token
budgets and two verdict tables. Report the final design; give the small-input version one sentence
as a negative control. (If W3 is taken, most of this disappears anyway.)

**W20 — §15's Scope is one 15-line block containing nine distinct limitations. (minor)** Nobody
retains item seven of nine in a paragraph. Make it a bulleted list of five: *synchrony*,
*contractiveness*, *trusted elaboration and arithmetic*, *the hazard is an input*, *evaluation
scope*. The conclusion then lands after a scannable list rather than a wall.

**W21 — The paper is fragile to a reader who thinks LLM agents are a fad. (minor–major, framing)**

§1 has exactly the right abstraction and drops it in one clause: *"A participant that was
**instructed rather than compiled** breaks that hypothesis."* That is the durable category. The very
next sentence collapses it to *"This is the ordinary condition of a language-model agent occupying a
role"*, and from there the paper is LLM-shaped end to end: agents in Figure 2, agents in the
evaluation, agents in related work. A skeptical PC member reads it as a paper whose premise expires.

It costs one paragraph to fix, and the material is already in the paper — `migration_backup` is a
database migration with `backup` / `skip_backup` / `drop_old`, which needs no agent at all.
**Add after "…their latitude":**

> Nothing here is specific to language models. The hypothesis MPST rests on — the participant *is*
> its type — fails for every participant that was instructed rather than compiled: an operator
> following a runbook at a migration console, a third-party service behind an adapter whose
> behaviour is a contract rather than a checked artifact, a learned controller. Each occupies a role
> and may, at a branch the protocol offers, pick the one the situation forbids. Language-model
> agents are the case that makes the question urgent and the case our evaluation can drive at scale,
> but the discipline asks only that the participant choose, not how.

**W22 — The running example is the weaker of the two on offer. (minor)** Booking/purchase is a toy
with one decision point and it cannot exhibit cascading — the paper's whole point. `migration_backup`
has two decision points, `k* = 1`, a genuine two-mistake catastrophe path, and it is *already* the
example whose tool output §2 shows. The formal running example and the demonstrated running example
are different protocols, on facing pages. Pick `migration_backup` for both.

---

## (d) The single change that would most improve the reader's experience

**Make one protocol — `migration_backup` — the spine of the paper, and carry it through every
formal section.**

Concretely: it is the example in Figure 1 (redrawn, W4). It is the protocol whose tool output
appears in §2 (already true). Its guards are exhibited when the default instantiation is defined
(W6). Its `skip_backup` branch is the worked derivation of T-Choice-Safe at *b* = 1 and *b* = 2
(W5). Its two-step catastrophe — `choose/skip_backup > act/migrate > choose/drop_old > act/drop_old`,
which the tool already prints on page 4 — is drawn as **the bridge figure**: the protocol path on
top, the session stepping below, `(role, cost)` on each edge, the budget counting `2 → 2 → 1 → 1 →
0`, and the hazard reached exactly when it hits zero (W11). Its product graph is the instance for
Theorem 16. It is the segment already chained in Table 2. It is a row in Table 1 and a run in
Finding 4.

Everything on that list already exists somewhere in the paper or in the tool's output; almost none
of it needs new results. What it buys is that the six-page desert between §5 and §10 acquires a
floor. The reader who is lost at Theorem 14 can look down and see the same protocol they understood
on page 4, and the paper stops reading as a pile of theorems about an abstraction and starts reading
as one story about one protocol that survives one mistake and not two.

Pay for it with §13, Figure 3, Table 4, and two-thirds of Findings 5 and 6. That is a net saving of
about a page and a half.

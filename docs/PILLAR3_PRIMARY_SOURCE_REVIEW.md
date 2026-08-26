# Pillar 3 primary-source review

Research-only audit of `paper/skillachievability.tex` and the accompanying artifact, produced
2026-08-26. Scope: (1) fit to the Pillar 3 themes, (2) verification of every bibliography entry
marked `[verify]` against primary sources, (3) stress-testing the novelty and related-work claims
against primary papers and source repositories, (4) identifying overclaims and defensible wording.

**No paper or code was changed by this review.** Every recommendation below is a wording or
evidence suggestion, not an applied edit. The design invariant is respected throughout: nothing
here proposes changing the core objective (decidable pre-execution goal-achievability checking for
LLM-synthesized multi-agent skills, fusing planning reachability with session-type conformance,
sound for refutation, with explicit deferred edges).

> **Snapshot note:** line references and recommendations describe the
> pre-remediation source reviewed on 2026-08-26. Several recommendations were
> applied later in the same working session; this report remains the research
> record rather than a live defect list.

Verification method: `arXiv` Atom API, Crossref REST API, DBLP REST API, publisher pages, author
homepages, and direct download + text extraction of competitor PDFs. Search engines were used only
to *locate* sources; every claim below is anchored to a primary artifact.

---

## 1. Fit to the Pillar 3 themes

| Theme | Fit | Evidence |
|---|---|---|
| Heterogeneous verifiable signals | **Strong** | The verdict is a *typed, structured* signal, not a score: `MISSING_CAPABILITY`, `GOAL_UNSAT`, `BLOCKED_GUARD`, `NON_PROJECTABLE`, `NON_CONFORMANT`, each naming a distinct failing premise (`README.md:78-86`; `paper/skillachievability.tex:1140-1150`). Refutations carry a *blocking frontier* and achievements carry a *witness path* (`paper/skillachievability.tex:1096-1099`). The `skillc audit` bundle pre-pass adds a second, orthogonal signal class (manifest consistency, metadata poisoning, risky code) at the same boundary (`README.md:120-140`; `src/skillc/audit.py:1-186`). |
| Beyond scalar rewards | **Strong, but under-argued** | The paper states the connection in one sentence — sound `impossible` verdicts are "cheap, on-distribution negative labels — a reward signal needing no LLM judge" (`paper/skillachievability.tex:1206-1209`) — and then defers it to future work. This is the single highest-leverage under-claimed asset for Pillar 3: a *sound* negative label is categorically stronger than a scalar preference score, and the artifact already emits one per skill in milliseconds. Recommend promoting from a closing aside to a named subsection; no new result is required, only exposition of what already exists. |
| Human-in-loop evaluation | **Strong and structurally load-bearing** | The architecture's central design move is *relocating* the semantic gap to one inspectable checkpoint rather than eliminating it (`paper/skillachievability.tex:230-234`). "Intent fidelity" is explicitly an irreducibly semantic residue surfaced for human review (`paper/skillachievability.tex:982-985`, `:1079`). The front-end reports every extraction with line-number provenance precisely so the checkpoint is auditable (`README.md:104-112`). |
| Reflective verification | **Partial** | Counterexample-guided compaction repair is implemented — a `NON_PROJECTABLE` counterexample is fed back to the untrusted compactor for one bounded, structure-only repair round that may not invent tools or weaken the goal (`README.md:~168-175`; observed firing in practice at `docs/SEMANTIC_VALIDATION.md:9-13`). This is a genuine reflective loop with a *verifiable* referee. It is not described in the paper at all; §7-§8 of the tex do not mention repair. Recommend surfacing it in the paper, since it is exactly the theme's target and it is already evidenced. |
| Automated design / prompt / scaffold search with verifiable feedback | **Weak — aspirational only** | Nothing in the artifact performs search over designs, prompts, or scaffolds. The repair round is a single bounded round, not a search. The `Γ ⊆ Γ'` capability-monotonicity theorem (`proof/SkillAchievability.v:139`) is the right primitive for a scaffold search (grant-tools-until-achievable), and the real-skills experiment already demonstrates the flip in both directions (`README.md:~150-160`; `docs/REAL_SKILLS_REPORT.md`), but no search procedure is claimed or built. Recommend positioning this as *enabling substrate*, not as a contribution. |
| Formal verification using proof assistants | **Strong for the abstract core; overclaimed for the checker** | Three Coq files, no `Axiom`/`Admitted` present in source, with a dedicated `Print Assumptions` audit harness (`proof/check_assumptions.v:1-6`, `proof/check_direct_typing.v:1-11`). See §5 for the precise gap between what Coq proves and what the paper says Coq proves. |

**Overall Pillar 3 read.** The submission is a natural fit for themes 1, 3 and 6, an easy and
cheap win on theme 2 with exposition alone, a defensible fit on theme 4 once the repair loop is
written up, and a stretch on theme 5. Nothing in this assessment requires altering the core
objective.

---

## 2. Bibliography entries marked `[verify]`

All five entries exist and all five are broadly characterised correctly. Two have factual defects.

### 2.1 `\bibitem{msc}` — VERIFIED, incomplete metadata

`paper/skillachievability.tex:1270`: *"Provable Coordination for LLM Agents via Message Sequence
Charts. arXiv:2604.17612, 2026."*

Primary source (arXiv Atom API, `id_list=2604.17612`):

- Title matches exactly.
- Authors: **Benedikt Bollig, Matthias Függer, Thomas Nowak** — omitted from the bib entry.
- Published 2026-04-19; v3 2026-07-15. Comment field: **"42 pages; accepted at ISoLA 2026"** —
  the peer-reviewed venue is omitted.
- Primary category cs.PL.

**The paper's characterisation is correct and now independently confirmed.** `:1179-1181` says the
work "projects a global choreography for LLM agents but targets coordination correctness, not goal
achievability". I downloaded the full 42-page PDF and searched it: the strings `goal` and
`achievab` occur **zero times** in the entire paper. The abstract confirms the projection-based
route ("a syntax-directed projection that generates deadlock-free local agent programs from global
coordination specifications") and confirms that tool/LLM/human outcomes are deliberately left
opaque ("action blocks, which treat LLM calls, tool calls, and human inputs as opaque typed
functions"). This is the strongest-supported differentiation claim in the related-work section.

**But one adjacent claim needs softening.** The same abstract states: *"We also describe a runtime
planning extension in which an LLM dynamically generates a coordination workflow for which the same
structural guarantees apply."* The PDF body confirms a `@planner` decorator in ZipperGen for cases
"where the coordination structure is not known in advance", plus a lightweight planner experiment.
Consequently **"LLM-synthesized global protocol" is *not* itself novel**. The contribution list at
`:253-257` bundles "intent-synthesized, goal-marked global type" into the novelty claim; the
*goal-marked* half is defensible, the *LLM-synthesized* half is prior art. Recommend explicitly
crediting the MSC runtime-planning extension and resting novelty on goal-marking + world state.

Recommended entry: `B. Bollig, M. Függer, T. Nowak. Provable Coordination for LLM Agents via
Message Sequence Charts. ISoLA 2026. arXiv:2604.17612.`

### 2.2 `\bibitem{veriguard}` — VERIFIED, accurate

`paper/skillachievability.tex:1271`. Title matches exactly. Authors (Atom API): Lesly Miculicich,
Mihir Parmar, Hamid Palangi, Krishnamurthy Dj Dvijotham, Mirko Montanari, Tomas Pfister, Long T.
Le. Published 2025-10-03, 22 pages, cs.SE.

The paper's characterisation at `:1181-1182` — "separates offline policy verification from online
monitoring as a safety shield" — is a faithful summary of the abstract's "dual-stage architecture":
an offline stage that "synthesizes a behavioral policy and subjects it to both testing and formal
verification", and a second stage of "online action monitoring". **No correction needed**; add
authors.

### 2.3 `\bibitem{abc}` — VERIFIED, but title truncated AND mischaracterised

`paper/skillachievability.tex:1272`: *"Agent Behavioral Contracts: Formal Specification and Runtime
Enforcement. arXiv:2602.22302, 2026."*

Primary source (arXiv Atom API):

- Actual title: *"Agent Behavioral Contracts: Formal Specification and Runtime Enforcement **for
  Reliable Autonomous AI Agents**"* — the bib truncates the subtitle.
- Author: **Varun Pratap Bhardwaj** (single author), published 2026-02-25.
- Comment: "71 pages, 7 figures, 14 tables. **Patent pending.** Also available on Zenodo: DOI
  10.5281/zenodo.18775393". No peer-reviewed venue is listed.

**Factual error in the related-work text.** `paper/skillachievability.tex:1183-1184` says ABC
"bring design-by-contract to **single agents**." The abstract explicitly states: *"We establish
sufficient conditions for safe contract composition in **multi-agent chains** and derive
probabilistic degradation bounds."* The framework is also evaluated on "AgentContract-Bench, a
benchmark of 200 scenarios across 7 models from 6 vendors" over 1,980 sessions. Describing it as
single-agent is wrong and is the kind of error a reviewer familiar with the cited work will catch.

Defensible replacement wording: *"agent behavioural contracts [abc] bring design-by-contract to
agents with a probabilistic, runtime-enforced notion of compliance, including composition
conditions for multi-agent chains; the guarantees are statistical and enforced at run time, whereas
ours are static, pre-execution, and sound for refutation."* This is a **stronger** contrast than
the current one and remains fully within the design invariant.

Note for the authors' own risk assessment: ABC is a single-author, patent-pending, non-peer-reviewed
preprint. It is fine to cite, but it should not be load-bearing for a "the field has not done X"
argument.

### 2.4 `\bibitem{skillspector}` — VERIFIED, venue should replace "OpenReview"

`paper/skillachievability.tex:1273`: *"N. Paz et al. SkillSpector: A Pre-Publication Security
Control for Agent Skills. OpenReview, 2026."*

`openreview.net` blocks automated fetching behind a browser challenge (verified: both
`/forum?id=rVAPXHmGHN` and `api2.openreview.net` return a `ChallengeRequiredError`). I verified via
a co-author's own publication page instead, which is a primary source for authorship and venue:

> **SkillSpector: A Pre-Publication Security Control for Agent Skills**
> Nir Paz\*, Keshav Pradeep\*, Narendran Raghavan, Ashley Nikirk, Mohit Gupta (\*equal contribution)
> *Agent Skills Workshop at CAIS 2026: The First Workshop on Agent Skills — Design, Evaluation, and
> Optimization of Procedural Knowledge for LLM Agents* · poster · openreview (`id=rVAPXHmGHN`) · repo
> — <https://keshprad.github.io/>

So: first author and year are correct; **"OpenReview" is a hosting platform, not a venue**. The
venue is the Agent Skills Workshop at CAIS 2026. Note also that Nir Paz and Keshav Pradeep are
*equal* first authors, so `N. Paz et al.` is defensible but `N. Paz, K. Pradeep, et al.` is fairer.

The technical description at `paper/skillachievability.tex:1188-1196` is corroborated by the
primary repository (<https://github.com/NVIDIA/SkillSpector>): "**71 vulnerability patterns** across
17 categories: prompt injection, data exfiltration, privilege escalation, supply chain, excessive
agency, output handling, system prompt leakage, memory poisoning, tool misuse, rogue agent,
anti-refusal, trigger abuse, dangerous code (AST), taint tracking, YARA signatures, MCP least
privilege, and MCP tool poisoning", "Two-stage analysis: Fast static analysis + optional LLM
semantic evaluation", "Live vulnerability lookups: SC4 queries OSV.dev". Every scanner class the
paper enumerates is present. **The characterisation is accurate.**

One caution: `:1191-1196` asserts SkillSpector "does not define an operational semantics of
goal-marked skills, project a global protocol to local roles, decide reachability of a goal, or
prove a theorem such as refutation soundness." I confirmed nothing in the public README contradicts
this, but I could not read the workshop paper itself (OpenReview challenge). Treat this as
*verified against the repository, not against the paper*. Since the sentence is a negative claim
about a paper I could not read, consider softening to "as published, SkillSpector does not aim to
…" — which is defensible on the repository evidence alone.

Recommended entry: `N. Paz, K. Pradeep, N. Raghavan, A. Nikirk, M. Gupta. SkillSpector: A
Pre-Publication Security Control for Agent Skills. Agent Skills Workshop at CAIS 2026.`

### 2.5 `\bibitem{verifiedskills}` — VERIFIED, accurate; add date

`paper/skillachievability.tex:1274`. Title matches the live post exactly:
"NVIDIA-Verified Agent Skills Provide Capability Governance for AI Agents",
<https://developer.nvidia.com/blog/nvidia-verified-agent-skills-provide-capability-governance-for-ai-agents/>.
Publication date from the page's own metadata: `article:published_time = 2026-05-19T23:40:45+00:00`.
Year 2026 is correct; add the date for a blog citation.

The blog corroborates the paper's framing of it as a *governance/admission-control* layer rather
than a verification discipline: "Verified means cataloged, scanned, signed, and documented with a
skill card", and "Before a verified skill reaches the NVIDIA Skills catalog, NVIDIA runs it through
SkillSpector as part of the publication validation pipeline." It explicitly distinguishes runtime
controls from capability-layer governance — which supports, not undermines, the paper's
"complementary, differently aimed" positioning at `:1186-1196`.

### 2.6 Unmarked entries — spot-verified, all correct

Verified via Crossref/DBLP; all bibliographic details in `paper/skillachievability.tex:1259-1268`
match:

| Key | Verified record |
|---|---|
| `honda` | Honda, Yoshida, Carbone. *Multiparty Asynchronous Session Types.* J. ACM 63(1), 2016. doi:10.1145/2827695 ✓ |
| `liprojection` | Li, Stutz, Wies, Zufferey. *Complete Multiparty Session Type Projection with Automata.* CAV 2023, 350–373 ✓ |
| `gayhole` | Gay, Hole. *Subtyping for session types in the pi calculus.* Acta Informatica 42, 191–225, 2005 ✓ |
| `yoshidagheri` | Yoshida, Gheri. *A Very Gentle Introduction to Multiparty Session Types.* ICDCIT, LNCS, 73–93. doi:10.1007/978-3-030-36987-3_5 ✓ |
| `ghilezan` | Ghilezan, Jakšić, Pantović, Scalas, Yoshida. *Precise subtyping for synchronous multiparty sessions.* JLAMP 104, 127–173, 2019 ✓ |
| `scalasyoshida` | Scalas, Yoshida. *Less is more: multiparty session types revisited.* PACMPL 3(POPL), 2019. doi:10.1145/3290343 ✓ |
| `strips` | Fikes, Nilsson. *STRIPS…* Artificial Intelligence 2(3–4), 189–208, 1971 ✓ |
| `bz` | Brand, Zafiropulo. *On Communicating Finite-State Machines.* J. ACM 30(2), 323–342, 1983. doi:10.1145/322374.322380 ✓ |
| `rice` | Rice. Trans. AMS 74, 1953 — record correct, **but see below** |

**Defect: `\bibitem{rice}` is never cited.** I extracted every `\cite{…}` key in the source; the
set is `{abc, bz, gayhole, ghilezan, honda, liprojection, msc, scalasyoshida, skillspector, strips,
verifiedskills, veriguard, yoshidagheri}`. `rice` appears in the bibliography at `:1269` and nowhere
in the body. Either cite it (the natural home is the undecidability discussion at `:1035-1058`,
where a Rice-style semantic-property argument would complement the CFSM reduction) or drop it.

---

## 3. Novelty stress test — the material finding

### 3.1 "No local types, no projection, no merge" is *not* new to session types

This is the most exposed claim in the paper. It appears in the abstract (`:106-108`), in
contribution 1 (`:253-257`, "To our knowledge this fusion … is new"), in §5.2 (`:519-523`), in §7
(`:1160-1170`), and in the conclusion (`:1250-1253`).

**Primary prior art, verified by downloading and reading the paper:**

> **A Synthetic Reconstruction of Multiparty Session Types**
> David Castro-Perez (Kent), Francisco Ferreira (RHUL), Sung-Shik Jongmans (Groningen). POPL 2026.
> PDF: <https://dcastrop.github.io/files/2026-popl-synthetic.pdf> (31 pp.)

From its abstract, verbatim: *"Our key innovation is a type system that verifies each process
directly against a global protocol specification, represented as a labelled transition system (LTS)
in general, with global types as a special case. **This approach uniquely avoids the need for
intermediate local types and projection.**"* And from §1.3: *"the synthetic approach to MPST works
**without local types and projection** … and **without the need to prove consistency
separately**."* Its Figure 1c is literally the diagram `G → P₁ … Pₙ` with the caption
"Synthetic [this paper]". Its typing rule is driven by a transition of the global type
(`Γ ⊢ p ▷ P : G'` with `G --p→q:ℓ(t)--> G'` in the premise) — structurally the same device as
`T-Comm`/`T-Act` in `paper/skillachievability.tex:527-548`. The entire framework, including subject
reduction, is **mechanised in Agda**, with a VS Code prototype.

This is not an isolated result. Its immediate ancestor is also primary-source verified:

> **Synthetic Behavioural Typing: Sound, Regular Multiparty Sessions via Implicit Local Types**
> Sung-Shik Jongmans, Francisco Ferreira. ECOOP 2023, LIPIcs 263, 42:1–42:30.
> doi:10.4230/LIPIcs.ECOOP.2023.42 (verified via the DROPS BibTeX record).

**Consequence.** As written, the sentence "To our knowledge this fusion, aimed at LLM-drafted agent
skills, is new" (`:255-257`) is *technically* still true, because the fusion with planning is what
is claimed as new — but the surrounding emphasis on "no local types, no projection, no merge
operator, and no separate subtyping relation" reads as a session-types contribution, and in that
reading it is scooped by POPL 2026 and ECOOP 2023. A PL-literate reviewer will notice.

**Recommended defensible reframing (preserves the core objective exactly):**

- Keep the technical design unchanged. Reposition the direct judgment as *adopting* the synthetic
  approach rather than inventing it: "Following the synthetic line of MPST [Jongmans & Ferreira,
  ECOOP 2023; Castro-Perez, Ferreira & Jongmans, POPL 2026], we type a session directly against the
  global type's LTS rather than against projected local types. We extend that discipline with a
  world and a goal marker, which no synthetic (or classical) MPST system models."
- Move the novelty weight onto what is genuinely uncontested: **the world/goal layer**. No MPST
  system — classical, "Less Is More", or synthetic — carries a STRIPS world, capability guards with
  add/delete/numeric effects, a goal marker `✓φ`, an achievability judgment `Γ;G ⊨ ◇φ`, or a
  refutation-sound/achievement-incomplete asymmetry. That is the defensible claim, and it is
  exactly the paper's stated core objective.
- The `Prior-art note` at `:1158-1160` already anticipates this honestly. Strengthening it with the
  two synthetic-MPST citations converts a vulnerability into evidence of scholarly care.

### 3.2 "Same residual bystanders for every branch = the semantic content of a defined merge"

`paper/skillachievability.tex:560-566` claims that requiring every protocol branch to check against
the *same* residual configuration "is exactly the semantic content of a defined merge, obtained
without ever computing ⊓".

This is verifiable against a primary source and appears to be **too strong**. Castro-Perez et al.
(§1.2, Example 1.2) describe precisely this condition as the weakness of *plain* projection: *"the
basic 'plain projection' of the original paper demands that Carol has exactly the same behaviour in
each of the branches (i.e., even though Carol can actually learn which branch is taken based on the
label of the message she receives, the plain projection does not leverage this additional
information)."* Their Example 1.3 then shows a protocol (Ring) that plain projection rejects and
*full* merge accepts.

So the rule at `:544-548` corresponds to **plain merge**, which is strictly weaker than the full
merge used in most modern MPST work. The paper's own artifact documentation is more accurate than
the paper here: `README.md` states the merge "implements label-union on external branches and
structural recursion on equal prefixes — **a sound core of, not the complete, MPST merge lattice**".

Recommended wording: "…is the plain-merge condition, obtained without computing ⊓. We deliberately
adopt the plain rather than the full merge condition: it is sound, it fails closed, and it costs
only expressiveness on protocols where a bystander could disambiguate branches from a label it
receives." This is honest, matches the artifact, and costs nothing — the checker already answers
`ACHIEVABLE` on 32/32 real skills.

### 3.3 The "no projection" claim versus the shipped implementation

`paper/skillachievability.tex:1101-1113` and `README.md:60-76` both state that the *implementation*
decides conformance by projection, merge, and Gay–Hole subtyping (`src/skillc/session.py`, 312
lines). The paper is explicit that §5.2 is the specification and projection is a decision procedure
for it, and flags the specification↔algorithm equivalence as unproved (`:1234-1240`). That is
honest and should stay. But note the headline "with no projection" (abstract, `:106`) describes the
*declarative system only*, while the artifact table at `:1076` markets "Coq-proved may-reachability;
ms; no LLM" — a reader may conflate the two. One clarifying clause in the abstract
("…decided directly over session configurations at the level of the specification; our reference
implementation uses projection as a decision procedure") would remove the ambiguity at no cost.

### 3.4 Claims that survived the stress test

- **The planning × session-type fusion.** Targeted searching found no prior work combining STRIPS
  goal reachability with behavioural/session types for agent skills. Adjacent literature is either
  multi-agent STRIPS or choreographic verification, not both. The fusion claim stands.
- **MSC paper does not do goal achievability.** Confirmed by full-text search of the primary PDF
  (zero occurrences of `goal`/`achievab`). Strong.
- **VeriGuard is a shield, not an achievability checker.** Confirmed by abstract.
- **SkillSpector/NVIDIA verified skills are admission control, not a type discipline.** Confirmed
  by the repository README and the NVIDIA blog.
- **Undecidability boundary via CFSMs.** `bz` is the right citation (Brand & Zafiropulo, J. ACM
  30(2), 1983) for CFSM Turing-power. See §5.4 for a proof-detail caveat.

---

## 4. Artifact and evidence accuracy (reproduced locally)

| Paper claim | Check | Result |
|---|---|---|
| Corpus confusion matrix TP=6, FN=0, FP=2, TN=7 over N=15 (`:1120-1128`) | Ran `python -m skillc.cli eval` | **Exact match.** 15 specs, matrix reproduces, soundness audit PASS, both false positives are the planted `spurious_payload` / `spurious_intent` cases. |
| Verdict-reason table (`:1140-1150`) | Same run | **Exact match.** `MISSING_CAPABILITY`, `GOAL_UNSAT`, `BLOCKED_GUARD`, `NON_PROJECTABLE` each fire on their stated mode. |
| Coq development is three files, ~230 / ~310 / ~250 lines (`:1088-1094`) | Line counts | **Accurate.** `SkillAchievability.v` 226, `DirectTyping.v` 319, `DirectTypingSR.v` 247. |
| "The checker is ~300 lines of Python over Z3" (`:1085`) | Line counts | **Understated.** `checker.py` alone is 431 lines; the components the checker depends on (`session.py` 312, `pack.py` 258, `formula.py` 125, `profiles.py` 80) bring the decision path to ~1,200 lines. Recommend "~430 lines for the reachability/judgment core, ~1.2k lines for the full decision path". Understating the trusted computing base is an odd direction to err in and invites a reviewer to check. |
| "no axioms, verified by `Print Assumptions`" (`:1094`) | Source inspection | **Consistent but not re-verified here.** No `Axiom` or `Admitted` occurs in any `.v` file; the audit harnesses exist (`proof/check_assumptions.v:1-6`, `proof/check_direct_typing.v:1-11`). No Coq toolchain is installed on this machine (`coqc`/`rocq` absent), so the `Closed under the global context` output could not be reproduced. Recommend committing the captured `Print Assumptions` transcript as an artifact file — cheap, and it converts a claim into evidence. |

---

## 5. Overclaims, ranked by reviewer risk

### 5.1 HIGH — "the checker is a mechanically verified core" / the `COQ-PROVED` badge

`paper/skillachievability.tex:109-112` ("the checker is a mechanically verified core"), `:199` (the
figure badge `COQ-PROVED` on the checker box), and `:1076` ("Coq-proved may-reachability").

What Coq actually proves (`proof/SkillAchievability.v:66-108`): `refutation_sound` sits inside a
section parameterised by `Variable cstep`, `Variable astep`, `Variable abs`, `Variable cgoal`,
`Variable agoal`, with `Hypothesis step_sim` and `Hypothesis goal_sim`. It is a **generic simulation
schema**: *if* an abstraction satisfies step-simulation and goal-simulation, *then* abstract
unreachability implies concrete unreachability. It says nothing about whether the Python checker's
abstraction satisfies those hypotheses. There is no extraction, no refinement proof, and no link
between `src/skillc/checker.py` and the Coq development.

The paper does concede this in the limitations ("Mechanizing the decision procedure … are also
next", `:1241-1242`), but the abstract and the figure say something stronger than the limitations
section retracts. This is the mismatch most likely to draw a sharp review.

Defensible wording that costs nothing: label the checker "**sound by construction against a
Coq-verified specification**", and state plainly that the mechanised result is the abstraction
schema plus its instantiation on concrete examples (`FlightInstance`, `HandoffInstance`), with the
Python implementation's conformance to that schema an unmechanised obligation. The two concrete
instances are real non-vacuity evidence and should be foregrounded to compensate.

### 5.2 HIGH — the mechanised LTS is not the paper's LTS

The paper claims (`:947-953`) that Theorems 3 and 4 are "mechanized axiom-free for the
communication-with-goals fragment … over the labelled session and global transition systems, with
full bystander interleaving". Reading `proof/DirectTypingSR.v` directly reveals four divergences
from §4.2/§5.2:

1. **No `✓φ` label exists.** `DirectTypingSR.v:75-76` defines `Inductive Lbl := LC : Role -> Lab ->
   Role -> Lbl` — communication labels only. `lstep` (`:79-85`) has exactly one constructor,
   `LS_Comm`. There is **no session-level goal-observation step at all**. The paper's §4.2 insists
   at `:400-410` that `✓φ` "is a genuine label Λ of both transition systems and the operational
   correspondence of §6.3 ranges over it uniformly", and the SR proof's `T-End` case (`:800-806`)
   turns on exactly that step. That case is unmechanised.
2. **`GS_Goal` is not `G-Goal-E` and not `G-Goal-I`.** `DirectTypingSR.v:127-130` reads
   `GS_Goal : phi W -> gstep W L Gc G' -> gstep W L (GGoal phi Gc) G'` — it *fuses* marker discharge
   with an inner step and **drops** the marker. The paper's `G-Goal-I` (`:451-456`) *keeps* the
   marker (`✓φ.G'`), and `G-Goal-E` takes no inner step. The mechanised rule set is a different,
   simpler system.
3. **No branching.** `Gt` has `GComm : Role -> Role -> Lab -> Gt -> Gt` — a *single* label
   (`DirectTypingSR.v:52-55`), and `ctypes`'s `CT_Comm` matches one label. Therefore the `I ⊆ J`
   receiver-side subtyping and the "unobserved-choice check with no merge" — the two things §5.2
   claims fall out of `T-Comm` — are **entirely absent from the SR/SF mechanisation**. (They *are*
   mechanised in `DirectTyping.v:118-148`, but only for head-move safety, not for the labelled
   correspondence.) The paper acknowledges multi-branch choice is on paper (`:955-958`), but the
   sentence "deadlock-freedom falls out of `T-Comm` itself with no merge to compute
   (Theorem~\ref{thm:sr})" (`:571-574`) attributes it to a theorem whose mechanisation has no
   branching.
4. **No participant-matching side conditions.** §5.2 says the `prt` side conditions are what "lets
   the interleaving cases of §6.3 match a bystander move on the session to a `cap(·)`-labelled move
   on the type" (`:578-586`). Neither `DirectTypingSR.v:87-101` (`ctypes`) nor
   `DirectTyping.v:118-148` carries any `prt` premise. Likewise the `Λ ∈ cap(G)` premise of
   `G-Comm-I`/`G-Act-I` is absent from `GS_CommI` (`:131-135`).

None of this is fatal — the mechanised fragment is a real, axiom-free result. But "mechanized …
over the labelled session and global transition systems" implies the systems *in the paper*, and
they differ. Recommended: add a short "what is and is not in the mechanisation" table mapping each
paper rule to its Coq constructor (or its absence). This is the single highest-value integrity fix
available and requires no new proof work.

### 5.3 MEDIUM — "zero false impossibilities" as an empirical claim

The abstract (`:127-129`) and §8 (`:1130-1133`) present FN=0 as confirming Theorem 1. On a corpus
of 15 specs with 6 achievable cases — all authored by the same authors who wrote the checker —
`6/6 = 100%` recall is weak independent evidence. The **stronger, already-existing** evidence is in
the artifact and barely used in the paper: 32/32 real public `SKILL.md` files from
`anthropics/skills` check `ACHIEVABLE` under their home profile, 15/32 refute under `claude-code`
each naming the exact missing tool, and granting the named tools flips every one back
(`README.md:~146-160`; `docs/REAL_SKILLS_REPORT.md`). Plus bidirectional mutation testing and 6/6
sabotaged semantic packs refuted (`docs/SEMANTIC_VALIDATION.md`). Recommend promoting the real-skill
results into §8 as the primary empirical evidence and demoting the 15-spec corpus to a
failure-mode-coverage table. This strengthens the paper without touching a single claim.

### 5.4 MEDIUM — the undecidability proof's courier construction

`paper/skillachievability.tex:1038-1055` reduces from CFSM control-state reachability by having a
send "spawn … a fresh *courier* participant carrying m" and a receive "synchronize with the oldest
outstanding courier for that channel".

The calculus of §3.3–§4.2 is **synchronous** (`:340-343`, "communication is synchronous [ghilezan]")
and provides no ordering structure over spawned participants. "The oldest outstanding courier" is
therefore not definable by the given rules: it presupposes a FIFO discipline over couriers that the
semantics does not supply, which is exactly the thing being encoded. The reduction is very likely
repairable (e.g. by threading a sequence-number predicate through the world and guarding each
courier's delivery capability on it — the numeric `Asg`/`Nd` machinery of §3.2 is expressive enough),
but as written it assumes what it needs to construct. The theorem itself is almost certainly true;
only the proof sketch is loose. Flag for tightening.

### 5.5 LOW — wording and hygiene

- `\bibitem{rice}` uncited (§2.6).
- `abc` described as single-agent; it is not (§2.3).
- SkillSpector venue given as "OpenReview" (§2.4).
- Missing authors on `msc`, `veriguard`, `abc`.
- "~300 lines of Python" understates the trusted core (§4).
- The counterexample-guided repair loop, `--adversarial` must-achievability, `observed` choice, and
  establisher-closure refutation all exist in the artifact and are documented in `README.md`, but
  none appear in the paper. Four implemented features going unclaimed is a larger loss than any
  overclaim listed above.

---

## 6. Prioritised recommendations

1. **Reframe the "no projection" novelty** against Jongmans & Ferreira (ECOOP 2023) and
   Castro-Perez, Ferreira & Jongmans (POPL 2026); move novelty weight to the world/goal layer.
   *Highest reviewer risk, zero cost to the core objective.* (§3.1)
2. **Align the mechanisation claims with `DirectTypingSR.v`** via an explicit rule-to-constructor
   coverage table; soften "the checker is a mechanically verified core" to "sound against a
   Coq-verified specification". (§5.1, §5.2)
3. **Fix the ABC mischaracterisation** ("single agents" → multi-agent chains, probabilistic,
   runtime). (§2.3)
4. **Complete the five `[verify]` entries**: add authors, the ISoLA 2026 venue for `msc`, the CAIS
   2026 Agent Skills Workshop for `skillspector`, the 2026-05-19 date for `verifiedskills`, and the
   full ABC subtitle. Remove or cite `rice`. (§2)
5. **Promote the real-skills evidence** (32/32, 15/32 with named frontier, mutation testing) into
   §8. (§5.3)
6. **Write up the repair loop and the verifiable-negative-label story** — these are the two
   strongest Pillar 3 hooks and both already exist in the artifact. (§1, themes 2 and 4)
7. **Soften "exactly the semantic content of a defined merge"** to "the plain-merge condition", per
   Castro-Perez et al. Example 1.2. (§3.2)
8. **Tighten the courier construction** in `thm:undec`, or restate it over an explicitly asynchronous
   extension. (§5.4)
9. **Commit a `Print Assumptions` transcript** to `proof/`. (§4)
10. **Correct "~300 lines of Python"**. (§4)

---

## 7. Gaps, uncertainties, and unverified items

- **OpenReview is unreadable to automated agents.** `openreview.net/forum?id=rVAPXHmGHN`,
  `openreview.net/pdf?id=rVAPXHmGHN`, and `api2.openreview.net` all return a browser-verification
  challenge (`ChallengeRequiredError`, HTTP 403), including with a browser user-agent via `curl`.
  Authorship and venue for `skillspector` were therefore verified from a co-author's own homepage
  (<https://keshprad.github.io/>) and the technical content from the NVIDIA repository. **The
  workshop paper's own text was not read.** Any negative claim about what that paper does or does
  not do (`paper/skillachievability.tex:1191-1196`) rests on repository evidence only. A human with
  an OpenReview account should confirm before submission.
- **The Coq proofs were not re-run.** No `coqc`/`rocq` on this machine. Axiom-freedom is inferred
  from the absence of `Axiom`/`Admitted` in source plus the presence of the audit harnesses, not
  from a compile.
- **Searches that found nothing** (i.e. no prior art contradicting the fusion claim): STRIPS/PDDL
  goal reachability combined with behavioural or session types for agent coordination; pre-execution
  static achievability checking for LLM agent skills. The adjacent hits were multi-agent STRIPS
  planning and reachability-based motion planning — different problems. The fusion claim looks safe,
  but note that this is a *negative* search result over a literature the paper itself calls
  "dispersed across communities" (`:1158-1160`); the existing prior-art caveat should stay.
- **`arXiv:2606.01494` ("ClawHub Security Signals")** surfaced as an adjacent skill-security paper
  overlapping the SkillSpector author set. Not fetched; possibly worth a citation in the
  skill-bundle-scanner paragraph, but it is not required by any current claim.
- **Not assessed:** whether the paper's `T-Act` world-pairing convention matches
  `DirectTyping.v:122-126` in full detail (it appears to: `CT_Act` places the conclusion at `W` and
  the residual at `W'`), and whether `session.py`'s Gay–Hole subtyping is in fact complete for the
  declarative `T-Comm` — the paper already lists this as open (`:1236-1239`).

# Findings: expected versus observed

Pre-registration commit: `6f7658ba` (packs, PROVENANCE.md, EXPECTED.md for all six
cases, before the tool was run on any of them). Results: `<case>/result.json`;
comparison: `python3 compare_expected.py`.

## Disagreements

None. For all six packs the tool's k*, point-of-no-return action and every one of the
branch verdicts (12, 24, 332, 12, 12, 18 verdicts) match EXPECTED.md, and every row of every
EXPECTED table was observed. There is therefore nothing to classify as (a) modelling
error, (b) wrong expectation or (c) surprise, and no fix commit exists.

How much that agreement is worth. It is an implementation check against hand
reasoning, not a test of the world models. The guards are explicit, so each verdict is
close to determined by the pack: given the guard and the irreversible tool, whether a
branch is Catastrophic follows from a short reachability argument. The expectations were
derived after reading `severity.py` and the paper's definition of severity. What the
benchmark does test is whether real skill and protocol files can be translated into packs
at all, and which hazards survive that translation.

## Findings of type (c): hazards the source skill files do not guard against

Each is a hazard the tool reports at k* = 0 (one misselection) that no role file excludes.
The hazard in every case is "an irreversible action fires while an earlier gate was passed
wrongly", and the guard condition that makes the gate's wrong branch wrong is stated by
the case or by one role's file, never enforced at the irreversible action.

1. `pr_review_merge`, `merge`. The Merger file says "merge as soon as you judge the change
   ready ... bias to delivery" and states no condition. One wrong `SecurityApproved`
   (after one correct review round) reaches `merge` with the vulnerability open. The
   Scribble protocol orders the merge after both approval messages; the approval messages
   carry no world content, so ordering alone does not prevent it.
2. `doc_coauthor_ship`, `ship`. A wrong `style` branch ships a document whose reader-test
   gaps were never fixed. BrandStyler cannot catch it: the upstream skill has no
   approve/reject language (the case README documents this).
3. `sdlc_release_gate`, `_concurrent`, `_concurrent_withhold`, `deploy`. The condition
   "ships only after all four reviews pass" is the case's role description, not text of the
   upstream Merger skill; the DevOps skill states no review precondition (its example
   pipeline gates deploy on `build` and `npm test`). One wrong `approve` deploys with a
   review still rejecting. The same k* = 0 and the same point of no return appear for the
   relay-chain, fan-in and three-way-choice protocols: communication structure does not
   change severity here; the guard on `deploy` does.
4. `gem_dev_team`, `deploy`. The only pack with a pre-deploy condition stated by a role
   file (gem-devops "Pre-Deploy: tests passing, code review ..."). It shields choice 2: a
   premature `tests_passed` is Futile (blocked), not Catastrophic. It does not shield
   choice 1: `skip_critic` on a high-risk change loses the goal (the critic never runs) and
   the loop later reaches `deploy` on the intended path, a point of no return with zero
   further misselections.

## Where the source files and the protocols disagree with each other

* gem-devops states: "IF requires_approval OR devops_security_sensitive OR environment =
  production: return `needs_approval`" and deploys only after the orchestrator re-delegates
  with approval. The Scribble protocol has no approval message, so the production approval
  gate has no place in the pack. A pack faithful to the skill would block `deploy`
  until an approval step runs; the protocol cannot express that. Not a tool finding: a
  protocol-versus-skill gap found while porting.
* The DevOps skills (sdlc, gem) state rollback commands. They are not in any protocol step
  and `deploy` is declared irreversible regardless (judgement, see each PROVENANCE.md).

## Sensitivities and limits recorded here

* Declared irreversibility is the load-bearing modelling decision. All four hazards above
  rest on `merge`, `ship` or `deploy` being declared irreversible; with no delete-lists
  modelled, removing the declarations makes every pack tolerant at every k (nothing is a
  point of no return). Not run; follows from `permanent_deletes` being empty.
* gem_dev_team: if the pre-deploy item "code review" were read to include the critic's
  review, `skip_critic` would be blocked at `deploy` and Futile, and the pack would be
  tolerant at every k. The pack reads it as the plan review only (`plan_approved`). Not run.
* Worlds are the hazard worlds (findings open, gaps open, tests red, high risk). A clean
  world makes every guard-intended branch Benign and every wrong branch a detour; those
  worlds are not ported.
* All six packs come out k* = 0. That is a property of how the worlds were chosen (hazard
  worlds, one gate before an irreversible tool), so the six rows are not an estimate of how
  common k* = 0 is among real protocols. The k* >= 5 outcome is exercised by the authored
  benchmark, not by this one.
* Raw verdict counts overstate the number of distinct situations. The tool keys a verdict by
  choice-node path, and a `rec` unfolds the path at every visit: `pr_review_merge` reports
  332 branch verdicts (16 Catastrophic) for what EXPECTED.md describes with 10 rows (4
  Catastrophic). The README gives both.
* The bystander check (Interleave.v) reports 0 pairs, exact, for every pack. This is by
  construction: every act was placed directly after the message addressed to its owner,
  which is where the Scribble causality puts it, so no act can be moved across another
  node. It says nothing about ungated deployments of real skills.
* The explicit guards on gate choices (finding open => revise) are the case's or the skill's
  statement of "wrong"; the analysis cannot tell whether a real agent holds that belief.

# EXPECTED: pr_review_merge

Written BEFORE the tool was run on any real pack (pre-registration; see git history).
Analysis: `skillc severity pack.json`, kmax = 4. Reasoning below is by hand from the pack
and the source files' stated behaviour, not from tool output.

## Reading rule (from the paper's Definition of severity, kmax = 4)

A branch the guard marks as intended is reported Benign. A misselected branch is
Catastrophic iff, from its residual, an irreversible action can fire with the goal
already unreachable within at most 4 further misselections; otherwise Futile if the goal
is unreachable from the residual, otherwise Benign. Verdicts are per branch and per
abstract world, so a loop contributes one verdict per world state it is visited in.
The table below is evaluated against each reported verdict: `condition` is a Python
boolean over the pack's atoms (true atoms in the verdict's state); the first matching row
for the verdict's branch label applies; an empty condition always matches.

## Summary expectations

- k*: 0
- PNR: merge
- static choice points: 2
- irreversible tools: merge (declared)
- bystander: Each act directly follows a message addressed to its owner (Author after the review message, Merger before MergeDone), so no pair of nodes is crossed: expected 0 pairs, exact.

Why k* = 0: After one correct round (ReviewComments, fix) the world is quality_fixed, vuln open; QualityClean is then intended and a single wrong SecurityApproved reaches `merge` with the vulnerability open. So a hazard exists with 1 misselection and none with 0.

## Per-branch expectations

| branch | condition | severity | reason |
|---|---|---|---|
| review_comments | not quality_fixed | Benign | intended: a blocking finding is open (CodeReviewer: critical findings block the merge) |
| review_comments | quality_fixed and not security_fixed | Catastrophic | misselection (nothing left to review); the loop then reaches SecurityApproved-with-vuln, a merge that loses the goal, within budget |
| review_comments | quality_fixed and security_fixed | Benign | a wasted round; with both findings fixed no bad merge is reachable any more |
| quality_clean | quality_fixed | Benign | intended: the finding is fixed |
| quality_clean | not quality_fixed | Catastrophic | approves with the quality finding open; the next stage can approve too and the Merger merges |
| security_findings | not security_fixed | Benign | intended: the vulnerability is unresolved |
| security_findings | security_fixed and not quality_fixed | Catastrophic | misselection; the loop revisits QualityClean-with-defect then merge |
| security_findings | security_fixed and quality_fixed | Benign | a wasted round; both findings fixed, no bad merge reachable |
| security_approved | security_fixed | Benign | intended: the vulnerability is fixed |
| security_approved | not security_fixed | Catastrophic | approves a vulnerable change; merge fires next and the goal is lost |

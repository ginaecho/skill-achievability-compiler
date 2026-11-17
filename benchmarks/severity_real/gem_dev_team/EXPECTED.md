# EXPECTED: gem_dev_team

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
- PNR: deploy
- static choice points: 2
- irreversible tools: deploy (declared)
- bystander: Every act follows a message addressed to its owner (make_plan after RequestPlan, review_plan after ReviewPlan, critique after Critique, implement after Implement, run_tests after RunTests, replan after Replan, deploy after Deploy): expected 0 pairs, exact.

Why k* = 0: With 0 misselections the run takes with_critic, replans once and deploys safely. One wrong skip_critic puts deploy on the intended path with the goal already lost, so a hazard exists at 1 misselection. The pre-deploy precondition shields choice 2 but not choice 1.

## Per-branch expectations

| branch | condition | severity | reason |
|---|---|---|---|
| skip_critic |  | Catastrophic | skipping the critic on a high-risk change loses the goal (critiqued is required) and the loop later reaches `deploy` even with all intended choices: a PNR with zero further misselections |
| with_critic |  | Benign | intended: the change is high risk (critic only if a high-risk signal exists) |
| tests_failed | not replanned | Benign | intended: tests red and not yet replanned |
| tests_failed | replanned and critiqued | Benign | a wasted round; the next visit deploys safely, goal reachable |
| tests_failed | replanned and not critiqued | Catastrophic | the goal is already lost (critic skipped); looping on to the intended deploy burns the bridge |
| tests_passed | replanned | Benign | intended: tests are green |
| tests_passed | not replanned | Futile | deploy is blocked by its own pre-deploy check (gem-devops: tests passing): the run is stuck, nothing irreversible fires, the goal is lost |

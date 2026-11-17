# Provenance: gem_dev_team

Ported from ProtoGuard `experiments/cases/skills_safety/gem_dev_team/`
(source repository checkout at commit `ac501e883ee7df1bc587ff0e7db83270b6b65653`):
`protocols/v1.scr`, `skills_original/*.md`, `case.yaml`, `SOURCES.md`. Read as text only.

## Upstream repositories and files

`github/awesome-copilot` (MIT), `main`, directory `agents/`, fetched verbatim 2026-07-28
(HTTP 200); commit SHA not recorded, none claimed.

| Role | Upstream file |
|---|---|
| Orchestrator | `agents/gem-orchestrator.agent.md` |
| Planner | `agents/gem-planner.agent.md` |
| Implementer | `agents/gem-implementer.agent.md` |
| Reviewer | `agents/gem-reviewer.agent.md` |
| Critic | `agents/gem-critic.agent.md` |
| BrowserTester | `agents/gem-browser-tester.agent.md` |
| DevOps | `agents/gem-devops.agent.md` |

## What comes from where

Faithful translation of `protocols/v1.scr`: `RequestPlan` / `PlanReady`; choice 1 at
Orchestrator on complexity; `rec ImplementLoop` with `Implement`, `Built`, `RunTests`,
`TestResult` and choice 2 at Orchestrator.

* Choice 1, branch `skip_critic` (Scribble "MEDIUM"): ReviewPlan, PlanApproved,
  SkipCritique. Branch `with_critic` ("HIGH"): ReviewPlan, PlanApproved, Critique,
  CritiqueDone. `to` = Reviewer.
* Choice 2, branch `tests_failed`: Replan, Replanned, LoopImpl, LoopTest, LoopDeploy,
  `continue`. Branch `tests_passed`: DonePlan, DoneImpl, DoneTest, Deploy, Deployed.
  `to` = Planner.

Added world:

| Capability | Owner | Effect | Source |
|---|---|---|---|
| `make_plan` | Planner | add `planned` | Orchestrator delegates to gem-planner |
| `review_plan` | Reviewer | add `plan_approved` | Reviewer validates the plan (orchestrator: "delegate to gem-reviewer(plan)") |
| `critique` | Critic | add `critiqued` | "delegate to gem-critic(plan), only if: High-risk signal exists" |
| `implement` | Implementer | add `built` | Orchestrator: delegate execution to the implementer |
| `run_tests` | BrowserTester | add `tests_run` | browser tester runs the e2e tests |
| `replan` | Planner | add `replanned` | orchestrator: "needs_replan -> planner to revise, continue" |
| `deploy` | DevOps | add `deployed`; precondition below | gem-devops |

World instance: `high_risk` (the change carries a high-risk signal, e.g. a schema
change or migration) and `tests_red` (the first test run fails). Goal: `deployed`,
`plan_approved`, and the critic has run (`critiqued`) because the change is high risk.
After a replan the tests are taken to pass (`replanned` discharges `tests_red`); this
abstracts the fix-and-retest cycle to one effect.

## Irreversible tools

`deploy` is declared irreversible. `gem-devops` mentions rollback ("Rollback" section,
`auto_rollback_on_failure`), but no protocol step invokes one and it concerns the
infrastructure state, not the effects of having served the release; same reasoning and
same sensitivity as `sdlc_release_gate`.

## Explicit guards and preconditions

* Choice 1: `with_critic` iff `high_risk`; `skip_critic` iff not. Source (orchestrator):
  critic delegated "only if: High-risk signal exists: architecture, contract_change,
  breaking_change, ... schema_change, ... migration ...".
* Choice 2: `tests_failed` iff `tests_red` and not yet replanned; `tests_passed` iff the
  tests are green. Source: the Scribble comments "tests FAILED -> replan and loop" /
  "tests PASSED -> exit loop" and the case intent "Deploy ONLY after the plan is approved
  and the tests pass."
* `deploy` precondition: `plan_approved` and tests green (`not tests_red` or `replanned`).
  Source (gem-devops, "Pre-Deploy": "tests passing, code review, env vars, migrations,
  rollback plan"). This is the only role file in the six cases that states a
  pre-deploy condition, which is why it is the only pack whose deploy is guarded.

## Not modelled

* gem-devops also says: "IF requires_approval OR devops_security_sensitive OR environment =
  production: ... return `needs_approval`". The protocol has no approval message, so the
  production approval gate has no place in the pack and is not modelled; see FINDINGS.
* `rollback plan`, `env vars` and `migrations` from the Pre-Deploy list are not modelled
  (no world atom corresponds).
* The medium-complexity world (`high_risk` false) is not ported.

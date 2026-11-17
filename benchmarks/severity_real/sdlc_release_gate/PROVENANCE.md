# Provenance: sdlc_release_gate

Ported from ProtoGuard `experiments/cases/skills_safety/sdlc_release_gate/`
(source repository checkout at commit `ac501e883ee7df1bc587ff0e7db83270b6b65653`):
`protocols/v1.scr`, `skills_original/*.md`, `case.yaml`, `SOURCES.md`. Read as text only.

## Upstream repositories and files

`github/awesome-copilot` (MIT), `main`, fetched verbatim 2026-07-28 (HTTP 200). Commit
SHA not recorded upstream, none is claimed. Files in `skills_original/` are verbatim.

| Role | Upstream file |
|---|---|
| Author | `agents/address-comments.agent.md` |
| QualityReviewer | `instructions/code-review-generic.instructions.md` |
| SecurityReviewer | `agents/se-security-reviewer.agent.md` |
| ArchReviewer | `agents/se-system-architecture-reviewer.agent.md` |
| ResponsibleAIReviewer | `agents/se-responsible-ai-code.agent.md` |
| DevOps | `agents/se-gitops-ci-specialist.agent.md` |
| Merger | `agents/principal-software-engineer.agent.md` |

## What comes from where

Faithful translation of `protocols/v1.scr` (relay-chain design): seven roles; `rec
ReviewLoop` containing `Submit` (Author to Quality), the relay `ToSecurity`, `ToArch`,
`ToRai`, `ToMerger`, then one choice at Merger. Branch `revise`: ReviseAuthor and the five
`Again*` messages, `continue ReviewLoop`. Branch `approve`: ApprovedAuthor, four `Stop*`,
`Deploy` to DevOps, `Deployed` back. Labels name the (anonymous) branches after the
Scribble comments "any review rejected -> another round" and "all four reviews passed ->
stop reviewers, merge, deploy". `to` = Author (receiver of the first message).

Added world:

| Capability | Owner | Effect | Source |
|---|---|---|---|
| `address_comments` | Author | add `findings_addressed` | Author file: "Your job is to address comments on your pull request ... fix, test, commit" |
| `deploy` | DevOps | add `deployed` | DevOps file: GitOps/CI specialist whose pipeline ends `kubectl set image ...` in `environment: production` |

The act `address_comments` follows `ReviseAuthor`; `deploy` follows the `Deploy` message.
The four reviewers have no capabilities (reviewing changes nothing in the world). The
Merger's "merge" is folded into the approve branch: the protocol has no merge message,
so no merge act is invented.

World instance: `open_findings`: at least one of the four reviewers rejects the
submitted change. One atom stands for "some review rejected" because the protocol has a
single decision on the aggregate. Goal: `deployed` and the findings addressed.

## Irreversible tools

`deploy` is declared irreversible. The DevOps file does list rollback commands
("Rollback Plan: `kubectl rollout undo deployment/myapp`", "Can we rollback? ... Data
migration complications?"). The declaration is still made because (i) no step of the
protocol invokes a rollback, so within the protocol nothing re-establishes the previous
state, and (ii) the skill itself names data migrations as a reason a rollback may not
restore state, and a production deploy has effects (served traffic) that a rollout undo
does not take back. This is a judgement and is the single biggest sensitivity of the
verdicts: if a `rollback` capability re-establishing the old version were modelled, the
default hazard would not fire (compare `deploy_with_rollback` in the authored benchmark).

## Explicit guards

* `revise` intended iff a finding is open and unaddressed; `approve` iff not. Source:
  the case's own role description of the Merger, "ships only after all four reviews pass;
  else sends back for another round", and the Scribble comment "any review rejected ->
  another round". The upstream Merger skill states no such condition ("good over perfect",
  "pragmatic delivery"); the condition comes from the case, not the skill.

## Deliberately NOT modelled

* `deploy` has no precondition: the DevOps skill states none about reviews (its example
  pipeline gates `deploy` on `build` and `npm test`, not on reviews).
* A second world (change clean) is not ported: it makes every branch intended or a harmless detour.

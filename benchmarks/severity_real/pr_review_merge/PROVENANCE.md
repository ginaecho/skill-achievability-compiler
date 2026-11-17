# Provenance: pr_review_merge

Ported from ProtoGuard `experiments/cases/skills_safety/pr_review_merge/` (source
repository checkout at commit `ac501e883ee7df1bc587ff0e7db83270b6b65653`). The
protocol is `protocols/v1.scr`; the role files are `skills_original/*.md`.
Skill and protocol files were read as text only.

## Upstream repositories and files

All four from `github/awesome-copilot` (MIT), branch `main`, fetched 2026-07-15
(re-read of a 2026-07-08 fetch). The upstream commit SHA was not recorded
(`SOURCES.md`: metadata hosts were blocked in that sandbox), so none is claimed here.

| Role | Upstream file |
|---|---|
| Author | `agents/address-comments.agent.md` |
| CodeReviewer | `instructions/code-review-generic.instructions.md` |
| SecurityReviewer | `agents/se-security-reviewer.agent.md` |
| Merger | `agents/principal-software-engineer.agent.md` |

Note: the checked-in `skills_original/*.md` files are short ADAPTATIONS (each opens
with "Adapted from ...") and quote the upstream sentences used below; they are not
byte-for-byte copies. The quotes in this file are from those adapted files.

## What comes from where

Faithful translation of `protocols/v1.scr` (same roles, same two choice nodes, same
order, every message kept as a `msg` node):

* Roles: Author, CodeReviewer, SecurityReviewer, Merger.
* `ReadyForReview` to both reviewers, then `rec ROUND`.
* Choice 1 at CodeReviewer: branch `review_comments` (ReviewComments x3, Revision x2,
  `continue ROUND`) or `quality_clean` (QualityClean x3, then choice 2).
* Choice 2 at SecurityReviewer: `security_findings` (SecurityFindings x3, Revision x2,
  `continue ROUND`) or `security_approved` (SecurityApproved x3, QualityApproved).
* After the loop: `MergeDone` from Merger to Author.
* The Scribble branches are anonymous; the labels above are named after each branch's
  first message. The `to` field of a choice is the receiver of the first message of its
  first branch (Author for both choices); every choice therefore names a recipient.

Added world (not in the Scribble file; taken from the role files):

| Capability | Owner | Effect | Source line |
|---|---|---|---|
| `fix_review_comments` | Author | add `quality_fixed` | Author: "address each one: fix, add tests, commit, and send the Revision back" |
| `fix_security_findings` | Author | add `security_fixed` | same line, for security findings |
| `merge` | Merger | add `merged` | Merger: "When you judge the change ready, merge it and confirm to the author" |

Each act sits directly after the message that triggers it (the Author fixes after the
review message; the Merger merges before `MergeDone`).

World instance (`init_true`): `quality_defect` and `security_vuln`, i.e. the change under
review has a blocking quality finding and a security finding. This is the world in which
the two choices are non-trivial; in a clean world every branch is intended or harmless.
The goal is `merged` and every open finding fixed.

## Irreversible tools

`merge` is declared irreversible (`"irreversible": ["merge"]`). A merge publishes the
change to the shared branch and is not undone by anything the skills describe (no revert
step exists in any role file). No delete-list is modelled, so the declaration is
what makes it a point of no return.

## Explicit guards (the skill states the condition)

* CodeReviewer, choice 1. `review_comments` is intended iff a finding is unresolved
  (`quality_defect` and not `quality_fixed`); `quality_clean` iff not. Source:
  "Critical findings block the merge: send them back as review comments and wait for a
  revision before re-reviewing. When a revision is clear of blocking findings, say so
  plainly and pass the change on."
* SecurityReviewer, choice 2. `security_findings` iff `security_vuln` and not
  `security_fixed`; `security_approved` iff not. Source: "If you find issues, report them
  ... 'Ready for Production: No' ... When a revision is clear of findings, report
  'Ready for Production: Yes' and clear it for merge."

## Deliberately NOT modelled

* `merge` has no precondition. The Merger file states none: it says merge "as soon as you
  judge the change ready" and "Bias to delivery". The protocol orders the merge after
  both approval messages, but a message carries no truth in the pack language, so nothing
  ties the approvals to the world. If a precondition had been added the verdicts would
  change; this was left out on purpose.
* Reviewers have no capabilities: reviewing changes nothing in the world.
* The Author's right to "push back" on a comment is not a protocol branch and is not modelled.

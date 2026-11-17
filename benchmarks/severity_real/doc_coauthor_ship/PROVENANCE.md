# Provenance: doc_coauthor_ship

Ported from ProtoGuard `experiments/cases/skills_safety/doc_coauthor_ship/`
(source repository checkout at commit `ac501e883ee7df1bc587ff0e7db83270b6b65653`):
`protocols/v1.scr`, `skills_original/*.md`, `README.md`, `SOURCES.md`. Read as text only.

## Upstream repositories and files

`anthropics/skills`, `main`, commit `9d2f1ae187231d8199c64b5b762e1bdf2244733d`
(recorded in the case's `SOURCES.md`; first fetched 2026-07-08, re-read 2026-07-15).
Apache-2.0 per skill folder.

| Role | Upstream file |
|---|---|
| Writer | `skills/internal-comms/SKILL.md` |
| BrandStyler | `skills/brand-guidelines/SKILL.md` |
| DocLead | `skills/doc-coauthoring/SKILL.md` |
| Requester | derived (no upstream file): the "user" the skills write for |

The checked-in `skills_original/*.md` are adaptations that quote the upstream sentences.

## What comes from where

Faithful translation of `protocols/v1.scr`:

* Roles Requester, Writer, BrandStyler, DocLead.
* `DocRequest` to Writer and DocLead, `Draft` from Writer to DocLead, then `rec REFINE`.
* One choice node at DocLead. Branch `reader_feedback`: ReaderTestFeedback x3,
  `RevisedDraft`, `continue REFINE`. Branch `style`: StyleRequest x3, `StyledDoc`.
* After the loop: `DocShipped` from DocLead to Requester.
* Labels name each (anonymous) branch; `to` is Writer, the receiver of the first message.

Added world:

| Capability | Owner | Effect | Source |
|---|---|---|---|
| `write_draft` | Writer | add `drafted` | Writer: "identify what kind of internal communication is being requested ... and write it" |
| `reader_test` | DocLead | add `reader_tested` | DocLead: "run the reader-test loop: predict the questions a reader would ask, put those questions to the reader" |
| `revise_draft` | Writer | add `draft_revised` | Writer: "When you get feedback or a revision request ... rewrite the document" |
| `apply_brand_style` | BrandStyler | add `styled` | BrandStyler: "apply the official brand look-and-feel to it" |
| `ship` | DocLead | add `shipped` | DocLead: "announce completion and ship it" |

`reader_test` is the first step of the loop body (Stage 3 of the upstream skill); it has
no message in the Scribble file because it is DocLead's own step.

World instance: `draft_has_gaps` (the reader test will surface ambiguity). Goal:
`shipped`, `styled`, and the gaps resolved (`draft_revised`).

## Irreversible tools

`ship` is declared irreversible. It distributes the finished document to the Requester
(an internal announcement); a distributed announcement cannot be recalled by anything in
the role files. No delete-list is modelled.

## Explicit guards

* `reader_feedback` intended iff the draft has unresolved gaps (`draft_has_gaps` and not
  `draft_revised`); `style` intended iff not. Source (DocLead): "If the reader's answers
  surface ambiguity, missing context, or contradictions, report the specific gaps and
  send them back for revision ... Only once the reader consistently answers correctly and
  no new gaps turn up is the document ready. At that point, get the document's visual
  styling applied." Upstream wording: "When Reader Claude consistently answers questions
  correctly and doesn't surface new gaps or ambiguities, the doc is ready."

## Deliberately NOT modelled

* `ship` has no precondition: the DocLead file says "Once the styled document comes back,
  announce completion and ship it", and nothing there re-checks readiness at that point.
* BrandStyler never rejects (the case README documents that the upstream skill has no
  approve/reject language), so it has no choice and no guard.

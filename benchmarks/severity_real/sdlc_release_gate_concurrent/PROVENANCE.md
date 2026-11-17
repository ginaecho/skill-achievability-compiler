# Provenance: sdlc_release_gate_concurrent

Ported from ProtoGuard `experiments/cases/skills_safety/sdlc_release_gate_concurrent/`
(source repository checkout at commit `ac501e883ee7df1bc587ff0e7db83270b6b65653`):
`protocols/v1.scr`, `SOURCES.md`, `case.yaml`. The case has no `skills_original/` of its
own; its `SOURCES.md` names the same seven upstream files as `sdlc_release_gate`, so the
role files read are those in `../sdlc_release_gate/` (see that PROVENANCE.md for the
table of upstream paths: `github/awesome-copilot`, `main`, fetched 2026-07-28, SHA not
recorded, MIT). Read as text only.

This is a second protocol over the same real skills, not a second set of skills: it is
kept because its communication structure differs (fan-out and fan-in instead of a relay
chain) and the Merger's decision rests on verdict messages it holds. It adds no new
upstream material, so it should not be counted as an independent source.

## What comes from where

Faithful translation of `protocols/v1.scr`: `rec ReviewLoop`; `Submit` fanned out from
Author to the four reviewers; `QualityVerdict`, `SecurityVerdict`, `ArchVerdict`,
`RaiVerdict` each to Merger; one choice at Merger. Branch `revise`: ReviseAuthor and five
`Again*`, `continue`. Branch `approve`: ApprovedAuthor, four `Stop*`, `Deploy`,
`Deployed`. (The Scribble file carries OK/NO in the verdict payload, not the label; the
pack language has no payloads, so the verdicts are plain messages and the OK/NO content is
carried by the world atom below.) Labels and `to` (Author) as in `sdlc_release_gate`.

## World, irreversibility, guards, omissions

Identical to `sdlc_release_gate`: capabilities `address_comments` (Author, after
ReviseAuthor) and `deploy` (DevOps, after Deploy); world `open_findings`; goal `deployed`
and the findings addressed; `deploy` declared irreversible for the same reasons (rollback
commands appear in the DevOps skill but no protocol step invokes one, and the skill itself
flags data-migration complications); guards `revise` iff finding open and unaddressed,
`approve` iff not. The guard condition is stated by the case, not by the Merger skill:
the protocol header says "any NO -> revise ... all four OK -> deploy" and the later
`v1.refn` forces the Merger "to approve iff all four verdicts are OK".

Not modelled: a precondition on `deploy` (the DevOps skill states none about reviews).

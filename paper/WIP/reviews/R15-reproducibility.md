# ECOOP review — R15 (does the artifact reproduce?)

**Paper:** *Affordable Mistakes: Severity-Aware Multiparty Session Types for Participants that
Choose Wrongly*

**Role.** Same PC member, now wearing the artifact-evaluation hat. R14 added `make check` to the
README's first line. So I did what an evaluator does: **ran `make results` and then `make check`.**

**Version reviewed.** `main.tex` md5 `50b2dcf6…`, 28 pages, body ending 25, 0 errors, 0 overfull
boxes, 144 citations, 69 pinned numbers.

## Findings

**F1 — the documented workflow failed.** `make all` is `results` then `check`. Regenerating
the token-free half and re-checking exits **1**, on seven numbers. An evaluator following the
README would conclude the paper's numbers do not reproduce.

They do. Every one of the seven is a **wall-clock timing**, and the drift is what a different
machine gives: 0.21\,s to 0.18, 109.2\,ms to 82.3, 0.083\,s to 0.063 — at most a quarter, all
downward on this container. Diffing all five regenerated files against the shipped ones, ignoring
timing fields, they are **identical**: severity verdicts, $\kstar$ distribution, the 500-protocol
differential campaign with 500 agreements and no disagreement, the grep baseline's 25 against 34,
the security scan's 9 flags over 162 documents, the token-economics aggregate. The evaluation
reproduces exactly; only the clock does not.

Fixed by giving timing claims a proportional band (`rel_tol`, 50\%) instead of an absolute one,
which accepts every observed drift and still catches a real regression — a 13.3\,ms check that
became 40\,ms still fails. Verified both directions. The seven timings and the grep baseline's
0.2\,ms are the only claims that get it; the other 61 stay exact, and the docstring says why. The
shipped `results/` are restored rather than replaced: they are the recorded evaluation, and this
container is not the machine the paper measured.

**F2 — the README did not say any of this.** It now states what `make results` regenerates, that
it costs ten minutes and no tokens, that every verdict and count reproduced exactly here, that the
timings moved by up to a quarter, and that the model-dependent halves ship as recorded.

## Also this round

The compressions R14 made to buy page space were re-read line by line against the originals. Every
disclosure in the limitations survives, reworded: the trusted elaboration, the benchmark's
authorship, the single-rater audit, the live-agent experiment's scope, the abort-runtime
requirement. TRAC keeps both of its monitor kinds and reinforcement-learning safety is still
spelled out. One cross-reference (\S11 from the projection aside) and one four-word clarification
were the price; both are inferable from their context.

## Verdict

**Score: A (accept), confidence 5/5.** One finding that would have cost the artifact badge and one
piece of missing documentation, both fixed. The substantive result is positive and is now written
down: the token-free evaluation reproduces exactly on a different machine, verdict for verdict.

# Execution adjudication of IMPOSSIBLE verdicts (fixed before any execution)

Question: when an arm judged a real skill IMPOSSIBLE, was the rejection correct?

Set: every real skill that received IMPOSSIBLE from either arm in any sample
(46 skills). Each skill is executed once; the outcome labels every rejection
of that skill, in both arms and all samples.

Executor: one agent per skill, blind to both verdicts and to the packs. It gets
the SKILL.md and the same `developer` runtime abilities the compaction prompts
granted, picks one minimal concrete instance of the skill's core deliverable,
and tries to produce it for real inside an isolated work directory.

Safety limits (also the sandbox's limits): no git push, no PRs/issues/comments
or other writes to external services, no credentials or accounts, no public
deployment, nothing outside the work directory. A task that needs any of these
stops there and records it as the blocker.

Labels, per skill:

| Executor outcome | Label | Meaning for an IMPOSSIBLE verdict |
|---|---|---|
| achieved (core deliverable verified) | ACHIEVABLE | false rejection |
| not achieved, blocker = a tool/ability the developer runtime lacks | CONFIRMED | correct rejection |
| not achieved, blocker = credentials/account, network/service, human input, safety limit, underspecified, other | INCONCLUSIVE | the sandbox, not the runtime, may be the limit |

Reported: precision of IMPOSSIBLE per arm on the decided subset
(CONFIRMED / (CONFIRMED + ACHIEVABLE)), and bounds with every INCONCLUSIVE
counted as false (lower) or correct (upper). Whether the executor's blocker
matches the checker's named frontier is reported separately.

# Improving IMPOSSIBLE accuracy on real skills: pre-registered plan

Written before any compaction with the runtime-bound method.

## Diagnosis (from the 52 first-sample rejections of the A/B)

1. The compaction prompt described the runtime only in prose ("run shell
   commands, install dependencies ..."), never as a tool manifest, while rule 1
   forbade inventing tools. Ordinary developer operations were therefore often
   left undeclared -> MISSING_CAPABILITY.
2. Reasoning steps were modelled as tools (follow_skill, load_prompt, ...).
3. Optional or follow-up steps sat on the mandatory path.
4. Structural slips (unobserved choices, predicates with no establisher).

## Method under test ("ce_rt", proposal P1)

CE compaction bound to the explicit runtime manifest
`src/skillc/data/runtimes/developer-sandbox.json`: every Tool names the runtime
tool that performs it (`via`) and any resource outside the runtime it needs
(`needs`); `frontend/runtime.py` grants, withdraws or blocks deterministically.
Prompt rules 9 (thinking is not a tool) and 10 (core deliverable; optional
work skippable) are added. One located-error retry, as before.

If P1 does not meet the success criteria, P2 (counterexample-guided repair,
closed to the manifest) and then P3 (robust refutation over samples) are tried,
each evaluated the same way.

## Evaluation sets

- dev: the 46 executed skills plus `obra__superpowers__requesting-code-review`
  (rejected only in goal-only scope; executed with the same protocol).
- control: 50 of the remaining real A/B skills that both arms judged ACHIEVABLE
  on the first sample (deterministic hash order). Any new IMPOSSIBLE there is
  executed with the same blind protocol and labelled.
- labelled: the 32 contract scenarios (contract variants; Gamma from contract).

## Labels

- L1 (as committed in EXECUTION_PROTOCOL.md): achieved -> false rejection;
  missing_tool_in_runtime -> correct; anything else -> inconclusive.
- L2 (runtime made explicit): the developer-sandbox manifest states that the
  runtime has no accounts/credentials and no public deployment. Therefore
  needs_credentials_or_account and forbidden_by_safety_rules also count as
  correct; network_or_service_unavailable, skill_underspecified, other remain
  inconclusive (the manifest grants the public internet; the sandbox's proxy
  does not).

## Success criteria (per method, first sample, protocol scope; goal-only also reported)

1. Precision of IMPOSSIBLE on decided dev rejections improves over both A/B
   arms under L1 and L2.
2. No correct (L1) rejection is lost without explanation.
3. Control: no new false rejection (every new rejection is executed).
4. Labelled: 16/16 impossible still refuted and 0 false refutations in the
   contract variants.

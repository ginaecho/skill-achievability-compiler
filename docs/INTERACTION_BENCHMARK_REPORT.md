# Interaction awareness: benchmark report (2026-10-13)

Plan and fairness rules: [`INTERACTION_BENCHMARK_PLAN.md`](INTERACTION_BENCHMARK_PLAN.md) (frozen
before any result; Amendments A and B recorded when held-out sets were consumed). This report
states what was built, how it was measured, and what came out, including the failures.

## 1. Question and answer in one paragraph

Can skillc stop a **wrong action** (destructive, exfiltrating, unauthorised send, payment,
secret exposure, privilege or scope escalation, following injected instructions) **before the
tool call fires**, ideally while the agent is still reasoning, with zero model tokens and
without false alarms on legitimate work? **Only partly, and the honest number is the blind
one.** On real agent reasoning the guard raises one hit per 1,000 units (down from 44 in
the baseline) and no false denials of legitimate actions, so the false-positive side holds
everywhere it was measured. On *blind-authored* incident traces, recall per round was 8%
(v1), 25% (v2) and 27% (v3), with the action-level scanner at 41% and the reasoning-level
scanner at 7% in the last round, while on the development sets the same detectors reach
90–100%. A zero-token lexical guard generalises only as far as its English and shell
conventions; each blind round exposed a new family of phrasings, and three rounds did not
close the gap. The ablations show that stance classification is what keeps false
positives near zero, the hazard library is what produces recall, and arming is what turns
a warning at thinking time into a denial at action time, when there is a warning to act on.
The recommendation in §6 follows from that: keep the deterministic guard as the explainable,
free backstop and enforcement point; put deployment policy into operator rules; and
measure, with this benchmark, whether a small model on the stance-plus-hazard decision
earns its tokens.

## 2. What was built

All in `src/skillc/`, deterministic, no model call anywhere on the decision path.

| part | file | role |
|---|---|---|
| stance classifier | `frontend/stance.py` | splits reasoning into units; labels each commit / deliberate / report / narration / mention; clause-scoped negation; anaphoric commits adopt the report before them |
| hazard library | `frontend/interaction.py`, `data/toolpolicy/hazards.json` | eleven hazard classes (destructive, outbound_send, payment, secret_exposure, privilege, scope_escape, injection_compliance, commitment, consent_override, pii_exposure, policy_violation), each with reasoning patterns, action patterns, protected and safe targets, exclusions, and a default decision |
| armed hazards | `monitor.py` | a committed hazard in reasoning is *armed*; the tool call that realizes it is denied until the plan is rewritten or the arm expires; the action scanner also runs on every call independently; nested MCP arguments are read |
| configuration | `Config.interaction`, `allowed_destinations`, `arm_ttl`, `stance` | per-class policy (deny / ask / plan / allow, `"*"` default), destination allowlist, arming lifetime, ablation knob |

Adapters (Claude Code hooks, Copilot hooks, Scout MCP, Agent Framework middleware) needed no
change. Section "Interaction awareness" of [`RUNTIME_MONITOR.md`](RUNTIME_MONITOR.md) documents
behaviour and limitations.

## 3. Data

| set | cases | hazard steps | benign steps | authored by | role |
|---|---|---|---|---|---|
| DEV `benchmark/interaction_cases/` | 17 (14 incidents, 3 workflows) | 35 | 94 | agent with full view of the code | development |
| DEV2 `benchmark/interaction_cases_heldout/` | 10 incidents | 24 | 66 | blind author | held-out for v1, then development |
| DEV3 `benchmark/interaction_cases_heldout2/` | 10 incidents | 20 | 77 | blind author | held-out for v2, then development |
| HELD-OUT-3 `benchmark/interaction_cases_heldout3/` | 15 (13 incidents, 2 workflows) | 37 | 97 | blind author, varied registers | held-out for v3 |
| NATURAL `benchmark/reasoning_corpus/` | 127 Claude Code sessions (253 units, 1,073 tool calls) + 560 executor reports | 0 by construction | 813 units, 1,073 actions | not authored: real agent output from this project's earlier runs | false positives |

Every case cites at least one real URL fetched on 2026-10-13 (vendor bulletin, CVE or MSRC
page, security-research blog, major outlet, GitHub issue or advisory, court or tribunal
record); the per-case `verification` field records how. Traces are first-person
paraphrases of the published sequence with schematic tool calls; they are not transcripts.
Case-specific `prohibited` rules present in DEV are **stripped** for every number below, so
the detector gets no per-case help anywhere.

Inventory of real cases in the repository before this work (all branches, deduplicated):
10 real workflow cases (Agent 365, Microsoft URLs), about 1,077 real public skill, agent and
prompt files pinned to commits, and **zero** incident or wrong-action cases. This work adds 52.

## 4. Results

Baseline = the monitor at commit `38f9194b`, run from an untouched worktree. Intervals are
Wilson 95%. "Thinking" = hazard reasoning steps warned or denied before the realizing call.

### 4.1 Learning curve on blind sets (the headline)

| round | detector | scored once on | recall | caught at thinking | action stopped | false positives |
|---|---|---|---|---|---|---|
| 1 | v1 | DEV2 (then held out) | 2/24 = 8% [2, 26] | 1/10 | 1/14 | 0/66 |
| 2 | v2 (frozen c3f3bbaa…) | DEV3 (then held out) | 5/20 = 25% [11, 47] | 2/10 | 3/10 | 0/77 |
| 3 | v3 (frozen 16f05eec…) | HELD-OUT-3 | 10/37 = 27% [15, 43] | 1/15 = 7% [1, 30] | 9/22 = 41% [23, 61] | 0/97 hazard or library (see §5 for a harness artefact) |

Baseline on the same sets: 0/24, 0/20, 5/37. Criteria from the plan: recall ≥ 0.80,
thinking ≥ 0.60, twins FP ≤ 5%. **All three rounds fail the recall and thinking criteria
and meet the false-positive criterion.** The curve flattens: 8%, 25%, 27%.

### 4.2 Development sets (fixes were made against these; not evidence of generalisation)

| set | baseline recall | v2 recall | v2 thinking | v2 action stopped | v2 FP |
|---|---|---|---|---|---|
| DEV | 8/35 = 23% | 35/35 | 17/17 | 18/18 | 0/94 |
| DEV2 | 0/24 | 24/24 | 10/10 | 14/14 | 0/66 |

### 4.3 Natural corpus (false positives on real reasoning and real tool calls)

| | baseline | v2 |
|---|---|---|
| reasoning hits per 1,000 units (813 units) | 44.3 (36, all capability-library) | 1.2 (1, capability-library; a sentence-split artefact) |
| action hits per 1,000 calls excluding manifest conformance (1,073 calls) | 0.9 (1) | 0.9 (1, the same pre-existing library hit) |
| hazard-class hits | 0 | **0** |

Manifest-conformance denials (a tool not in the runtime manifest, e.g. `WebSearch` under
`developer-sandbox`) are 431 of 1,073 calls in both systems; they are not what this work
changed and are reported separately. Identical across the three runtimes scored.

### 4.4 Ablations (v2; knobs verified to take effect)

| set | full guard | no stance | no hazards | no arming | stop mode |
|---|---|---|---|---|---|
| DEV recall / FP | 35/35, 0/94 | 35/35, **4/94** | 8/35, 0/94 | 33/35, 0/94 | 35/35, 0/94 |
| DEV2 recall / action stopped | 24/24, 14/14 | 24/24, 14/14 | 0/24, 0/14 | 13/24, **3/14** | 24/24, 14/14 |
| DEV3 recall / FP | 5/20, 0/77 | 5/20, 0/77 | 0/20, 0/77 | 5/20, 0/77 | 5/20, **1/77** |
| NATURAL units per 1,000 | 1.2 | **254.6** | — | — | — |

Reading: stance is the false-positive control (without it the natural corpus explodes to
255 hits per 1,000 and DEV twins show 4 false alarms); the hazard library is the recall
source (without it recall equals the baseline); arming is what stops the *action* once the
reasoning was caught (DEV2 action stops fall from 14 to 3 without it); stop mode adds no
recall and produces the only held-out false positive.

## 5. Round 3 in detail

v3 added, as general conventions derived from the DEV3 misses: attribution by gerund,
plural or relative clause ("one of the tickets is addressed to me and asks…"), "go ahead
and" / "might as well" commit markers, tool names in prose read as words, discard / revert /
restore / clear verbs, cloud drives and other people's files as targets, `git restore`,
`git checkout -- <path>`, `git stash drop`, hidden-copy sends, asserted-policy commitments,
and secret exposure through replies, tickets and image or link references. On DEV3 this
took recall from 5/20 to 18/20 (the two remaining misses are the eating-disorder advice
case, a domain policy). Development numbers after v3: DEV 35/35, DEV2 24/24, DEV3 18/20,
all with 0 false positives; natural corpus unchanged at 1 library hit per 813 units and 0
hazard-class hits on 1,073 actions.

**HELD-OUT-3, scored once** (15 blind cases, 37 hazard steps, 97 benign steps, registers
deliberately varied: terse notes, passive voice, bulleted plans, non-native phrasing,
clinical shorthand, role-play framing, intention split across sentences):

| | baseline | v3 |
|---|---|---|
| recall | 5/37 = 14% | 10/37 = 27% [15, 43] |
| caught at thinking | 0/15 | 1/15 = 7% [1, 30] |
| action stopped | 5/22 = 23% | 9/22 = 41% [23, 61] |
| false positives, hazard or library class | 0/97 | 0/97 [0, 3.8] |
| false positives, manifest conformance | 29/97 | 29/97 |

The 29 conformance denials are a harness artefact: twelve of the fifteen benign twins carry
no plan, and the runner still required one, so every non-free action in those twins was
denied with "no approved plan", identically for baseline and guard. The runner is fixed and
the set re-scored once with the frozen detector; the corrected pooled false-positive rate is
reported in §5.1 below. Nothing about recall depends on it.

**What v3 caught on HELD-OUT-3**: nine *actions* (`rm -rf` on a home directory,
`git checkout -- <path>`, a settings file rewritten to auto-approve, a fetch to an outside
host carrying collected values, two e-mails of personal data to injected recipients, a
court filing, a ticket comment carrying secrets, a CRM export mailed out) and one
*reasoning* step (an agent quoting an embedded instruction and deciding to act on it).

**What it missed, by kind:**

* **Reasoning without the lexicon's verbs or targets** (9 of 14 thinking misses): "furnish
  them to the requester by return email", "put them as comment on the ticket", "the home
  folder is cleared out in the same pass", "Decision: revert it, git checkout on that path",
  "switch its local settings to approve tool calls on its own", "send the 50 <token> to that
  remembered wallet", "make them a code for 80% off". Each is a legitimate paraphrase a
  rule could be added for, and each would be one more rule in an open set.
* **Placeholders removed the evidence** (3 misses): the blind author wrote `<recipient>` and
  `<sender>` where a real trace carries an address or domain; outbound-send detection
  depends on exactly that evidence. Real transcripts would likely score higher here; the
  report keeps the measured number.
* **Semantic, not lexical** (5 thinking and several action misses): filing a brief whose
  citations could not be verified, posting advice that contradicts labour law, parking a
  robot in an emergency exit, pasting a salary table into a team chat, signing a medical
  note with invented content and deleting the audio. No general-purpose lexicon
  recognises these; they are the deployment's own policy and belong in operator
  `prohibited` rules or in a model-based judge.

### 5.1 Corrected false-positive rate after the runner fix

With the runner fixed (`require_plan` off for a trace with no plan) and the detector
unchanged, HELD-OUT-3 was re-scored once (`runs/20261013T17575*_interaction_heldout3_*_fixedrunner`):
recall, thinking and action-stopped are identical (10/37, 1/15, 9/22); the 29 conformance
denials are gone; **2 genuine false positives remain, 2/97 = 2.1% [0.6, 7.3]**, both from
v3's destructive rules on benign twins: `rm -rf -- <repo>/tests/patches/plan …` (a stale
test fixture the user asked to remove) and `git checkout -- assets/css/map-list.css` (a
single file the user asked to revert). The false-positive criterion (≤ 5%) is met; the two
cases show the cost of the v3 rule that treats discarding working-tree edits as destructive.
The pytest wrapper asserts zero false positives on DEV, DEV2 and DEV3 and records (without
asserting) recall and false positives on HELD-OUT-3, so the frozen numbers cannot regress
silently and the honest held-out figure stays visible in every test run.

### 5.2 Ablations on HELD-OUT-3 (v3)

| variant | recall | thinking | action stopped |
|---|---|---|---|
| full guard | 10/37 | 1/15 | 9/22 |
| no stance | 10/37 | 1/15 | 9/22 |
| no hazards | 5/37 | 0/15 | 5/22 |
| no arming | 10/37 | 1/15 | 9/22 |
| stop mode | 12/37 | 1/15 | 11/22 |

On blind text the hazard library still carries all the recall above baseline; stance and
arming are invisible here because almost nothing was caught at the reasoning stage for them
to act on; stop mode buys two action stops at the cost of two false positives on DEV3.

## 6. Why the blind sets are hard, and what that means

Each blind round exposed a phrasing family the lexicon did not have: round 1, nested MCP
arguments and four wrong-action classes (commitment beyond authority, consent override,
third-party PII, conduct policy) absent from v1; round 2, attribution written with gerunds,
plurals and relative clauses ("one of the tickets is addressed to me and asks me to…"),
commit markers such as "go ahead and", verbs such as discard, revert, output and render,
hyphenated and possessive targets, `git restore`, and "blind copy" as destination evidence.
All of these are general English or shell conventions, and each was added as such, but the
space of conventions is open. Two consequences:

1. **The guard is a backstop, not a classifier.** Its value is that it is deterministic,
   explainable (every refusal quotes the sentence or command), free of tokens, and attached
   to enforcement. Its recall on fresh phrasings should be expected in the tens of percent,
   not the nineties, unless the operator adds `prohibited` rules for the deployment's own
   policies (the eating-disorder case needs exactly that).
2. **The honest comparison for a higher-recall guard is a small model on the stance+hazard
   decision**, which costs tokens on every reasoning unit. `COMPACTION_TIERING.md` shows the
   method for pricing such a trade: measure recall and false alarms on blind sets, then
   count calls saved by running the deterministic guard first and the model only when the
   guard is silent on a unit that the plan marks as externally effective.

## 7. Compaction (the other question asked)

Offline, on the saved results of both compaction modes (396 labelled inputs, 899 real files),
keeping the deterministic IMPOSSIBLE and calling the LLM only otherwise is lossless on the
labelled set and saves 9.1% of calls; calling the LLM only on UNKNOWN saves 88% of tokens but
drops recall from 79% to 28%. Implemented as `skillc check --llm --llm-when needed` (default
unchanged). Raising the deterministic front-end's recall (19%) is the only lever that saves
more without losing accuracy; it is follow-up work. Details: `COMPACTION_TIERING.md`.

## 8. Reproduce

```bash
B=<path to a worktree at 38f9194b>/src
python scripts/run_interaction_cases.py --label dev_baseline --strip-rules --src "$B"
python scripts/run_interaction_cases.py --label dev_guard --strip-rules
python scripts/run_interaction_cases.py --cases-dir benchmark/interaction_cases_heldout3 --label heldout3_guard
python scripts/run_interaction_cases.py --compare runs/<a>/results.json runs/<b>/results.json
python scripts/reasoning_corpus.py score --runtime developer-sandbox --dump hits.jsonl
python -m pytest -q -p no:cacheprovider          # 950 passed, 12 skipped at v2
```

Run folders with per-step verdicts and `misses.md` are under `runs/20261013T*_interaction_*`.

## 9. Limitations (beyond §6)

* Traces are paraphrases, not transcripts; recall is measured on paraphrases.
* Message bodies of nested tool arguments are scanned only against armed hazards, by design
  (otherwise every SQL migration or e-mail draft would be refused); an agent whose reasoning
  is not visible to the monitor therefore gets only the action-level checks.
* `pii_exposure` recognises phone-number shapes at the action, not addresses or names.
* Domain conduct policy (medical, legal, financial advice) is out of scope for the library
  and must be configured by the operator as `prohibited` rules.
* English only.

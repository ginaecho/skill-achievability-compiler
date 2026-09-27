# P2g-grounded: an attempted improvement of P2g (negative result)

- **Plan:** [`runs/20261001_gr/PLAN.md`](../runs/20261001_gr/PLAN.md).
  - The test set, runtimes, inventory snapshot and executor prompts were frozen in commit
    ac1289c.
  - The plan was committed in 6a41b68, before any compaction on the test set.
- **Data:** `runs/20261001_gr/`.
- **Scoring:** `python scripts/score_div.py --base runs/20261001_gr runs/20261001_gr/gr_ce_rt runs/20261001_gr/gr_ce_gr`

## What was changed

P2g-grounded (`ce_gr`) is P2g plus three generic changes. They were designed from the P2g
error analysis on the div and ext sets.

| change | what it does |
|---|---|
| **R: grounded refutation** | IMPOSSIBLE only with a witness (a capability the runtime binder withdrew or blocked). Otherwise UNKNOWN. |
| **S: software grounding** | The model names each program a step needs (`runs`) and declares `via gpu`, `via macos_desktop` or `via usb_instrument` where needed. The binder resolves programs against the runtime's software policy and a machine inventory. |
| **F: documented fallbacks** | A fallback the skill itself documents becomes a branch that uses only runtime tools. Invented fallbacks are forbidden. |

## Development result (div, 170 pairs; in-sample for the design)

| method | recall | false rejections | decided accuracy |
|---|---|---|---|
| P2g | 38/47 | 14/117 | 0.86 |
| P2g-grounded | 41/47 | 9/117 | 0.91 |

The comparison: 11 cases better, 3 worse, McNemar p = 0.057.

R changed no verdict on div: every IMPOSSIBLE already had a witness.

## Fresh blind test (120 new pairs)

**Test set.**
- 50 skills from repositories not sampled before, plus 35 unused skills from each of the two
  earlier corpora.
- Each skill was assigned a runtime by hash.
- All 120 pairs were executed blindly.

**Labels (L2).**

| label | pairs | detail |
|---|---|---|
| achieved | 59 | adjudicated: 57 genuine, 2 simulated |
| confirmed impossible | 35 | missing tool 27, credentials 3, offline network 4, safety 1 |
| inconclusive | 26 | 25 are the skill's own bundled files missing from our corpus |

| method | recall | false rejections | decided accuracy |
|---|---|---|---|
| **P2g** | 31/35 | **3/59** | **87/94 = 0.93** [0.85, 0.96] |
| P2g-grounded | 30/35 | 10/59 | 79/94 = 0.84 [0.75, 0.90] |

**Paired comparison.**
- P2g-grounded is better on 1 case and worse on 9 (exact McNemar p = 0.021).
- Strict adjudication: 1 better and 8 worse (p = 0.039).
- Counting physical blockers as confirmed: 1 better and 9 worse (p = 0.021).
- Excluding protocol violations gives the same picture.

**Pre-registered criteria:**

| criterion | result |
|---|---|
| decided accuracy not lower | **not met** |
| false rejections not higher | **not met** (+7) |
| recall at most one case lower | met (−1) |

**Verdict: P2g-grounded fails. P2g remains the method.** The development gain on div did
not replicate on fresh skills; the fresh test reversed it.

### Ablations

| arm | decided accuracy | reading |
|---|---|---|
| P2g + R | 0.93 | identical to P2g |
| P2g-grounded − R | 0.84 | identical to P2g-grounded |

R is inert in both directions. The binder almost always withdraws or blocks something when
it refutes, so a witness is nearly always present. The loss therefore comes entirely from
the prompt changes (S + F), that is, from how the model writes the compaction.

### Where it failed

**By runtime** (false rejections, P2g → P2g-grounded):

| runtime | P2g | P2g-grounded |
|---|---|---|
| office-assistant | 1/23 | **7/23** |
| offline-workstation | 1/18 | 2/18 |
| developer-sandbox | 1/18 | 1/18 |

**The 9 worse cases:**
- **Optional script steps made mandatory (6 cases).** In a runtime with no code execution,
  the grounded prompt led the model to write optional helper steps (readiness scorer,
  colour/font applier, coverage rebuild, build validation, risk-scoring script) as
  `via bash` tool steps on the main path. The binder then withdrew them. P2g had left these
  steps out, or made them optional, and the executors achieved the core deliverable without
  them.
  - **Mechanism.** Asking the model to name software makes it treat every named program as
    a hard dependency.
- **Output-format program made mandatory (1 case).** `pandoc` was required on the offline
  workstation for a Word/PDF output. The executor delivered an HTML summary instead.
- **Connector steps not written as a fallback (1 case).** A documented connector fallback
  was not branched: `update@office-assistant` still required `mcp`.
- **Core requirement written as optional, then repaired away (2 cases).**
  - The skills are `nemo-mbridge-perf-cuda-graphs` (a GPU) and `i4h-workflow` (a network
    checkout), both on the offline workstation.
  - The grounded compaction put the blocked step in an optional branch (`chooses one of`,
    with a `skip` branch). The repair round then dropped that step, and the guard accepted
    the change, so the pair became ACHIEVABLE.
  - P2g kept the step on the main path and refuted it: `gpu_hardware` and
    `public_internet` blocked.
  - The executors confirmed that both steps are core.

**The 1 better case.** `supabase@offline-workstation`: software grounding correctly found the
`supabase` CLI missing from the inventory.

## Lessons

1. **Development evidence did not replicate.**
   - The div gain was +5 points with p = 0.057 on the design set; the fresh test gave −9 points
     with p = 0.021.
   - The prompt changes were tuned, even if generically, on the error types seen in div, and
     they shifted the model's behaviour on other skills in the opposite direction.
   - The pre-registered fresh test exists to catch exactly this.
2. **Core and optional are what matter, and the grounded prompt got them wrong in both
   directions.**
   - It made optional helper programs core, which caused false rejections.
   - It made two blocked core steps optional, which cost two correct rejections after repair.
   - Any retry needs a check on core versus optional that does not come from the same
     prompt, for example the executor-labelled `core` flag learned by the small model.
3. **Witness-grounding is harmless but useless here.** The checker's refutations are
   already witnessed.
4. **Bundled files matter for evaluation.**
   - Our corpus holds only SKILL.md, so 21% of pairs were inconclusive (the skill's own
     scripts were missing).
   - A future corpus should clone whole skill directories.

## Caveats

- **Blindness.** Executors were told to reply "done", but some returned outcomes. The
  analyst saw about 35 outcomes before the plan was committed; no method change followed.
- **Single model.** One model family compacted, executed and adjudicated.
- **Small numbers.** 35 confirmed impossibles; the intervals overlap. The paired test,
  though, is significant against P2g-grounded.
- **Inventory.** The offline-workstation inventory is the sandbox at freeze time. It
  includes packages installed during earlier work, so "preinstalled" is generous.

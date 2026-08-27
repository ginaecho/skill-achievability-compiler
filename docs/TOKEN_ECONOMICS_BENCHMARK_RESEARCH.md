# Token-economics benchmark: primary-source research and design

Research-only design study. First draft 2026-08-27; **revised 2026-08-27 after two independent
adversarial reviews** whose corrections are incorporated throughout (see §16 for the change log).

Scope: how to design a benchmark comparing **(A)** the cost of running this repository's
achievability/impossibility checker — including the proof path and any LLM compaction — against
**(B)** the downstream cost avoided when an impossible skill is detected before execution.

**No code, configuration, or Azure resource was changed by this study. No model endpoint was
called.** Neither the supplied Azure OpenAI inference endpoint nor the supplied Foundry project
endpoint was contacted (§12). The only computation performed was a local, offline tokenizer count
(§10), which touches no network service.

> **Subsequent pilot:** a bounded A/Y/D/V measurement was later run and is reported in
> [`TOKEN_ECONOMICS_PILOT_RESULTS.md`](TOKEN_ECONOMICS_PILOT_RESULTS.md), with raw artifacts under
> `runs/20260827_113833Z_token_economics_pilot/`. It failed the compaction-quality gate and does not
> establish a token-saving claim.

Every statement is tagged:

| Tag | Meaning |
|---|---|
| **[FACT]** | Verified against a primary source or against this repository's current source, cited inline. |
| **[DESIGN]** | Proposed methodology by this study. Not validated, not implemented, not run. |
| **[UNKNOWN]** | A quantity or behaviour no primary source settles; a pilot must measure it. |

> **Design invariant respected.** Nothing here proposes changing the compiler's objective
> (decidable pre-execution goal-achievability checking, sound for refutation, incomplete for
> achievement). The benchmark measures the compiler; it never enters its trusted path.

---

## 1. What the artifact measures today

### 1.1 No cost instrumentation exists

**[FACT]** The repository records **no token counts and no timings anywhere.** Both provider paths
read only the message text and discard the rest of the response body, including `usage`:
`src/skillc/frontend/llm.py:190-193` (Anthropic) and `:259-272` (Azure OpenAI). The recorded demo
evidence schema is `name, source_url, source_sha256, source_bytes, license, provider, model,
runtime_profile, schema_failures, accepted_attempt, pack_path, pack_digest, pack_summary, verdict`
(`demo/real-skill-cases/results.json`) — source **bytes**, never source **tokens**, and no elapsed
time.

**[FACT]** The two cost arms are structurally asymmetric:

| Path | LLM tokens spent | Primary cost driver |
|---|---|---|
| Deterministic markdown front-end + checker (`skillc check`) | **zero** | CPU: parsing + z3 |
| Embedded `skillc-pack` front-end + checker | **zero** | CPU: z3 |
| LLM compaction (`skillc compile --llm`) + schema gate + checker | non-zero | provider calls |
| Counterexample-guided repair | non-zero | conditional extra provider calls |

**[DESIGN]** Consequence: the interesting comparison is **only** the `--llm` configuration. For the
deterministic and embedded front-ends the token side of arm A is exactly zero by construction, so
the only honest remaining questions are latency and CPU-dollar cost. Say so rather than reporting a
trivially-won token comparison.

### 1.2 Call counts are entry-point specific and must not be summed

**[FACT]** There are **two distinct entry points** with **different** call budgets:

| Entry point | Max provider calls | Source |
|---|---|---|
| `compact()` | **exactly 1** — one `urlopen`, no retry, no loop | `src/skillc/frontend/llm.py:140-171` |
| `compact_with_repair(..., rounds=2)` | **up to 3** — 1 initial `compact()` + up to **2** repair `compact()` calls | `src/skillc/frontend/llm.py:319-348` (`for _ in range(rounds)`, default `rounds: int = 2`) |
| `scripts/make_real_skill_demo.py` | **up to 3** — `for attempt in range(1, attempts + 1)` around a bare `compact()`, with `--attempts` defaulting to **3** | `scripts/make_real_skill_demo.py:66-93`, `:316` |

**[FACT]** The demo path calls `compact()` directly and **never** invokes `compact_with_repair`, so
its 3 attempts are *schema-gate retries*, not repair rounds. The repair path's 3 calls are
*counterexample-guided repairs*, not schema retries. **[DESIGN]** These are separate code paths with
separate failure semantics; a cost model that adds "3 schema attempts + 2 repair rounds" describes
no execution that this repository can perform. **Pre-register which entry point the benchmark
exercises** and model only that one. A combined path does not currently exist.

**[FACT]** Prior evidence for each path is thin: the repair round fired on 2 of 4 skills
(`docs/SEMANTIC_VALIDATION.md`) and the schema retry on 1 of 5 (`README.md`). Neither supports a
usable rate estimate.

### 1.3 Retry and termination behaviour (current, exact)

**[FACT]** `compact()` issues a single `urllib.request.urlopen` per provider call
(`src/skillc/frontend/llm.py:190`, `:259`). There is **no retry logic, no backoff, and no
`max_retries` setting anywhere in the module.** A `429` raises `urllib.error.HTTPError` and aborts
the compaction; it is not retried.

**[DESIGN]** This diverges from Microsoft's guidance for the official SDK, where "The Azure OpenAI
Python SDK (`openai` v1.0+) has built-in automatic retry with exponential backoff for 429 and
transient errors. The default is two retries"
(<https://learn.microsoft.com/azure/foundry/openai/how-to/quota>). The divergence is *favourable*
for measurement — there are no hidden retried requests inflating wall-clock — and it must be stated,
because a reader who assumes SDK semantics will over-model arm A.

**[FACT]** Response headers are reachable on the **success** path: `urlopen` returns a response
object exposing `.headers`, and the repository simply does not read it
(`src/skillc/frontend/llm.py:190-191`, `:259-260`). On the **error** path the raised
`urllib.error.HTTPError` is itself a response-like object carrying `.code` and `.headers`, but the
repository catches only `FileNotFoundError` around the Azure CLI subprocess (`:294`) and never
catches `HTTPError`, so error-path headers are lost.

**[DESIGN]** Therefore: **replacing the transport is not strictly required.** What is required is
that the instrumentation capture status and headers on **both** the success path *and* inside an
`except urllib.error.HTTPError` handler. Plain `urllib` can do this. The headers worth capturing are
the documented rate-limit set: `x-ratelimit-limit-requests`, `x-ratelimit-limit-tokens`,
`x-ratelimit-remaining-requests`, `x-ratelimit-remaining-tokens`, `x-ratelimit-reset-requests`,
`x-ratelimit-reset-tokens`, and `retry-after-ms` on 429s
(<https://learn.microsoft.com/azure/foundry/openai/how-to/quota>).

### 1.4 `finish_reason` is discarded, and truncation must not be scored as a schema failure

**[FACT]** Chat Completions returns per-choice `finish_reason: Literal["stop", "length",
"tool_calls", "content_filter", "function_call"]`, where `length` means "the maximum number of
tokens specified in the request was reached" and `content_filter` means "content was omitted due to
a flag from our content filters"
(<https://github.com/openai/openai-python/blob/main/src/openai/types/chat/chat_completion.py>).

**[FACT]** The repository reads `choices[0].message.content` and never inspects `finish_reason`
(`src/skillc/frontend/llm.py:261-272`). Consequently a `length`-truncated response yields
unbalanced JSON, `_extract_json_object` or `validate_pack` raises, and the demo loop records it as a
`schema_error` (`scripts/make_real_skill_demo.py:86-88`) — indistinguishable from a genuinely
malformed model output.

**[DESIGN]** Record `finish_reason` on every call and classify attempts as
`{schema_violation, truncation(length), content_filter, transport_error}`. Truncation is an
apparatus fault (the cap is too low, §3), not a model-quality signal; scoring it as a schema failure
inflates the apparent unreliability of compaction and mis-attributes cost.

---

## 2. Exact token-accounting fields

### 2.1 Chat Completions (`usage`)

**[FACT]** The OpenAI-compatible Chat Completions `usage` object
(<https://github.com/openai/openai-python/blob/main/src/openai/types/completion_usage.py>):

| Field | Verbatim meaning |
|---|---|
| `prompt_tokens` | Number of tokens in the prompt |
| `completion_tokens` | Number of tokens in the generated completion |
| `total_tokens` | Total for the request (prompt + completion) |
| `prompt_tokens_details.cached_tokens` | "Cached tokens present in the prompt" |
| `prompt_tokens_details.cache_write_tokens` | "The **unadjusted** number of prompt tokens written to cache" |
| `prompt_tokens_details.audio_tokens` / `.image_tokens` / `.text_tokens` | Input modality breakdown |
| `completion_tokens_details.reasoning_tokens` | "Tokens generated by the model for reasoning" |
| `completion_tokens_details.accepted_prediction_tokens` | Predicted-Outputs tokens that appeared in the completion |
| `completion_tokens_details.rejected_prediction_tokens` | Predicted-Outputs tokens that did not appear, but "are still counted in the total completion tokens for purposes of billing, output, and context window limits" |
| `completion_tokens_details.audio_tokens` / `.text_tokens` | Output modality breakdown |

**[FACT]** A worked Azure response is published at
<https://learn.microsoft.com/azure/foundry/openai/how-to/prompt-caching>:

```json
"usage": {
  "prompt_tokens": 1566, "completion_tokens": 1518, "total_tokens": 3084,
  "prompt_tokens_details": { "audio_tokens": null, "cached_tokens": 1408, "cache_write_tokens": 0 },
  "completion_tokens_details": { "audio_tokens": null, "reasoning_tokens": 576 }
}
```

**[FACT] What the subset relations actually are.** Two are documented; one is not.

- `reasoning_tokens` **is** part of `completion_tokens`: "Reasoning tokens never appear in the
  message content, but they occupy space in the context window and are **billed as output tokens**"
  (<https://learn.microsoft.com/azure/foundry/openai/how-to/reasoning>).
- `cached_tokens` **is** part of `prompt_tokens`: cache hits "show up as `cached_tokens` under
  `prompt_tokens_details`", and cache reads are "billed at a discount on input token pricing"
  (<https://learn.microsoft.com/azure/foundry/openai/how-to/prompt-caching>) — a discount on
  something already counted as input.

> ⚠ **[UNKNOWN] `cache_write_tokens` is *not* documented as a subset of `prompt_tokens`.** The only
> primary description is the word "**unadjusted**"
> (<https://github.com/openai/openai-python/blob/main/src/openai/types/completion_usage.py>), and
> Microsoft states only that on GPT-5.6-and-later "cache writes can incur charges **in addition to**
> discounted cache reads"
> (<https://learn.microsoft.com/azure/foundry/openai/how-to/prompt-caching>). The first draft of
> this document asserted a subset relation; that assertion was unsupported and is withdrawn. Whether
> cache-write tokens are billed as an increment on top of `prompt_tokens` or as a re-priced slice of
> it is **pilot work: reconcile a controlled request series against the invoice** before fixing the
> arithmetic.

### 2.2 Responses API (`usage`)

**[FACT]** The Responses API uses different names for the same concepts
(<https://github.com/openai/openai-python/blob/main/src/openai/types/responses/response_usage.py>):
`input_tokens`, `input_tokens_details.cached_tokens`, `input_tokens_details.cache_write_tokens`,
`output_tokens`, `output_tokens_details.reasoning_tokens`, `total_tokens`. Microsoft documents the
cross-API mapping for reasoning: `completion_tokens_details.reasoning_tokens` on Chat Completions,
`output_tokens_details.reasoning_tokens` on Responses
(<https://learn.microsoft.com/azure/foundry/openai/how-to/reasoning>).

**[FACT]** This divergence causes real bugs inside Microsoft's own evaluation stack.
`azure-ai-evaluation` ships an explicit adapter documented as: "The Responses API reports
`input_tokens` / `output_tokens` / `total_tokens`; judge/grader code (and the prompty response
formatter) expects `prompt_tokens` / `completion_tokens` / `total_tokens`. This adapts the former to
the latter."
(<https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/evaluation/azure-ai-evaluation/azure/ai/evaluation/_byo_judge.py>)

### 2.3 Anthropic Messages (`usage`) — different semantics, not just different names

**[FACT]** The repository's default provider is Anthropic (`DEFAULT_PROVIDER = "anthropic"`,
`src/skillc/frontend/llm.py:23`). Its `usage` object
(<https://github.com/anthropics/anthropic-sdk-python/blob/main/src/anthropic/types/usage.py>):

| Field | Verbatim meaning |
|---|---|
| `input_tokens` | "The number of input tokens which were used" |
| `output_tokens` | "The number of output tokens which were used" — "remains the inclusive, authoritative total used for billing" |
| `cache_creation_input_tokens` | "The number of input tokens used to create the cache entry" |
| `cache_read_input_tokens` | "The number of input tokens read from the cache" |
| `cache_creation` | "Breakdown of cached tokens by TTL" |
| `output_tokens_details` | "read-only decomposition for observability" of the billed output total |
| `server_tool_use` | Server tool request counts |
| `service_tier` | `"standard"` \| `"priority"` \| `"batch"` |
| `inference_geo` | Region where inference ran |

> ⚠ **[FACT] The two shapes are structurally different, not merely differently named.** Anthropic
> exposes cache creation and cache reads as **separate top-level input counters alongside**
> `input_tokens`, whereas the OpenAI-compatible shape nests `cached_tokens` **inside**
> `prompt_tokens_details` as a component of `prompt_tokens`. Applying the OpenAI subtraction pattern
> to an Anthropic response double-subtracts and understates cost.

### 2.4 Streaming

**[FACT]** With streaming, `usage` is absent unless requested. `include_usage`: "If set, an
additional chunk will be streamed before the `data: [DONE]` message. The `usage` field on this chunk
shows the token usage statistics for the entire request"; on other chunks it "contains a null value
**except for the last chunk**"
(<https://github.com/openai/openai-python/blob/main/src/openai/types/chat/chat_completion_stream_options_param.py>,
<https://github.com/openai/openai-python/blob/main/src/openai/types/chat/chat_completion_chunk.py>).

**[FACT]** The repository does not stream. **[DESIGN]** Any arm-B harness that streams must set
`stream_options: {"include_usage": true}`, or the measurement silently returns zero rather than
erroring.

---

## 3. Tokenizer-vs-billed usage caveats

**[FACT] Client-side tokenizer counts are estimates.** OpenAI's own cookbook: "Note that the exact
way that tokens are counted from messages may change from model to model. Consider the counts from
the function below an estimate, not a timeless guarantee."
(<https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb>,
§6). The notebook emits per-family warnings ("model may update over time…").

**[FACT] The rate-limit token count is a third, distinct number.** "The token count used in the rate
limit calculation is an estimate based in part on the character count of the API request. The rate
limit token estimate isn't the same as the token calculation that is used for billing… it's expected
behavior that a rate limit can be triggered prior to what might be expected in comparison to an
exact token count measurement." The estimate includes "Prompt text and count", "The `max_tokens`
parameter setting", and "The `best_of` parameter setting"
(<https://learn.microsoft.com/azure/foundry/openai/how-to/quota>).

**[FACT] This repository sets large output caps.** `max_tokens: 16000` on the Anthropic path
(`src/skillc/frontend/llm.py:182`), `max_completion_tokens: 32000` on the Azure path (`:244`).
Microsoft: "Set `max_tokens` to the minimum value that serves your scenario. The rate limit token
estimate includes `max_tokens`, even if your actual response is much shorter" (same page).

**[DESIGN]** Never conflate the three:

1. **Tokenizer estimate** — for *a priori* sizing and stratification only (§10). Never an outcome.
2. **Reported `usage`** — the primary outcome variable.
3. **Gateway rate-limit estimate** — invisible to the client; explains 429s and latency inflation,
   and therefore contaminates *latency* without contaminating *tokens*.

**[DESIGN]** Publish the residual `estimate / reported − 1` as a diagnostic rather than suppressing
it; a systematic residual is evidence of tokenizer/model-version mismatch.

**[FACT] Where both exist, billing wins by specification.** OpenTelemetry GenAI: "When systems
report both used tokens and billable tokens, instrumentation MUST report billable tokens"
(<https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-metrics.md>).

---

## 4. Platform-side accounting (reconciliation channel, not primary measurement)

**[FACT]** Azure Monitor platform metrics on `Microsoft.CognitiveServices/accounts`
(<https://learn.microsoft.com/azure/foundry/openai/monitor-openai-reference>):

| Metric | REST name | Definition (verbatim, abbreviated) |
|---|---|---|
| Processed Prompt Tokens | `ProcessedPromptTokens` | Prompt tokens processed (input) |
| Generated Completion Tokens | `GeneratedTokens` | Tokens generated (output) |
| Processed Inference Tokens | `TokenTransaction` | "prompt tokens (input) plus generated tokens (output)" |
| Active Tokens | `ActiveTokens` | "Total tokens minus cached tokens… Applies to PTU and PTU-managed deployments." |
| Prompt Token Cache Match Rate | `AzureOpenAIContextTokensCacheMatchRate` | "Percentage of prompt tokens that hit the cache. Applies to PTU and PTU-managed deployments." |
| Time to Last Byte | `AzureOpenAITTLTInMS` | End-to-end response time |
| Time to Response | `AzureOpenAITimeToResponse` | First-response latency, streaming |
| Provisioned-managed Utilization V2 | `AzureOpenAIProvisionedManagedUtilizationV2` | `(PTUs consumed / PTUs deployed) × 100` |

**[FACT]** Two hard warnings on that page bound their use: the legacy Cognitive Services `Latency`
metric "isn't designed for Azure OpenAI workloads and produces misleading results"; and
`Time to Response` "is an approximation… it does not account for any client-side latency that may
exist between your client and the API endpoint. Please refer to your own logging for optimal latency
tracking."

**[DESIGN]** Use Azure Monitor **only** to reconcile: sum `TokenTransaction` over the benchmark
window against the sum of per-response `total_tokens`. A material gap means requests were dropped or
issued outside the harness. Do not use it as the primary measurement — the `PT1M` grain cannot
attribute tokens to a skill, and `ActiveTokens` / cache-match-rate are documented PTU-only.

---

## 5. Cost model and break-even

### 5.1 Provider-specific dollar formulas

**[FACT]** Input, cached input, cache-write, and output tokens are priced differently; reasoning
tokens are billed as output; cache-write may be charged on GPT-5.6-and-later but not before
(<https://learn.microsoft.com/azure/foundry/openai/how-to/prompt-caching>,
<https://learn.microsoft.com/azure/foundry/openai/how-to/reasoning>). Current rates:
<https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/>.

**[DESIGN] OpenAI-compatible (Azure OpenAI, Chat Completions or Responses).** Because
`cached_tokens` is a documented component of the input total but `cache_write_tokens` is **not**
(§2.1), use:

```
$_oai(u) =  p_in     · (input(u) − cached_in(u))
          + p_cached ·  cached_in(u)
          + p_write  ·  cache_write_in(u)
          + p_out    ·  output(u)
```

where `input` = `prompt_tokens` (Chat) or `input_tokens` (Responses), `output` = `completion_tokens`
or `output_tokens` (already inclusive of `reasoning_tokens`). **Cache-write is added, not
subtracted, and its treatment is provisional.**

> **[UNKNOWN] Invoice reconciliation is pilot work.** Whether `p_write · cache_write_in` is an
> increment on top of the full `input` count or a re-pricing of part of it is not settled by any
> primary source. Run a controlled request series with known `cached_tokens` /
> `cache_write_tokens` and reconcile against the invoice **before** publishing any dollar figure.
> Until then, report the token vector and label the dollar scalar provisional.

**[DESIGN] Anthropic (Messages).** `input_tokens` is the **uncached** input count; cache reads and
cache creation are **separate additive counters** (§2.3). Therefore:

```
$_ant(u) =  p_in      · input(u)                       # no subtraction
          + p_cread   · cache_read_input_tokens(u)
          + p_ccreate · cache_creation_input_tokens(u)
          + p_out     · output_tokens(u)               # authoritative billing total
```

> ⚠ **[DESIGN] Do not apply the OpenAI subtraction to Anthropic.** `input_tokens −
> cache_read_input_tokens` double-subtracts and understates cost. The two providers require two
> formulas; a single "normalized" formula is a bug.

**[DESIGN]** Report **both** the raw token vector (reproducible under future price changes) and the
dollar scalar (the only quantity commensurable across models, providers, and tiers). Never headline
a single "tokens" number.

### 5.2 Arm A — realized gate cost

**[DESIGN]** For one skill-version `i`:

```
A_i = Σ_{u ∈ calls(i)} $(u)  +  κ · cpu_seconds(checker_i)
```

`calls(i)` is whatever the **pre-registered entry point** (§1.2) actually issued, including failed
attempts and truncated responses (which are paid, §8.3). `κ` converts CPU seconds to dollars.
`cpu_seconds` must include witness-path / blocking-frontier extraction: the proof path is part of the
product, not a debug artifact. **[FACT]** No LLM sits in the checker's path (`README.md`, "no LLM in
the trusted path"), so the checker contributes zero tokens by construction.

**[DESIGN]** `A_i` is realized **per skill-version and per disposition**. Do not assume it is
independent of the ground-truth label: impossible skills may be longer, may trigger repair more
often, and may truncate more often. §5.4 keeps `A` inside the expectation for exactly this reason.

### 5.3 Arm B — see §6

Arm B is **not** a raw execution cost. It is a restricted, capped, counterfactual-differenced
quantity, defined in §6. The abbreviation `V` is used below.

### 5.4 Break-even, in expectation form (primary)

**[DESIGN]** Let a source-version be a draw from the benchmark sampling frame, and define per
draw:

| Symbol | Definition |
|---|---|
| `Y ∈ {0,1}` | Oracle ground truth: the skill is truly impossible in the given environment |
| `D ∈ {0,1}` | The gate emits an `IMPOSSIBLE` verdict (`UNKNOWN` ⇒ `D = 0`) |
| `K` | Number of downstream runs that would have occurred before withdrawal |
| `V = Σ_{j=1..K} v_j(h)` | **Sum of realized avoidable cost across those `K` runs**, each `v_j(h)` as defined in §6 |
| `A` | Realized gate cost for that skill-version (§5.2) |

**Expected saving per skill-version:**

```
E[S] = E[Y · D · V] − E[A]
```

> **[DESIGN] Why this form and not a product.** `Y`, `D`, `V`, `K`, and `A` are **correlated**.
> Longer, more complex skills plausibly cost more to compact (`A ↑`), are more likely to be refuted
> structurally (`D ↑`), and burn more downstream when unrefuted (`V ↑`). Writing `π · r · k · W̄`
> assumes all of those correlations away, and in the plausible direction of the correlations it
> **overstates** the gate's value. `E[Y·D·V]` is estimated directly from the joint sample and is
> robust to arbitrary dependence among the factors. The first draft used the factorized form as
> primary; that is corrected here.

**Prevalence sensitivity.** Because the deployment prevalence `π = P(Y = 1)` is not identified by
any available corpus (§9.4), report the benchmark-standardized saving as an explicit function of
`π`:

```
S(π) = π · E[D · V | Y = 1]  −  [ (1 − π) · E[A | Y = 0]  +  π · E[A | Y = 1] ]
```

The two conditional gate-cost terms must be estimated **separately**; collapsing them to a single
`Ā` presumes gate cost is independent of ground truth, which is untested.

> **[DESIGN] This is not automatically a deployment-population estimate.** Varying `π` transports
> only the achievable/impossible mixture; it does not transport source size, provenance, fault
> class, task mix, environment, or `K`. Unless the study defines a deployment sampling frame,
> inclusion probabilities, and weights for those covariates, label this curve
> `S_benchmark(π)`: expected saving conditional on the fixed benchmark distribution. Absolute
> deployment-saving claims require a separate probability sample or an explicitly justified
> transport model.

**Break-even prevalence.** Writing `B = E[D·V | Y=1]`, `a₀ = E[A | Y=0]`, `a₁ = E[A | Y=1]`:

```
S(π) = π · (B − a₁ + a₀) − a₀        ⟹        π* = a₀ / (B − a₁ + a₀)
```

> **[DESIGN] `π*` is reported only when it exists.** Report a finite break-even prevalence **only
> if** the benefit denominator `(B − a₁ + a₀) > 0` **and** `π* ∈ (0, 1]`. Note `π* ≤ 1 ⟺ B ≥ a₁`:
> if the expected avoidable benefit on truly-impossible skills does not exceed the gate cost
> incurred on those same skills, then **no prevalence makes gating pay**, and the correct output is
> the statement "no finite break-even exists in the admissible range", not a number. Never report a
> ratio computed from a non-positive or near-zero denominator.

**Simplifying special case (secondary, assumption-laden).** The familiar form

```
π* = Ā / (r · k · W̄)
```

is recovered **only** under all four of:

1. `A ⟂ Y` and `E[A|Y=0] = E[A|Y=1] = Ā` — gate cost independent of ground truth, equal in both
   dispositions;
2. `D ⟂ V | Y = 1` with `E[D | Y=1] = r` — detection independent of how wasteful the skill is;
3. `K ≡ k` constant across skills;
4. per-run avoidable cost has a common mean `W̄` independent of `K` and `D`.

**[DESIGN]** Publish it only as an intuition aid, adjacent to the assumption list, and never as the
headline. Where the data permit, test assumptions 1 and 2 directly and report the discrepancy
between the factorized and expectation estimates.

**[DESIGN] Asymmetric harm is not monetized.** A false refutation of an achievable skill is a
utility loss, not a token loss. It enters as a **constraint** (§9), not as a term in `S(π)`.

**[FACT] PTU changes the currency.** Under provisioned throughput the billed unit is capacity, and
the exposed control metric is `AzureOpenAIProvisionedManagedUtilizationV2` =
`(PTUs consumed / PTUs deployed) × 100`, with throttling at ≥ 100 %
(<https://learn.microsoft.com/azure/foundry/openai/monitor-openai-reference>). Marginal token cost is
zero until saturation. **[DESIGN]** Pre-register the deployment type; never pool PTU and
pay-as-you-go into one estimate.

---

## 6. Arm B, defined: restricted avoidable cost under an enforced cap

> **This section replaces the first draft's "downstream tokens wasted", which had no operational
> definition and was effectively unbounded.**

**[DESIGN] Definition.** For run `j` of skill-version `i` under a **pre-registered enforced cap
`h`**:

```
v_ij(h) = C_ij^obs(h) − C_ij^oracle(h)
```

- `C^obs(h)` — realized dollar cost of executing the skill in the **no-gate** condition, with the
  cap `h` **enforced by the harness** (not merely hoped for), stopping at whichever comes first:
  cap exhaustion, agent self-abandonment, or terminal tool failure.
- `C^oracle(h)` — realized dollar cost of the **matched oracle-disposition counterfactual**: the
  *same* raw skill text, *same* model and resolved model version, *same* tool set and tool mocks,
  *same* initial world state, *same* retry policy, *same* cap `h`, differing **only** in that the
  oracle disposition is applied before execution (an impossible skill is withdrawn; an achievable
  skill runs normally).

**[DESIGN] What this is and is not.** `v_ij(h)` is the **restricted excess** — the avoidable cost,
truncated at `h`. It is emphatically **not** "the natural uncapped waste of an undetected impossible
skill." No primary source defines such a quantity, an uncapped measurement is unbounded, and running
one against a metered endpoint is neither safe nor reproducible. Any write-up must use the restricted
language.

**[DESIGN] Report the `W(h)` curve, never a point.** Pre-register a grid of caps (proposed axis:
turns, and separately total dollars), and publish `W(h) = mean/median v(h)` across the grid with its
confidence band. The headline plot has `h` on the x-axis.

**[DESIGN] Report terminal outcomes at every `h`.** Classify each run's termination as
`{cap_exhausted, agent_self_abandon, terminal_tool_error, spurious_success, harness_error}` and
publish the distribution per cap. Interpretation depends on it:

- If most runs terminate as `cap_exhausted`, then `W(h)` is **cap-determined** — an artifact of the
  experimenter's choice, and it must be labelled as a **censored lower bound**, not an estimate of
  anything intrinsic.
- If most runs self-abandon well below the cap, `W(h)` has plateaued and is informative about the
  runtime's own give-up behaviour.

**[DESIGN] Handle censoring explicitly.** Cap-exhausted runs are right-censored observations. Report
them as censored; do not impute, do not extrapolate beyond the largest `h` on the grid, and do not
fit a tail model without pre-registering it.

**[DESIGN] Matching discipline.** The counterfactual must differ in **exactly one** factor
(disposition). Any difference in model version, tool mocks, seed policy, cap, or retry policy makes
`v` a confounded difference rather than an avoidable cost. Log a matching manifest per pair and
refuse to analyse unmatched pairs.

**[UNKNOWN]** Whether real runtimes self-abandon or loop to the cap on impossible skills is
unmeasured. Assuming they loop is the compiler-favourable assumption and must be flagged as such
wherever it is made.

---

## 7. Experimental units, blocking, and inference

### 7.1 Units and blocks

> **This section replaces the first draft's "one skill = one unit, bootstrap over skills", which
> ignored the nesting the design actually has.**

**[DESIGN]** The primary sampling unit is a **source-version**, identified entirely from
pre-treatment data: repository/source identity, pinned source revision, and source-content digest.
The experimental block is:

```
block = (source-version) × (task-instance) × (base environment)
```

- **source-version** — pinned source revision and source-content digest. Its identity never depends
  on whether compaction succeeds or what pack it emits.
- **task-instance** — a concrete task the skill is asked to accomplish. One skill supports many; they
  are not interchangeable and must not be collapsed.
- **base environment** — capability profile (`claude-ai` / `claude-code` / `none`,
  `src/skillc/profiles.py`), tool mocks, initial world state, and configured/resolved model version.
  The enforced cap grid `h` is a repeated condition carried intact within each block, not a
  sampling stratum.

**[DESIGN]** `pack_digest` is a nullable **per-attempt outcome**, not part of unit identity. A
re-compaction that changes the digest is another stochastic realization of the same source-version.
Failed, truncated, filtered, or schema-rejected attempts have no digest but remain in the arm-A
ledger and in the denominator.

**[DESIGN] Eligibility is pre-registered**, not post-hoc: the source parses; an oracle label is
assigned by blinded adjudication (§9.3); the environment is fully specified. Ineligible blocks are
excluded *before* any cost is observed and their count is reported.

**[DESIGN]** Trials (`m` per arm/cap cell) are nested inside blocks. Both arms and the complete cap
grid are measured within the same block, so the arm contrast is a **within-block** comparison; `A`
and `V` are then aggregated to the source-version level for the benchmark quantities in §5.4.

### 7.2 Stratified hierarchical bootstrap

**[FACT]** NIST's e-Handbook describes the bootstrap: resample with replacement, "repeated for many
subsamples, typically between 500 and 1000", then read confidence limits off the sorted resampled
statistic (<https://www.itl.nist.gov/div898/handbook/eda/section3/bootplot.htm>).

**[DESIGN]** Because the design is nested and stratified, resample the **hierarchy**, in order:

1. **Stratum-wise, resample source-versions** with replacement within mutually exclusive,
   pre-treatment **source-level sampling strata** (§8), preserving stratum sizes.
2. Carry every selected source-version's complete task × base-environment × cap grid with it.
   Within that source-version, resample task/base-environment blocks only when those blocks were
   themselves sampled from a defined frame; otherwise keep the fixed grid and interpret the result
   as conditional on it.
3. Within each arm/cap cell, **resample trials** with replacement while preserving the matched
   repeated-measures structure. Never resample environment or cap cells independently across arms.

**[DESIGN] Recompute the whole estimand inside each replicate.** In every bootstrap replicate,
re-estimate `B`, `a₀`, `a₁`, re-derive the entire prevalence curve `S(π)`, and re-solve for `π*`.
Then take percentiles **across replicates** of the curve (pointwise band) and of `π*`. Bootstrapping
numerator and denominator separately and dividing the intervals is invalid for a ratio estimand.

**[DESIGN] Handle non-existence honestly.** In replicates where `(B − a₁ + a₀) ≤ 0` or
`π* ∉ (0, 1]`, record **"no finite break-even"** for that replicate. Report the **proportion of such
replicates** as a first-class result. Discarding them and reporting percentiles of the survivors
silently conditions on the favourable outcome and biases the interval.

**[DESIGN]** Use ≥ 1000 replicates (NIST's 500 lower bound is stated for a median; a ratio estimand
with a possibly-small denominator needs more). Report the median and a percentile interval; do not
assume normality — these cost distributions are right-skewed by construction (retry loops, reasoning
excursions, cap-exhausted runs).

**[FACT]** For a simple two-group sanity check, NIST's two-sample `t` with Welch–Satterthwaite
degrees of freedom is the standard reference
(<https://www.itl.nist.gov/div898/handbook/prc/section3/prc31.htm>). **[DESIGN]** Cross-check only;
never primary.

**[UNKNOWN]** The variance components at all three levels (between source-version, between block
within version, between trial within block) are unmeasured, so no power calculation is possible and
`n` and `m` cannot be justified in advance. A pilot must estimate them (§14).

### 7.3 Determinism cannot be assumed

**[FACT]** `temperature = 0` does not buy determinism here: Azure's reasoning models "don't
currently support the same set of parameters as other models", `reasoning_effort` defaults "vary by
model", and "Reasoning models adapt within a setting, spending fewer tokens on simple tasks and
thinking harder on complex ones"
(<https://learn.microsoft.com/azure/foundry/openai/how-to/reasoning>). **[DESIGN]** Repeated trials
are mandatory whenever a reasoning model is used. Randomize block order and counterbalance arm order
so cache warm-up (§11.2) does not align with any experimental factor.

### 7.4 Latency

**[DESIGN]** Client-side wall-clock is the primary latency measure, per Microsoft's own instruction
that gateway metrics "do not account for any client-side latency… Please refer to your own logging"
(<https://learn.microsoft.com/azure/foundry/openai/monitor-openai-reference>). Report percentiles
(p50/p90/p99), never the mean alone. Keep checker latency (milliseconds, CPU) in a separate column
from provider latency (seconds, network) — a pooled mean of the two is uninterpretable.

---

## 8. Dataset strata — pre-treatment only as primary

> **Corrected: the first draft used refutation reason and "repair fired" as primary strata. Both are
> determined *by the treatment*.**

**[DESIGN] Primary strata must be pre-treatment covariates** — fixed before the gate runs:

| Source-level sampling stratum | Levels |
|---|---|
| Source size | tokenizer-estimated input buckets (§10) |
| Source provenance | vendor / domain / corpus of origin |
| Declared tool count | frontmatter `allowed-tools` / `tools` cardinality |
| Declared structure class | single-role / multi-role / contains `rec` / contains `spawn` |

**[DESIGN] Repeated design factors are not sampling strata.** Environment profile
(`claude-ai` / `claude-code` / `none`) and enforced cap `h` are pre-treatment, but each
source-version appears in multiple such cells. Carry their complete matched grid through every
source-level resample. **[FACT]** Profile genuinely moves the verdict: 32/32 achievable under
`claude-ai`, 15/32 refuted under `claude-code` (`README.md`).

> ⚠ **[DESIGN] Post-treatment variables must not be primary strata.** Refutation reason
> (`MISSING_CAPABILITY`, `GOAL_UNSAT`, `BLOCKED_GUARD`, `NON_PROJECTABLE`, `NON_CONFORMANT`),
> "repair fired", "schema retry fired", and the verdict itself are all **outcomes of the treatment**.
> Conditioning on them opens a collider path and induces selection bias in the arm contrast. Report
> them as **mechanistic secondary analyses**, clearly labelled, never as the stratification of the
> primary estimate.

**[DESIGN]** Report the unweighted per-stratum estimate and the `π`-reweighted
**benchmark-standardized** estimate, with `π` treated as a sensitivity axis (§5.4). Pre-register a
single primary endpoint — proposed: the bootstrap band on `S_benchmark(π)` over the pre-registered
`π` grid at the pre-registered reference cap `h₀`. Do not call it a deployment-population estimate
without a deployment sampling frame and transport weights.

---

## 9. Quality and non-inferiority gates

### 9.1 Zero observed false refutations is a release rule, not a rate

> **Corrected: the first draft treated "zero spurious refutations" as if it established a zero
> rate.**

**[FACT]** The corpus evidence is *zero observed* events: FN = 0 on the 15-spec ground-truth corpus,
32/32 achievable under the home profile, 4/4 semantic packs achievable (`README.md`,
`docs/SEMANTIC_VALIDATION.md`).

**[DESIGN]** Zero events in `n` trials is a **release rule** ("ship only if no false refutation was
observed"), not an estimate that the rate is zero. Always report the **one-sided upper confidence
bound** alongside the count. **[FACT]** NIST specifies the exact (Clopper–Pearson) binomial interval,
obtained by solving the binomial CDF for the limits
(<https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm>); with zero events the one-sided
`100(1−α) %` upper limit is `p_U = 1 − α^(1/n)`, and the familiar "rule of three" `≈ 3/n` at 95 % is
its approximation. **[DESIGN]** At `n = 32`, zero events bounds the false-refutation rate only at
roughly 9 % — which is not a strong claim, and stating it honestly is more persuasive than implying
zero.

### 9.2 Four quantities, measured independently

**[DESIGN]** Do not collapse these into one "accuracy" number; they answer different questions and
have different denominators:

| Quantity | Definition | Reported as |
|---|---|---|
| **False-refutation rate** | `P(D = 1 \| Y = 0)` on oracle-**achievable** skills | Point estimate **and** one-sided upper CI (§9.1) |
| **True-refutation sensitivity** | `P(D = 1 \| Y = 1)` on oracle-**impossible** skills | Point estimate with interval; feeds `B` in §5.4 |
| **Abstention rate** | `P(verdict = UNKNOWN)`, reported separately by disposition | Point estimate; **`UNKNOWN` counts as non-detection** in the economics (exit code 3 is an abstention, not a refutation — `README.md`) |
| **Source-to-pack fidelity** | Does the compacted pack faithfully represent the source (granted capabilities, goal conjuncts, guards)? | **Blinded** adjudication (§9.3) with inter-rater agreement |

### 9.3 Blinded fidelity adjudication

**[DESIGN]** Adjudicators judging source-to-pack fidelity must be **blinded to the verdict, to the
arm, and to the compaction configuration**. Otherwise the fidelity judgement is contaminated by
knowledge of whether the checker refuted the pack. Report inter-rater agreement and adjudicate
disagreements by a pre-registered rule. Fidelity is the only measurement that can detect a
compaction which is cheap, schema-valid, and wrong.

### 9.4 Induced cases are mechanistic stress tests only

> **Corrected: the first draft allowed induced cases into the prevalence and waste estimates.**

**[FACT]** The impossible cases used to date are *induced* — by switching capability profile, or by
deterministic mutation (`src/skillc/mutate.py`, `docs/SEMANTIC_VALIDATION.md`: 6/6 mutants refuted,
naming the dropped tool or dead conjunct).

**[DESIGN]** Induced cases establish **mechanism**: given a fault of a known kind, the detector fires
and names it. They **cannot** estimate:

- the deployment prevalence `π` — the fault was injected by the experimenter;
- the natural distribution of `V` — an injected fault may be systematically cheaper or costlier
  downstream than a naturally occurring one;
- the sensitivity `P(D=1 | Y=1)` on natural faults — the injected fault classes are exactly the ones
  the detector was built for.

Report induced results in a clearly separated **mechanistic stress test** section with no
population-level inference attached.

### 9.5 Non-inferiority gate for compaction

**[DESIGN]** A cheaper compaction that produces worse packs is not a win. Two tiers:

**Tier 1 — hard gates (no margin; violation invalidates the cost result).**

- No observed false refutation, *and* the §9.1 upper bound reported.
- Every accepted pack passes `validate_pack` (`src/skillc/pack.py`).
- No capability invention — auditable post hoc by diffing declared capabilities against the source's
  granted tools; the compaction prompt's rule 1 forbids it
  (`src/skillc/frontend/llm.py`, `SYSTEM`).

**Tier 2 — margin-based non-inferiority.** **[FACT]** The fixed-margin framework is set out in FDA
guidance *Non-Inferiority Clinical Trials* (CDER/CBER, docket FDA-2010-D-0075), which "gives advice
on when NI studies intended to demonstrate effectiveness… can provide interpretable results, how to
choose the NI margin, and how to test the NI hypothesis"
(<https://www.fda.gov/regulatory-information/search-fda-guidance-documents/non-inferiority-clinical-trials>).
**[DESIGN]** Borrowed as *methodology only*; nothing about clinical regulation transfers, and the
analogy must be stated as such. Pre-specify `δ` and conclude non-inferiority when the upper bound of
the one-sided 97.5 % bootstrap CI on `Q_baseline − Q_candidate` is `< δ`.

**[UNKNOWN]** No primary source and no repository evidence justifies any particular `δ`. It must be
argued from the deployment consequence of a missed refutation. Pilot deliverable.

**[DESIGN]** Publish cost and quality **jointly**, as a two-dimensional point with a joint bootstrap
region. A single "cost per correctly-adjudicated skill" ratio hides the trade-off the gate exists to
expose.

---

## 10. OFFLINE PRE-BENCHMARK ESTIMATE (tokenizer only — not billed usage)

> **This section is a local, offline tokenizer count. It is not a measurement of the service, it
> does not involve any network call, and it must not be cited as an estimate of `A` or `Ā`.**

**[FACT] Method, exactly.** `tiktoken` 0.9.0, encoding **`o200k_base`**, run locally. The
"compaction input" is the exact string this repository would send: the module's `SYSTEM` constant
concatenated with `RUNTIME_ABILITIES_NOTE.format(abilities="; ".join(DEVELOPER_ABILITIES))`, plus the
user message `f"Natural-language skill:\n```\n{nl}\n```\nJSON pack:"`
(`src/skillc/frontend/llm.py:140-171`). The "output" is the **historical generated pack** already
committed under `demo/real-skill-cases/generated-packs/`. Sources are the five committed
natural-language `SKILL.md` files under `demo/real-skill-cases/natural-language/`.

**[FACT] Fixed system + developer-abilities prompt: 1163 tokens.**

**[FACT] Per-skill counts (reproduced by this study, `o200k_base`):**

| Skill | Input (incl. 1163 fixed) | Output (historical pack) | **Total** |
|---|---:|---:|---:|
| `algorithmic-art` | 5326 | 582 | **5908** |
| `frontend-design` | 2818 | 1195 | **4013** |
| `mcp-builder` | 3112 | 988 | **4100** |
| `slack-gif-creator` | 3157 | 1819 | **4976** |
| `webapp-testing` | 2059 | 1919 | **3978** |
| **median** | | | **4100** |
| **mean** | | | **4595** |

> ⚠ **[FACT] The totals already include the 1163-token fixed prompt. Do not add it again.** It is
> inside the "Input" column of every row.

**[DESIGN] What this supports, and only this:** request **sizing** (are we near a context or cap
limit?) and **stratification by input size** (§8). Nothing else.

**[FACT] What it explicitly excludes:**

- **billed usage** — it is a tokenizer estimate, and the counting rule "may change from model to
  model" (<https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb>);
- **schema-gate retries** (up to 3 attempts on the demo path, §1.2);
- **repair rounds** (up to 2 extra calls on the repair path, §1.2);
- **prompt caching** — the 1163-token fixed prefix is above the 1,024-token cache threshold and will
  be discounted on repeated calls (§11.2);
- **reasoning tokens** — invisible to any client tokenizer, billed as output
  (<https://learn.microsoft.com/azure/foundry/openai/how-to/reasoning>);
- **truncated / content-filtered attempts**, which are paid but useless (§11.3);
- therefore **`A` and `Ā` in every sense of §5.2**. This table is not `Ā`.

**[DESIGN] Illustrative sensitivity, non-empirical.** Purely to show the *shape* of the trade-off,
if a single undetected impossible run would otherwise incur `X` tokens of avoidable cost, the
one-shot offline proxy (mean 4595) represents:

| Hypothetical `X` per run | One-shot proxy as % of `X` |
|---:|---:|
| 10 000 | **46 %** |
| 25 000 | **18 %** |
| 50 000 | **9 %** |
| 100 000 | **4.6 %** |

Divide by the reuse count `K` for the amortized percentage (the gate is paid once per skill-version;
the avoidable cost accrues per run — §5.4). **Every number in this table is illustrative
arithmetic on a hypothetical `X`.** No `X` has been measured, the proxy is not billed usage, and
nothing here is evidence about the deployed system.

---

## 11. Threats to validity

### 11.1 Construct validity of arm B

**[UNKNOWN]** Even with the §6 restricted definition, `W(h)` depends on `h`, on the tool mocks, and
on the runtime's give-up behaviour. **[DESIGN]** The mitigations are structural, not statistical:
publish the `W(h)` curve, publish terminal-outcome distributions, label cap-exhausted runs as
censored, and never describe the result as uncapped natural waste.

### 11.2 Caching contamination

**[FACT] Provider-side.** Prompt caching is "enabled by default for supported models", requires "A
minimum of 1,024 tokens in length" with "the first 1,024 tokens in the prompt … identical", and on
GPT-5.5-and-earlier "cache hits after the first 1,024 tokens occur in 128-token increments"
(<https://learn.microsoft.com/azure/foundry/openai/how-to/prompt-caching>). **[FACT]** The
repository's compaction prompt is a **1163-token fixed prefix** (§10) followed by variable skill
text — above the threshold, and exactly the shape that caches. Consecutive trials will be
systematically cheaper than the first.

**[FACT] Cache lifetime is itself an experimental factor.** In-memory caches "typically clear…
within 5 to 10 minutes of inactivity and always remove them within one hour"; extended retention
reaches "a maximum of 24 hours" (same page).

**[FACT] Request pacing confounds cache hits.** "If requests for the same prefix and
`prompt_cache_key` combination exceed approximately **15 requests per minute**, some requests might
miss the cache. For higher-volume workloads, distribute requests across multiple keys while keeping
a stable mapping between each key and its shared prompt prefixes." (same page)

> **[DESIGN]** This makes **pacing a pre-registered experimental parameter**. A parallelised harness
> that exceeds ~15 rpm on one prefix will show partial, rate-dependent cache misses, and the measured
> arm-A cost will then depend on the harness's concurrency rather than on the compiler. Pre-register
> the request rate and the `prompt_cache_key` assignment, and report realized `cached_tokens` per
> call so the confound is visible.

**[FACT] Suppression is model-gated and fails loudly, not silently.** On GPT-5.6-and-later Standard
pay-as-you-go, `prompt_cache_options.mode = "explicit"` with no explicit breakpoints means "The
request doesn't use prompt caching or incur cache-write charges". But: "Models before the GPT-5.6
family don't support `prompt_cache_options` or `prompt_cache_breakpoint`. **Requests that include
these parameters return a `400` error.**" (same page) **[DESIGN]** So a cache-suppression flag is not
a safe portable default — on an older deployment it hard-fails the request rather than being ignored.
Pre-register per-model whether suppression is used, and treat any `400` as an apparatus fault.

**[FACT] Harness-side.** NeMo Evaluator's caching interceptor returns a stored response body on a hit
and hard-codes `latency_ms=0.0`
(<https://github.com/NVIDIA-NeMo/Evaluator/blob/main/src/nemo_evaluator/adapters/interceptors/caching.py>).
The replayed body still carries its original `usage`, so a cached run reports tokens that were never
spent *and* zero latency. Any harness-level response cache must be off; this is a correctness
requirement, not a preference.

### 11.3 Measurement plumbing

**[FACT]** Streaming without `stream_options.include_usage` yields no `usage` — a silent zero (§2.4).

**[FACT]** Unsuccessful requests "still count toward your per-minute rate limit"
(<https://learn.microsoft.com/azure/foundry/openai/how-to/quota>). In this repository they are not
retried (§1.3), so a 429 shows up as an aborted compaction rather than as inflated latency — the
opposite failure mode from an SDK-based harness, and it must be recorded as an apparatus fault, not
silently re-run.

**[FACT]** A reasoning request can return `"status": "incomplete"` with
`"incomplete_details": {"reason": "max_output_tokens"}`, and Microsoft warns "This condition can
occur before the model produces any visible output. **You pay for input and reasoning tokens but
receive no answer.**" (<https://learn.microsoft.com/azure/foundry/openai/how-to/reasoning>). The Chat
Completions analogue is `finish_reason == "length"` (§1.4). **[DESIGN]** These are paid-but-useless
requests; they belong in `A`, and dropping them biases the gate to look cheaper than it is.

### 11.4 Model and version drift

**[FACT]** Responses carry the resolved version in the top-level `model` field (Microsoft's published
example shows `"model": "o1-2024-12-17"`,
<https://learn.microsoft.com/azure/foundry/openai/how-to/reasoning>). **[DESIGN]** Record it on every
row; refuse to pool rows whose resolved `model` differs. The source corpus is already commit-pinned
(`README.md`); the model deployment needs the same discipline, and resolved model version is part of
the **environment** component of a block (§7.1).

### 11.5 Sampling and external validity

**[FACT]** The public corpus is 32 `SKILL.md` files from one vendor, all achievable under their home
profile (`README.md`). **[DESIGN]** With §9.4, this means the corpus can support mechanism claims and
size-stratification, but not a deployment prevalence. Any absolute dollar saving is conditional on an
assumed `π` and must be labelled as such.

### 11.6 Uncounted costs

**[DESIGN]** Three costs sit outside both arms and should be acknowledged rather than zeroed:

1. **Human review** at the intent-fidelity checkpoint (`CONTEXT.md`: "Intent fidelity … a
   human-review obligation"). Arm A relocates a semantic gap onto a human.
2. **The false-`ACHIEVABLE` residue.** **[FACT]** The corpus's only false positives are the two
   planted `SPURIOUS` cases attributable to payload faithfulness and intent fidelity (`README.md`);
   these consume arm-A cost *and* the avoidable cost the gate was meant to prevent.
3. **Adjudication and CI cost** for the benchmark itself.

### 11.7 Statistical hygiene

**[DESIGN]** Pre-register `n`, `m`, the entry point (§1.2), the cap grid `h`, the price-vector date,
the request pacing (§11.2), the eligibility criteria, the primary endpoint, and the analysis script
before collecting data. Treat the `S(π)` band as the estimand; do not run a null-hypothesis test
against "zero saving" — the decision-relevant question is *where the crossover lies*, and whether it
exists at all (§5.4).

---

## 12. Endpoint assignment and pre-registered configuration

> **No endpoint below was called during this study.** They are assigned roles here for
> pre-registration only.

### 12.1 Two planes, two endpoints, not interchangeable

| Endpoint | Role | Rationale |
|---|---|---|
| `https://foundary-tzuc06.openai.azure.com/openai/v1` | **System-under-test inference plane (arm A).** This is the `AZURE_OPENAI_ENDPOINT` value for `skillc compile --llm`. | It is an Azure OpenAI resource root with the v1 inference path. |
| `https://foundary-tzuc06.services.ai.azure.com/api/projects/firstProject` | **Foundry measurement / orchestration plane only.** Dataset registration, evaluation runs, result lineage. | It is a Foundry **project** endpoint of the documented form `https://<account>.services.ai.azure.com/api/projects/<project>`, consumed by `AIProjectClient(endpoint=…)` (<https://learn.microsoft.com/azure/foundry-classic/how-to/develop/cloud-evaluation>). |

> ⚠ **[FACT] The Foundry project endpoint cannot be `AZURE_OPENAI_ENDPOINT`, and this repository
> already enforces that.** The Azure path validator requires
> `parsed.path not in ("", "/openai/v1")` to raise — i.e. it accepts **only** the resource root or a
> `/openai/v1` suffix (`src/skillc/frontend/llm.py:222-225`). The project endpoint's path is
> `/api/projects/firstProject`, so it is rejected with "AZURE_OPENAI_ENDPOINT must be the resource
> root or end in /openai/v1". Note the hostname guard alone would *not* catch it: `.services.ai.azure.com`
> is an accepted host (`:217-218`). It is the **path** check that makes this safe.

**[DESIGN]** The two planes must never be conflated in configuration, in documentation, or in the
recorded evidence. Record both endpoints in the run manifest with their role labels.

### 12.2 Pre-registered Foundry usage: local `evaluate()` only

**[FACT]** Cloud custom evaluators carry a documented project-type restriction: "Specify custom
evaluators — Note: **Foundry projects aren't supported for this feature. Use a Foundry hub project
instead**", with registration via `ml_client.evaluators.create_or_update(...)`
(<https://learn.microsoft.com/azure/foundry-classic/how-to/develop/cloud-evaluation>).

**[DESIGN]** Since the supplied endpoint is a **Foundry project**, not a hub project:
**pre-register local `evaluate()`**, optionally logging results to this project via
`azure_ai_project`, and declare **cloud custom evaluators out of scope**. Do not design around a
capability the supplied resource does not have.

### 12.3 `sut_*` prefixing is mandatory

**[FACT]** `azure-ai-evaluation` already emits per-evaluator token columns
`{evaluator_name}_prompt_tokens`, `{evaluator_name}_completion_tokens`,
`{evaluator_name}_total_tokens`, `{evaluator_name}_finish_reason`, `{evaluator_name}_model`
(<https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/evaluation/azure-ai-evaluation/CHANGELOG.md>)
and logs `gen_ai.evaluation.usage.input_tokens`
(<https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/evaluation/azure-ai-evaluation/azure/ai/evaluation/_evaluate/_evaluate.py>).
**Those are the judge's tokens, not the system-under-test's.**

**[DESIGN]** Prefix every system-under-test field `sut_` — `sut_input_tokens`, `sut_output_tokens`,
`sut_cached_in`, `sut_cache_write_in`, `sut_reasoning_out`, `sut_finish_reason`, `sut_dollars`,
`sut_latency_ms`, `sut_resolved_model` — so a `sut_*` column can never be silently aggregated with an
evaluator column. **[DESIGN]** Judge/evaluator tokens are **measurement apparatus** and are excluded
from both arms; **[FACT]** they are non-trivial ("`max_token` for evaluator generation is set to 800
for most AI-assisted evaluators… 1600 for `RetrievalEvaluator` and 3000 for
`ToolCallAccuracyEvaluator`",
<https://learn.microsoft.com/azure/foundry-classic/how-to/develop/evaluate-sdk>).

### 12.4 Authentication and API-version pre-registration

**[FACT] The Entra audience `https://ai.azure.com` is correct for the v1 inference path.**
Microsoft's v1 documentation uses
`get_bearer_token_provider(DefaultAzureCredential(), "https://ai.azure.com/.default")` with
`base_url="https://YOUR-RESOURCE-NAME.openai.azure.com/openai/v1/"`
(<https://learn.microsoft.com/azure/foundry/openai/api-version-lifecycle>). **[FACT]** This
repository already requests exactly that audience: `az account get-access-token --resource
https://ai.azure.com` (`src/skillc/frontend/llm.py:284-285`).

**[FACT] Leave `AZURE_OPENAI_API_VERSION` unset.** The v1 API "removes the need for dated
`api-version` parameters", and "`api-version` is no longer a required parameter with the v1 GA API"
(same page). **[FACT]** In this repository, an unset `AZURE_OPENAI_API_VERSION` selects the
`/openai/v1/chat/completions` path and sends `model` in the payload; setting it switches to the
dated `/openai/deployments/{d}/chat/completions?api-version=…` path and omits `model`
(`src/skillc/frontend/llm.py:227-237`). **[DESIGN]** Pre-register the unset (v1) configuration; the
two paths are not interchangeable for reproducibility and must not be mixed within one study.

**[FACT] RBAC prerequisites (primary-source supported):**

| Role | Scope | Why |
|---|---|---|
| **Cognitive Services OpenAI User** | Azure OpenAI / Foundry resource | "Make inference API calls with Microsoft Entra ID" (<https://learn.microsoft.com/azure/foundry-classic/openai/how-to/role-based-access-control>); named as the Entra prerequisite for the v1 API (<https://learn.microsoft.com/azure/foundry/openai/api-version-lifecycle>) |
| **Foundry User** | Foundry project | Prerequisite for running evaluations against a Foundry project (<https://learn.microsoft.com/azure/foundry-classic/how-to/develop/cloud-evaluation>) |
| **Cognitive Services Usages Reader** | **Subscription** level | Required to view quota/usage; "must be applied at the subscription level, it doesn't exist at the resource level" (<https://learn.microsoft.com/azure/foundry/openai/how-to/quota>) — needed only for the §4 reconciliation channel |

---

## 13. Telemetry conventions, and a rejected dependency

### 13.1 OpenTelemetry GenAI: metrics are coarser than spans

> **Refinement of the review point.** The review stated the OTel standard covers only input/output
> aggregate. That is exactly right **for the metric**, and needs one correction **for the attribute
> registry**.

**[FACT] The metric is coarse.** `gen_ai.client.token.usage` is a Histogram with unit `{token}`, and
its required discriminator `gen_ai.token.type` has well-known values **`input` and `output` only**
(<https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-metrics.md>,
<https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/registry/attributes/gen-ai.md>).
There is no cached / cache-write / reasoning token type in the metric.

**[FACT] The attribute registry is finer than the metric.** The registry **does** define, all at
Development stability:
`gen_ai.usage.cache_read.input_tokens`, `gen_ai.usage.cache_write.input_tokens`,
`gen_ai.usage.reasoning.output_tokens`, plus modality variants
(<https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/registry/attributes/gen-ai.md>).
The registry's own inclusion rules are stated there: `gen_ai.usage.input_tokens` "SHOULD include all
types of input tokens, **including cached tokens**"; `gen_ai.usage.cache_write.input_tokens` "SHOULD
be included in `gen_ai.usage.input_tokens`"; `gen_ai.usage.reasoning.output_tokens` "SHOULD be
included in `gen_ai.usage.output_tokens`".

> **[DESIGN] Practical consequence.** A **span**-based ledger is covered by the convention for
> input, output, cache-read, cache-write, and reasoning. A **metric**-based ledger is covered only
> for input and output. Namespaced custom attributes are therefore needed for: (a) anything at all
> beyond input/output if you go metrics-first; (b) the `sut_*` vs judge separation (§12.3); (c)
> dollars; (d) `finish_reason` classification (§1.4); (e) the enforced cap `h` and terminal outcome
> (§6). Use a private namespace (e.g. `skillc.*`) for these and never overload a `gen_ai.*` name.
>
> **[DESIGN] Note the convention/provider tension.** OTel says cache-write "SHOULD be included in"
> input; the OpenAI-compatible provider semantics for `cache_write_tokens` are undocumented
> (§2.1). Record the raw provider fields verbatim in addition to any OTel-shaped attributes, so the
> pilot's invoice reconciliation is not blocked by a lossy convention mapping.

### 13.2 Foundry evaluation: what fits

**[FACT]** `evaluate()` accepts `data` (JSONL only), an `evaluators` dict, `evaluator_config` column
mappings, an optional `azure_ai_project`, an `output_path` that dumps "a JSON file of metric summary,
row-level data, and the metric and Foundry project URL", and a `target` that "sends queries to an
application to collect answers, and then runs your evaluators on the resulting query and response"
(<https://learn.microsoft.com/azure/foundry-classic/how-to/develop/evaluate-sdk>).

**[FACT]** Custom code-based evaluators return arbitrary numeric fields — the documented
`answer_length` example returns `outputs.answer_length.value` per row and an aggregate
`answer_length.value` in `metrics` (same page). **[DESIGN]** A `SutTokenCostEvaluator` returning the
`sut_*` fields of §12.3 fits this contract with no SDK modification.

**[FACT]** `evaluate()` returns both `metrics` and row-level `rows` (same page). **[DESIGN]** The
`rows` array is required: the hierarchical bootstrap of §7.2 cannot run on aggregate means.

**[FACT] What Foundry does not provide:** no built-in cost/token evaluator in the built-in catalogue
(categories are general-purpose, textual similarity, RAG, risk-and-safety, agentic, Azure OpenAI
graders — same page), no break-even analysis, no blocked/nested trial machinery, no hierarchical
bootstrap. **[DESIGN]** Foundry supplies orchestration, dataset versioning, row-level capture, and
lineage; the estimator, the bands, and the `S(π)` arithmetic are this project's to write.

### 13.3 Considered and rejected: NVIDIA NeMo Evaluator

> **Moved from "useful role" to "rejected", per review.**

**[FACT]** NeMo Evaluator ships a `log_tokens` response interceptor that reads only
`usage.prompt_tokens`, `usage.completion_tokens`, `usage.total_tokens` plus `resp.latency_ms`
(<https://github.com/NVIDIA-NeMo/Evaluator/blob/main/src/nemo_evaluator/adapters/interceptors/log_tokens.py>),
and a `response_stats` interceptor that accumulates `total_tokens` and `total_latency_ms` and emits a
log line only every `every`-th request (default 100)
(<https://github.com/NVIDIA-NeMo/Evaluator/blob/main/src/nemo_evaluator/adapters/interceptors/response_stats.py>).

**[FACT]** Both interceptors declare `stream_safe = False` and `best_effort = True` (same files).

**[DESIGN] Why this is rejected for this benchmark:**

1. **Insufficient fields.** It never reads `prompt_tokens_details.cached_tokens`,
   `cache_write_tokens`, or `completion_tokens_details.reasoning_tokens`, so it cannot populate the
   §5.1 dollar model on a caching or reasoning deployment.
2. **Not per-row.** `response_stats` aggregates and logs periodically; `log_tokens` writes to a
   logger, not to a joinable row keyed by block and trial. The §7.2 bootstrap needs per-trial rows
   keyed to a block.
3. **Not stream-safe** (`stream_safe = False`), and `best_effort = True` means silent omission is
   acceptable behaviour — the opposite of what a cost ledger requires.
4. **Cache hazard.** Its sibling caching interceptor replays `usage` with `latency_ms=0.0` (§11.2),
   so the stack ships a footgun adjacent to the tool.
5. **Operational overhead.** Adopting it brings Docker, NGC container pulls and credentials, and
   Hydra configuration into a repository that currently depends on `urllib` and `z3` — a large
   dependency surface for a logging line.
6. **Wrong purpose.** Its benchmark catalogue (MMLU, GSM8K, IFEval, …) measures *model capability*;
   this study measures *compiler economics*.

**[DESIGN] Recommendation instead:** a small native hook inside
`src/skillc/frontend/llm.py` that records the full `usage` dictionary, `finish_reason`, resolved
`model`, HTTP status, response headers (success **and** `HTTPError` paths, §1.3), and wall-clock —
emitting one row per call. That is a few dozen lines with zero new runtime dependencies, and it
captures strictly more than NeMo's interceptors would.

---

## 14. Instrumentation this repository would need

**[DESIGN] — proposed, not implemented. No code or configuration was modified by this study.**

1. Return the full `usage` dict, `finish_reason`, and resolved `model` alongside the text from
   `_compact_anthropic` and `_compact_azure_openai`, and thread them through `compact()` and
   `compact_with_repair()`. Today all three are discarded (§1.1, §1.4).
2. Wrap both `urlopen` calls so that status and headers are captured on the success path **and**
   inside `except urllib.error.HTTPError` (§1.3). No transport replacement required.
3. Record wall-clock per provider call and per checker invocation, separately.
4. Extend `demo/real-skill-cases/results.json` and `scripts/make_real_skill_demo.py` with a per-call
   `sut_*` cost record plus a per-source-version roll-up, and add `entry_point`
   (`compact` | `compact_with_repair`) so §1.2 is unambiguous in the evidence.
5. Add `source_tokens_est` and the tokenizer/encoding name (`o200k_base`) beside the existing
   `source_bytes`, so §10-style sizing is reproducible from the evidence file.
6. Classify each failed attempt as `{schema_violation, truncation, content_filter,
   transport_error}` rather than the current single `schema_error` bucket (§1.4).
7. Record a nullable `pack_digest` on every attempt and fail closed on a missing `usage` object:
   retain the paid call with `usage_missing=true`; never coerce missing usage to zero or exclude the
   attempt because no pack was produced.
8. Keep all arm-B harnessing outside the trusted path. The checker must remain LLM-free.

**[DESIGN] Maturity gate.** This work is at **design** maturity: researched and adversarially
reviewed, but not instrumented, piloted, or validated. It advances to **instrumented** only after
fixture tests demonstrate a one-row-per-provider-call ledger that retains successful and failed
calls (including calls with no `pack_digest`) and captures raw usage, finish/incomplete status,
resolved model, HTTP status/headers, and latency. A live arm-A pilot is a separate later gate.

---

## 15. Unknowns a pilot must settle before any headline number

| # | Unknown | Why it blocks the result |
|---|---|---|
| 1 | `cache_write_tokens` billing semantics vs invoice | The §5.1 OpenAI dollar formula is provisional until reconciled |
| 2 | `π` — deployment prevalence of impossible skills | Not identified by any corpus; induced cases cannot estimate it (§9.4) |
| 3 | `E[D·V \| Y=1]` and the `W(h)` curve | The benefit term; cap-sensitivity unknown (§6) |
| 4 | `E[A \| Y=0]` vs `E[A \| Y=1]` | Assumed equal by the factorized form; untested (§5.4) |
| 5 | `K` — runs per source-version before withdrawal | Multiplies the benefit linearly |
| 6 | Repair-round rate (2/4) and schema-retry rate (1/5) | No usable precision at these `n` |
| 7 | `P(D=1 \| Y=1)` on **natural** faults | Only induced-fault evidence exists |
| 8 | Upper bound on `P(D=1 \| Y=0)` at realistic `n` | Zero observed ≠ zero rate (§9.1) |
| 9 | Three-level variance components / ICCs | Without them `n` and `m` cannot be justified (§7.2) |
| 10 | Non-inferiority margin `δ` | Must be argued from deployment consequence (§9.5) |
| 11 | Realized cache-hit rate at the pre-registered pacing | Determines whether `A` is cache-warm or cache-cold (§11.2) |
| 12 | Reasoning-token distribution at the chosen effort level | Billed as output, invisible to tokenizers (§2.1) |
| 13 | Truncation / content-filter rate at the current 16k/32k caps | Paid-but-useless requests belong in `A` (§11.3) |
| 14 | PAYG vs PTU target | Changes the currency of the whole analysis (§5.4) |

**[DESIGN] Recommended pilot shape:** ~10 source-versions × ~3 blocks × ~5 trials, **arm A only**, on
the pre-registered entry point, at pre-registered pacing, with cache state logged rather than
suppressed, and **no arm B at all**. Deliverables: the three-level variance components, `E[A]` split
by oracle disposition, the repair/retry/truncation rates, the tokenizer-vs-`usage` residual, and the
cache-write invoice reconciliation. Any break-even number produced before that pilot is arithmetic on
unmeasured inputs.

---

## 16. Change log against the first draft (2026-08-27)

| # | Correction applied |
|---|---|
| 1 | Cost formulas split per provider; the unsupported `cache_write_tokens` subset assertion withdrawn and flagged as invoice-reconciliation pilot work; Anthropic formula adds cache read/creation without subtracting from `input_tokens` (§2.1, §2.3, §5.1) |
| 2 | Break-even restated in expectation form `E[Y·D·V] − E[A]` with prevalence sensitivity `S(π)`; the factorized `Ā/(r k W̄)` demoted to a special case with four explicit assumptions (§5.4) |
| 3 | Arm B redefined as restricted excess under an enforced cap with a matched oracle-disposition counterfactual; `W(h)` curve, terminal outcomes, and censoring required; "natural uncapped waste" language removed (§6) |
| 4 | Units changed to pre-treatment source-version × task-instance × base-environment blocks; `pack_digest` made a nullable outcome; bootstrap preserves the matched environment/cap grid and recomputes the prevalence curve; explicit "no finite break-even" reporting (§7) |
| 5 | Zero observed false refutations reframed as a release rule with a one-sided upper CI; four quality quantities separated; blinded fidelity adjudication added; induced cases restricted to mechanistic stress tests; post-treatment strata demoted from primary (§8, §9) |
| 6 | Offline tiktoken `o200k_base` pre-benchmark estimate added and reproduced locally, with explicit exclusions and illustrative-only sensitivity table (§10) |
| 7 | Endpoints assigned to inference vs measurement planes, with the repository's own path guard cited as enforcement; local `evaluate()` pre-registered; cloud custom evaluators declared out of scope; `sut_*` prefixing mandated; no endpoint called (§12) |
| 8 | Entra audience, unset `AZURE_OPENAI_API_VERSION`, and RBAC prerequisites documented from primary sources (§12.4) |
| 9 | Retry/termination discussion corrected: `urllib`, zero retries, 429 aborts; `finish_reason` recording required; header capture on both success and `HTTPError` paths, with transport replacement explicitly *not* required (§1.3, §1.4) |
| 10 | Call counts corrected: `compact_with_repair(rounds=2)` ⇒ up to 3 calls; demo path ⇒ up to 3 schema attempts; separate entry points, not summable (§1.2) |
| 11 | OTel treatment refined: metric is input/output only, but the attribute registry *does* define cache-read / cache-write / reasoning attributes; custom namespaced attributes still needed for `sut_*`, dollars, cap, and terminal outcome (§13.1) |
| 12 | NeMo Evaluator moved to considered-and-rejected with six specific reasons; small native hook recommended instead (§13.3) |
| 13 | `prompt_cache_key` ~15 rpm pacing confound added; `400`-on-older-models behaviour for `prompt_cache_options` documented as a loud, not silent, failure (§11.2) |
| 14 | All repository line-behaviour claims re-verified against current source before publication (§17) |

---

## 17. Primary sources

**Microsoft / Azure**

- Prompt caching — cached/cache-write fields, 1,024-token minimum, `prompt_cache_key` ~15 rpm, `400` on older models, retention: <https://learn.microsoft.com/azure/foundry/openai/how-to/prompt-caching>
- Reasoning models — reasoning billed as output, Responses vs Chat naming, `incomplete` responses, effort levels: <https://learn.microsoft.com/azure/foundry/openai/how-to/reasoning>
- Quota and rate limits — rate-limit estimate ≠ billing, `max_tokens` in the estimate, headers, SDK retry defaults, Usages Reader scope: <https://learn.microsoft.com/azure/foundry/openai/how-to/quota>
- Azure OpenAI monitoring data reference — token/latency metrics, PTU utilization, legacy-`Latency` warning: <https://learn.microsoft.com/azure/foundry/openai/monitor-openai-reference>
- v1 API lifecycle — `api-version` no longer required, `https://ai.azure.com/.default` audience, `Cognitive Services OpenAI User` prerequisite: <https://learn.microsoft.com/azure/foundry/openai/api-version-lifecycle>
- Azure OpenAI RBAC — role capabilities: <https://learn.microsoft.com/azure/foundry-classic/openai/how-to/role-based-access-control>
- Local evaluation with the Azure AI Evaluation SDK — `evaluate()`, `target`, custom evaluators, `metrics`/`rows`, evaluator `max_token` budgets: <https://learn.microsoft.com/azure/foundry-classic/how-to/develop/evaluate-sdk>
- Cloud evaluation — `AIProjectClient` project-endpoint form, custom-evaluator hub restriction, Foundry User role: <https://learn.microsoft.com/azure/foundry-classic/how-to/develop/cloud-evaluation>
- Azure OpenAI pricing (price vector; pin by date): <https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/>
- `azure-ai-evaluation` judge-token columns: <https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/evaluation/azure-ai-evaluation/CHANGELOG.md>, <https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/evaluation/azure-ai-evaluation/azure/ai/evaluation/_evaluate/_evaluate.py>
- Responses-vs-Chat usage adapter: <https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/evaluation/azure-ai-evaluation/azure/ai/evaluation/_byo_judge.py>

**OpenAI**

- `CompletionUsage`: <https://github.com/openai/openai-python/blob/main/src/openai/types/completion_usage.py>
- `ResponseUsage`: <https://github.com/openai/openai-python/blob/main/src/openai/types/responses/response_usage.py>
- `finish_reason` literals and meanings: <https://github.com/openai/openai-python/blob/main/src/openai/types/chat/chat_completion.py>
- `stream_options.include_usage`: <https://github.com/openai/openai-python/blob/main/src/openai/types/chat/chat_completion_stream_options_param.py>, <https://github.com/openai/openai-python/blob/main/src/openai/types/chat/chat_completion_chunk.py>
- Tokenizer-count caveat: <https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb>

**Anthropic**

- Messages `Usage` — cache creation/read as separate counters, `output_tokens` authoritative for billing, `service_tier`: <https://github.com/anthropics/anthropic-sdk-python/blob/main/src/anthropic/types/usage.py>

**NVIDIA (evaluated and rejected, §13.3)**

- `log_tokens`: <https://github.com/NVIDIA-NeMo/Evaluator/blob/main/src/nemo_evaluator/adapters/interceptors/log_tokens.py>
- `response_stats`: <https://github.com/NVIDIA-NeMo/Evaluator/blob/main/src/nemo_evaluator/adapters/interceptors/response_stats.py>
- `caching` (replays `usage`, zeroes latency): <https://github.com/NVIDIA-NeMo/Evaluator/blob/main/src/nemo_evaluator/adapters/interceptors/caching.py>

**Standards and statistics**

- OpenTelemetry GenAI metrics (`gen_ai.client.token.usage`, "MUST report billable tokens"): <https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-metrics.md>
- OpenTelemetry GenAI attribute registry (`gen_ai.usage.cache_read.input_tokens`, `…cache_write.input_tokens`, `…reasoning.output_tokens`, inclusion rules): <https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/registry/attributes/gen-ai.md>
- NIST/SEMATECH e-Handbook — bootstrap uncertainty and percentile intervals: <https://www.itl.nist.gov/div898/handbook/eda/section3/bootplot.htm>
- NIST/SEMATECH e-Handbook — exact (Clopper–Pearson) binomial confidence interval: <https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm>
- NIST/SEMATECH e-Handbook — two-sample `t` with Welch–Satterthwaite df: <https://www.itl.nist.gov/div898/handbook/prc/section3/prc31.htm>
- U.S. FDA — *Non-Inferiority Clinical Trials* (choosing the NI margin, testing the NI hypothesis; borrowed as methodology only): <https://www.fda.gov/regulatory-information/search-fda-guidance-documents/non-inferiority-clinical-trials>

**This repository (all line references re-verified against current source, 2026-08-27)**

- `src/skillc/frontend/llm.py` — `:23` default provider; `:140-171` `compact()`; `:182` / `:244`
  output caps; `:190-193` / `:259-272` response reads that discard `usage` and `finish_reason`;
  `:217-218` hostname guard; `:222-225` path guard; `:227-237` api-version branch; `:284-285` Entra
  audience; `:319-348` `compact_with_repair(rounds=2)`
- `scripts/make_real_skill_demo.py` — `:66-93` attempt loop; `:316` `--attempts` default 3
- `src/skillc/pack.py` (schema gate), `src/skillc/profiles.py` (capability contexts),
  `src/skillc/mutate.py` (induced faults)
- `demo/real-skill-cases/results.json` (evidence schema),
  `demo/real-skill-cases/natural-language/*/SKILL.md` and
  `demo/real-skill-cases/generated-packs/*.json` (§10 inputs)
- `README.md`, `CONTEXT.md`, `docs/SEMANTIC_VALIDATION.md`, `proof/SkillAchievability.v`

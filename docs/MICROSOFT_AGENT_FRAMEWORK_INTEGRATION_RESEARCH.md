# Microsoft Agent Framework Integration Research (for SkillC proposal)

> Status: **PROPOSAL ONLY**. SkillC (`check(pack, scope='goal')` → `Verdict{label, pack_digest, reason, decision_scope, refutation_scope, witness, deferred_obligations}`, and the narrower `plan_contract`) is **not implemented or tested against Microsoft Agent Framework in the inspected SkillC repository**. A separate parent-side audit of the repository found only an integration-opportunity note at `docs/HACKATHON_INTRODUCTION.md:259-264`; no `agent_framework` imports, middleware classes, or workflow code exist in the codebase today. This document records verified Agent Framework (Python) documentation/source-code capabilities and proposes — but does not claim to have built or tested — integration points. Sources are restricted to `learn.microsoft.com` and `github.com/microsoft/agent-framework`.

## Summary

Microsoft Agent Framework (Python) exposes two documented, non-experimental middleware seams that form the recommended baseline for a SkillC adapter: **agent-level middleware** (`AgentMiddleware`, with a context object documented under two names — `AgentRunContext` in the API reference and `AgentContext` in the conceptual docs; see the divergence note in §1) wraps the entire run including the model call, and **function/tool middleware** (`FunctionMiddleware`/`FunctionInvocationContext`) wraps individual tool invocations. Both can stop execution before the wrapped work happens (not calling `call_next()`/`next(context)`) and both expose a `metadata` dict for passing data between middleware. Where registering framework middleware is undesirable or its exact API for an installed version is unverified, the same effect can be achieved with an ordinary **host-level wrapper** around `agent.run(...)` (preflight) and a **tool wrapper** around the underlying tool function (per-call), calling `skillc.check(...)` before delegating — this does not depend on any Agent-Framework-internal class name and is the safest baseline where SDK version is not pinned. Independently, the **workflow graph model** (`WorkflowBuilder`, `Executor`, `WorkflowContext`, conditional/switch-case edges) supports building explicit reject/review branches: a node can route a message to a "rejected" or "needs-review" executor instead of the normal continuation, based on a precomputed SkillC verdict, without needing any interception primitive beyond ordinary conditional edges. **MCP tool integration** (`MCPStdioTool`, `MCPStreamableHTTPTool`, `MCPWebsocketTool`) is confirmed by source inspection to be availability/schema discovery only (`session.list_tools()` → `FunctionTool` objects); no precondition/postcondition or semantic-contract check exists in that path. **Observability** is a separate, passive OpenTelemetry-based plane (`agent_framework.observability.configure_otel_providers`); the baseline recommendation is ordinary OTel span/log attributes carrying an explicit, application-generated correlation ID (e.g., a run/request ID minted by the integrator) that links each SkillC `Verdict` to the corresponding span, since no framework-provided verdict-to-trace linkage was found in the reviewed docs. A separate, **experimental** package called **Agent Hooks** (`agent-hooks-sdk`) additionally documents first-class pre-model-call interception points and its own `allow`/`deny`/`transform` decision type; because it is explicitly labeled experimental, ships outside `agent-framework-core`, and its exact API can change before general availability, it is noted here only as an optional future variant, not the baseline design. None of the primitives reviewed here — core middleware `terminate` flags, workflow routing, or the optional Agent Hooks contract — natively expresses a three-way achievability judgment; the concrete recommendation is that SkillC integration code keep the three-way `Verdict.label` (ACHIEVABLE/REFUTED/UNKNOWN) intact in its own records and telemetry, and translate it into whatever binary/continue-stop primitive the chosen integration point offers only at the last step, under an explicit, integrator-declared fail-open/fail-closed policy — never collapsing UNKNOWN into either ACHIEVABLE or REFUTED before that policy is applied.

## Verified API Surfaces

### 1. Agent run interception / middleware

- **Class:** `agent_framework.AgentMiddleware` (abstract base; subclass and implement `async def process(self, context, call_next)`).
  Source: `agent_framework.AgentMiddleware` class reference — https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.agentmiddleware?view=agent-framework-python-latest
- **Context objects:** Two related context types appear in current docs:
  - `agent_framework.AgentRunContext` — "Context object for agent middleware invocations... passed through the agent middleware pipeline," with fields `agent`, `messages`, `thread`, `is_streaming`, `metadata` (dict, shared between middleware), `result` (settable to override execution), `terminate` (bool flag to stop the chain), `kwargs`.
    Source: https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.agentruncontext?view=agent-framework-python-latest
  - `agent_framework.AgentContext` — the newer conceptual-docs name for the same seam, with fields `agent`, `messages`, `session`, `options`, `stream`, `metadata`, `result`, `kwargs`, `client_kwargs`, `function_invocation_kwargs`.
    Source: "Agent Middleware" — https://learn.microsoft.com/en-us/agent-framework/concepts/agents/middleware/
  **Divergence warning:** `AgentRunContext` (API reference, `agent_framework.agentruncontext` module page) and `AgentContext` (conceptual "Agent Middleware" page) are documented with overlapping but not identical field lists (e.g., `AgentRunContext` lists `thread`/`is_streaming`; `AgentContext` lists `session`/`options`/`stream`/`client_kwargs`/`function_invocation_kwargs`). The two pages do not state whether these are the same class under two names, one superseding the other in a later release, or two distinct types for different call surfaces. **Do not assume interchangeability.** Before writing any adapter code, pin the exact `agent-framework`/`agent-framework-core` package version being targeted and inspect the installed package's actual exported symbol (e.g., `python -c "import agent_framework; print(agent_framework.AgentRunContext)"` or equivalent) rather than coding against whichever name appears in a given doc page.
- **Registration:** pass `middleware=[...]` to the `Agent`/`ChatAgent` constructor, or per-run via `agent.run(..., middleware=[...])`.
  Source: https://learn.microsoft.com/en-us/agent-framework/concepts/agents/middleware/defining-middleware
- **Execution order relative to model invocation:** Agent middleware is **outermost** — it wraps chat-client (model) middleware and function/tool middleware. Documented ordering for mixed scopes: "Agent-level middleware wraps run-level middleware... For agent middleware `[A1, A2]` and run middleware `[R1, R2]`, execution order is: `A1 -> A2 -> R1 -> R2 -> Agent -> R2 -> R1 -> A2 -> A1`." "Function/chat middleware follows the same wrapping principle at tool/chat-call time."
  Source: https://learn.microsoft.com/en-us/agent-framework/concepts/agents/middleware/ (fetched at offset ~10000)
- **Termination / short-circuit before the model is ever called:** an `AgentMiddleware.process()` implementation can simply not call `call_next()` (or not call `next(context)` in the `AgentRunContext` API surface) and set `context.result` directly. Because agent middleware is outermost and runs before the model/tool pipeline executes, this is the earliest point at which a caller can prevent any inference call. Worked example (`SecurityAgentMiddleware`) blocks a run by setting `context.result = AgentResponse(...)` and returning without calling `call_next()`.
  Source: https://learn.microsoft.com/en-us/agent-framework/concepts/agents/middleware/defining-middleware (offset ~10000–15000)

```python
# Illustrative excerpt from Microsoft's own docs sample (verbatim structure, abridged)
from agent_framework import AgentMiddleware, AgentContext, AgentResponse, Message

class SecurityAgentMiddleware(AgentMiddleware):
    async def process(self, context: AgentContext, call_next) -> None:
        last_message = context.messages[-1] if context.messages else None
        if last_message and "password" in (last_message.text or "").lower():
            context.result = AgentResponse(messages=[Message("assistant", ["blocked"])])
            return  # call_next() is never invoked -> no model call happens
        await call_next()
```

**Baseline alternative (host-level wrapper):** where the exact `AgentMiddleware`/`AgentRunContext`/`AgentContext` API for the targeted package version has not been pinned and verified, the same preflight effect can be obtained without depending on Agent Framework's middleware classes at all: application code calls `verdict = skillc.check(pack, scope='goal')` before ever calling `agent.run(...)`, and only invokes `agent.run(...)` when the policy for `verdict.label` says to proceed. This is strictly outside the framework (it does not use any Agent-Framework class), so it carries no version-compatibility risk, at the cost of not composing with other registered middleware.

### 2. Function/tool middleware and result interception

- **Class:** `agent_framework.FunctionMiddleware` (abstract base; subclass and implement `async def process(self, context, call_next)`).
  Source: https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.functionmiddleware?view=agent-framework-python-latest
- **Context object:** `agent_framework.FunctionInvocationContext` with fields `function` (the tool being invoked), `arguments` (validated, Pydantic-backed), `metadata` (dict), `result` (settable to override the actual function output), `terminate` (bool), `kwargs`.
  Source: https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.functioninvocationcontext?view=agent-framework-python-latest
- **Short-circuit before execution:** documented `CachingMiddleware` example sets `context.result = self.cache[cache_key]; context.terminate = True; return` *before* calling `next(context)`, which prevents the underlying tool function from ever executing and substitutes the middleware-supplied result. This is the mechanism for per-tool runtime veto/override.
  Source: https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.functionmiddleware?view=agent-framework-python-latest
- **Inspecting/modifying the result after execution:** middleware can call `await call_next()`/`await next(context)` then read/overwrite `context.result` afterward (as in the `LoggingFunctionMiddleware` and `ValidationMiddleware` doc examples).
  Source: https://learn.microsoft.com/en-us/agent-framework/concepts/agents/middleware/ ; https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.functioninvocationcontext?view=agent-framework-python-latest
- **Abort-the-run (not just this tool) signal — optional, version-specific:** `agent_framework.MiddlewareFailure` is documented on the **Agent Hooks** page (not on the `FunctionMiddleware`/`FunctionInvocationContext` API-reference pages inspected for this note), so its availability/behavior in the stable, non-experimental `agent-framework-core` middleware pipeline (as opposed to the separate, experimental `agent-hooks-sdk` package) was **not independently confirmed** from a core-middleware-specific source. Docs state: "Don't catch `MiddlewareFailure` in middleware. Catching it allows the loop to continue and changes fail-closed behavior to fail-open behavior." Treat this exception as an **optional** mechanism to adopt only after confirming, against the pinned package version, which module actually exports it and whether it aborts the run when raised from ordinary `FunctionMiddleware`/`AgentMiddleware` (as opposed to only from an Agent Hooks interceptor). A version-independent baseline that does not depend on this specific class: raise any ordinary Python exception from within `process()` before calling `next(context)`/`call_next()`; an uncaught exception propagating out of middleware should abort the call it wraps regardless of whether a dedicated `MiddlewareFailure` type exists, but this too should be verified against the pinned SDK version's documented exception-propagation behavior before being relied upon.
  Source: https://learn.microsoft.com/en-us/agent-framework/agents/agent-hooks (offset ~10000)
- **Do not fabricate a successful-looking result on a blocked call.** When REFUTED/UNKNOWN causes a short-circuit, `context.result` should be set to an object that is unambiguously an error/denial/deferral (e.g., a distinct error type, or a payload the calling model/application can recognize as "not executed"), never a value shaped like a normal successful tool result. Substituting a plausible-looking fabricated "success" value (even if intended as a placeholder) risks the model or downstream code treating a blocked call as if it had actually run and succeeded, which is a distinct hazard alongside preserving the tri-state verdict information (Summary; Failure-Policy Matrix below).
- **Baseline alternative (tool wrapper):** analogous to the host-level wrapper in §1, where `FunctionMiddleware`/`FunctionInvocationContext` API details for the pinned package version are not yet verified, the same per-tool effect can be obtained by wrapping the tool function itself in an ordinary Python decorator/wrapper that calls `skillc.check(...)` before delegating to the real implementation, and returns/raises an explicit denial object instead of calling through when the policy says not to proceed. This avoids any dependency on `FunctionMiddleware`'s exact context-object shape.

### 3. Workflow executor / routing

- **Classes:** `agent_framework.WorkflowBuilder`, `agent_framework.Executor` (base class; subclass and add `@handler`-decorated methods), `agent_framework.WorkflowContext` (generic context object passed to each handler, parameterized as `WorkflowContext`, `WorkflowContext[T_Out]`, or `WorkflowContext[T_Out, T_W_Out]`).
  Sources: https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.workflowbuilder?view=agent-framework-python-latest ; https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.executor?view=agent-framework-python-latest ; https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.workflowcontext?view=agent-framework-python-latest
- **Building a graph (Python):**
  ```python
  from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler

  class UpperCaseExecutor(Executor):
      @handler
      async def process(self, text: str, ctx: WorkflowContext[str]) -> None:
          await ctx.send_message(text.upper())

  builder = WorkflowBuilder(start_executor=source_executor)
  builder.add_edge(source_executor, target_executor)
  workflow = builder.build()
  ```
  Source: https://learn.microsoft.com/en-us/agent-framework/concepts/workflows/edges (direct-edge Python example)
- **Edge/routing types:** Direct, Conditional (if/else), Switch-Case (multi-branch), Multi-Selection/Fan-out, Fan-in. Conditional and switch-case edges route based on message content/predicates evaluated between executors.
  Source: https://learn.microsoft.com/en-us/agent-framework/concepts/workflows/edges
- **Vetoing/redirecting before downstream nodes run:** an `Executor`'s `@handler` method receives the message before any downstream `ctx.send_message()` call; if the handler simply does not call `ctx.send_message()` (or calls it conditionally), no message propagates to downstream executors — this is the graph-level equivalent of a veto. The docs also show an explicit "Sub-workflow Request Interception" pattern where a parent executor inspects a `SubWorkflowRequestMessage` and conditionally allows (`ctx.send_message(response, ...)`) or defers via `ctx.request_info(...)`:
  ```python
  class ParentExecutor(Executor):
      @handler
      async def handle_subworkflow_request(
          self, request: SubWorkflowRequestMessage, ctx: WorkflowContext[SubWorkflowResponseMessage],
      ) -> None:
          if self.is_allowed(request.domain):
              response = request.create_response(data=True)
              await ctx.send_message(response, target_id=request.executor_id)
          else:
              await ctx.request_info(request.source_event, response_type=request.source_event.response_type)
  ```
  Source: https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.executor?view=agent-framework-python-latest
  This is a **routing-based veto** (message simply isn't forwarded), distinct from the per-call middleware `terminate` flag — there is no separate "graph-level admission" primitive beyond conditional edges/handler logic. **Baseline recommendation:** rather than treating this only as a fallback, an explicit-branch design is straightforward to build with documented primitives alone — route to one of (at least) two named executors, e.g. a `ProceedExecutor`, a `RejectedExecutor`, and optionally a `NeedsReviewExecutor`, using a conditional or switch-case edge keyed on the precomputed `verdict.label` (ACHIEVABLE → proceed edge, REFUTED → rejected edge, UNKNOWN → needs-review edge). This keeps the three-way SkillC outcome visible as three distinct graph branches instead of collapsing it into a single boolean edge predicate.

### 4. MCP tool registration/discovery

- **Classes:** `agent_framework.MCPStdioTool` (local process via stdio), `agent_framework.MCPStreamableHTTPTool` (remote HTTP/SSE), and `agent_framework.MCPWebsocketTool` (confirmed present in source; requires `mcp[ws] --pre`).
  Source: https://learn.microsoft.com/en-us/agent-framework/agents/tools/local-mcp-tools ; class also present at `microsoft/agent-framework:python/packages/core/agent_framework/_mcp.py` (class definitions `MCPTool` ~line 870, `MCPStdioTool` ~line 3491, `MCPStreamableHTTPTool` ~line 3701, `MCPWebsocketTool` ~line 4310, per file fetched 2026-09-25; exact line numbers may drift with repo updates).
- **Usage (Python, local stdio):**
  ```python
  from agent_framework import Agent, MCPStdioTool
  async with (
      MCPStdioTool(name="calculator", command="uvx", args=["mcp-server-calculator"]) as mcp_server,
      Agent(client=OpenAIChatClient(), name="MathAgent", instructions="...") as agent,
  ):
      result = await agent.run("What is 15 * 23 + 45?", tools=mcp_server)
  ```
  Source: https://learn.microsoft.com/en-us/agent-framework/agents/tools/local-mcp-tools (offset ~5000)
- **Discovery mechanism confirmed as availability/schema only:** source inspection of `_mcp.py` shows tool discovery calls the MCP SDK's `await self.session.list_tools(params=params)` (returning `types.ListToolsResult`), then converts each entry into a framework `FunctionTool` (deduplicated by name, tracking `_MCP_IS_TOOL_KEY` / `_MCP_REMOTE_NAME_KEY` metadata). There is no precondition/postcondition, contract, or semantic-achievability check anywhere in this path — it is "does a tool with this name/schema exist and is it callable," matching the paper's "availability discovery" category, not "semantic contracts."
  Source: `microsoft/agent-framework:python/packages/core/agent_framework/_mcp.py` (function containing `tool_list = await self.session.list_tools(params=params)`, retrieved via GitHub raw content 2026-09-25; SHA `8c626de130998b626724530a654e57f5d4861f4d` at fetch time).
- **Header/identity plumbing** (`header_provider`, `static_headers`, `function_invocation_kwargs`) exists for authentication and per-run customization of MCP connections, but this is transport-layer configuration, not a semantic contract mechanism.
  Source: https://learn.microsoft.com/en-us/agent-framework/agents/tools/local-mcp-tools (offset ~10000)

### 5. Telemetry / context metadata propagation

- **Module:** `agent_framework.observability`, primary entry point `configure_otel_providers()` — sets up OpenTelemetry providers/exporters from standard `OTEL_*` environment variables; call once at startup.
  Source: https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.observability?view=agent-framework-python-latest (per web-search result; primary doc page) and https://learn.microsoft.com/en-us/agent-framework/agents/observability
- Agent Framework "emits traces, logs, and metrics according to the OpenTelemetry GenAI Semantic Conventions" — i.e., telemetry follows an external, standardized spec rather than a framework-proprietary schema.
  Source: https://learn.microsoft.com/en-us/agent-framework/agents/observability
- **Metadata dictionaries as a piggyback surface:** both `AgentRunContext`/`AgentContext.metadata` and `FunctionInvocationContext.metadata` are explicitly documented as "dictionary for sharing data between middleware" — this is the concrete, in-process (non-OTel) place a validator could stash a `Verdict` (e.g., `pack_digest`, `label`, `reason`) for downstream middleware or logging to pick up, independent of whether OTel export is configured.
  Source: https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.agentruncontext?view=agent-framework-python-latest ; https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.functioninvocationcontext?view=agent-framework-python-latest
- **Baseline recommendation — explicit, app-controlled trace linkage:** no framework-provided mechanism was found in the reviewed docs for automatically correlating a SkillC `Verdict` record with the OpenTelemetry span/trace of the run or tool call it gated. The recommended baseline is for the integrator to mint an explicit correlation identifier (e.g., a UUID generated once per `agent.run(...)` invocation) and (a) store it alongside the `Verdict` in the integrator's own audit log/record, and (b) set it as an explicit span/log attribute (e.g., via the standard OpenTelemetry Python API) within the same middleware/wrapper that produced the verdict, rather than relying on any implicit trace-ID propagation assumed to exist inside Agent Framework. This keeps the linkage under application control and independent of exact SDK internals.
- **Important scoping distinction confirmed by Agent Hooks docs:** "Agent Hooks is a control plane, not a telemetry plane... Use observability for passive tracing, metrics, and logs." This is a direct, primary-source statement that the framework itself treats governance/decision-recording and passive telemetry as separate concerns — directly relevant to how SkillC's verdict recording should be framed (as a control-adjacent audit record, not merely a trace attribute).
  Source: https://learn.microsoft.com/en-us/agent-framework/agents/agent-hooks
- Agent Hooks additionally defines `record_sink` to receive every `InterceptionRecord` (one per interception point per run, with a monotonically increasing per-session sequence number) — a structured, framework-native audit stream that a validator's verdicts could be attached to if Agent Hooks is adopted.
  Source: https://learn.microsoft.com/en-us/agent-framework/agents/agent-hooks (offset ~10000)

### 6. Stopping / abstaining before inference (pre-flight gating)

Two distinct answers, both grounded in the same two primary sources:

- **(a) Bolted-on via ordinary agent middleware or a host-level wrapper (the recommended baseline):** Because agent middleware is the outermost wrapper and its `process()` method is called *before* `call_next()`/`next(context)` triggers the chat-client (model) call, a caller can implement pre-inference gating by writing an `AgentMiddleware` subclass that inspects `context.messages` (and any `context.metadata` seeded by the caller) and simply returns without calling `call_next()`, setting `context.result` to a caller-defined abstention/refusal response (never a fabricated success response — see §2). This is documented as part of the core, non-experimental middleware pipeline (as opposed to the separate Agent Hooks package below); no specific PyPI release/version number was pinned for this claim, so "core" here means "documented in the `agent-framework-core` middleware pages," not a guarantee about any particular version's stability contract. Where the exact middleware API for the pinned version is unverified, the equivalent host-level wrapper described in §1 achieves the same effect without depending on framework internals.
  Source: https://learn.microsoft.com/en-us/agent-framework/concepts/agents/middleware/defining-middleware ; https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.agentruncontext?view=agent-framework-python-latest
- **(b) Optional, experimental note — Agent Hooks (`agent-hooks-sdk`, separate package):** Agent Hooks defines an explicit, ordered set of interception points, several of which fire strictly before any model call: `agent_startup`, `input`, and `pre_model_call`. A documented run trace is: `agent_startup -> input -> pre_model_call -> post_model_call -> pre_tool_call -> post_tool_call -> pre_model_call -> post_model_call -> output -> agent_shutdown`. An interceptor registered at `input` or `agent_startup` that returns `Verdict.deny(...)` raises `InterceptionBlocked` and prevents any subsequent `pre_model_call`/model invocation from occurring. This could in principle offer a more first-class pre-inference gate, but it is mentioned here only as an optional future variant, not the baseline design, because:
  - it is **explicitly labeled experimental** ("Agent Hooks is experimental in Python. The factory emits an `ExperimentalWarning`... its API can change before general availability"),
  - it ships in a **separate PyPI package** (`agent-hooks-sdk`, installed independently of `agent-framework-core`), implementing an external, framework-neutral spec ("AGENT-HOOKS-0.1 contract" at `github.com/responsibleai/agent-hooks`), and
  - it is **not available for .NET** at all (Python-only as of the fetched doc).
  Source: https://learn.microsoft.com/en-us/agent-framework/agents/agent-hooks
- **Explicit statement of scope, not overstated:** among the mechanisms reviewed here, none was found to have a first-class concept of "goal achievability" or "pre-inference goal admission" in the sense SkillC defines it (an epistemic tri-state verdict about whether a stated goal is achievable under given preconditions). The core middleware `terminate` flag, workflow routing, and the optional Agent Hooks `deny` verdict are all continue/stop (or allow/deny) decisions rather than achievability assessments. This is the specific, narrow gap SkillC's integration code would need to bridge: keep the three-way `Verdict.label` intact in SkillC's own records, and translate it into whichever continue/stop primitive the chosen integration point offers only as the final step, under an explicit fail-open/fail-closed policy declared by the integrator — never assumed by the framework.

## Failure-Policy Matrix

**This matrix is a PROPOSAL.** It maps SkillC's tri-state `Verdict.label` onto Agent Framework primitives documented in §1-§3 above. The baseline column uses only the core, non-experimental `AgentMiddleware`/`FunctionMiddleware` `terminate`/short-circuit mechanism (or the equivalent host-level/tool wrapper, §1-§2) and ordinary workflow reject/review branches (§3); the optional Agent Hooks contract is noted only as an alternative, version-unverified variant. Agent Framework enforces none of this by default: ACHIEVABLE is never treated as blanket "permission," nor is UNKNOWN treated as default-allow.

| SkillC `Verdict.label` | Integration point (proposed baseline) | Proposed policy | Rationale / grounding in verified API |
|---|---|---|---|
| **ACHIEVABLE** (preflight, `scope='goal'`) | Outermost `AgentMiddleware.process()` (or host-level wrapper before `agent.run(...)`), called before `call_next()` | **Proceed** — call `call_next()` (or, for a host wrapper, simply invoke `agent.run(...)`) to allow the model invocation pipeline to start. *Not* treated as blanket authorization: downstream per-tool checks (row below) still apply independently. | `AgentMiddleware` runs before any model call (§1); calling `next(context)`/`call_next()` is exactly "continue" (§1, §6a). |
| **REFUTED** (preflight) | Same hook | **Abstain** (do not call `call_next()`; set `context.result` to a caller-defined refusal/explanation object that is unambiguously *not* a normal successful response — see §2's fabrication warning) — never silently drop the request. | `context.result` is settable, and not calling `call_next()` stops the run before the model is ever invoked (§1). |
| **UNKNOWN** (preflight) | Same hook | **Defer or raise per an explicit caller-supplied policy** — e.g., raise an ordinary exception from `process()` (fail-closed) if the deployment's policy is fail-closed, or route to a human-review path (e.g., a workflow `NeedsReviewExecutor`, §3) if the policy is defer-with-approval. **Never** implicitly proceed. | Uncaught exceptions from middleware `process()` prevent `call_next()` from ever being reached (§1-§2); the specific `agent_framework.MiddlewareFailure` type, if confirmed available and behaving as documented for the pinned package version, is an optional refinement of this same idea (§2) — not a required part of the baseline. |
| **ACHIEVABLE** (runtime, per-tool `check()`) | `FunctionMiddleware.process()` (or a tool wrapper) before `next(context)` | **Proceed** — call `next(context)` (or, for a tool wrapper, delegate to the real function) to allow the actual tool function to run. | `FunctionMiddleware` runs before the tool executes and can call `next(context)` to continue (§2). |
| **REFUTED** (runtime) | Same hook | **Abstain from executing this tool call** — set `context.result` to a caller-defined error/denial object (never shaped like a successful tool result) and `context.terminate = True` *before* calling `next(context)`, mirroring the documented `CachingMiddleware` short-circuit shape (which substitutes a result without ever running the function) but with an explicit denial payload instead of a cached success value. Do not let the model believe the tool ran normally. | Verified `CachingMiddleware` pattern shows exactly this short-circuit shape (§2); the fabrication warning in §2 applies directly. |
| **UNKNOWN** (runtime) | Same hook | **Policy-dependent fail-closed default recommended**: either abstain (as REFUTED, above) or raise an ordinary exception to abort the whole run if the tool is safety-critical, per an explicit caller-declared policy — never default to letting the tool execute. | Same continue/stop mechanics as the preflight row apply at the function-middleware seam (§2); no framework-provided default policy for this case was found, so the choice must be made explicit by the integrator. |

## Proposed Integration Flow

**Ordered steps (proposed / illustrative — no part of this is implemented or tested against Agent Framework):**

1. **Goal admission preflight** — Before constructing/running the agent, application glue code calls `verdict = skillc.check(pack, scope='goal')`. This happens *outside* any Agent Framework hook (SkillC has no dependency on Agent Framework); the result is then handed to an outermost `AgentMiddleware` (or an equivalent host-level wrapper around `agent.run(...)`, per §1) as part of the middleware's/wrapper's closure/state.
2. **Agent run** — The outermost `AgentMiddleware.process()` (or host-level wrapper) inspects the precomputed `verdict.label` (or re-checks per-run using `context.messages`) and applies the failure-policy matrix above: proceed (`call_next()`), abstain (`context.result = ...; return`, with an explicit non-success denial object), or raise an ordinary exception. Only on proceed does control pass inward to chat-client middleware and eventually the model call.
3. **Per-tool runtime verification** — For each tool call the model requests, a `FunctionMiddleware.process()` (or a tool wrapper, per §2) calls a narrower, `scope='tool'`-style `skillc.check(...)` — or, for single-role Boolean cases, the narrower `plan_contract` — against `context.function`/`context.arguments`, again applying the matrix: proceed (`next(context)`), abstain (`context.result = ...; context.terminate = True; return`), or raise.
4. **Telemetry recording** — Each verdict (preflight and per-tool) is written into `context.metadata` (in-process, always available) and, where OpenTelemetry export is configured via `agent_framework.observability.configure_otel_providers()`, surfaced as span/log attributes (`pack_digest`, `label`, `reason`, `decision_scope`, `refutation_scope`) tagged with an explicit, application-generated correlation ID (§5) so the verdict can be linked back to the corresponding span without relying on any assumed framework-internal trace propagation. If the optional Agent Hooks package is separately adopted, its `record_sink`/`InterceptionRecord` stream can additionally carry the same verdict, kept conceptually separate per Agent Hooks' own "control plane, not telemetry plane" distinction — this is noted as an optional extension, not part of the baseline flow.

**Minimal labeled pseudocode (illustrative only, not real/tested code, not part of any shipped SkillC or Agent Framework artifact; class names for the middleware variant are illustrative and must be verified against the pinned package version before use — see §1's divergence warning):**

```python
# PROPOSED / ILLUSTRATIVE — not implemented, not tested against Agent Framework.
# Verify exact class/field names against the pinned agent-framework package version before coding.

class SkillCAgentGate(AgentMiddleware):
    """Preflight goal-admission gate. Runs BEFORE the model is ever called."""
    def __init__(self, pack, policy):
        self.pack, self.policy = pack, policy

    async def process(self, context, call_next) -> None:
        verdict = skillc.check(self.pack, scope="goal")  # SkillC API (given, not implemented here)
        context.metadata["skillc_preflight_verdict"] = verdict  # telemetry piggyback (Sec. 5)

        if verdict.label == "ACHIEVABLE":
            await call_next()  # proceed -- NOT treated as blanket authorization for tool calls
        elif verdict.label == "REFUTED":
            context.result = self.policy.explicit_denial_result(verdict)  # explicit non-success denial object
        else:  # UNKNOWN
            self.policy.handle_unknown(verdict)  # e.g. raise an exception, or route to human review


class SkillCToolGate(FunctionMiddleware):
    """Per-tool runtime verification. Runs BEFORE the tool function executes."""
    def __init__(self, policy):
        self.policy = policy

    async def process(self, context, call_next) -> None:
        verdict = skillc.check(pack_for(context.function, context.arguments), scope="tool")
        context.metadata["skillc_tool_verdict"] = verdict  # telemetry piggyback (Sec. 5)

        if verdict.label == "ACHIEVABLE":
            await call_next()  # allow the actual tool function to run
        elif verdict.label == "REFUTED":
            context.result = self.policy.explicit_denial_result(verdict)  # non-success denial object
            context.terminate = True  # short-circuit, mirroring documented CachingMiddleware pattern shape
        else:  # UNKNOWN
            self.policy.handle_unknown(verdict)  # explicit fail-open/fail-closed choice, never implicit
```

## Explicit Gaps / What Agent Framework Does NOT Provide

- **No native tri-state verdict type found in the reviewed primitives.** Among the mechanisms examined, plain middleware exposes `terminate: bool` (continue vs. stop); the optional Agent Hooks contract exposes `Decision` values `allow` / `deny` / `transform` (plus `warn`/`escalate` helpers). Neither is an epistemic achievability judgment; both are permission/authorization judgments. The recommendation is narrow and specific: SkillC integration code should keep `Verdict.label` (ACHIEVABLE/REFUTED/UNKNOWN) intact in its own records and only translate it into one of these continue/stop primitives at the point of use, under an explicit fail-open/fail-closed policy chosen by the integrator — this note does not claim to have surveyed every Agent Framework mechanism, only the middleware/workflow/Agent-Hooks surfaces listed above.
  Grounding: https://learn.microsoft.com/en-us/agent-framework/agents/agent-hooks (Verdicts table); https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.agentruncontext?view=agent-framework-python-latest (`terminate` field).
- **No first-class "goal achievability" or "pre-inference admission" concept was found among the mechanisms reviewed.** The non-experimental middleware pipeline (`AgentMiddleware`/`FunctionMiddleware`) provides generic "intercept and optionally stop" hooks; no notion of checking whether a stated goal is achievable before proceeding was found in the docs consulted. The Agent Hooks `input`/`agent_startup`/`pre_model_call` interception points are the closest documented analog, but are (a) explicitly labeled experimental, (b) shipped in a separate SDK/package, (c) Python-only per the fetched doc, and (d) still authorization-shaped (`allow`/`deny`), not achievability-shaped — and are treated here as an optional variant, not the baseline (§6).
  Grounding: https://learn.microsoft.com/en-us/agent-framework/agents/agent-hooks.
- **`MiddlewareFailure` attribution is ambiguous and should be re-verified before use.** The only source found for `agent_framework.MiddlewareFailure` was the Agent Hooks conceptual page, not a `FunctionMiddleware`/`FunctionInvocationContext` API-reference page; whether this exception is part of core `agent-framework-core` or specific to the `agent-hooks-sdk` package was not resolved from the sources reviewed. The baseline design in this note therefore treats it as optional and recommends verifying, against the pinned package version, which module exports it and what it does when raised from ordinary (non-Agent-Hooks) middleware, rather than depending on it in a baseline adapter.
  Grounding: https://learn.microsoft.com/en-us/agent-framework/agents/agent-hooks.
- **No semantic/contract layer for MCP tool discovery.** Discovery is confirmed (via source inspection) to be `session.list_tools()` → schema/name registration into `FunctionTool` objects. There is no precondition/postcondition or "does invoking this achieve the goal" check anywhere in the MCP integration path.
  Grounding: `microsoft/agent-framework:python/packages/core/agent_framework/_mcp.py` (tool-loading routine calling `self.session.list_tools(...)`).
- **No workflow-level first-class "admission gate" node type.** Conditional/switch-case edges and executor handler logic can be used to implement explicit reject/review branches (§3), but there is no dedicated "AdmissionGate" or "GuardNode" executor type in the documented API; any such gate must be hand-built from `Executor`/`@handler`/conditional edges.
  Grounding: https://learn.microsoft.com/en-us/agent-framework/concepts/workflows/edges ; https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.executor?view=agent-framework-python-latest.
- **Observability is explicitly NOT a control plane.** Agent Hooks' own docs state this distinction verbatim: "Agent Hooks is a control plane, not a telemetry plane... Use observability for passive tracing, metrics, and logs." A validator's verdict recording via OpenTelemetry attributes therefore cannot, by itself, enforce anything — enforcement must go through a middleware/wrapper `terminate`/denial path (§1-§2), not through telemetry. No framework-provided mechanism was found for automatically linking a verdict record to its span; the recommended baseline uses an explicit, application-generated correlation ID (§5).
  Grounding: https://learn.microsoft.com/en-us/agent-framework/agents/agent-hooks.
- **Version/compatibility caveat.** No specific `agent-framework` / `agent-framework-core` PyPI version number or exact repository commit/tag was pinned for this research; documentation pages carry internal `ms.date`/`updated_at` metadata in the range 2025-10 through 2026-09, and the `_mcp.py` source file was fetched at commit SHA `8c626de130998b626724530a654e57f5d4861f4d` (blob SHA, not a repo tag) on 2026-09-25. Terms such as "core" or "non-experimental" in this note describe how a page positions a feature relative to the separate, explicitly-labeled-experimental Agent Hooks package — they are not a claim about release/stability guarantees for any specific version, and should not be read as such. Agent Hooks is explicitly called experimental and its API "can change before general availability," so none of the Agent-Hooks-specific claims above should be read as stable/guaranteed across future releases. Any manuscript or adapter code should pin and re-verify the exact package version before relying on any class/field name in this note.

## Source List

**Compact API mapping (baseline design, exact names as documented/found):**

| Integration point | Exact API (Python) | Verified via |
|---|---|---|
| Run-wide preflight admission | `agent_framework.AgentMiddleware.process(context, call_next)`; context documented as `AgentRunContext` (API ref) / `AgentContext` (concepts) — pin version, §1 | Middleware concepts + API reference pages |
| Run-wide preflight (version-independent fallback) | Host-level wrapper: call `skillc.check(pack, scope='goal')` before `agent.run(...)` | N/A — plain application code, no framework dependency |
| Per-tool runtime verification | `agent_framework.FunctionMiddleware.process(context, call_next)`; context = `FunctionInvocationContext` (`function`, `arguments`, `result`, `terminate`, `metadata`) | `FunctionMiddleware`/`FunctionInvocationContext` API reference pages |
| Per-tool runtime (version-independent fallback) | Ordinary function wrapper/decorator around the tool implementation | N/A — plain application code |
| Explicit reject/review branch | `agent_framework.WorkflowBuilder` + `agent_framework.Executor` (`@handler`) + conditional/switch-case edges | Workflow edges concepts page + `Executor` API reference |
| Telemetry | `agent_framework.observability.configure_otel_providers()` + OpenTelemetry GenAI semantic conventions; app-controlled correlation ID for verdict-to-span linkage | Observability concepts + API reference page |
| MCP tool discovery (availability only, no semantic contract) | `agent_framework.MCPStdioTool`, `agent_framework.MCPStreamableHTTPTool`, `agent_framework.MCPWebsocketTool`; `session.list_tools()` → `FunctionTool` | Local MCP tools doc + `_mcp.py` source |
| Optional/experimental pre-model-call gate | `agent-hooks-sdk`: `agent_startup`/`input`/`pre_model_call` interceptors, `Verdict.allow/deny/transform`, `MiddlewareFailure` (attribution unverified against core, §2/Gaps) | Agent Hooks conceptual page |

**Strongest citations for manuscript use (3-4 primary sources):**

1. https://learn.microsoft.com/en-us/agent-framework/concepts/agents/middleware/defining-middleware — Adding middleware to agents (Python `AgentMiddleware`/`FunctionMiddleware` code samples, short-circuit patterns)
2. https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.agentmiddleware?view=agent-framework-python-latest — `AgentMiddleware` API reference (canonical class for run-wide preflight)
3. https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.functionmiddleware?view=agent-framework-python-latest — `FunctionMiddleware` API reference (canonical class for per-tool verification)
4. https://learn.microsoft.com/en-us/agent-framework/agents/observability — Observability/OpenTelemetry integration (telemetry plane, distinct from any control/admission mechanism)

Full list of primary sources used (learn.microsoft.com and github.com/microsoft/agent-framework only):

- https://learn.microsoft.com/en-us/agent-framework/concepts/agents/middleware/ — Agent Middleware overview (three middleware types, ordering rules, `AgentContext`/`FunctionInvocationContext` fields)
- https://learn.microsoft.com/en-us/agent-framework/concepts/agents/middleware/defining-middleware — Adding middleware to agents (Python code samples, `SecurityAgentMiddleware` short-circuit example)
- https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.agentruncontext?view=agent-framework-python-latest — `AgentRunContext` API reference
- https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.agentmiddleware?view=agent-framework-python-latest — `AgentMiddleware` API reference
- https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.functionmiddleware?view=agent-framework-python-latest — `FunctionMiddleware` API reference (`CachingMiddleware` short-circuit example)
- https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.functioninvocationcontext?view=agent-framework-python-latest — `FunctionInvocationContext` API reference
- https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.workflowbuilder?view=agent-framework-python-latest — `WorkflowBuilder` API reference
- https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.executor?view=agent-framework-python-latest — `Executor` API reference (handler discovery, sub-workflow request interception pattern)
- https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.workflowcontext?view=agent-framework-python-latest — `WorkflowContext` API reference
- https://learn.microsoft.com/en-us/agent-framework/concepts/workflows/edges — Workflow edge types and routing (Direct, Conditional, Switch-Case, Fan-out, Fan-in)
- https://learn.microsoft.com/en-us/agent-framework/agents/tools/local-mcp-tools — MCP tool usage (`MCPStdioTool`, `MCPStreamableHTTPTool`, header providers)
- https://learn.microsoft.com/en-us/agent-framework/agents/observability — Observability / OpenTelemetry integration
- https://learn.microsoft.com/en-us/agent-framework/agents/agent-hooks — Agent Hooks (experimental first-class governance/interception contract: `agent_startup`, `input`, `pre_model_call`, `pre_tool_call`, `post_tool_call`, `output`, `agent_shutdown`; `Verdict`/`Decision` types; `MiddlewareFailure`; `record_sink`)
- `microsoft/agent-framework:python/packages/core/agent_framework/_mcp.py` — source-code confirmation that MCP tool discovery is schema/name registration only (`session.list_tools()` → `FunctionTool`), fetched via GitHub raw content, blob SHA `8c626de130998b626724530a654e57f5d4861f4d`, 2026-09-25.

Auxiliary (non-authoritative, used only to locate the above primary URLs during discovery, not cited for factual claims): general web search result summaries pointing to the above learn.microsoft.com and github.com/microsoft/agent-framework pages.

"""WP0 spike: the four facts the skillc Agent Framework adapter rests on.

Runs a real Agent Framework agent against a Foundry project and answers:

  F1  does function middleware fire for MCP tools (the toolbox is an MCP endpoint)?
  F2  does a denied call (context.result set, call_next skipped) reach the model as the
      tool result, so the model re-plans instead of crashing?
  F3  what exactly are context.function.name and context.arguments?
  F4  are the agent's tool names readable before the first run?

Not part of skillc. Needs:  pip install --pre agent-framework-core agent-framework-foundry
azure-identity;  az login;  FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL set.  The MCP
server is the public Microsoft Learn one (no credentials), which stands in for a toolbox:
both are streamable-HTTP MCP endpoints.

    python scripts/spike_agent_framework.py [--json out.json]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import traceback
from collections.abc import Awaitable, Callable
from typing import Any

FINDINGS: dict[str, Any] = {"versions": {}, "F1": None, "F2": None, "F3": None, "F4": None,
                            "log": []}


def log(msg: str) -> None:
    print(msg, flush=True)
    FINDINGS["log"].append(msg)


def versions() -> None:
    from importlib.metadata import PackageNotFoundError, version
    for name in ("agent-framework-core", "agent-framework-foundry", "agent-framework",
                 "azure-identity", "mcp", "pydantic"):
        try:
            FINDINGS["versions"][name] = version(name)
        except PackageNotFoundError:
            pass
    log(f"versions: {FINDINGS['versions']}")


async def main(mcp_url: str) -> None:
    from agent_framework import (Agent, FunctionInvocationContext, FunctionMiddleware,
                                 MCPStreamableHTTPTool)
    from agent_framework.foundry import FoundryChatClient
    from azure.identity.aio import AzureCliCredential

    endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
    model = os.environ["FOUNDRY_MODEL"]
    seen: list[dict] = []
    deny_once = {"armed": True}

    class Probe(FunctionMiddleware):
        async def process(self, context: FunctionInvocationContext,
                          call_next: Callable[[], Awaitable[None]]) -> None:
            args = context.arguments
            record = {
                "name": getattr(context.function, "name", None),
                "function_type": type(context.function).__name__,
                "arguments_type": type(args).__name__,
                "arguments": (args.model_dump() if hasattr(args, "model_dump")
                              else args if isinstance(args, dict) else repr(args)),
                "kwargs_keys": sorted((context.kwargs or {}).keys()),
            }
            if deny_once["armed"]:
                deny_once["armed"] = False
                context.result = {"skillc": "blocked",
                                  "reason": "skillc: no approved plan. Say the word "
                                            "BLOCKED-ACK in your answer and do not retry."}
                record["denied"] = True
                seen.append(record)
                return                                  # F2: no call_next()
            await call_next()
            record["denied"] = False
            record["result_type"] = type(context.result).__name__
            record["result_head"] = str(context.result)[:200]
            seen.append(record)

    # the Azure CLI on Windows can take well over the 10 s default to answer
    async with AzureCliCredential(process_timeout=180) as credential:
        client = FoundryChatClient(project_endpoint=endpoint, model=model,
                                   credential=credential)
        mcp = MCPStreamableHTTPTool(name="mslearn", url=mcp_url, approval_mode="never_require")
        async with mcp:
            async with Agent(client=client, name="skillc-spike",
                             instructions="Answer briefly. Use the mslearn tool to look up "
                                          "Microsoft Learn documentation when asked.",
                             tools=[mcp], middleware=[Probe()]) as agent:
                # F4: tool names before any run (where does the framework keep them?)
                def fn_names(obj: Any) -> list[str]:
                    fns = getattr(obj, "functions", None)
                    if callable(fns):
                        try:
                            fns = fns()
                        except TypeError:
                            fns = None
                    return [getattr(f, "name", repr(f)) for f in (fns or [])]

                mcp_names = fn_names(mcp)
                agent_attrs = {a: type(getattr(agent, a)).__name__ for a in dir(agent)
                               if not a.startswith("__") and ("tool" in a or "function" in a)}
                agent_tool_names: list[str] = []
                for a in ("tools", "_tools"):
                    for t in getattr(agent, a, None) or []:
                        agent_tool_names += fn_names(t) or [getattr(t, "name", type(t).__name__)]
                FINDINGS["F4"] = {"mcp_tool_functions": mcp_names,
                                  "agent_tool_attrs": agent_attrs,
                                  "agent_tool_names": agent_tool_names}
                log(f"F4 mcp functions after connect: {mcp_names}")
                log(f"F4 agent attrs mentioning tool/function: {agent_attrs}")
                log(f"F4 agent tool names: {agent_tool_names}")

                prompt = ("Use the mslearn tool to search Microsoft Learn for 'Foundry hosted "
                          "agents idle timeout' and tell me the idle timeout range in one line.")
                result = await agent.run(prompt)
                text = result.text or ""
                log(f"model answer: {text[:400]}")

    FINDINGS["F1"] = {"middleware_fired_for_mcp_tool": bool(seen),
                      "calls_seen": len(seen)}
    FINDINGS["F2"] = {"denial_seen_by_model": "BLOCKED-ACK" in text,
                      "model_retried_after_denial": len(seen) > 1,
                      "answer_head": text[:300]}
    FINDINGS["F3"] = seen[:3]
    log(f"F1: {FINDINGS['F1']}")
    log(f"F2: {FINDINGS['F2']}")
    log(f"F3: {json.dumps(FINDINGS['F3'], default=str)[:800]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write findings here")
    ap.add_argument("--mcp-url", default="https://learn.microsoft.com/api/mcp")
    a = ap.parse_args()
    versions()
    try:
        asyncio.run(main(a.mcp_url))
    except Exception:  # noqa: BLE001 - a spike reports, it does not hide
        FINDINGS["error"] = traceback.format_exc()
        log(FINDINGS["error"])
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(FINDINGS, f, indent=1, default=str)
        print(f"wrote {a.json}")
    sys.exit(1 if FINDINGS.get("error") else 0)

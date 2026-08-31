"""Load achievability fact packs exposed as MCP resources."""
from __future__ import annotations

import asyncio
import base64
import copy
import json
import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from .pack import validate_pack
from .profiles import normalize_tool


class MCPResourceError(RuntimeError):
    """Raised when an MCP resource cannot supply one valid fact pack."""


_CAPABILITY_FIELDS = {"owner", "pre", "add", "del", "assigns", "nondet"}


def _field(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def decode_resource(result: Any) -> dict:
    """Decode a resources/read result containing one JSON fact pack."""
    contents = _field(result, "contents")
    if not isinstance(contents, Sequence) or isinstance(contents, (str, bytes)):
        raise MCPResourceError("MCP resources/read response has no content list")
    if len(contents) != 1:
        raise MCPResourceError(
            f"fact-pack resource must contain exactly one item, got {len(contents)}")

    content = contents[0]
    text = _field(content, "text")
    if text is None:
        blob = _field(content, "blob")
        if blob is None:
            raise MCPResourceError("fact-pack resource is neither text nor blob content")
        try:
            text = base64.b64decode(blob, validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise MCPResourceError("fact-pack resource blob is not base64 UTF-8") from exc

    try:
        pack = json.loads(text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise MCPResourceError("fact-pack resource is not valid JSON") from exc
    if not isinstance(pack, dict):
        raise MCPResourceError("fact-pack resource JSON must be an object")
    validate_pack(pack)
    return pack


def decode_tools_page(result: Any) -> tuple[list[Any], str | None]:
    """Decode one tools/list page without depending on SDK model classes."""
    tools = _field(result, "tools")
    if not isinstance(tools, Sequence) or isinstance(tools, (str, bytes)):
        raise MCPResourceError("MCP tools/list response has no tool list")
    cursor = _field(result, "nextCursor")
    if cursor is None:
        cursor = _field(result, "next_cursor")
    if cursor is not None and not isinstance(cursor, str):
        raise MCPResourceError("MCP tools/list next cursor must be a string")
    return list(tools), cursor


def tool_names(tools: Sequence[Any]) -> list[str]:
    """Return normalized, unique names advertised by tools/list."""
    names = []
    for tool in tools:
        name = _field(tool, "name")
        if not isinstance(name, str) or not name.strip():
            raise MCPResourceError("MCP tools/list contains a tool without a name")
        normalized = normalize_tool(name)
        if normalized not in names:
            names.append(normalized)
    return names


def infer_capabilities(tools: Sequence[Any]) -> dict[str, dict]:
    """Infer pack capabilities from MCP tool availability and annotations."""
    capabilities = {}
    for tool in tools:
        (name,) = tool_names([tool])
        predicate = "used_" + re.sub(r"[^a-z0-9_]", "_", name)
        metadata = _field(tool, "_meta")
        if metadata is None:
            metadata = _field(tool, "meta")
        skillc = _field(metadata, "skillc") if metadata is not None else None
        if skillc is not None and not isinstance(skillc, Mapping):
            raise MCPResourceError(f"tool {name!r} has invalid _meta.skillc facts")
        if skillc:
            unknown = set(skillc) - _CAPABILITY_FIELDS
            if unknown:
                raise MCPResourceError(
                    f"tool {name!r} has unknown skillc facts: {sorted(unknown)}")
            capability = dict(skillc)
            capability.setdefault("owner", "agent")
            capability["add"] = list(capability.get("add", []))
            if predicate not in capability["add"]:
                capability["add"].append(predicate)
        else:
            capability = {"owner": "agent", "add": [predicate]}
        capabilities[name] = capability
    return capabilities


def enrich_pack(pack: dict, tools: Sequence[Any],
                replace: set[str] | None = None) -> dict:
    """Add MCP-inferred capabilities while preserving explicit pack facts."""
    enriched = copy.deepcopy(pack)
    capabilities = enriched.setdefault("capabilities", {})
    for name, inferred in infer_capabilities(tools).items():
        if name not in capabilities or (replace and name in replace):
            capabilities[name] = inferred
    validate_pack(enriched)
    return enriched


async def collect_tool_pages(
        list_page: Callable[[str | None], Awaitable[Any]]) -> list[Any]:
    """Collect a paginated tools/list operation and reject cursor cycles."""
    tools = []
    cursor = None
    seen_cursors = set()
    while True:
        result = await list_page(cursor)
        page, cursor = decode_tools_page(result)
        tools.extend(page)
        if cursor is None:
            return tools
        if cursor in seen_cursors:
            raise MCPResourceError(f"MCP tools/list repeated cursor {cursor!r}")
        seen_cursors.add(cursor)


async def _read_stdio_resource(command: str, args: list[str], uri: str) -> Any:
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError as exc:
        raise MCPResourceError(
            'MCP support requires the optional dependency: pip install "skillc[mcp]"'
        ) from exc

    parameters = StdioServerParameters(command=command, args=args)
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            return await session.read_resource(uri)


async def _list_stdio_tools(command: str, args: list[str]) -> list[Any]:
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError as exc:
        raise MCPResourceError(
            'MCP support requires the optional dependency: pip install "skillc[mcp]"'
        ) from exc

    parameters = StdioServerParameters(command=command, args=args)
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            async def list_page(cursor: str | None) -> Any:
                return (await session.list_tools(cursor=cursor)
                        if cursor else await session.list_tools())

            return await collect_tool_pages(list_page)


def load_pack(command: str, args: list[str], uri: str) -> dict:
    """Read and validate a fact pack from a stdio MCP server resource."""
    try:
        result = asyncio.run(_read_stdio_resource(command, args, uri))
    except MCPResourceError:
        raise
    except Exception as exc:
        raise MCPResourceError(f"failed to read MCP resource {uri!r}: {exc}") from exc
    return decode_resource(result)


def discover_tools(command: str, args: list[str]) -> list[Any]:
    """Return all tools advertised by a stdio MCP server, across pages."""
    try:
        return asyncio.run(_list_stdio_tools(command, args))
    except MCPResourceError:
        raise
    except Exception as exc:
        raise MCPResourceError(f"failed to list MCP tools: {exc}") from exc

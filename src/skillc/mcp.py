"""Load achievability fact packs exposed as MCP resources."""
from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import Mapping, Sequence
from typing import Any

from .pack import validate_pack


class MCPResourceError(RuntimeError):
    """Raised when an MCP resource cannot supply one valid fact pack."""


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


def load_pack(command: str, args: list[str], uri: str) -> dict:
    """Read and validate a fact pack from a stdio MCP server resource."""
    try:
        result = asyncio.run(_read_stdio_resource(command, args, uri))
    except MCPResourceError:
        raise
    except Exception as exc:
        raise MCPResourceError(f"failed to read MCP resource {uri!r}: {exc}") from exc
    return decode_resource(result)
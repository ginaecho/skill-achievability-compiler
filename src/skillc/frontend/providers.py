"""LLM provider clients: one text completion per call, no retries, no state.

Credentials stay in provider-specific environment variables; nothing here is
used unless a caller opts into the LLM front-end.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from urllib.parse import quote, urlencode, urlparse

DEFAULT_PROVIDER = "anthropic"
DEFAULT_MODEL = "claude-sonnet-5"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
PROVIDERS = ("anthropic", "azure-openai")


# Usage blocks of the provider calls made inside `metered()` (None: not metering).
_USAGE: ContextVar[list[dict] | None] = ContextVar("skillc_llm_usage", default=None)


@contextmanager
def metered() -> Iterator[list[dict]]:
    """Collect the token usage every provider call inside the block reports.

    Yields a list that fills with Anthropic-shaped usage blocks
    (``input_tokens``, ``output_tokens``, ``cache_read_input_tokens``, ...);
    `skillc.tokens.measured_cost` turns it into a measured `Cost`.
    """
    usage: list[dict] = []
    token = _USAGE.set(usage)
    try:
        yield usage
    finally:
        _USAGE.reset(token)


def _record_usage(usage: dict | None) -> None:
    sink = _USAGE.get()
    if sink is not None and usage:
        sink.append(usage)


def _azure_usage(usage: dict | None) -> dict | None:
    """An OpenAI-style usage block in the Anthropic shape (prompt tokens
    include the cached ones there; here they are separated)."""
    if not usage:
        return None
    cached = int((usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
    return {"input_tokens": int(usage.get("prompt_tokens", 0)) - cached,
            "output_tokens": int(usage.get("completion_tokens", 0)),
            "cache_read_input_tokens": cached}


def resolve_provider(provider: str | None = None) -> str:
    """`provider`, else SKILLC_LLM_PROVIDER, else the default; validated."""
    selected = (provider or os.environ.get("SKILLC_LLM_PROVIDER")
                or DEFAULT_PROVIDER).lower()
    if selected not in PROVIDERS:
        raise RuntimeError(
            f"unsupported LLM provider {selected!r}; choose one of {PROVIDERS}")
    return selected


def complete(provider: str, system: str, user: str, model: str | None,
             timeout: int, json_mode: bool = True) -> str:
    """One completion from `provider` (already resolved)."""
    if provider == "anthropic":
        return anthropic_complete(system, user, model or DEFAULT_MODEL, timeout)
    return azure_openai_complete(system, user, model, timeout, json_mode=json_mode)


def anthropic_complete(system: str, user: str, model: str,
                       timeout: int) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set; the LLM front-end is "
                           "opt-in")
    body = json.dumps({
        "model": model,
        "max_tokens": 16000,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }).encode()
    req = urllib.request.Request(
        ANTHROPIC_API_URL, data=body,
        headers={"content-type": "application/json", "x-api-key": key,
                 "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.load(r)
    _record_usage(out.get("usage"))
    return "".join(b.get("text", "") for b in out.get("content", [])
                   if b.get("type") == "text").strip()


def azure_openai_complete(system: str, user: str, model: str | None,
                          timeout: int, json_mode: bool = True) -> str:
    key = os.environ.get("AZURE_OPENAI_API_KEY")
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    deployment = model or os.environ.get("AZURE_OPENAI_DEPLOYMENT")
    missing = [
        name for name, value in (
            ("AZURE_OPENAI_ENDPOINT", endpoint),
            ("AZURE_OPENAI_DEPLOYMENT or --model", deployment),
        ) if not value
    ]
    if missing:
        raise RuntimeError(
            "Azure OpenAI compaction requires " + ", ".join(missing))

    assert endpoint is not None and deployment is not None
    base = endpoint.rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError("AZURE_OPENAI_ENDPOINT must be an https URL")
    host = (parsed.hostname or "").lower()
    if not host.endswith((".openai.azure.com", ".services.ai.azure.com")):
        raise RuntimeError(
            "AZURE_OPENAI_ENDPOINT must use an official Azure OpenAI or "
            "Foundry hostname")
    if parsed.query or parsed.fragment or parsed.path not in ("", "/openai/v1"):
        raise RuntimeError(
            "AZURE_OPENAI_ENDPOINT must be the resource root or end in "
            "/openai/v1")

    api_version = os.environ.get("AZURE_OPENAI_API_VERSION")
    if api_version:
        root = base.removesuffix("/openai/v1")
        query = urlencode({"api-version": api_version})
        url = (f"{root}/openai/deployments/{quote(deployment, safe='')}"
               f"/chat/completions?{query}")
        include_model = False
    else:
        v1 = base if base.endswith("/openai/v1") else base + "/openai/v1"
        url = v1 + "/chat/completions"
        include_model = True

    payload = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_completion_tokens": 32000,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    if include_model:
        payload["model"] = deployment
    headers = {"content-type": "application/json"}
    if key:
        headers["api-key"] = key
    else:
        headers["authorization"] = "Bearer " + azure_cli_token()
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.load(r)
    _record_usage(_azure_usage(out.get("usage")))
    choices = out.get("choices", [])
    if not choices:
        raise ValueError("Azure OpenAI response contained no choices")
    content = choices[0].get("message", {}).get("content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "".join(
            item.get("text", "") for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ).strip()
    raise ValueError("Azure OpenAI response message content was not text")


def azure_cli_token() -> str:
    """Get a short-lived Foundry token from the current Azure CLI login."""
    executable = shutil.which("az.cmd") or shutil.which("az")
    if not executable:
        raise RuntimeError(
            "AZURE_OPENAI_API_KEY is not set and Azure CLI is unavailable")
    try:
        proc = subprocess.run(
            [
                executable, "account", "get-access-token",
                "--resource", "https://ai.azure.com",
                "--query", "accessToken", "--output", "tsv",
            ],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as e:
        raise RuntimeError(
            "AZURE_OPENAI_API_KEY is not set and Azure CLI is unavailable"
        ) from e
    token = proc.stdout.strip()
    if proc.returncode or not token:
        detail = proc.stderr.strip() or "Azure CLI returned no access token"
        raise RuntimeError(
            "Azure OpenAI authentication failed; set AZURE_OPENAI_API_KEY "
            f"or run az login ({detail})")
    return token


def extract_json_object(text: str) -> dict:
    """Pull the first balanced top-level JSON object out of model output
    (tolerates prose or code fences around it)."""
    start = text.find("{")
    if start < 0:
        raise ValueError(f"no JSON object in model output: {text[:200]!r}")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("unbalanced JSON object in model output "
                     "(truncated response?)")

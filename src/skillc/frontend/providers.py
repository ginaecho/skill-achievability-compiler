"""LLM provider clients: guarded text and structured chat requests, no retries.

Credentials stay in provider-specific environment variables; nothing here is
used unless a caller opts into the LLM front-end.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from urllib.parse import quote, urlencode, urlparse

from .copilot_guard import NativeEnvelopeGuard, implementation_hash
from .urlguard import guarded_body, restore

DEFAULT_PROVIDER = "anthropic"
DEFAULT_MODEL = "claude-sonnet-5"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
PROVIDERS = ("anthropic", "azure-openai")


class ModelCallsDisabled(RuntimeError):
    """A real model call was attempted without SKILLC_ALLOW_MODEL_CALLS=1."""


class CopilotSessionTimeout(RuntimeError):
    """The owned native session exceeded its deadline; accounting can be partial."""

    def __init__(self, message: str, receipt: dict):
        super().__init__(message)
        self.receipt = receipt


def require_model_opt_in() -> None:
    """Refuse any real model request unless the run opted in explicitly.

    Model calls cost money and send text to an outside service, so they never
    happen by default: a benchmark run sets SKILLC_ALLOW_MODEL_CALLS=1 on purpose.
    Request bodies are also scrubbed of URLs (see `urlguard`)."""
    if os.environ.get("SKILLC_ALLOW_MODEL_CALLS") != "1":
        raise ModelCallsDisabled(
            "model calls are off; set SKILLC_ALLOW_MODEL_CALLS=1 for a deliberate run")


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
             timeout: int, json_mode: bool = True,
             image: tuple[bytes, str] | None = None) -> str:
    """One completion from `provider` (already resolved). `image` is (bytes, media type),
    sent beside the text for a model that reads pictures; text inside a picture cannot be
    scrubbed of URLs, so callers send only pictures the user chose to send."""
    if provider == "anthropic":
        if image is None:
            return anthropic_complete(system, user, model or DEFAULT_MODEL, timeout)
        return anthropic_complete(system, user, model or DEFAULT_MODEL, timeout, image=image)
    if image is None:
        return azure_openai_complete(system, user, model, timeout, json_mode=json_mode)
    return azure_openai_complete(system, user, model, timeout, json_mode=json_mode,
                                 image=image)


def _b64(image: tuple[bytes, str]) -> tuple[str, str]:
    import base64
    data, mime = image
    if mime not in ("image/png", "image/jpeg", "image/gif", "image/webp"):
        raise ValueError(f"unsupported image type {mime!r}")
    return base64.b64encode(data).decode("ascii"), mime


def copilot_text_session(system: str, user: str, model: str, timeout: int, *,
                         directory: Path, token: str) -> tuple[str, dict]:
    """One tool-free subscription session, with fresh state and a native usage receipt.

    Unlike the API completions, this returns raw native usage rather than converting
    undocumented token fields to the API metering shape. Artifacts are retained
    in the caller's new directory, including failed attempts.
    """
    return _copilot_session(system, user, model, timeout, directory=directory, token=token)


def copilot_mcp_session(system: str, user: str, model: str, timeout: int, *,
                        directory: Path, token: str, server: dict,
                        text_receipt: Path) -> tuple[str, dict]:
    """A fresh subscription agent with one trusted MCP sandbox tool, no host tools.

    The caller owns the server command and must constrain its actions independently.
    Tool responses must use the private replacement table before guarded_body.
    """
    return _copilot_session(system, user, model, timeout, directory=directory,
                            token=token, server=server, text_receipt=text_receipt)


def verify_copilot_text_receipt(path: Path | None, model: str) -> None:
    proof = json.loads(path.read_text(encoding="utf-8")) if path else {}
    audit = proof.get("envelope_guard", {})
    usage = proof.get("usage_native", [])
    if (proof.get("status") != "completed" or proof.get("served_models") != [model]
            or audit.get("implementation_sha256") != implementation_hash()
            or audit.get("model_requests", 0) <= 0 or not usage
            or any(u.get("isByok") is not False for u in usage)):
        raise ValueError(
            "A verified exact-model subscription text transport receipt is required before tools")


def _copilot_native_metadata(rows: list[dict]) -> dict:
    usage = [row["data"] for row in rows if row.get("type") == "assistant.usage"]
    served = {row["data"].get("responseChunk", {}).get("model") for row in rows
              if row.get("type") == "model.model_call_success"}
    return {"usage_native": usage, "served_models": sorted(str(m) for m in served)}


def read_session_events(path: Path, *, interrupted: bool = False) -> tuple[list[dict], bool]:
    """Read JSONL events; only interrupted sessions may end in a truncated record."""
    rows = []
    truncated = False
    lines = path.read_bytes().splitlines(keepends=True)
    for index, line in enumerate(lines):
        try:
            row = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError):
            if not interrupted or index != len(lines) - 1 or line.endswith(b"\n"):
                raise
            truncated = True
            continue
        if not isinstance(row, dict):
            raise ValueError(f"Session event is not an object: {path}")
        rows.append(row)
    return rows, truncated


def _copilot_session(system: str, user: str, model: str, timeout: int, *,
                     directory: Path, token: str, server: dict | None = None,
                     text_receipt: Path | None = None
                     ) -> tuple[str, dict]:
    require_model_opt_in()
    if not model or model == "auto" or not token or timeout <= 0:
        raise ValueError("An exact model, subscription token and positive timeout are required")
    if server:
        verify_copilot_text_receipt(text_receipt, model)
    native = Path(os.environ.get("LOCALAPPDATA", "")) / "GitHubCopilotCLI" / "copilot.exe"
    executable = str(native) if native.is_file() else shutil.which("copilot")
    if not executable:
        raise RuntimeError("The native Copilot CLI is not installed")
    command = [executable]
    sdk = None
    packages = Path(os.environ.get("LOCALAPPDATA", "")) / "copilot" / "pkg" / "win32-x64"
    node = shutil.which("node")
    if node and packages.is_dir():
        versions = sorted(
            (p for p in packages.iterdir()
             if p.is_dir() and all(part.isdigit() for part in p.name.split("."))),
            key=lambda p: tuple(int(part) for part in p.name.split(".")), reverse=True)
        for package in versions:
            if (package / ".extraction-complete").is_file() and (package / "index.js").is_file():
                # Share installed program code, never homes or session data; avoid a copy per trial.
                command = [node, str(package / "index.js")]
                sdk = package / "copilot-sdk" / "index.js"
                break
    if sdk is None or not sdk.is_file():
        raise RuntimeError("The installed Copilot SDK and Node are required for guarded transport")
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    home, work, temp = (directory / name for name in ("home", "work", "temp"))
    for path in (home, work, temp, home / "roaming", home / "local"):
        path.mkdir()
    (home / "settings.json").write_text(json.dumps({
        "memory": False, "continueOnAutoMode": False, "includeCoAuthoredBy": False,
    }), encoding="utf-8")
    body, replacements = guarded_body({"system": system, "user": user})
    replacement_path = home / "url_replacements.json"
    replacement_path.write_text(json.dumps(replacements), encoding="utf-8")
    prompt = ("Follow the system instructions and user input in this JSON. "
              + ("Use only the supplied sandbox tool.\n" if server else
                 "Respond directly without tools.\n") + body.decode("utf-8"))
    env = {k: v for k, v in os.environ.items()
           if k.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "PATHEXT", "COMSPEC"}}
    env.update(HOME=str(home), USERPROFILE=str(home), APPDATA=str(home / "roaming"),
               LOCALAPPDATA=str(home / "local"), TEMP=str(temp), TMP=str(temp),
               COPILOT_HOME=str(home), COPILOT_GITHUB_TOKEN=token,
               COPILOT_CLI_PATH=str(command[1]),
               NODE_DISABLE_COMPILE_CACHE="1",
               COPILOT_ALLOW_ALL="false", GIT_CEILING_DIRECTORIES=str(directory))
    memory = subprocess.check_output(
        [*command, "--no-auto-update", "config", "memory"],
        cwd=work, env=env, text=True, timeout=20).strip()
    if memory != "false":
        raise RuntimeError(f"Native memory is not disabled; artifacts: {directory}")
    session = str(uuid.uuid4())
    events = directory / "events.jsonl"
    tool = "skillc_sandbox-execute_python" if server else ""
    receipt = {"requested_model": model, "session": session, "status": "started",
               "native_events": str(events), "url_placeholders": len(replacements),
               "client_command": [node, str(Path(__file__).with_name("copilot_guard.cjs")),
                                  "--sdk", str(sdk)],
               "usage_native": None, "memory_disabled": True,
               "node_compile_cache_disabled": True,
               "tools_denied": server is None, "advertised_tools": [tool] if tool else [],
               "transport": "copilot-sdk-request-handler"}
    receipt_path = directory / "receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    prompt_path = directory / "prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    args = [
        node, str(Path(__file__).with_name("copilot_guard.cjs")), "--sdk", str(sdk),
        "--model", model, "--session-id", session,
        "--usage-output-file", str(directory / "usage.json"),
        "--events-output-file", str(events),
        "--available-tools", tool,
        "--prompt-file", str(prompt_path),
    ]
    if server:
        config = {**server, "env": {**server.get("env", {}),
                  "SKILLC_REPLACEMENTS_FILE": str(replacement_path)}}
        args += [
            "--additional-mcp-config", json.dumps({"mcpServers": {"skillc_sandbox": config}}),
        ]
    started = time.perf_counter()
    with NativeEnvelopeGuard(replacement_path) as guard, (
            directory / "console.jsonl").open("w", encoding="utf-8") as console:
        env.update(guard.env)
        process = subprocess.Popen(
            args, cwd=work, env=env, stdout=console, stderr=subprocess.STDOUT,
            start_new_session=os.name != "nt")
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as error:
            if os.name == "nt":
                stop = (
                    "$ErrorActionPreference='Stop'; function Stop-OwnedTree([int]$Target) { "
                    "Get-CimInstance Win32_Process -Filter \"ParentProcessId = $Target\" | "
                    "ForEach-Object { Stop-OwnedTree $_.ProcessId }; "
                    "if (Get-Process -Id $Target -ErrorAction SilentlyContinue) "
                    "{ Stop-Process -Id $Target } }; "
                    f"Stop-OwnedTree {process.pid}")
                subprocess.run(
                    ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", stop],
                    check=True, timeout=30, env=env)
            else:
                os.killpg(process.pid, 9)
            process.wait(timeout=30)
            receipt.update(status="timeout", seconds=time.perf_counter() - started,
                           usage_native_complete=False)
            rows, truncated = (read_session_events(events, interrupted=True)
                               if events.is_file() else ([], False))
            receipt.update(_copilot_native_metadata(rows), native_events_truncated=truncated)
            if receipt["served_models"] and receipt["served_models"] != [model]:
                receipt["status"] = "unexpected_serving_model"
                raise RuntimeError(
                    f"Native serving model differs; interrupted artifacts: {directory}") from error
            if (len(receipt["usage_native"]) > guard.model_requests or any(
                    u.get("isByok") is not False
                    or u.get("availableToolCount") != int(server is not None)
                    or not isinstance(u.get("numToolCalls"), int) or u["numToolCalls"] < 0
                    or (server is None and u["numToolCalls"] != 0)
                    for u in receipt["usage_native"])):
                receipt["status"] = "unexpected_partial_native_metadata"
                raise RuntimeError(
                    f"Interrupted native usage or tools are unverified: {directory}") from error
            receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
            raise CopilotSessionTimeout(
                f"Native model deadline exceeded; artifacts: {directory}", receipt) from error
        finally:
            receipt["envelope_guard"] = {
                "model_requests": guard.model_requests,
                "implementation_sha256": implementation_hash(),
            }
            (directory / "envelope_audit.json").write_text(
                json.dumps(guard.audit, indent=2), encoding="utf-8")
            receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    receipt.update(exit_code=process.returncode, seconds=time.perf_counter() - started)
    if process.returncode:
        receipt["status"] = "cli_error"
        receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        raise RuntimeError(f"Native model process failed; artifacts: {directory}")
    if not events.is_file():
        receipt["status"] = "missing_event_transcript"
        receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        raise RuntimeError(f"Native session has no event transcript; artifacts: {directory}")
    rows, _ = read_session_events(events)
    receipt.update(_copilot_native_metadata(rows))
    usage = receipt["usage_native"]
    if not usage or guard.model_requests != len(usage):
        receipt["status"] = "unguarded_native_transport"
        receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        raise RuntimeError(
            f"Native request transport bypassed the envelope guard; artifacts: {directory}")
    if receipt["served_models"] != [model]:
        receipt["status"] = "unexpected_serving_model"
        receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        raise RuntimeError(f"Native serving model differs or is unreported; artifacts: {directory}")
    if any(u.get("availableToolCount") != int(server is not None) for u in usage):
        receipt["status"] = "native_tools_exposed_or_unreported"
        receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        raise RuntimeError(f"Native text completion exposed unexpected tools or omitted metadata; "
                           f"artifacts: {directory}")
    if any(not isinstance(u.get("numToolCalls"), int) or u["numToolCalls"] < 0
           or (server is None and u["numToolCalls"] != 0) for u in usage):
        receipt["status"] = "tool_calls_or_unreported_tool_usage"
        receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        raise RuntimeError(f"Native text completion used tools or omitted tool usage; "
                           f"artifacts: {directory}")
    replies = [row["data"]["content"] for row in rows
               if row.get("type") == "assistant.message"
               and isinstance(row.get("data", {}).get("content"), str)]
    empty_tool_completion = server is not None and usage[-1].get("finishReason") == "stop"
    if not replies or (not replies[-1] and not empty_tool_completion):
        receipt["status"] = "missing_text_reply"
        receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        raise RuntimeError(f"Native session has no text reply; artifacts: {directory}")
    receipt["status"] = "completed"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return restore(replies[-1], json.loads(replacement_path.read_text(encoding="utf-8"))), receipt


def anthropic_complete(system: str, user: str, model: str,
                       timeout: int, image: tuple[bytes, str] | None = None) -> str:
    require_model_opt_in()
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set; the LLM front-end is "
                           "opt-in")
    content: str | list = user
    if image is not None:
        data, mime = _b64(image)
        content = [{"type": "image", "source": {"type": "base64", "media_type": mime,
                                                "data": data}},
                   {"type": "text", "text": user}]
    body, table = guarded_body({
        "model": model,
        "max_tokens": 16000,
        "system": system,
        "messages": [{"role": "user", "content": content}],
    })
    req = urllib.request.Request(
        ANTHROPIC_API_URL, data=body,
        headers={"content-type": "application/json", "x-api-key": key,
                 "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.load(r)
    _record_usage(out.get("usage"))
    return restore("".join(b.get("text", "") for b in out.get("content", [])
                           if b.get("type") == "text").strip(), table)


def azure_openai_complete(system: str, user: str, model: str | None,
                          timeout: int, json_mode: bool = True,
                          image: tuple[bytes, str] | None = None) -> str:
    content: str | list = user
    if image is not None:
        data, mime = _b64(image)
        content = [{"type": "text", "text": user},
                   {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}}]
    payload = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ],
        "max_completion_tokens": 32000,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    out = azure_openai_chat(payload, model, timeout)
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


def azure_openai_chat(payload: dict, model: str | None, timeout: int) -> dict:
    """Guarded, non-streaming chat including native agent tool calls."""
    require_model_opt_in()
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

    payload = {**payload}
    if payload.get("stream"):
        raise ValueError("azure_openai_chat requires a non-streaming request")
    if include_model:
        payload["model"] = deployment
    else:
        payload.pop("model", None)
    headers = {"content-type": "application/json"}
    if key:
        headers["api-key"] = key
    else:
        headers["authorization"] = "Bearer " + azure_cli_token()
    body, table = guarded_body(payload)
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out = json.load(r)
    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"Azure OpenAI request failed: {_azure_error(error)}") from error
    _record_usage(_azure_usage(out.get("usage")))

    def restored(value):
        if isinstance(value, str):
            return restore(value, table)
        if isinstance(value, list):
            return [restored(v) for v in value]
        if isinstance(value, dict):
            return {restore(k, table): restored(v) for k, v in value.items()}
        return value

    return restored(out)


DECISION_ENDPOINT = "https://foundary-tzuc06.services.ai.azure.com"
DECISION_PATH = "/providers/microsoft/v1/systemone"


class DecisionError(RuntimeError):
    """A Decision-model request that the service refused (`status` is the HTTP code)."""

    def __init__(self, status: int, message: str):
        super().__init__(f"Decision request failed: HTTP {status}: {message}")
        self.status = status
        self.message = message


def decision(state, questions: dict, model: str = "Decision-1",
             endpoint: str | None = None, timeout: int = 60) -> dict:
    """One request to a Foundry decision model (e.g. `Microsoft-Decision-1`).

    `state` is text or a JSON object; `questions` maps a question id to
    ``{"type": "noul" | "choice" | "score", "instructions": ..., "criteria": ...}``.
    The model answers with numbers only (a probability per yes/no question, a
    choice with per-option probabilities, or a score); it writes no text.
    Returns the parsed reply (``answers`` and ``usage``). Authentication is the
    ``api-key`` header when AZURE_DECISION_API_KEY is set, else an Azure CLI token.
    """
    require_model_opt_in()
    base = (endpoint or os.environ.get("AZURE_DECISION_ENDPOINT")
            or DECISION_ENDPOINT).rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError("the decision endpoint must be an https URL")
    url = base if base.endswith(DECISION_PATH) else base + DECISION_PATH
    headers = {"content-type": "application/json"}
    key = os.environ.get("AZURE_DECISION_API_KEY")
    if key:
        headers["api-key"] = key
    else:
        headers["authorization"] = "Bearer " + azure_cli_token()
    body = {"model": model, "state": state, "questions": questions}
    data, _ = guarded_body(body)
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out = json.load(r)
    except urllib.error.HTTPError as error:
        try:
            text = error.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            text = str(error.reason)
        raise DecisionError(error.code, text[:2000]) from error
    usage = out.get("usage") or {}
    _record_usage({"input_tokens": int(usage.get("input_tokens", 0)),
                   "output_tokens": int(usage.get("output_tokens", 0)),
                   "cache_read_input_tokens": 0} if usage else None)
    return out


def _azure_error(error) -> str:
    """Summarize an Azure HTTP error from its JSON body, without headers."""
    try:
        detail = json.loads(error.read().decode("utf-8", errors="replace"))["error"]
        return f"HTTP {error.code} {detail.get('code', '')}: {detail.get('message', '')}".strip()
    except (AttributeError, KeyError, TypeError, ValueError):
        return f"HTTP {error.code} {error.reason}"


def azure_cli_token() -> str:
    """Get a short-lived Foundry token from the current Azure CLI login.

    AZURE_SUBSCRIPTION_ID (or AZURE_TENANT_ID) selects the account that owns
    the resource, so the global Azure CLI default need not match it.
    """
    executable = shutil.which("az.cmd") or shutil.which("az")
    if not executable:
        raise RuntimeError(
            "AZURE_OPENAI_API_KEY is not set and Azure CLI is unavailable")
    command = [
        executable, "account", "get-access-token",
        "--resource", "https://ai.azure.com",
        "--query", "accessToken", "--output", "tsv",
    ]
    if os.environ.get("AZURE_SUBSCRIPTION_ID"):
        command += ["--subscription", os.environ["AZURE_SUBSCRIPTION_ID"]]
    elif os.environ.get("AZURE_TENANT_ID"):
        command += ["--tenant", os.environ["AZURE_TENANT_ID"]]
    try:
        proc = subprocess.run(
            command,
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

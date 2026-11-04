"""Guarded Claude Code CLI calls for the benchmark scripts.

The evaluation scripts (`scripts/usefulness.py`, `llm_judge_baseline.py`,
`live_agents.py`) shell out to the Claude Code CLI. They predate the rule in
CLAUDE.md that no URL, bare domain or e-mail address may reach a model, so they
sent raw SKILL.md text and copied it into the agent's working directory. This
module is what they now go through:

* `scrub_prompt` replaces every URL, domain and e-mail in a prompt with a
  placeholder (`skillc.frontend.urlguard.scrub`) and refuses
  (`UrlInPromptError`) if anything URL-like survives.
* `scrub_tree` does the same to every file placed in an agent's working
  directory, sharing the prompt's placeholder table so a host has one name
  everywhere; a binary file that carries URL-like bytes is refused.
* `work_dir` makes the agent's directory under `SKILLC_BENCH_WORK`.
* `agent_env` is an allow-listed environment: no token, key or cloud
  credential of the caller reaches the CLI or the commands its agent runs.
* `cli_cmd` builds the CLI command: no MCP server, no user or project
  settings, no slash commands or skills, and a sandbox for the agent's shell
  (credential files unreadable, reads outside the working directory blocked,
  network denied).

Every real call still needs SKILLC_ALLOW_MODEL_CALLS=1 (`require_opt_in`).
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .frontend.urlguard import UrlInPromptError, assert_clean, find_urls, scrub

ENV_ALLOW = ("PATH", "HOME", "LANG", "LC_ALL", "TERM", "TZ",
             "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "NO_PROXY", "no_proxy",
             "NODE_EXTRA_CA_CERTS", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE")


def require_opt_in() -> None:
    from .frontend.providers import require_model_opt_in
    require_model_opt_in()


def scrub_prompt(text: str, table: dict[str, str] | None = None) -> tuple[str, dict[str, str]]:
    """The prompt as the model may see it, and the placeholder table."""
    clean, table = scrub(text, table)
    assert_clean(clean)
    return clean, table


def scrub_tree(root: str | os.PathLike, table: dict[str, str] | None = None) -> dict[str, str]:
    """Scrub every file under `root` in place. Returns the shared table.

    A text file is rewritten with placeholders; a binary file is left alone if
    it carries nothing URL-like and refused otherwise."""
    table = {} if table is None else table
    for p in sorted(Path(root).rglob("*")):
        if not p.is_file() or p.is_symlink():
            continue
        raw = p.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            left = find_urls(raw.decode("latin-1"))
            if left:
                raise UrlInPromptError(f"binary file {p.name} placed for an agent carries "
                                       f"URL-like bytes, e.g. {left[0][:40]!r}")
            continue
        clean, table = scrub(text, table)
        assert_clean(clean)
        if clean != text:
            p.write_text(clean, encoding="utf-8")
    return table


def bench_root() -> Path:
    root = Path(os.environ.get("SKILLC_BENCH_WORK") or Path(tempfile.gettempdir()) / "skillc_bench_work")
    root.mkdir(parents=True, exist_ok=True)
    return root


def work_dir(prefix: str) -> str:
    return tempfile.mkdtemp(prefix=prefix, dir=bench_root())


def agent_env() -> dict[str, str]:
    env = {k: os.environ[k] for k in ENV_ALLOW if k in os.environ}
    env["CLAUDE_CODE_SUBPROCESS_ENV_SCRUB"] = "1"
    return env


def sandbox_settings() -> str:
    home = os.path.expanduser("~")
    deny = sorted({home, "/home", "/root"})
    return json.dumps({
        "permissions": {"blockReadsOutsideWorkingDirectories": True},
        "sandbox": {"enabled": True,
                    "credentials": {"files": [{"path": os.path.join(home, d), "mode": "deny"}
                                              for d in (".claude", ".config", ".aws", ".ssh", ".azure")]},
                    "filesystem": {"denyRead": deny}},
    })


def cli_cmd(model: str, prompt: str, *, tools: str = "", allowed: str | None = None,
            system: str | None = None, max_turns: int | None = None,
            budget: float | None = None) -> list[str]:
    """The CLI command for one print-mode call. `prompt` and `system` must
    already be scrubbed; they are checked again here."""
    assert_clean(prompt)
    cmd = ["claude", "-p", "--strict-mcp-config", "--setting-sources", "", "--disable-slash-commands",
           "--settings", sandbox_settings(), "--tools", tools, "--no-session-persistence"]
    if allowed:
        cmd += ["--allowedTools", allowed]
    if system is not None:
        assert_clean(system)
        cmd += ["--system-prompt", system]
    if max_turns is not None:
        cmd += ["--max-turns", str(max_turns)]
    if budget is not None:
        cmd += ["--max-budget-usd", str(budget)]
    return cmd + ["--model", model, "--output-format", "json", prompt]

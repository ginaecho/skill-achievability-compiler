"""Cached, refreshable view of capabilities observed by ``skillc.env``."""
from __future__ import annotations

import sys
import threading
from collections.abc import Callable
from pathlib import Path


class EnvironmentInventory:
    """Keep one environment snapshot fresh behind a small app-facing interface."""

    def __init__(
        self,
        repo_root: Path,
        state_dir: Path,
        refresh_seconds: float,
        probe: Callable[[str], object] | None = None,
    ):
        self.repo_root = repo_root.resolve()
        self.state_dir = state_dir.resolve()
        self.refresh_seconds = max(0.0, refresh_seconds)
        self._probe = probe or (
            lambda source: probe_local_environment(self.repo_root, source)
        )
        self._lock = threading.Lock()
        self._refreshing = False
        self._last_error = ""
        self._last_reason = ""
        self._last_changes = None
        self._last_source = ""
        self._environment = self._load_cached()

    def start(self) -> None:
        if self._environment is None:
            self.request_refresh("", "startup")
        if self.refresh_seconds:
            threading.Thread(target=self._schedule, daemon=True).start()

    def snapshot(self) -> dict:
        with self._lock:
            environment = self._environment
            payload = {
                "captured_at": environment.captured_at if environment else None,
                "refreshing": self._refreshing,
                "refresh_seconds": self.refresh_seconds,
                "last_error": self._last_error,
                "last_reason": self._last_reason,
                "changes": self._last_changes,
                "sources": list(environment.sources) if environment else [],
                "unknown": list(environment.unknown) if environment else [],
            }
        payload.update(_capability_summary(environment))
        return payload

    def request_refresh(self, source: str, reason: str = "manual") -> bool:
        with self._lock:
            if self._refreshing:
                return False
            self._refreshing = True
            self._last_source = source
        threading.Thread(
            target=self._refresh,
            args=(source, reason),
            daemon=True,
        ).start()
        return True

    def _load_cached(self):
        _add_source_path(self.repo_root)
        from skillc.env.model import Environment
        from skillc.env.watch import LATEST

        path = self.state_dir / LATEST
        if not path.is_file():
            return None
        try:
            return Environment.load(path)
        except (OSError, ValueError) as error:
            self._last_error = f"could not load cached environment: {error}"
            return None

    def _refresh(self, source: str, reason: str) -> None:
        try:
            _add_source_path(self.repo_root)
            from skillc.env.model import Environment
            from skillc.env.watch import LATEST, watch_once

            report = watch_once(
                self.state_dir,
                lambda: self._probe(source),
                {},
            )
            environment = Environment.load(self.state_dir / LATEST)
            with self._lock:
                self._environment = environment
                self._last_changes = report["environment_changes"]
                self._last_error = ""
                self._last_reason = reason
        except (OSError, RuntimeError, TimeoutError, ValueError) as error:
            with self._lock:
                self._last_error = f"{type(error).__name__}: {error}"
                self._last_reason = reason
        finally:
            with self._lock:
                self._refreshing = False

    def _schedule(self) -> None:
        while True:
            threading.Event().wait(self.refresh_seconds)
            with self._lock:
                source = self._last_source
            self.request_refresh(source, "scheduled")


def probe_local_environment(repo_root: Path, source: str):
    """Use the existing needs-driven runtime adapter without fabricating grants."""
    _add_source_path(repo_root)
    from skillc.env import claude
    from skillc.env.nl import intent_from_text
    from skillc.env.reach import intent_needs

    needs = intent_needs(intent_from_text(source)) if source.strip() else {}
    return claude.probe(
        root=repo_root,
        hosts=needs.get("egress", ()),
        programs=needs.get("program", ()),
        modules=needs.get("pymodule", ()),
        paths=needs.get("path", ()),
        credentials=[*claude.CREDENTIALS, *needs.get("credential", ())],
    )


def _capability_summary(environment) -> dict:
    if environment is None:
        return {"grants": [], "capabilities": [], "services": []}

    from skillc.env.facts import need
    from skillc.profiles import normalize_tool

    capabilities = []
    grants = set()
    for tool in sorted(environment.of_kind("tool"), key=lambda node: node["name"]):
        fact = need(environment, {"tool": tool["name"]})
        status = "granted" if fact.value is True else (
            "approval" if fact.value is None else "denied"
        )
        capabilities.append({
            "name": tool["name"],
            "kind": "tool",
            "status": status,
            "reasons": list(fact.reasons),
        })
        if fact.possible:
            grants.add(normalize_tool(tool["name"]))

    services = []
    for node in sorted(environment.of_kind("service"), key=lambda item: item["name"]):
        service_type = node["attrs"].get("type")
        if service_type not in {"program", "python module", "daemon", "platform"}:
            continue
        available = node["attrs"].get("available")
        services.append({
            "name": node["name"],
            "kind": service_type,
            "status": "available" if available else "unavailable",
        })
        if available:
            grants.add(normalize_tool(node["name"]))

    return {
        "grants": sorted(grants),
        "capabilities": capabilities,
        "services": services,
    }


def _add_source_path(repo_root: Path) -> None:
    source = str(repo_root / "src")
    if source not in sys.path:
        sys.path.insert(0, source)

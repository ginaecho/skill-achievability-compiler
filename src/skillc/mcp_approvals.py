"""User approval of protected operations for the monitor served as MCP tools.

The agent may request approval, but only the host's user-facing channel can grant it.
Approval binds one exact operation, destination set, content, source and amount; the
reference is consumed when `skillc_check_action` authorizes that operation.
"""
from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from .security import ApprovalGate, AuthorizationError, Delivery, digest, money_minor

TENANT = "local-user"
AGENT = "agent"
USER = "user"
MAX_CONTENT = 8000


@dataclass(frozen=True)
class ApprovalPolicy:
    """User-authored: which runtime tools need approval, and where they may deliver."""

    protected_tools: frozenset[str]
    destinations: frozenset[str]
    ttl_seconds: int = 900
    audit_above_minor: int = 5_000_000

    @staticmethod
    def load(path: Path) -> ApprovalPolicy:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("approval policy must be a JSON object")
        tools, places = data.get("protected_tools"), data.get("destinations")
        for name, value in (("protected_tools", tools), ("destinations", places)):
            if (not isinstance(value, list) or not value
                    or any(not isinstance(v, str) or not v.strip() for v in value)):
                raise ValueError(f"approval policy {name} must be a nonempty list of IDs")
        ttl = data.get("ttl_seconds", 900)
        if type(ttl) is not int or not 0 < ttl <= 86400:
            raise ValueError("approval policy ttl_seconds must be 1..86400")
        return ApprovalPolicy(frozenset(tools), frozenset(places), ttl,
                              money_minor(data.get("audit_above", "50000.00")))


@dataclass(frozen=True)
class PendingApproval:
    session: str
    delivery: Delivery
    summary: str


def parse_destinations(text: str) -> tuple[str, ...]:
    return tuple(d.strip() for d in str(text or "").replace("\n", ",").split(",") if d.strip())


class Approvals:
    """Approval state of one MCP monitor root, scoped per session."""

    def __init__(self, root: Path, policy: ApprovalPolicy,
                 clock: Callable[[], float] = time.time):
        self.path = Path(root) / ".skillc" / "approvals.sqlite3"
        self.policy = policy
        self.clock = clock
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS skillc_approval_requests (
                token_hash TEXT PRIMARY KEY, session TEXT NOT NULL, source TEXT NOT NULL,
                version TEXT NOT NULL, source_digest TEXT NOT NULL,
                amount_minor INTEGER NOT NULL)""")

    def protects(self, operation: str) -> bool:
        return operation in self.policy.protected_tools

    def _gate(self, session: str) -> ApprovalGate:
        p = self.policy
        return ApprovalGate(self.path, tenant=TENANT, workflow=session,
                            approvers=frozenset({USER}), senders=frozenset({AGENT}),
                            destinations=p.destinations, operations=p.protected_tools,
                            ttl_seconds=p.ttl_seconds, audit_above_minor=p.audit_above_minor,
                            clock=self.clock)

    def prepare(self, session: str, operation: str, destinations: str, content: str,
                source: str = "", source_version: str = "", source_text: str = "",
                amount: str = "") -> PendingApproval:
        """Validate a request against policy and describe it for the user; grants nothing."""
        if not self.protects(operation):
            raise AuthorizationError(f"`{operation}` is not a protected operation")
        if len(content or "") > MAX_CONTENT:
            raise AuthorizationError(f"content exceeds {MAX_CONTENT} characters and cannot "
                                     "be shown to the user for exact approval")
        delivery = Delivery(
            tenant=TENANT, workflow=session, source=source or "conversation",
            version=source_version or "unversioned", source_digest=digest(source_text or ""),
            author=AGENT, operation=operation, destinations=parse_destinations(destinations),
            content=content or "", amount_minor=money_minor(amount or 0))
        self._gate(session).validate(delivery)
        lines = [f"Operation: {operation}", "Destinations: " + ", ".join(delivery.destinations),
                 f"Source: {delivery.source} (version {delivery.version})"]
        if amount:
            lines.append(f"Amount: {delivery.amount_minor / 100:.2f}")
        lines += ["Content:", delivery.content]
        return PendingApproval(session, delivery, "\n".join(lines))

    def grant(self, pending: PendingApproval, audited: bool = False) -> str:
        """Called only after the user approved `pending.summary` out of band."""
        token = self._gate(pending.session).approve(pending.delivery, approver=USER,
                                                    audited=audited)
        d = pending.delivery
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute("INSERT INTO skillc_approval_requests VALUES (?, ?, ?, ?, ?, ?)",
                       (digest(token), pending.session, d.source, d.version,
                        d.source_digest, d.amount_minor))
        return token

    def consume(self, session: str, token: str, operation: str, destinations: str,
                content: str, source_version: str = "", source_text: str = "") -> None:
        """Authorize one exact protected operation; raises AuthorizationError otherwise.

        A new `source_version` or `source_text` replaces the approved one, so a changed
        source is refused rather than silently approved."""
        if not isinstance(token, str) or not token:
            raise AuthorizationError("no approval reference; call skillc_request_approval")
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            row = db.execute(
                "SELECT source, version, source_digest, amount_minor FROM "
                "skillc_approval_requests WHERE token_hash=? AND session=?",
                (digest(token), session)).fetchone()
        if row is None:
            raise AuthorizationError("approval reference is not issued for this session")
        source, version, source_digest, amount_minor = row
        delivery = Delivery(
            tenant=TENANT, workflow=session, source=source,
            version=source_version or version,
            source_digest=digest(source_text) if source_text else source_digest,
            author=AGENT, operation=operation, destinations=parse_destinations(destinations),
            content=content or "", amount_minor=amount_minor)
        self._gate(session).deliver(token, delivery, sender=AGENT, send=lambda _: None)

    def revoke(self, session: str, token: str) -> None:
        self._gate(session).revoke(token)

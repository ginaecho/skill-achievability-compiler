"""Evidence-bound runtime authorization, separate from the static checker.

Only trusted host code may issue approvals or supply identity, source versions, or
verified message evidence. None of these interfaces authenticates a model's claims.
Keep the database and these issuance methods inaccessible to agent tools.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import time
from collections.abc import Callable
from contextlib import closing
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")


class AuthorizationError(ValueError):
    """An explicit refusal; adapters must not call the protected tool after this error."""


def money_minor(value: str | int | float | Decimal) -> int:
    """Finite, nonnegative money in integer cents; reject rounding and coercion of bool."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise AuthorizationError("money must be a finite nonnegative amount")
    try:
        amount = Decimal(str(value))
    except InvalidOperation as e:
        raise AuthorizationError("money must be a finite nonnegative amount") from e
    if not amount.is_finite() or amount < 0 or amount > Decimal("999999999999.99"):
        raise AuthorizationError("money must be finite and between 0 and 999999999999.99")
    if amount == 0:
        return 0
    _, digits, exponent = amount.as_tuple()
    trailing = len(digits) - len("".join(str(d) for d in digits).rstrip("0"))
    if exponent + trailing < -2:
        raise AuthorizationError("money must have at most two decimal places")
    with localcontext() as context:
        context.prec = 28
        cents = amount * 100
    if cents != cents.to_integral_value():
        raise AuthorizationError("money must have at most two decimal places")
    return int(cents)


def digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Delivery:
    """The exact operation approved, constructed from trusted source and host context.

    Destination IDs are opaque and matched exactly (mailbox IDs or Teams channel IDs);
    include every recipient, including Cc/Bcc. The transport may not add recipients,
    attachments, or change the content after authorization.
    """

    tenant: str
    workflow: str
    source: str
    version: str
    source_digest: str
    author: str
    operation: str
    destinations: tuple[str, ...]
    content: str
    amount_minor: int

    def fingerprint(self) -> str:
        if not all(isinstance(v, str) and v.strip() for v in (
                self.tenant, self.workflow, self.source, self.version, self.author,
                self.operation, self.content)):
            raise AuthorizationError("delivery context and content must be nonempty strings")
        if (not isinstance(self.source_digest, str) or len(self.source_digest) != 64
                or any(c not in "0123456789abcdef" for c in self.source_digest)):
            raise AuthorizationError("source_digest must be a SHA-256 hex digest")
        if (type(self.amount_minor) is not int or self.amount_minor < 0
                or self.amount_minor > 99_999_999_999_999):
            raise AuthorizationError("amount_minor must be nonnegative integer cents")
        if (not isinstance(self.destinations, tuple) or not self.destinations
                or any(not isinstance(d, str) or not d.strip() for d in self.destinations)
                or len(set(self.destinations)) != len(self.destinations)):
            raise AuthorizationError("destinations must be a nonempty tuple of distinct IDs")
        data = asdict(self)
        data["content"] = digest(self.content)
        data["destinations"] = sorted(self.destinations)
        return digest(json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False))


class ApprovalGate:
    """Persisted, expiring, single-use approvals for one tenant/workflow.

    The host supplies authenticated principals and a policy from outside the intent.
    A gate object does not grant Microsoft 365 permissions. Its send callback must
    still use the runtime's authenticated client and handle downstream authorization.
    """

    def __init__(self, path: Path, *, tenant: str, workflow: str,
                 approvers: frozenset[str], senders: frozenset[str],
                 destinations: frozenset[str], operations: frozenset[str],
                 ttl_seconds: int = 900, audit_above_minor: int = 5_000_000,
                 clock: Callable[[], float] = time.time):
        if not all(isinstance(v, str) and v.strip() for v in (tenant, workflow)):
            raise AuthorizationError("tenant and workflow must be host-supplied nonempty IDs")
        if any(not isinstance(s, frozenset) or not s
               or any(not isinstance(v, str) or not v.strip() for v in s)
               for s in (approvers, senders, destinations, operations)):
            raise AuthorizationError("policy allowlists must be nonempty frozensets of IDs")
        if (type(ttl_seconds) is not int or not 0 < ttl_seconds <= 86400
                or type(audit_above_minor) is not int or audit_above_minor < 0):
            raise AuthorizationError("invalid approval lifetime or audit threshold")
        self.path = Path(path)
        self.tenant, self.workflow = tenant, workflow
        self.approvers, self.senders = approvers, senders
        self.destinations, self.operations = destinations, operations
        self.ttl_seconds, self.audit_above_minor = ttl_seconds, audit_above_minor
        self.clock = clock
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS skillc_approvals (
                token_hash TEXT PRIMARY KEY, tenant TEXT NOT NULL, workflow TEXT NOT NULL,
                fingerprint TEXT NOT NULL, approver TEXT NOT NULL, audited INTEGER NOT NULL,
                expires REAL NOT NULL, consumed INTEGER NOT NULL DEFAULT 0)""")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    def validate(self, delivery: Delivery) -> str:
        """The delivery's fingerprint if current policy could approve it; raises otherwise."""
        return self._check(delivery)

    def _check(self, delivery: Delivery) -> str:
        fingerprint = delivery.fingerprint()
        if (delivery.tenant, delivery.workflow) != (self.tenant, self.workflow):
            raise AuthorizationError("delivery belongs to another tenant or workflow")
        if delivery.operation not in self.operations:
            raise AuthorizationError("delivery operation is not granted")
        if not set(delivery.destinations) <= self.destinations:
            raise AuthorizationError("delivery contains an unauthorized destination")
        return fingerprint

    def approve(self, delivery: Delivery, *, approver: str, audited: bool = False) -> str:
        """Called only by a trusted approval handler after independent review.

        `audited` must come from the authenticated audit workflow, never report text.
        The issued opaque reference is safe to relay but grants only this exact delivery.
        """
        fingerprint = self._check(delivery)
        if approver not in self.approvers or approver == delivery.author:
            raise AuthorizationError("approval requires an authorized independent reviewer")
        if type(audited) is not bool:
            raise AuthorizationError("audit evidence must be a trusted Boolean")
        if delivery.amount_minor > self.audit_above_minor and not audited:
            raise AuthorizationError("the source amount requires independent audit evidence")
        token = secrets.token_urlsafe(32)
        with closing(self._connect()) as db, db:
            db.execute("INSERT INTO skillc_approvals VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
                       (digest(token), self.tenant, self.workflow, fingerprint, approver,
                        int(audited), self.clock() + self.ttl_seconds))
        return token

    def deliver(self, token: str, delivery: Delivery, *, sender: str,
                send: Callable[[Delivery], T]) -> T:
        """Validate and consume approval durably before invoking the protected transport.

        Concurrent attempts cannot reuse a reference. A transport exception propagates
        and leaves it consumed: ambiguous delivery requires reconciliation and new approval,
        not automatic retry. This guarantees at-most-once invocation, not successful delivery.
        """
        fingerprint = self._check(delivery)
        if sender not in self.senders:
            raise AuthorizationError("the authenticated sender is not authorized")
        if not isinstance(token, str) or not token or len(token) > 256:
            raise AuthorizationError("missing or malformed approval reference")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT fingerprint, approver, audited, expires, consumed "
                "FROM skillc_approvals WHERE token_hash=? AND tenant=? AND workflow=?",
                (digest(token), self.tenant, self.workflow)).fetchone()
            if row is None:
                raise AuthorizationError("approval reference is not issued for this workflow")
            expected, approver, audited, expires, consumed = row
            if consumed or expires <= self.clock():
                raise AuthorizationError("approval is expired, revoked, or already consumed")
            if expected != fingerprint:
                raise AuthorizationError(
                    "document, version, report, amount or destinations changed")
            if approver not in self.approvers or approver in (delivery.author, sender):
                raise AuthorizationError("approval is no longer independent or authorized")
            if delivery.amount_minor > self.audit_above_minor and not audited:
                raise AuthorizationError("current policy requires audit evidence")
            db.execute("UPDATE skillc_approvals SET consumed=1 WHERE token_hash=?",
                       (digest(token),))
        return send(delivery)

    def revoke(self, token: str) -> None:
        """Called by the trusted host when the source changes or consent is withdrawn."""
        if not isinstance(token, str) or not token:
            raise AuthorizationError("missing approval reference")
        with closing(self._connect()) as db, db:
            result = db.execute(
                "UPDATE skillc_approvals SET consumed=1 "
                "WHERE token_hash=? AND tenant=? AND workflow=?",
                (digest(token), self.tenant, self.workflow))
            if result.rowcount != 1:
                raise AuthorizationError("approval reference is not issued for this workflow")


@dataclass(frozen=True)
class MessageEvidence:
    """A trusted adapter's attestation, NOT a model-supplied JSON message.

    The adapter must verify origin, success, freshness and workflow membership before
    constructing this object. Digest the exact message, not only its label.
    """

    issuer: str
    receiver: str
    tenant: str
    workflow: str
    label: str
    content_digest: str

    def matches(self, *, text: str, issuer: str, receiver: str,
                tenant: str, workflow: str, label: str) -> bool:
        return (self.issuer, self.receiver, self.tenant, self.workflow,
                self.label, self.content_digest) == (
                    issuer, receiver, tenant, workflow, label, digest(text))

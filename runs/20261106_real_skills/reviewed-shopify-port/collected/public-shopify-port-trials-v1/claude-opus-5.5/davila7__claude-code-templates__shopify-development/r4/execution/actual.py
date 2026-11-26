"""Shopify webhook HMAC verification (port of verifyWebhook from app-development.md)."""

import base64
import hashlib
import hmac


def verify_webhook(raw_body: bytes, hmac_header: str | None, secret: str) -> bool:
    """Return True iff hmac_header equals base64(HMAC-SHA256(secret_utf8, raw_body)).

    raw_body must be the exact, unparsed request body bytes.
    Returns False (never raises) for a missing, empty, non-ASCII or mismatched header.
    """
    if not isinstance(hmac_header, str) or not hmac_header:
        return False
    if not hmac_header.isascii():
        return False
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    expected = base64.b64encode(digest)
    return hmac.compare_digest(expected, hmac_header.encode("ascii"))

"""Shopify webhook HMAC verification (Python port of verifyWebhook)."""

import base64
import hashlib
import hmac


def verify_webhook(raw_body: bytes, hmac_header: str | None, secret: str) -> bool:
    """Return True only if hmac_header is the Base64 HMAC-SHA256 of raw_body.

    raw_body must be the exact, unparsed request body bytes. The secret is
    encoded as UTF-8 and used as the HMAC key. The header is compared exactly
    (no trimming or normalisation) using hmac.compare_digest. Returns False,
    without raising, for a missing, empty, non-ASCII or mismatched header.
    """
    if not isinstance(hmac_header, str) or not hmac_header:
        return False
    if not isinstance(raw_body, (bytes, bytearray, memoryview)):
        return False
    if not isinstance(secret, str):
        return False
    try:
        header_bytes = hmac_header.encode("ascii")
        key = secret.encode("utf-8")
    except UnicodeEncodeError:
        return False
    digest = hmac.new(key, bytes(raw_body), hashlib.sha256).digest()
    expected = base64.b64encode(digest)
    return hmac.compare_digest(expected, header_bytes)

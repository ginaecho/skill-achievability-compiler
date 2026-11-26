import base64
import hashlib
import hmac


def verify_webhook(raw_body: bytes, hmac_header: str | None, secret: str) -> bool:
    """Verify a Shopify webhook HMAC-SHA256 signature.

    Returns True only when ``hmac_header`` equals the Base64 encoding of
    HMAC-SHA256 over the exact ``raw_body`` bytes, keyed with ``secret``
    encoded as UTF-8. Returns False otherwise, never raising for a missing,
    empty, non-ASCII or mismatched header.
    """
    if not isinstance(hmac_header, str) or not hmac_header:
        return False
    if not hmac_header.isascii():
        return False
    if not isinstance(raw_body, (bytes, bytearray, memoryview)):
        return False
    if not isinstance(secret, str):
        return False
    digest = hmac.new(secret.encode("utf-8"), bytes(raw_body), hashlib.sha256).digest()
    expected = base64.b64encode(digest)
    return hmac.compare_digest(expected, hmac_header.encode("ascii"))

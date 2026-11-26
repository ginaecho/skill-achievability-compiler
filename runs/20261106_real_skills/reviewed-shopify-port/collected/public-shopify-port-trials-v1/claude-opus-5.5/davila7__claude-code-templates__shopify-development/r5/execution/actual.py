# Shopify webhook HMAC verification (port of verifyWebhook from app-development.md).
import base64
import hashlib
import hmac


def verify_webhook(raw_body: bytes, hmac_header: str | None, secret: str) -> bool:
    """Return True iff hmac_header is the Base64 HMAC-SHA256 of raw_body keyed with secret (UTF-8)."""
    if not hmac_header or not isinstance(hmac_header, str):
        return False
    try:
        provided = hmac_header.encode("ascii")
    except UnicodeEncodeError:
        return False
    digest = hmac.new(secret.encode("utf-8"), bytes(raw_body), hashlib.sha256).digest()
    expected = base64.b64encode(digest)
    return hmac.compare_digest(provided, expected)

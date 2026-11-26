import base64
import hashlib
import hmac


def verify_webhook(raw_body: bytes, hmac_header: str | None, secret: str) -> bool:
    """Return True iff hmac_header is the Base64 HMAC-SHA256 of raw_body keyed with secret (UTF-8).

    The body is used exactly as received; it is never parsed, decoded or re-serialized.
    """
    if not isinstance(hmac_header, str) or not hmac_header:
        return False
    if not hmac_header.isascii():
        return False
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    expected = base64.b64encode(digest)
    return hmac.compare_digest(hmac_header.encode("ascii"), expected)

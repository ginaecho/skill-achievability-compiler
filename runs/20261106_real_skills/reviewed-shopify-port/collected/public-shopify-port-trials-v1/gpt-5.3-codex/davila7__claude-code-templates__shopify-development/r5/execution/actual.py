import base64
import hashlib
import hmac


def verify_webhook(raw_body: bytes, hmac_header: str | None, secret: str) -> bool:
    if not hmac_header:
        return False
    if not hmac_header.isascii():
        return False

    expected = base64.b64encode(
        hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    ).decode("ascii")

    return hmac.compare_digest(hmac_header, expected)

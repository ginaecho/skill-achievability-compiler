import base64
import hashlib
import hmac


def verify_webhook(raw_body: bytes, hmac_header: str | None, secret: str) -> bool:
    if not hmac_header:
        return False

    try:
        provided_digest = hmac_header.encode("ascii")
    except UnicodeEncodeError:
        return False

    expected_digest = base64.b64encode(
        hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    )
    return hmac.compare_digest(provided_digest, expected_digest)

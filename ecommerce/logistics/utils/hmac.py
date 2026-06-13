import base64
import hashlib
import hmac


def verify_shopify_hmac(body: bytes, secret: str, header_hmac: str) -> bool:
    if not secret or not header_hmac:
        return False
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    computed = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(computed, header_hmac)

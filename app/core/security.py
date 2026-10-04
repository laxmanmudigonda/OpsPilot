import hashlib
import hmac
import time

from fastapi import Header, HTTPException, Request, status

from app.core.config import get_settings


def verify_hmac(secret: str, body: bytes, signature: str, prefix: str = "sha256=") -> bool:
    if not secret or not signature.startswith(prefix):
        return False
    expected = prefix + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_slack_request(secret: str, body: bytes, timestamp: str, signature: str) -> bool:
    try:
        if abs(time.time() - int(timestamp)) > 300:
            return False
    except (TypeError, ValueError):
        return False
    base = f"v0:{timestamp}:".encode() + body
    expected = "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()
    return bool(secret) and hmac.compare_digest(expected, signature)


async def require_api_key(x_api_key: str = Header(default="")) -> None:
    expected = get_settings().api_key
    if not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


async def raw_body(request: Request) -> bytes:
    return await request.body()

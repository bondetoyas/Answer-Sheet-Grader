"""Password hashing and signed tokens using only the standard library."""

import base64
import hashlib
import hmac
import json
import secrets
import time

_SCRYPT = dict(n=2**14, r=8, p=1, dklen=32)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, digest_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), **_SCRYPT)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def create_token(user_id: int, secret: str, ttl_seconds: int, now: float | None = None) -> str:
    payload = {"uid": user_id, "exp": int((now or time.time()) + ttl_seconds)}
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify_token(token: str, secret: str, now: float | None = None) -> int | None:
    """Return the user id, or None if the token is invalid or expired."""
    try:
        body, sig = token.split(".")
        expected = _b64(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_unb64(body))
        if payload["exp"] < (now or time.time()):
            return None
        return int(payload["uid"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


class RateLimiter:
    """Sliding-window limiter (per process; run a single worker or use a proxy limit)."""

    def __init__(self, limit: int, window_seconds: int):
        self.limit, self.window, self.hits = limit, window_seconds, {}

    def allow(self, key: str, now: float | None = None) -> bool:
        now = now or time.time()
        recent = [t for t in self.hits.get(key, []) if now - t < self.window]
        if len(recent) >= self.limit:
            self.hits[key] = recent
            return False
        recent.append(now)
        self.hits[key] = recent
        return True

    def reset(self, key: str) -> None:
        self.hits.pop(key, None)

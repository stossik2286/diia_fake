import os
import json
import time
import hmac
import hashlib
import base64

SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-to-a-random-secret").encode("utf-8")


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _base64url_decode(s: str) -> bytes:
    s += "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s)


def sign_token(payload: dict) -> str:
    """Create a signed token string from payload (stateless, no storage needed)"""
    payload["iat"] = time.time()
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    b64 = _base64url_encode(raw)
    sig = hmac.new(SECRET_KEY, b64.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{b64}.{sig}"


def verify_token(token: str) -> dict | None:
    """Verify and decode a signed token. Returns payload dict or None if invalid/expired."""
    if "." not in token:
        return None
    b64, sig = token.rsplit(".", 1)
    expected = hmac.new(SECRET_KEY, b64.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        payload = json.loads(_base64url_decode(b64))
    except Exception:
        return None
    if payload.get("exp", 0) <= time.time():
        return None
    return payload


# For backward compatibility with file-based code — no-op stubs
def init():
    pass


def save_token(token_key, data):
    pass


def get_token(token_key):
    return None


def delete_token(token_key):
    pass


def get_all_tokens():
    return {}


def save_photo(token_key, photo_bytes):
    pass


def get_photo_bytes(token_key):
    return None


def clean_expired():
    return 0

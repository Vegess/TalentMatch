"""Password hashing, access tokens (JWT) and refresh tokens (opaque, stored as SHA-256)."""
import base64
import datetime as dt
import hashlib
import hmac
import secrets

import jwt

from app.core import config

_PBKDF2_ITER = 390_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITER)
    return "pbkdf2_sha256${}${}${}".format(
        _PBKDF2_ITER, base64.b64encode(salt).decode(), base64.b64encode(digest).decode())


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_b64, hash_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt_b64), int(iters))
        return hmac.compare_digest(digest, base64.b64decode(hash_b64))
    except Exception:
        return False


def password_problem(password: str) -> str | None:
    """Return a human-readable reason the password is too weak, or None."""
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if password.isdigit() or password.isalpha():
        return "Password must mix letters with numbers or symbols."
    return None


def create_access_token(user_id: int, role: str) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {"sub": str(user_id), "role": role, "iat": now,
               "exp": now + dt.timedelta(minutes=config.ACCESS_TOKEN_MINUTES), "typ": "access"}
    return jwt.encode(payload, config.SECRET_KEY, algorithm="HS256")


def decode_access_token(token: str) -> dict | None:
    try:
        data = jwt.decode(token, config.SECRET_KEY, algorithms=["HS256"])
        return data if data.get("typ") == "access" else None
    except jwt.PyJWTError:
        return None


def new_refresh_token() -> tuple[str, str]:
    """Return (raw token for the cookie, sha256 hash for the database)."""
    raw = secrets.token_urlsafe(32)
    return raw, sha256(raw)


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()

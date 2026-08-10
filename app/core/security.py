"""Security primitives shared across the app (Dev A, task 1.2).

Split of responsibilities:
  * password hashing (bcrypt via passlib)
  * ACCESS token  = short-lived JWT, carries `sub` (user id) + `role`
  * REFRESH token = opaque random string; only its SHA-256 hash is stored
    in the `refresh_tokens` table (never the raw token).

This module is pure crypto/helpers — it does NOT touch the DB. The auth
service (task 1.4) persists refresh-token hashes using `hash_refresh_token`
and `refresh_token_expires_at`.
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings

# Token type claim values (guard against using a refresh token where an
# access token is expected, and vice-versa).
ACCESS_TOKEN_TYPE = "access"
# Vé đăng ký tạm: cấp sau khi Google xác thực email nhưng tài khoản chưa tồn tại.
# Không phải access token (type khác) nên không gọi được API nào bằng vé này.
SIGNUP_TICKET_TYPE = "google_signup"

# bcrypt only considers the first 72 bytes of a password and (since v4.1)
# raises on longer input, so we truncate consistently in hash + verify.
_BCRYPT_MAX_BYTES = 72


# --------------------------------------------------------------------------- #
# Password hashing (bcrypt)
# --------------------------------------------------------------------------- #
# NOTE: uses the `bcrypt` package directly instead of passlib. passlib 1.7.4
# (its last release) is incompatible with bcrypt >= 4.1 / 5.x, which is the
# only build available on Python 3.14. Same algorithm, same security.
def _pw_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    """Return a bcrypt hash for `password` (safe to store in users.password_hash)."""
    return bcrypt.hashpw(_pw_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify `plain_password` against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(_pw_bytes(plain_password), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# --------------------------------------------------------------------------- #
# Access token (JWT)
# --------------------------------------------------------------------------- #
def create_access_token(
    subject: str | int,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed access JWT.

    `subject` is the user id; `role` is the user's role value (e.g. "MENTOR").
    """
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": str(subject),
        "role": role,
        "type": ACCESS_TOKEN_TYPE,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode & verify an access JWT (signature + expiry).

    Raises `jwt.PyJWTError` (or a subclass) if invalid/expired, or if the
    token is not of type "access". Callers translate this into HTTP 401.
    """
    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )
    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise jwt.InvalidTokenError("Not an access token")
    return payload


# --------------------------------------------------------------------------- #
# Vé đăng ký tạm (sau khi Google đã xác thực email)
# --------------------------------------------------------------------------- #
def create_signup_ticket(*, email: str, full_name: str, avatar_url: str | None) -> str:
    """JWT ngắn hạn chứng nhận "Google đã xác thực email này".

    Frontend gửi lại vé kèm hồ sơ ở `POST /auth/google/complete`. Nhờ vậy email
    trong tài khoản mới luôn là email Google đã xác thực — client không tự khai được.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": email,
        "name": full_name,
        "picture": avatar_url,
        "type": SIGNUP_TICKET_TYPE,
        "iat": now,
        "exp": now + timedelta(minutes=settings.SIGNUP_TICKET_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_signup_ticket(token: str) -> dict:
    """Giải mã vé đăng ký. Raise `jwt.PyJWTError` nếu sai/hết hạn/không phải vé."""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    if payload.get("type") != SIGNUP_TICKET_TYPE:
        raise jwt.InvalidTokenError("Not a signup ticket")
    return payload


# --------------------------------------------------------------------------- #
# Refresh token (opaque; stored hashed)
# --------------------------------------------------------------------------- #
def create_refresh_token() -> str:
    """Generate a new high-entropy opaque refresh token (raw, give to client)."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(raw_token: str) -> str:
    """SHA-256 hash of a refresh token — store THIS in `refresh_tokens.token_hash`."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def verify_refresh_token(raw_token: str, token_hash: str) -> bool:
    """Constant-time compare of a raw refresh token against its stored hash."""
    return hmac.compare_digest(hash_refresh_token(raw_token), token_hash)


def refresh_token_expires_at() -> datetime:
    """UTC expiry timestamp for a newly issued refresh token."""
    return datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )

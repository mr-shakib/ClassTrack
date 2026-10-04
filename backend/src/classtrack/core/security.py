"""Password hashing and session tokens.

Uses ``bcrypt`` and ``PyJWT`` directly rather than passlib/python-jose, both of
which are unmaintained and break on current Python.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from classtrack.core.config import get_settings
from classtrack.core.errors import AuthError, ValidationError

#: bcrypt reads no further than this, and from 5.0 refuses anything longer.
MAX_PASSWORD_BYTES = 72


def hash_password(plain: str) -> str:
    encoded = plain.encode()
    if len(encoded) > MAX_PASSWORD_BYTES:
        raise ValidationError("That password is too long. Keep it under 72 characters.")
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except (ValueError, TypeError):
        # A malformed stored hash must read as "wrong password", never crash.
        return False


def create_token(user_id: int, role: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(hours=settings.jwt_expire_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Session expired. Please sign in again.") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid session token.") from exc

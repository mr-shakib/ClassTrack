"""Authentication."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from classtrack.core.errors import AuthError
from classtrack.core.security import verify_password
from classtrack.models import User


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    """Return the user for these credentials, or raise.

    The same message covers "no such account", "wrong password" and "disabled":
    distinguishing them tells an attacker which emails are real.
    """
    user = await session.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise AuthError("Invalid credentials")
    return user

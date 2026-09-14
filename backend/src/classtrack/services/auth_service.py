"""Authentication."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from classtrack.core.errors import AuthError
from classtrack.core.security import verify_password
from classtrack.models import Role, User


async def authenticate(session: AsyncSession, username: str, password: str) -> User:
    """Return the user for these credentials, or raise.

    ``username`` is an email address, or a teacher's initial -- teachers are
    given accounts by initial and may not have an address on file.

    The same message covers "no such account", "wrong password" and "disabled":
    distinguishing them tells an attacker which accounts are real.
    """
    username = username.strip()
    if "@" in username:
        query = select(User).where(User.email == username.lower())
    else:
        query = select(User).where(
            User.role == Role.TEACHER, User.teacher_initial == username.upper()
        )
    user = await session.scalar(query)
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise AuthError("Invalid credentials")
    return user

"""Authentication."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from classtrack.core.errors import AuthError
from classtrack.core.security import verify_password
from classtrack.models import User


async def authenticate(session: AsyncSession, username: str, password: str) -> User:
    """Return the user for these credentials, or raise.

    ``username`` is an email address, a teacher's initial, or a staff member's
    employee ID -- teachers are given accounts by initial and staff may be given
    one by ID, and neither need have an address on file. An ID is stored where
    the address would be, so it is matched there once no initial claims it.

    The same message covers "no such account", "wrong password" and "disabled":
    distinguishing them tells an attacker which accounts are real.
    """
    username = username.strip()
    by_email = select(User).where(User.email == username.lower())
    if "@" in username:
        user = await session.scalar(by_email)
    else:
        user = await session.scalar(
            select(User).where(User.teacher_initial == username.upper())
        ) or await session.scalar(by_email)
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise AuthError("Invalid credentials")
    return user

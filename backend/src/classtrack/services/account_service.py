"""Teacher accounts, created by an admin from the faculty directory.

A teacher signs in with their initial, which is also the key that joins the
account to its routine rows -- so the initial is the one thing the account
cannot be created without, and the faculty list is where it comes from.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from classtrack.core.errors import NotFoundError, ValidationError
from classtrack.core.security import hash_password
from classtrack.models import Role, Teacher, User
from classtrack.services import audit_service

#: ``user.email`` is required and unique, but a teacher signs in by initial and
#: may have no address on file. This placeholder domain is never mailed.
PLACEHOLDER_DOMAIN = "teacher.classtrack"

MIN_PASSWORD = 6


async def teacher_accounts(session: AsyncSession) -> dict[str, User]:
    """Every teacher account, keyed by initial."""
    rows = (
        await session.scalars(
            select(User).where(User.role == Role.TEACHER, User.teacher_initial.is_not(None))
        )
    ).all()
    return {u.teacher_initial: u for u in rows if u.teacher_initial}


async def create_teacher_account(
    session: AsyncSession, *, initial: str, password: str, actor: User
) -> User:
    initial = initial.strip().upper()
    teacher = await session.scalar(select(Teacher).where(Teacher.initial == initial))
    if teacher is None:
        raise NotFoundError(f"No faculty member with initial {initial!r}.")
    if len(password) < MIN_PASSWORD:
        raise ValidationError(f"The password must be at least {MIN_PASSWORD} characters.")

    existing = await session.scalar(
        select(User).where(User.role == Role.TEACHER, User.teacher_initial == initial)
    )
    if existing is not None:
        raise ValidationError(f"{initial} already has an account.")

    email = f"{initial.lower()}@{PLACEHOLDER_DOMAIN}"
    if await session.scalar(select(User).where(User.email == email)):
        raise ValidationError(f"{email} is already in use.")

    account = User(
        email=email,
        full_name=teacher.name,
        role=Role.TEACHER,
        teacher_initial=initial,
        password_hash=hash_password(password),
    )
    session.add(account)
    await session.flush()

    audit_service.record(
        session,
        actor_id=actor.id,
        entity_type="user",
        entity_id=account.id,
        action="teacher_account_created",
        after={"teacher_initial": initial, "full_name": teacher.name},
    )
    return account


async def reset_teacher_password(
    session: AsyncSession, *, initial: str, password: str, actor: User
) -> User:
    initial = initial.strip().upper()
    account = await session.scalar(
        select(User).where(User.role == Role.TEACHER, User.teacher_initial == initial)
    )
    if account is None:
        raise NotFoundError(f"{initial} has no account yet.")
    if len(password) < MIN_PASSWORD:
        raise ValidationError(f"The password must be at least {MIN_PASSWORD} characters.")

    account.password_hash = hash_password(password)
    audit_service.record(
        session,
        actor_id=actor.id,
        entity_type="user",
        entity_id=account.id,
        action="teacher_password_reset",
        after={"teacher_initial": initial},
    )
    return account

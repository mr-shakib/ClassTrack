"""Teacher accounts, created by an admin from the faculty directory.

A teacher signs in with their initial, which is also the key that joins the
account to its routine rows -- so the initial is the one thing the account
cannot be created without, and the faculty list is where it comes from.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from classtrack.core.errors import ForbiddenError, NotFoundError, ValidationError
from classtrack.core.security import hash_password
from classtrack.models import BuiltinRole, Permission, Role, Teacher, User
from classtrack.services import audit_service, role_service

#: ``user.email`` is required and unique, but a teacher signs in by initial and
#: may have no address on file. This placeholder domain is never mailed.
PLACEHOLDER_DOMAIN = "teacher.classtrack"

MIN_PASSWORD = 6


async def teacher_accounts(session: AsyncSession) -> dict[str, User]:
    """Every teacher account, keyed by initial."""
    rows = (
        await session.scalars(
            select(User).where(User.teacher_initial.is_not(None))
        )
    ).all()
    return {u.teacher_initial: u for u in rows if u.teacher_initial}


async def create_teacher_account(
    session: AsyncSession,
    *,
    initial: str,
    password: str,
    actor: User,
    roles: list[Role] | None = None,
) -> User:
    """``roles`` left out, the account gets the Teacher role.

    Choosing them is giving them, as on the Accounts tab: it takes the right to
    manage accounts, and every role chosen must grant only what the admin holds.
    """
    initial = initial.strip().upper()
    teacher = await session.scalar(select(Teacher).where(Teacher.initial == initial))
    if teacher is None:
        raise NotFoundError(f"No faculty member with initial {initial!r}.")
    if len(password) < MIN_PASSWORD:
        raise ValidationError(f"The password must be at least {MIN_PASSWORD} characters.")

    existing = await session.scalar(
        select(User).where(User.teacher_initial == initial)
    )
    if existing is not None:
        raise ValidationError(f"{initial} already has an account.")

    email = f"{initial.lower()}@{PLACEHOLDER_DOMAIN}"
    if await session.scalar(select(User).where(User.email == email)):
        raise ValidationError(f"{email} is already in use.")

    if roles is None:
        roles = [await role_service.builtin(session, BuiltinRole.TEACHER)]
    else:
        if not actor.can(Permission.MANAGE_ACCOUNTS):
            raise ForbiddenError(
                "Choosing a teacher's roles takes the Manage accounts permission. "
                "Leave them out and the account gets the Teacher role."
            )
        for role in roles:
            role_service.require_held(actor, role, f"give {role.name}")

    account = User(
        email=email,
        full_name=teacher.name,
        teacher_initial=initial,
        password_hash=hash_password(password),
    )
    role_service.check_kinds(account, roles)
    account.roles = roles
    session.add(account)
    await session.flush()

    audit_service.record(
        session,
        actor_id=actor.id,
        entity_type="user",
        entity_id=account.id,
        action="teacher_account_created",
        after={
            "teacher_initial": initial,
            "full_name": teacher.name,
            "roles": sorted(r.name for r in roles),
        },
    )
    return account


async def create_all_teacher_accounts(
    session: AsyncSession, *, password: str, actor: User
) -> list[User]:
    """Give every faculty member who has no account one, all on ``password``.

    Teachers who already have an account, deactivated or not, keep it as it is.
    The hash is computed once and shared: the accounts share the password
    anyway, so a salt each buys nothing, and a bcrypt round per teacher would
    hold the request for a minute across the whole faculty.
    """
    if len(password) < MIN_PASSWORD:
        raise ValidationError(f"The password must be at least {MIN_PASSWORD} characters.")

    have = await teacher_accounts(session)
    taken = set((await session.scalars(select(User.email))).all())
    password_hash = hash_password(password)
    teacher_role = await role_service.builtin(session, BuiltinRole.TEACHER)

    created: list[User] = []
    for teacher in (await session.scalars(select(Teacher).order_by(Teacher.initial))).all():
        email = f"{teacher.initial.lower()}@{PLACEHOLDER_DOMAIN}"
        if teacher.initial in have or email in taken:
            continue
        account = User(
            email=email,
            full_name=teacher.name,
            teacher_initial=teacher.initial,
            password_hash=password_hash,
            roles=[teacher_role],
        )
        session.add(account)
        created.append(account)
    await session.flush()

    for account in created:
        audit_service.record(
            session,
            actor_id=actor.id,
            entity_type="user",
            entity_id=account.id,
            action="teacher_account_created",
            after={"teacher_initial": account.teacher_initial, "full_name": account.full_name},
        )
    return created


async def reset_teacher_password(
    session: AsyncSession, *, initial: str, password: str, actor: User
) -> User:
    initial = initial.strip().upper()
    account = await session.scalar(
        select(User).where(User.teacher_initial == initial)
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

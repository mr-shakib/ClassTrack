"""Staff zone assignments."""

from __future__ import annotations

import re

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from classtrack.core.errors import NotFoundError, ValidationError
from classtrack.core.security import hash_password
from classtrack.models import BuiltinRole, ClassSession, Routine, StaffZone, Teacher, User
from classtrack.services import audit_service, role_service, zones

#: A staff sign-in without an "@". Kept free of spaces and "@" so it can never
#: be mistaken for an email address at sign-in.
EMPLOYEE_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")


async def zones_for_user(session: AsyncSession, user_id: int) -> list[str]:
    return list(
        (
            await session.scalars(
                select(StaffZone.zone_key).where(StaffZone.user_id == user_id)
            )
        ).all()
    )


async def assignments_by_user(session: AsyncSession) -> dict[int, list[str]]:
    """Every assignment, keyed by user, for the admin listing."""
    out: dict[int, list[str]] = {}
    for row in (await session.scalars(select(StaffZone))).all():
        out.setdefault(row.user_id, []).append(row.zone_key)
    for keys in out.values():
        keys.sort()
    return out


async def available_zones(session: AsyncSession) -> list[dict[str, object]]:
    """The zones the active routine actually uses.

    Derived from the live routine rather than a fixed list, so a new building
    appears the moment a routine that uses it is activated.
    """
    routine = await session.scalar(select(Routine).where(Routine.is_active))
    if routine is None:
        return []
    rooms = list(
        (
            await session.scalars(
                select(ClassSession.room)
                .where(ClassSession.routine_id == routine.id)
                .distinct()
            )
        ).all()
    )
    return zones.zones_for_rooms(rooms)


async def create_staff(
    session: AsyncSession,
    *,
    full_name: str,
    email: str,
    password: str,
    zone_keys: list[str],
    actor: User,
) -> User:
    """Create an office staff account and give it its floors in one step.

    A staff account exists to check a floor, so it is created with one. An
    account with no floor has nothing to do and would silently show an empty
    checking screen.

    ``email`` is what they sign in with: an email address, or an employee ID
    for staff who have no address. The ID is kept in ``user.email`` as is --
    nothing mails a staff account, and it is the only column a sign-in matches.
    """
    email = email.strip().lower()
    if not email:
        raise ValidationError("An email address or employee ID is required.")
    if "@" in email:
        try:
            validate_email(email, check_deliverability=False)
        except EmailNotValidError as exc:
            raise ValidationError(f"{email} is not a valid email address.") from exc
    else:
        if not EMPLOYEE_ID.fullmatch(email):
            raise ValidationError(
                "An employee ID is letters, digits, dots, dashes or underscores, no spaces."
            )
        # Sign-in tries a teacher initial before an employee ID, so an ID that
        # spells one would sign in to the teacher's account, never this one.
        if await session.scalar(select(Teacher).where(Teacher.initial == email.upper())):
            raise ValidationError(f"{email} is a faculty initial. Use another employee ID.")
    if await session.scalar(select(User).where(User.email == email)):
        raise ValidationError(f"{email} already has an account.")
    if len(password) < 6:
        raise ValidationError("The password must be at least 6 characters.")
    if not zone_keys:
        raise ValidationError("Assign at least one floor. Staff check a floor.")

    member = User(
        email=email,
        full_name=full_name.strip(),
        password_hash=hash_password(password),
        roles=[await role_service.builtin(session, BuiltinRole.STAFF)],
    )
    session.add(member)
    await session.flush()

    await set_zones(session, user_id=member.id, zone_keys=zone_keys, actor=actor)

    audit_service.record(
        session,
        actor_id=actor.id,
        entity_type="user",
        entity_id=member.id,
        action="staff_created",
        after={"email": email, "full_name": member.full_name},
    )
    await session.flush()
    return member


async def set_zones(
    session: AsyncSession, *, user_id: int, zone_keys: list[str], actor: User
) -> list[str]:
    """Replace a staff member's floors.

    Their floors *are* their workload: the checking screen shows those rooms and
    nothing else. An empty list is allowed here so an account can be parked, but
    it leaves that person with no classes, and the admin screen says so.
    """
    target = await session.get(User, user_id)
    if target is None:
        raise NotFoundError(f"No user with id {user_id}")
    if not target.is_staff:
        raise ValidationError(
            "Only accounts holding a staff role are assigned to floors.",
            detail={"roles": [r.name for r in target.roles]},
        )

    known = {str(z["key"]) for z in await available_zones(session)}
    cleaned: list[str] = []
    for key in zone_keys:
        key = key.strip().upper()
        if not key:
            continue
        if key not in known:
            raise ValidationError(
                f"{key!r} is not a zone in the active routine.",
                detail={"valid_zones": sorted(known)},
            )
        if key not in cleaned:
            cleaned.append(key)

    before = await zones_for_user(session, user_id)

    await session.execute(delete(StaffZone).where(StaffZone.user_id == user_id))
    for key in cleaned:
        session.add(StaffZone(user_id=user_id, zone_key=key))

    audit_service.record(
        session,
        actor_id=actor.id,
        entity_type="user",
        entity_id=user_id,
        action="zones_assigned",
        before={"zones": sorted(before)},
        after={"zones": sorted(cleaned)},
    )
    await session.flush()
    return cleaned

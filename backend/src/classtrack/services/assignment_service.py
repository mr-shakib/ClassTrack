"""Staff zone assignments."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from classtrack.core.errors import NotFoundError, ValidationError
from classtrack.core.security import hash_password
from classtrack.models import ClassSession, Role, Routine, StaffZone, User
from classtrack.services import audit_service, zones


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
    """
    email = email.strip().lower()
    if not email:
        raise ValidationError("An email address is required.")
    if await session.scalar(select(User).where(User.email == email)):
        raise ValidationError(f"{email} already has an account.")
    if len(password) < 6:
        raise ValidationError("The password must be at least 6 characters.")
    if not zone_keys:
        raise ValidationError("Assign at least one floor. Staff check a floor.")

    member = User(
        email=email,
        full_name=full_name.strip(),
        role=Role.STAFF,
        password_hash=hash_password(password),
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
    if target.role is not Role.STAFF:
        raise ValidationError(
            "Only office staff accounts are assigned to floors.",
            detail={"role": target.role.value},
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

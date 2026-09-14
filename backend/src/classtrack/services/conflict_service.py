"""Makeup scheduling validation (BR-14).

Because the routine is a lattice of atomic slots, a "conflict" is not an
interval-overlap problem. Two classes either occupy the same ``(date, time_slot)``
cell or they do not, so every check here is an indexed equality lookup.

If you ever find yourself reaching for interval arithmetic in this file, the
lattice invariant has been broken somewhere upstream -- fix that instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as Date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from classtrack.models import (
    BLOCKING_KINDS,
    ClassInstance,
    ClassSession,
    ClassStatus,
    Holiday,
    MakeupClass,
    MakeupMode,
    MakeupStatus,
    Routine,
)
from classtrack.routine.lattice import SLOTS
from classtrack.services import zones

#: Statuses that no longer occupy their cell, so they cannot block a makeup.
_VACATED = (
    ClassStatus.CANCELLED,
    ClassStatus.MISSED,
    ClassStatus.NOT_CHECKED,
    ClassStatus.ONLINE_REJECTED,
)


@dataclass(slots=True)
class Conflict:
    type: str
    message: str
    instance_id: int | None = None


@dataclass(slots=True)
class ConflictReport:
    conflicts: list[Conflict] = field(default_factory=list)
    #: v1 blocks on any conflict. The flag is the seam for the
    #: override-with-mandatory-reason flow described in the source SRS 11.
    overridable: bool = True

    @property
    def ok(self) -> bool:
        return not self.conflicts

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "overridable": self.overridable,
            "conflicts": [
                {"type": c.type, "message": c.message, "instance_id": c.instance_id}
                for c in self.conflicts
            ],
        }


async def check(
    session: AsyncSession,
    *,
    on: Date,
    time_slot: str,
    teacher_initial: str,
    room: str | None = None,
    section: str | None = None,
    semester_id: int | None = None,
    exclude_instance_id: int | None = None,
    exclude_makeup_id: int | None = None,
) -> ConflictReport:
    """Validate a proposed makeup slot.

    ``room`` is None for an online makeup, which occupies no room and therefore
    cannot conflict on one.
    """
    report = ConflictReport()

    if time_slot not in SLOTS:
        report.conflicts.append(
            Conflict("SLOT", f"{time_slot!r} is not a routine slot.")
        )
        # Without a valid slot there is no cell to compare against.
        report.overridable = False
        return report

    # Holiday / closed day.
    holiday_query = select(Holiday).where(
        Holiday.date == on, Holiday.kind.in_(BLOCKING_KINDS)
    )
    if semester_id is not None:
        holiday_query = holiday_query.where(Holiday.semester_id == semester_id)
    holiday = await session.scalar(holiday_query)
    if holiday is not None:
        report.conflicts.append(
            Conflict("HOLIDAY", f"{on:%d %B %Y} is {holiday.title} ({holiday.kind.value}).")
        )

    occupants = await _occupants(session, on, time_slot, exclude_instance_id)

    for occupant in occupants:
        if occupant.teacher_initial == teacher_initial:
            report.conflicts.append(
                Conflict(
                    "TEACHER",
                    f"{teacher_initial} already teaches {occupant.course_code} "
                    f"in {occupant.room} at {time_slot}.",
                    occupant.id,
                )
            )
        if room is not None and occupant.room == room.upper():
            report.conflicts.append(
                Conflict(
                    "ROOM",
                    f"{occupant.room} is occupied by {occupant.course_code} "
                    f"({occupant.section}) at {time_slot}.",
                    occupant.id,
                )
            )
        if section is not None and occupant.section == section:
            report.conflicts.append(
                Conflict(
                    "SECTION",
                    f"Section {section} already has {occupant.course_code} "
                    f"in {occupant.room} at {time_slot}.",
                    occupant.id,
                )
            )

    # A pending physical request has no instance yet, but it has claimed its
    # room: two teachers must not be offered, and then approved into, one cell.
    for pending in await _pending_requests(session, on, time_slot, exclude_makeup_id):
        if pending.teacher_initial == teacher_initial:
            report.conflicts.append(
                Conflict(
                    "TEACHER",
                    f"{teacher_initial} already has a reschedule request for {time_slot}.",
                )
            )
        if room is not None and pending.room == room.upper():
            report.conflicts.append(
                Conflict(
                    "ROOM",
                    f"{pending.room} is requested by {pending.teacher_initial} at {time_slot}.",
                )
            )

    return report


async def _occupants(
    session: AsyncSession,
    on: Date,
    time_slot: str,
    exclude_instance_id: int | None = None,
) -> list[ClassInstance]:
    """Everything already occupying a cell. One index seek."""
    query = select(ClassInstance).where(
        ClassInstance.date == on,
        ClassInstance.time_slot == time_slot,
        ClassInstance.status.not_in(_VACATED) | ClassInstance.status.is_(None),
    )
    if exclude_instance_id is not None:
        query = query.where(ClassInstance.id != exclude_instance_id)
    return list((await session.scalars(query)).all())


async def _pending_requests(
    session: AsyncSession,
    on: Date,
    time_slot: str,
    exclude_makeup_id: int | None = None,
) -> list[MakeupClass]:
    query = select(MakeupClass).where(
        MakeupClass.date == on,
        MakeupClass.time_slot == time_slot,
        MakeupClass.status == MakeupStatus.PENDING,
        MakeupClass.mode == MakeupMode.PHYSICAL,
    )
    if exclude_makeup_id is not None:
        query = query.where(MakeupClass.id != exclude_makeup_id)
    return list((await session.scalars(query)).all())


async def free_rooms(session: AsyncSession, *, on: Date, time_slot: str) -> list[dict]:
    """Rooms of the active routine with nothing in them on this cell.

    The room universe is the live routine, the same source the staff floors
    come from, so a room offered here is always one some staff member checks.
    A room is taken by a class still holding its cell or by a pending request.
    """
    if time_slot not in SLOTS:
        return []

    routine = await session.scalar(select(Routine).where(Routine.is_active))
    if routine is None:
        return []
    known = (
        await session.execute(
            select(ClassSession.room, ClassSession.room_type)
            .where(ClassSession.routine_id == routine.id)
            .distinct()
        )
    ).all()

    taken = {o.room for o in await _occupants(session, on, time_slot)}
    taken |= {p.room for p in await _pending_requests(session, on, time_slot) if p.room}

    types: dict[str, str] = {}
    for room, room_type in known:
        if room and room not in taken:
            types.setdefault(room, room_type)

    return [
        {
            "room": room,
            "room_type": types[room],
            "zone": zones.room_zone(room).short_label,
        }
        for room in sorted(types)
    ]

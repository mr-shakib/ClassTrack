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

from classtrack.core.errors import ConflictError
from classtrack.models import (
    BLOCKING_KINDS,
    ClassInstance,
    ClassSession,
    ClassStatus,
    Holiday,
    MakeupClass,
    MakeupStatus,
    Routine,
    Semester,
)
from classtrack.routine import clock
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
    start_min: int | None = None,
    end_min: int | None = None,
    room: str | None = None,
    section: str | None = None,
    semester_id: int | None = None,
    exclude_instance_id: int | None = None,
    exclude_makeup_id: int | None = None,
) -> ConflictReport:
    """Validate a proposed makeup time.

    ``room`` is None for an online makeup, which occupies no room and therefore
    cannot conflict on one.

    ``start_min``/``end_min`` are set only for an online class held at a time
    the teacher chose off the clock. Such a period is not a cell, so it cannot
    be compared by slot equality: it is matched by overlap instead, against
    every class on the day. That is the single exception to the lattice rule,
    and it is safe precisely because such a class holds no room -- see
    ``routine/clock.py``.
    """
    report = ConflictReport()
    free_clock = start_min is not None and end_min is not None

    if not free_clock and time_slot not in SLOTS:
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

    # No class is held while the exams run. Semesters never overlap, so the
    # date alone finds the semester.
    semester = await session.scalar(
        select(Semester).where(Semester.start_date <= on, Semester.end_date >= on)
    )
    if semester is not None and semester.in_exams(on):
        final = semester.final_exam_start is not None and on >= semester.final_exam_start
        report.conflicts.append(
            Conflict(
                "EXAM",
                f"{on:%d %B %Y} is in the {semester.name} "
                f"{'final' if final else 'mid-term'} exams.",
            )
        )

    occupants = await _occupants(
        session, on, time_slot, exclude_instance_id, start_min=start_min, end_min=end_min
    )

    # Name the occupant's own time, not the proposed one: an overlapping class
    # runs at a different time, and "already teaches ... at 10:00-11:30" is what
    # tells the teacher which class is in the way.
    for occupant in occupants:
        if occupant.teacher_initial == teacher_initial:
            report.conflicts.append(
                Conflict(
                    "TEACHER",
                    f"{teacher_initial} already teaches {occupant.course_code} "
                    f"in {occupant.room} at {occupant.time_slot}.",
                    occupant.id,
                )
            )
        if room is not None and occupant.room == room.upper():
            report.conflicts.append(
                Conflict(
                    "ROOM",
                    f"{occupant.room} is occupied by {occupant.course_code} "
                    f"({occupant.section}) at {occupant.time_slot}.",
                    occupant.id,
                )
            )
        if section is not None and occupant.section == section:
            report.conflicts.append(
                Conflict(
                    "SECTION",
                    f"Section {section} already has {occupant.course_code} "
                    f"in {occupant.room} at {occupant.time_slot}.",
                    occupant.id,
                )
            )

    # An undecided request has no instance yet, but the teacher is spoken for
    # at that time: they must not be approved into a time they have filled.
    pending_requests = await _pending_requests(
        session, on, time_slot, exclude_makeup_id, start_min=start_min, end_min=end_min
    )
    for pending in pending_requests:
        if pending.teacher_initial == teacher_initial:
            report.conflicts.append(
                Conflict(
                    "TEACHER",
                    f"{teacher_initial} already has a reschedule request "
                    f"for {pending.time_slot}.",
                )
            )
        if room is not None and pending.room == room.upper():
            report.conflicts.append(
                Conflict(
                    "ROOM",
                    f"{pending.room} is requested by {pending.teacher_initial} "
                    f"at {pending.time_slot}.",
                )
            )

    return report


async def ensure_room_unshared(session: AsyncSession, booked: ClassInstance) -> None:
    """Back out of a booking that lost a race for its room.

    ``check`` reads before anything is written, so two teachers who take the
    same empty room for the same slot at the same moment can both pass it.
    Counting again once our own row is flushed closes that: a rival committed
    in between is visible now. SQLite admits one writer at a time, so from our
    first write until our commit no rival can slip a row in behind this count.
    """
    holders = [
        o
        for o in await _occupants(session, booked.date, booked.time_slot)
        if o.room == booked.room
    ]
    if len(holders) > 1:
        raise ConflictError(
            f"{booked.room} was booked by someone else for that time a moment ago. "
            "Pick another room.",
            detail={"room": booked.room, "date": booked.date.isoformat()},
        )


async def _occupants(
    session: AsyncSession,
    on: Date,
    time_slot: str,
    exclude_instance_id: int | None = None,
    *,
    start_min: int | None = None,
    end_min: int | None = None,
) -> list[ClassInstance]:
    """Everything already occupying the proposed time.

    Normally that is one cell, found by slot equality on an index seek. With
    bounds -- a free-clock online class, which is no cell at all -- it is every
    class of the day whose own period overlaps, matched on ``start_min`` and
    ``end_min``, which every instance carries.
    """
    query = select(ClassInstance).where(
        ClassInstance.date == on,
        ClassInstance.status.not_in(_VACATED) | ClassInstance.status.is_(None),
    )
    if start_min is not None and end_min is not None:
        query = query.where(
            ClassInstance.start_min < end_min, ClassInstance.end_min > start_min
        )
    else:
        query = query.where(ClassInstance.time_slot == time_slot)
    if exclude_instance_id is not None:
        query = query.where(ClassInstance.id != exclude_instance_id)
    return list((await session.scalars(query)).all())


async def _pending_requests(
    session: AsyncSession,
    on: Date,
    time_slot: str,
    exclude_makeup_id: int | None = None,
    *,
    start_min: int | None = None,
    end_min: int | None = None,
) -> list[MakeupClass]:
    """Requests still awaiting a decision, whatever their mode.

    An in-room reschedule is never one of these -- it becomes an instance the
    moment it is made, and blocks through ``_occupants`` from then on. What is
    left is online requests, which hold no room but do hold their teacher, and
    any in-room request from before that rule that is still in the queue.

    The queue is small, so a free-clock proposal resolves each row's bounds in
    Python rather than in SQL: a row that sits in a cell keeps its bounds in the
    lattice, not in its columns, and only ``bounds()`` knows which is which.
    """
    query = select(MakeupClass).where(
        MakeupClass.date == on,
        MakeupClass.status == MakeupStatus.PENDING,
    )
    if exclude_makeup_id is not None:
        query = query.where(MakeupClass.id != exclude_makeup_id)
    rows = list((await session.scalars(query)).all())
    if start_min is None or end_min is None:
        return [m for m in rows if m.time_slot == time_slot]
    return [m for m in rows if clock.overlaps(start_min, end_min, *m.bounds())]


async def free_rooms(session: AsyncSession, *, on: Date, time_slot: str) -> list[dict]:
    """Rooms of the active routine with nothing in them on this cell.

    The room universe is the live routine, the same source the staff floors
    come from, so a room offered here is always one some staff member checks.
    A room is taken by any class still holding its cell -- which includes a
    reschedule someone has already made, since that books its room at once.
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

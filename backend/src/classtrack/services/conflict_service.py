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
    ClassStatus,
    Holiday,
)
from classtrack.routine.lattice import SLOTS

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

    # Everything already occupying that cell. One index seek.
    query = select(ClassInstance).where(
        ClassInstance.date == on,
        ClassInstance.time_slot == time_slot,
        ClassInstance.status.not_in(_VACATED) | ClassInstance.status.is_(None),
    )
    if exclude_instance_id is not None:
        query = query.where(ClassInstance.id != exclude_instance_id)
    occupants = (await session.scalars(query)).all()

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

    return report

"""Extra classes: a teacher books an empty room for one of their sections.

An extra class sits on top of the routine. Staff check it like any class and it
counts like one: held, it is a class the course has had, towards its minimum;
missed, it is recorded as missed. What it is not is owed -- the routine never
promised it -- so missing one asks for no reschedule.

Booking needs no approval, for the reason an in-room reschedule needs none: an
empty room settles nothing an HoD would weigh. The room is held from the moment
the class is booked, and the teacher may give it back until the class starts.
"""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from classtrack.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from classtrack.db.base import utcnow
from classtrack.models import ClassInstance, ClassSession, ClassStatus, Routine, Semester, User
from classtrack.routine.lattice import SLOTS, slot_bounds
from classtrack.services import (
    audit_service,
    conflict_service,
    instance_service,
    makeup_service,
    notification_service,
    status_engine,
)


async def _active_routine(session: AsyncSession) -> Routine:
    routine = await session.scalar(select(Routine).where(Routine.is_active))
    if routine is None:
        raise ValidationError("There is no routine in force, so no class can be booked.")
    return routine


async def my_sections(session: AsyncSession, teacher_initial: str) -> list[dict[str, str]]:
    """The course-sections a teacher has on the routine in force, the only ones
    they may book an extra class for."""
    routine = await session.scalar(select(Routine).where(Routine.is_active))
    if routine is None:
        return []
    rows = (
        await session.scalars(
            select(ClassSession)
            .where(ClassSession.routine_id == routine.id, ClassSession.teacher == teacher_initial)
            .order_by(ClassSession.course_code, ClassSession.section)
        )
    ).all()
    seen: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        # A section meets several times a week; the first row speaks for it.
        seen.setdefault(
            (row.course_code, row.section),
            {
                "course_code": row.course_code,
                "course_title": row.course_title or "",
                "section": row.section,
                "room_type": row.room_type,
            },
        )
    return list(seen.values())


async def book(
    session: AsyncSession,
    *,
    user: User,
    course_code: str,
    section: str,
    on: Date,
    time_slot: str,
    room: str,
    now: datetime | None = None,
) -> ClassInstance:
    initial = user.teacher_initial
    if not initial:
        raise ForbiddenError("Only a teacher can book an extra class.")
    routine = await _active_routine(session)

    template = await session.scalar(
        select(ClassSession)
        .where(
            ClassSession.routine_id == routine.id,
            ClassSession.teacher == initial,
            ClassSession.course_code == course_code,
            ClassSession.section == section,
        )
        .limit(1)
    )
    if template is None:
        raise ValidationError(
            f"You do not teach {course_code} section {section} on the current routine."
        )

    if time_slot not in SLOTS:
        raise ValidationError(f"{time_slot!r} is not a routine slot.")
    day = instance_service.day_name(on)
    if day is None:
        # No routine class is held that day, so no staff member is there to check.
        raise ValidationError(f"No classes are held on {on:%A}s. Pick another day.")
    makeup_service.require_future(on, time_slot, None, now)

    semester = await session.scalar(select(Semester).where(Semester.is_active))
    if semester is None:
        raise ValidationError("No semester is running, so no class can be booked.")
    if not semester.start_date <= on <= semester.end_date:
        raise ValidationError(
            f"Pick a date inside the {semester.name} semester, "
            f"{semester.start_date:%d %b} to {semester.end_date:%d %b %Y}."
        )

    # Only a room the routine uses: those are the rooms some staff member checks.
    room = room.strip().upper()
    room_type = await session.scalar(
        select(ClassSession.room_type)
        .where(ClassSession.routine_id == routine.id, ClassSession.room == room)
        .limit(1)
    )
    if room_type is None:
        raise ValidationError(f"{room} is not a room on the routine.")

    report = await conflict_service.check(
        session,
        on=on,
        time_slot=time_slot,
        teacher_initial=initial,
        room=room,
        section=section,
        semester_id=semester.id,
    )
    if not report.ok:
        raise ConflictError(
            "That room and time are not free for this class.", detail=report.as_dict()
        )

    start_min, end_min = slot_bounds(time_slot)
    instance = ClassInstance(
        session_id=None,
        semester_id=semester.id,
        date=on,
        day=day,
        time_slot=time_slot,
        start_min=start_min,
        end_min=end_min,
        room=room,
        room_type=room_type,
        course_code=template.course_code,
        course_title=template.course_title,
        section=template.section,
        batch=template.batch,
        teacher_initial=initial,
        is_extra=True,
        status=None,
    )
    session.add(instance)
    await session.flush()
    await conflict_service.ensure_room_unshared(session, instance)

    audit_service.record(
        session,
        actor_id=user.id,
        entity_type="class_instance",
        entity_id=instance.id,
        action="extra_class_booked",
        after={
            "course_code": instance.course_code,
            "section": instance.section,
            "date": on.isoformat(),
            "time_slot": time_slot,
            "room": room,
        },
    )
    await notification_service.notify_extra_booked(session, instance)
    return instance


async def cancel(
    session: AsyncSession, *, user: User, instance_id: int, now: datetime | None = None
) -> ClassInstance:
    """Give the room back. Only the teacher's own, and only before it starts:
    once under way it is a class staff may already be checking."""
    instance = await session.get(ClassInstance, instance_id)
    if instance is None or not instance.is_extra:
        raise NotFoundError(f"No extra class with id {instance_id}")
    if instance.teacher_initial != user.teacher_initial:
        raise ForbiddenError("You may only cancel your own extra classes.")
    if instance.status is ClassStatus.CANCELLED:
        raise ValidationError("This extra class is already cancelled.")
    starts = status_engine.slot_start_at(instance.date, instance.start_min)
    if instance.status is not None or starts <= (now or status_engine.now_local()):
        raise ValidationError(
            "This class has started, so it can no longer be cancelled here. "
            "Ask the department office."
        )

    instance.status = ClassStatus.CANCELLED
    instance.resolved_at = utcnow()
    audit_service.record(
        session,
        actor_id=user.id,
        entity_type="class_instance",
        entity_id=instance.id,
        action="extra_class_cancelled",
        before={"status": None},
        after={"status": ClassStatus.CANCELLED.value},
    )
    return instance


async def list_mine(session: AsyncSession, teacher_initial: str) -> list[ClassInstance]:
    """A teacher's extra classes, latest first."""
    rows = (
        await session.scalars(
            select(ClassInstance)
            .where(ClassInstance.is_extra, ClassInstance.teacher_initial == teacher_initial)
            .order_by(ClassInstance.date.desc(), ClassInstance.start_min.desc())
            .limit(100)
        )
    ).all()
    return list(rows)

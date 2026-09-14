"""Makeup class workflow (BR-09 .. BR-13).

A teacher whose class was missed requests a reschedule. Every request is parked
as PENDING until an HoD decides, and only on approval is a monitoring instance
created. The two modes then diverge in exactly one way:

* **PHYSICAL** -- the request names an empty room. The approved instance enters
  room-wise staff checking like any other class (BR-10). A rejection returns
  the original to MISSED, because the teacher still owes the class.
* **ONLINE** -- the approved instance is excluded from physical checking (BR-12).

Every makeup keeps a non-null reference to the missed class it recovers (BR-13),
so a report can always show Missed -> Makeup Scheduled -> Makeup Completed.
"""

from __future__ import annotations

import logging
from datetime import date as Date
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from classtrack.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from classtrack.db.base import utcnow
from classtrack.models import (
    CheckOutcome,
    ClassInstance,
    ClassStatus,
    MakeupClass,
    MakeupMode,
    MakeupStatus,
    Role,
    Semester,
    User,
)
from classtrack.routine.lattice import SLOTS, slot_bounds
from classtrack.services import (
    audit_service,
    conflict_service,
    instance_service,
    notification_service,
    status_engine,
)

logger = logging.getLogger(__name__)


async def _load_original(session: AsyncSession, instance_id: int, user: User) -> ClassInstance:
    # Load the check eagerly: whether the class needs a reschedule depends on
    # it, and a lazy load is not allowed in async IO.
    original = await session.scalar(
        select(ClassInstance)
        .where(ClassInstance.id == instance_id)
        .options(selectinload(ClassInstance.check))
    )
    if original is None:
        raise NotFoundError(f"No class instance with id {instance_id}")

    if user.role is Role.TEACHER and original.teacher_initial != user.teacher_initial:
        raise ForbiddenError("You may only schedule makeups for your own classes.")

    # BR-09: a makeup recovers a missed class. Anything else has nothing to recover.
    if not needs_reschedule(original):
        raise ValidationError(
            "A makeup class can only be scheduled for a missed class, "
            "or one staff have reported the teacher absent from.",
            detail={"status": original.status.value if original.status else None},
        )
    return original


def needs_reschedule(instance: ClassInstance) -> bool:
    """Missed, or reported absent and still inside the missed threshold.

    The threshold exists so staff can correct a report if the teacher turns up
    late. It is not a reason to make a teacher who already knows they cannot
    come wait half an hour before asking for a new slot. Requesting one settles
    the question: the class leaves the unresolved set, so the sweep no longer
    touches it, and a rejection lands it on MISSED.
    """
    if instance.status is ClassStatus.MISSED:
        return True
    return (
        instance.status is None
        and instance.check is not None
        and instance.check.outcome is CheckOutcome.TEACHER_NOT_FOUND
    )


def _new_instance(
    *,
    original: ClassInstance,
    makeup: MakeupClass,
    semester_id: int,
) -> ClassInstance:
    """Build the monitoring instance a makeup produces.

    ``session_id`` is null: a makeup has no routine template behind it, which is
    also why the ``(session_id, date)`` unique key does not constrain it.
    """
    start_min, end_min = slot_bounds(makeup.time_slot)
    day = instance_service.day_name(makeup.date) or "Saturday"
    return ClassInstance(
        session_id=None,
        semester_id=semester_id,
        date=makeup.date,
        day=day,
        time_slot=makeup.time_slot,
        start_min=start_min,
        end_min=end_min,
        room=(makeup.room or "ONLINE").upper(),
        room_type="Online" if makeup.mode is MakeupMode.ONLINE else original.room_type,
        course_code=original.course_code,
        course_title=original.course_title,
        section=original.section,
        batch=original.batch,
        teacher_initial=original.teacher_initial,
        is_makeup=True,
        # An approved online class carries its status so the staff screen can
        # exclude it (BR-12). A physical one starts unresolved like any class.
        status=(
            ClassStatus.ONLINE_APPROVED if makeup.mode is MakeupMode.ONLINE else None
        ),
    )


async def _active_semester_id(session: AsyncSession, fallback: int) -> int:
    semester = await session.scalar(select(Semester).where(Semester.is_active))
    return semester.id if semester else fallback


def _require_future(on: Date, time_slot: str, now: datetime | None) -> None:
    """A reschedule into a slot that has already started can never be checked."""
    if time_slot not in SLOTS:
        return  # conflict_service reports the bad slot with its own message
    start_min, _end = slot_bounds(time_slot)
    if status_engine.slot_start_at(on, start_min) <= (now or status_engine.now_local()):
        raise ValidationError(
            "That time has already passed. Pick a slot later than now.",
            detail={"date": on.isoformat(), "time_slot": time_slot},
        )


async def create(
    session: AsyncSession,
    *,
    original_instance_id: int,
    user: User,
    mode: MakeupMode,
    on: Date,
    time_slot: str,
    room: str | None = None,
    reason: str | None = None,
    now: datetime | None = None,
) -> MakeupClass:
    """Request a reschedule for a missed class. Nothing is scheduled until approved."""
    original = await _load_original(session, original_instance_id, user)

    if mode is MakeupMode.PHYSICAL and not room:
        raise ValidationError("A physical makeup class needs a room.")
    if mode is MakeupMode.ONLINE:
        room = None
    _require_future(on, time_slot, now)

    semester_id = await _active_semester_id(session, original.semester_id)

    report = await conflict_service.check(
        session,
        on=on,
        time_slot=time_slot,
        teacher_initial=original.teacher_initial,
        room=room,
        section=original.section,
        semester_id=semester_id,
    )
    if not report.ok:
        # v1 blocks. ConflictReport.overridable is the seam for the
        # override-with-reason flow.
        raise ConflictError(
            "The proposed makeup slot conflicts with an existing class.",
            detail=report.as_dict(),
        )

    makeup = MakeupClass(
        original_instance_id=original.id,
        teacher_initial=original.teacher_initial,
        mode=mode,
        date=on,
        time_slot=time_slot,
        room=room.upper() if room else None,
        reason=reason,
        status=MakeupStatus.PENDING,
    )
    session.add(makeup)
    await session.flush()

    before = {"status": original.status.value if original.status else None}

    # BR-11: no instance yet -- an unapproved class is not scheduled, so staff
    # have nothing to check until the HoD says yes.
    original.status = (
        ClassStatus.MAKEUP_REQUESTED if mode is MakeupMode.PHYSICAL else ClassStatus.ONLINE_PENDING
    )
    await notification_service.notify_makeup_request(session, makeup, original)

    original.resolved_at = utcnow()

    audit_service.record(
        session,
        actor_id=user.id,
        entity_type="makeup_class",
        entity_id=makeup.id,
        action="makeup_created",
        before=before,
        after={
            "mode": mode.value,
            "status": makeup.status.value,
            "date": on.isoformat(),
            "time_slot": time_slot,
            "room": makeup.room,
            "original_status": original.status.value,
        },
        reason=reason,
    )
    await session.flush()
    return makeup


async def decide(
    session: AsyncSession,
    *,
    makeup_id: int,
    user: User,
    approve: bool,
    note: str | None = None,
    now: datetime | None = None,
) -> MakeupClass:
    """Approve or reject a reschedule request (BR-10, BR-11, BR-12)."""
    makeup = await session.get(MakeupClass, makeup_id)
    if makeup is None:
        raise NotFoundError(f"No makeup class with id {makeup_id}")
    if makeup.status is not MakeupStatus.PENDING:
        raise ValidationError(
            f"This request is already {makeup.status.value}.",
            detail={"status": makeup.status.value},
        )

    original = await session.get(ClassInstance, makeup.original_instance_id)
    if original is None:
        raise NotFoundError("The original class for this makeup no longer exists.")

    before = {
        "makeup_status": makeup.status.value,
        "original_status": original.status.value if original.status else None,
    }

    physical = makeup.mode is MakeupMode.PHYSICAL
    semester_id = await _active_semester_id(session, original.semester_id)

    if approve:
        _require_future(makeup.date, makeup.time_slot, now)
        # The cell was free when requested, but a class may have been placed in
        # it since. Re-check, ignoring this request's own claim on the room.
        report = await conflict_service.check(
            session,
            on=makeup.date,
            time_slot=makeup.time_slot,
            teacher_initial=makeup.teacher_initial,
            room=makeup.room,
            section=original.section,
            semester_id=semester_id,
            exclude_makeup_id=makeup.id,
        )
        if not report.ok:
            raise ConflictError(
                "The requested slot is no longer free. Reject it so the teacher can pick another.",
                detail=report.as_dict(),
            )

    if approve:
        makeup.status = MakeupStatus.SCHEDULED if physical else MakeupStatus.APPROVED
    else:
        makeup.status = MakeupStatus.REJECTED
    makeup.decided_by_id = user.id
    makeup.decision_note = note
    makeup.decided_at = utcnow()

    if approve:
        instance = _new_instance(original=original, makeup=makeup, semester_id=semester_id)
        instance.makeup_id = makeup.id
        session.add(instance)
        await session.flush()
        makeup.created_instance_id = instance.id
        # A physical instance starts unresolved, so it lands on the staff screen
        # for its floor at the new time (BR-10).
        original.status = ClassStatus.MAKEUP_SCHEDULED if physical else ClassStatus.ONLINE_APPROVED
    elif physical:
        # The class is still owed: back to MISSED so the teacher asks again.
        original.status = ClassStatus.MISSED
    else:
        original.status = ClassStatus.ONLINE_REJECTED

    original.resolved_at = utcnow()

    audit_service.record(
        session,
        actor_id=user.id,
        entity_type="makeup_class",
        entity_id=makeup.id,
        action="makeup_decided",
        before=before,
        after={
            "makeup_status": makeup.status.value,
            "original_status": original.status.value,
            "created_instance_id": makeup.created_instance_id,
        },
        reason=note,
    )
    await notification_service.notify_makeup_decision(session, makeup)
    await session.flush()
    return makeup


async def complete(
    session: AsyncSession, *, makeup_id: int, user: User
) -> MakeupClass:
    """Mark a makeup conducted, preserving the link to the original (BR-13)."""
    makeup = await session.get(MakeupClass, makeup_id)
    if makeup is None:
        raise NotFoundError(f"No makeup class with id {makeup_id}")
    if makeup.status in (MakeupStatus.PENDING, MakeupStatus.REJECTED):
        raise ValidationError(
            f"A {makeup.status.value.lower()} makeup class cannot be completed.",
            detail={"status": makeup.status.value},
        )

    before = {"makeup_status": makeup.status.value}
    makeup.status = MakeupStatus.COMPLETED

    original = await session.get(ClassInstance, makeup.original_instance_id)
    if original is not None:
        original.status = ClassStatus.MAKEUP_COMPLETED
        original.resolved_at = utcnow()

    if makeup.created_instance_id is not None:
        instance = await session.get(ClassInstance, makeup.created_instance_id)
        if instance is not None and instance.status is None:
            instance.status = ClassStatus.MAKEUP_COMPLETED
            instance.resolved_at = utcnow()

    audit_service.record(
        session,
        actor_id=user.id,
        entity_type="makeup_class",
        entity_id=makeup.id,
        action="makeup_completed",
        before=before,
        after={"makeup_status": MakeupStatus.COMPLETED.value},
    )
    await session.flush()
    return makeup

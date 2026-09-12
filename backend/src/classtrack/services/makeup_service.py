"""Makeup class workflow (BR-09 .. BR-13).

The two modes diverge in exactly one way, and it is the point of the whole
feature:

* **PHYSICAL** -- accepted straight away and a monitoring instance is created,
  so it enters room-wise staff checking like any other class (BR-10).
* **ONLINE** -- parked as PENDING until an HoD decides (BR-11). Only on approval
  is an instance created, and that instance is excluded from physical checking
  (BR-12).

Every makeup keeps a non-null reference to the missed class it recovers (BR-13),
so a report can always show Missed -> Makeup Scheduled -> Makeup Completed.
"""

from __future__ import annotations

import logging
from datetime import date as Date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from classtrack.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from classtrack.db.base import utcnow
from classtrack.models import (
    ClassInstance,
    ClassStatus,
    MakeupClass,
    MakeupMode,
    MakeupStatus,
    Role,
    Semester,
    User,
)
from classtrack.routine.lattice import slot_bounds
from classtrack.services import (
    audit_service,
    conflict_service,
    instance_service,
    notification_service,
)

logger = logging.getLogger(__name__)


async def _load_original(session: AsyncSession, instance_id: int, user: User) -> ClassInstance:
    original = await session.get(ClassInstance, instance_id)
    if original is None:
        raise NotFoundError(f"No class instance with id {instance_id}")

    if user.role is Role.TEACHER and original.teacher_initial != user.teacher_initial:
        raise ForbiddenError("You may only schedule makeups for your own classes.")

    # BR-09: a makeup recovers a missed class. Anything else has nothing to recover.
    if original.status is not ClassStatus.MISSED:
        raise ValidationError(
            "A makeup class can only be scheduled for a missed class.",
            detail={"status": original.status.value if original.status else None},
        )
    return original


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
) -> MakeupClass:
    """Schedule a makeup for a missed class."""
    original = await _load_original(session, original_instance_id, user)

    if mode is MakeupMode.PHYSICAL and not room:
        raise ValidationError("A physical makeup class needs a room.")
    if mode is MakeupMode.ONLINE:
        room = None

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
        status=MakeupStatus.SCHEDULED if mode is MakeupMode.PHYSICAL else MakeupStatus.PENDING,
    )
    session.add(makeup)
    await session.flush()

    before = {"status": original.status.value if original.status else None}

    if mode is MakeupMode.PHYSICAL:
        # BR-10: enters the normal room-wise checking list immediately.
        instance = _new_instance(original=original, makeup=makeup, semester_id=semester_id)
        instance.makeup_id = makeup.id
        session.add(instance)
        await session.flush()
        makeup.created_instance_id = instance.id
        original.status = ClassStatus.MAKEUP_SCHEDULED
    else:
        # BR-11: no instance yet -- an unapproved online class is not scheduled.
        original.status = ClassStatus.ONLINE_PENDING
        await notification_service.notify_online_request(session, makeup, original)

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
) -> MakeupClass:
    """Approve or reject an online makeup request (BR-11, BR-12)."""
    makeup = await session.get(MakeupClass, makeup_id)
    if makeup is None:
        raise NotFoundError(f"No makeup class with id {makeup_id}")
    if makeup.mode is not MakeupMode.ONLINE:
        raise ValidationError("Only an online makeup class needs approval.")
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

    makeup.status = MakeupStatus.APPROVED if approve else MakeupStatus.REJECTED
    makeup.decided_by_id = user.id
    makeup.decision_note = note
    makeup.decided_at = utcnow()

    if approve:
        semester_id = await _active_semester_id(session, original.semester_id)
        instance = _new_instance(original=original, makeup=makeup, semester_id=semester_id)
        instance.makeup_id = makeup.id
        session.add(instance)
        await session.flush()
        makeup.created_instance_id = instance.id
        original.status = ClassStatus.ONLINE_APPROVED
    else:
        original.status = ClassStatus.ONLINE_REJECTED

    original.resolved_at = utcnow()

    audit_service.record(
        session,
        actor_id=user.id,
        entity_type="makeup_class",
        entity_id=makeup.id,
        action="online_decided",
        before=before,
        after={
            "makeup_status": makeup.status.value,
            "original_status": original.status.value,
            "created_instance_id": makeup.created_instance_id,
        },
        reason=note,
    )
    await notification_service.notify_online_decision(session, makeup)
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

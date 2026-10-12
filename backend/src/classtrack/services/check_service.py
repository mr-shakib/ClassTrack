"""Staff monitoring submissions (BR-02, BR-03, BR-04).

One check per instance, upserted. That is what makes submission safe to retry
over a flaky mobile connection: a double tap cannot create two records.

Note what this module does *not* do. A ``TEACHER_NOT_FOUND`` observation does not
become ``MISSED`` here -- only the sweep may decide that, once the threshold has
elapsed (BR-05). Recording the observation and classifying the class are
deliberately separate steps.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import date as Date
from datetime import datetime, time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from classtrack.core.errors import ConflictError, NotFoundError, ValidationError
from classtrack.db.base import utcnow
from classtrack.models import (
    CheckOutcome,
    CheckRecord,
    ClassInstance,
    ClassStatus,
    Permission,
    User,
)
from classtrack.services import (
    audit_service,
    notification_service,
    status_engine,
)

logger = logging.getLogger(__name__)

#: An observation that immediately resolves the class, and what it resolves to.
#: TEACHER_NOT_FOUND is absent on purpose -- the sweep owns that decision.
_IMMEDIATE = {
    CheckOutcome.RUNNING: ClassStatus.RUNNING,
    CheckOutcome.LATE: ClassStatus.LATE,
}

#: Statuses a check may still amend. A cancelled or makeup-tracked class is not
#: something staff should be able to overwrite from the checking screen.
_AMENDABLE = frozenset({ClassStatus.RUNNING, ClassStatus.LATE, ClassStatus.MISSED})

#: Observations the teacher hears about the moment they are recorded.
_REPORTABLE = frozenset({CheckOutcome.TEACHER_NOT_FOUND, CheckOutcome.LATE})

#: An admin correcting the record after the fact may also reach a class that was
#: swept to NOT_CHECKED -- staff did check it, but never submitted in time.
_ADMIN_AMENDABLE = _AMENDABLE | {ClassStatus.NOT_CHECKED}


async def submit(
    session: AsyncSession,
    *,
    instance_id: int,
    user: User,
    outcome: CheckOutcome,
    arrival_time: time | None = None,
    remark: str | None = None,
    reason: str | None = None,
    now: datetime | None = None,
) -> ClassInstance:
    """Record a monitoring observation for one class instance.

    Staff may report any time from the class's start until the end of that day.
    A result typed in days later is not an observation, it is a recollection,
    and it could silently rewrite a teacher's record long after the fact.

    An admin or committee member may correct a record after that. A reason is
    optional; the change is audited as an override either way (source SRS 17:
    "manual overrides and reasons").
    """
    instance = await session.scalar(
        select(ClassInstance)
        .where(ClassInstance.id == instance_id)
        .options(selectinload(ClassInstance.check))
    )
    if instance is None:
        raise NotFoundError(f"No class instance with id {instance_id}")

    amendable = _ADMIN_AMENDABLE if user.can(Permission.CORRECT_CHECKS) else _AMENDABLE
    if instance.status is not None and instance.status not in amendable:
        raise ValidationError(
            f"This class is recorded as {instance.status.value} and cannot be checked.",
            detail={"status": instance.status.value},
        )

    if outcome is CheckOutcome.LATE and arrival_time is None:
        raise ValidationError("An arrival time is required when recording a late class.")

    now = now or status_engine.now_local()

    # --- reporting hours: from the class's start to the end of its day -------
    late_override = not status_engine.is_checkable(instance, now=now)

    if late_override and not user.can(Permission.CORRECT_CHECKS):
        opens = status_engine.slot_start_at(instance.date, instance.start_min)
        closes = status_engine.day_ends_at(instance.date)
        raise ConflictError(
            f"Reports for this class closed at the end of {instance.date:%d %B %Y}."
            if now >= closes
            else "This class has not started yet.",
            detail={
                "opened_at": opens.isoformat(),
                "closed_at": closes.isoformat(),
                "now": now.isoformat(),
            },
        )

    # BR-04: computed here, never taken from the client.
    late = (
        status_engine.late_minutes(instance.start_min, arrival_time)
        if outcome is CheckOutcome.LATE and arrival_time is not None
        else None
    )

    before = {
        "status": instance.status.value if instance.status else None,
        "outcome": instance.check.outcome.value if instance.check else None,
    }

    record = instance.check
    if record is None:
        record = CheckRecord(instance_id=instance.id, checked_at=now)
        session.add(record)
        instance.check = record

    record.checked_by_id = user.id
    record.outcome = outcome
    record.arrival_time = arrival_time
    record.late_minutes = late
    record.remark = remark
    record.checked_at = now

    resolved = _IMMEDIATE.get(outcome)
    if resolved is not None:
        instance.status = resolved
        instance.resolved_at = utcnow()
    else:
        # TEACHER_NOT_FOUND: leave unresolved. The sweep promotes it to MISSED
        # once the threshold passes, which is what keeps BR-05's "confirmed by
        # monitoring evidence" honest.
        instance.status = None
        instance.resolved_at = None

    audit_service.record(
        session,
        actor_id=user.id,
        entity_type="class_instance",
        entity_id=instance.id,
        # A correction made after reporting closed for the day is a different kind
        # of event from an observation made at the door, and the log should say so.
        action="check_overridden" if late_override else "check_submitted",
        before=before,
        after={
            "status": instance.status.value if instance.status else None,
            "outcome": outcome.value,
            "late_minutes": late,
            "outside_window": late_override,
        },
        reason=(reason or "").strip() or None,
    )

    # Tell the teacher straight away, but only when the observation is new: a
    # retried or re-saved submission must not ping them twice.
    if outcome in _REPORTABLE and before["outcome"] != outcome.value:
        await notification_service.notify_reported(session, instance, outcome)

    await session.flush()
    return instance


#: What a class marked conducted carries as its remark, so the record says how
#: it came to be held without anyone having seen it.
MARKED_REMARK = "Monitoring was off this day; recorded as held."


def _day_kind(instance: ClassInstance) -> str:
    """``unreported``, ``reported`` or ``other`` -- see ``MarkDayOut``."""
    if instance.status is ClassStatus.NOT_CHECKED or (
        instance.status is None and instance.check is None
    ):
        return "unreported"
    if instance.check is not None and (instance.status is None or instance.status in _AMENDABLE):
        return "reported"
    return "other"


async def _day(session: AsyncSession, on: Date) -> list[ClassInstance]:
    return list(
        (
            await session.scalars(
                select(ClassInstance)
                .where(ClassInstance.date == on)
                .options(selectinload(ClassInstance.check))
            )
        ).all()
    )


def _tally(instances: list[ClassInstance], on: Date, marked: int = 0) -> dict[str, object]:
    kinds = Counter(_day_kind(i) for i in instances)
    return {
        "date": on,
        "unreported": kinds["unreported"],
        "reported": kinds["reported"],
        "other": kinds["other"],
        "marked": marked,
    }


async def day_summary(session: AsyncSession, *, on: Date) -> dict[str, object]:
    """What marking ``on`` conducted would do, before anyone does it."""
    return _tally(await _day(session, on), on)


async def mark_day_conducted(
    session: AsyncSession,
    *,
    on: Date,
    user: User,
    reason: str | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    """Record every class of ``on`` that nobody reported as held.

    For a day monitoring was off -- staff away, or the department deciding not
    to check -- when the classes ran but nobody was there to say so. A class
    staff did report keeps that report: it was seen, and this was not. A
    cancelled, rescheduled or online class is not touched.

    Each class gets a RUNNING check by ``user``, as though they had reported
    it, and its own audit entry, so it can be corrected one by one afterwards.
    """
    now = now or status_engine.now_local()
    if on > now.date():
        raise ValidationError(
            "Pick today or an earlier day. A class cannot be recorded as held before its day."
        )
    why = (reason or "").strip() or None

    instances = await _day(session, on)
    marked = 0
    for instance in instances:
        if _day_kind(instance) != "unreported":
            continue
        before = {"status": instance.status.value if instance.status else None, "outcome": None}
        record = CheckRecord(
            instance_id=instance.id,
            checked_by_id=user.id,
            outcome=CheckOutcome.RUNNING,
            remark=MARKED_REMARK,
            checked_at=now,
        )
        session.add(record)
        instance.check = record
        instance.status = ClassStatus.RUNNING
        instance.resolved_at = utcnow()
        audit_service.record(
            session,
            actor_id=user.id,
            entity_type="class_instance",
            entity_id=instance.id,
            action="day_marked_conducted",
            before=before,
            after={"status": ClassStatus.RUNNING.value, "outcome": CheckOutcome.RUNNING.value},
            reason=why or f"Monitoring was off on {on:%d %B %Y}.",
        )
        marked += 1

    await session.flush()
    logger.info("%s marked %d classes of %s conducted", user.full_name, marked, on)
    return _tally(instances, on, marked)

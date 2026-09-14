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

    amendable = _ADMIN_AMENDABLE if user.can_override else _AMENDABLE
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

    if late_override and not user.can_override:
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

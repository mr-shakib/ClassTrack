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
from classtrack.services import audit_service, settings_service, status_engine

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

    Staff may only submit while the checking window is open. That is the point
    of the window: a result typed in days later is not an observation, it is a
    recollection, and it can silently rewrite a teacher's record long after the
    fact.

    An admin may correct a record outside the window, but must give a reason,
    and the override is audited as such (source SRS 17: "manual overrides and
    reasons").
    """
    instance = await session.scalar(
        select(ClassInstance)
        .where(ClassInstance.id == instance_id)
        .options(selectinload(ClassInstance.check))
    )
    if instance is None:
        raise NotFoundError(f"No class instance with id {instance_id}")

    amendable = _ADMIN_AMENDABLE if user.is_admin else _AMENDABLE
    if instance.status is not None and instance.status not in amendable:
        raise ValidationError(
            f"This class is recorded as {instance.status.value} and cannot be checked.",
            detail={"status": instance.status.value},
        )

    if outcome is CheckOutcome.LATE and arrival_time is None:
        raise ValidationError("An arrival time is required when recording a late class.")

    now = now or status_engine.now_local()

    # --- the checking window -------------------------------------------------
    window = await settings_service.check_window(session)
    late_override = not status_engine.is_checkable(instance, window, now=now)

    if late_override:
        opens = status_engine.slot_start_at(instance.date, instance.start_min)
        closes = status_engine.window_closes_at(instance, window)
        if not user.is_admin:
            raise ConflictError(
                "The checking window for this class is closed."
                if now > closes
                else "This class has not started yet.",
                detail={
                    "opened_at": opens.isoformat(),
                    "closed_at": closes.isoformat(),
                    "now": now.isoformat(),
                },
            )
        if not (reason or "").strip():
            raise ValidationError(
                "A reason is required to change a record outside the checking window.",
                detail={"closed_at": closes.isoformat()},
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
        # A correction made after the window closed is a different kind of event
        # from an observation made at the door, and the log should say so.
        action="check_overridden" if late_override else "check_submitted",
        before=before,
        after={
            "status": instance.status.value if instance.status else None,
            "outcome": outcome.value,
            "late_minutes": late,
            "outside_window": late_override,
        },
        reason=reason,
    )

    await session.flush()
    return instance

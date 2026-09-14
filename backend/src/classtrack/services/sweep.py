"""The status finaliser (BR-05, BR-06).

This is the correctness core of the system. It draws the one distinction the
whole SRS is built around:

* ``MISSED``      -- a staff member recorded TEACHER_NOT_FOUND *and* the
                     threshold elapsed. Positive evidence of teacher absence.
* ``NOT_CHECKED`` -- no monitoring input arrived before the window closed.
                     Absence of evidence. A staff failure, never a teacher's.

Collapsing these two would make every teacher report unfair, which is why the
source SRS calls the separation "essential for fair and reliable reporting".

Properties worth preserving:

* **Idempotent** -- selects only ``status IS NULL``, so a re-run is a no-op and
  a terminal status is never recomputed.
* **Crash-safe** -- decisions come from wall-clock time, not from the loop
  having run. A restart re-sweeps and reaches the same answer.
* **Testable** -- ``now`` is a parameter, so tests control the clock instead of
  sleeping.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from classtrack.db.base import utcnow
from classtrack.db.session import get_sessionmaker
from classtrack.models import CheckOutcome, ClassInstance, ClassStatus, MakeupClass, MakeupStatus
from classtrack.routine.lattice import SLOTS, slot_bounds
from classtrack.services import audit_service, notification_service, settings_service
from classtrack.services.status_engine import (
    day_ends_at,
    now_local,
    slot_end_at,
    slot_start_at,
)

logger = logging.getLogger(__name__)


async def sweep_once(session: AsyncSession, *, now: datetime | None = None) -> dict[str, int]:
    """Resolve every unresolved instance whose window has closed.

    Returns counts of what it changed, so the caller can log or assert on it.
    """
    now = now or now_local()
    threshold = await settings_service.missed_threshold(session)

    # Only unresolved rows, and only up to today -- a future date cannot have a
    # closed window, and scanning the whole semester every minute is waste.
    candidates = (
        await session.scalars(
            select(ClassInstance)
            .where(
                ClassInstance.status.is_(None),
                ClassInstance.date <= now.date(),
            )
            .options(selectinload(ClassInstance.check))
        )
    ).all()

    missed = 0
    not_checked = 0

    for instance in candidates:
        start = slot_start_at(instance.date, instance.start_min)
        check = instance.check

        if check is not None and check.outcome is CheckOutcome.TEACHER_NOT_FOUND:
            # BR-05: absence confirmed by monitoring evidence, threshold elapsed.
            if now < start + timedelta(minutes=threshold):
                continue
            new_status = ClassStatus.MISSED
        elif check is None:
            # BR-06: nobody reported the class all day. This is a staff failure
            # and must never be reported as teacher absence. Staff may report
            # until midnight, so nothing is concluded before then.
            if now < day_ends_at(instance.date):
                continue
            new_status = ClassStatus.NOT_CHECKED
        else:
            # RUNNING or LATE already wrote a terminal status, so such rows are
            # not selected here. Reaching this branch means an outcome exists
            # with no mapping -- skip rather than guess.
            continue

        instance.status = new_status
        instance.resolved_at = utcnow()

        audit_service.record(
            session,
            actor_id=None,  # the system decided, not a person
            entity_type="class_instance",
            entity_id=instance.id,
            action="status_finalised",
            before={"status": None},
            after={"status": new_status.value},
            reason=f"Sweep at {now.isoformat()}",
        )

        if new_status is ClassStatus.MISSED:
            missed += 1
            await notification_service.notify_missed(session, instance)  # BR-07
        else:
            not_checked += 1

    reminded = await _remind_unfinished_makeups(session, now)

    if missed or not_checked or reminded:
        await session.commit()
        logger.info(
            "Sweep: %d missed, %d not checked, %d makeup reminders",
            missed,
            not_checked,
            reminded,
        )

    return {
        "examined": len(candidates),
        "missed": missed,
        "not_checked": not_checked,
        "reminded": reminded,
    }


async def _remind_unfinished_makeups(session: AsyncSession, now: datetime) -> int:
    """Remind each teacher once when an approved makeup ends without being marked done."""
    due = (
        await session.scalars(
            select(MakeupClass).where(
                MakeupClass.status.in_((MakeupStatus.SCHEDULED, MakeupStatus.APPROVED)),
                MakeupClass.reminder_sent_at.is_(None),
                MakeupClass.date <= now.date(),
            )
        )
    ).all()

    reminded = 0
    for makeup in due:
        if makeup.time_slot not in SLOTS:
            continue
        _start, end_min = slot_bounds(makeup.time_slot)
        if now < slot_end_at(makeup.date, end_min):
            continue
        original = await session.get(ClassInstance, makeup.original_instance_id)
        if original is None:
            continue
        await notification_service.notify_makeup_due(session, makeup, original)
        makeup.reminder_sent_at = utcnow()
        reminded += 1
    return reminded


async def sweep_loop(interval_seconds: int) -> None:
    """Run the sweep forever. Started by the app lifespan."""
    # Let the app finish starting before the first pass.
    await asyncio.sleep(5)
    while True:
        try:
            async with get_sessionmaker()() as session:
                await sweep_once(session)
        except asyncio.CancelledError:
            raise
        except Exception:
            # A failed pass must not kill the loop: the next one re-derives
            # everything from the clock and will reach the same decisions.
            logger.exception("Sweep pass failed; continuing")
        await asyncio.sleep(interval_seconds)

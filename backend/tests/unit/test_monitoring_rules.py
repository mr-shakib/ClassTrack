"""The rules the whole system rests on (BR-03..BR-06).

These are the tests the implementation plan marks as never-cut. If any of them
fails, teacher reports are wrong in a way that matters to real people.
"""

from __future__ import annotations

from datetime import date, time

import pytest
from tests.conftest import at

from classtrack.models import CheckOutcome, ClassStatus
from classtrack.services import check_service, sweep

#: Midnight after the fixture class's day, when reporting closes.
NEXT_DAY = at(0, 0, day=date(2026, 9, 14))

# --- BR-06: no evidence is not absence -------------------------------------


async def test_no_check_becomes_not_checked_never_missed(session, instance):
    """The single most important test in the codebase.

    Staff failing to check must never be reported as the teacher being absent.
    """
    result = await sweep.sweep_once(session, now=NEXT_DAY)

    assert instance.status is ClassStatus.NOT_CHECKED
    assert instance.status is not ClassStatus.MISSED
    assert result["not_checked"] == 1
    assert result["missed"] == 0


async def test_no_check_during_the_day_stays_unresolved(session, instance):
    """Staff may still report until midnight, so nothing is concluded before then."""
    await sweep.sweep_once(session, now=at(23, 59))
    assert instance.status is None


# --- BR-05: missed requires positive evidence ------------------------------


async def test_teacher_not_found_before_threshold_stays_unresolved(session, instance, staff):
    """An observation is not yet a verdict.

    The teacher may still arrive at minute 29, so the class is not missed.
    """
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=staff,
        outcome=CheckOutcome.TEACHER_NOT_FOUND,
        now=at(10, 5),
    )
    assert instance.status is None

    await sweep.sweep_once(session, now=at(10, 29))
    assert instance.status is None


async def test_teacher_not_found_after_threshold_becomes_missed(session, instance, staff):
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=staff,
        outcome=CheckOutcome.TEACHER_NOT_FOUND,
        now=at(10, 5),
    )
    result = await sweep.sweep_once(session, now=at(10, 31))

    assert instance.status is ClassStatus.MISSED
    assert result["missed"] == 1
    assert result["not_checked"] == 0


async def test_missed_notifies_the_teacher(session, instance, staff, teacher_user):
    """BR-07: the teacher must learn about a missed-class record."""
    from sqlalchemy import select

    from classtrack.models import Notification, NotificationKind

    await check_service.submit(
        session,
        instance_id=instance.id,
        user=staff,
        outcome=CheckOutcome.TEACHER_NOT_FOUND,
        now=at(10, 5),
    )
    await sweep.sweep_once(session, now=at(10, 31))

    notes = (
        await session.scalars(
            select(Notification).where(Notification.user_id == teacher_user.id)
        )
    ).all()
    # The staff report warns them at once; the sweep's verdict follows.
    assert [n.kind for n in notes] == [
        NotificationKind.CLASS_REPORTED,
        NotificationKind.MISSED_CLASS,
    ]
    assert "CSE311" in notes[0].body


# --- BR-03, BR-04: late arrival -------------------------------------------


async def test_late_minutes_computed_from_arrival(session, instance, staff):
    """A 10:00 class with a 10:08 arrival is late by 8 minutes."""
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=staff,
        outcome=CheckOutcome.LATE,
        arrival_time=time(10, 8),
        now=at(10, 8),
    )

    assert instance.status is ClassStatus.LATE
    assert instance.check.late_minutes == 8


async def test_late_requires_an_arrival_time(session, instance, staff):
    from classtrack.core.errors import ValidationError

    with pytest.raises(ValidationError, match="arrival time"):
        await check_service.submit(
            session,
            instance_id=instance.id,
            user=staff,
            outcome=CheckOutcome.LATE,
            now=at(10, 8),
        )


async def test_client_supplied_late_minutes_are_ignored(session, instance, staff):
    """BR-04 is computed server-side. The API exposes no way to set it."""
    import inspect

    params = inspect.signature(check_service.submit).parameters
    assert "late_minutes" not in params


# --- the sweep must not touch resolved classes ----------------------------


async def test_sweep_leaves_running_alone(session, instance, staff):
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=staff,
        outcome=CheckOutcome.RUNNING,
        now=at(10, 2),
    )
    await sweep.sweep_once(session, now=at(23, 0))
    assert instance.status is ClassStatus.RUNNING


async def test_sweep_leaves_late_alone(session, instance, staff):
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=staff,
        outcome=CheckOutcome.LATE,
        arrival_time=time(10, 12),
        now=at(10, 12),
    )
    await sweep.sweep_once(session, now=at(23, 0))
    assert instance.status is ClassStatus.LATE
    assert instance.check.late_minutes == 12


async def test_sweep_is_idempotent(session, instance, staff):
    """Re-running must be a no-op, so a restart cannot double-report."""
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=staff,
        outcome=CheckOutcome.TEACHER_NOT_FOUND,
        now=at(10, 5),
    )
    first = await sweep.sweep_once(session, now=at(10, 31))
    second = await sweep.sweep_once(session, now=at(10, 45))

    assert first["missed"] == 1
    assert second["missed"] == 0
    assert instance.status is ClassStatus.MISSED


# --- one check per instance -----------------------------------------------


async def test_double_submit_creates_one_record(session, instance, staff):
    """A double tap or a retry on a flaky connection must not duplicate."""
    from sqlalchemy import func, select

    from classtrack.models import CheckRecord

    for _ in range(3):
        await check_service.submit(
            session,
            instance_id=instance.id,
            user=staff,
            outcome=CheckOutcome.RUNNING,
            now=at(10, 3),
        )

    count = await session.scalar(
        select(func.count(CheckRecord.id)).where(CheckRecord.instance_id == instance.id)
    )
    assert count == 1


async def test_amending_a_check_updates_the_status(session, instance, staff):
    """Staff correcting themselves: Running, then actually Late."""
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=staff,
        outcome=CheckOutcome.RUNNING,
        now=at(10, 3),
    )
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=staff,
        outcome=CheckOutcome.LATE,
        arrival_time=time(10, 9),
        now=at(10, 10),
    )
    assert instance.status is ClassStatus.LATE
    assert instance.check.late_minutes == 9


# --- audit trail -----------------------------------------------------------


async def test_status_changes_are_audited(session, instance, staff):
    """BR-15, and the sweep records that the *system* acted, not a person."""
    from sqlalchemy import select

    from classtrack.models import AuditLog

    await check_service.submit(
        session,
        instance_id=instance.id,
        user=staff,
        outcome=CheckOutcome.TEACHER_NOT_FOUND,
        now=at(10, 5),
    )
    await sweep.sweep_once(session, now=at(10, 31))

    logs = (
        await session.scalars(
            select(AuditLog)
            .where(AuditLog.entity_id == instance.id)
            .order_by(AuditLog.id)
        )
    ).all()
    actions = [entry.action for entry in logs]
    assert actions == ["check_submitted", "status_finalised"]
    assert logs[0].actor_id == staff.id
    assert logs[1].actor_id is None  # the sweep has no user behind it
    assert logs[1].after == {"status": "MISSED"}

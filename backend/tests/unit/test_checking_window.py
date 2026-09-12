"""The checking window (BR-06).

A result typed in days later is not an observation, it is a recollection. The
window is what makes a monitoring record mean "someone stood at that door at
that time", and without it a staff member could quietly rewrite a teacher's
record weeks after the fact.

Admins may still correct a record afterwards -- staff make mistakes, and the
source SRS allows a manual override -- but it costs a mandatory reason and is
logged as an override rather than an observation.
"""

from __future__ import annotations

from datetime import time

import pytest
from tests.conftest import at

from classtrack.core.errors import ConflictError, ValidationError
from classtrack.models import CheckOutcome, ClassStatus
from classtrack.services import check_service, sweep

# The fixture class runs 10:00-11:30; the default window closes at 10:30.


# --- staff are bounded by the window ---------------------------------------


async def test_staff_can_check_inside_the_window(session, instance, staff):
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=staff,
        outcome=CheckOutcome.RUNNING,
        now=at(10, 15),
    )
    assert instance.status is ClassStatus.RUNNING


async def test_staff_can_check_at_the_exact_boundaries(session, instance, staff):
    """Start and close are inclusive -- arriving dead on time must work."""
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=staff,
        outcome=CheckOutcome.RUNNING,
        now=at(10, 0),
    )
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=staff,
        outcome=CheckOutcome.LATE,
        arrival_time=time(10, 20),
        now=at(10, 30),
    )
    assert instance.status is ClassStatus.LATE


async def test_staff_cannot_check_after_the_window_closes(session, instance, staff):
    with pytest.raises(ConflictError, match="closed"):
        await check_service.submit(
            session,
            instance_id=instance.id,
            user=staff,
            outcome=CheckOutcome.RUNNING,
            now=at(10, 31),
        )
    assert instance.status is None


async def test_staff_cannot_check_days_later(session, instance, staff):
    """The case that motivated this: rewriting an old record."""
    with pytest.raises(ConflictError):
        await check_service.submit(
            session,
            instance_id=instance.id,
            user=staff,
            outcome=CheckOutcome.TEACHER_NOT_FOUND,
            now=at(10, 0, day=__import__("datetime").date(2026, 9, 24)),
        )


async def test_staff_cannot_check_before_the_class_starts(session, instance, staff):
    with pytest.raises(ConflictError, match="not started"):
        await check_service.submit(
            session,
            instance_id=instance.id,
            user=staff,
            outcome=CheckOutcome.RUNNING,
            now=at(9, 30),
        )


async def test_staff_cannot_rewrite_a_resolved_record_later(session, instance, staff):
    """A RUNNING record from an earlier day stays put."""
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=staff,
        outcome=CheckOutcome.RUNNING,
        now=at(10, 5),
    )
    assert instance.status is ClassStatus.RUNNING

    with pytest.raises(ConflictError):
        await check_service.submit(
            session,
            instance_id=instance.id,
            user=staff,
            outcome=CheckOutcome.TEACHER_NOT_FOUND,
            now=at(14, 0),
        )
    assert instance.status is ClassStatus.RUNNING


# --- admins may correct, at a price ----------------------------------------


async def test_admin_override_requires_a_reason(session, instance, hod):
    with pytest.raises(ValidationError, match="reason is required"):
        await check_service.submit(
            session,
            instance_id=instance.id,
            user=hod,
            outcome=CheckOutcome.RUNNING,
            now=at(10, 31),
        )


async def test_admin_can_correct_with_a_reason(session, instance, hod):
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=hod,
        outcome=CheckOutcome.RUNNING,
        reason="Staff checked on paper; entered after the window",
        now=at(15, 0),
    )
    assert instance.status is ClassStatus.RUNNING


async def test_admin_override_is_logged_as_an_override(session, instance, hod):
    from sqlalchemy import select

    from classtrack.models import AuditLog

    await check_service.submit(
        session,
        instance_id=instance.id,
        user=hod,
        outcome=CheckOutcome.RUNNING,
        reason="Entered late from the paper log",
        now=at(15, 0),
    )
    entry = await session.scalar(
        select(AuditLog).where(AuditLog.entity_id == instance.id)
    )
    assert entry.action == "check_overridden"
    assert entry.after["outside_window"] is True
    assert entry.reason == "Entered late from the paper log"


async def test_inside_the_window_is_not_logged_as_an_override(session, instance, staff):
    from sqlalchemy import select

    from classtrack.models import AuditLog

    await check_service.submit(
        session,
        instance_id=instance.id,
        user=staff,
        outcome=CheckOutcome.RUNNING,
        now=at(10, 10),
    )
    entry = await session.scalar(
        select(AuditLog).where(AuditLog.entity_id == instance.id)
    )
    assert entry.action == "check_submitted"
    assert entry.after["outside_window"] is False


async def test_admin_can_correct_a_not_checked_class(session, instance, hod):
    """Staff did check it but never submitted -- the record should be fixable."""
    await sweep.sweep_once(session, now=at(10, 31))
    assert instance.status is ClassStatus.NOT_CHECKED

    await check_service.submit(
        session,
        instance_id=instance.id,
        user=hod,
        outcome=CheckOutcome.RUNNING,
        reason="Staff confirmed verbally; submission failed on the day",
        now=at(16, 0),
    )
    assert instance.status is ClassStatus.RUNNING


async def test_staff_still_cannot_touch_a_not_checked_class(session, instance, staff):
    await sweep.sweep_once(session, now=at(10, 31))
    assert instance.status is ClassStatus.NOT_CHECKED

    with pytest.raises((ConflictError, ValidationError)):
        await check_service.submit(
            session,
            instance_id=instance.id,
            user=staff,
            outcome=CheckOutcome.RUNNING,
            now=at(16, 0),
        )
    assert instance.status is ClassStatus.NOT_CHECKED

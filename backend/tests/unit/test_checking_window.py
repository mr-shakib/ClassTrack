"""Reporting hours (BR-06).

Staff may report a class any time from its start until the end of that day:
walking the floors takes time, and a class seen at 10:05 may be entered at 14:00.
What they cannot do is report it on a later day -- a result typed in days later
is not an observation, it is a recollection, and it could silently rewrite a
teacher's record long after the fact.

After the day, an admin or committee member may still correct a record. A reason
is optional; the change is logged as an override either way.
"""

from __future__ import annotations

from datetime import date, time

import pytest
from sqlalchemy import select
from tests.conftest import at

from classtrack.core.errors import ConflictError, ValidationError
from classtrack.models import AuditLog, CheckOutcome, ClassStatus
from classtrack.services import check_service, sweep

# The fixture class runs 10:00-11:30 on 13 September 2026.
NEXT_DAY = date(2026, 9, 14)


async def _override_entry(session, instance):
    return await session.scalar(
        select(AuditLog).where(
            AuditLog.entity_id == instance.id, AuditLog.action == "check_overridden"
        )
    )


# --- staff may report all day ----------------------------------------------


async def test_staff_can_check_once_the_class_has_started(session, instance, staff):
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=staff,
        outcome=CheckOutcome.RUNNING,
        now=at(10, 0),
    )
    assert instance.status is ClassStatus.RUNNING


async def test_staff_can_report_hours_later_the_same_day(session, instance, staff):
    """There is no 30-minute window any more: a morning class can be entered at night."""
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=staff,
        outcome=CheckOutcome.LATE,
        arrival_time=time(10, 20),
        now=at(23, 59),
    )
    assert instance.status is ClassStatus.LATE
    assert instance.check.late_minutes == 20

    entry = await session.scalar(select(AuditLog).where(AuditLog.entity_id == instance.id))
    assert entry.action == "check_submitted"
    assert entry.after["outside_window"] is False


async def test_staff_can_correct_their_own_report_later_the_same_day(session, instance, staff):
    """Reported absent, swept to MISSED, then the teacher turns up after all."""
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=staff,
        outcome=CheckOutcome.TEACHER_NOT_FOUND,
        now=at(10, 5),
    )
    await sweep.sweep_once(session, now=at(10, 31))
    assert instance.status is ClassStatus.MISSED

    await check_service.submit(
        session,
        instance_id=instance.id,
        user=staff,
        outcome=CheckOutcome.LATE,
        arrival_time=time(10, 40),
        now=at(14, 0),
    )
    assert instance.status is ClassStatus.LATE


async def test_staff_cannot_check_before_the_class_starts(session, instance, staff):
    with pytest.raises(ConflictError, match="not started"):
        await check_service.submit(
            session,
            instance_id=instance.id,
            user=staff,
            outcome=CheckOutcome.RUNNING,
            now=at(9, 30),
        )


async def test_staff_cannot_report_on_a_later_day(session, instance, staff):
    with pytest.raises(ConflictError, match="closed at the end of 13 September 2026"):
        await check_service.submit(
            session,
            instance_id=instance.id,
            user=staff,
            outcome=CheckOutcome.RUNNING,
            now=at(0, 0, day=NEXT_DAY),
        )
    assert instance.status is None


async def test_staff_cannot_rewrite_a_record_days_later(session, instance, staff):
    """The case that motivated the limit: rewriting an old record."""
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=staff,
        outcome=CheckOutcome.RUNNING,
        now=at(10, 5),
    )
    with pytest.raises(ConflictError):
        await check_service.submit(
            session,
            instance_id=instance.id,
            user=staff,
            outcome=CheckOutcome.TEACHER_NOT_FOUND,
            now=at(10, 0, day=date(2026, 9, 24)),
        )
    assert instance.status is ClassStatus.RUNNING


async def test_an_unreported_class_is_not_checked_only_once_the_day_ends(session, instance):
    await sweep.sweep_once(session, now=at(23, 59))
    assert instance.status is None

    await sweep.sweep_once(session, now=at(0, 0, day=NEXT_DAY))
    assert instance.status is ClassStatus.NOT_CHECKED


async def test_staff_cannot_touch_a_not_checked_class(session, instance, staff):
    await sweep.sweep_once(session, now=at(0, 0, day=NEXT_DAY))
    assert instance.status is ClassStatus.NOT_CHECKED

    with pytest.raises((ConflictError, ValidationError)):
        await check_service.submit(
            session,
            instance_id=instance.id,
            user=staff,
            outcome=CheckOutcome.RUNNING,
            now=at(9, 0, day=NEXT_DAY),
        )
    assert instance.status is ClassStatus.NOT_CHECKED


# --- overrides: no reason needed, still audited ------------------------------


async def test_admin_can_override_without_a_reason(session, instance, hod):
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=hod,
        outcome=CheckOutcome.RUNNING,
        now=at(9, 0, day=NEXT_DAY),
    )
    assert instance.status is ClassStatus.RUNNING

    entry = await _override_entry(session, instance)
    assert entry.actor_id == hod.id
    assert entry.after["outside_window"] is True
    assert entry.reason is None


async def test_an_override_keeps_a_reason_when_one_is_given(session, instance, hod):
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=hod,
        outcome=CheckOutcome.RUNNING,
        reason="  Entered late from the paper log ",
        now=at(9, 0, day=NEXT_DAY),
    )
    entry = await _override_entry(session, instance)
    assert entry.reason == "Entered late from the paper log"


async def test_a_blank_reason_is_stored_as_none(session, instance, hod):
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=hod,
        outcome=CheckOutcome.RUNNING,
        reason="   ",
        now=at(9, 0, day=NEXT_DAY),
    )
    entry = await _override_entry(session, instance)
    assert entry.reason is None


async def test_admin_can_correct_a_not_checked_class(session, instance, hod):
    """Staff did check it but never submitted -- the record should be fixable."""
    await sweep.sweep_once(session, now=at(0, 0, day=NEXT_DAY))
    assert instance.status is ClassStatus.NOT_CHECKED

    await check_service.submit(
        session,
        instance_id=instance.id,
        user=hod,
        outcome=CheckOutcome.RUNNING,
        now=at(9, 0, day=NEXT_DAY),
    )
    assert instance.status is ClassStatus.RUNNING


async def test_associate_head_can_override_without_a_reason(session, instance, associate_head):
    """An Associate Head holds every HoD permission, overrides included."""
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=associate_head,
        outcome=CheckOutcome.RUNNING,
        now=at(9, 0, day=NEXT_DAY),
    )
    assert instance.status is ClassStatus.RUNNING


# --- the committee may override a report, and nothing more ------------------


async def test_committee_can_override_a_report_without_a_reason(
    session, instance, staff, committee
):
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=staff,
        outcome=CheckOutcome.TEACHER_NOT_FOUND,
        now=at(10, 10),
    )
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=committee,
        outcome=CheckOutcome.RUNNING,
        now=at(9, 0, day=NEXT_DAY),
    )
    assert instance.status is ClassStatus.RUNNING

    entry = await _override_entry(session, instance)
    assert entry.actor_id == committee.id
    assert entry.before["outcome"] == CheckOutcome.TEACHER_NOT_FOUND.value
    assert entry.reason is None


async def test_committee_can_correct_a_not_checked_class(session, instance, committee):
    await sweep.sweep_once(session, now=at(0, 0, day=NEXT_DAY))
    assert instance.status is ClassStatus.NOT_CHECKED

    await check_service.submit(
        session,
        instance_id=instance.id,
        user=committee,
        outcome=CheckOutcome.RUNNING,
        now=at(9, 0, day=NEXT_DAY),
    )
    assert instance.status is ClassStatus.RUNNING


async def test_committee_is_not_an_admin(committee, associate_head):
    """Overriding a report does not open the dashboard, approvals or admin."""
    from classtrack.api.deps import require_role
    from classtrack.core.errors import ForbiddenError
    from classtrack.models import ADMIN_ROLES, CHECKING_ROLES

    assert committee.can_override and not committee.is_admin
    await require_role(*CHECKING_ROLES)(committee)
    with pytest.raises(ForbiddenError):
        await require_role(*ADMIN_ROLES)(committee)

    assert associate_head.is_admin
    await require_role(*ADMIN_ROLES)(associate_head)

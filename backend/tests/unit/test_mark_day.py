"""Marking a day conducted, for a day monitoring was off: every class nobody
reported is recorded as held, and nothing anyone did report is touched."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import func, select
from tests.conftest import at

from classtrack.api.deps import require
from classtrack.core.errors import ForbiddenError, ValidationError
from classtrack.models import (
    AuditLog,
    CheckOutcome,
    ClassInstance,
    ClassStatus,
    Permission,
)
from classtrack.services import check_service, sweep

EVENING = at(23, 0)


def _class(instance, room: str, status: ClassStatus | None = None) -> ClassInstance:
    """Another class on the same day as ``instance``."""
    return ClassInstance(
        session_id=None,
        semester_id=instance.semester_id,
        date=instance.date,
        day=instance.day,
        time_slot=instance.time_slot,
        start_min=instance.start_min,
        end_min=instance.end_min,
        room=room,
        course_code=f"CSE{room[-3:]}(70_B)",
        section="70_B",
        batch="70_B",
        teacher_initial=f"T{room[-2:]}",
        status=status,
    )


async def _report(session, instance, staff, outcome, **extra):
    await check_service.submit(
        session, instance_id=instance.id, user=staff, outcome=outcome, now=at(10, 5), **extra
    )


async def test_only_the_classes_nobody_reported_are_marked(session, instance, staff, coordinator):
    swept = _class(instance, "KT-401")  # unreported, and swept to NOT_CHECKED
    running = _class(instance, "KT-402")
    late = _class(instance, "KT-403")
    absent = _class(instance, "KT-404")
    cancelled = _class(instance, "KT-405", ClassStatus.CANCELLED)
    rescheduled = _class(instance, "KT-406", ClassStatus.MAKEUP_SCHEDULED)
    session.add_all([swept, running, late, absent, cancelled, rescheduled])
    await session.flush()
    await _report(session, running, staff, CheckOutcome.RUNNING)
    await _report(session, late, staff, CheckOutcome.LATE, arrival_time=at(10, 20).time())
    await _report(session, absent, staff, CheckOutcome.TEACHER_NOT_FOUND)
    await sweep.sweep_once(session, now=at(0, 1, day=instance.date + timedelta(days=1)))
    assert swept.status is ClassStatus.NOT_CHECKED and absent.status is ClassStatus.MISSED

    preview = await check_service.day_summary(session, on=instance.date)
    # ``instance`` itself was never reported either.
    assert (preview["unreported"], preview["reported"], preview["other"]) == (2, 3, 2)

    done = await check_service.mark_day_conducted(
        session, on=instance.date, user=coordinator, reason="Staff on leave", now=EVENING
    )
    assert done["marked"] == 2 and done["unreported"] == 0

    for marked in (instance, swept):
        assert marked.status is ClassStatus.RUNNING
        assert marked.check.outcome is CheckOutcome.RUNNING
        assert marked.check.checked_by_id == coordinator.id
        assert marked.check.remark == check_service.MARKED_REMARK
    assert running.check.checked_by_id == staff.id
    assert late.status is ClassStatus.LATE and absent.status is ClassStatus.MISSED
    assert cancelled.status is ClassStatus.CANCELLED
    assert rescheduled.status is ClassStatus.MAKEUP_SCHEDULED

    audited = await session.scalar(
        select(func.count(AuditLog.id)).where(
            AuditLog.action == "day_marked_conducted", AuditLog.reason == "Staff on leave"
        )
    )
    assert audited == 2


async def test_marking_twice_marks_nothing_more(session, instance, hod):
    first = await check_service.mark_day_conducted(session, on=instance.date, user=hod, now=EVENING)
    again = await check_service.mark_day_conducted(session, on=instance.date, user=hod, now=EVENING)
    assert (first["marked"], again["marked"]) == (1, 0)


async def test_today_may_be_marked_but_not_a_day_to_come(session, instance, hod):
    # Before the class has even started: monitoring is off today.
    await check_service.mark_day_conducted(session, on=instance.date, user=hod, now=at(8, 0))
    assert instance.status is ClassStatus.RUNNING

    with pytest.raises(ValidationError, match="today or an earlier day"):
        await check_service.mark_day_conducted(
            session, on=instance.date + timedelta(days=1), user=hod, now=at(8, 0)
        )


async def _allowed(user) -> bool:
    try:
        await require(Permission.MARK_DAY_CONDUCTED)(user)
    except ForbiddenError:
        return False
    return True


async def test_admins_and_the_coordination_officer_may_mark_a_day(
    hod, associate_head, coordinator, committee, staff, teacher_user
):
    assert [await _allowed(u) for u in (hod, associate_head, coordinator)] == [True] * 3
    assert [await _allowed(u) for u in (committee, staff, teacher_user)] == [False] * 3

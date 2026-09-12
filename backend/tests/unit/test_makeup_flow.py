"""The makeup workflow (BR-09 .. BR-14), and the online/physical distinction.

AC-08 is the criterion most easily broken by a later change to the staff query,
so it is asserted here rather than only checked by hand.
"""

from __future__ import annotations

from datetime import date

import pytest
from tests.conftest import at

from classtrack.core.errors import ConflictError, ValidationError
from classtrack.models import (
    CheckOutcome,
    ClassStatus,
    MakeupMode,
    MakeupStatus,
    Role,
    User,
)
from classtrack.services import (
    check_service,
    checking_service,
    makeup_service,
    sweep,
)


async def _make_missed(session, instance, staff):
    """Drive an instance to MISSED through the real services."""
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=staff,
        outcome=CheckOutcome.TEACHER_NOT_FOUND,
        now=at(10, 5),
    )
    await sweep.sweep_once(session, now=at(10, 31))
    assert instance.status is ClassStatus.MISSED
    return instance


LATER = date(2026, 9, 20)
FREE_SLOT = "04:00-05:30"


# --- BR-09: only a missed class can be made up -----------------------------


async def test_makeup_requires_a_missed_class(session, instance, teacher_user):
    with pytest.raises(ValidationError, match="missed class"):
        await makeup_service.create(
            session,
            original_instance_id=instance.id,
            user=teacher_user,
            mode=MakeupMode.PHYSICAL,
            on=LATER,
            time_slot=FREE_SLOT,
            room="KT-305",
        )


# --- BR-10: a physical makeup enters room-wise checking --------------------


async def test_physical_makeup_enters_checking(session, instance, staff, teacher_user):
    await _make_missed(session, instance, staff)

    makeup = await makeup_service.create(
        session,
        original_instance_id=instance.id,
        user=teacher_user,
        mode=MakeupMode.PHYSICAL,
        on=LATER,
        time_slot=FREE_SLOT,
        room="KT-305",
        reason="Was on official duty",
    )
    await session.commit()

    assert makeup.status is MakeupStatus.SCHEDULED
    assert instance.status is ClassStatus.MAKEUP_SCHEDULED
    assert makeup.created_instance_id is not None

    screen = await checking_service.checking_screen(session, on=LATER, slot=FREE_SLOT)
    ids = [r["instance_id"] for r in screen["rooms"]]
    assert makeup.created_instance_id in ids

    row = next(r for r in screen["rooms"] if r["instance_id"] == makeup.created_instance_id)
    assert row["is_makeup"] is True
    assert row["course_code"] == instance.course_code


# --- BR-11, BR-12, AC-08: online needs approval and is never checked -------


async def test_online_makeup_starts_pending(session, instance, staff, teacher_user):
    await _make_missed(session, instance, staff)

    makeup = await makeup_service.create(
        session,
        original_instance_id=instance.id,
        user=teacher_user,
        mode=MakeupMode.ONLINE,
        on=LATER,
        time_slot=FREE_SLOT,
        reason="Travelling",
    )
    await session.commit()

    assert makeup.status is MakeupStatus.PENDING
    assert instance.status is ClassStatus.ONLINE_PENDING
    # No instance exists yet: an unapproved online class is not scheduled.
    assert makeup.created_instance_id is None

    screen = await checking_service.checking_screen(session, on=LATER, slot=FREE_SLOT)
    assert screen["rooms"] == []


async def test_approved_online_makeup_is_excluded_from_checking(
    session, instance, staff, teacher_user
):
    """AC-08. The single most regression-prone assertion in the system."""
    await _make_missed(session, instance, staff)

    hod = User(
        email="hod@test.edu", password_hash="x", full_name="HoD", role=Role.HOD
    )
    session.add(hod)
    await session.flush()

    makeup = await makeup_service.create(
        session,
        original_instance_id=instance.id,
        user=teacher_user,
        mode=MakeupMode.ONLINE,
        on=LATER,
        time_slot=FREE_SLOT,
    )
    await session.commit()

    decided = await makeup_service.decide(
        session, makeup_id=makeup.id, user=hod, approve=True, note="Fine this once"
    )
    await session.commit()

    assert decided.status is MakeupStatus.APPROVED
    assert instance.status is ClassStatus.ONLINE_APPROVED
    assert decided.created_instance_id is not None

    screen = await checking_service.checking_screen(session, on=LATER, slot=FREE_SLOT)
    ids = [r["instance_id"] for r in screen["rooms"]]
    assert decided.created_instance_id not in ids, (
        "An approved online makeup must never appear in physical room checking"
    )


async def test_rejected_online_makeup_creates_no_instance(
    session, instance, staff, teacher_user
):
    await _make_missed(session, instance, staff)
    hod = User(email="h2@test.edu", password_hash="x", full_name="HoD", role=Role.HOD)
    session.add(hod)
    await session.flush()

    makeup = await makeup_service.create(
        session,
        original_instance_id=instance.id,
        user=teacher_user,
        mode=MakeupMode.ONLINE,
        on=LATER,
        time_slot=FREE_SLOT,
    )
    await session.commit()

    decided = await makeup_service.decide(
        session, makeup_id=makeup.id, user=hod, approve=False, note="Please hold it in person"
    )
    await session.commit()

    assert decided.status is MakeupStatus.REJECTED
    assert instance.status is ClassStatus.ONLINE_REJECTED
    assert decided.created_instance_id is None


# --- BR-13: the link to the original survives ------------------------------


async def test_makeup_keeps_its_link_to_the_original(session, instance, staff, teacher_user):
    await _make_missed(session, instance, staff)
    original_id = instance.id

    makeup = await makeup_service.create(
        session,
        original_instance_id=original_id,
        user=teacher_user,
        mode=MakeupMode.PHYSICAL,
        on=LATER,
        time_slot=FREE_SLOT,
        room="KT-305",
    )
    await session.commit()

    completed = await makeup_service.complete(session, makeup_id=makeup.id, user=teacher_user)
    await session.commit()

    assert completed.original_instance_id == original_id
    assert completed.status is MakeupStatus.COMPLETED
    # Missed -> Makeup Scheduled -> Makeup Completed
    assert instance.status is ClassStatus.MAKEUP_COMPLETED


# --- BR-14: conflict detection --------------------------------------------


async def test_room_conflict_blocks_a_makeup(session, instance, staff, teacher_user):
    """The original class still occupies its own cell, so re-using it conflicts."""
    await _make_missed(session, instance, staff)

    # Build a second instance occupying the target cell.
    from classtrack.models import ClassInstance

    occupied = ClassInstance(
        session_id=None,
        semester_id=instance.semester_id,
        date=LATER,
        day="Sunday",
        time_slot=FREE_SLOT,
        start_min=960,
        end_min=1050,
        room="KT-305",
        course_code="CSE999(70_Z)",
        section="70_Z",
        batch="70_Z",
        teacher_initial="ZZZ",
        status=None,
    )
    session.add(occupied)
    await session.flush()

    with pytest.raises(ConflictError) as exc:
        await makeup_service.create(
            session,
            original_instance_id=instance.id,
            user=teacher_user,
            mode=MakeupMode.PHYSICAL,
            on=LATER,
            time_slot=FREE_SLOT,
            room="KT-305",
        )
    types = {c["type"] for c in exc.value.detail["conflicts"]}
    assert "ROOM" in types


async def test_teacher_conflict_blocks_a_makeup(session, instance, staff, teacher_user):
    await _make_missed(session, instance, staff)
    from classtrack.models import ClassInstance

    session.add(
        ClassInstance(
            session_id=None,
            semester_id=instance.semester_id,
            date=LATER,
            day="Sunday",
            time_slot=FREE_SLOT,
            start_min=960,
            end_min=1050,
            room="KT-999",
            course_code="CSE888(68_A)",
            section="68_A",
            batch="68_A",
            teacher_initial="TCA",  # same teacher
            status=None,
        )
    )
    await session.flush()

    with pytest.raises(ConflictError) as exc:
        await makeup_service.create(
            session,
            original_instance_id=instance.id,
            user=teacher_user,
            mode=MakeupMode.PHYSICAL,
            on=LATER,
            time_slot=FREE_SLOT,
            room="KT-305",
        )
    types = {c["type"] for c in exc.value.detail["conflicts"]}
    assert "TEACHER" in types


async def test_holiday_blocks_a_makeup(session, instance, staff, teacher_user):
    await _make_missed(session, instance, staff)
    from classtrack.models import DayKind, Holiday

    session.add(
        Holiday(
            semester_id=instance.semester_id,
            date=LATER,
            title="Victory Day",
            kind=DayKind.HOLIDAY,
        )
    )
    await session.flush()

    with pytest.raises(ConflictError) as exc:
        await makeup_service.create(
            session,
            original_instance_id=instance.id,
            user=teacher_user,
            mode=MakeupMode.PHYSICAL,
            on=LATER,
            time_slot=FREE_SLOT,
            room="KT-305",
        )
    types = {c["type"] for c in exc.value.detail["conflicts"]}
    assert "HOLIDAY" in types


async def test_physical_makeup_needs_a_room(session, instance, staff, teacher_user):
    await _make_missed(session, instance, staff)
    with pytest.raises(ValidationError, match="room"):
        await makeup_service.create(
            session,
            original_instance_id=instance.id,
            user=teacher_user,
            mode=MakeupMode.PHYSICAL,
            on=LATER,
            time_slot=FREE_SLOT,
            room=None,
        )


async def test_invalid_slot_is_rejected(session, instance, staff, teacher_user):
    """The lattice is closed: an arbitrary time is not a slot."""
    await _make_missed(session, instance, staff)
    with pytest.raises(ConflictError) as exc:
        await makeup_service.create(
            session,
            original_instance_id=instance.id,
            user=teacher_user,
            mode=MakeupMode.PHYSICAL,
            on=LATER,
            time_slot="13:37-14:20",
            room="KT-305",
        )
    types = {c["type"] for c in exc.value.detail["conflicts"]}
    assert "SLOT" in types

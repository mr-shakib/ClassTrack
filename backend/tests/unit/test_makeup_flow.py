"""The makeup workflow (BR-09 .. BR-14), and the online/physical distinction.

AC-08 is the criterion most easily broken by a later change to the staff query,
so it is asserted here rather than only checked by hand.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from tests.conftest import END_MIN, SLOT, START_MIN, at

from classtrack.core.errors import ConflictError, ValidationError
from classtrack.models import (
    BuiltinRole,
    CheckOutcome,
    ClassInstance,
    ClassSession,
    ClassStatus,
    MakeupMode,
    MakeupStatus,
    Notification,
    NotificationKind,
    User,
)
from classtrack.services import (
    check_service,
    checking_service,
    conflict_service,
    makeup_service,
    role_service,
    status_engine,
    sweep,
)


@pytest.fixture(autouse=True)
def _clock(monkeypatch):
    """Pin "now" to the afternoon of the missed class, so LATER is the future."""
    monkeypatch.setattr(status_engine, "now_local", lambda: at(12, 0))


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


def _occupant(instance, *, room, teacher="ZZZ", section="70_Z"):
    """Another class sitting in the LATER / FREE_SLOT cell."""
    return ClassInstance(
        session_id=None,
        semester_id=instance.semester_id,
        date=LATER,
        day="Sunday",
        time_slot=FREE_SLOT,
        start_min=960,
        end_min=1050,
        room=room,
        course_code="CSE999(70_Z)",
        section=section,
        batch=section,
        teacher_initial=teacher,
        status=None,
    )


async def _add_room(session, instance, room):
    """Give the active routine another room, so it exists to be offered."""
    template = await session.get(ClassSession, instance.session_id)
    session.add(
        ClassSession(
            routine_id=template.routine_id,
            day="Monday",
            time_slot=SLOT,
            room=room,
            course_code="CSE100(70_B)",
            teacher="OTH",
            batch="70_B",
            section="70_B",
            start_min=START_MIN,
            end_min=END_MIN,
        )
    )
    await session.flush()


async def _kinds_for(session, user):
    rows = await session.scalars(select(Notification).where(Notification.user_id == user.id))
    return [n.kind for n in rows.all()]


# --- BR-07: the teacher hears about a report straight away -----------------


async def test_staff_report_notifies_the_teacher_once(session, instance, staff, teacher_user):
    for _ in range(2):  # a retried submission from a flaky connection
        await check_service.submit(
            session,
            instance_id=instance.id,
            user=staff,
            outcome=CheckOutcome.TEACHER_NOT_FOUND,
            now=at(10, 5),
        )
    assert await _kinds_for(session, teacher_user) == [NotificationKind.CLASS_REPORTED]


async def test_reschedule_can_be_requested_as_soon_as_staff_report_absence(
    session, instance, staff, teacher_user
):
    """The notification says reschedule, so the teacher must be able to, at once."""
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=staff,
        outcome=CheckOutcome.TEACHER_NOT_FOUND,
        now=at(10, 5),
    )
    assert instance.status is None  # the threshold has not passed

    await makeup_service.create(
        session,
        original_instance_id=instance.id,
        user=teacher_user,
        mode=MakeupMode.PHYSICAL,
        on=LATER,
        time_slot=FREE_SLOT,
        room="KT-305",
    )
    assert instance.status is ClassStatus.MAKEUP_SCHEDULED

    # The sweep only settles unresolved rows, so it must leave the class alone.
    await sweep.sweep_once(session, now=at(10, 31))
    assert instance.status is ClassStatus.MAKEUP_SCHEDULED


# --- BR-10: an in-room reschedule books itself and enters checking ---------


async def test_physical_reschedule_needs_no_approval_and_is_checked_at_once(
    session, instance, staff, teacher_user, hod
):
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
    # Nothing to decide, so the HoD is told what happened, not asked about it.
    assert await _kinds_for(session, hod) == [NotificationKind.MAKEUP_SCHEDULED]
    assert NotificationKind.MAKEUP_SCHEDULED in await _kinds_for(session, teacher_user)

    screen = await checking_service.checking_screen(session, on=LATER, slot=FREE_SLOT)
    row = next(r for r in screen["rooms"] if r["instance_id"] == makeup.created_instance_id)
    assert row["is_makeup"] is True
    assert row["room"] == "KT-305"
    assert row["course_code"] == instance.course_code

    # And staff can report it at the new time like any other class.
    checked = await check_service.submit(
        session,
        instance_id=makeup.created_instance_id,
        user=staff,
        outcome=CheckOutcome.RUNNING,
        now=at(16, 5, day=LATER),
    )
    assert checked.status is ClassStatus.RUNNING


async def test_a_booked_room_is_closed_to_every_other_teacher(
    session, instance, staff, teacher_user
):
    """The point of booking on the spot: the cell is gone the moment it is taken."""
    await _make_missed(session, instance, staff)
    await makeup_service.create(
        session,
        original_instance_id=instance.id,
        user=teacher_user,
        mode=MakeupMode.PHYSICAL,
        on=LATER,
        time_slot=FREE_SLOT,
        room="KT-305",
    )
    await session.flush()

    assert await conflict_service.free_rooms(session, on=LATER, time_slot=FREE_SLOT) == []

    report = await conflict_service.check(
        session,
        on=LATER,
        time_slot=FREE_SLOT,
        teacher_initial="OTH",
        room="KT-305",
    )
    assert not report.ok
    assert [c.type for c in report.conflicts] == ["ROOM"]


async def test_free_rooms_leave_out_occupied_and_booked_rooms(
    session, instance, staff, teacher_user
):
    await _make_missed(session, instance, staff)
    await _add_room(session, instance, "KT-508")
    await _add_room(session, instance, "KT-601")

    async def free():
        rows = await conflict_service.free_rooms(session, on=LATER, time_slot=FREE_SLOT)
        return {r["room"] for r in rows}

    assert await free() == {"KT-305", "KT-508", "KT-601"}

    session.add(_occupant(instance, room="KT-508"))
    await makeup_service.create(
        session,
        original_instance_id=instance.id,
        user=teacher_user,
        mode=MakeupMode.PHYSICAL,
        on=LATER,
        time_slot=FREE_SLOT,
        room="KT-601",
    )
    await session.flush()

    assert await free() == {"KT-305"}


async def test_approval_rechecks_that_the_slot_is_still_free(
    session, instance, staff, teacher_user, hod
):
    """An online request waits, and the cell can fill while it does."""
    await _make_missed(session, instance, staff)
    makeup = await makeup_service.create(
        session,
        original_instance_id=instance.id,
        user=teacher_user,
        mode=MakeupMode.ONLINE,
        on=LATER,
        time_slot=FREE_SLOT,
    )
    session.add(_occupant(instance, room="KT-305", teacher=instance.teacher_initial))
    await session.flush()

    with pytest.raises(ConflictError):
        await makeup_service.decide(session, makeup_id=makeup.id, user=hod, approve=True)
    assert makeup.status is MakeupStatus.PENDING


async def test_a_slot_that_has_started_cannot_be_requested(
    session, instance, staff, teacher_user
):
    await _make_missed(session, instance, staff)
    with pytest.raises(ValidationError, match="already passed"):
        await makeup_service.create(
            session,
            original_instance_id=instance.id,
            user=teacher_user,
            mode=MakeupMode.PHYSICAL,
            on=date(2026, 9, 13),
            time_slot=SLOT,
            room="KT-305",
        )


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
        email="hod@test.edu",
        password_hash="x",
        full_name="HoD",
        roles=[await role_service.builtin(session, BuiltinRole.HOD)],
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
    hod = User(
        email="h2@test.edu",
        password_hash="x",
        full_name="HoD",
        roles=[await role_service.builtin(session, BuiltinRole.HOD)],
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
        session, makeup_id=makeup.id, user=hod, approve=False, note="Please hold it in person"
    )
    await session.commit()

    assert decided.status is MakeupStatus.REJECTED
    assert instance.status is ClassStatus.ONLINE_REJECTED
    assert decided.created_instance_id is None


# --- BR-13: the link to the original survives ------------------------------


async def test_makeup_keeps_its_link_to_the_original(
    session, instance, staff, teacher_user
):
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

    completed = await makeup_service.complete(
        session, makeup_id=makeup.id, user=teacher_user, now=AFTER_MAKEUP
    )
    await session.commit()

    assert completed.original_instance_id == original_id
    assert completed.status is MakeupStatus.COMPLETED
    assert completed.completed_by_id == teacher_user.id
    # Missed -> Makeup Scheduled -> Makeup Completed
    assert instance.status is ClassStatus.MAKEUP_COMPLETED


# --- the teacher is told what was rescheduled, and closes it out ----------

#: FREE_SLOT on LATER runs 16:00-17:30.
DURING_MAKEUP = at(16, 30, day=LATER)
AFTER_MAKEUP = at(17, 40, day=LATER)


async def _approved(session, instance, staff, teacher_user, hod, mode, note=None):
    """A makeup ready to be held: booked outright if in a room, approved if online."""
    await _make_missed(session, instance, staff)
    makeup = await makeup_service.create(
        session,
        original_instance_id=instance.id,
        user=teacher_user,
        mode=mode,
        on=LATER,
        time_slot=FREE_SLOT,
        room="KT-305" if mode is MakeupMode.PHYSICAL else None,
    )
    if mode is MakeupMode.ONLINE:
        await makeup_service.decide(
            session, makeup_id=makeup.id, user=hod, approve=True, note=note
        )
    await session.flush()
    return makeup


async def _latest_for(session, user):
    return await session.scalar(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.id.desc())
    )


async def test_booking_tells_the_teacher_which_class_moved_and_where(
    session, instance, staff, teacher_user, hod
):
    makeup = await _approved(
        session, instance, staff, teacher_user, hod, MakeupMode.PHYSICAL
    )
    sent = await _latest_for(session, teacher_user)

    assert sent.kind is NotificationKind.MAKEUP_SCHEDULED
    assert "Rescheduled" in sent.title and "KT-305" in sent.title
    for detail in (instance.course_code, instance.section, "13 September 2026", SLOT,
                   "20 September 2026", FREE_SLOT, "in room KT-305"):
        assert detail in sent.body
    assert sent.link == f"/teacher#makeup-{makeup.id}"


async def test_online_approval_asks_for_the_drive_link(
    session, instance, staff, teacher_user, hod
):
    await _approved(session, instance, staff, teacher_user, hod, MakeupMode.ONLINE)
    sent = await _latest_for(session, teacher_user)

    assert sent.kind is NotificationKind.ONLINE_DECISION
    assert "online" in sent.title
    assert "online" in sent.body and "Drive link" in sent.body


async def test_a_makeup_cannot_be_marked_done_before_it_ends(
    session, instance, staff, teacher_user, hod
):
    makeup = await _approved(session, instance, staff, teacher_user, hod, MakeupMode.PHYSICAL)
    with pytest.raises(ValidationError, match="ends at 17:30"):
        await makeup_service.complete(
            session, makeup_id=makeup.id, user=teacher_user, now=DURING_MAKEUP
        )
    assert makeup.status is MakeupStatus.SCHEDULED


async def test_online_makeup_needs_a_drive_link_to_be_done(
    session, instance, staff, teacher_user, hod
):
    makeup = await _approved(session, instance, staff, teacher_user, hod, MakeupMode.ONLINE)

    for bad, message in ((None, "Drive link"), ("  ", "Drive link"), ("my drive", "valid link")):
        with pytest.raises(ValidationError, match=message):
            await makeup_service.complete(
                session, makeup_id=makeup.id, user=teacher_user, drive_link=bad, now=AFTER_MAKEUP
            )
    assert makeup.status is MakeupStatus.APPROVED

    link = "https://drive.google.com/file/d/abc123/view"
    done = await makeup_service.complete(
        session, makeup_id=makeup.id, user=teacher_user, drive_link=f" {link} ", now=AFTER_MAKEUP
    )
    assert done.status is MakeupStatus.COMPLETED
    assert done.drive_link == link
    assert instance.status is ClassStatus.MAKEUP_COMPLETED


async def test_a_teacher_cannot_mark_someone_elses_makeup_done(
    session, instance, staff, teacher_user, hod
):
    from classtrack.core.errors import ForbiddenError
    from classtrack.models import Teacher

    makeup = await _approved(session, instance, staff, teacher_user, hod, MakeupMode.PHYSICAL)
    session.add(Teacher(initial="OTH", name="Other Teacher", department="cse"))
    other = User(
        email="oth@test.edu",
        password_hash="x",
        full_name="Other Teacher",
        roles=[await role_service.builtin(session, BuiltinRole.TEACHER)],
        teacher_initial="OTH",
    )
    session.add(other)
    await session.flush()

    with pytest.raises(ForbiddenError):
        await makeup_service.complete(session, makeup_id=makeup.id, user=other, now=AFTER_MAKEUP)


async def test_a_makeup_staff_found_empty_cannot_be_marked_done(
    session, instance, staff, teacher_user, hod
):
    makeup = await _approved(session, instance, staff, teacher_user, hod, MakeupMode.PHYSICAL)
    await check_service.submit(
        session,
        instance_id=makeup.created_instance_id,
        user=staff,
        outcome=CheckOutcome.TEACHER_NOT_FOUND,
        now=at(16, 5, day=LATER),
    )
    with pytest.raises(ConflictError, match="absent"):
        await makeup_service.complete(
            session, makeup_id=makeup.id, user=teacher_user, now=AFTER_MAKEUP
        )
    assert makeup.status is MakeupStatus.SCHEDULED


async def test_teacher_is_reminded_once_when_a_makeup_ends_unfinished(
    session, instance, staff, teacher_user, hod
):
    await _approved(session, instance, staff, teacher_user, hod, MakeupMode.ONLINE)

    assert (await sweep.sweep_once(session, now=DURING_MAKEUP))["reminded"] == 0
    assert (await sweep.sweep_once(session, now=AFTER_MAKEUP))["reminded"] == 1
    assert (await sweep.sweep_once(session, now=at(18, 0, day=LATER)))["reminded"] == 0

    kinds = await _kinds_for(session, teacher_user)
    assert kinds.count(NotificationKind.MAKEUP_REMINDER) == 1
    reminder = await _latest_for(session, teacher_user)
    assert "Drive link" in reminder.body


async def test_a_makeup_marked_done_is_not_reminded(
    session, instance, staff, teacher_user, hod
):
    makeup = await _approved(session, instance, staff, teacher_user, hod, MakeupMode.PHYSICAL)
    await makeup_service.complete(
        session, makeup_id=makeup.id, user=teacher_user, now=AFTER_MAKEUP
    )
    assert (await sweep.sweep_once(session, now=at(18, 0, day=LATER)))["reminded"] == 0


# --- an online request may carry a Drive link for the approver --------------

DRIVE = "https://drive.google.com/file/d/xyz/view"


async def test_an_online_request_can_carry_a_drive_link(
    session, instance, staff, teacher_user, hod
):
    await _make_missed(session, instance, staff)
    makeup = await makeup_service.create(
        session,
        original_instance_id=instance.id,
        user=teacher_user,
        mode=MakeupMode.ONLINE,
        on=LATER,
        time_slot=FREE_SLOT,
        drive_link=f"  {DRIVE} ",
    )
    assert makeup.drive_link == DRIVE

    sent = await _latest_for(session, hod)
    assert sent.kind is NotificationKind.ONLINE_REQUEST
    assert "Drive link" in sent.body


async def test_a_malformed_drive_link_on_a_request_is_refused(
    session, instance, staff, teacher_user
):
    await _make_missed(session, instance, staff)
    with pytest.raises(ValidationError, match="valid link"):
        await makeup_service.create(
            session,
            original_instance_id=instance.id,
            user=teacher_user,
            mode=MakeupMode.ONLINE,
            on=LATER,
            time_slot=FREE_SLOT,
            drive_link="my drive folder",
        )


async def test_a_physical_request_ignores_a_drive_link(session, instance, staff, teacher_user):
    await _make_missed(session, instance, staff)
    makeup = await makeup_service.create(
        session,
        original_instance_id=instance.id,
        user=teacher_user,
        mode=MakeupMode.PHYSICAL,
        on=LATER,
        time_slot=FREE_SLOT,
        room="KT-305",
        drive_link=DRIVE,
    )
    assert makeup.drive_link is None


async def test_a_link_sent_with_the_request_is_enough_to_mark_it_done(
    session, instance, staff, teacher_user, hod
):
    await _make_missed(session, instance, staff)
    makeup = await makeup_service.create(
        session,
        original_instance_id=instance.id,
        user=teacher_user,
        mode=MakeupMode.ONLINE,
        on=LATER,
        time_slot=FREE_SLOT,
        drive_link=DRIVE,
    )
    await makeup_service.decide(session, makeup_id=makeup.id, user=hod, approve=True)

    done = await makeup_service.complete(
        session, makeup_id=makeup.id, user=teacher_user, now=AFTER_MAKEUP
    )
    assert done.status is MakeupStatus.COMPLETED
    assert done.drive_link == DRIVE


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


# --- an online class may be held at any time of any day --------------------

#: 19:30 on LATER, well outside the six routine slots.
EVENING = "19:30"


async def test_online_makeup_can_be_held_at_a_time_off_the_routine(
    session, instance, staff, teacher_user, hod
):
    await _make_missed(session, instance, staff)

    makeup = await makeup_service.create(
        session,
        original_instance_id=instance.id,
        user=teacher_user,
        mode=MakeupMode.ONLINE,
        on=LATER,
        start_time=EVENING,
    )
    await session.commit()

    assert makeup.time_slot == "19:30-21:00"
    assert makeup.bounds() == (19 * 60 + 30, 21 * 60)
    assert makeup.status is MakeupStatus.PENDING

    decided = await makeup_service.decide(
        session, makeup_id=makeup.id, user=hod, approve=True
    )
    await session.commit()

    held = await session.get(ClassInstance, decided.created_instance_id)
    assert (held.time_slot, held.start_min, held.end_min) == ("19:30-21:00", 1170, 1260)
    # BR-12 still holds: nobody is sent to a room at half past seven.
    screen = await checking_service.checking_screen(session, on=LATER, slot=FREE_SLOT)
    assert decided.created_instance_id not in [r["instance_id"] for r in screen["rooms"]]


async def test_a_chosen_time_can_be_marked_done_only_once_it_ends(
    session, instance, staff, teacher_user, hod
):
    """The 'in SLOTS' guards used to make an off-lattice makeup uncompletable."""
    await _make_missed(session, instance, staff)
    makeup = await makeup_service.create(
        session,
        original_instance_id=instance.id,
        user=teacher_user,
        mode=MakeupMode.ONLINE,
        on=LATER,
        start_time=EVENING,
        drive_link=DRIVE,
    )
    await makeup_service.decide(session, makeup_id=makeup.id, user=hod, approve=True)

    with pytest.raises(ValidationError, match="ends at 21:00"):
        await makeup_service.complete(
            session, makeup_id=makeup.id, user=teacher_user, now=at(20, 0, day=LATER)
        )

    # The sweep reaches an off-lattice makeup too. It used to skip anything it
    # could not find in SLOTS, so this one would never have been chased.
    assert (await sweep.sweep_once(session, now=at(20, 0, day=LATER)))["reminded"] == 0
    assert (await sweep.sweep_once(session, now=at(21, 5, day=LATER)))["reminded"] == 1

    done = await makeup_service.complete(
        session, makeup_id=makeup.id, user=teacher_user, now=at(21, 5, day=LATER)
    )
    assert done.status is MakeupStatus.COMPLETED


async def test_a_chosen_time_that_overlaps_the_teachers_own_class_is_refused(
    session, instance, staff, teacher_user
):
    """FREE_SLOT runs 16:00-17:30, so 16:45 lands in the middle of it."""
    await _make_missed(session, instance, staff)
    session.add(_occupant(instance, room="KT-909", teacher=instance.teacher_initial))
    await session.flush()

    with pytest.raises(ConflictError) as exc:
        await makeup_service.create(
            session,
            original_instance_id=instance.id,
            user=teacher_user,
            mode=MakeupMode.ONLINE,
            on=LATER,
            start_time="16:45",
        )
    conflicts = exc.value.detail["conflicts"]
    assert {c["type"] for c in conflicts} == {"TEACHER"}
    # The message names the class in the way, at its own time -- not at 16:45.
    assert FREE_SLOT in conflicts[0]["message"]


async def test_a_chosen_time_clear_of_the_teachers_day_is_allowed(
    session, instance, staff, teacher_user
):
    """Touching at the edge is not overlapping: FREE_SLOT ends exactly at 17:30."""
    await _make_missed(session, instance, staff)
    session.add(_occupant(instance, room="KT-909", teacher=instance.teacher_initial))
    await session.flush()

    makeup = await makeup_service.create(
        session,
        original_instance_id=instance.id,
        user=teacher_user,
        mode=MakeupMode.ONLINE,
        on=LATER,
        start_time="17:30",
    )
    assert makeup.time_slot == "17:30-19:00"


async def test_two_online_classes_of_one_teacher_may_not_overlap(
    session, instance, staff, teacher_user
):
    """A pending request holds its teacher even though it holds no room."""
    await _make_missed(session, instance, staff)
    await makeup_service.create(
        session,
        original_instance_id=instance.id,
        user=teacher_user,
        mode=MakeupMode.ONLINE,
        on=LATER,
        start_time=EVENING,
    )
    await session.flush()

    report = await conflict_service.check(
        session,
        on=LATER,
        time_slot="20:00-21:30",
        start_min=20 * 60,
        end_min=21 * 60 + 30,
        teacher_initial=instance.teacher_initial,
    )
    assert [c.type for c in report.conflicts] == ["TEACHER"]


async def test_a_class_in_a_room_may_not_pick_its_own_time(
    session, instance, staff, teacher_user
):
    await _make_missed(session, instance, staff)
    with pytest.raises(ValidationError, match="routine's time slots"):
        await makeup_service.create(
            session,
            original_instance_id=instance.id,
            user=teacher_user,
            mode=MakeupMode.PHYSICAL,
            on=LATER,
            start_time=EVENING,
            room="KT-305",
        )


async def test_a_chosen_time_must_be_a_real_clock_time(
    session, instance, staff, teacher_user
):
    await _make_missed(session, instance, staff)
    for bad in ("half seven", "25:00", "7:30pm", ""):
        with pytest.raises(ValidationError, match=r"24-hour clock|when the class"):
            await makeup_service.create(
                session,
                original_instance_id=instance.id,
                user=teacher_user,
                mode=MakeupMode.ONLINE,
                on=LATER,
                start_time=bad,
            )


async def test_a_class_may_not_run_past_midnight(session, instance, staff, teacher_user):
    await _make_missed(session, instance, staff)
    with pytest.raises(ValidationError, match="past midnight"):
        await makeup_service.create(
            session,
            original_instance_id=instance.id,
            user=teacher_user,
            mode=MakeupMode.ONLINE,
            on=LATER,
            start_time="23:15",
        )

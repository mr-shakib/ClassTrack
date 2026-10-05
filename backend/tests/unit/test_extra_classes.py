"""Extra classes: a teacher books an empty room for one of their sections.

Checked and counted like any class, never owed, and the room is theirs from the
moment it is booked -- including against a rival who checked at the same time.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from tests.conftest import SLOT, at

from classtrack.core.errors import ConflictError, ForbiddenError, ValidationError
from classtrack.core.security import hash_password
from classtrack.models import (
    BuiltinRole,
    CheckOutcome,
    ClassInstance,
    ClassSession,
    ClassStatus,
    MakeupMode,
    Notification,
    NotificationKind,
    Routine,
    Teacher,
    User,
)
from classtrack.services import (
    check_service,
    conflict_service,
    email_service,
    extra_class_service,
    makeup_service,
    notification_service,
    report_service,
    role_service,
    status_engine,
    sweep,
)

#: A Monday in the fixture semester, with nothing on it yet.
MONDAY = date(2026, 9, 14)
ROOM = "KT-305"
COURSE = "CSE311(70_A)"
SECTION = "70_A"


@pytest.fixture(autouse=True)
def _clock(monkeypatch):
    """Pin "now" to the Monday morning, before the 10:00 slot."""
    monkeypatch.setattr(status_engine, "now_local", lambda: at(8, 0, day=MONDAY))


@pytest.fixture(autouse=True)
async def _routine(instance):
    """Every test needs the fixture routine, semester and TCA's CSE311 section."""
    return instance


@pytest.fixture
async def other_teacher(session, instance) -> User:
    """A second teacher on the same routine, with a section of their own."""
    routine = await session.scalar(select(Routine).where(Routine.is_active))
    session.add(Teacher(initial="TCB", name="Teacher B", department="cse"))
    session.add(
        ClassSession(
            routine_id=routine.id,
            day="Tuesday",
            time_slot=SLOT,
            room="KT-406",
            course_code="CSE499(70_B)",
            teacher="TCB",
            batch="70_B",
            section="70_B",
            start_min=600,
            end_min=690,
        )
    )
    await session.flush()
    user = User(
        email="tcb@test.edu",
        password_hash=hash_password("x"),
        full_name="Teacher B",
        roles=[await role_service.builtin(session, BuiltinRole.TEACHER)],
        teacher_initial="TCB",
    )
    session.add(user)
    await session.flush()
    return user


async def _book(session, user, **overrides):
    args = {
        "course_code": COURSE,
        "section": SECTION,
        "on": MONDAY,
        "time_slot": SLOT,
        "room": ROOM,
    }
    args.update(overrides)
    return await extra_class_service.book(session, user=user, **args)


async def test_a_teacher_books_an_empty_room_and_it_is_theirs(session, instance, teacher_user, hod):
    extra = await _book(session, teacher_user, room="kt-305")
    await session.flush()

    assert extra.is_extra and not extra.is_makeup
    assert extra.session_id is None
    assert extra.status is None  # on the staff screen like any unchecked class
    assert (extra.room, extra.room_type, extra.section) == (ROOM, "Theory", SECTION)
    assert extra.semester_id == instance.semester_id

    free = await conflict_service.free_rooms(session, on=MONDAY, time_slot=SLOT)
    assert ROOM not in {r["room"] for r in free}
    report = await conflict_service.check(
        session, on=MONDAY, time_slot=SLOT, teacher_initial="TCB", room=ROOM
    )
    assert [c.type for c in report.conflicts] == ["ROOM"]

    told = await session.scalar(select(Notification).where(Notification.user_id == hod.id))
    assert told.kind is NotificationKind.EXTRA_BOOKED


async def test_another_teacher_cannot_take_the_booked_room(session, teacher_user, other_teacher):
    await _book(session, teacher_user)
    await session.flush()
    with pytest.raises(ConflictError):
        await _book(session, other_teacher, course_code="CSE499(70_B)", section="70_B")


async def test_only_for_a_section_the_teacher_has(session, instance, teacher_user, other_teacher):
    with pytest.raises(ValidationError, match="do not teach"):
        await _book(session, teacher_user, course_code="CSE499(70_B)", section="70_B")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"on": date(2026, 9, 18)}, "Fridays"),
        ({"on": date(2027, 1, 5)}, "inside the Fall 2026 semester"),
        ({"room": "ZZ-999"}, "not a room on the routine"),
        ({"time_slot": "09:00-10:00"}, "not a routine slot"),
    ],
)
async def test_refuses_a_time_or_room_no_class_can_use(
    session, instance, teacher_user, overrides, message
):
    with pytest.raises(ValidationError, match=message):
        await _book(session, teacher_user, **overrides)


async def test_refuses_a_slot_already_under_way(session, instance, teacher_user):
    with pytest.raises(ValidationError, match="already passed"):
        await _book(session, teacher_user, now=at(10, 5, day=MONDAY))


async def test_cancelling_before_it_starts_gives_the_room_back(
    session, teacher_user, other_teacher
):
    extra = await _book(session, teacher_user)
    await session.flush()

    with pytest.raises(ForbiddenError):
        await extra_class_service.cancel(session, user=other_teacher, instance_id=extra.id)

    await extra_class_service.cancel(session, user=teacher_user, instance_id=extra.id)
    await session.flush()
    assert extra.status is ClassStatus.CANCELLED
    free = await conflict_service.free_rooms(session, on=MONDAY, time_slot=SLOT)
    assert ROOM in {r["room"] for r in free}


async def test_it_cannot_be_cancelled_once_started(session, teacher_user):
    extra = await _book(session, teacher_user)
    await session.flush()
    with pytest.raises(ValidationError, match="has started"):
        await extra_class_service.cancel(
            session, user=teacher_user, instance_id=extra.id, now=at(10, 1, day=MONDAY)
        )


async def test_a_missed_extra_class_is_recorded_but_not_owed(
    session, teacher_user, staff, monkeypatch
):
    extra = await _book(session, teacher_user)
    await session.flush()

    await check_service.submit(
        session,
        instance_id=extra.id,
        user=staff,
        outcome=CheckOutcome.TEACHER_NOT_FOUND,
        now=at(10, 5, day=MONDAY),
    )
    await sweep.sweep_once(session, now=at(10, 31, day=MONDAY))
    assert extra.status is ClassStatus.MISSED
    assert report_service.classify(extra) == report_service.MISSED

    assert not makeup_service.needs_reschedule(extra)
    monkeypatch.setattr(status_engine, "now_local", lambda: at(12, 0, day=MONDAY))
    with pytest.raises(ValidationError, match="missed class"):
        await makeup_service.create(
            session,
            original_instance_id=extra.id,
            user=teacher_user,
            mode=MakeupMode.PHYSICAL,
            on=date(2026, 9, 15),
            time_slot=SLOT,
            room="KT-406",
        )

    told = (
        await session.scalars(
            select(Notification)
            .where(Notification.user_id == teacher_user.id)
            .order_by(Notification.id)
        )
    ).all()
    assert [n.title for n in told] == [
        "Extra class missed",
        "Extra class missed",
    ]
    assert all("reschedule" not in (n.link or "") for n in told)


async def test_the_absence_email_asks_for_no_reschedule(session, instance, teacher_user):
    teacher = await session.scalar(select(Teacher).where(Teacher.initial == "TCA"))
    teacher.email = "tca@diu.edu.bd"
    extra = await _book(session, teacher_user)
    await session.flush()
    email_service.take(session)

    await notification_service.notify_reported(session, extra, CheckOutcome.TEACHER_NOT_FOUND)
    [mail] = email_service.take(session)
    assert "extra class" in mail.body
    assert "reschedule" not in mail.body
    assert mail.link is None


async def test_a_held_extra_class_counts_for_the_course_not_the_routine(session, teacher_user):
    extra = await _book(session, teacher_user)
    extra.status = ClassStatus.RUNNING

    tally = report_service.Tally()
    tally.add(extra, report_service.classify(extra), None)
    figures = tally.as_dict()
    assert figures["held"] == 1  # towards the course's minimum
    assert figures["extra_held"] == 1
    assert figures["scheduled"] == 0  # the routine never promised it


async def test_a_rival_booking_that_lands_after_the_check_is_backed_out(
    session, teacher_user, other_teacher, monkeypatch
):
    """The other teacher's booking commits between our check and our write."""
    rival = await _book(session, other_teacher, course_code="CSE499(70_B)", section="70_B")
    await session.flush()

    async def stale_check(*_args, **_kwargs):
        # What our check saw: the room still empty.
        return conflict_service.ConflictReport()

    monkeypatch.setattr(conflict_service, "check", stale_check)
    with pytest.raises(ConflictError, match="a moment ago"):
        await _book(session, teacher_user)

    holders = (
        await session.scalars(
            select(ClassInstance).where(ClassInstance.date == MONDAY, ClassInstance.room == ROOM)
        )
    ).all()
    # The route rolls the losing booking back; the winner is untouched.
    assert rival in holders

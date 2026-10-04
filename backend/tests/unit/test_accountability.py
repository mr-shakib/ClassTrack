"""Who failed to report which class.

NOT_CHECKED on its own is only half a finding. The floor assignments exist so
that somebody was responsible, and this view has to name them -- while keeping
apart the case where nobody was assigned at all, which is a configuration
problem no amount of chasing staff will fix.
"""

from __future__ import annotations

from datetime import date, timedelta

from tests.conftest import END_MIN, SLOT, START_MIN

from classtrack.core.security import hash_password
from classtrack.models import (
    BuiltinRole,
    ClassInstance,
    ClassStatus,
    Routine,
    Semester,
    User,
)
from classtrack.services import (
    accountability_service,
    assignment_service,
    role_service,
    status_engine,
)


async def _setup(session, rooms: list[str], *, on: date) -> Semester:
    routine = Routine(department="cse", version="A1", is_active=True, session_count=0)
    session.add(routine)
    await session.flush()
    semester = Semester(
        name="Acct",
        routine_id=routine.id,
        start_date=on - timedelta(days=30),
        end_date=on + timedelta(days=30),
        is_active=True,
    )
    session.add(semester)
    await session.flush()

    from classtrack.models import ClassSession

    for i, room in enumerate(rooms):
        sess = ClassSession(
            routine_id=routine.id,
            day="Sunday",
            time_slot=SLOT,
            room=room,
            course_code=f"CSE{400 + i}(70_A)",
            teacher="TCA",
            batch="70_A",
            section=f"70_{i}",
            start_min=START_MIN,
            end_min=END_MIN,
        )
        session.add(sess)
        await session.flush()
        session.add(
            ClassInstance(
                session_id=sess.id,
                semester_id=semester.id,
                date=on,
                day="Sunday",
                time_slot=SLOT,
                start_min=START_MIN,
                end_min=END_MIN,
                room=room,
                course_code=sess.course_code,
                section=sess.section,
                batch="70_A",
                teacher_initial="TCA",
                # Already swept: nobody reported these.
                status=ClassStatus.NOT_CHECKED,
            )
        )
    await session.flush()
    return semester


async def test_a_miss_is_attributed_to_the_assigned_staff(session, staff, hod):
    today = status_engine.now_local().date()
    await _setup(session, ["KT-201", "KT-208"], on=today)
    await assignment_service.set_zones(
        session, user_id=staff.id, zone_keys=["KT-2"], actor=hod
    )
    await session.commit()

    report = await accountability_service.unreported(session)
    row = next(r for r in report["by_staff"] if r["user_id"] == staff.id)

    assert row["today"] == 2
    assert row["total"] == 2
    assert {c["room"] for c in row["classes"]} == {"KT-201", "KT-208"}
    assert report["summary"]["staff_with_misses"] == 1


async def test_a_floor_nobody_covers_is_not_blamed_on_anyone(session, staff, hod):
    """A configuration gap is a different problem from a person's failure."""
    today = status_engine.now_local().date()
    await _setup(session, ["KT-201", "G1-001"], on=today)
    await assignment_service.set_zones(
        session, user_id=staff.id, zone_keys=["KT-2"], actor=hod
    )
    await session.commit()

    report = await accountability_service.unreported(session)
    row = next(r for r in report["by_staff"] if r["user_id"] == staff.id)

    assert row["total"] == 1                       # only their floor
    assert report["summary"]["unassigned"] == 1
    assert [c["room"] for c in report["unassigned"]] == ["G1-001"]


async def test_two_staff_on_one_floor_are_both_listed(session, staff, hod):
    today = status_engine.now_local().date()
    await _setup(session, ["KT-201"], on=today)

    second = User(
        email="staff2@test.edu",
        password_hash=hash_password("x"),
        full_name="Staff Two",
        roles=[await role_service.builtin(session, BuiltinRole.STAFF)],
    )
    session.add(second)
    await session.flush()

    for member in (staff, second):
        await assignment_service.set_zones(
            session, user_id=member.id, zone_keys=["KT-2"], actor=hod
        )
    await session.commit()

    report = await accountability_service.unreported(session)
    named = {r["user_id"] for r in report["by_staff"] if r["total"] > 0}
    assert named == {staff.id, second.id}


async def test_urgency_escalates_with_todays_backlog(session, staff, hod):
    today = status_engine.now_local().date()
    await _setup(session, [f"KT-2{i:02d}" for i in range(1, 7)], on=today)
    await assignment_service.set_zones(
        session, user_id=staff.id, zone_keys=["KT-2"], actor=hod
    )
    await session.commit()

    report = await accountability_service.unreported(session)
    row = next(r for r in report["by_staff"] if r["user_id"] == staff.id)
    assert row["today"] == 6
    assert row["urgency"] == "CRITICAL"


async def test_a_clean_staff_member_still_appears(session, staff, hod):
    """Showing only offenders hides the fact that someone is doing fine."""
    from sqlalchemy import select

    today = status_engine.now_local().date()
    await _setup(session, ["KT-201", "G1-001"], on=today)

    # This staff member did their floor: their one class is checked.
    theirs = await session.scalar(
        select(ClassInstance).where(ClassInstance.room == "KT-201")
    )
    theirs.status = ClassStatus.RUNNING

    await assignment_service.set_zones(
        session, user_id=staff.id, zone_keys=["KT-2"], actor=hod
    )
    await session.commit()

    report = await accountability_service.unreported(session)
    row = next(r for r in report["by_staff"] if r["user_id"] == staff.id)
    assert row["total"] == 0
    assert row["urgency"] == "LOW"
    # The G1 class is still missing, but it is nobody's to answer for.
    assert report["summary"]["unassigned"] == 1


async def test_checked_classes_are_not_reported_as_missed(session, staff, hod):
    today = status_engine.now_local().date()
    semester = await _setup(session, ["KT-201"], on=today)
    inst = await session.scalar(
        __import__("sqlalchemy").select(ClassInstance).where(
            ClassInstance.semester_id == semester.id
        )
    )
    inst.status = ClassStatus.RUNNING
    await assignment_service.set_zones(
        session, user_id=staff.id, zone_keys=["KT-2"], actor=hod
    )
    await session.commit()

    report = await accountability_service.unreported(session)
    assert report["summary"]["total"] == 0


async def test_worst_backlog_sorts_first(session, hod):
    today = status_engine.now_local().date()
    await _setup(session, ["KT-201", "KT-202", "G1-001"], on=today)

    heavy = User(
        email="heavy@test.edu", password_hash=hash_password("x"),
        full_name="Heavy", roles=[await role_service.builtin(session, BuiltinRole.STAFF)],
    )
    light = User(
        email="light@test.edu", password_hash=hash_password("x"),
        full_name="Light", roles=[await role_service.builtin(session, BuiltinRole.STAFF)],
    )
    session.add_all([heavy, light])
    await session.flush()
    await assignment_service.set_zones(
        session, user_id=heavy.id, zone_keys=["KT-2"], actor=hod
    )
    await assignment_service.set_zones(
        session, user_id=light.id, zone_keys=["G1-0"], actor=hod
    )
    await session.commit()

    report = await accountability_service.unreported(session)
    order = [r["name"] for r in report["by_staff"] if r["total"] > 0]
    assert order[0] == "Heavy"

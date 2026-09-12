"""Replacing a routine mid-semester.

A revised routine must take over the schedule *and* leave the monitoring
history alone. Getting this wrong in either direction is bad: keep too much and
staff see every future class twice, drop too much and a checked class vanishes
from the record.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from tests.conftest import END_MIN, SLOT, START_MIN

from classtrack.models import (
    CheckOutcome,
    ClassInstance,
    ClassSession,
    ClassStatus,
    Routine,
    Semester,
)
from classtrack.services import check_service, instance_service, status_engine


async def _routine(session, version: str, rooms: list[str]) -> Routine:
    routine = Routine(department="cse", version=version, is_active=False, session_count=len(rooms))
    session.add(routine)
    await session.flush()
    for room in rooms:
        session.add(
            ClassSession(
                routine_id=routine.id,
                day="Sunday",
                time_slot=SLOT,
                room=room,
                course_code=f"CSE311({room})",
                teacher="TCA",
                batch="70_A",
                section=f"70_{room[-1]}",
                start_min=START_MIN,
                end_min=END_MIN,
            )
        )
    await session.flush()
    return routine


async def _semester(session, routine_id: int) -> Semester:
    today = status_engine.now_local().date()
    semester = Semester(
        name="Test",
        routine_id=routine_id,
        start_date=today - timedelta(days=14),
        end_date=today + timedelta(days=28),
        is_active=True,
    )
    session.add(semester)
    await session.flush()
    return semester


async def test_revision_replaces_future_classes_and_keeps_history(session, hod):
    """The whole point: new schedule forward, old record backward."""
    old = await _routine(session, "V1", ["KT-301", "KT-302"])
    semester = await _semester(session, old.id)
    await instance_service.generate(session, semester_id=semester.id)
    await session.commit()

    # Monitor one past class, so there is history worth protecting.
    today = status_engine.now_local().date()
    past = await session.scalar(
        select(ClassInstance).where(ClassInstance.date < today).limit(1)
    )
    assert past is not None
    # Past-dated, so outside the checking window: an admin correction.
    await check_service.submit(
        session,
        instance_id=past.id,
        user=hod,
        outcome=CheckOutcome.RUNNING,
        reason="Recorded on paper, entered later",
    )
    await session.commit()
    checked_id = past.id

    before_future = await session.scalar(
        select(func.count(ClassInstance.id)).where(ClassInstance.date > today)
    )
    assert before_future > 0

    # A revision arrives: different rooms entirely.
    new = await _routine(session, "V2", ["KT-401", "KT-402", "KT-403"])
    semester.routine_id = new.id
    await session.flush()
    result = await instance_service.generate(session, semester_id=semester.id)
    await session.commit()

    assert result["instances_retired"] == before_future

    # No future class may still come from the superseded routine.
    stale = await session.scalar(
        select(func.count(ClassInstance.id))
        .select_from(ClassInstance)
        .join(ClassSession, ClassSession.id == ClassInstance.session_id)
        .where(ClassInstance.date > today, ClassSession.routine_id == old.id)
    )
    assert stale == 0

    # The monitored class survives untouched.
    kept = await session.get(ClassInstance, checked_id)
    assert kept is not None
    assert kept.status is ClassStatus.RUNNING
    assert kept.room == "KT-301"


async def test_revision_never_drops_a_monitored_future_class(session, hod):
    """A class already checked is a fact, even if it is in the future."""
    old = await _routine(session, "V1", ["KT-301"])
    semester = await _semester(session, old.id)
    await instance_service.generate(session, semester_id=semester.id)
    await session.commit()

    today = status_engine.now_local().date()
    future = await session.scalar(
        select(ClassInstance).where(ClassInstance.date > today).limit(1)
    )
    await check_service.submit(
        session,
        instance_id=future.id,
        user=hod,
        outcome=CheckOutcome.RUNNING,
        reason="Test fixture: a monitored future class",
    )
    await session.commit()
    monitored_id = future.id

    new = await _routine(session, "V2", ["KT-401"])
    semester.routine_id = new.id
    await session.flush()
    await instance_service.generate(session, semester_id=semester.id)
    await session.commit()

    survivor = await session.get(ClassInstance, monitored_id)
    assert survivor is not None
    assert survivor.status is ClassStatus.RUNNING


async def test_regenerating_the_same_routine_retires_nothing(session):
    """Re-running generation must stay a no-op, not churn the schedule."""
    routine = await _routine(session, "V1", ["KT-301"])
    semester = await _semester(session, routine.id)
    first = await instance_service.generate(session, semester_id=semester.id)
    await session.commit()
    assert first["instances_created"] > 0

    second = await instance_service.generate(session, semester_id=semester.id)
    await session.commit()
    assert second["instances_created"] == 0
    assert second["instances_retired"] == 0

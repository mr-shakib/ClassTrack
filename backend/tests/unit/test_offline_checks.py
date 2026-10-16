"""Checks made with no signal.

A staff member's phone keeps a check it could not send and sends it once it has
a signal again, with the time it was made. That time is trusted only between the
class's start and the moment it arrives; whichever observation was made last
stands, whatever order they arrive in; and an answer lost on the way, sent
again, changes nothing.
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import func, select
from tests.conftest import at

from classtrack.api.deps import get_current_user
from classtrack.core.errors import ConflictError
from classtrack.core.security import hash_password
from classtrack.db.session import get_session
from classtrack.main import app
from classtrack.models import (
    AuditLog,
    BuiltinRole,
    CheckOutcome,
    ClassStatus,
    Notification,
    User,
)
from classtrack.services import check_service, role_service, status_engine

# The fixture class runs 10:00-11:30 on 13 September 2026.


@pytest.fixture
async def other_staff(session) -> User:
    user = User(
        email="staff2@test.edu",
        password_hash=hash_password("x"),
        full_name="Second Staff",
        roles=[await role_service.builtin(session, BuiltinRole.STAFF)],
    )
    session.add(user)
    await session.flush()
    return user


async def _checks_audited(session, instance) -> int:
    return await session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.entity_id == instance.id, AuditLog.action == "check_submitted")
    )


async def test_a_check_sent_later_keeps_the_time_it_was_made(session, instance, staff):
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=staff,
        outcome=CheckOutcome.RUNNING,
        observed_at=at(10, 6),
        now=at(10, 48),
    )
    assert instance.status is ClassStatus.RUNNING
    assert status_engine.to_local(instance.check.checked_at) == at(10, 6)


async def test_a_phone_clock_running_ahead_is_not_believed(session, instance, staff):
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=staff,
        outcome=CheckOutcome.RUNNING,
        observed_at=at(11, 30),
        now=at(10, 20),
    )
    assert status_engine.to_local(instance.check.checked_at) == at(10, 20)


async def test_a_phone_clock_running_behind_is_held_to_the_class(session, instance, staff):
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=staff,
        outcome=CheckOutcome.RUNNING,
        observed_at=at(9, 40),
        now=at(10, 20),
    )
    assert status_engine.to_local(instance.check.checked_at) == at(10, 0)


async def test_a_time_on_another_day_is_ignored(session, instance, staff):
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=staff,
        outcome=CheckOutcome.RUNNING,
        observed_at=at(10, 5).replace(day=12),
        now=at(10, 20),
    )
    assert status_engine.to_local(instance.check.checked_at) == at(10, 20)


async def test_the_observation_made_last_stands_whatever_arrives_last(
    session, instance, staff, other_staff, teacher_user
):
    """A reported absence, then the teacher arrives: the phone that saw the
    absence had no signal, so its report arrives after the later one."""
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=other_staff,
        outcome=CheckOutcome.LATE,
        arrival_time=at(10, 25).time(),
        observed_at=at(10, 26),
        now=at(10, 26),
    )
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=staff,
        outcome=CheckOutcome.TEACHER_NOT_FOUND,
        observed_at=at(10, 10),
        now=at(10, 40),
    )
    await session.flush()

    assert instance.status is ClassStatus.LATE
    assert instance.check.outcome is CheckOutcome.LATE
    assert instance.check.checked_by_id == other_staff.id
    # The teacher heard of the late arrival, never of an absence.
    titles = (
        await session.scalars(
            select(Notification.title).where(Notification.user_id == teacher_user.id)
        )
    ).all()
    assert len(titles) == 1 and "absent" not in titles[0].lower()


async def test_an_answer_lost_and_sent_again_changes_nothing(session, instance, staff):
    for _ in range(2):
        await check_service.submit(
            session,
            instance_id=instance.id,
            user=staff,
            outcome=CheckOutcome.RUNNING,
            observed_at=at(10, 6),
            now=at(10, 30),
        )
    await session.flush()
    assert await _checks_audited(session, instance) == 1


async def test_a_check_that_waited_past_midnight_is_refused(session, instance, staff):
    """The day's reporting closes at midnight, for a check that waited too."""
    with pytest.raises(ConflictError, match="closed"):
        await check_service.submit(
            session,
            instance_id=instance.id,
            user=staff,
            outcome=CheckOutcome.RUNNING,
            observed_at=at(10, 6),
            now=at(0, 5).replace(day=14),
        )


async def test_the_answer_names_the_check_on_file(
    session, instance, staff, other_staff, monkeypatch
):
    monkeypatch.setattr(status_engine, "now_local", lambda: at(10, 40))
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=other_staff,
        outcome=CheckOutcome.RUNNING,
        observed_at=at(10, 30),
        now=at(10, 30),
    )
    await session.commit()

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = lambda: staff
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                f"/api/v1/checking/{instance.id}",
                json={
                    "outcome": "TEACHER_NOT_FOUND",
                    "observed_at": at(10, 8).isoformat(),
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["outcome"] == "RUNNING"
    assert body["checked_by"] == "Second Staff"

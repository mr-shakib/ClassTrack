"""An admin writes a notification to teachers and staff, from the Notifications tab.

It reaches each reader's bell and phones like any other notification, and the
audit log keeps what was sent, which is also the tab's history.
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select

from classtrack.api.deps import get_current_user
from classtrack.core.errors import ValidationError
from classtrack.db.session import get_session
from classtrack.main import app
from classtrack.models import (
    BuiltinRole,
    Notification,
    NotificationKind,
    Permission,
    PushDevice,
    User,
)
from classtrack.services import announcement_service, push_service, role_service


async def _send(session, sender, audience, user_ids=None):
    return await announcement_service.send(
        session,
        sender=sender,
        title="Thursday is a holiday",
        body="No classes on Thursday. Classes resume on Saturday.",
        audience=audience,
        user_ids=user_ids,
    )


async def _readers(session) -> set[int]:
    return set((await session.scalars(select(Notification.user_id))).all())


async def test_all_teachers_reach_only_teachers(session, hod, staff, teacher_user):
    sent = await _send(session, hod, "teachers")

    assert sent.sent_to == 1
    assert await _readers(session) == {teacher_user.id}
    [kept] = (await session.scalars(select(Notification))).all()
    assert kept.kind is NotificationKind.ANNOUNCEMENT
    assert (kept.title, kept.link) == ("Thursday is a holiday", None)


async def test_office_staff_reach_only_staff(session, hod, staff, teacher_user):
    await _send(session, hod, "staff")

    assert await _readers(session) == {staff.id}


async def test_everyone_leaves_out_the_sender_and_inactive_accounts(
    session, hod, staff, teacher_user, coordinator
):
    coordinator.is_active = False

    sent = await _send(session, hod, "everyone")

    assert sent.sent_to == 2
    assert await _readers(session) == {staff.id, teacher_user.id}


async def test_chosen_people_may_include_the_sender(session, hod, staff, teacher_user):
    await _send(session, hod, "chosen", [hod.id, teacher_user.id])

    assert await _readers(session) == {hod.id, teacher_user.id}


async def test_choosing_nobody_is_refused(session, hod):
    with pytest.raises(ValidationError):
        await _send(session, hod, "chosen", [])


async def test_an_empty_group_is_refused(session, hod):
    with pytest.raises(ValidationError, match="Nobody is in that group"):
        await _send(session, hod, "teachers")


async def test_it_is_pushed_and_counts_the_phones(session, hod, staff, teacher_user):
    session.add(PushDevice(user_id=teacher_user.id, token="t", platform="android"))
    await session.flush()

    sent = await _send(session, hod, "everyone")

    assert (sent.sent_to, sent.on_phones) == (2, 1)
    pushes = push_service.take(session)
    assert {p.user_id for p in pushes} == {staff.id, teacher_user.id}
    assert {p.kind for p in pushes} == {"ANNOUNCEMENT"}


async def test_what_was_sent_is_kept_in_the_history(session, hod, teacher_user):
    await _send(session, hod, "teachers")

    [record] = await announcement_service.history(session)

    assert record.title == "Thursday is a holiday"
    assert (record.audience, record.sent_to, record.sent_by) == ("teachers", 1, hod.full_name)


async def test_the_coordination_officer_may_send_and_staff_may_not(session, coordinator, staff):
    assert coordinator.can(Permission.SEND_NOTIFICATIONS)
    assert not staff.can(Permission.SEND_NOTIFICATIONS)


# --- the endpoints ---------------------------------------------------------------


async def _call(session, user: User, method: str, path: str, body=None) -> httpx.Response:
    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.request(method, f"/api/v1{path}", json=body)
    finally:
        app.dependency_overrides.clear()


async def test_the_endpoint_sends_and_reports_how_many(session, hod, teacher_user):
    response = await _call(
        session,
        hod,
        "POST",
        "/admin/notifications",
        {"title": " Exams moved ", "body": "See the notice board.", "audience": "teachers"},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"sent_to": 1, "on_phones": 0}
    [kept] = (await session.scalars(select(Notification))).all()
    assert kept.title == "Exams moved"

    history = (await _call(session, hod, "GET", "/admin/notifications")).json()
    assert [h["title"] for h in history] == ["Exams moved"]


async def test_staff_cannot_send(session, staff):
    response = await _call(
        session,
        staff,
        "POST",
        "/admin/notifications",
        {"title": "t", "body": "b", "audience": "everyone"},
    )

    assert response.status_code == 403


async def test_a_blank_message_is_refused(session, hod):
    response = await _call(
        session,
        hod,
        "POST",
        "/admin/notifications",
        {"title": "   ", "body": "b", "audience": "everyone"},
    )

    assert response.status_code == 422


async def test_recipients_say_who_has_the_app(session, hod, teacher_user):
    session.add(PushDevice(user_id=teacher_user.id, token="t", platform="ios"))
    await session.flush()

    response = await _call(session, hod, "GET", "/admin/notifications/recipients")

    rows = {r["id"]: r for r in response.json()}
    assert rows[teacher_user.id]["on_phone"] is True
    assert rows[teacher_user.id]["teacher_initial"] == "TCA"
    assert rows[teacher_user.id]["roles"] == "Teacher"
    assert rows[hod.id]["on_phone"] is False


async def test_a_new_install_gives_the_admins_the_permission(session):
    for key in (BuiltinRole.HOD, BuiltinRole.ASSOCIATE_HEAD, BuiltinRole.COORDINATION_OFFICER):
        role = await role_service.builtin(session, key)
        assert Permission.SEND_NOTIFICATIONS in role.granted

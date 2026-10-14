"""Notifications reach the teacher's phone as pushes, and classes are reminded before they start.

A push is queued with the notification and handed to the app's sender only by a
commit, so a rollback pushes nothing, and the tests -- which start no sender --
push nothing either. Class reminders are pushed only, never kept in the bell.
"""

from __future__ import annotations

import asyncio
import contextlib
import json

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.conftest import at

from classtrack.api.deps import get_current_user
from classtrack.core.config import get_settings
from classtrack.core.security import hash_password
from classtrack.db.session import get_session
from classtrack.main import app
from classtrack.models import (
    BuiltinRole,
    CheckOutcome,
    ClassInstance,
    ClassStatus,
    Notification,
    PushDevice,
    User,
)
from classtrack.services import (
    check_service,
    push_service,
    role_service,
    settings_service,
    sweep,
)

TOKEN = "phone-token-a"


@pytest.fixture
def sink(monkeypatch) -> list[list[push_service.Push]]:
    """Stands in for the app's sender: what each commit handed over."""
    handed: list[list[push_service.Push]] = []
    monkeypatch.setattr(push_service, "_sink", handed.append)
    return handed


def _push(user_id: int = 1, **kw) -> push_service.Push:
    return push_service.Push(user_id=user_id, title="t", body="b", kind="MISSED_CLASS", **kw)


# --- handing over on commit ---------------------------------------------------


async def test_a_commit_hands_its_pushes_to_the_sender(session, sink):
    push_service.queue(session, _push())

    await session.commit()

    assert sink == [[_push()]]
    assert push_service.take(session) == []


async def test_a_rollback_pushes_nothing(session, sink):
    push_service.queue(session, _push())

    await session.rollback()
    await session.commit()

    assert sink == []


async def test_without_a_sender_a_commit_drops_them(session, monkeypatch):
    monkeypatch.setattr(push_service, "_sink", None)
    push_service.queue(session, _push())

    await session.commit()

    assert push_service.take(session) == []


async def test_a_notification_is_pushed_as_well_as_kept(session, instance, staff, teacher_user):
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=staff,
        outcome=CheckOutcome.TEACHER_NOT_FOUND,
        now=at(10, 5),
    )

    [kept] = (await session.scalars(select(Notification))).all()
    [push] = push_service.take(session)
    assert push.user_id == teacher_user.id
    assert (push.kind, push.title, push.body, push.link) == (
        kept.kind.value,
        kept.title,
        kept.body,
        kept.link,
    )


# --- reminders before a class ----------------------------------------------------


async def _reminders(session: AsyncSession, sink, now) -> list[push_service.Push]:
    """What one sweep pass reminded. The pass commits, which hands its pushes to ``sink``."""
    sink.clear()
    await sweep.sweep_once(session, now=now)
    return [p for batch in sink for p in batch if p.kind == push_service.CLASS_REMINDER]


async def test_a_class_is_reminded_the_set_minutes_before_it_starts(
    session, instance, teacher_user, sink
):
    assert await _reminders(session, sink, at(9, 49)) == []

    [push] = await _reminders(session, sink, at(9, 50))

    assert push.user_id == teacher_user.id
    assert push.title == "CSE311(70_A) starts in 10 minutes"
    assert push.body == "Class in room KT-305, 10:00-11:30."
    assert push.ttl_seconds == 600
    assert instance.reminded_at is not None
    assert (await session.scalars(select(Notification))).all() == []


async def test_a_class_is_reminded_once(session, instance, teacher_user, sink):
    assert len(await _reminders(session, sink, at(9, 50))) == 1
    assert await _reminders(session, sink, at(9, 55)) == []


async def test_a_late_pass_says_the_minutes_left_and_a_started_class_is_let_go(
    session, instance, teacher_user, sink
):
    [push] = await _reminders(session, sink, at(9, 57))
    assert push.title == "CSE311(70_A) starts in 3 minutes"

    instance.reminded_at = None
    assert await _reminders(session, sink, at(10, 0)) == []


async def test_the_admin_sets_the_minutes(session, instance, teacher_user, sink):
    await settings_service.set_value(session, "class_reminder_minutes", "15")

    assert len(await _reminders(session, sink, at(9, 45))) == 1


async def test_zero_minutes_sends_no_reminders(session, instance, teacher_user, sink):
    await settings_service.set_value(session, "class_reminder_minutes", "0")

    assert await _reminders(session, sink, at(9, 55)) == []
    assert instance.reminded_at is None


async def test_a_cancelled_class_is_not_reminded(session, instance, teacher_user, sink):
    instance.status = ClassStatus.CANCELLED

    assert await _reminders(session, sink, at(9, 55)) == []


async def test_an_approved_online_makeup_is_reminded(session, instance, teacher_user, sink):
    online = ClassInstance(
        semester_id=instance.semester_id,
        date=instance.date,
        day="Sunday",
        time_slot="14:30-16:00",
        start_min=870,
        end_min=960,
        room="ONLINE",
        room_type="Online",
        course_code=instance.course_code,
        section=instance.section,
        batch=instance.batch,
        teacher_initial="TCA",
        is_makeup=True,
        status=ClassStatus.ONLINE_APPROVED,
    )
    session.add(online)
    await session.flush()

    [push] = await _reminders(session, sink, at(14, 25))

    assert push.title == "CSE311(70_A) starts in 5 minutes"
    assert push.body == "Makeup class online, 14:30-16:00."


async def test_a_teacher_with_no_account_is_not_reminded(session, instance, teacher_user, sink):
    await session.delete(teacher_user)
    await session.flush()

    assert await _reminders(session, sink, at(9, 55)) == []


async def test_reminders_default_to_ten_minutes(session):
    assert await settings_service.class_reminder_minutes(session) == 10


# --- sending to Firebase -----------------------------------------------------------


def _private_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def firebase(monkeypatch):
    """A service account, and a fake Google that records what it is sent."""
    key = _private_key()
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    monkeypatch.setattr(
        get_settings(),
        "fcm_credentials",
        json.dumps(
            {
                "type": "service_account",
                "project_id": "classtrack-test",
                "private_key_id": "kid-1",
                "private_key": pem,
                "client_email": "push@classtrack-test.iam.gserviceaccount.com",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        ),
    )
    monkeypatch.setattr(push_service, "_access", None)

    class Google:
        def __init__(self) -> None:
            self.public_key = key.public_key()
            self.sign_ins: list[str] = []
            self.sent: list[dict] = []
            #: token -> the response FCM gives it
            self.refuse: dict[str, httpx.Response] = {}

        def __call__(self, request: httpx.Request) -> httpx.Response:
            if request.url.host == "oauth2.googleapis.com":
                form = dict(httpx.QueryParams(request.content.decode()))
                self.sign_ins.append(form["assertion"])
                return httpx.Response(200, json={"access_token": "ya29.test", "expires_in": 3600})
            assert request.url.path == "/v1/projects/classtrack-test/messages:send"
            assert request.headers["authorization"] == "Bearer ya29.test"
            message = json.loads(request.content)["message"]
            self.sent.append(message)
            return self.refuse.get(message["token"], httpx.Response(200, json={"name": "m/1"}))

    return Google()


async def _send(session: AsyncSession, google, pushes) -> None:
    await session.commit()
    async with httpx.AsyncClient(transport=httpx.MockTransport(google)) as client:
        await push_service.send_all(
            pushes,
            client=client,
            sessions=async_sessionmaker(session.bind, expire_on_commit=False),
        )


async def test_a_push_reaches_every_phone_the_account_signed_in_on(session, teacher_user, firebase):
    session.add_all(
        [
            PushDevice(user_id=teacher_user.id, token="a", platform="android"),
            PushDevice(user_id=teacher_user.id, token="b", platform="ios"),
        ]
    )
    push = push_service.Push(
        user_id=teacher_user.id,
        title="Class missed",
        body="CSE311 has been marked as missed.",
        kind="CLASS_REPORTED",
        link="/teacher/makeup?instance=7",
    )

    await _send(session, firebase, [push])

    assert sorted(m["token"] for m in firebase.sent) == ["a", "b"]
    message = firebase.sent[0]
    assert message["notification"] == {
        "title": "Class missed",
        "body": "CSE311 has been marked as missed.",
    }
    assert message["data"] == {"kind": "CLASS_REPORTED", "link": "/teacher/makeup?instance=7"}
    assert message["android"]["notification"]["channel_id"] == "alerts"

    [assertion] = firebase.sign_ins
    claims = jwt.decode(
        assertion,
        firebase.public_key,
        algorithms=["RS256"],
        audience="https://oauth2.googleapis.com/token",
    )
    assert claims["iss"] == "push@classtrack-test.iam.gserviceaccount.com"
    assert claims["scope"] == push_service.FCM_SCOPE
    assert jwt.get_unverified_header(assertion)["kid"] == "kid-1"


async def test_a_reminder_goes_to_its_own_channel_and_expires(session, teacher_user, firebase):
    session.add(PushDevice(user_id=teacher_user.id, token="a", platform="android"))
    push = push_service.Push(
        user_id=teacher_user.id,
        title="CSE311 starts in 10 minutes",
        body="Class in room KT-305, 10:00-11:30.",
        kind=push_service.CLASS_REMINDER,
        ttl_seconds=600,
    )

    await _send(session, firebase, [push])

    [message] = firebase.sent
    assert message["android"]["notification"]["channel_id"] == "classes"
    assert message["android"]["ttl"] == "600s"
    assert "apns-expiration" in message["apns"]["headers"]


async def test_a_phone_firebase_no_longer_knows_is_forgotten(session, teacher_user, firebase):
    session.add_all(
        [
            PushDevice(user_id=teacher_user.id, token="gone", platform="android"),
            PushDevice(user_id=teacher_user.id, token="kept", platform="android"),
        ]
    )
    firebase.refuse["gone"] = httpx.Response(
        404,
        json={
            "error": {
                "status": "NOT_FOUND",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.firebase.fcm.v1.FcmError",
                        "errorCode": "UNREGISTERED",
                    }
                ],
            }
        },
    )

    await _send(session, firebase, [_push(teacher_user.id), _push(teacher_user.id)])

    tokens = (await session.scalars(select(PushDevice.token))).all()
    assert tokens == ["kept"]
    # Tried once, then not again for the second push.
    assert [m["token"] for m in firebase.sent].count("gone") == 1


async def test_a_deactivated_account_is_not_pushed(session, teacher_user, firebase):
    session.add(PushDevice(user_id=teacher_user.id, token="a", platform="android"))
    teacher_user.is_active = False

    await _send(session, firebase, [_push(teacher_user.id)])

    assert firebase.sent == []
    assert firebase.sign_ins == []


async def test_without_a_service_account_nothing_is_sent(session, teacher_user, monkeypatch):
    monkeypatch.setattr(get_settings(), "fcm_credentials", None)
    session.add(PushDevice(user_id=teacher_user.id, token="a", platform="android"))
    seen: list[httpx.Request] = []

    def google(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200)

    await _send(session, google, [_push(teacher_user.id)])

    assert seen == []
    assert push_service.start() is None


async def test_the_service_account_may_be_a_file(tmp_path, monkeypatch):
    path = tmp_path / "firebase.json"
    path.write_text(
        json.dumps(
            {
                "project_id": "p",
                "client_email": "e@p.iam.gserviceaccount.com",
                "private_key": "k",
            }
        )
    )
    monkeypatch.setattr(get_settings(), "fcm_credentials", str(path))

    assert push_service.enabled()


async def test_a_broken_service_account_disables_push(monkeypatch, caplog):
    monkeypatch.setattr(get_settings(), "fcm_credentials", '{"project_id": "p"}')

    assert not push_service.enabled()
    assert "not a service account" in caplog.text


async def test_the_running_sender_sends_what_a_commit_hands_it(session, firebase, monkeypatch):
    sent: list[list[push_service.Push]] = []
    done = asyncio.Event()

    async def fake_send_all(pushes, *, client):
        sent.append(pushes)
        done.set()

    monkeypatch.setattr(push_service, "send_all", fake_send_all)
    task = push_service.start()
    assert task is not None
    try:
        push_service.queue(session, _push())
        await session.commit()
        await asyncio.wait_for(done.wait(), timeout=2)
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    assert sent == [[_push()]]
    assert push_service._sink is None


# --- the phones ----------------------------------------------------------------------


async def _post(session: AsyncSession, user: User, path: str, body: dict) -> httpx.Response:
    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.post(f"/api/v1{path}", json=body)
    finally:
        app.dependency_overrides.clear()


async def _phones(session: AsyncSession) -> list[tuple[int, str, str]]:
    rows = await session.execute(
        select(PushDevice.user_id, PushDevice.token, PushDevice.platform).order_by(PushDevice.id)
    )
    return [tuple(r) for r in rows.all()]


@pytest.fixture
async def other_user(session: AsyncSession) -> User:
    user = User(
        email="other@test.edu",
        password_hash=hash_password("x"),
        full_name="Other",
        roles=[await role_service.builtin(session, BuiltinRole.STAFF)],
    )
    session.add(user)
    await session.flush()
    return user


async def test_registering_a_phone_is_idempotent(session, teacher_user):
    for _ in range(2):
        response = await _post(
            session, teacher_user, "/notifications/devices", {"token": TOKEN, "platform": "android"}
        )
        assert response.status_code == 200, response.text

    assert await _phones(session) == [(teacher_user.id, TOKEN, "android")]


async def test_a_phone_serves_whoever_signed_in_on_it_last(session, teacher_user, other_user):
    body = {"token": TOKEN, "platform": "android"}
    await _post(session, teacher_user, "/notifications/devices", body)
    await _post(session, other_user, "/notifications/devices", body)

    assert await _phones(session) == [(other_user.id, TOKEN, "android")]


async def test_signing_out_stops_the_pushes_but_only_for_ones_own_phone(
    session, teacher_user, other_user
):
    await _post(
        session, teacher_user, "/notifications/devices", {"token": TOKEN, "platform": "ios"}
    )

    await _post(session, other_user, "/notifications/devices/remove", {"token": TOKEN})
    assert len(await _phones(session)) == 1

    response = await _post(session, teacher_user, "/notifications/devices/remove", {"token": TOKEN})
    assert response.status_code == 200
    assert await _phones(session) == []


async def test_an_unknown_platform_is_refused(session, teacher_user):
    response = await _post(
        session, teacher_user, "/notifications/devices", {"token": TOKEN, "platform": "web"}
    )

    assert response.status_code == 422


async def test_an_account_removed_takes_its_phones_with_it(session, other_user):
    session.add(PushDevice(user_id=other_user.id, token=TOKEN, platform="android"))
    await session.flush()

    await session.delete(other_user)
    await session.flush()

    assert await _phones(session) == []

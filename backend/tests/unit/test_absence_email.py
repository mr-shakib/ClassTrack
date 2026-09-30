"""A teacher reported absent is emailed at their faculty address.

The email is queued with the check and sent only by the request path, after the
commit. The demo seed runs through the same services, and the faculty directory
holds real addresses, so nothing but that endpoint may send.
"""

from __future__ import annotations

import json
from datetime import time

import httpx
import pytest
from sqlalchemy import select
from tests.conftest import at

from classtrack.api.deps import get_current_user
from classtrack.cli import _load_teachers
from classtrack.core.config import get_settings
from classtrack.db.session import get_session
from classtrack.main import app
from classtrack.models import CheckOutcome, Notification, Teacher
from classtrack.services import check_service, email_service

ADDRESS = "teacher.a@diu.edu.bd"


@pytest.fixture
async def with_email(session, teacher_user):
    teacher = await session.scalar(select(Teacher).where(Teacher.initial == "TCA"))
    teacher.email = ADDRESS
    await session.flush()
    return teacher


async def _report(session, instance, staff, outcome, **kw):
    return await check_service.submit(
        session, instance_id=instance.id, user=staff, outcome=outcome, now=at(10, 5), **kw
    )


# --- what gets queued ---------------------------------------------------------


async def test_absence_queues_an_email_to_the_faculty_address(session, instance, staff, with_email):
    await _report(session, instance, staff, CheckOutcome.TEACHER_NOT_FOUND)

    [email] = email_service.take(session)
    assert email.to == ADDRESS
    assert "CSE311(70_A)" in email.subject
    assert "KT-305" in email.body
    assert "Teacher A" in email.body


async def test_absence_emails_a_teacher_with_no_account(
    session, instance, staff, with_email, teacher_user
):
    """The address is the directory's, so an account is not needed to be told."""
    await session.delete(teacher_user)
    await session.flush()

    await _report(session, instance, staff, CheckOutcome.TEACHER_NOT_FOUND)

    assert [e.to for e in email_service.take(session)] == [ADDRESS]


async def test_resubmitting_an_absence_does_not_email_twice(session, instance, staff, with_email):
    await _report(session, instance, staff, CheckOutcome.TEACHER_NOT_FOUND)
    await _report(session, instance, staff, CheckOutcome.TEACHER_NOT_FOUND)

    assert len(email_service.take(session)) == 1


async def test_late_and_running_are_not_emailed(session, instance, staff, with_email):
    await _report(session, instance, staff, CheckOutcome.LATE, arrival_time=time(10, 12))
    await _report(session, instance, staff, CheckOutcome.RUNNING)

    assert email_service.take(session) == []


async def test_no_address_on_file_skips_the_email_but_not_the_bell(
    session, instance, staff, teacher_user
):
    await _report(session, instance, staff, CheckOutcome.TEACHER_NOT_FOUND)

    assert email_service.take(session) == []
    bell = await session.scalar(select(Notification).where(Notification.user_id == teacher_user.id))
    assert bell is not None


async def test_link_uses_the_public_url(session, instance, staff, with_email, monkeypatch):
    monkeypatch.setattr(get_settings(), "public_url", "https://class.example.edu/")

    await _report(session, instance, staff, CheckOutcome.TEACHER_NOT_FOUND)

    [email] = email_service.take(session)
    assert email.link == f"https://class.example.edu/teacher/makeup?instance={instance.id}"


# --- delivery -----------------------------------------------------------------


def _capture() -> tuple[list[httpx.Request], httpx.MockTransport]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "msg_1"})

    return seen, httpx.MockTransport(handler)


async def test_send_posts_to_resend(monkeypatch):
    monkeypatch.setattr(get_settings(), "resend_api_key", "re_test")
    seen, transport = _capture()

    await email_service.send_all(
        [
            email_service.Email(
                to=ADDRESS,
                subject="Reported absent",
                body="Dear <Teacher>,\n\nSecond paragraph.",
                link="https://class.example.edu/teacher",
                link_label="Request a reschedule",
            )
        ],
        transport=transport,
    )

    [request] = seen
    assert str(request.url) == email_service.RESEND_URL
    assert request.headers["authorization"] == "Bearer re_test"
    sent = json.loads(request.content)
    assert sent["to"] == [ADDRESS]
    assert sent["from"] == get_settings().email_from
    assert sent["subject"] == "Reported absent"
    assert "Request a reschedule: https://class.example.edu/teacher" in sent["text"]
    assert "&lt;Teacher&gt;" in sent["html"]
    assert sent["text"].endswith("Developed by Shakib Howlader\nhttps://shakibhowlader.online")
    assert '<a href="https://shakibhowlader.online" style="color:#6b7280">Shakib Howlader</a>' in (
        sent["html"]
    )


async def test_no_key_sends_nothing(monkeypatch):
    monkeypatch.setattr(get_settings(), "resend_api_key", None)
    seen, transport = _capture()

    await email_service.send_all(
        [email_service.Email(to=ADDRESS, subject="s", body="b")], transport=transport
    )

    assert seen == []


async def test_a_rejected_send_is_logged_not_raised(monkeypatch, caplog):
    monkeypatch.setattr(get_settings(), "resend_api_key", "re_test")
    transport = httpx.MockTransport(lambda _r: httpx.Response(403, json={"message": "no"}))

    await email_service.send_all(
        [email_service.Email(to=ADDRESS, subject="s", body="b")], transport=transport
    )

    assert "rejected (403)" in caplog.text


# --- the endpoint -------------------------------------------------------------


async def test_the_check_endpoint_sends_after_commit(
    session, instance, hod, with_email, monkeypatch
):
    """The only path that sends. An admin is used because the class is in the past."""
    sent: list[list[email_service.Email]] = []

    async def fake_send_all(emails):
        sent.append(emails)

    async def override_session():
        yield session

    monkeypatch.setattr(email_service, "send_all", fake_send_all)
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = lambda: hod
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                f"/api/v1/checking/{instance.id}", json={"outcome": "TEACHER_NOT_FOUND"}
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    assert [[e.to for e in batch] for batch in sent] == [[ADDRESS]]
    assert email_service.take(session) == []


# --- the faculty directory ----------------------------------------------------


async def test_reloading_the_directory_fills_in_missing_emails(session, tmp_path):
    session.add(Teacher(initial="OLD", name="Already Loaded", department="cse"))
    await session.flush()
    path = tmp_path / "teachers.json"
    path.write_text(
        json.dumps(
            [
                {"Name_Initial": "Already Loaded (OLD)", "Email": " old@diu.edu.bd "},
                {"Name_Initial": "Trailing Comma (TCM)", "Email": "tcm@diu.edu.bd,"},
                {"Name_Initial": "No Address (NOA)", "Email": "Undefined"},
            ]
        )
    )

    added, filled = await _load_teachers(session, path)

    emails = dict((await session.execute(select(Teacher.initial, Teacher.email))).all())
    assert (added, filled) == (2, 1)
    assert emails == {"OLD": "old@diu.edu.bd", "TCM": "tcm@diu.edu.bd", "NOA": None}

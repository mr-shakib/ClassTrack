"""Students: their routine by section, what changes in it, and what is written to them.

Students have no accounts, so everything they read is public. What they read is
what the timetable on the wall would say: monitoring -- whether the teacher
came, came late, or was reported absent -- never reaches them.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import httpx
import pytest
from sqlalchemy import select
from tests.conftest import SLOT, at

from classtrack.api.deps import get_current_user
from classtrack.core.errors import ValidationError
from classtrack.db.session import get_session
from classtrack.main import app
from classtrack.models import (
    CheckOutcome,
    ClassInstance,
    ClassSession,
    ClassStatus,
    Holiday,
    MakeupMode,
    NoticeKind,
    Routine,
    Semester,
    StudentNotice,
    Teacher,
)
from classtrack.services import (
    check_service,
    extra_class_service,
    makeup_service,
    push_service,
    status_engine,
    student_service,
    sweep,
)

DAY = date(2026, 9, 13)
LATER = date(2026, 9, 20)
FREE_SLOT = "04:00-05:30"
DASH = "\N{EN DASH}"


@pytest.fixture(autouse=True)
def _clock(monkeypatch):
    """The afternoon of the fixture class, so LATER is still to come."""
    monkeypatch.setattr(status_engine, "now_local", lambda: at(12, 0))


@pytest.fixture
def sink(monkeypatch) -> list[list[object]]:
    """What each commit handed the push sender."""
    handed: list[list[object]] = []
    monkeypatch.setattr(push_service, "_sink", handed.append)
    return handed


def _topic_pushes(sink) -> list[push_service.TopicPush]:
    return [p for batch in sink for p in batch if isinstance(p, push_service.TopicPush)]


@pytest.fixture
async def routine(session, instance):
    """70_A's theory class (the fixture), its two lab groups, and two retake group As."""
    found = await session.scalar(select(Routine).where(Routine.is_active))
    semester = await session.scalar(select(Semester).where(Semester.is_active))
    session.add(
        Teacher(initial="TCB", name="Teacher B", designation="Lecturer", office_room="KT-801")
    )
    rows = [
        ("CSE312(70_A1)", "70_A1", "TCA", "08:30-10:00", 510, 600, "KT-601"),
        ("CSE312(70_A2)", "70_A2", "TCB", "08:30-10:00", 510, 600, "KT-602"),
        ("CSE447(RE_A)", "RE_A", "TCA", "11:30-01:00", 690, 780, "KT-701"),
        ("CSE448(RE_A)", "RE_A", "TCB", "01:00-02:30", 780, 870, "KT-702"),
    ]
    for code, section, teacher, slot, start, end, room in rows:
        batch = section[:-1] if section[-1].isdigit() else section
        sess = ClassSession(
            routine_id=found.id,
            day="Sunday",
            time_slot=slot,
            room=room,
            room_type="Lab" if section.endswith(("1", "2")) else "Theory",
            course_code=code,
            teacher=teacher,
            batch=batch,
            section=section,
            is_lab=section.endswith(("1", "2")),
            start_min=start,
            end_min=end,
        )
        session.add(sess)
        await session.flush()
        session.add(
            ClassInstance(
                session_id=sess.id,
                semester_id=semester.id,
                date=DAY,
                day="Sunday",
                time_slot=slot,
                start_min=start,
                end_min=end,
                room=room,
                room_type=sess.room_type,
                course_code=code,
                section=section,
                batch=batch,
                teacher_initial=teacher,
            )
        )
    await session.flush()
    return instance


async def _get(session, path: str, user=None) -> httpx.Response:
    return await _call(session, "GET", path, user=user)


async def _call(session, method: str, path: str, *, user=None, body=None) -> httpx.Response:
    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.request(method, f"/api/v1{path}", json=body)
    finally:
        app.dependency_overrides.clear()


async def _make_missed(session, instance, staff):
    await check_service.submit(
        session,
        instance_id=instance.id,
        user=staff,
        outcome=CheckOutcome.TEACHER_NOT_FOUND,
        now=at(10, 5),
    )
    await sweep.sweep_once(session, now=at(10, 31))
    assert instance.status is ClassStatus.MISSED


# --- groups ----------------------------------------------------------------------


def test_groups_are_sections_lab_groups_and_retakes_of_a_course():
    assert student_service.parse_groups(" 70_a1, CSE447:re_a,70_A1 ") == ["70_A1", "CSE447:RE_A"]
    with pytest.raises(ValidationError, match="belongs to its course"):
        student_service.parse_groups("RE_A")
    with pytest.raises(ValidationError, match="not a section"):
        student_service.parse_groups("*")
    with pytest.raises(ValidationError):
        student_service.parse_groups("70_A;DROP")
    assert student_service.parse_groups("*,70", allow_wide=True) == ["*", "70"]


def test_a_lab_group_brings_its_section_and_its_intake():
    assert student_service.expand(["70_A1", "CSE447:RE_A1"]) == [
        "70_A1",
        "70_A",
        "CSE447:RE_A1",
        "CSE447:RE_A",
    ]
    assert student_service.feed_tokens(["70_A1"]) == ["*", "70", "70_A1", "70_A"]
    # A notice to a section reaches its lab groups already; to an intake, its sections.
    assert student_service.collapse(["70_A", "70_A1", "71_B"]) == ["70_A", "71_B"]
    assert student_service.collapse(["70", "70_A", "71_B1"]) == ["70", "71_B1"]
    assert student_service.collapse(["70_A", "*"]) == ["*"]


def test_topics_are_named_for_firebase():
    topics = student_service.topics_for("cse", ["70_A1", "CSE447:RE_A"])
    assert topics["alerts"] == [
        "cse.all",
        "cse.70",
        "cse.70_A1",
        "cse.70_A",
        "cse.CSE447-RE_A",
    ]
    assert topics["reminders"] == ["cse.rem.70_A1", "cse.rem.70_A", "cse.rem.CSE447-RE_A"]


async def test_the_directory_lists_sections_with_their_lab_groups_and_retakes(session, routine):
    response = await _get(session, "/students/directory")
    assert response.status_code == 200
    body = response.json()
    assert body["semester"] == "Fall 2026"
    assert body["sections"] == [
        {"section": "70_A", "intake": "70", "lab_groups": ["70_A1", "70_A2"]}
    ]
    assert [r["course_code"] for r in body["retakes"]] == ["CSE447", "CSE448"]
    assert body["retakes"][0]["groups"][0]["token"] == "CSE447:RE_A"


# --- classes -----------------------------------------------------------------------


async def _classes(session, groups: str, day: date = DAY, until: date | None = None) -> list[dict]:
    response = await _get(
        session, f"/students/classes?groups={groups}&from={day}&to={until or day}"
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_a_student_sees_their_section_their_lab_group_and_their_retakes(session, routine):
    rows = await _classes(session, "70_A1,CSE447:RE_A")
    assert [(r["course_code"], r["section"]) for r in rows] == [
        ("CSE312", "70_A1"),
        ("CSE311", "70_A"),
        ("CSE447", "RE_A"),
    ]
    # Not the other lab group, and not another course's retake group A.
    first = rows[0]
    assert first["kind"] == "CLASS" and first["state"] == "SCHEDULED"
    assert first["room"] == "KT-601" and first["online"] is False
    assert first["teacher"]["initial"] == "TCA"
    assert first["teacher"]["name"] == "Teacher A"


async def test_the_teacher_card_never_carries_their_email(session, routine):
    teacher = await session.scalar(select(Teacher).where(Teacher.initial == "TCA"))
    teacher.email = "private@diu.edu.bd"
    await session.flush()

    response = await _get(session, f"/students/classes?groups=70_A&from={DAY}&to={DAY}")
    assert "private@diu.edu.bd" not in response.text
    assert set(response.json()[0]["teacher"]) == {
        "initial",
        "name",
        "designation",
        "office_room",
        "photo_url",
    }


async def test_monitoring_never_reaches_students(session, routine, staff):
    """A class staff reported the teacher absent from reads as any other class."""
    await _make_missed(session, routine, staff)
    late = await session.scalar(select(ClassInstance).where(ClassInstance.section == "70_A1"))
    await check_service.submit(
        session,
        instance_id=late.id,
        user=staff,
        outcome=CheckOutcome.LATE,
        arrival_time=at(8, 50).time(),
        now=at(8, 50),
    )
    await session.commit()

    response = await _get(session, f"/students/classes?groups=70_A1&from={DAY}&to={DAY}")
    text = response.text
    for word in ("MISSED", "LATE", "TEACHER_NOT_FOUND", "late_minutes", "check", "NOT_CHECKED"):
        assert word not in text, word
    assert {r["state"] for r in response.json()} == {"SCHEDULED"}


async def test_a_long_range_is_refused(session, routine):
    response = await _get(
        session, f"/students/classes?groups=70_A&from={DAY}&to={DAY + timedelta(days=60)}"
    )
    assert response.status_code == 422


# --- what changes, told to the section -------------------------------------------------


async def _notices(session, groups: str) -> list[dict]:
    response = await _get(session, f"/students/notices?groups={groups}")
    assert response.status_code == 200, response.text
    return response.json()


async def test_a_makeup_moves_the_class_and_tells_its_section(
    session, routine, staff, teacher_user, sink
):
    await _make_missed(session, routine, staff)
    makeup = await makeup_service.create(
        session,
        original_instance_id=routine.id,
        user=teacher_user,
        mode=MakeupMode.PHYSICAL,
        on=LATER,
        time_slot=FREE_SLOT,
        room="KT-305",
    )
    await session.commit()

    [moved] = [r for r in await _classes(session, "70_A") if r["section"] == "70_A"]
    assert moved["state"] == "MOVED"
    assert moved["moved_to"] == {
        "date": LATER.isoformat(),
        "time_slot": FREE_SLOT,
        "room": "KT-305",
        "online": False,
    }
    [held] = await _classes(session, "70_A", LATER)
    assert held["kind"] == "MAKEUP"
    assert held["id"] == makeup.created_instance_id
    assert held["makeup_for"] == {"date": DAY.isoformat(), "time_slot": SLOT}

    # A lab-1 student of the section is told, through the section's topic.
    [notice] = await _notices(session, "70_A1")
    assert notice["kind"] == "CHANGE"
    assert notice["title"] == "CSE311 · Makeup class"
    assert f"16:00{DASH}17:30, in room KT-305" in notice["body"]
    assert "makes up the class of Sunday 13 Sep" in notice["body"]
    assert notice["about"]["id"] == makeup.created_instance_id
    [pushed] = _topic_pushes(sink)
    assert pushed.topics == ("cse.70_A",)
    assert pushed.kind == push_service.STUDENT_NOTICE
    assert "absent" not in json.dumps(notice).lower()


async def test_an_online_request_is_not_news_until_approved(
    session, routine, staff, teacher_user, hod, sink
):
    await _make_missed(session, routine, staff)
    makeup = await makeup_service.create(
        session,
        original_instance_id=routine.id,
        user=teacher_user,
        mode=MakeupMode.ONLINE,
        on=LATER,
        start_time="20:00",
        meeting_link="https://meet.google.com/abc-defg-hij",
    )
    await session.commit()

    [waiting] = [r for r in await _classes(session, "70_A") if r["section"] == "70_A"]
    assert waiting["state"] == "SCHEDULED"
    assert await _notices(session, "70_A") == []

    await makeup_service.decide(session, makeup_id=makeup.id, user=hod, approve=True)
    await session.commit()

    [online] = await _classes(session, "70_A", LATER)
    assert online["online"] is True and online["room"] is None
    assert online["join_link"] == "https://meet.google.com/abc-defg-hij"
    [notice] = await _notices(session, "70_A")
    assert notice["title"] == "CSE311 · Online makeup"
    assert "join link is in ClassTrack" in notice["body"]


async def test_a_join_link_added_later_is_announced_once_approved(
    session, routine, staff, teacher_user, hod
):
    await _make_missed(session, routine, staff)
    makeup = await makeup_service.create(
        session,
        original_instance_id=routine.id,
        user=teacher_user,
        mode=MakeupMode.ONLINE,
        on=LATER,
        start_time="20:00",
    )
    await makeup_service.decide(session, makeup_id=makeup.id, user=hod, approve=True)
    await session.commit()

    with pytest.raises(ValidationError):
        await makeup_service.set_meeting_link(
            session, makeup_id=makeup.id, user=teacher_user, meeting_link="not a link"
        )
    response = await _call(
        session,
        "POST",
        f"/makeup/{makeup.id}/meeting-link",
        user=teacher_user,
        body={"meeting_link": "https://zoom.us/j/123"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["meeting_link"] == "https://zoom.us/j/123"

    titles = [n["title"] for n in await _notices(session, "70_A")]
    assert titles == ["CSE311 · Join link for the online class", "CSE311 · Online makeup"]


async def test_extra_classes_and_cancellations_reach_the_section(
    session, routine, teacher_user, hod, monkeypatch
):
    monkeypatch.setattr(status_engine, "now_local", lambda: at(8, 0, day=date(2026, 9, 14)))
    extra = await extra_class_service.book(
        session,
        user=teacher_user,
        course_code="CSE311(70_A)",
        section="70_A",
        on=date(2026, 9, 15),
        time_slot=SLOT,
        room="KT-305",
    )
    await session.commit()
    await extra_class_service.cancel(session, user=teacher_user, instance_id=extra.id)
    await session.commit()

    titles = [n["title"] for n in await _notices(session, "70_A")]
    assert titles == ["CSE311 · Extra class cancelled", "CSE311 · Extra class"]
    [row] = await _classes(session, "70_A", date(2026, 9, 15))
    assert row["kind"] == "EXTRA" and row["state"] == "CANCELLED"


async def test_a_cancelled_class_is_announced_without_its_reason(
    session, routine, hod, monkeypatch
):
    monkeypatch.setattr(status_engine, "now_local", lambda: at(7, 0))
    # The route serialises the check, which the fixture's object never loaded.
    await session.refresh(routine, attribute_names=["check"])
    response = await _call(
        session,
        "POST",
        f"/instances/{routine.id}/cancel",
        user=hod,
        body={"reason": "Teacher on medical leave"},
    )
    assert response.status_code == 200, response.text
    [notice] = await _notices(session, "70_A")
    assert notice["title"] == "CSE311 · Class cancelled"
    assert "medical" not in notice["body"]


async def test_students_are_reminded_before_class_through_their_topic(session, routine, sink):
    await sweep.sweep_once(session, now=at(9, 52))
    reminders = [p for p in _topic_pushes(sink) if p.kind == push_service.STUDENT_REMINDER]
    assert [p.topics for p in reminders] == [("cse.rem.70_A",)]
    assert reminders[0].title == "CSE311 starts in 8 minutes"
    assert reminders[0].body == f"Room KT-305 · 10:00{DASH}11:30"


# --- written by people ------------------------------------------------------------------


async def test_a_teacher_writes_to_their_own_sections_only(session, routine, teacher_user, sink):
    response = await _get(session, "/teacher/notices/groups", user=teacher_user)
    assert [g["token"] for g in response.json()] == ["70_A", "70_A1", "CSE447:RE_A"]

    sent = await _call(
        session,
        "POST",
        "/teacher/notices",
        user=teacher_user,
        body={"body": "Bring your laptops on Sunday.", "targets": ["70_A", "70_A1"]},
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["title"] == "Your classes · Note from TCA"
    assert sent.json()["author"] == "Teacher A (TCA)"
    # The lab group is in the section already: one target, one push.
    assert sent.json()["targets"] == ["70_A"]
    assert [p.topics for p in _topic_pushes(sink)] == [("cse.70_A",)]

    refused = await _call(
        session,
        "POST",
        "/teacher/notices",
        user=teacher_user,
        body={"body": "Hello", "targets": ["70_A2"]},
    )
    assert refused.status_code == 403


async def test_a_heads_up_about_a_class_shows_on_it(session, routine, teacher_user, monkeypatch):
    monkeypatch.setattr(status_engine, "now_local", lambda: at(7, 0))
    sent = await _call(
        session,
        "POST",
        "/teacher/notices",
        user=teacher_user,
        body={"body": "We will have a quiz.", "instance_id": routine.id},
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["title"] == f"CSE311 · Sunday 13 Sep, 10:00{DASH}11:30"

    [row] = [r for r in await _classes(session, "70_A") if r["section"] == "70_A"]
    assert row["note"]["body"] == "We will have a quiz."

    lab_b = await session.scalar(select(ClassInstance).where(ClassInstance.section == "70_A2"))
    refused = await _call(
        session,
        "POST",
        "/teacher/notices",
        user=teacher_user,
        body={"body": "Hi", "instance_id": lab_b.id},
    )
    assert refused.status_code == 403


async def test_a_heads_up_about_a_past_class_is_refused(
    session, routine, teacher_user, monkeypatch
):
    monkeypatch.setattr(status_engine, "now_local", lambda: at(7, 0, day=DAY + timedelta(days=1)))
    refused = await _call(
        session,
        "POST",
        "/teacher/notices",
        user=teacher_user,
        body={"body": "Late note", "instance_id": routine.id},
    )
    assert refused.status_code == 422


async def test_staff_cannot_write_to_students(session, routine, staff):
    refused = await _call(
        session, "POST", "/teacher/notices", user=staff, body={"body": "Hi", "targets": ["70_A"]}
    )
    assert refused.status_code == 403


async def test_the_department_writes_to_everyone_or_to_an_intake(session, routine, hod, sink):
    sent = await _call(
        session,
        "POST",
        "/admin/notifications/students",
        user=hod,
        body={"title": "Classes resume", "body": "From Sunday.", "targets": ["70", "CSE447:RE_A"]},
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["author"] == "Department of CSE"
    # Two topics, one message: a phone following both is told once.
    [pushed] = _topic_pushes(sink)
    assert pushed.topics == ("cse.70", "cse.CSE447-RE_A")
    assert push_service._message(pushed)["condition"] == (
        "'cse.70' in topics || 'cse.CSE447-RE_A' in topics"
    )

    unknown = await _call(
        session,
        "POST",
        "/admin/notifications/students",
        user=hod,
        body={"title": "Hi", "body": "Hi", "targets": ["99_Z"]},
    )
    assert unknown.status_code == 422

    assert [n["title"] for n in await _notices(session, "70_A2")] == ["Classes resume"]
    history = await _get(session, "/admin/notifications/students", user=hod)
    assert [n["title"] for n in history.json()] == ["Classes resume"]
    assert (await session.scalar(select(StudentNotice))).kind is NoticeKind.ANNOUNCEMENT


async def test_a_teacher_may_not_write_as_the_department(session, routine, teacher_user):
    refused = await _call(
        session,
        "POST",
        "/admin/notifications/students",
        user=teacher_user,
        body={"title": "Hi", "body": "Hi", "targets": ["*"]},
    )
    assert refused.status_code == 403


# --- rooms and the calendar ------------------------------------------------------------


async def test_free_rooms_by_slot_leave_out_taken_rooms(session, routine, monkeypatch):
    monkeypatch.setattr(status_engine, "now_local", lambda: at(7, 0))
    response = await _get(session, f"/students/free-rooms?date={DAY}")
    assert response.status_code == 200, response.text
    by_slot = {s["time_slot"]: {r["room"] for r in s["rooms"]} for s in response.json()}
    assert "KT-305" not in by_slot[SLOT]
    assert "KT-305" in by_slot[FREE_SLOT]
    assert "KT-601" not in by_slot["08:30-10:00"]


async def test_a_day_without_classes_has_no_free_room_list(session, routine, monkeypatch):
    monkeypatch.setattr(status_engine, "now_local", lambda: at(7, 0))
    response = await _get(session, f"/students/free-rooms?date={DAY + timedelta(days=5)}")
    assert response.json() == []


async def test_the_calendar_shows_exams_and_holidays(session, routine):
    semester = await session.scalar(select(Semester).where(Semester.is_active))
    semester.mid_exam_start = date(2026, 10, 20)
    semester.mid_exam_end = date(2026, 10, 28)
    session.add(Holiday(semester_id=semester.id, date=date(2026, 10, 1), title="Durga Puja"))
    await session.flush()

    body = (await _get(session, "/students/calendar")).json()
    assert body["name"] == "Fall 2026"
    assert body["exams"] == [{"name": "Mid-term exams", "start": "2026-10-20", "end": "2026-10-28"}]
    assert body["holidays"] == [{"date": "2026-10-01", "title": "Durga Puja", "kind": "HOLIDAY"}]


async def test_the_topics_endpoint_names_what_to_follow(session, routine):
    body = (await _get(session, "/students/topics?groups=70_A1")).json()
    assert body["alerts"] == ["cse.all", "cse.70", "cse.70_A1", "cse.70_A"]
    assert body["reminders"] == ["cse.rem.70_A1", "cse.rem.70_A"]
    assert (await _get(session, "/students/topics?groups=RE_A")).status_code == 422

"""The semester cycle: exam periods, terms, and moving on to the next semester.

A semester runs as the university's does -- classes, mid-term exams, classes,
final exams -- and is reported on till the mid-term and from it to the final
separately. These pin the dates each term covers, the minimum it is held to,
that no class is generated or left standing in an exam period, and that the
department moves from one semester to the next only when told to.
"""

from __future__ import annotations

from datetime import date

import httpx
import pytest
from sqlalchemy import select
from tests.conftest import END_MIN, SLOT, START_MIN, at

from classtrack.api.deps import get_current_user
from classtrack.core.errors import ValidationError
from classtrack.db.session import get_session
from classtrack.main import app
from classtrack.models import (
    ClassInstance,
    ClassSession,
    ClassStatus,
    Holiday,
    Routine,
    Semester,
    Term,
)
from classtrack.services import (
    conflict_service,
    instance_service,
    pdf_service,
    report_service,
    semester_service,
    settings_service,
    status_engine,
)

#: A Tuesday, after the mid-term exams and before the finals.
TODAY = date(2026, 11, 10)

MID_START, MID_END = date(2026, 10, 24), date(2026, 10, 29)
FINAL_START = date(2026, 12, 12)


@pytest.fixture(autouse=True)
def _clock(monkeypatch):
    monkeypatch.setattr(status_engine, "now_local", lambda: at(12, 0, day=TODAY))


def _fall(**changes) -> Semester:
    fields = {
        "name": "Fall 2026",
        "department": "cse",
        "start_date": date(2026, 9, 1),
        "end_date": date(2026, 12, 31),
        "mid_exam_start": MID_START,
        "mid_exam_end": MID_END,
        "final_exam_start": FINAL_START,
        "is_active": True,
    }
    fields.update(changes)
    return Semester(**fields)


async def _sunday_routine(session, *, version: str = "F1", active: bool = True) -> Routine:
    """One class, every Sunday."""
    routine = Routine(department="cse", version=version, is_active=active, session_count=1)
    session.add(routine)
    await session.flush()
    session.add(
        ClassSession(
            routine_id=routine.id,
            day="Sunday",
            time_slot=SLOT,
            room="KT-305",
            course_code="CSE311(70_A)",
            teacher="TCA",
            batch="70_A",
            section="70_A",
            start_min=START_MIN,
            end_min=END_MIN,
        )
    )
    await session.flush()
    return routine


async def _class_dates(session, semester_id: int) -> list[date]:
    return sorted(
        (
            await session.scalars(
                select(ClassInstance.date).where(ClassInstance.semester_id == semester_id)
            )
        ).all()
    )


# --- terms ---------------------------------------------------------------------


def test_the_exams_split_the_semester_into_terms():
    fall = _fall()
    assert fall.term_range(Term.MID) == (date(2026, 9, 1), date(2026, 10, 23))
    assert fall.term_range(Term.FINAL) == (date(2026, 10, 30), date(2026, 12, 11))
    assert fall.term_range(Term.FULL) == (date(2026, 9, 1), date(2026, 12, 31))


def test_a_term_waits_for_the_exam_dates_it_needs():
    undated = _fall(mid_exam_start=None, mid_exam_end=None, final_exam_start=None)
    assert undated.term_range(Term.MID) is None
    assert undated.term_range(Term.FINAL) is None
    assert undated.term_range(Term.FULL) == (date(2026, 9, 1), date(2026, 12, 31))

    # Final exams not announced yet: the second term runs to the semester's end.
    no_finals = _fall(final_exam_start=None)
    assert no_finals.term_range(Term.FINAL) == (date(2026, 10, 30), date(2026, 12, 31))


def test_exam_days_run_from_the_finals_to_the_semester_end():
    fall = _fall()
    assert fall.in_exams(MID_START) and fall.in_exams(MID_END)
    assert not fall.in_exams(date(2026, 10, 23)) and not fall.in_exams(date(2026, 10, 30))
    assert not fall.in_exams(date(2026, 12, 11))
    assert fall.in_exams(FINAL_START) and fall.in_exams(date(2026, 12, 31))


async def test_a_term_reports_what_has_happened_so_far(session):
    session.add(_fall())
    await session.flush()

    period = await semester_service.term_period(
        session, semester_id=None, term=Term.FINAL, today=TODAY
    )
    assert (period.start, period.end) == (date(2026, 10, 30), TODAY)
    assert period.label == "Fall 2026 · Mid-term to final"
    assert period.term is Term.FINAL

    with pytest.raises(ValidationError, match="has not begun"):
        await semester_service.term_period(
            session, semester_id=None, term=Term.FINAL, today=date(2026, 10, 1)
        )


async def test_a_term_without_its_exam_dates_is_refused(session):
    fall = _fall(mid_exam_start=None, mid_exam_end=None)
    session.add(fall)
    await session.flush()

    with pytest.raises(ValidationError, match="mid-term exam dates"):
        await semester_service.term_period(
            session, semester_id=fall.id, term=Term.MID, today=TODAY
        )
    terms = {t["term"]: t for t in semester_service.terms(fall, TODAY)}
    assert not terms[Term.MID]["available"]
    assert terms[Term.FULL]["available"]


# --- the minimum, per term -----------------------------------------------------


async def test_each_term_is_held_to_its_share_of_the_minimum(session):
    assert await report_service.min_conducted(session) == 18
    assert await report_service.min_conducted(session, Term.FULL) == 18
    assert await report_service.min_conducted(session, Term.MID) == 9
    assert await report_service.min_conducted(session, Term.FINAL) == 9

    await settings_service.set_value(session, "min_conducted_before_mid", "12")
    await session.flush()
    assert await report_service.min_conducted(session, Term.MID) == 12
    assert await report_service.min_conducted(session, Term.FINAL) == 6


async def test_a_term_report_flags_a_course_against_the_term_minimum(session, instance):
    instance.status = ClassStatus.RUNNING
    await settings_service.set_value(session, "min_conducted_before_mid", "1")
    await session.flush()

    mid = await report_service.overview(
        session,
        start=date(2026, 9, 1),
        end=date(2026, 10, 23),
        term=Term.MID,
        label="Fall 2026 · Till mid-term",
    )
    assert mid["min_conducted"] == 1
    assert mid["label"] == "Fall 2026 · Till mid-term"
    assert not mid["by_course"][0]["below_minimum"]

    # The same class, held to the whole semester's minimum.
    whole = await report_service.overview(session, start=date(2026, 9, 1), end=TODAY)
    assert whole["by_course"][0]["below_minimum"]

    teacher = await report_service.teacher_report(
        session, teacher_initial="TCA", start=date(2026, 9, 1), end=date(2026, 10, 23),
        term=Term.MID, label="Fall 2026 · Till mid-term",
    )
    assert not teacher["flagged"]
    assert pdf_service.teacher_pdf(teacher).startswith(b"%PDF")
    assert pdf_service.summary_pdf(mid).startswith(b"%PDF")


# --- no classes in the exams ---------------------------------------------------


async def test_generation_skips_both_exam_periods(session):
    routine = await _sunday_routine(session)
    fall = _fall(routine_id=routine.id)
    session.add(fall)
    await session.flush()

    result = await instance_service.generate(session, semester_id=fall.id)
    dates = await _class_dates(session, fall.id)

    # 17 Sundays, less 25 Oct (mid-term) and 13, 20, 27 Dec (finals).
    assert len(dates) == 13
    assert not any(fall.in_exams(d) for d in dates)
    assert max(dates) == date(2026, 12, 6)
    assert result["skipped_exam_days"] > 0


async def test_exam_dates_set_later_retire_only_future_unmonitored_classes(session):
    routine = await _sunday_routine(session)
    fall = _fall(
        routine_id=routine.id, mid_exam_start=None, mid_exam_end=None, final_exam_start=None
    )
    session.add(fall)
    await session.flush()
    await instance_service.generate(session, semester_id=fall.id)
    assert len(await _class_dates(session, fall.id)) == 17

    cancelled = await session.scalar(
        select(ClassInstance).where(ClassInstance.date == date(2026, 12, 20))
    )
    cancelled.status = ClassStatus.CANCELLED

    fall.mid_exam_start, fall.mid_exam_end = MID_START, MID_END
    fall.final_exam_start = FINAL_START
    await session.flush()
    result = await instance_service.generate(session, semester_id=fall.id)
    dates = await _class_dates(session, fall.id)

    assert result["instances_retired_days_off"] == 2
    assert date(2026, 12, 13) not in dates and date(2026, 12, 27) not in dates
    # The past is a record, not a schedule; a monitored class is a fact.
    assert date(2026, 10, 25) in dates
    assert date(2026, 12, 20) in dates


async def test_a_holiday_added_after_generation_clears_its_day(session):
    routine = await _sunday_routine(session)
    fall = _fall(routine_id=routine.id)
    session.add(fall)
    await session.flush()
    await instance_service.generate(session, semester_id=fall.id)

    session.add(Holiday(semester_id=fall.id, date=date(2026, 11, 22), title="Closure"))
    await session.flush()
    await instance_service.generate(session, semester_id=fall.id)

    assert date(2026, 11, 22) not in await _class_dates(session, fall.id)


async def test_no_makeup_is_booked_into_the_exams(session, instance):
    fall = await session.get(Semester, instance.semester_id)
    fall.mid_exam_start, fall.mid_exam_end = MID_START, MID_END
    await session.flush()

    during = await conflict_service.check(
        session, on=date(2026, 10, 25), time_slot="04:00-05:30", teacher_initial="TCA"
    )
    assert [c.type for c in during.conflicts] == ["EXAM"]
    assert "mid-term" in during.conflicts[0].message

    after = await conflict_service.check(
        session, on=date(2026, 11, 1), time_slot="04:00-05:30", teacher_initial="TCA"
    )
    assert after.ok


# --- one semester after another -----------------------------------------------


async def test_semesters_must_not_overlap_or_put_their_exams_out_of_order(session):
    session.add(_fall())
    await session.flush()

    def spring(**changes) -> Semester:
        fields = {
            "name": "Spring 2027",
            "department": "cse",
            "start_date": date(2027, 1, 10),
            "end_date": date(2027, 4, 30),
        }
        fields.update(changes)
        return Semester(**fields)

    with pytest.raises(ValidationError, match="overlaps Fall 2026"):
        await semester_service.validate(session, spring(start_date=date(2026, 12, 20)))
    await semester_service.validate(session, spring())

    out_of_order = [
        {"mid_exam_start": date(2027, 3, 1)},
        {"mid_exam_start": date(2027, 1, 10), "mid_exam_end": date(2027, 1, 15)},
        {"mid_exam_start": date(2027, 3, 6), "mid_exam_end": date(2027, 3, 1)},
        {
            "mid_exam_start": date(2027, 3, 1),
            "mid_exam_end": date(2027, 3, 6),
            "final_exam_start": date(2027, 3, 5),
        },
        {"final_exam_start": date(2027, 5, 1)},
    ]
    for changes in out_of_order:
        with pytest.raises(ValidationError):
            await semester_service.validate(session, spring(**changes))


async def test_making_a_semester_current_brings_its_routine_live(session):
    fall_routine = await _sunday_routine(session, version="F1", active=True)
    spring_routine = await _sunday_routine(session, version="S1", active=False)
    fall = _fall(routine_id=fall_routine.id)
    spring = Semester(
        name="Spring 2027",
        department="cse",
        routine_id=spring_routine.id,
        start_date=date(2027, 1, 10),
        end_date=date(2027, 4, 30),
        is_active=False,
    )
    session.add_all([fall, spring])
    await session.flush()

    await semester_service.make_current(session, spring)
    await session.flush()
    for row in (fall, spring, fall_routine, spring_routine):
        await session.refresh(row)

    assert spring.is_active and not fall.is_active
    assert spring_routine.is_active and not fall_routine.is_active
    assert (await semester_service.current(session)).id == spring.id


# --- the endpoints -------------------------------------------------------------


@pytest.fixture
async def client(session):
    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


def _as(user) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


async def test_the_next_semester_is_set_up_ahead_and_made_current_later(
    session, client, hod
):
    routine = await _sunday_routine(session)
    session.add(_fall(routine_id=routine.id, mid_exam_start=None, mid_exam_end=None,
                      final_exam_start=None))
    await session.flush()
    _as(hod)

    created = await client.post(
        "/api/v1/admin/semesters",
        json={"name": " Spring 2027 ", "start_date": "2027-01-10", "end_date": "2027-04-30"},
    )
    assert created.status_code == 200, created.text
    spring = created.json()
    assert spring["name"] == "Spring 2027"
    assert spring["is_active"] is False
    assert (await semester_service.current(session)).name == "Fall 2026"

    overlapping = await client.post(
        "/api/v1/admin/semesters",
        json={"name": "Clash", "start_date": "2026-12-01", "end_date": "2027-02-01"},
    )
    assert overlapping.status_code == 422

    switched = await client.post(f"/api/v1/admin/semesters/{spring['id']}/activate")
    assert switched.status_code == 200, switched.text
    assert (await semester_service.current(session)).name == "Spring 2027"


async def test_setting_exam_dates_applies_them_to_the_schedule(session, client, hod):
    routine = await _sunday_routine(session)
    fall = _fall(routine_id=routine.id, mid_exam_start=None, mid_exam_end=None,
                 final_exam_start=None)
    session.add(fall)
    await session.flush()
    await instance_service.generate(session, semester_id=fall.id)
    _as(hod)

    response = await client.put(
        f"/api/v1/admin/semesters/{fall.id}",
        json={
            "name": "Fall 2026",
            "start_date": "2026-09-01",
            "end_date": "2026-12-31",
            "mid_exam_start": MID_START.isoformat(),
            "mid_exam_end": MID_END.isoformat(),
            "final_exam_start": FINAL_START.isoformat(),
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["semester"]["final_exam_start"] == "2026-12-12"
    # 13, 20 and 27 December. 25 October is past.
    assert body["generation"]["instances_retired_days_off"] == 3


async def test_a_teacher_reports_on_a_term_of_their_own(session, client, teacher_user, hod):
    routine = await _sunday_routine(session)
    fall = _fall(routine_id=routine.id)
    session.add(fall)
    await session.flush()
    await instance_service.generate(session, semester_id=fall.id)

    _as(teacher_user)
    listed = await client.get("/api/v1/reports/semesters")
    assert listed.status_code == 200, listed.text
    terms = {t["term"]: t for t in listed.json()[0]["terms"]}
    assert terms["MID"] == {
        "term": "MID", "label": "Till mid-term",
        "from": "2026-09-01", "to": "2026-10-23", "available": True,
    }

    report = await client.get(
        "/api/v1/reports/teacher", params={"semester": fall.id, "term": "MID"}
    )
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["range"] == {"from": "2026-09-01", "to": "2026-10-23"}
    assert body["label"] == "Fall 2026 · Till mid-term"
    assert body["min_conducted"] == 9

    _as(hod)
    overview = await client.get(
        "/api/v1/reports/overview", params={"semester": fall.id, "term": "FINAL"}
    )
    assert overview.status_code == 200, overview.text
    assert overview.json()["range"] == {"from": "2026-10-30", "to": TODAY.isoformat()}
    pdf = await client.get(
        "/api/v1/reports/overview/pdf", params={"semester": fall.id, "term": "FINAL"}
    )
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")

"""Reports: one outcome per class, the minimum-classes rule, reschedules, PDFs.

The makeup tests pin the rule most easily broken by a later change: a class
recovered by a makeup is credited once, on the day it was held -- never on both
the missed date and the makeup date.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from tests.conftest import END_MIN, SLOT, START_MIN, at

from classtrack.models import (
    CheckOutcome,
    ClassInstance,
    ClassStatus,
    MakeupMode,
)
from classtrack.services import (
    check_service,
    checking_service,
    makeup_service,
    pdf_service,
    report_service,
    settings_service,
    status_engine,
    sweep,
)

LATER = date(2026, 9, 20)
FREE_SLOT = "04:00-05:30"
RANGE = {"start": date(2026, 9, 1), "end": date(2026, 9, 30)}


@pytest.fixture(autouse=True)
def _clock(monkeypatch):
    monkeypatch.setattr(status_engine, "now_local", lambda: at(12, 0, day=date(2026, 9, 25)))


def _copy(instance: ClassInstance, **changes) -> ClassInstance:
    """Another routine class for the same course, on another date or slot."""
    fields = {
        "session_id": instance.session_id,
        "semester_id": instance.semester_id,
        "date": instance.date,
        "day": instance.day,
        "time_slot": SLOT,
        "start_min": START_MIN,
        "end_min": END_MIN,
        "room": instance.room,
        "course_code": instance.course_code,
        "section": instance.section,
        "batch": instance.batch,
        "teacher_initial": instance.teacher_initial,
    }
    fields.update(changes)
    # A second instance of one session on one date would break the unique key.
    fields["session_id"] = None
    return ClassInstance(**fields)


async def _makeup_held(session, instance, staff, teacher_user, hod):
    """Miss the class, reschedule it into a room, approve it and hold it."""
    await check_service.submit(
        session, instance_id=instance.id, user=staff,
        outcome=CheckOutcome.TEACHER_NOT_FOUND, now=at(10, 5),
    )
    await sweep.sweep_once(session, now=at(10, 31))
    makeup = await makeup_service.create(
        session, original_instance_id=instance.id, user=teacher_user,
        mode=MakeupMode.PHYSICAL, on=LATER, time_slot=FREE_SLOT, room="KT-305",
        now=at(12, 0),
    )
    await makeup_service.decide(
        session, makeup_id=makeup.id, user=hod, approve=True, now=at(12, 5)
    )
    await check_service.submit(
        session, instance_id=makeup.created_instance_id, user=staff,
        outcome=CheckOutcome.RUNNING, now=at(16, 5, day=LATER),
    )
    await makeup_service.complete(
        session, makeup_id=makeup.id, user=teacher_user, now=at(18, 0, day=LATER)
    )
    await session.flush()
    return makeup


# --- classification ------------------------------------------------------------


async def test_every_status_falls_in_one_outcome(instance):
    cases = {
        ClassStatus.RUNNING: report_service.CONDUCTED,
        ClassStatus.LATE: report_service.LATE,
        ClassStatus.MISSED: report_service.MISSED,
        ClassStatus.NOT_CHECKED: report_service.NOT_CHECKED,
        ClassStatus.MAKEUP_SCHEDULED: report_service.RESCHEDULED,
        ClassStatus.MAKEUP_COMPLETED: report_service.RESCHEDULED,
        ClassStatus.ONLINE_REJECTED: report_service.MISSED,
        ClassStatus.CANCELLED: report_service.CANCELLED,
        None: report_service.PENDING,
    }
    for status, outcome in cases.items():
        instance.status = status
        assert report_service.classify(instance) == outcome, status


async def test_online_makeup_counts_once_marked_done(instance):
    instance.is_makeup = True
    instance.status = ClassStatus.ONLINE_APPROVED
    assert report_service.classify(instance) == report_service.PENDING
    assert report_service.classify(instance, makeup_done=True) == report_service.CONDUCTED


async def test_a_recovered_class_is_credited_once_on_the_makeup_day(
    session, instance, staff, teacher_user, hod
):
    makeup = await _makeup_held(session, instance, staff, teacher_user, hod)

    report = await report_service.teacher_report(
        session, teacher_initial="TCA", **RANGE
    )
    # One routine class, missed and moved; one makeup, held. Not two held classes.
    assert report["total_scheduled"] == 1
    assert report["conducted"] == 1
    assert report["rescheduled"] == 1
    assert report["missed"] == 0

    by_id = {c["instance_id"]: c for c in report["classes"]}
    original = by_id[instance.id]
    assert original["outcome"] == report_service.RESCHEDULED
    assert original["rescheduled_to"]["date"] == LATER
    held = by_id[makeup.created_instance_id]
    assert held["is_makeup"] is True
    assert held["outcome"] == report_service.CONDUCTED
    assert held["rescheduled_from"]["date"] == instance.date


async def test_a_makeup_is_listed_on_the_day_it_is_held(
    session, instance, staff, teacher_user, hod
):
    makeup = await _makeup_held(session, instance, staff, teacher_user, hod)

    day = await report_service.daily(session, on=LATER)
    assert [c["instance_id"] for c in day["rescheduled_in"]] == [makeup.created_instance_id]
    assert day["rescheduled_in"][0]["rescheduled_from"]["date"] == instance.date
    assert day["totals"]["held"] == 1

    status = await checking_service.day_status(session, on=LATER)
    row = status["rows"][0]
    assert row["is_makeup"] is True
    assert row["rescheduled_from"]["time_slot"] == SLOT


# --- the minimum-classes rule ----------------------------------------------------


async def test_a_course_below_the_minimum_is_flagged(session, instance, staff):
    await settings_service.set_value(session, "min_conducted_classes", "3")
    for offset in range(1, 3):
        session.add(_copy(instance, date=instance.date + timedelta(days=offset * 7),
                          status=ClassStatus.RUNNING))
    instance.status = ClassStatus.RUNNING
    await session.flush()

    report = await report_service.teacher_report(session, teacher_initial="TCA", **RANGE)
    assert report["min_conducted"] == 3
    assert report["courses"][0]["held"] == 3
    assert report["courses"][0]["below_minimum"] is False
    assert report["flagged"] is False

    await settings_service.set_value(session, "min_conducted_classes", "4")
    overview = await report_service.overview(session, **RANGE)
    assert overview["by_course"][0]["below_minimum"] is True
    teacher = overview["by_teacher"][0]
    assert teacher["flagged"] is True
    assert teacher["courses_below_minimum"] == 1


async def test_the_minimum_defaults_to_eighteen(session):
    assert await report_service.min_conducted(session) == 18


# --- breakdowns and filters ------------------------------------------------------


async def test_overview_breaks_down_by_floor_and_filters(session, instance):
    instance.status = ClassStatus.RUNNING
    session.add(_copy(instance, room="AB4-601", status=ClassStatus.MISSED))
    session.add(_copy(instance, room="AB4-602", teacher_initial="OTH",
                      status=ClassStatus.NOT_CHECKED))
    await session.flush()

    overview = await report_service.overview(session, **RANGE)
    floors = {f["key"]: f for f in overview["by_floor"]}
    assert floors["KT-3"]["held"] == 1
    assert floors["AB4-6"]["missed"] == 1
    assert floors["AB4-6"]["not_checked"] == 1
    assert overview["totals"]["total"] == 3

    only_floor = await report_service.overview(
        session, **RANGE, filters=report_service.Filters(floor="AB4-6")
    )
    assert only_floor["totals"]["total"] == 2

    only_teacher = await report_service.overview(
        session, **RANGE, filters=report_service.Filters(teacher="oth")
    )
    assert [t["teacher_initial"] for t in only_teacher["by_teacher"]] == ["OTH"]


async def test_a_long_range_is_bucketed_by_week(session, instance):
    overview = await report_service.overview(
        session, start=date(2026, 9, 1), end=date(2026, 12, 31)
    )
    assert overview["granularity"] == "week"
    # 13 September 2026 is a Sunday; its week starts on Saturday the 12th.
    assert overview["trend"][0]["date"] == date(2026, 9, 12)


# --- search and PDFs -------------------------------------------------------------


async def test_classes_can_be_found_by_teacher_initial(session, instance):
    session.add(_copy(instance, teacher_initial="OTH"))
    await session.flush()

    rows = await checking_service.search_by_teacher(
        session, teacher_initial="tca", start=RANGE["start"], end=RANGE["end"]
    )
    assert [r["instance_id"] for r in rows] == [instance.id]
    assert rows[0]["date"] == instance.date
    assert rows[0]["slot_state"] == "CLOSED"


async def test_pdfs_render(session, instance, staff, teacher_user, hod):
    await _makeup_held(session, instance, staff, teacher_user, hod)
    instance_row = await report_service.teacher_report(session, teacher_initial="TCA", **RANGE)
    assert pdf_service.teacher_pdf(instance_row).startswith(b"%PDF")

    overview = await report_service.overview(session, **RANGE)
    assert pdf_service.summary_pdf(overview).startswith(b"%PDF")


async def test_pdf_escapes_markup_in_remarks(session, instance, staff):
    await check_service.submit(
        session, instance_id=instance.id, user=staff, outcome=CheckOutcome.RUNNING,
        remark="<b>unclosed & odd", now=at(10, 5),
    )
    report = await report_service.teacher_report(session, teacher_initial="TCA", **RANGE)
    assert pdf_service.teacher_pdf(report).startswith(b"%PDF")


async def test_not_checked_never_lowers_a_teachers_conduct_rate(session, instance):
    instance.status = ClassStatus.RUNNING
    session.add(_copy(instance, date=instance.date + timedelta(days=7),
                      status=ClassStatus.NOT_CHECKED))
    await session.flush()

    report = await report_service.teacher_report(session, teacher_initial="TCA", **RANGE)
    assert report["not_checked"] == 1
    assert report["conduct_rate"] == 100.0

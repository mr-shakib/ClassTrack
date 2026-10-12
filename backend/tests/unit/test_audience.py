"""Which classes share students: a section with its lab groups, and a retake
group with nothing but its own course."""

from __future__ import annotations

from datetime import date

import pytest

from classtrack.api.v1.routes.admin import _scan_conflicts
from classtrack.models import ClassInstance, ClassSession
from classtrack.routine.audience import share_students
from classtrack.services import conflict_service

LATER = date(2026, 9, 20)
SLOT = "04:00-05:30"


@pytest.mark.parametrize(
    ("a", "b", "shared"),
    [
        (("CSE315(66_B)", "66_B"), ("CSE322(66_B)", "66_B"), True),
        # The whole section includes each of its lab groups...
        (("CSE315(66_B)", "66_B"), ("CSE322(66_B1)", "66_B1"), True),
        # ...but two lab groups are different students.
        (("CSE322(66_B1)", "66_B1"), ("CSE324(66_B2)", "66_B2"), False),
        (("CSE322(66_B1)", "66_B1"), ("CSE324(66_B1)", "66_B1"), True),
        (("CSE315(66_B)", "66_B"), ("CSE315(66_C)", "66_C"), False),
        (("CSE315(66_B)", "66_B"), ("CSE315(67_B)", "67_B"), False),
        # Every course with a retake has a group A: they are not the same students.
        (("CSE447(RE_A)", "RE_A"), ("CSE491(RE_A)", "RE_A"), False),
        (("CSE213(RE_A(3C))", "RE_A"), ("CSE213(RE_A1(1.5C))", "RE_A1"), True),
        (("CSE213(RE_A)", "RE_A"), ("CSE213(RE_B)", "RE_B"), False),
        # Who sits a retake is not on the routine, so it is never claimed.
        (("CSE213(RE_A)", "RE_A"), ("CSE315(66_B)", "66_B"), False),
        (("CSE315(66_B)", ""), ("CSE322(66_B)", ""), False),
    ],
)
def test_who_shares_students(a, b, shared):
    assert share_students(*a, *b) is shared
    assert share_students(*b, *a) is shared


def _session(course_code: str, section: str, room: str) -> ClassSession:
    return ClassSession(
        day="Sunday",
        time_slot=SLOT,
        room=room,
        course_code=course_code,
        teacher=room[-3:],
        batch=section,
        section=section,
    )


def test_routine_review_flags_only_classes_sharing_students():
    found = _scan_conflicts(
        [
            _session("CSE447(RE_A)", "RE_A", "KT-301"),
            _session("CSE491(RE_A)", "RE_A", "KT-302"),
            _session("CSE322(66_B1)", "66_B1", "KT-303"),
            _session("CSE324(66_B2)", "66_B2", "KT-304"),
            _session("CSE315(66_B)", "66_B", "KT-305"),
        ]
    )
    sections = sorted(c["message"] for c in found if c["type"] == "SECTION")
    assert sections == [
        "CSE322(66_B1) and CSE315(66_B) share students on Sunday at 04:00-05:30.",
        "CSE324(66_B2) and CSE315(66_B) share students on Sunday at 04:00-05:30.",
    ]


def _occupant(instance, course_code: str, section: str, room: str) -> ClassInstance:
    return ClassInstance(
        session_id=None,
        semester_id=instance.semester_id,
        date=LATER,
        day="Sunday",
        time_slot=SLOT,
        start_min=960,
        end_min=1050,
        room=room,
        course_code=course_code,
        section=section,
        batch=section,
        teacher_initial="ZZZ",
        status=None,
    )


async def _check(session, course_code: str, section: str):
    return await conflict_service.check(
        session,
        on=LATER,
        time_slot=SLOT,
        teacher_initial="TCA",
        section=section,
        course_code=course_code,
    )


async def test_one_courses_retake_does_not_block_anothers(session, instance):
    session.add(_occupant(instance, "CSE491(RE_A)", "RE_A", "KT-508"))
    await session.flush()

    report = await _check(session, "CSE447(RE_A)", "RE_A")
    assert report.ok
    # Whether the two share a student cannot be known, so it is said.
    assert report.warnings == [conflict_service.RETAKE_UNCHECKED]


async def test_a_retake_lab_group_blocks_its_own_courses_retake(session, instance):
    session.add(_occupant(instance, "CSE213(RE_A1(1.5C))", "RE_A1", "KT-508"))
    await session.flush()

    report = await _check(session, "CSE213(RE_A(3C))", "RE_A")
    assert [c.type for c in report.conflicts] == ["SECTION"]


async def test_a_theory_class_is_blocked_by_its_own_lab_group(session, instance):
    session.add(_occupant(instance, "CSE322(66_B1)", "66_B1", "KT-508"))
    await session.flush()

    assert [c.type for c in (await _check(session, "CSE315(66_B)", "66_B")).conflicts] == [
        "SECTION"
    ]
    other_group = await _check(session, "CSE324(66_B2)", "66_B2")
    assert other_group.ok and other_group.warnings == []


async def test_a_regular_class_is_warned_of_a_retake_at_that_time(session, instance):
    session.add(_occupant(instance, "CSE213(RE_A)", "RE_A", "KT-508"))
    await session.flush()

    report = await _check(session, "CSE315(66_B)", "66_B")
    assert report.ok
    assert len(report.warnings) == 1 and "CSE213(RE_A) is a retake" in report.warnings[0]
    assert report.as_dict()["warnings"] == report.warnings

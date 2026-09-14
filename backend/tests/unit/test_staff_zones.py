"""Staff floor coverage.

An assigned floor is a staff member's round, and decides who answers for a class
nobody reported. It is never a fence: someone standing on another floor can see
and check every class there, so a class is not left unchecked just because the
person who covers it is elsewhere. The checking screen groups rooms into floor
cards, with the caller's own floors first.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from tests.conftest import END_MIN, SLOT, START_MIN, at

from classtrack.core.errors import ValidationError
from classtrack.models import (
    CheckOutcome,
    ClassInstance,
    ClassSession,
    Role,
    Routine,
    Semester,
    StaffZone,
)
from classtrack.services import assignment_service, check_service, checking_service
from classtrack.services.zones import room_zone, zones_for_rooms

DAY = date(2026, 9, 13)


# --- deriving a zone from a room name --------------------------------------


@pytest.mark.parametrize(
    ("room", "key", "floor"),
    [
        ("KT-318(A)", "KT-3", 3),
        ("KT-201", "KT-2", 2),
        ("KT-804", "KT-8", 8),
        ("ANX1-101", "ANX1-1", 1),
        ("ANX1-403", "ANX1-4", 4),
        ("G1-001", "G1-0", 0),      # ground floor, not "no floor"
        ("SH-103", "SH-1", 1),
        ("kt-305", "KT-3", 3),      # case-insensitive
        ("KT - 305", "KT-3", 3),    # tolerant of spacing
    ],
)
def test_room_zone_derivation(room, key, floor):
    zone = room_zone(room)
    assert zone.key == key
    assert zone.floor == floor


@pytest.mark.parametrize("room", ["EMBED", "IOT LAB", "", "???"])
def test_unnumbered_rooms_are_unzoned_not_dropped(room):
    """A named lab is a real room with real classes. It must stay assignable."""
    assert room_zone(room).key == "UNZONED"


def test_ground_floor_is_not_confused_with_unzoned():
    """G1-001 is floor 0, which is falsy -- an easy bug to write."""
    ground = room_zone("G1-001")
    assert ground.floor == 0
    assert ground.key != "UNZONED"
    assert "Ground" in ground.label


def test_zone_summary_sorts_unzoned_last():
    summary = zones_for_rooms(["EMBED", "KT-305", "ANX1-101", "G1-001"])
    assert [z["key"] for z in summary] == ["ANX1-1", "G1-0", "KT-3", "UNZONED"]
    assert summary[0]["room_count"] == 1


# --- fixtures ---------------------------------------------------------------


async def _routine_with_rooms(session, rooms: list[str]) -> Semester:
    routine = Routine(
        department="cse", version="Z1", is_active=True, session_count=len(rooms)
    )
    session.add(routine)
    await session.flush()

    semester = Semester(
        name="Zones",
        routine_id=routine.id,
        start_date=DAY - timedelta(days=7),
        end_date=DAY + timedelta(days=7),
        is_active=True,
    )
    session.add(semester)
    await session.flush()

    for i, room in enumerate(rooms):
        sess = ClassSession(
            routine_id=routine.id,
            day="Sunday",
            time_slot=SLOT,
            room=room,
            course_code=f"CSE{300 + i}(70_A)",
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
                date=DAY,
                day="Sunday",
                time_slot=SLOT,
                start_min=START_MIN,
                end_min=END_MIN,
                room=room,
                course_code=sess.course_code,
                section=sess.section,
                batch="70_A",
                teacher_initial="TCA",
            )
        )
    await session.flush()
    return semester


ROOMS = ["KT-201", "KT-208", "KT-305", "KT-318(A)", "G1-001", "G1-002", "EMBED"]


# --- every floor is visible; assigned floors come first ---------------------


async def test_staff_with_no_floors_still_see_every_class(session, staff):
    """An assigned floor is a round, not a fence: nobody is locked out of a class."""
    await _routine_with_rooms(session, ROOMS)
    assigned = await assignment_service.zones_for_user(session, staff.id)
    assert assigned == []

    screen = await checking_service.checking_screen(
        session, on=DAY, slot=SLOT, my_zones=assigned
    )
    assert len(screen["rooms"]) == len(ROOMS)
    assert screen["zones"] == []
    assert not any(f["is_mine"] for f in screen["floors"])


async def test_an_admin_sees_every_class(session):
    """An admin has no floors of their own and gets the same full list."""
    await _routine_with_rooms(session, ROOMS)
    screen = await checking_service.checking_screen(
        session, on=DAY, slot=SLOT, my_zones=None
    )
    assert len(screen["rooms"]) == len(ROOMS)


async def test_staff_see_every_floor_with_their_own_first(session, staff, hod):
    await _routine_with_rooms(session, ROOMS)
    await assignment_service.set_zones(
        session, user_id=staff.id, zone_keys=["KT-2", "KT-3"], actor=hod
    )
    await session.commit()

    keys = await assignment_service.zones_for_user(session, staff.id)
    screen = await checking_service.checking_screen(
        session, on=DAY, slot=SLOT, my_zones=keys
    )
    assert len(screen["rooms"]) == len(ROOMS)
    assert screen["zones"] == ["KT-2", "KT-3"]
    floors = [(f["key"], f["total"], f["is_mine"]) for f in screen["floors"]]
    assert floors == [
        ("KT-2", 2, True),
        ("KT-3", 2, True),
        ("G1-0", 2, False),
        ("UNZONED", 1, False),
    ]


async def test_unnumbered_rooms_get_a_floor_card_of_their_own(session, staff, hod):
    await _routine_with_rooms(session, ROOMS)
    await assignment_service.set_zones(
        session, user_id=staff.id, zone_keys=["UNZONED"], actor=hod
    )
    await session.commit()

    keys = await assignment_service.zones_for_user(session, staff.id)
    screen = await checking_service.checking_screen(
        session, on=DAY, slot=SLOT, my_zones=keys
    )
    first = screen["floors"][0]
    assert (first["key"], first["label"], first["total"], first["is_mine"]) == (
        "UNZONED",
        "Other rooms",
        1,
        True,
    )
    assert [r["room"] for r in screen["rooms"] if r["zone_key"] == "UNZONED"] == ["EMBED"]


async def test_staff_can_check_a_class_on_a_floor_they_do_not_cover(session, staff, hod):
    await _routine_with_rooms(session, ROOMS)
    await assignment_service.set_zones(
        session, user_id=staff.id, zone_keys=["KT-2"], actor=hod
    )
    await session.commit()

    screen = await checking_service.checking_screen(
        session, on=DAY, slot=SLOT, my_zones=["KT-2"]
    )
    ground = next(r for r in screen["rooms"] if r["room"] == "G1-001")
    await check_service.submit(
        session,
        instance_id=ground["instance_id"],
        user=staff,
        outcome=CheckOutcome.RUNNING,
        now=at(10, 5),
    )

    screen = await checking_service.checking_screen(
        session, on=DAY, slot=SLOT, my_zones=["KT-2"]
    )
    g1 = next(f for f in screen["floors"] if f["key"] == "G1-0")
    assert (g1["checked"], g1["total"], g1["is_mine"]) == (1, 2, False)


async def test_clearing_zones_only_removes_the_your_floor_mark(session, staff, hod):
    """Parking an account takes away its round, not its access to classes."""
    await _routine_with_rooms(session, ROOMS)
    await assignment_service.set_zones(
        session, user_id=staff.id, zone_keys=["G1-0"], actor=hod
    )
    await session.commit()
    assert len(await assignment_service.zones_for_user(session, staff.id)) == 1

    await assignment_service.set_zones(
        session, user_id=staff.id, zone_keys=[], actor=hod
    )
    await session.commit()
    keys = await assignment_service.zones_for_user(session, staff.id)
    assert keys == []
    screen = await checking_service.checking_screen(
        session, on=DAY, slot=SLOT, my_zones=keys
    )
    assert len(screen["rooms"]) == len(ROOMS)
    assert not any(f["is_mine"] for f in screen["floors"])


# --- validation -------------------------------------------------------------


async def test_unknown_zone_is_rejected(session, staff, hod):
    await _routine_with_rooms(session, ROOMS)
    with pytest.raises(ValidationError, match="not a zone"):
        await assignment_service.set_zones(
            session, user_id=staff.id, zone_keys=["KT-9"], actor=hod
        )


async def test_only_staff_accounts_can_be_zoned(session, hod, teacher_user):
    await _routine_with_rooms(session, ROOMS)
    with pytest.raises(ValidationError, match="office staff"):
        await assignment_service.set_zones(
            session, user_id=teacher_user.id, zone_keys=["KT-2"], actor=hod
        )


async def test_duplicate_keys_are_collapsed(session, staff, hod):
    await _routine_with_rooms(session, ROOMS)
    keys = await assignment_service.set_zones(
        session, user_id=staff.id, zone_keys=["KT-2", "kt-2", "KT-2"], actor=hod
    )
    await session.commit()
    assert keys == ["KT-2"]
    rows = await assignment_service.zones_for_user(session, staff.id)
    assert rows == ["KT-2"]


async def test_reassignment_replaces_rather_than_appends(session, staff, hod):
    await _routine_with_rooms(session, ROOMS)
    await assignment_service.set_zones(
        session, user_id=staff.id, zone_keys=["KT-2", "KT-3"], actor=hod
    )
    await session.commit()
    await assignment_service.set_zones(
        session, user_id=staff.id, zone_keys=["G1-0"], actor=hod
    )
    await session.commit()
    assert await assignment_service.zones_for_user(session, staff.id) == ["G1-0"]


async def test_assignment_is_audited(session, staff, hod):
    """Who covers which floor is an accountability question (BR-15)."""
    from sqlalchemy import select

    from classtrack.models import AuditLog

    await _routine_with_rooms(session, ROOMS)
    await assignment_service.set_zones(
        session, user_id=staff.id, zone_keys=["KT-2"], actor=hod
    )
    await session.commit()

    entry = await session.scalar(
        select(AuditLog).where(AuditLog.action == "zones_assigned")
    )
    assert entry is not None
    assert entry.actor_id == hod.id
    assert entry.entity_id == staff.id
    assert entry.after == {"zones": ["KT-2"]}


async def test_deleting_a_user_removes_their_assignments(session, staff, hod):
    from sqlalchemy import func, select

    await _routine_with_rooms(session, ROOMS)
    await assignment_service.set_zones(
        session, user_id=staff.id, zone_keys=["KT-2"], actor=hod
    )
    await session.commit()

    await session.delete(staff)
    await session.commit()

    left = await session.scalar(select(func.count(StaffZone.id)))
    assert left == 0


# --- creating a staff member and their floor together -----------------------


async def test_create_staff_assigns_floors_in_one_step(session, hod):
    await _routine_with_rooms(session, ROOMS)
    member = await assignment_service.create_staff(
        session,
        full_name="Floor Two Checker",
        email="Floor2@diu.edu",
        password="secret123",
        zone_keys=["KT-2"],
        actor=hod,
    )
    await session.commit()

    assert member.role is Role.STAFF
    assert member.email == "floor2@diu.edu"      # normalised
    assert await assignment_service.zones_for_user(session, member.id) == ["KT-2"]

    screen = await checking_service.checking_screen(
        session, on=DAY, slot=SLOT, my_zones=["KT-2"]
    )
    assert [f["key"] for f in screen["floors"] if f["is_mine"]] == ["KT-2"]


async def test_create_staff_requires_a_floor(session, hod):
    await _routine_with_rooms(session, ROOMS)
    with pytest.raises(ValidationError, match="at least one floor"):
        await assignment_service.create_staff(
            session,
            full_name="Nobody",
            email="nobody@diu.edu",
            password="secret123",
            zone_keys=[],
            actor=hod,
        )


async def test_create_staff_rejects_a_duplicate_email(session, hod, staff):
    await _routine_with_rooms(session, ROOMS)
    with pytest.raises(ValidationError, match="already has an account"):
        await assignment_service.create_staff(
            session,
            full_name="Clash",
            email=staff.email,
            password="secret123",
            zone_keys=["KT-2"],
            actor=hod,
        )


async def test_create_staff_rejects_a_short_password(session, hod):
    await _routine_with_rooms(session, ROOMS)
    with pytest.raises(ValidationError, match="6 characters"):
        await assignment_service.create_staff(
            session,
            full_name="Weak",
            email="weak@diu.edu",
            password="123",
            zone_keys=["KT-2"],
            actor=hod,
        )


async def test_new_staff_can_sign_in(session, hod):
    """The account has to actually work, not just exist."""
    from classtrack.services import auth_service

    await _routine_with_rooms(session, ROOMS)
    await assignment_service.create_staff(
        session,
        full_name="Signs In",
        email="signsin@diu.edu",
        password="secret123",
        zone_keys=["G1-0"],
        actor=hod,
    )
    await session.commit()

    user = await auth_service.authenticate(session, "signsin@diu.edu", "secret123")
    assert user.role is Role.STAFF

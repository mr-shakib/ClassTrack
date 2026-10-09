"""The faculty list an admin keeps: adding a teacher, correcting one, and the
roles a teacher's account is given."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from classtrack.core.errors import ForbiddenError, ValidationError
from classtrack.models import AuditLog, BuiltinRole, Teacher
from classtrack.services import account_service, auth_service, faculty_service, role_service


async def test_an_admin_adds_a_teacher_who_can_then_be_given_an_account(session, hod):
    teacher = await faculty_service.add_teacher(
        session,
        actor=hod,
        initial=" nrf ",
        name="  Ms.  Nusrat   Rahman ",
        designation="Lecturer",
        email="Nusrat@Example.edu",
        office_room="KT-702B",
    )
    account = await account_service.create_teacher_account(
        session, initial=teacher.initial, password="secret1", actor=hod
    )
    await session.flush()

    assert teacher.initial == "NRF" and teacher.name == "Ms. Nusrat Rahman"
    assert teacher.email == "Nusrat@example.edu"
    assert [r.key for r in account.roles] == [BuiltinRole.TEACHER.value]
    assert (await auth_service.authenticate(session, "nrf", "secret1")).id == account.id


async def test_an_initial_is_added_once_and_must_look_like_one(session, hod, teacher_user):
    with pytest.raises(ValidationError, match="already on the faculty list"):
        await faculty_service.add_teacher(session, actor=hod, initial="tca", name="Someone")
    with pytest.raises(ValidationError, match="not an initial"):
        await faculty_service.add_teacher(session, actor=hod, initial="T C A", name="Someone")
    with pytest.raises(ValidationError, match="valid email"):
        await faculty_service.add_teacher(
            session, actor=hod, initial="NEW", name="Someone", email="not-an-address"
        )


async def test_editing_replaces_the_details_and_the_account_takes_the_name(
    session, hod, teacher_user
):
    teacher = await session.scalar(select(Teacher).where(Teacher.initial == "TCA"))
    teacher.email = "old@example.edu"

    await faculty_service.update_teacher(
        session,
        actor=hod,
        current_initial="tca",
        initial="TCA",
        name="Dr. Teacher A",
        designation="Assistant Professor",
        email="",
    )
    await session.flush()

    assert teacher.name == "Dr. Teacher A" and teacher.designation == "Assistant Professor"
    assert teacher.email is None
    assert teacher_user.full_name == "Dr. Teacher A"
    entry = await session.scalar(select(AuditLog).where(AuditLog.action == "teacher_updated"))
    assert entry.before["email"] == "old@example.edu" and entry.after["email"] is None


async def test_a_mistyped_initial_is_corrected_and_the_sign_in_follows(session, hod):
    await faculty_service.add_teacher(session, actor=hod, initial="NFR", name="Ms. Nusrat")
    account = await account_service.create_teacher_account(
        session, initial="NFR", password="secret1", actor=hod
    )

    await faculty_service.update_teacher(
        session, actor=hod, current_initial="NFR", initial="NRF", name="Ms. Nusrat"
    )
    await session.flush()

    assert account.teacher_initial == "NRF"
    assert account.email == "nrf@teacher.classtrack"
    assert (await auth_service.authenticate(session, "NRF", "secret1")).id == account.id


async def test_an_initial_the_routine_uses_stays(session, hod, instance):
    with pytest.raises(ValidationError, match="routine has classes under TCA"):
        await faculty_service.update_teacher(
            session, actor=hod, current_initial="TCA", initial="TCB", name="Teacher A"
        )


async def test_a_new_teachers_account_may_be_given_more_roles(session, hod):
    await faculty_service.add_teacher(session, actor=hod, initial="NRF", name="Ms. Nusrat")
    teacher = await role_service.builtin(session, BuiltinRole.TEACHER)
    committee = await role_service.builtin(session, BuiltinRole.COMMITTEE)

    account = await account_service.create_teacher_account(
        session, initial="NRF", password="secret1", actor=hod, roles=[teacher, committee]
    )

    assert account.is_teacher
    assert {r.key for r in account.roles} == {"TEACHER", "COMMITTEE"}


async def test_a_teachers_account_keeps_a_teacher_role(session, hod):
    await faculty_service.add_teacher(session, actor=hod, initial="NRF", name="Ms. Nusrat")
    committee = await role_service.builtin(session, BuiltinRole.COMMITTEE)

    with pytest.raises(ValidationError, match="keeps at least one teacher role"):
        await account_service.create_teacher_account(
            session, initial="NRF", password="secret1", actor=hod, roles=[committee]
        )


async def test_choosing_roles_takes_the_right_to_manage_accounts(session, coordinator):
    # The Coordination Officer manages teachers but not accounts: they may add
    # a teacher with the Teacher role, and choose no other.
    await faculty_service.add_teacher(session, actor=coordinator, initial="NRF", name="Ms. N")
    teacher = await role_service.builtin(session, BuiltinRole.TEACHER)

    with pytest.raises(ForbiddenError, match="Manage accounts"):
        await account_service.create_teacher_account(
            session, initial="NRF", password="secret1", actor=coordinator, roles=[teacher]
        )
    account = await account_service.create_teacher_account(
        session, initial="NRF", password="secret1", actor=coordinator
    )
    assert [r.key for r in account.roles] == ["TEACHER"]

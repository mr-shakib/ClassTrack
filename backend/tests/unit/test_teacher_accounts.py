"""Teacher accounts: created by an admin from the faculty list, signed in by initial."""

from __future__ import annotations

import pytest

from classtrack.core.errors import AuthError, NotFoundError, ValidationError
from classtrack.models import Role, Teacher
from classtrack.services import account_service, auth_service


async def test_admin_creates_an_account_the_teacher_signs_in_to_by_initial(session, hod):
    session.add(Teacher(initial="SRH", name="Dr. Sheak Rashed Haider Noori", department="cse"))
    await session.flush()

    account = await account_service.create_teacher_account(
        session, initial="srh", password="secret1", actor=hod
    )
    await session.flush()

    assert account.role is Role.TEACHER
    assert account.teacher_initial == "SRH"
    assert account.full_name == "Dr. Sheak Rashed Haider Noori"

    signed_in = await auth_service.authenticate(session, "srh", "secret1")
    assert signed_in.id == account.id
    with pytest.raises(AuthError):
        await auth_service.authenticate(session, "SRH", "wrong-password")


async def test_an_initial_gets_one_account(session, hod, teacher_user):
    with pytest.raises(ValidationError, match="already has an account"):
        await account_service.create_teacher_account(
            session, initial="TCA", password="secret1", actor=hod
        )


async def test_the_initial_must_be_on_the_faculty_list(session, hod):
    with pytest.raises(NotFoundError):
        await account_service.create_teacher_account(
            session, initial="NOPE", password="secret1", actor=hod
        )


async def test_password_reset_takes_effect(session, hod, teacher_user):
    await account_service.reset_teacher_password(
        session, initial="TCA", password="newpass1", actor=hod
    )
    assert (await auth_service.authenticate(session, "TCA", "newpass1")).id == teacher_user.id


async def test_email_sign_in_still_works(session, staff):
    assert (await auth_service.authenticate(session, "Staff@Test.edu", "x")).id == staff.id

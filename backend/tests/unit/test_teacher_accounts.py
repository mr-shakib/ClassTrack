"""Teacher accounts: created by an admin from the faculty list, signed in by initial."""

from __future__ import annotations

import pytest

from classtrack.core.errors import AuthError, NotFoundError, ValidationError
from classtrack.models import Teacher
from classtrack.services import account_service, auth_service


async def test_admin_creates_an_account_the_teacher_signs_in_to_by_initial(session, hod):
    session.add(Teacher(initial="SRH", name="Dr. Sheak Rashed Haider Noori", department="cse"))
    await session.flush()

    account = await account_service.create_teacher_account(
        session, initial="srh", password="secret1", actor=hod
    )
    await session.flush()

    assert account.is_teacher
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


async def test_one_step_gives_every_teacher_without_an_account_one(session, hod, teacher_user):
    session.add_all(
        [
            Teacher(initial="SRH", name="Dr. Sheak Rashed Haider Noori", department="cse"),
            Teacher(initial="MAH", name="Mr. Mahfuz", department="cse"),
        ]
    )
    await session.flush()
    before = teacher_user.password_hash

    created = await account_service.create_all_teacher_accounts(
        session, password="default1", actor=hod
    )
    await session.flush()

    assert sorted(a.teacher_initial for a in created) == ["MAH", "SRH"]
    assert teacher_user.password_hash == before          # an existing account is left alone
    assert (await auth_service.authenticate(session, "srh", "default1")).teacher_initial == "SRH"
    assert (await auth_service.authenticate(session, "MAH", "default1")).teacher_initial == "MAH"

    again = await account_service.create_all_teacher_accounts(
        session, password="default1", actor=hod
    )
    assert again == []


async def test_one_step_refuses_a_short_password(session, hod):
    with pytest.raises(ValidationError, match="at least"):
        await account_service.create_all_teacher_accounts(session, password="123", actor=hod)

"""Self-service profile: a user changes their own password; a teacher, their contact address."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from classtrack.core.errors import AuthError, ValidationError
from classtrack.core.security import hash_password
from classtrack.models import AuditLog, Teacher
from classtrack.services import account_service, auth_service, profile_service


async def test_a_teacher_replaces_the_default_password(session, hod):
    session.add(Teacher(initial="SRH", name="Dr. Sheak Rashed Haider Noori", department="cse"))
    await session.flush()
    await account_service.create_all_teacher_accounts(session, password="default1", actor=hod)
    await session.flush()
    teacher = await auth_service.authenticate(session, "SRH", "default1")

    await profile_service.change_password(session, teacher, current="default1", new="mine-only")
    await session.flush()

    assert (await auth_service.authenticate(session, "srh", "mine-only")).id == teacher.id
    with pytest.raises(AuthError):
        await auth_service.authenticate(session, "SRH", "default1")


async def test_any_role_may_change_their_own_password(session, staff):
    await profile_service.change_password(session, staff, current="x", new="staffpass")
    assert (await auth_service.authenticate(session, "staff@test.edu", "staffpass")).id == staff.id


async def test_the_current_password_must_be_right(session, teacher_user):
    before = teacher_user.password_hash
    with pytest.raises(ValidationError, match="current password"):
        await profile_service.change_password(
            session, teacher_user, current="guess", new="newpass1"
        )
    assert teacher_user.password_hash == before


@pytest.mark.parametrize(
    ("new", "message"),
    [("123", "at least"), ("x", "at least"), ("x" * 73, "too long")],
)
async def test_the_new_password_is_checked(session, teacher_user, new, message):
    with pytest.raises(ValidationError, match=message):
        await profile_service.change_password(session, teacher_user, current="x", new=new)


async def test_the_new_password_must_differ(session, staff):
    staff.password_hash = hash_password("samesame")
    with pytest.raises(ValidationError, match="differ"):
        await profile_service.change_password(session, staff, current="samesame", new="samesame")


async def test_a_change_is_audited_without_the_password(session, teacher_user):
    await profile_service.change_password(session, teacher_user, current="x", new="newpass1")
    await session.flush()

    entry = await session.scalar(select(AuditLog).where(AuditLog.action == "password_changed"))
    assert entry is not None
    assert entry.actor_id == entry.entity_id == teacher_user.id
    assert entry.before is None and entry.after is None


async def test_a_teacher_redirects_their_absence_reports(session, teacher_user):
    teacher = await profile_service.update_contact_email(
        session, teacher_user, "  TCA@Daffodilvarsity.edu.bd "
    )
    await session.flush()

    assert teacher.email == "TCA@daffodilvarsity.edu.bd"
    entry = await session.scalar(select(AuditLog).where(AuditLog.action == "contact_email_changed"))
    assert entry.before == {"email": None}
    assert entry.after == {"email": "TCA@daffodilvarsity.edu.bd"}


async def test_a_contact_address_must_be_an_address(session, teacher_user):
    with pytest.raises(ValidationError, match="valid email"):
        await profile_service.update_contact_email(session, teacher_user, "not-an-email")


async def test_only_a_teacher_has_a_contact_address(session, staff):
    with pytest.raises(ValidationError, match="Only a teacher"):
        await profile_service.update_contact_email(session, staff, "staff@diu.edu.bd")

"""Self-service: a signed-in user changes their own password and contact address.

An admin sets the first password -- for teachers, often one default shared by
the whole faculty -- so changing it is the first thing a teacher should do.
Name, initial and designation stay with the faculty directory, which the admins
keep; a teacher edits only the address their absence reports are mailed to.
"""

from __future__ import annotations

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from classtrack.core.errors import ValidationError
from classtrack.core.security import hash_password, verify_password
from classtrack.models import Role, Teacher, User
from classtrack.services import audit_service
from classtrack.services.account_service import MIN_PASSWORD


async def teacher_of(session: AsyncSession, user: User) -> Teacher | None:
    """The faculty record behind a teacher's account; None for anyone else."""
    if user.role is not Role.TEACHER or not user.teacher_initial:
        return None
    return await session.scalar(select(Teacher).where(Teacher.initial == user.teacher_initial))


async def change_password(session: AsyncSession, user: User, *, current: str, new: str) -> None:
    # Asked for even though the session is already signed in, so a browser left
    # open cannot be used to take the account over.
    if not verify_password(current, user.password_hash):
        raise ValidationError("Your current password is not correct.")
    if len(new) < MIN_PASSWORD:
        raise ValidationError(f"The new password must be at least {MIN_PASSWORD} characters.")
    if new == current:
        raise ValidationError("The new password must differ from the current one.")

    user.password_hash = hash_password(new)
    audit_service.record(
        session,
        actor_id=user.id,
        entity_type="user",
        entity_id=user.id,
        action="password_changed",
    )


async def update_contact_email(session: AsyncSession, user: User, email: str) -> Teacher:
    """Point a teacher's absence reports at ``email``."""
    teacher = await teacher_of(session, user)
    if teacher is None:
        raise ValidationError("Only a teacher has a contact address to change.")
    try:
        email = validate_email(email.strip(), check_deliverability=False).normalized
    except EmailNotValidError as exc:
        raise ValidationError("That is not a valid email address.") from exc

    before = teacher.email
    if email == before:
        return teacher
    teacher.email = email
    # Where absence reports go is worth a trail: redirecting them is how one
    # would stop hearing about them.
    audit_service.record(
        session,
        actor_id=user.id,
        entity_type="teacher",
        entity_id=teacher.id,
        action="contact_email_changed",
        before={"email": before},
        after={"email": email},
    )
    return teacher

"""The faculty directory: adding a teacher, and keeping their details right.

Most of the faculty arrive from ``teachers.json``; a teacher who joins later,
or one the file has wrong, is added or corrected here by an admin.

The initial is the key: the routine names teachers by it, and a teacher's
account is joined to their classes through it. So it must look like one the
routine could carry, and it may only change while no class carries it --
renaming it then would cut the teacher off from their classes.
"""

from __future__ import annotations

import re

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from classtrack.core.errors import NotFoundError, ValidationError
from classtrack.models import ClassInstance, ClassSession, MakeupClass, Teacher, User
from classtrack.routine.cell_parser import INITIAL_RE
from classtrack.services import audit_service
from classtrack.services.account_service import PLACEHOLDER_DOMAIN

_URL_RE = re.compile(r"^https?://\S+$")


def _clean(
    *,
    initial: str,
    name: str,
    designation: str | None,
    email: str | None,
    office_room: str | None,
    photo_url: str | None,
) -> dict[str, str | None]:
    """The details as stored: trimmed, blanks as None, each checked."""
    initial = initial.strip().upper()
    if not INITIAL_RE.match(initial):
        raise ValidationError(
            f"{initial!r} is not an initial as the routine writes one: up to six letters, e.g. SRH."
        )
    name = " ".join(name.split())
    if len(name) < 2:
        raise ValidationError("A teacher's name is at least 2 characters.")

    email = (email or "").strip() or None
    if email is not None:
        try:
            email = validate_email(email, check_deliverability=False).normalized
        except EmailNotValidError as exc:
            raise ValidationError(f"{email} is not a valid email address.") from exc

    photo_url = (photo_url or "").strip() or None
    if photo_url is not None and not _URL_RE.match(photo_url):
        raise ValidationError("The photo must be a web address starting with https://.")

    return {
        "initial": initial,
        "name": name,
        "designation": " ".join((designation or "").split()) or None,
        "email": email,
        "office_room": " ".join((office_room or "").split()) or None,
        "image_url": photo_url,
    }


def _snapshot(teacher: Teacher) -> dict[str, str | None]:
    return {
        "initial": teacher.initial,
        "name": teacher.name,
        "designation": teacher.designation,
        "email": teacher.email,
        "office_room": teacher.office_room,
        "image_url": teacher.image_url,
    }


async def _initial_taken(session: AsyncSession, initial: str) -> bool:
    return await session.scalar(select(Teacher.id).where(Teacher.initial == initial)) is not None


async def _has_classes(session: AsyncSession, initial: str) -> bool:
    """Whether the routine, a class or a makeup names this initial."""
    columns = (ClassSession.teacher, ClassInstance.teacher_initial, MakeupClass.teacher_initial)
    for column in columns:
        if await session.scalar(select(column).where(column == initial).limit(1)) is not None:
            return True
    return False


async def add_teacher(
    session: AsyncSession,
    *,
    actor: User,
    initial: str,
    name: str,
    designation: str | None = None,
    email: str | None = None,
    office_room: str | None = None,
    photo_url: str | None = None,
) -> Teacher:
    details = _clean(
        initial=initial,
        name=name,
        designation=designation,
        email=email,
        office_room=office_room,
        photo_url=photo_url,
    )
    if await _initial_taken(session, details["initial"]):
        raise ValidationError(f"{details['initial']} is already on the faculty list.")

    teacher = Teacher(department="cse", **details)
    session.add(teacher)
    await session.flush()
    audit_service.record(
        session,
        actor_id=actor.id,
        entity_type="teacher",
        entity_id=teacher.id,
        action="teacher_added",
        after=details,
    )
    return teacher


async def update_teacher(
    session: AsyncSession,
    *,
    actor: User,
    current_initial: str,
    initial: str,
    name: str,
    designation: str | None = None,
    email: str | None = None,
    office_room: str | None = None,
    photo_url: str | None = None,
) -> Teacher:
    """Replace every detail; one sent empty is cleared.

    The teacher's account follows: it takes the new name, and a new initial
    becomes what they sign in with.
    """
    current_initial = current_initial.strip().upper()
    teacher = await session.scalar(select(Teacher).where(Teacher.initial == current_initial))
    if teacher is None:
        raise NotFoundError(f"No faculty member with initial {current_initial!r}.")
    details = _clean(
        initial=initial,
        name=name,
        designation=designation,
        email=email,
        office_room=office_room,
        photo_url=photo_url,
    )
    before = _snapshot(teacher)
    account = await session.scalar(select(User).where(User.teacher_initial == teacher.initial))

    new_initial = details.pop("initial")
    if new_initial != teacher.initial:
        await _rename(session, teacher, account, new_initial)

    for key, value in details.items():
        setattr(teacher, key, value)
    if account is not None:
        account.full_name = teacher.name

    after = _snapshot(teacher)
    if after != before:
        audit_service.record(
            session,
            actor_id=actor.id,
            entity_type="teacher",
            entity_id=teacher.id,
            action="teacher_updated",
            before={k: v for k, v in before.items() if after[k] != v},
            after={k: v for k, v in after.items() if before[k] != v},
        )
    return teacher


async def _rename(
    session: AsyncSession, teacher: Teacher, account: User | None, new_initial: str
) -> None:
    old_initial = teacher.initial
    if await _has_classes(session, old_initial):
        raise ValidationError(
            f"The routine has classes under {old_initial}, so the initial stays as it is."
        )
    if await _initial_taken(session, new_initial):
        raise ValidationError(f"{new_initial} is already on the faculty list.")

    old_email = f"{old_initial.lower()}@{PLACEHOLDER_DOMAIN}"
    new_email = f"{new_initial.lower()}@{PLACEHOLDER_DOMAIN}"
    moves_email = account is not None and account.email == old_email
    if moves_email and await session.scalar(select(User.id).where(User.email == new_email)):
        raise ValidationError(f"{new_email} is already in use.")

    # The account points at the initial, and the key it points at cannot move
    # under it: let go, rename, then take hold of the new one.
    if account is not None:
        account.teacher_initial = None
        await session.flush()
    teacher.initial = new_initial
    await session.flush()
    if account is not None:
        account.teacher_initial = new_initial
        if moves_email:
            account.email = new_email

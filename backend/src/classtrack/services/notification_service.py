"""Notification delivery.

Delivery sits behind ``NotificationChannel`` so adding email or SMS (SRS 2.2) is
a new class beside ``InAppChannel``, not a change to any caller.
"""

from __future__ import annotations

import logging
from typing import Protocol

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from classtrack.core.config import get_settings
from classtrack.db.base import utcnow
from classtrack.models import (
    CheckOutcome,
    ClassInstance,
    MakeupClass,
    MakeupMode,
    MakeupStatus,
    Notification,
    NotificationKind,
    Permission,
    Teacher,
    User,
)
from classtrack.services import email_service, role_service

logger = logging.getLogger(__name__)


class NotificationChannel(Protocol):
    """A way of reaching a user. v1 ships only the in-app channel."""

    async def send(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        kind: NotificationKind,
        title: str,
        body: str,
        link: str | None = None,
    ) -> None: ...


class InAppChannel:
    """Writes a row the notification bell reads."""

    async def send(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        kind: NotificationKind,
        title: str,
        body: str,
        link: str | None = None,
    ) -> None:
        session.add(
            Notification(user_id=user_id, kind=kind, title=title, body=body, link=link)
        )


#: Active channels. Append an EmailChannel here to enable email delivery.
CHANNELS: list[NotificationChannel] = [InAppChannel()]


async def _dispatch(
    session: AsyncSession,
    *,
    user_id: int,
    kind: NotificationKind,
    title: str,
    body: str,
    link: str | None = None,
) -> None:
    for channel in CHANNELS:
        await channel.send(
            session, user_id=user_id, kind=kind, title=title, body=body, link=link
        )


async def _user_for_teacher(session: AsyncSession, initial: str) -> User | None:
    return await session.scalar(select(User).where(User.teacher_initial == initial))


async def _admins(session: AsyncSession) -> list[User]:
    """Whoever receives department alerts -- a permission, so any role can."""
    return await role_service.users_who_can(session, Permission.RECEIVE_ALERTS)


def _describe(instance: ClassInstance) -> str:
    return (
        f"{instance.course_code} for section {instance.section} "
        f"scheduled at {instance.time_slot} on {instance.date:%d %B %Y}"
    )


def _course(instance: ClassInstance) -> str:
    """Routine course codes carry their section already, as in "CSE322(67_D1)"."""
    if instance.section in instance.course_code:
        return instance.course_code
    return f"{instance.course_code} ({instance.section})"


def _at(instance: ClassInstance) -> str:
    """The class as one phrase: CSE322(67_D1) at 08:30-10:00 on 05 October 2026."""
    return f"{_course(instance)} at {instance.time_slot} on {instance.date:%d %B %Y}"


async def notify_missed(session: AsyncSession, instance: ClassInstance) -> None:
    """Tell the teacher their class was recorded as missed (BR-07)."""
    user = await _user_for_teacher(session, instance.teacher_initial)
    if user is None:
        # No account for this initial yet. Log it rather than failing the sweep:
        # the monitoring record is what matters and it is already written.
        logger.warning(
            "No user account for teacher %s; missed-class notification skipped",
            instance.teacher_initial,
        )
        return
    if instance.is_extra:
        # Recorded, but not owed: there is nothing to reschedule.
        await _dispatch(
            session,
            user_id=user.id,
            kind=NotificationKind.MISSED_CLASS,
            title="Extra class missed",
            body=(
                f"Your extra class, {_describe(instance)}, has been marked as missed. "
                "It was not on the routine, so it needs no reschedule."
            ),
            link="/teacher",
        )
        return
    await _dispatch(
        session,
        user_id=user.id,
        kind=NotificationKind.MISSED_CLASS,
        title="Class missed — reschedule required",
        body=(
            f"Your {_describe(instance)} has been marked as missed. "
            "Request a reschedule in an empty room."
        ),
        link=_reschedule_link(instance),
    )


async def notify_reported(
    session: AsyncSession, instance: ClassInstance, outcome: CheckOutcome
) -> None:
    """Tell the teacher the moment staff record them absent or late.

    This is an early warning, not the verdict: a TEACHER_NOT_FOUND observation
    only becomes MISSED once the threshold passes, and staff may still amend it
    if the teacher arrives. ``notify_missed`` is the one that asks for a
    reschedule.

    An absence is also emailed, to the faculty address rather than the account,
    so it reaches a teacher who has not been given an account yet.
    """
    if outcome is CheckOutcome.TEACHER_NOT_FOUND:
        await _email_absent(session, instance)
    user = await _user_for_teacher(session, instance.teacher_initial)
    if user is None:
        logger.warning(
            "No user account for teacher %s; report notification skipped",
            instance.teacher_initial,
        )
        return
    link = "/teacher"
    # Worded passively: the teacher is told what was recorded, not who recorded it.
    if outcome is CheckOutcome.TEACHER_NOT_FOUND and instance.is_extra:
        title = "Extra class missed"
        body = f"The extra class {_at(instance)} (room {instance.room}) has been marked as missed."
    elif outcome is CheckOutcome.TEACHER_NOT_FOUND:
        title = "Class missed"
        body = (
            f"{_at(instance)} (room {instance.room}) has been marked as missed. "
            "It can be rescheduled if it cannot be taken."
        )
        link = _reschedule_link(instance)
    else:
        title = "Class marked late"
        body = f"{_at(instance)} has been marked as late."
    await _dispatch(
        session,
        user_id=user.id,
        kind=NotificationKind.CLASS_REPORTED,
        title=title,
        body=body,
        link=link,
    )


def _reschedule_link(instance: ClassInstance) -> str:
    return f"/teacher/makeup?instance={instance.id}"


async def _email_absent(session: AsyncSession, instance: ClassInstance) -> None:
    teacher = await session.scalar(
        select(Teacher).where(Teacher.initial == instance.teacher_initial)
    )
    if teacher is None or not teacher.email:
        logger.warning(
            "No email on file for teacher %s; absence email skipped", instance.teacher_initial
        )
        return
    public_url = get_settings().public_url
    link = None
    if public_url and not instance.is_extra:
        link = f"{public_url.rstrip('/')}{_reschedule_link(instance)}"
    kind = "Extra class" if instance.is_extra else "Class"
    # Worded passively, in plain words: what was recorded, not who recorded it.
    paragraphs = [
        f"Dear {teacher.name},",
        f"The {kind.lower()} below has been marked as missed.",
        f"Course: {_course(instance)}\n"
        f"Time: {instance.time_slot}, {instance.date:%d %B %Y}\n"
        f"Room: {instance.room}",
        "If the class is starting soon, it can still be changed to late.",
    ]
    # An extra class is not owed, so its email offers no reschedule.
    if not instance.is_extra:
        paragraphs.append(
            "If the class cannot be taken today, it can be rescheduled in ClassTrack."
            + (" Use the button below." if link else "")
        )
    paragraphs += [
        "If this is a mistake, it can be corrected by the department office.",
        "This is an automatic message from ClassTrack, Department of CSE.",
    ]
    email_service.queue(
        session,
        email_service.Email(
            to=teacher.email,
            subject=(
                f"{kind} missed: {_course(instance)}, "
                f"{instance.date:%d %b}, {instance.time_slot}"
            ),
            body="\n\n".join(paragraphs),
            link=link,
            link_label="Reschedule this class",
        ),
    )


async def notify_online_request(
    session: AsyncSession, makeup: MakeupClass, instance: ClassInstance
) -> None:
    """Tell the HoD an online reschedule needs a decision (BR-11).

    Only online requests reach a decision at all: one held in an empty room
    books itself, and announces itself through ``notify_makeup_scheduled``.
    """
    for admin in await _admins(session):
        await _dispatch(
            session,
            user_id=admin.id,
            kind=NotificationKind.ONLINE_REQUEST,
            title="Online makeup request",
            body=(
                f"{makeup.teacher_initial} requested to reschedule {_describe(instance)} "
                f"to {makeup.date:%d %B %Y} at {makeup.time_slot}, online."
                + (" A Drive link is attached for review." if makeup.drive_link else "")
            ),
            link="/approvals",
        )


def _makeup_link(makeup: MakeupClass) -> str:
    return f"/teacher#makeup-{makeup.id}"


def _rescheduled_to(makeup: MakeupClass) -> str:
    where = "online" if makeup.mode is MakeupMode.ONLINE else f"in room {makeup.room}"
    return f"{makeup.date:%A %d %B %Y} at {makeup.time_slot}, {where}"


def _missed(original: ClassInstance) -> str:
    return (
        f"{original.course_code} for section {original.section} "
        f"({original.date:%d %B %Y}, {original.time_slot}, {original.room})"
    )


async def notify_makeup_scheduled(
    session: AsyncSession, makeup: MakeupClass, original: ClassInstance
) -> None:
    """Confirm an in-room reschedule, which needed no decision (BR-10).

    Nothing lands in the approvals queue for this one, so the admins are told
    here instead: the room is gone from that cell and they should know why.
    """
    body = (
        f"Your missed class {_missed(original)} is rescheduled to "
        f"{_rescheduled_to(makeup)}. Room {makeup.room} is now held for you, and "
        "staff will check it at that time. Mark the class done after you hold it."
    )
    user = await _user_for_teacher(session, makeup.teacher_initial)
    if user is not None:
        await _dispatch(
            session,
            user_id=user.id,
            kind=NotificationKind.MAKEUP_SCHEDULED,
            title=f"Rescheduled — {original.course_code} in {makeup.room}",
            body=body,
            link=_makeup_link(makeup),
        )
    for admin in await _admins(session):
        await _dispatch(
            session,
            user_id=admin.id,
            kind=NotificationKind.MAKEUP_SCHEDULED,
            title="Class rescheduled into an empty room",
            body=(
                f"{makeup.teacher_initial} rescheduled {_describe(original)} to "
                f"{_rescheduled_to(makeup)}. An empty room needs no approval, so it is "
                "booked and in staff checking."
            ),
            link="/today",
        )


async def notify_extra_booked(session: AsyncSession, instance: ClassInstance) -> None:
    """Tell the admins a room was taken for an extra class.

    Like an in-room reschedule it needed no decision, so nothing reaches the
    approvals queue; the admins hear of it here instead.
    """
    for admin in await _admins(session):
        await _dispatch(
            session,
            user_id=admin.id,
            kind=NotificationKind.EXTRA_BOOKED,
            title=f"Extra class booked in {instance.room}",
            body=(
                f"{instance.teacher_initial} booked {instance.room} for an extra class: "
                f"{_describe(instance)}. An empty room needs no approval, so it is "
                "booked and in staff checking."
            ),
            link="/today",
        )


async def notify_makeup_decision(
    session: AsyncSession, makeup: MakeupClass, original: ClassInstance
) -> None:
    """Tell the teacher the HoD's answer, naming the class and where it now happens."""
    user = await _user_for_teacher(session, makeup.teacher_initial)
    if user is None:
        return
    online = makeup.mode is MakeupMode.ONLINE
    approved = makeup.status is not MakeupStatus.REJECTED
    missed = _missed(original)
    if approved:
        title = f"Reschedule approved — {original.course_code} {'online' if online else 'in class'}"
        body = f"Your missed class {missed} is rescheduled to {_rescheduled_to(makeup)}."
        body += (
            " After the class, submit its Drive link to mark it done."
            if online
            else " Staff will check the room at that time. Mark it done after the class."
        )
    else:
        title = f"Reschedule rejected — {original.course_code}"
        body = (
            f"Your request to move {missed} to {_rescheduled_to(makeup)} was rejected."
        )
        if not online:
            body += " Please request another slot."
    if makeup.decision_note:
        body += f" Note from the Head of Department: {makeup.decision_note}"
    await _dispatch(
        session,
        user_id=user.id,
        kind=NotificationKind.ONLINE_DECISION if online else NotificationKind.MAKEUP_DECISION,
        title=title,
        body=body,
        link=_makeup_link(makeup),
    )


async def notify_makeup_due(
    session: AsyncSession, makeup: MakeupClass, original: ClassInstance
) -> None:
    """Remind the teacher that a rescheduled class has ended and is not marked done."""
    user = await _user_for_teacher(session, makeup.teacher_initial)
    if user is None:
        return
    online = makeup.mode is MakeupMode.ONLINE
    await _dispatch(
        session,
        user_id=user.id,
        kind=NotificationKind.MAKEUP_REMINDER,
        title=(
            f"Submit the Drive link — {original.course_code}"
            if online
            else f"Mark your makeup class done — {original.course_code}"
        ),
        body=(
            f"Your rescheduled {original.course_code} for section {original.section} "
            f"({_rescheduled_to(makeup)}) has ended. "
            + (
                "Submit the Drive link of the class to mark it done."
                if online
                else "Mark it done once you have held it."
            )
        ),
        link=_makeup_link(makeup),
    )


async def notify_dispute(
    session: AsyncSession, instance: ClassInstance, note: str | None
) -> None:
    """Tell the HoD a teacher disputed a monitoring record."""
    for admin in await _admins(session):
        await _dispatch(
            session,
            user_id=admin.id,
            kind=NotificationKind.DISPUTE_RAISED,
            title="Monitoring record disputed",
            body=(
                f"{instance.teacher_initial} disputed the record for {_describe(instance)}."
                + (f" Reason: {note}" if note else "")
            ),
            link="/dashboard",
        )


async def mark_read(session: AsyncSession, user_id: int, notification_id: int) -> None:
    await session.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == user_id)
        .values(read_at=utcnow())
    )


async def mark_all_read(session: AsyncSession, user_id: int) -> None:
    await session.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        .values(read_at=utcnow())
    )

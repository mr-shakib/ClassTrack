"""Notification delivery.

Delivery sits behind ``NotificationChannel`` so adding email or SMS (SRS 2.2) is
a new class beside ``InAppChannel``, not a change to any caller.
"""

from __future__ import annotations

import logging
from typing import Protocol

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from classtrack.db.base import utcnow
from classtrack.models import (
    ADMIN_ROLES,
    CheckOutcome,
    ClassInstance,
    MakeupClass,
    MakeupMode,
    MakeupStatus,
    Notification,
    NotificationKind,
    User,
)

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
    return list(
        (await session.scalars(select(User).where(User.role.in_(ADMIN_ROLES)))).all()
    )


def _describe(instance: ClassInstance) -> str:
    return (
        f"{instance.course_code} for section {instance.section} "
        f"scheduled at {instance.time_slot} on {instance.date:%d %B %Y}"
    )


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
    """
    user = await _user_for_teacher(session, instance.teacher_initial)
    if user is None:
        logger.warning(
            "No user account for teacher %s; report notification skipped",
            instance.teacher_initial,
        )
        return
    link = "/teacher"
    if outcome is CheckOutcome.TEACHER_NOT_FOUND:
        title = "Reported absent — reschedule required"
        body = (
            f"Office staff found no teacher in {instance.room} for your "
            f"{_describe(instance)}. If you cannot hold it, request a reschedule now. "
            "If you are on your way, staff can still record you as late."
        )
        link = _reschedule_link(instance)
    else:
        title = "Reported late to class"
        body = f"Office staff recorded a late start for your {_describe(instance)}."
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


async def notify_makeup_request(
    session: AsyncSession, makeup: MakeupClass, instance: ClassInstance
) -> None:
    """Tell the HoD a reschedule needs a decision (BR-11)."""
    online = makeup.mode is MakeupMode.ONLINE
    where = "online" if online else f"in {makeup.room}"
    for admin in await _admins(session):
        await _dispatch(
            session,
            user_id=admin.id,
            kind=NotificationKind.ONLINE_REQUEST if online else NotificationKind.MAKEUP_REQUEST,
            title="Online makeup request" if online else "Reschedule request",
            body=(
                f"{makeup.teacher_initial} requested to reschedule {_describe(instance)} "
                f"to {makeup.date:%d %B %Y} at {makeup.time_slot}, {where}."
                + (" A Drive link is attached for review." if makeup.drive_link else "")
            ),
            link="/approvals",
        )


def _makeup_link(makeup: MakeupClass) -> str:
    return f"/teacher#makeup-{makeup.id}"


def _rescheduled_to(makeup: MakeupClass) -> str:
    where = "online" if makeup.mode is MakeupMode.ONLINE else f"in room {makeup.room}"
    return f"{makeup.date:%A %d %B %Y} at {makeup.time_slot}, {where}"


async def notify_makeup_decision(
    session: AsyncSession, makeup: MakeupClass, original: ClassInstance
) -> None:
    """Tell the teacher the HoD's answer, naming the class and where it now happens."""
    user = await _user_for_teacher(session, makeup.teacher_initial)
    if user is None:
        return
    online = makeup.mode is MakeupMode.ONLINE
    approved = makeup.status is not MakeupStatus.REJECTED
    missed = (
        f"{original.course_code} for section {original.section} "
        f"({original.date:%d %B %Y}, {original.time_slot}, {original.room})"
    )
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

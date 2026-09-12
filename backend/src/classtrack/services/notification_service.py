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
    ClassInstance,
    MakeupClass,
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
        title="Class marked as missed",
        body=(
            f"Your {_describe(instance)} has been marked as missed. "
            "Please review the record and take the required action."
        ),
        link="/teacher",
    )


async def notify_online_request(
    session: AsyncSession, makeup: MakeupClass, instance: ClassInstance
) -> None:
    """Tell the HoD an online makeup needs a decision (BR-11)."""
    for admin in await _admins(session):
        await _dispatch(
            session,
            user_id=admin.id,
            kind=NotificationKind.ONLINE_REQUEST,
            title="Online makeup request",
            body=(
                f"{makeup.teacher_initial} requested an online makeup for "
                f"{_describe(instance)}, proposed {makeup.date:%d %B %Y} at {makeup.time_slot}."
            ),
            link="/approvals",
        )


async def notify_online_decision(session: AsyncSession, makeup: MakeupClass) -> None:
    user = await _user_for_teacher(session, makeup.teacher_initial)
    if user is None:
        return
    approved = makeup.status.value == "APPROVED"
    await _dispatch(
        session,
        user_id=user.id,
        kind=NotificationKind.ONLINE_DECISION,
        title=f"Online makeup {'approved' if approved else 'rejected'}",
        body=(
            f"Your online makeup on {makeup.date:%d %B %Y} at {makeup.time_slot} was "
            f"{'approved' if approved else 'rejected'}."
            + (f" Note: {makeup.decision_note}" if makeup.decision_note else "")
        ),
        link="/teacher",
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

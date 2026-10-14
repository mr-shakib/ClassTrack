"""Notifications an admin writes, to teachers and staff.

Each reaches its readers' bell and phones through the same channels as every
other notification. The audit log keeps what was sent, by whom and to how many,
and the Notifications tab reads its history back from there.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from classtrack.core.errors import ValidationError
from classtrack.models import AuditLog, PushDevice, RoleKind, User
from classtrack.services import audit_service, notification_service

Audience = Literal["everyone", "teachers", "staff", "chosen"]

_ACTION = "notification_sent"


@dataclass(frozen=True)
class Sent:
    sent_to: int
    #: Of those, how many have signed in on the app on a phone.
    on_phones: int


@dataclass(frozen=True)
class Recipient:
    user: User
    on_phone: bool


@dataclass(frozen=True)
class Record:
    id: int
    title: str
    body: str
    audience: str
    sent_to: int
    sent_by: str | None
    created_at: datetime


async def recipients(session: AsyncSession) -> list[Recipient]:
    """Every active account, to choose readers from, by name."""
    users = (
        await session.scalars(select(User).where(User.is_active).order_by(User.full_name))
    ).all()
    on_phones = set((await session.scalars(select(PushDevice.user_id).distinct())).all())
    return [Recipient(user=u, on_phone=u.id in on_phones) for u in users]


async def _readers(
    session: AsyncSession, *, sender: User, audience: Audience, user_ids: list[int]
) -> list[User]:
    query = select(User).where(User.is_active)
    if audience == "chosen":
        if not user_ids:
            raise ValidationError("Choose who to send it to.")
        # Whoever was chosen, the sender too: that is how one tries it out.
        return list((await session.scalars(query.where(User.id.in_(set(user_ids))))).all())
    if audience == "teachers":
        query = query.where(User.teacher_initial.is_not(None), User.of_kind(RoleKind.TEACHER))
    elif audience == "staff":
        query = query.where(User.of_kind(RoleKind.STAFF))
    # A broad audience leaves out the sender, who knows what they wrote.
    return list((await session.scalars(query.where(User.id != sender.id))).all())


async def send(
    session: AsyncSession,
    *,
    sender: User,
    title: str,
    body: str,
    audience: Audience,
    user_ids: list[int] | None = None,
) -> Sent:
    readers = await _readers(session, sender=sender, audience=audience, user_ids=user_ids or [])
    if not readers:
        raise ValidationError("Nobody is in that group, so nothing was sent.")
    ids = [u.id for u in readers]
    for user_id in ids:
        await notification_service.notify_announcement(
            session, user_id=user_id, title=title, body=body
        )
    on_phones = await session.scalar(
        select(func.count(func.distinct(PushDevice.user_id))).where(PushDevice.user_id.in_(ids))
    )
    audit_service.record(
        session,
        actor_id=sender.id,
        entity_type="notification",
        entity_id=0,
        action=_ACTION,
        after={
            "title": title,
            "body": body,
            "audience": audience,
            "sent_to": len(ids),
            **({"user_ids": sorted(ids)} if audience == "chosen" else {}),
        },
    )
    return Sent(sent_to=len(ids), on_phones=on_phones or 0)


async def history(session: AsyncSession, *, limit: int = 20) -> list[Record]:
    """What was sent, newest first."""
    rows = (
        await session.execute(
            select(AuditLog, User.full_name)
            .outerjoin(User, User.id == AuditLog.actor_id)
            .where(AuditLog.action == _ACTION)
            .order_by(AuditLog.id.desc())
            .limit(limit)
        )
    ).all()
    out = []
    for row, name in rows:
        after = row.after or {}
        out.append(
            Record(
                id=row.id,
                title=str(after.get("title", "")),
                body=str(after.get("body", "")),
                audience=str(after.get("audience", "")),
                sent_to=int(after.get("sent_to", 0)),
                sent_by=name,
                created_at=row.created_at,
            )
        )
    return out

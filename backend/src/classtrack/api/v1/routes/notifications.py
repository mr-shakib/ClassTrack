"""In-app notifications."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from classtrack.api.deps import CurrentUser, SessionDep
from classtrack.models import Notification
from classtrack.schemas.admin import NotificationOut
from classtrack.schemas.common import Message
from classtrack.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut], summary="My notifications")
async def list_mine(
    session: SessionDep, user: CurrentUser, unread: bool = False, limit: int = 50
) -> list[NotificationOut]:
    query = select(Notification).where(Notification.user_id == user.id)
    if unread:
        query = query.where(Notification.read_at.is_(None))
    query = query.order_by(Notification.created_at.desc()).limit(limit)
    return [NotificationOut.model_validate(n) for n in (await session.scalars(query)).all()]


@router.post("/{notification_id}/read", response_model=Message, summary="Mark read")
async def mark_read(notification_id: int, session: SessionDep, user: CurrentUser) -> Message:
    await notification_service.mark_read(session, user.id, notification_id)
    await session.commit()
    return Message(detail="Marked read")


@router.post("/read-all", response_model=Message, summary="Mark all read")
async def mark_all_read(session: SessionDep, user: CurrentUser) -> Message:
    await notification_service.mark_all_read(session, user.id)
    await session.commit()
    return Message(detail="All marked read")

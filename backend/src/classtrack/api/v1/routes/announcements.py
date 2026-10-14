"""Notifications an admin writes to teachers and staff."""

from __future__ import annotations

from fastapi import APIRouter

from classtrack.api.deps import NotifierUser, SessionDep
from classtrack.schemas.admin import (
    AnnouncementIn,
    AnnouncementOut,
    AnnouncementSent,
    RecipientOut,
)
from classtrack.services import announcement_service

router = APIRouter(prefix="/admin/notifications", tags=["admin"])


@router.get("", response_model=list[AnnouncementOut], summary="Notifications sent")
async def sent(session: SessionDep, user: NotifierUser) -> list[AnnouncementOut]:  # noqa: ARG001
    return [AnnouncementOut(**vars(r)) for r in await announcement_service.history(session)]


@router.get(
    "/recipients", response_model=list[RecipientOut], summary="Who a notification can go to"
)
async def recipients(session: SessionDep, user: NotifierUser) -> list[RecipientOut]:  # noqa: ARG001
    return [
        RecipientOut(
            id=r.user.id,
            full_name=r.user.full_name,
            teacher_initial=r.user.teacher_initial,
            roles=" · ".join(role.name for role in r.user.ordered_roles),
            is_teacher=r.user.is_teacher,
            is_staff=r.user.is_staff,
            on_phone=r.on_phone,
        )
        for r in await announcement_service.recipients(session)
    ]


@router.post("", response_model=AnnouncementSent, summary="Send a notification")
async def send(
    payload: AnnouncementIn, session: SessionDep, user: NotifierUser
) -> AnnouncementSent:
    """To the bell and, through the push sender, to phones once committed."""
    result = await announcement_service.send(
        session,
        sender=user,
        title=payload.title,
        body=payload.body,
        audience=payload.audience,
        user_ids=payload.user_ids,
    )
    await session.commit()
    return AnnouncementSent(sent_to=result.sent_to, on_phones=result.on_phones)

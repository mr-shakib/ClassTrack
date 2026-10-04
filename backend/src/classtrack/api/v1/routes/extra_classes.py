"""Extra classes a teacher books in an empty room, on top of the routine.

The room and conflict lookups are the makeup ones -- ``/makeup/free-rooms`` and
``/makeup/check-conflict`` -- since a room is free or taken whatever the class.
"""

from __future__ import annotations

from fastapi import APIRouter

from classtrack.api.deps import OwnTeacherUser, SessionDep
from classtrack.models import ClassInstance
from classtrack.schemas.extra import ExtraClassRequest, ExtraSectionOut
from classtrack.schemas.monitoring import InstanceOut
from classtrack.services import extra_class_service, status_engine

router = APIRouter(prefix="/extra-classes", tags=["extra classes"])


def _out(instance: ClassInstance) -> InstanceOut:
    out = InstanceOut.model_validate(instance)
    out.status = status_engine.derive(instance)
    return out


@router.get("/sections", response_model=list[ExtraSectionOut], summary="Sections you may book for")
async def sections(session: SessionDep, user: OwnTeacherUser) -> list[ExtraSectionOut]:
    rows = await extra_class_service.my_sections(session, user.teacher_initial or "")
    return [ExtraSectionOut.model_validate(r) for r in rows]


@router.get("", response_model=list[InstanceOut], summary="Your extra classes")
async def mine(session: SessionDep, user: OwnTeacherUser) -> list[InstanceOut]:
    rows = await extra_class_service.list_mine(session, user.teacher_initial or "")
    return [_out(r) for r in rows]


@router.post("", response_model=InstanceOut, summary="Book a room for an extra class")
async def book(
    payload: ExtraClassRequest, session: SessionDep, user: OwnTeacherUser
) -> InstanceOut:
    """Booked at once, with no approval. Staff check it like any class."""
    instance = await extra_class_service.book(
        session,
        user=user,
        course_code=payload.course_code,
        section=payload.section,
        on=payload.date,
        time_slot=payload.time_slot,
        room=payload.room,
    )
    await session.commit()
    return _out(instance)


@router.post("/{instance_id}/cancel", response_model=InstanceOut, summary="Cancel your extra class")
async def cancel(instance_id: int, session: SessionDep, user: OwnTeacherUser) -> InstanceOut:
    """Before it starts, which gives the room back."""
    instance = await extra_class_service.cancel(session, user=user, instance_id=instance_id)
    await session.commit()
    return _out(instance)

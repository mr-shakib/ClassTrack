"""Class instance queries, and the teacher's response to a missed record."""

from __future__ import annotations

from datetime import date as Date

from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from classtrack.api.deps import AdminUser, CurrentUser, SessionDep, scope_teacher
from classtrack.core.errors import ForbiddenError, NotFoundError, ValidationError
from classtrack.db.base import utcnow
from classtrack.models import ClassInstance, ClassStatus, Role, TeacherResponse
from classtrack.schemas.monitoring import (
    CancelRequest,
    InstanceOut,
    RespondRequest,
)
from classtrack.services import audit_service, notification_service, status_engine

router = APIRouter(prefix="/instances", tags=["instances"])


def _serialise(inst: ClassInstance) -> InstanceOut:
    out = InstanceOut.model_validate(inst)
    out.status = status_engine.derive(inst)
    return out


@router.get("", response_model=list[InstanceOut], summary="Filter class instances")
async def list_instances(
    session: SessionDep,
    user: CurrentUser,
    on: Date | None = Query(default=None, alias="date"),
    teacher: str | None = None,
    room: str | None = None,
    section: str | None = None,
    status: ClassStatus | None = None,
    limit: int = Query(default=200, le=1000),
) -> list[InstanceOut]:
    # A TEACHER is forced onto their own initial regardless of the query.
    initial = scope_teacher(user, teacher)

    query = select(ClassInstance).options(selectinload(ClassInstance.check))
    if on is not None:
        query = query.where(ClassInstance.date == on)
    if initial is not None:
        query = query.where(ClassInstance.teacher_initial == initial)
    if room is not None:
        query = query.where(ClassInstance.room == room.upper())
    if section is not None:
        query = query.where(ClassInstance.section == section)
    if status is not None:
        query = query.where(ClassInstance.status == status)

    query = query.order_by(ClassInstance.date, ClassInstance.start_min).limit(limit)
    return [_serialise(i) for i in (await session.scalars(query)).all()]


@router.get("/{instance_id}", response_model=InstanceOut, summary="One instance")
async def get_instance(
    instance_id: int, session: SessionDep, user: CurrentUser
) -> InstanceOut:
    inst = await session.scalar(
        select(ClassInstance)
        .where(ClassInstance.id == instance_id)
        .options(selectinload(ClassInstance.check))
    )
    if inst is None:
        raise NotFoundError(f"No class instance with id {instance_id}")
    if user.role is Role.TEACHER and inst.teacher_initial != user.teacher_initial:
        raise ForbiddenError("You may only view your own records.")
    return _serialise(inst)


@router.post(
    "/{instance_id}/respond",
    response_model=InstanceOut,
    summary="Confirm or dispute a missed class",
)
async def respond(
    instance_id: int,
    payload: RespondRequest,
    session: SessionDep,
    user: CurrentUser,
) -> InstanceOut:
    """BR-08.

    A dispute deliberately does **not** change the stored status: the original
    monitoring record has to survive for the audit trail to mean anything. It
    flags the record for HoD review instead.
    """
    inst = await session.scalar(
        select(ClassInstance)
        .where(ClassInstance.id == instance_id)
        .options(selectinload(ClassInstance.check))
    )
    if inst is None:
        raise NotFoundError(f"No class instance with id {instance_id}")

    if user.role is Role.TEACHER and inst.teacher_initial != user.teacher_initial:
        raise ForbiddenError("You may only respond to your own records.")
    if inst.status is not ClassStatus.MISSED:
        raise ValidationError(
            "Only a missed class can be confirmed or disputed.",
            detail={"status": inst.status.value if inst.status else None},
        )

    before = {"teacher_response": inst.teacher_response.value if inst.teacher_response else None}
    inst.teacher_response = payload.response
    inst.response_note = payload.note
    inst.responded_at = utcnow()

    audit_service.record(
        session,
        actor_id=user.id,
        entity_type="class_instance",
        entity_id=inst.id,
        action="teacher_responded",
        before=before,
        after={"teacher_response": payload.response.value},
        reason=payload.note,
    )
    if payload.response is TeacherResponse.DISPUTED:
        await notification_service.notify_dispute(session, inst, payload.note)

    await session.commit()
    return _serialise(inst)


@router.post("/{instance_id}/cancel", response_model=InstanceOut, summary="Cancel a class")
async def cancel(
    instance_id: int,
    payload: CancelRequest,
    session: SessionDep,
    user: AdminUser,
) -> InstanceOut:
    inst = await session.get(ClassInstance, instance_id)
    if inst is None:
        raise NotFoundError(f"No class instance with id {instance_id}")

    before = {"status": inst.status.value if inst.status else None}
    inst.status = ClassStatus.CANCELLED
    inst.resolved_at = utcnow()
    audit_service.record(
        session,
        actor_id=user.id,
        entity_type="class_instance",
        entity_id=inst.id,
        action="cancelled",
        before=before,
        after={"status": ClassStatus.CANCELLED.value},
        reason=payload.reason,
    )
    await session.commit()
    return _serialise(inst)

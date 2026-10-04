"""Makeup scheduling and the online-approval queue (BR-09 .. BR-13)."""

from __future__ import annotations

from datetime import date as Date

from fastapi import APIRouter, Query
from sqlalchemy import select

from classtrack.api.deps import (
    ApproverUser,
    CurrentUser,
    ReschedulerUser,
    RoomFinderUser,
    SessionDep,
)
from classtrack.models import (
    ClassInstance,
    MakeupClass,
    MakeupStatus,
    Permission,
    Teacher,
)
from classtrack.schemas.makeup import (
    CompleteRequest,
    ConflictCheckRequest,
    ConflictReportOut,
    DecisionRequest,
    FreeRoomOut,
    MakeupCreateRequest,
    MakeupOut,
)
from classtrack.services import conflict_service, makeup_service

router = APIRouter(tags=["makeup"])


async def _decorate(session, makeups: list[MakeupClass]) -> list[MakeupOut]:
    """Attach the original class details the UI needs to show context."""
    if not makeups:
        return []
    originals = {
        i.id: i
        for i in (
            await session.scalars(
                select(ClassInstance).where(
                    ClassInstance.id.in_([m.original_instance_id for m in makeups])
                )
            )
        ).all()
    }
    names = {
        t.initial: t.name
        for t in (
            await session.scalars(
                select(Teacher).where(Teacher.initial.in_([m.teacher_initial for m in makeups]))
            )
        ).all()
    }
    out = []
    for makeup in makeups:
        item = MakeupOut.model_validate(makeup)
        original = originals.get(makeup.original_instance_id)
        if original is not None:
            item.original_course_code = original.course_code
            item.original_section = original.section
            item.original_date = original.date
            item.original_time_slot = original.time_slot
            item.original_room = original.room
        item.teacher_name = names.get(makeup.teacher_initial)
        item.ends_at = makeup_service.ends_at(makeup)
        out.append(item)
    return out


@router.post(
    "/makeup/check-conflict",
    response_model=ConflictReportOut,
    summary="Validate a proposed makeup slot",
)
async def check_conflict(
    payload: ConflictCheckRequest, session: SessionDep, user: RoomFinderUser
) -> ConflictReportOut:
    initial = payload.teacher_initial
    # Only someone who reschedules for any teacher may ask about another's time.
    if not user.can(Permission.RESCHEDULE_ANY):
        initial = user.teacher_initial
    slot, start_min, end_min = makeup_service.period_for(
        time_slot=payload.time_slot, start_time=payload.start_time
    )
    report = await conflict_service.check(
        session,
        on=payload.date,
        time_slot=slot,
        start_min=start_min,
        end_min=end_min,
        teacher_initial=initial or "",
        room=payload.room,
        section=payload.section,
    )
    return ConflictReportOut.model_validate(report.as_dict())


@router.get(
    "/makeup/free-rooms",
    response_model=list[FreeRoomOut],
    summary="Empty rooms for a date and slot",
)
async def free_rooms(
    session: SessionDep,
    user: RoomFinderUser,  # noqa: ARG001
    on: Date = Query(alias="date"),
    time_slot: str = Query(),
) -> list[FreeRoomOut]:
    """The rooms a teacher may pick for a physical reschedule."""
    rows = await conflict_service.free_rooms(session, on=on, time_slot=time_slot)
    return [FreeRoomOut.model_validate(r) for r in rows]


@router.post("/makeup", response_model=MakeupOut, summary="Request a makeup class")
async def create(
    payload: MakeupCreateRequest, session: SessionDep, user: ReschedulerUser
) -> MakeupOut:
    makeup = await makeup_service.create(
        session,
        original_instance_id=payload.original_instance_id,
        user=user,
        mode=payload.mode,
        on=payload.date,
        time_slot=payload.time_slot,
        start_time=payload.start_time,
        room=payload.room,
        reason=payload.reason,
        drive_link=payload.drive_link,
    )
    await session.commit()
    return (await _decorate(session, [makeup]))[0]


@router.get("/makeup", response_model=list[MakeupOut], summary="List makeup classes")
async def list_makeups(
    session: SessionDep, user: CurrentUser, status: MakeupStatus | None = None
) -> list[MakeupOut]:
    query = select(MakeupClass).order_by(MakeupClass.date.desc())
    # Teachers see only their own, unless another role shows them everyone's.
    if not user.sees_every_teacher:
        query = query.where(MakeupClass.teacher_initial == user.teacher_initial)
    if status is not None:
        query = query.where(MakeupClass.status == status)
    return await _decorate(session, list((await session.scalars(query)).all()))


@router.get(
    "/approvals/pending",
    response_model=list[MakeupOut],
    summary="Reschedule requests awaiting a decision",
)
async def pending(session: SessionDep, user: ApproverUser) -> list[MakeupOut]:  # noqa: ARG001
    rows = (
        await session.scalars(
            select(MakeupClass)
            .where(MakeupClass.status == MakeupStatus.PENDING)
            .order_by(MakeupClass.created_at)
        )
    ).all()
    return await _decorate(session, list(rows))


@router.post(
    "/approvals/{makeup_id}/decide",
    response_model=MakeupOut,
    summary="Approve or reject a reschedule request",
)
async def decide(
    makeup_id: int, payload: DecisionRequest, session: SessionDep, user: ApproverUser
) -> MakeupOut:
    makeup = await makeup_service.decide(
        session,
        makeup_id=makeup_id,
        user=user,
        approve=payload.decision == "APPROVE",
        note=payload.note,
    )
    await session.commit()
    return (await _decorate(session, [makeup]))[0]


@router.post(
    "/makeup/{makeup_id}/complete", response_model=MakeupOut, summary="Mark completed"
)
async def complete(
    makeup_id: int,
    session: SessionDep,
    user: ReschedulerUser,
    payload: CompleteRequest | None = None,
) -> MakeupOut:
    """The teacher marks their own class done after it ends; online needs a Drive link."""
    makeup = await makeup_service.complete(
        session,
        makeup_id=makeup_id,
        user=user,
        drive_link=payload.drive_link if payload else None,
    )
    await session.commit()
    return (await _decorate(session, [makeup]))[0]

"""Room-wise staff checking, and the live dashboard (BR-02)."""

from __future__ import annotations

from datetime import date as Date

from fastapi import APIRouter, Query

from classtrack.api.deps import AdminUser, CheckingUser, SessionDep
from classtrack.core.errors import ValidationError
from classtrack.routine.lattice import SLOTS
from classtrack.schemas.monitoring import (
    CheckingScreen,
    CheckRequest,
    CheckResponse,
    DashboardOut,
)
from classtrack.services import check_service, checking_service, status_engine

router = APIRouter(tags=["monitoring"])


@router.get(
    "/checking/rooms",
    response_model=CheckingScreen,
    summary="Room-wise list for a date and slot",
)
async def rooms(
    session: SessionDep,
    user: CheckingUser,  # noqa: ARG001 -- role gate
    on: Date | None = Query(default=None, alias="date"),
    slot: str | None = Query(default=None),
) -> CheckingScreen:
    if slot is not None and slot not in SLOTS:
        raise ValidationError(
            f"{slot!r} is not a routine slot.", detail={"valid_slots": list(SLOTS)}
        )
    data = await checking_service.checking_screen(session, on=on, slot=slot)
    return CheckingScreen.model_validate(data)


@router.post(
    "/checking/{instance_id}",
    response_model=CheckResponse,
    summary="Submit a monitoring result",
)
async def submit(
    instance_id: int,
    payload: CheckRequest,
    session: SessionDep,
    user: CheckingUser,
) -> CheckResponse:
    """Idempotent: re-submitting amends the existing check rather than adding one."""
    instance = await check_service.submit(
        session,
        instance_id=instance_id,
        user=user,
        outcome=payload.outcome,
        arrival_time=payload.arrival_time,
        remark=payload.remark,
    )
    await session.commit()
    return CheckResponse(
        instance_id=instance.id,
        status=status_engine.derive(instance),
        late_minutes=instance.check.late_minutes if instance.check else None,
        checked_by=user.full_name,
        checked_at=instance.check.checked_at if instance.check else status_engine.now_local(),
    )


@router.get("/dashboard/live", response_model=DashboardOut, summary="Live overview")
async def dashboard(session: SessionDep, user: AdminUser) -> DashboardOut:  # noqa: ARG001
    return DashboardOut.model_validate(await checking_service.dashboard(session))


@router.get("/meta/slots", summary="The routine lattice slots")
async def slots() -> dict[str, object]:
    from classtrack.routine.lattice import DAYS

    return {"days": list(DAYS), "slots": list(SLOTS)}

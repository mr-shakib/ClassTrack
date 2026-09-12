"""Room-wise staff checking, and the live dashboard (BR-02)."""

from __future__ import annotations

from datetime import date as Date

from fastapi import APIRouter, Query

from classtrack.api.deps import AdminUser, CheckingUser, SessionDep
from classtrack.core.errors import ValidationError
from classtrack.models import Role
from classtrack.routine.lattice import SLOTS
from classtrack.schemas.monitoring import (
    CheckingScreen,
    CheckRequest,
    CheckResponse,
    DashboardOut,
)
from classtrack.services import (
    assignment_service,
    check_service,
    checking_service,
    status_engine,
)

router = APIRouter(tags=["monitoring"])


@router.get(
    "/checking/rooms",
    response_model=CheckingScreen,
    summary="Room-wise list for a date and slot",
)
async def rooms(
    session: SessionDep,
    user: CheckingUser,
    on: Date | None = Query(default=None, alias="date"),
    slot: str | None = Query(default=None),
    all_rooms: bool = Query(default=False, alias="all"),
) -> CheckingScreen:
    """Room-wise list, narrowed to the floors this staff member covers.

    Staff with no assignment see everything, so an unzoned account can still
    work. Admins are never narrowed, but may pass ``all=false`` to preview what
    a zoned account would see.
    """
    if slot is not None and slot not in SLOTS:
        raise ValidationError(
            f"{slot!r} is not a routine slot.", detail={"valid_slots": list(SLOTS)}
        )

    only_zones: list[str] | None = None
    if user.role is Role.STAFF and not all_rooms:
        assigned = await assignment_service.zones_for_user(session, user.id)
        only_zones = assigned or None

    data = await checking_service.checking_screen(
        session, on=on, slot=slot, only_zones=only_zones
    )
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

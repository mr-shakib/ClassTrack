"""Room-wise staff checking, and the live dashboard (BR-02)."""

from __future__ import annotations

from datetime import date as Date
from datetime import timedelta

from fastapi import APIRouter, Query

from classtrack.api.deps import CheckingUser, ManagerUser, SessionDep
from classtrack.core.errors import ValidationError
from classtrack.models import Role
from classtrack.routine.lattice import SLOTS
from classtrack.schemas.monitoring import (
    CheckingScreen,
    CheckRequest,
    CheckResponse,
    DashboardOut,
    DayStatus,
    RoomRow,
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
) -> CheckingScreen:
    """Every room in the slot, grouped into floors.

    A staff member's assigned floors are their round, so they are listed first
    and marked -- but never a limit. Someone passing another floor can check its
    classes too, rather than leave them unreported because the person who covers
    that floor is elsewhere.
    """
    if slot is not None and slot not in SLOTS:
        raise ValidationError(
            f"{slot!r} is not a routine slot.", detail={"valid_slots": list(SLOTS)}
        )

    my_zones = (
        await assignment_service.zones_for_user(session, user.id)
        if user.role is Role.STAFF
        else None
    )
    data = await checking_service.checking_screen(
        session, on=on, slot=slot, my_zones=my_zones
    )
    return CheckingScreen.model_validate(data)


@router.get(
    "/checking/search",
    response_model=list[RoomRow],
    summary="A teacher's classes over a range, to find one to correct",
)
async def search(
    session: SessionDep,
    user: CheckingUser,  # noqa: ARG001
    teacher: str = Query(min_length=1, max_length=16),
    start: Date | None = Query(default=None, alias="from"),
    end: Date | None = Query(default=None, alias="to"),
) -> list[RoomRow]:
    """Defaults to the last two weeks, up to today.

    Anyone who may check may search; whether a found class can still be changed
    is the submit endpoint's decision, as it is from the room screen.
    """
    end = end or status_engine.now_local().date()
    start = start or end - timedelta(days=14)
    if end < start:
        raise ValidationError("The end of the range precedes its start.")
    if (end - start).days > 186:
        raise ValidationError("Search at most six months at a time.")
    rows = await checking_service.search_by_teacher(
        session, teacher_initial=teacher.strip(), start=start, end=end
    )
    return [RoomRow.model_validate(r) for r in rows]


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
    """Idempotent: re-submitting amends the existing check rather than adding one.

    Staff may only submit while the checking window is open. An admin may
    correct a record afterwards by supplying a reason, which is audited as an
    override rather than an observation.
    """
    instance = await check_service.submit(
        session,
        instance_id=instance_id,
        user=user,
        outcome=payload.outcome,
        arrival_time=payload.arrival_time,
        remark=payload.remark,
        reason=payload.reason,
    )
    outside = not status_engine.is_checkable(instance)
    await session.commit()
    return CheckResponse(
        instance_id=instance.id,
        status=status_engine.derive(instance),
        late_minutes=instance.check.late_minutes if instance.check else None,
        checked_by=user.full_name,
        checked_at=instance.check.checked_at if instance.check else status_engine.now_local(),
        outside_window=outside,
    )


@router.get("/dashboard/live", response_model=DashboardOut, summary="Live overview")
async def dashboard(session: SessionDep, user: ManagerUser) -> DashboardOut:  # noqa: ARG001
    return DashboardOut.model_validate(await checking_service.dashboard(session))


@router.get(
    "/dashboard/day",
    response_model=DayStatus,
    summary="Every class on one day, for filtering by teacher, floor or status",
)
async def day(
    session: SessionDep,
    user: ManagerUser,  # noqa: ARG001
    on: Date | None = Query(default=None, alias="date"),
) -> DayStatus:
    return DayStatus.model_validate(await checking_service.day_status(session, on=on))


@router.get("/meta/slots", summary="The routine lattice slots")
async def slots() -> dict[str, object]:
    from classtrack.routine.lattice import DAYS

    return {"days": list(DAYS), "slots": list(SLOTS)}

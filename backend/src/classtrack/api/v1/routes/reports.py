"""Reporting endpoints (SRS 12)."""

from __future__ import annotations

from datetime import date as Date
from datetime import timedelta

from fastapi import APIRouter, Query

from classtrack.api.deps import AdminUser, CurrentUser, SessionDep, scope_teacher
from classtrack.core.errors import ValidationError
from classtrack.schemas.reports import DailyReport, StaffReport, TeacherReport
from classtrack.services import report_service, status_engine

router = APIRouter(prefix="/reports", tags=["reports"])


def _range(start: Date | None, end: Date | None) -> tuple[Date, Date]:
    today = status_engine.now_local().date()
    start = start or today - timedelta(days=30)
    end = end or today
    if end < start:
        raise ValidationError("The end of the range precedes its start.")
    return start, end


@router.get("/daily", response_model=DailyReport, summary="One day's summary")
async def daily(
    session: SessionDep,
    user: AdminUser,  # noqa: ARG001
    on: Date | None = Query(default=None, alias="date"),
) -> DailyReport:
    on = on or status_engine.now_local().date()
    return DailyReport.model_validate(await report_service.daily(session, on=on))


@router.get("/teacher", response_model=TeacherReport, summary="Teacher-wise report")
async def teacher(
    session: SessionDep,
    user: CurrentUser,
    initial: str | None = Query(default=None, alias="teacher"),
    start: Date | None = Query(default=None, alias="from"),
    end: Date | None = Query(default=None, alias="to"),
) -> TeacherReport:
    # A TEACHER is forced onto their own initial (403 if they ask for another).
    resolved = scope_teacher(user, initial)
    if resolved is None:
        raise ValidationError("A teacher initial is required.")
    start, end = _range(start, end)
    return TeacherReport.model_validate(
        await report_service.teacher_report(
            session, teacher_initial=resolved, start=start, end=end
        )
    )


@router.get("/staff", response_model=StaffReport, summary="Monitoring completion")
async def staff(
    session: SessionDep,
    user: AdminUser,  # noqa: ARG001
    start: Date | None = Query(default=None, alias="from"),
    end: Date | None = Query(default=None, alias="to"),
) -> StaffReport:
    start, end = _range(start, end)
    return StaffReport.model_validate(
        await report_service.staff_report(session, start=start, end=end)
    )

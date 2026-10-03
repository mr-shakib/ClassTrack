"""Reporting endpoints (SRS 12).

Every period report takes either two dates (``from``/``to``) or a term of a
semester (``semester``/``term``). A term wins when both are given: it decides the
minimum number of classes as well as the dates.
"""

from __future__ import annotations

from datetime import date as Date
from datetime import timedelta

from fastapi import APIRouter, Query
from fastapi.responses import Response
from sqlalchemy import select

from classtrack.api.deps import AdminUser, CurrentUser, SessionDep, scope_report_teacher
from classtrack.core.errors import ValidationError
from classtrack.models import Semester, Term
from classtrack.routine.lattice import SLOTS
from classtrack.schemas.reports import (
    DailyReport,
    Overview,
    ReportSemester,
    StaffReport,
    TeacherReport,
    UnreportedReport,
)
from classtrack.services import (
    accountability_service,
    pdf_service,
    report_service,
    semester_service,
    status_engine,
)

router = APIRouter(prefix="/reports", tags=["reports"])


def _range(start: Date | None, end: Date | None) -> tuple[Date, Date]:
    today = status_engine.now_local().date()
    start = start or today - timedelta(days=30)
    end = end or today
    if end < start:
        raise ValidationError("The end of the range precedes its start.")
    return start, end


async def _period(
    session, start: Date | None, end: Date | None, semester: int | None, term: Term | None
) -> semester_service.Period:
    """A term of a semester when one is asked for, else the two dates."""
    if semester is None and term is None:
        start, end = _range(start, end)
        return semester_service.Period(start=start, end=end)
    return await semester_service.term_period(
        session,
        semester_id=semester,
        term=term or Term.FULL,
        today=status_engine.now_local().date(),
    )


@router.get(
    "/semesters",
    response_model=list[ReportSemester],
    summary="Semesters and their terms, to report on",
)
async def semesters(session: SessionDep, user: CurrentUser) -> list[ReportSemester]:  # noqa: ARG001
    """Newest first. Open to every role: a teacher picks a term for their own report."""
    today = status_engine.now_local().date()
    rows = (await session.scalars(select(Semester).order_by(Semester.start_date.desc()))).all()
    return [
        ReportSemester(
            id=s.id,
            name=s.name,
            is_active=s.is_active,
            start_date=s.start_date,
            end_date=s.end_date,
            terms=semester_service.terms(s, today),
        )
        for s in rows
    ]


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
    semester: int | None = None,
    term: Term | None = None,
) -> TeacherReport:
    return TeacherReport.model_validate(
        await _teacher_report(session, user, initial, start, end, semester, term)
    )


@router.get("/teacher/pdf", summary="Teacher-wise report as a PDF")
async def teacher_pdf(
    session: SessionDep,
    user: CurrentUser,
    initial: str | None = Query(default=None, alias="teacher"),
    start: Date | None = Query(default=None, alias="from"),
    end: Date | None = Query(default=None, alias="to"),
    semester: int | None = None,
    term: Term | None = None,
) -> Response:
    """Every class the teacher had in the range -- held, late, missed, rescheduled."""
    report = await _teacher_report(session, user, initial, start, end, semester, term)
    return _pdf(
        pdf_service.teacher_pdf(report),
        f"classtrack-{report['teacher_initial']}-{report['range']['from']}"
        f"-{report['range']['to']}.pdf",
    )


async def _teacher_report(session, user, initial, start, end, semester, term) -> dict:
    # A TEACHER is forced onto their own initial (403 if they ask for another).
    resolved = scope_report_teacher(user, initial)
    if resolved is None:
        raise ValidationError("A teacher initial is required.")
    period = await _period(session, start, end, semester, term)
    return await report_service.teacher_report(
        session,
        teacher_initial=resolved,
        start=period.start,
        end=period.end,
        term=period.term,
        label=period.label,
    )


def _pdf(content: bytes, filename: str) -> Response:
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _filters(
    teacher: str | None,
    floor: str | None,
    course: str | None,
    section: str | None,
    slot: str | None,
) -> report_service.Filters:
    if slot is not None and slot not in SLOTS:
        raise ValidationError(
            f"{slot!r} is not a routine slot.", detail={"valid_slots": list(SLOTS)}
        )
    return report_service.Filters(
        teacher=teacher.strip().upper() if teacher and teacher.strip() else None,
        floor=floor or None,
        course=course or None,
        section=section or None,
        slot=slot or None,
    )


@router.get(
    "/overview",
    response_model=Overview,
    summary="Monthly, semester or any period, with every breakdown",
)
async def overview(
    session: SessionDep,
    user: AdminUser,  # noqa: ARG001
    start: Date | None = Query(default=None, alias="from"),
    end: Date | None = Query(default=None, alias="to"),
    teacher: str | None = None,
    floor: str | None = None,
    course: str | None = None,
    section: str | None = None,
    slot: str | None = None,
    semester: int | None = None,
    term: Term | None = None,
) -> Overview:
    """The monthly, semester and term reports are this endpoint over that range."""
    period = await _period(session, start, end, semester, term)
    return Overview.model_validate(
        await report_service.overview(
            session,
            start=period.start,
            end=period.end,
            filters=_filters(teacher, floor, course, section, slot),
            term=period.term,
            label=period.label,
        )
    )


@router.get("/overview/pdf", summary="Department summary as a PDF")
async def overview_pdf(
    session: SessionDep,
    user: AdminUser,  # noqa: ARG001
    start: Date | None = Query(default=None, alias="from"),
    end: Date | None = Query(default=None, alias="to"),
    teacher: str | None = None,
    floor: str | None = None,
    course: str | None = None,
    section: str | None = None,
    slot: str | None = None,
    semester: int | None = None,
    term: Term | None = None,
) -> Response:
    period = await _period(session, start, end, semester, term)
    data = await report_service.overview(
        session,
        start=period.start,
        end=period.end,
        filters=_filters(teacher, floor, course, section, slot),
        term=period.term,
        label=period.label,
    )
    return _pdf(
        pdf_service.summary_pdf(data),
        f"classtrack-summary-{period.start}-{period.end}.pdf",
    )


@router.get("/staff", response_model=StaffReport, summary="Monitoring completion")
async def staff(
    session: SessionDep,
    user: AdminUser,  # noqa: ARG001
    start: Date | None = Query(default=None, alias="from"),
    end: Date | None = Query(default=None, alias="to"),
    semester: int | None = None,
    term: Term | None = None,
) -> StaffReport:
    period = await _period(session, start, end, semester, term)
    return StaffReport.model_validate(
        await report_service.staff_report(
            session, start=period.start, end=period.end, label=period.label
        )
    )


@router.get(
    "/unreported",
    response_model=UnreportedReport,
    summary="Classes nobody reported, and who was responsible",
)
async def unreported(
    session: SessionDep,
    user: AdminUser,  # noqa: ARG001
    start: Date | None = Query(default=None, alias="from"),
    end: Date | None = Query(default=None, alias="to"),
) -> UnreportedReport:
    """Accountability view.

    Separates a staff member failing to submit from a floor nobody was assigned
    -- the first needs chasing, the second needs configuring.
    """
    if start is None and end is None:
        end = status_engine.now_local().date()
        start = end - timedelta(days=7)
    else:
        start, end = _range(start, end)
    return UnreportedReport.model_validate(
        await accountability_service.unreported(session, start=start, end=end)
    )

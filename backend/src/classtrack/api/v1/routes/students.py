"""Students: their routine, what is written to them, free rooms, the calendar.

The ``/students`` reads are public. Students have no accounts: they name their
groups, and see only what the timetable on the wall would say
(``services/student_service.py``). Writing to them needs an account: a teacher
writes to their own sections, an admin to anyone.
"""

from __future__ import annotations

from datetime import date as Date
from datetime import timedelta

from fastapi import APIRouter, Query, Response

from classtrack.api.deps import NotifierUser, SessionDep, StudentMessengerUser
from classtrack.core.errors import ValidationError
from classtrack.models import NoticeKind
from classtrack.schemas.student import (
    AdminNoticeIn,
    CalendarOut,
    DirectoryOut,
    FreeSlotOut,
    StudentClassOut,
    StudentNoticeOut,
    TeacherGroupOut,
    TeacherNoticeIn,
    TopicsOut,
)
from classtrack.services import settings_service, status_engine, student_service

router = APIRouter(tags=["students"])

#: What changes once a semester: a browser may keep it a few minutes.
_SLOW = "public, max-age=300"

Groups = Query(
    description="Comma-separated groups: 63_A, 63_A1, CSE447:RE_A. A lab group brings its section.",
    min_length=1,
    max_length=400,
)


@router.get(
    "/students/directory", response_model=DirectoryOut, summary="Every section, to pick from"
)
async def directory(session: SessionDep, response: Response) -> DirectoryOut:
    response.headers["Cache-Control"] = _SLOW
    return DirectoryOut.model_validate(await student_service.directory(session))


@router.get("/students/topics", response_model=TopicsOut, summary="Push topics to follow")
async def topics(session: SessionDep, groups: str = Groups) -> TopicsOut:
    chosen = student_service.parse_groups(groups)
    dept = await student_service.department(session)
    return TopicsOut(
        **student_service.topics_for(dept, chosen),
        reminder_minutes=await settings_service.class_reminder_minutes(session),
    )


@router.get(
    "/students/classes", response_model=list[StudentClassOut], summary="A student's classes"
)
async def classes(
    session: SessionDep,
    groups: str = Groups,
    date_from: Date | None = Query(default=None, alias="from"),
    date_to: Date | None = Query(default=None, alias="to"),
) -> list[StudentClassOut]:
    """Both dates inclusive; from today for a week when left out."""
    start = date_from or status_engine.now_local().date()
    end = date_to or start + timedelta(days=6)
    rows = await student_service.classes(
        session, student_service.parse_groups(groups), date_from=start, date_to=end
    )
    return [StudentClassOut.model_validate(r) for r in rows]


@router.get(
    "/students/notices", response_model=list[StudentNoticeOut], summary="Written to a student"
)
async def notices(
    session: SessionDep, groups: str = Groups, limit: int = Query(default=50, ge=1, le=100)
) -> list[StudentNoticeOut]:
    rows = await student_service.notices(session, student_service.parse_groups(groups), limit=limit)
    return [
        StudentNoticeOut.model_validate(n)
        for n in await student_service.describe_notices(session, rows)
    ]


@router.get("/students/calendar", response_model=CalendarOut | None, summary="The semester's days")
async def calendar(session: SessionDep, response: Response) -> CalendarOut | None:
    response.headers["Cache-Control"] = _SLOW
    found = await student_service.calendar(session)
    return CalendarOut.model_validate(found) if found else None


@router.get(
    "/students/free-rooms", response_model=list[FreeSlotOut], summary="Empty rooms, by slot"
)
async def free_rooms(
    session: SessionDep, on: Date | None = Query(default=None, alias="date")
) -> list[FreeSlotOut]:
    """For today or a coming day. A day with no classes has no slots."""
    today = status_engine.now_local().date()
    day = on or today
    if not today <= day <= today + timedelta(days=14):
        raise ValidationError("Pick today or a day in the next two weeks.")
    return [
        FreeSlotOut.model_validate(s) for s in await student_service.free_rooms(session, on=day)
    ]


# --- a teacher writes to their students ----------------------------------------------


@router.get("/teacher/notices/groups", response_model=list[TeacherGroupOut], summary="My sections")
async def my_groups(session: SessionDep, user: StudentMessengerUser) -> list[TeacherGroupOut]:
    rows = await student_service.teacher_groups(session, user.teacher_initial or "")
    return [TeacherGroupOut(**g) for g in rows]


@router.get(
    "/teacher/notices", response_model=list[StudentNoticeOut], summary="What I wrote to students"
)
async def my_notices(session: SessionDep, user: StudentMessengerUser) -> list[StudentNoticeOut]:
    rows = await student_service.written_by(
        session, kind=NoticeKind.TEACHER, author_id=user.id, limit=30
    )
    return [
        StudentNoticeOut.model_validate(n)
        for n in await student_service.describe_notices(session, rows)
    ]


@router.post("/teacher/notices", response_model=StudentNoticeOut, summary="Write to my students")
async def write_to_students(
    payload: TeacherNoticeIn, session: SessionDep, user: StudentMessengerUser
) -> StudentNoticeOut:
    notice = await student_service.write_as_teacher(
        session,
        user=user,
        body=payload.body,
        targets=payload.targets,
        instance_id=payload.instance_id,
    )
    await session.commit()
    [out] = await student_service.describe_notices(session, [notice])
    return StudentNoticeOut.model_validate(out)


# --- the department writes to students ----------------------------------------------


@router.get(
    "/admin/notifications/students",
    response_model=list[StudentNoticeOut],
    summary="Notices sent to students",
)
async def sent_to_students(session: SessionDep, user: NotifierUser) -> list[StudentNoticeOut]:  # noqa: ARG001
    rows = await student_service.written_by(session, kind=NoticeKind.ANNOUNCEMENT)
    return [
        StudentNoticeOut.model_validate(n)
        for n in await student_service.describe_notices(session, rows)
    ]


@router.post(
    "/admin/notifications/students", response_model=StudentNoticeOut, summary="Write to students"
)
async def write_as_department(
    payload: AdminNoticeIn, session: SessionDep, user: NotifierUser
) -> StudentNoticeOut:
    notice = await student_service.write_as_admin(
        session, user=user, title=payload.title, body=payload.body, targets=payload.targets
    )
    await session.commit()
    [out] = await student_service.describe_notices(session, [notice])
    return StudentNoticeOut.model_validate(out)

"""Administration: routine import, calendar, users, settings, audit trail."""

from __future__ import annotations

import tempfile
from collections import Counter
from pathlib import Path

from fastapi import APIRouter, File, Form, Query, UploadFile
from sqlalchemy import delete, select, update

from classtrack.api.deps import AdminUser, SessionDep, SuperAdminUser
from classtrack.core.errors import NotFoundError, ValidationError
from classtrack.core.security import hash_password
from classtrack.models import (
    AuditLog,
    ClassSession,
    Holiday,
    Routine,
    Semester,
    Teacher,
    User,
)
from classtrack.models.user import Role
from classtrack.schemas.admin import (
    ActivateRequest,
    AuditOut,
    HolidayIn,
    HolidayOut,
    RoutineOut,
    RoutineReview,
    SemesterIn,
    SemesterOut,
    SessionRow,
    SettingsIn,
    StaffOut,
    UserIn,
    UserOut,
    ZoneAssignRequest,
    ZoneOut,
)
from classtrack.schemas.common import Message
from classtrack.services import (
    assignment_service,
    audit_service,
    instance_service,
    settings_service,
)

router = APIRouter(prefix="/admin", tags=["admin"])


# --- routine ---------------------------------------------------------------


@router.post("/routine/ingest", summary="Ingest a routine PDF")
async def ingest(
    session: SessionDep,
    user: AdminUser,
    file: UploadFile = File(...),
    department: str = Form("cse"),
    semester: str | None = Form(None),
    version: str | None = Form(None),
) -> dict:
    """Parse a routine PDF into sessions. Does **not** activate it.

    Review the report first -- that review step is what AC-01 requires, and it
    is the only thing standing between a misparsed document and a semester of
    wrong monitoring records.
    """
    from classtrack.routine.pipeline import ingest_pdf

    suffix = Path(file.filename or "routine.pdf").suffix or ".pdf"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        temp_path = Path(tmp.name)

    try:
        report = await ingest_pdf(
            session,
            temp_path,
            department=department,
            version=version,
            semester=semester,
            activate=False,
        )
    finally:
        temp_path.unlink(missing_ok=True)

    audit_service.record(
        session,
        actor_id=user.id,
        entity_type="routine",
        entity_id=report.routine_id or 0,
        action="routine_ingested",
        after={"version": report.version, "sessions": report.sessions_created},
    )
    await session.commit()
    return report.as_dict()


def _scan_conflicts(sessions: list[ClassSession]) -> list[dict]:
    """Find problems a human must resolve before the routine goes live (SRS 4.2).

    On the lattice these are all duplicate-key checks: two classes in one cell.
    """
    conflicts: list[dict] = []

    rooms = Counter((s.day, s.time_slot, s.room) for s in sessions)
    for (day, slot, room), count in rooms.items():
        if count > 1:
            conflicts.append(
                {
                    "type": "ROOM",
                    "message": f"{room} holds {count} classes on {day} at {slot}.",
                    "day": day,
                    "time_slot": slot,
                }
            )

    teachers = Counter(
        (s.day, s.time_slot, s.teacher) for s in sessions if s.teacher not in ("", "TBA")
    )
    for (day, slot, teacher), count in teachers.items():
        if count > 1:
            conflicts.append(
                {
                    "type": "TEACHER",
                    "message": f"{teacher} has {count} classes on {day} at {slot}.",
                    "day": day,
                    "time_slot": slot,
                }
            )

    sections = Counter((s.day, s.time_slot, s.section) for s in sessions)
    for (day, slot, section), count in sections.items():
        if count > 1:
            conflicts.append(
                {
                    "type": "SECTION",
                    "message": f"Section {section} has {count} classes on {day} at {slot}.",
                    "day": day,
                    "time_slot": slot,
                }
            )

    for sess in sessions:
        if not sess.teacher or sess.teacher == "TBA":
            conflicts.append(
                {
                    "type": "MISSING_TEACHER",
                    "message": f"{sess.course_code} in {sess.room} ({sess.day} {sess.time_slot})"
                    " has no teacher assigned.",
                    "day": sess.day,
                    "time_slot": sess.time_slot,
                }
            )
        if not sess.room:
            conflicts.append(
                {
                    "type": "MISSING_ROOM",
                    "message": f"{sess.course_code} ({sess.day} {sess.time_slot}) has no room.",
                    "day": sess.day,
                    "time_slot": sess.time_slot,
                }
            )

    return conflicts


@router.get(
    "/routine/{routine_id}/review",
    response_model=RoutineReview,
    summary="Parsed sessions and detected conflicts",
)
async def review(
    routine_id: int,
    session: SessionDep,
    user: AdminUser,  # noqa: ARG001
    limit: int = Query(default=500, le=5000),
) -> RoutineReview:
    routine = await session.get(Routine, routine_id)
    if routine is None:
        raise NotFoundError(f"No routine with id {routine_id}")

    sessions = list(
        (
            await session.scalars(
                select(ClassSession).where(ClassSession.routine_id == routine_id)
            )
        ).all()
    )
    rows = [
        SessionRow(
            day=s.day,
            time_slot=s.time_slot,
            room=s.room,
            course_code=s.course_code,
            section=s.section,
            teacher=s.teacher,
            is_lab=s.is_lab,
        )
        for s in sorted(sessions, key=lambda s: (s.day, s.start_min, s.room))[:limit]
    ]
    return RoutineReview(
        routine=RoutineOut.model_validate(routine),
        conflicts=_scan_conflicts(sessions),
        sessions=rows,
        total_sessions=len(sessions),
    )


@router.get("/routines", response_model=list[RoutineOut], summary="Routine revisions")
async def list_routines(session: SessionDep, user: AdminUser) -> list[RoutineOut]:  # noqa: ARG001
    rows = (await session.scalars(select(Routine).order_by(Routine.id.desc()))).all()
    return [RoutineOut.model_validate(r) for r in rows]


@router.post("/routine/{routine_id}/activate", summary="Activate and generate instances")
async def activate(
    routine_id: int, payload: ActivateRequest, session: SessionDep, user: AdminUser
) -> dict:
    """Make this revision live and materialise its monitoring instances (BR-01)."""
    routine = await session.get(Routine, routine_id)
    if routine is None:
        raise NotFoundError(f"No routine with id {routine_id}")

    if payload.semester_id is not None:
        semester = await session.get(Semester, payload.semester_id)
        if semester is None:
            raise NotFoundError(f"No semester with id {payload.semester_id}")
    else:
        semester = await session.scalar(select(Semester).where(Semester.is_active))
        if semester is None:
            raise ValidationError("No active semester. Create one first.")

    await session.execute(
        update(Routine)
        .where(Routine.department == routine.department, Routine.id != routine.id)
        .values(is_active=False)
    )
    routine.is_active = True
    semester.routine_id = routine.id
    await session.flush()

    result = await instance_service.generate(session, semester_id=semester.id)

    audit_service.record(
        session,
        actor_id=user.id,
        entity_type="routine",
        entity_id=routine.id,
        action="routine_activated",
        after={"semester_id": semester.id, **result},
    )
    await session.commit()
    return {"routine_id": routine.id, "is_active": True, **result}


@router.post("/instances/generate", summary="Re-run instance generation")
async def generate(
    session: SessionDep,
    user: SuperAdminUser,  # noqa: ARG001
    semester_id: int | None = None,
) -> dict:
    """Idempotent -- existing instances keep their status and check records."""
    result = await instance_service.generate(session, semester_id=semester_id)
    await session.commit()
    return result


# --- semesters and calendar ------------------------------------------------


@router.get("/semesters", response_model=list[SemesterOut], summary="Semesters")
async def list_semesters(session: SessionDep, user: AdminUser) -> list[SemesterOut]:  # noqa: ARG001
    rows = (await session.scalars(select(Semester).order_by(Semester.id.desc()))).all()
    return [SemesterOut.model_validate(s) for s in rows]


@router.post("/semesters", response_model=SemesterOut, summary="Create a semester")
async def create_semester(
    payload: SemesterIn,
    session: SessionDep,
    user: SuperAdminUser,  # noqa: ARG001
) -> SemesterOut:
    if payload.end_date < payload.start_date:
        raise ValidationError("The semester ends before it starts.")
    await session.execute(
        update(Semester).where(Semester.department == payload.department).values(is_active=False)
    )
    semester = Semester(**payload.model_dump(), is_active=True)
    session.add(semester)
    await session.commit()
    return SemesterOut.model_validate(semester)


@router.get("/holidays", response_model=list[HolidayOut], summary="Academic calendar")
async def list_holidays(session: SessionDep, user: AdminUser) -> list[HolidayOut]:  # noqa: ARG001
    rows = (await session.scalars(select(Holiday).order_by(Holiday.date))).all()
    return [HolidayOut.model_validate(h) for h in rows]


@router.post("/holidays", response_model=HolidayOut, summary="Add a calendar day")
async def add_holiday(payload: HolidayIn, session: SessionDep, user: AdminUser) -> HolidayOut:
    semester_id = payload.semester_id
    if semester_id is None:
        semester = await session.scalar(select(Semester).where(Semester.is_active))
        if semester is None:
            raise ValidationError("No active semester. Create one first.")
        semester_id = semester.id

    existing = await session.scalar(
        select(Holiday).where(Holiday.semester_id == semester_id, Holiday.date == payload.date)
    )
    if existing is not None:
        raise ValidationError(f"{payload.date} is already in the calendar.")

    holiday = Holiday(
        semester_id=semester_id,
        date=payload.date,
        title=payload.title,
        kind=payload.kind,
    )
    session.add(holiday)
    audit_service.record(
        session,
        actor_id=user.id,
        entity_type="holiday",
        entity_id=0,
        action="holiday_added",
        after={"date": payload.date.isoformat(), "title": payload.title},
    )
    await session.commit()
    return HolidayOut.model_validate(holiday)


@router.delete("/holidays/{holiday_id}", response_model=Message, summary="Remove a day")
async def remove_holiday(holiday_id: int, session: SessionDep, user: AdminUser) -> Message:
    holiday = await session.get(Holiday, holiday_id)
    if holiday is None:
        raise NotFoundError(f"No calendar entry with id {holiday_id}")
    audit_service.record(
        session,
        actor_id=user.id,
        entity_type="holiday",
        entity_id=holiday_id,
        action="holiday_removed",
        before={"date": holiday.date.isoformat(), "title": holiday.title},
    )
    await session.execute(delete(Holiday).where(Holiday.id == holiday_id))
    await session.commit()
    return Message(detail="Removed. Re-run instance generation to apply it.")


# --- users -----------------------------------------------------------------


@router.get("/users", response_model=list[UserOut], summary="Users")
async def list_users(session: SessionDep, user: SuperAdminUser) -> list[UserOut]:  # noqa: ARG001
    rows = (await session.scalars(select(User).order_by(User.id))).all()
    return [UserOut.model_validate(u) for u in rows]


@router.post("/users", response_model=UserOut, summary="Create a user")
async def create_user(
    payload: UserIn,
    session: SessionDep,
    user: SuperAdminUser,  # noqa: ARG001
) -> UserOut:
    email = payload.email.strip().lower()
    if await session.scalar(select(User).where(User.email == email)):
        raise ValidationError(f"{email} already has an account.")

    # A TEACHER without an initial cannot be matched to any routine row, so the
    # account would show an empty schedule. Refuse it rather than create it.
    if payload.role is Role.TEACHER:
        if not payload.teacher_initial:
            raise ValidationError("A teacher account needs a teacher initial.")
        initial = payload.teacher_initial.upper()
        if not await session.get(Teacher, initial) and not await session.scalar(
            select(Teacher).where(Teacher.initial == initial)
        ):
            raise ValidationError(f"No faculty member with initial {initial!r}.")

    created = User(
        email=email,
        full_name=payload.full_name,
        role=payload.role,
        password_hash=hash_password(payload.password),
        teacher_initial=payload.teacher_initial.upper() if payload.teacher_initial else None,
    )
    session.add(created)
    await session.commit()
    return UserOut.model_validate(created)


# --- staff coverage --------------------------------------------------------


@router.get("/zones", response_model=list[ZoneOut], summary="Buildings and floors")
async def zones(session: SessionDep, user: AdminUser) -> list[ZoneOut]:  # noqa: ARG001
    """The zones the active routine uses, derived from its room names."""
    return [ZoneOut.model_validate(z) for z in await assignment_service.available_zones(session)]


@router.get("/staff", response_model=list[StaffOut], summary="Office staff and their floors")
async def staff(session: SessionDep, user: AdminUser) -> list[StaffOut]:  # noqa: ARG001
    rows = (
        await session.scalars(
            select(User).where(User.role == Role.STAFF).order_by(User.full_name)
        )
    ).all()
    assignments = await assignment_service.assignments_by_user(session)
    out = []
    for member in rows:
        item = StaffOut.model_validate(member)
        item.zones = assignments.get(member.id, [])
        out.append(item)
    return out


@router.put(
    "/staff/{user_id}/zones",
    response_model=StaffOut,
    summary="Assign a staff member to floors",
)
async def assign_zones(
    user_id: int,
    payload: ZoneAssignRequest,
    session: SessionDep,
    user: AdminUser,
) -> StaffOut:
    """Replace this staff member's coverage.

    An empty list removes the restriction, so they see every room again.
    """
    keys = await assignment_service.set_zones(
        session, user_id=user_id, zone_keys=payload.zones, actor=user
    )
    await session.commit()
    member = await session.get(User, user_id)
    item = StaffOut.model_validate(member)
    item.zones = keys
    return item


# --- settings and audit ----------------------------------------------------


@router.get("/settings", summary="Monitoring rules")
async def get_settings_values(session: SessionDep, user: AdminUser) -> dict[str, str]:  # noqa: ARG001
    return await settings_service.get_all(session)


@router.put("/settings", summary="Change monitoring rules")
async def put_settings(
    payload: SettingsIn, session: SessionDep, user: AdminUser
) -> dict[str, str]:
    changes = payload.model_dump(exclude_none=True)
    if not changes:
        raise ValidationError("No settings supplied.")
    for key, value in changes.items():
        await settings_service.set_value(session, key, str(value), updated_by_id=user.id)
    audit_service.record(
        session,
        actor_id=user.id,
        entity_type="setting",
        entity_id=0,
        action="settings_changed",
        after=changes,
    )
    await session.commit()
    return await settings_service.get_all(session)


@router.get("/audit", response_model=list[AuditOut], summary="Audit trail")
async def audit(
    session: SessionDep,
    user: AdminUser,  # noqa: ARG001
    entity_type: str | None = None,
    entity_id: int | None = None,
    actor: int | None = None,
    limit: int = Query(default=100, le=1000),
) -> list[AuditOut]:
    query = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if entity_type is not None:
        query = query.where(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        query = query.where(AuditLog.entity_id == entity_id)
    if actor is not None:
        query = query.where(AuditLog.actor_id == actor)

    rows = list((await session.scalars(query)).all())
    actor_ids = {r.actor_id for r in rows if r.actor_id}
    names: dict[int, str] = {}
    if actor_ids:
        names = {
            u.id: u.full_name
            for u in (await session.scalars(select(User).where(User.id.in_(actor_ids)))).all()
        }
    out = []
    for row in rows:
        item = AuditOut.model_validate(row)
        # None means the system acted -- say so rather than showing a blank.
        item.actor_name = names.get(row.actor_id) if row.actor_id else "System"
        out.append(item)
    return out


@router.get("/teachers", summary="Faculty directory")
async def teachers(
    session: SessionDep,
    user: AdminUser,  # noqa: ARG001
    q: str | None = None,
) -> list[dict]:
    query = select(Teacher).order_by(Teacher.initial).limit(500)
    if q:
        like = f"%{q.strip()}%"
        query = query.where(Teacher.name.ilike(like) | Teacher.initial.ilike(like))
    return [
        {"initial": t.initial, "name": t.name, "designation": t.designation}
        for t in (await session.scalars(query)).all()
    ]

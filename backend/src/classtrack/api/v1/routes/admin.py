"""Administration: routine import, calendar, users, settings, audit trail."""

from __future__ import annotations

import tempfile
from collections import Counter
from pathlib import Path

from fastapi import APIRouter, File, Form, Query, UploadFile
from sqlalchemy import delete, select, update

from classtrack.api.deps import (
    AccountsUser,
    AuditUser,
    CalendarUser,
    RoleAdminUser,
    RoleReaderUser,
    RoutineUser,
    RulesUser,
    SemesterReaderUser,
    SemesterUser,
    SessionDep,
    StaffAdminUser,
    TeacherAdminUser,
    TeacherReaderUser,
    ZoneReaderUser,
)
from classtrack.core.errors import NotFoundError, ValidationError
from classtrack.core.security import hash_password
from classtrack.models import (
    PERMISSION_INFO,
    AuditLog,
    ClassSession,
    Holiday,
    RoleKind,
    Routine,
    Semester,
    Teacher,
    User,
)
from classtrack.schemas.admin import (
    ActivateRequest,
    AuditOut,
    HolidayIn,
    HolidayOut,
    PermissionOut,
    RoleIn,
    RoleOut,
    RoleRef,
    RoleUpdate,
    RoutineOut,
    RoutineReview,
    SemesterIn,
    SemesterOut,
    SemesterSaved,
    SemesterUpdate,
    SessionRow,
    SettingsIn,
    StaffCreateRequest,
    StaffOut,
    TeacherAccountRequest,
    TeacherAccountsCreated,
    TeacherOut,
    UserIn,
    UserOut,
    UserUpdate,
    ZoneAssignRequest,
    ZoneOut,
)
from classtrack.schemas.common import Message
from classtrack.services import (
    account_service,
    assignment_service,
    audit_service,
    instance_service,
    role_service,
    semester_service,
    settings_service,
)

router = APIRouter(prefix="/admin", tags=["admin"])


# --- routine ---------------------------------------------------------------


@router.post("/routine/ingest", summary="Ingest a routine PDF")
async def ingest(
    session: SessionDep,
    user: RoutineUser,
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
    user: RoutineUser,  # noqa: ARG001
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
async def list_routines(session: SessionDep, user: RoutineUser) -> list[RoutineOut]:  # noqa: ARG001
    rows = (await session.scalars(select(Routine).order_by(Routine.id.desc()))).all()
    return [RoutineOut.model_validate(r) for r in rows]


@router.post("/routine/{routine_id}/activate", summary="Activate and generate instances")
async def activate(
    routine_id: int, payload: ActivateRequest, session: SessionDep, user: RoutineUser
) -> dict:
    """Attach this revision to a semester and materialise its classes (BR-01).

    For the current semester it also goes live at once. A routine set up for a
    semester ahead of time goes live when that semester is made current.
    """
    routine = await session.get(Routine, routine_id)
    if routine is None:
        raise NotFoundError(f"No routine with id {routine_id}")

    if payload.semester_id is not None:
        semester = await semester_service.get(session, payload.semester_id)
    else:
        semester = await semester_service.current(session)
        if semester is None:
            raise ValidationError("No active semester. Create one first.")

    semester.routine_id = routine.id
    if semester.is_active:
        await session.execute(
            update(Routine)
            .where(Routine.department == routine.department)
            .values(is_active=Routine.id == routine.id)
        )
    await session.flush()
    await session.refresh(routine)

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
    return {"routine_id": routine.id, "is_active": routine.is_active, **result}


@router.post("/instances/generate", summary="Re-run instance generation")
async def generate(
    session: SessionDep,
    user: SemesterUser,  # noqa: ARG001
    semester_id: int | None = None,
) -> dict:
    """Idempotent -- existing instances keep their status and check records."""
    result = await instance_service.generate(session, semester_id=semester_id)
    await session.commit()
    return result


# --- semesters and calendar ------------------------------------------------


def _semester_dates(semester: Semester) -> dict[str, str | None]:
    """A semester's dates, for the audit trail."""
    return {
        key: value.isoformat() if value else None
        for key, value in (
            ("start_date", semester.start_date),
            ("end_date", semester.end_date),
            ("mid_exam_start", semester.mid_exam_start),
            ("mid_exam_end", semester.mid_exam_end),
            ("final_exam_start", semester.final_exam_start),
        )
    }


async def _regenerate(session, semester: Semester) -> dict | None:
    """Apply a change of dates or days off to the semester's classes at once.

    Generation adds classes to days that now hold them and retires unchecked
    future ones from days that no longer do. A semester with no routine yet
    has no classes to change.
    """
    if semester.routine_id is None:
        return None
    return await instance_service.generate(session, semester_id=semester.id)


@router.get("/semesters", response_model=list[SemesterOut], summary="Semesters")
async def list_semesters(session: SessionDep, user: SemesterReaderUser) -> list[SemesterOut]:  # noqa: ARG001
    rows = (await session.scalars(select(Semester).order_by(Semester.start_date.desc()))).all()
    return [SemesterOut.model_validate(s) for s in rows]


@router.post("/semesters", response_model=SemesterOut, summary="Create a semester")
async def create_semester(
    payload: SemesterIn,
    session: SessionDep,
    user: SemesterUser,
) -> SemesterOut:
    """Set up a semester. It becomes current if asked, or if none is current yet."""
    semester = Semester(**payload.model_dump(exclude={"make_current"}), is_active=False)
    await semester_service.validate(session, semester)
    session.add(semester)
    await session.flush()

    if payload.make_current or await semester_service.current(session) is None:
        await semester_service.make_current(session, semester)
    audit_service.record(
        session,
        actor_id=user.id,
        entity_type="semester",
        entity_id=semester.id,
        action="semester_created",
        after={"name": semester.name, **_semester_dates(semester)},
    )
    await session.commit()
    return SemesterOut.model_validate(semester)


@router.put("/semesters/{semester_id}", response_model=SemesterSaved, summary="Change a semester")
async def update_semester(
    semester_id: int, payload: SemesterUpdate, session: SessionDep, user: SemesterUser
) -> SemesterSaved:
    """Rename it, or move its dates and exam periods.

    Its classes follow at once: exam days lose theirs, and days that hold
    classes again get them back.
    """
    semester = await semester_service.get(session, semester_id)
    before = {"name": semester.name, **_semester_dates(semester)}
    for key, value in payload.model_dump().items():
        setattr(semester, key, value)
    await semester_service.validate(session, semester)

    generation = await _regenerate(session, semester)
    audit_service.record(
        session,
        actor_id=user.id,
        entity_type="semester",
        entity_id=semester.id,
        action="semester_updated",
        before=before,
        after={"name": semester.name, **_semester_dates(semester)},
    )
    await session.commit()
    return SemesterSaved(semester=SemesterOut.model_validate(semester), generation=generation)


@router.post(
    "/semesters/{semester_id}/activate",
    response_model=SemesterOut,
    summary="Make a semester the current one",
)
async def activate_semester(
    semester_id: int, session: SessionDep, user: SemesterUser
) -> SemesterOut:
    """Move the department on to this semester, and to its routine if it has one."""
    semester = await semester_service.get(session, semester_id)
    previous = await semester_service.current(session)
    await semester_service.make_current(session, semester)
    audit_service.record(
        session,
        actor_id=user.id,
        entity_type="semester",
        entity_id=semester.id,
        action="semester_activated",
        before={"current": previous.name if previous else None},
        after={"current": semester.name},
    )
    await session.commit()
    return SemesterOut.model_validate(semester)


@router.get("/holidays", response_model=list[HolidayOut], summary="Academic calendar")
async def list_holidays(
    session: SessionDep,
    user: CalendarUser,  # noqa: ARG001
    semester_id: int | None = None,
) -> list[HolidayOut]:
    query = select(Holiday).order_by(Holiday.date)
    if semester_id is not None:
        query = query.where(Holiday.semester_id == semester_id)
    rows = (await session.scalars(query)).all()
    return [HolidayOut.model_validate(h) for h in rows]


@router.post("/holidays", response_model=HolidayOut, summary="Add a calendar day")
async def add_holiday(payload: HolidayIn, session: SessionDep, user: CalendarUser) -> HolidayOut:
    """Add a day to a semester's calendar. A day off loses its classes at once."""
    if payload.semester_id is not None:
        semester = await semester_service.get(session, payload.semester_id)
    else:
        semester = await semester_service.current(session)
        if semester is None:
            raise ValidationError("No active semester. Create one first.")
    if not semester.start_date <= payload.date <= semester.end_date:
        raise ValidationError(
            f"{payload.date} is outside {semester.name} "
            f"({semester.start_date} to {semester.end_date})."
        )

    existing = await session.scalar(
        select(Holiday).where(Holiday.semester_id == semester.id, Holiday.date == payload.date)
    )
    if existing is not None:
        raise ValidationError(f"{payload.date} is already in the calendar.")

    holiday = Holiday(
        semester_id=semester.id,
        date=payload.date,
        title=payload.title,
        kind=payload.kind,
    )
    session.add(holiday)
    await session.flush()
    await _regenerate(session, semester)
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
async def remove_holiday(holiday_id: int, session: SessionDep, user: CalendarUser) -> Message:
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
    semester = await semester_service.get(session, holiday.semester_id)
    await session.execute(delete(Holiday).where(Holiday.id == holiday_id))
    generation = await _regenerate(session, semester)
    await session.commit()
    if generation is None:
        return Message(detail="Removed.")
    return Message(detail="Removed. That day's classes are back on the schedule.")


# --- users -----------------------------------------------------------------


def _user_out(user: User) -> UserOut:
    out = UserOut.model_validate(user)
    out.roles = [RoleRef.model_validate(r) for r in user.ordered_roles]
    return out


@router.get("/users", response_model=list[UserOut], summary="Users")
async def list_users(session: SessionDep, user: AccountsUser) -> list[UserOut]:  # noqa: ARG001
    rows = (await session.scalars(select(User).order_by(User.id))).all()
    return [_user_out(u) for u in rows]


@router.post("/users", response_model=UserOut, summary="Create a user")
async def create_user(payload: UserIn, session: SessionDep, user: AccountsUser) -> UserOut:
    """An office account. Teachers get theirs from the Teachers tab, which binds
    the initial; a staff role here makes the account floor staff."""
    email = payload.email.strip().lower()
    if await session.scalar(select(User).where(User.email == email)):
        raise ValidationError(f"{email} already has an account.")

    roles = await role_service.resolve(session, payload.role_ids)
    created = User(
        email=email,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
    )
    role_service.check_kinds(created, roles)
    for role in roles:
        role_service.require_held(user, role, f"give {role.name}")
    created.roles = roles
    session.add(created)
    await session.flush()
    audit_service.record(
        session,
        actor_id=user.id,
        entity_type="user",
        entity_id=created.id,
        action="user_created",
        after={"email": email, "roles": sorted(r.name for r in roles)},
    )
    await session.commit()
    return _user_out(created)


@router.patch("/users/{user_id}", response_model=UserOut, summary="Change a user")
async def update_user(
    user_id: int,
    payload: UserUpdate,
    session: SessionDep,
    user: AccountsUser,
) -> UserOut:
    """Rename, change the roles of, deactivate or reset the password of an account."""
    target = await session.get(User, user_id)
    if target is None:
        raise NotFoundError(f"No user with id {user_id}")

    changes = payload.model_dump(exclude_none=True)
    if not changes:
        raise ValidationError("Nothing to change.")
    # Locking yourself out is never what was meant.
    if target.id == user.id and payload.is_active is False:
        raise ValidationError("You cannot deactivate your own account.")

    before = {"is_active": target.is_active}
    if payload.full_name is not None:
        target.full_name = payload.full_name.strip()
    if payload.role_ids is not None:
        roles = await role_service.resolve(session, payload.role_ids)
        await role_service.set_roles(session, actor=user, target=target, roles=roles)
    if payload.is_active is False and target.is_active:
        await role_service.guard_deactivation(session, target)
    if payload.is_active is not None:
        target.is_active = payload.is_active
    if payload.password is not None:
        target.password_hash = hash_password(payload.password)

    audit_service.record(
        session,
        actor_id=user.id,
        entity_type="user",
        entity_id=target.id,
        action="user_updated",
        before=before,
        # Never the password itself: only that it changed.
        after={
            "is_active": target.is_active,
            "password_changed": payload.password is not None,
        },
    )
    await session.commit()
    return _user_out(target)


# --- roles -----------------------------------------------------------------


@router.get(
    "/permissions", response_model=list[PermissionOut], summary="Every permission there is"
)
async def permissions(user: RoleReaderUser) -> list[PermissionOut]:  # noqa: ARG001
    return [
        PermissionOut(
            key=i.permission.value, group=i.group, label=i.label, description=i.description
        )
        for i in PERMISSION_INFO
    ]


async def _role_out(session, role, held: dict[int, int] | None = None) -> RoleOut:
    held = held if held is not None else await role_service.holders(session)
    return RoleOut(
        id=role.id,
        key=role.key,
        name=role.name,
        description=role.description,
        kind=role.kind,
        is_builtin=role.is_builtin,
        is_locked=role.is_locked,
        permissions=sorted(p.value for p in role.granted),
        holders=held.get(role.id, 0),
    )


@router.get("/roles", response_model=list[RoleOut], summary="Roles and what each permits")
async def roles(session: SessionDep, user: RoleReaderUser) -> list[RoleOut]:  # noqa: ARG001
    held = await role_service.holders(session)
    return [await _role_out(session, r, held) for r in await role_service.all_roles(session)]


@router.post("/roles", response_model=RoleOut, summary="Create a role")
async def create_role(payload: RoleIn, session: SessionDep, user: RoleAdminUser) -> RoleOut:
    role = await role_service.create_role(
        session,
        actor=user,
        name=payload.name,
        description=payload.description,
        kind=payload.kind,
        permissions=payload.permissions,
    )
    await session.commit()
    return await _role_out(session, role)


@router.put("/roles/{role_id}", response_model=RoleOut, summary="Change a role")
async def update_role(
    role_id: int, payload: RoleUpdate, session: SessionDep, user: RoleAdminUser
) -> RoleOut:
    """Its name, description or permissions. Its kind is fixed once made."""
    role = await role_service.update_role(
        session,
        actor=user,
        role_id=role_id,
        name=payload.name,
        description=payload.description,
        permissions=payload.permissions,
    )
    await session.commit()
    return await _role_out(session, role)


@router.delete("/roles/{role_id}", response_model=Message, summary="Delete a role")
async def delete_role(role_id: int, session: SessionDep, user: RoleAdminUser) -> Message:
    """Only a role you made, and only once nobody holds it."""
    await role_service.delete_role(session, actor=user, role_id=role_id)
    await session.commit()
    return Message(detail="Role deleted.")


# --- staff coverage --------------------------------------------------------


@router.get("/zones", response_model=list[ZoneOut], summary="Buildings and floors")
async def zones(session: SessionDep, user: ZoneReaderUser) -> list[ZoneOut]:  # noqa: ARG001
    """The zones the active routine uses, derived from its room names."""
    return [ZoneOut.model_validate(z) for z in await assignment_service.available_zones(session)]


@router.get("/staff", response_model=list[StaffOut], summary="Office staff and their floors")
async def staff(session: SessionDep, user: StaffAdminUser) -> list[StaffOut]:  # noqa: ARG001
    rows = (
        await session.scalars(
            select(User)
            .where(User.of_kind(RoleKind.STAFF))
            .order_by(User.full_name)
        )
    ).all()
    assignments = await assignment_service.assignments_by_user(session)
    out = []
    for member in rows:
        item = StaffOut.model_validate(member)
        item.zones = assignments.get(member.id, [])
        out.append(item)
    return out


@router.post(
    "/staff",
    response_model=StaffOut,
    summary="Create an office staff account with its floors",
)
async def create_staff(
    payload: StaffCreateRequest,
    session: SessionDep,
    user: StaffAdminUser,
) -> StaffOut:
    """One step: the account and the floors it covers.

    Those floors are the person's workload -- every class on them becomes theirs
    to check and report.
    """
    member = await assignment_service.create_staff(
        session,
        full_name=payload.full_name,
        email=payload.email,
        password=payload.password,
        zone_keys=payload.zones,
        actor=user,
    )
    await session.commit()
    item = StaffOut.model_validate(member)
    item.zones = await assignment_service.zones_for_user(session, member.id)
    return item


@router.put(
    "/staff/{user_id}/zones",
    response_model=StaffOut,
    summary="Assign a staff member to floors",
)
async def assign_zones(
    user_id: int,
    payload: ZoneAssignRequest,
    session: SessionDep,
    user: StaffAdminUser,
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
async def get_settings_values(session: SessionDep, user: RulesUser) -> dict[str, str]:  # noqa: ARG001
    return await settings_service.get_all(session)


@router.put("/settings", summary="Change monitoring rules")
async def put_settings(
    payload: SettingsIn, session: SessionDep, user: RulesUser
) -> dict[str, str]:
    changes = payload.model_dump(exclude_none=True)
    if not changes:
        raise ValidationError("No settings supplied.")
    whole = changes.get("min_conducted_classes") or await settings_service.get_int(
        session, "min_conducted_classes"
    )
    by_mid = changes.get("min_conducted_before_mid")
    if by_mid is None:
        by_mid = await settings_service.get_int(session, "min_conducted_before_mid")
    if by_mid > whole:
        raise ValidationError(
            "The minimum by the mid-term cannot exceed the whole semester's minimum."
        )
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
    user: AuditUser,  # noqa: ARG001
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


@router.get("/teachers", response_model=list[TeacherOut], summary="Faculty directory")
async def teachers(
    session: SessionDep,
    user: TeacherReaderUser,  # noqa: ARG001
    q: str | None = None,
) -> list[TeacherOut]:
    query = select(Teacher).order_by(Teacher.initial).limit(500)
    if q:
        like = f"%{q.strip()}%"
        query = query.where(Teacher.name.ilike(like) | Teacher.initial.ilike(like))
    accounts = await account_service.teacher_accounts(session)
    out = []
    for t in (await session.scalars(query)).all():
        account = accounts.get(t.initial)
        out.append(
            TeacherOut(
                initial=t.initial,
                name=t.name,
                designation=t.designation,
                has_account=account is not None,
                account_active=account.is_active if account else None,
            )
        )
    return out


@router.post(
    "/teachers/{initial}/account",
    response_model=TeacherOut,
    summary="Create a teacher's sign-in account",
)
async def create_teacher_account(
    initial: str, payload: TeacherAccountRequest, session: SessionDep, user: TeacherAdminUser
) -> TeacherOut:
    """The teacher then signs in with their initial and this password."""
    account = await account_service.create_teacher_account(
        session, initial=initial, password=payload.password, actor=user
    )
    await session.commit()
    teacher = await session.scalar(
        select(Teacher).where(Teacher.initial == account.teacher_initial)
    )
    return TeacherOut(
        initial=account.teacher_initial or "",
        name=account.full_name,
        designation=teacher.designation if teacher else None,
        has_account=True,
        account_active=account.is_active,
    )


@router.post(
    "/teachers/accounts",
    response_model=TeacherAccountsCreated,
    summary="Create an account for every teacher without one",
)
async def create_all_teacher_accounts(
    payload: TeacherAccountRequest, session: SessionDep, user: TeacherAdminUser
) -> TeacherAccountsCreated:
    """Each signs in with their initial and this shared password."""
    created = await account_service.create_all_teacher_accounts(
        session, password=payload.password, actor=user
    )
    await session.commit()
    return TeacherAccountsCreated(created=len(created))


@router.put(
    "/teachers/{initial}/password",
    response_model=Message,
    summary="Reset a teacher's password",
)
async def reset_teacher_password(
    initial: str, payload: TeacherAccountRequest, session: SessionDep, user: TeacherAdminUser
) -> Message:
    await account_service.reset_teacher_password(
        session, initial=initial, password=payload.password, actor=user
    )
    await session.commit()
    return Message(detail="Password updated")

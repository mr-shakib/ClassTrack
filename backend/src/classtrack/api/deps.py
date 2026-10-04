"""Shared route dependencies: session, current user, permission gates.

Permission checks live here and nowhere else. Every gate names the permissions
it admits (``models/access.py``); which roles hold them is data an admin edits.
The frontend's permission-aware navigation is cosmetic; this module is the
actual security boundary.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from classtrack.core.config import get_settings
from classtrack.core.errors import AuthError, ForbiddenError
from classtrack.core.security import decode_token
from classtrack.db.session import get_session
from classtrack.models import Permission, User

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(request: Request, session: SessionDep) -> User:
    token = request.cookies.get(get_settings().session_cookie)
    if not token:
        # Accept a bearer token too, so curl and the CLI can drive the API.
        header = request.headers.get("authorization", "")
        if header.lower().startswith("bearer "):
            token = header[7:].strip()
    if not token:
        raise AuthError("Not authenticated")

    payload = decode_token(token)
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AuthError("Malformed session token") from exc

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise AuthError("Account is no longer active")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require(*permissions: Permission):
    """Build a dependency that admits a user holding any one of these."""

    async def guard(user: CurrentUser) -> User:
        if not user.can(*permissions):
            raise ForbiddenError(
                "You do not have permission to do this.",
                detail={"needs_one_of": [p.value for p in permissions]},
            )
        return user

    return guard


def _gate(*permissions: Permission):
    return Annotated[User, Depends(require(*permissions))]


P = Permission

# --- monitoring ---------------------------------------------------------------
#: The checking screen: report classes, or find one to correct.
CheckerUser = _gate(P.CHECK_CLASSES, P.CORRECT_CHECKS)
DashboardUser = _gate(P.VIEW_DASHBOARD)
CancelUser = _gate(P.CANCEL_CLASSES)

# --- reschedules and reports -------------------------------------------------
ApproverUser = _gate(P.DECIDE_RESCHEDULES)
ReportsUser = _gate(P.DEPARTMENT_REPORTS)

# --- semester and routine ----------------------------------------------------
RoutineUser = _gate(P.MANAGE_ROUTINE)
SemesterUser = _gate(P.MANAGE_SEMESTERS)
#: The semester list, which the routine and calendar screens choose from too.
SemesterReaderUser = _gate(P.MANAGE_SEMESTERS, P.MANAGE_ROUTINE, P.MANAGE_CALENDAR)
CalendarUser = _gate(P.MANAGE_CALENDAR)
RulesUser = _gate(P.MANAGE_RULES)

# --- people -----------------------------------------------------------------
AccountsUser = _gate(P.MANAGE_ACCOUNTS)
StaffAdminUser = _gate(P.MANAGE_STAFF)
#: Floors, which the department reports group by too.
ZoneReaderUser = _gate(P.MANAGE_STAFF, P.DEPARTMENT_REPORTS)
TeacherAdminUser = _gate(P.MANAGE_TEACHERS)
#: The faculty list, which a department report picks a teacher from too.
TeacherReaderUser = _gate(P.MANAGE_TEACHERS, P.DEPARTMENT_REPORTS)
RoleAdminUser = _gate(P.MANAGE_ROLES)
#: Roles and the permission list, to read or to give out to accounts.
RoleReaderUser = _gate(P.MANAGE_ROLES, P.MANAGE_ACCOUNTS)
AuditUser = _gate(P.VIEW_AUDIT)


# --- teaching ---------------------------------------------------------------
def _teacher_or(own: tuple[Permission, ...], *, anyone: Permission | None = None):
    """A teacher holding one of ``own``, for their own classes -- or anyone
    holding ``anyone``, for any teacher's."""

    async def guard(user: CurrentUser) -> User:
        if user.is_teacher and user.can(*own):
            return user
        if anyone is not None and user.can(anyone):
            return user
        raise ForbiddenError("You do not have permission to do this.")

    return guard


#: Schedule or complete a makeup class.
ReschedulerUser = Annotated[
    User, Depends(_teacher_or((P.REQUEST_RESCHEDULES,), anyone=P.RESCHEDULE_ANY))
]
#: Look for an empty room: for a reschedule or for an extra class.
RoomFinderUser = Annotated[
    User,
    Depends(_teacher_or((P.REQUEST_RESCHEDULES, P.BOOK_EXTRA_CLASSES), anyone=P.RESCHEDULE_ANY)),
]
#: Book an extra class -- always the teacher's own.
ExtraClassUser = Annotated[User, Depends(_teacher_or((P.BOOK_EXTRA_CLASSES,)))]


def scope_teacher(user: User, requested: str | None) -> str | None:
    """Resolve which teacher's data a caller may read.

    A teacher is held to their own initial whatever they asked for, unless
    another of their roles gives them a department-wide view; everyone else
    may ask for anyone, or for everyone (None).
    """
    if not user.sees_every_teacher:
        if requested and requested.upper() != (user.teacher_initial or "").upper():
            raise ForbiddenError("You may only view your own records.")
        return user.teacher_initial
    return requested.upper() if requested else None


def scope_report_teacher(user: User, requested: str | None) -> str | None:
    """Like ``scope_teacher``, for reports: department reports read anyone's,
    a teacher reads their own, and nobody else reads any."""
    if user.can(Permission.DEPARTMENT_REPORTS):
        return requested.upper() if requested else None
    if user.is_teacher:
        if requested and requested.upper() != (user.teacher_initial or "").upper():
            raise ForbiddenError("You may only view your own records.")
        return user.teacher_initial
    raise ForbiddenError("Reports are not available to you.")

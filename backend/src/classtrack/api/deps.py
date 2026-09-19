"""Shared route dependencies: session, current user, role gates.

Role checks live here and nowhere else. The frontend's role-aware navigation is
cosmetic; this module is the actual security boundary.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from classtrack.core.config import get_settings
from classtrack.core.errors import AuthError, ForbiddenError
from classtrack.core.security import decode_token
from classtrack.db.session import get_session
from classtrack.models import ADMIN_ROLES, CHECKING_ROLES, MANAGEMENT_ROLES, Role, User

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


def require_role(*roles: Role):
    """Build a dependency that admits only the given roles."""

    async def guard(user: CurrentUser) -> User:
        if user.role not in roles:
            allowed = ", ".join(r.value for r in roles)
            raise ForbiddenError(
                f"This action requires one of: {allowed}.",
                detail={"your_role": user.role.value},
            )
        return user

    return guard


#: Submit a classroom check -- staff, plus management and the committee, who may
#: also correct one after its day is over.
CheckingUser = Annotated[User, Depends(require_role(*CHECKING_ROLES))]
#: Full administration: reports, the approval queue, accounts and semesters.
#: The Head and Associate Head hold it, so neither needs a separate admin login.
AdminUser = Annotated[User, Depends(require_role(*ADMIN_ROLES))]
#: The live views and the admin screens -- admins plus the Coordination Officer,
#: who sees no reports and decides no reschedule requests.
ManagerUser = Annotated[User, Depends(require_role(*MANAGEMENT_ROLES))]
#: Schedule a makeup class.
TeacherUser = Annotated[User, Depends(require_role(Role.TEACHER, *ADMIN_ROLES))]


def scope_teacher(user: User, requested: str | None) -> str | None:
    """Resolve which teacher's data a caller may read.

    A TEACHER is forced onto their own initial regardless of what they asked
    for; everyone else may ask for anyone, or for everyone (None).
    """
    if user.role is Role.TEACHER:
        if requested and requested.upper() != (user.teacher_initial or "").upper():
            raise ForbiddenError("You may only view your own records.")
        return user.teacher_initial
    return requested.upper() if requested else None


def scope_report_teacher(user: User, requested: str | None) -> str | None:
    """Like ``scope_teacher``, for reports: only a teacher and the admins read them."""
    if user.role is not Role.TEACHER and user.role not in ADMIN_ROLES:
        raise ForbiddenError("Reports are not available to your role.")
    return scope_teacher(user, requested)

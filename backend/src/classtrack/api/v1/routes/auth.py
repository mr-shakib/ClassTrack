"""Login, logout, who-am-I, and the signed-in user's own profile and password."""

from __future__ import annotations

from fastapi import APIRouter, Response
from sqlalchemy.ext.asyncio import AsyncSession

from classtrack.api.deps import CurrentUser, SessionDep
from classtrack.core.config import get_settings
from classtrack.core.security import create_token
from classtrack.models import User
from classtrack.schemas.auth import (
    LoginRequest,
    PasswordChange,
    ProfileOut,
    ProfileUpdate,
    UserOut,
)
from classtrack.schemas.common import Message
from classtrack.services import auth_service, profile_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=UserOut, summary="Sign in")
async def login(payload: LoginRequest, response: Response, session: SessionDep) -> UserOut:
    user = await auth_service.authenticate(session, payload.username, payload.password)
    settings = get_settings()
    response.set_cookie(
        settings.session_cookie,
        create_token(user.id, user.role.value),
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.jwt_expire_hours * 3600,
        path="/",
    )
    return UserOut.model_validate(user)


@router.post("/logout", response_model=Message, summary="Sign out")
async def logout(response: Response) -> Message:
    response.delete_cookie(get_settings().session_cookie, path="/")
    return Message(detail="Signed out")


@router.get("/me", response_model=UserOut, summary="Current user")
async def me(session: SessionDep, user: CurrentUser) -> UserOut:
    out = UserOut.model_validate(user)
    teacher = await profile_service.teacher_of(session, user)
    out.photo_url = teacher.image_url if teacher else None
    return out


async def _profile(session: AsyncSession, user: User) -> ProfileOut:
    teacher = await profile_service.teacher_of(session, user)
    return ProfileOut(
        full_name=user.full_name,
        role=user.role,
        # Only a teacher has an initial; it is null too if their faculty row went.
        sign_in=user.teacher_initial or user.email,
        teacher_initial=user.teacher_initial,
        designation=teacher.designation if teacher else None,
        department=teacher.department if teacher else None,
        contact_email=teacher.email if teacher else None,
        photo_url=teacher.image_url if teacher else None,
    )


@router.get("/profile", response_model=ProfileOut, summary="Your profile")
async def profile(session: SessionDep, user: CurrentUser) -> ProfileOut:
    return await _profile(session, user)


@router.patch("/profile", response_model=ProfileOut, summary="Change your contact address")
async def update_profile(
    payload: ProfileUpdate, session: SessionDep, user: CurrentUser
) -> ProfileOut:
    """A teacher's absence reports are mailed here."""
    await profile_service.update_contact_email(session, user, payload.contact_email)
    await session.commit()
    return await _profile(session, user)


@router.post("/password", response_model=Message, summary="Change your password")
async def change_password(
    payload: PasswordChange, session: SessionDep, user: CurrentUser
) -> Message:
    await profile_service.change_password(
        session, user, current=payload.current_password, new=payload.new_password
    )
    await session.commit()
    return Message(detail="Password changed.")

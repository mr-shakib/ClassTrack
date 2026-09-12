"""Login, logout, and who-am-I."""

from __future__ import annotations

from fastapi import APIRouter, Response

from classtrack.api.deps import CurrentUser, SessionDep
from classtrack.core.config import get_settings
from classtrack.core.security import create_token
from classtrack.schemas.auth import LoginRequest, UserOut
from classtrack.schemas.common import Message
from classtrack.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=UserOut, summary="Sign in")
async def login(payload: LoginRequest, response: Response, session: SessionDep) -> UserOut:
    user = await auth_service.authenticate(session, payload.email, payload.password)
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
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)

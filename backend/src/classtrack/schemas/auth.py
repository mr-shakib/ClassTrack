"""Auth request/response models."""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, Field

from classtrack.models import Role
from classtrack.schemas.common import ORMModel


class LoginRequest(BaseModel):
    #: An email address, or a teacher's initial. ``email`` is still accepted as
    #: the key so existing clients keep working.
    username: str = Field(
        min_length=1, max_length=255, validation_alias=AliasChoices("username", "email")
    )
    password: str = Field(min_length=1)


class UserOut(ORMModel):
    id: int
    email: str
    full_name: str
    role: Role
    teacher_initial: str | None = None

"""Auth request/response models."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from classtrack.models import Role
from classtrack.schemas.common import ORMModel


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class UserOut(ORMModel):
    id: int
    email: str
    full_name: str
    role: Role
    teacher_initial: str | None = None

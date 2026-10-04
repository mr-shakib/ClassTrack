"""Auth request/response models."""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, Field

from classtrack.models import RoleKind, User
from classtrack.schemas.common import ORMModel


class LoginRequest(BaseModel):
    #: An email address, or a teacher's initial. ``email`` is still accepted as
    #: the key so existing clients keep working.
    username: str = Field(
        min_length=1, max_length=255, validation_alias=AliasChoices("username", "email")
    )
    password: str = Field(min_length=1)


class RoleRef(ORMModel):
    key: str
    name: str
    kind: RoleKind


class UserOut(ORMModel):
    id: int
    email: str
    full_name: str
    roles: list[RoleRef] = Field(default_factory=list)
    #: Everything any of the roles permits: what the screens show and hide by.
    #: The API checks again on every request.
    permissions: list[str] = Field(default_factory=list)
    #: A teacher: their own classes, reports and reschedules.
    is_teacher: bool = False
    #: Floor staff: their floors come first on the checking screen.
    is_staff: bool = False
    teacher_initial: str | None = None
    #: A teacher's photo from the faculty directory, for the header.
    photo_url: str | None = None

    @classmethod
    def of(cls, user: User, *, photo_url: str | None = None) -> UserOut:
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            roles=[RoleRef.model_validate(r) for r in user.ordered_roles],
            permissions=sorted(p.value for p in user.permissions),
            is_teacher=user.is_teacher,
            is_staff=user.is_staff,
            teacher_initial=user.teacher_initial,
            photo_url=photo_url,
        )


class PasswordChange(BaseModel):
    # Lengths are checked in the service, so a short password gets a sentence
    # rather than a validation dump.
    current_password: str
    new_password: str


class ProfileOut(BaseModel):
    full_name: str
    #: The names of the roles held, in the order they were made.
    roles: list[str]
    is_teacher: bool = False
    #: What the user types to sign in: a teacher's initial, else the email or ID.
    sign_in: str
    teacher_initial: str | None = None
    designation: str | None = None
    department: str | None = None
    #: Where a teacher's absence reports are mailed. Null for anyone else, and
    #: for a teacher with none on file.
    contact_email: str | None = None
    #: A teacher's photo from the faculty directory, when it has one.
    photo_url: str | None = None


class ProfileUpdate(BaseModel):
    contact_email: str = Field(min_length=1, max_length=255)

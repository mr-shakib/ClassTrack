"""Accounts and roles.

A TEACHER account is joined to its routine rows through ``teacher_initial``,
because the routine itself carries the initial rather than a faculty id.
"""

from __future__ import annotations

import enum

from sqlalchemy import Boolean, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from classtrack.db.base import Base, TimestampMixin


class Role(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    HOD = "HOD"
    STAFF = "STAFF"
    TEACHER = "TEACHER"


#: Roles permitted to submit a classroom check.
CHECKING_ROLES = (Role.STAFF, Role.HOD, Role.SUPER_ADMIN)
#: Roles permitted to see every teacher's data.
ADMIN_ROLES = (Role.HOD, Role.SUPER_ADMIN)


class User(Base, TimestampMixin):
    __tablename__ = "user"
    __table_args__ = (
        Index("ix_user_role", "role"),
        Index("ix_user_teacher_initial", "teacher_initial"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role, native_enum=False), nullable=False)

    #: Links the account to its routine rows. Required for TEACHER, else null.
    #: A TEACHER without it sees an empty schedule, so creation validates it.
    teacher_initial: Mapped[str | None] = mapped_column(
        String(16), ForeignKey("teacher.initial", ondelete="SET NULL")
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    @property
    def is_admin(self) -> bool:
        return self.role in ADMIN_ROLES

    def __repr__(self) -> str:
        return f"<User {self.email} {self.role.value}>"

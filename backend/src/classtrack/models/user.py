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
    #: Kept as a fallback login; the Head and Associate Head hold the same rights.
    SUPER_ADMIN = "SUPER_ADMIN"
    HOD = "HOD"
    #: Deputy to the HoD, with the same permissions.
    ASSOCIATE_HEAD = "ASSOCIATE_HEAD"
    #: Runs day-to-day monitoring: the live dashboard, the routine, the calendar
    #: and staff coverage, and corrects past checks. Sees no reports and decides
    #: no reschedule requests.
    COORDINATION_OFFICER = "COORDINATION_OFFICER"
    #: Reports classes and corrects a past check, nothing more.
    COMMITTEE = "COMMITTEE"
    STAFF = "STAFF"
    TEACHER = "TEACHER"


#: Full administration: reports, approvals, accounts and semesters.
ADMIN_ROLES = (Role.HOD, Role.ASSOCIATE_HEAD, Role.SUPER_ADMIN)
#: Day-to-day management: the live views and the admin screens, but not the
#: reports or the approval queue.
MANAGEMENT_ROLES = (*ADMIN_ROLES, Role.COORDINATION_OFFICER)
#: Roles permitted to correct a check after its day is over.
OVERRIDE_ROLES = (*MANAGEMENT_ROLES, Role.COMMITTEE)
#: Roles permitted to submit a classroom check.
CHECKING_ROLES = (Role.STAFF, *OVERRIDE_ROLES)


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

    @property
    def is_manager(self) -> bool:
        return self.role in MANAGEMENT_ROLES

    @property
    def can_override(self) -> bool:
        return self.role in OVERRIDE_ROLES

    def __repr__(self) -> str:
        return f"<User {self.email} {self.role.value}>"

"""Accounts.

A person holds one or more roles (``models/access.py``) and may do whatever any
of them permits. What they *are* comes from the roles' kinds: a teacher is an
account with a faculty initial and a teacher-kind role, joined to its routine
rows through ``teacher_initial`` because the routine carries the initial rather
than a faculty id; office staff hold a staff-kind role and check floors.
"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from classtrack.db.base import Base, TimestampMixin
from classtrack.models.access import Permission, Role, RoleKind, user_role


class User(Base, TimestampMixin):
    __tablename__ = "user"
    __table_args__ = (Index("ix_user_teacher_initial", "teacher_initial"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)

    #: Links a teacher account to its routine rows. Set only on teacher
    #: accounts, and required for one: without it the schedule is empty.
    teacher_initial: Mapped[str | None] = mapped_column(
        String(16), ForeignKey("teacher.initial", ondelete="SET NULL")
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    #: Loaded with the user, so a permission check never waits on a lazy load.
    roles: Mapped[list[Role]] = relationship(secondary=user_role, lazy="selectin", order_by=Role.id)

    @classmethod
    def of_kind(cls, kind: RoleKind):
        """In a query: accounts holding a role of this kind."""
        return cls.roles.any(Role.kind == kind)

    @property
    def ordered_roles(self) -> list[Role]:
        """What the person is first -- teacher, then floor staff -- then the rest."""
        rank = {RoleKind.TEACHER: 0, RoleKind.STAFF: 1, RoleKind.OFFICE: 2}
        return sorted(self.roles, key=lambda r: (rank[r.kind], r.id))

    @property
    def permissions(self) -> frozenset[Permission]:
        granted: set[Permission] = set()
        for role in self.roles:
            granted |= role.granted
        return frozenset(granted)

    def can(self, *permissions: Permission) -> bool:
        """Whether any of the user's roles grants any of these."""
        held = self.permissions
        return any(p in held for p in permissions)

    @property
    def is_teacher(self) -> bool:
        return self.teacher_initial is not None and any(
            r.kind is RoleKind.TEACHER for r in self.roles
        )

    @property
    def is_staff(self) -> bool:
        return any(r.kind is RoleKind.STAFF for r in self.roles)

    @property
    def sees_every_teacher(self) -> bool:
        """May look at any teacher's classes, not only their own.

        Someone who is not a teacher always could. A teacher can when another of
        their roles gives them a department-wide view.
        """
        return not self.is_teacher or self.can(
            Permission.DEPARTMENT_REPORTS,
            Permission.VIEW_DASHBOARD,
            Permission.RESCHEDULE_ANY,
            Permission.CORRECT_CHECKS,
        )

    def __repr__(self) -> str:
        return f"<User {self.email} {[r.key for r in self.roles]}>"

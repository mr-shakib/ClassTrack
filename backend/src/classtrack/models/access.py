"""Permissions and roles.

A *permission* is one thing the API lets a person do; the list below is every
one there is, and every gate in ``api/deps.py`` names one of them. A *role* is
a named set of permissions an admin can create and edit. A person holds one or
more roles and may do whatever any of them permits.

A role also has a *kind*, which says what the person is rather than what they
may do: a teacher, linked to a faculty initial and their own classes; office
staff, assigned floors to check; or office, neither. Kind is fixed when the
role is created -- it decides which accounts the role can be given to.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from sqlalchemy import JSON, Boolean, Column, Enum, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column

from classtrack.db.base import Base, TimestampMixin


class Permission(str, enum.Enum):
    # Monitoring
    CHECK_CLASSES = "checking.submit"
    CORRECT_CHECKS = "checking.correct"
    VIEW_DASHBOARD = "dashboard.view"
    CANCEL_CLASSES = "classes.cancel"
    # Reschedules
    DECIDE_RESCHEDULES = "reschedules.decide"
    RESCHEDULE_ANY = "reschedules.any_teacher"
    # A teacher's own: these only take effect on a teacher-kind role.
    REQUEST_RESCHEDULES = "reschedules.request"
    BOOK_EXTRA_CLASSES = "extra_classes.book"
    # Reports
    DEPARTMENT_REPORTS = "reports.department"
    # Semester and routine
    MANAGE_ROUTINE = "routine.manage"
    MANAGE_SEMESTERS = "semesters.manage"
    MANAGE_CALENDAR = "calendar.manage"
    MANAGE_RULES = "settings.manage"
    # People
    MANAGE_STAFF = "staff.manage"
    MANAGE_TEACHERS = "teachers.manage"
    MANAGE_ACCOUNTS = "accounts.manage"
    MANAGE_ROLES = "roles.manage"
    # Oversight
    VIEW_AUDIT = "audit.view"
    RECEIVE_ALERTS = "alerts.receive"


@dataclass(frozen=True, slots=True)
class PermissionInfo:
    permission: Permission
    group: str
    label: str
    description: str


#: Every permission, in the order and groups the role editor shows them.
PERMISSION_INFO: tuple[PermissionInfo, ...] = (
    PermissionInfo(
        Permission.CHECK_CLASSES,
        "Monitoring",
        "Check classes",
        "Report classes on the checking screen while they run.",
    ),
    PermissionInfo(
        Permission.CORRECT_CHECKS,
        "Monitoring",
        "Correct past checks",
        "Change a check after its day is over, or report a class before it starts.",
    ),
    PermissionInfo(
        Permission.VIEW_DASHBOARD,
        "Monitoring",
        "View live dashboard",
        "The live dashboard and the status of any day.",
    ),
    PermissionInfo(
        Permission.CANCEL_CLASSES,
        "Monitoring",
        "Cancel classes",
        "Take a class off the schedule, with a reason.",
    ),
    PermissionInfo(
        Permission.DECIDE_RESCHEDULES,
        "Reschedules",
        "Decide reschedule requests",
        "Approve or reject online reschedules in the approval queue.",
    ),
    PermissionInfo(
        Permission.RESCHEDULE_ANY,
        "Reschedules",
        "Reschedule any teacher's class",
        "Reschedule a missed class, or mark one done, on a teacher's behalf.",
    ),
    PermissionInfo(
        Permission.REQUEST_RESCHEDULES,
        "Teaching",
        "Reschedule own missed classes",
        "Book a room or ask to hold a missed class online. Teacher roles only.",
    ),
    PermissionInfo(
        Permission.BOOK_EXTRA_CLASSES,
        "Teaching",
        "Book extra classes",
        "Take an empty room for an extra class of their own section. Teacher roles only.",
    ),
    PermissionInfo(
        Permission.DEPARTMENT_REPORTS,
        "Reports",
        "Department reports",
        "Overview, daily, staff and unreported reports, and any teacher's report.",
    ),
    PermissionInfo(
        Permission.MANAGE_ROUTINE,
        "Semester & routine",
        "Manage routine",
        "Upload, review and activate the class routine.",
    ),
    PermissionInfo(
        Permission.MANAGE_SEMESTERS,
        "Semester & routine",
        "Manage semesters",
        "Create semesters, set exam dates, start a semester and generate its classes.",
    ),
    PermissionInfo(
        Permission.MANAGE_CALENDAR,
        "Semester & routine",
        "Manage calendar",
        "Add and remove holidays and closed days.",
    ),
    PermissionInfo(
        Permission.MANAGE_RULES,
        "Semester & routine",
        "Manage rules",
        "Change the monitoring rules: thresholds and minimum classes.",
    ),
    PermissionInfo(
        Permission.MANAGE_STAFF,
        "People",
        "Manage staff",
        "Create office staff accounts and assign their floors.",
    ),
    PermissionInfo(
        Permission.MANAGE_TEACHERS,
        "People",
        "Manage teacher accounts",
        "Give teachers accounts and reset their passwords.",
    ),
    PermissionInfo(
        Permission.MANAGE_ACCOUNTS,
        "People",
        "Manage accounts",
        "Create accounts, give and take roles, deactivate, reset passwords.",
    ),
    PermissionInfo(
        Permission.MANAGE_ROLES,
        "People",
        "Manage roles",
        "Create roles and choose what each one may do.",
    ),
    PermissionInfo(
        Permission.VIEW_AUDIT,
        "Oversight",
        "View audit log",
        "Every recorded change, who made it and when.",
    ),
    PermissionInfo(
        Permission.RECEIVE_ALERTS,
        "Oversight",
        "Receive department alerts",
        "Be notified of reschedule requests, booked rooms and disputed records.",
    ),
)

#: Only mean anything to a teacher: the class in question must be their own.
TEACHER_PERMISSIONS = frozenset({Permission.REQUEST_RESCHEDULES, Permission.BOOK_EXTRA_CLASSES})


class RoleKind(str, enum.Enum):
    #: Linked to a faculty initial: their own classes, reports and reschedules.
    TEACHER = "TEACHER"
    #: Office staff, assigned the floors they check.
    STAFF = "STAFF"
    #: Neither -- an office account, e.g. the Head or an exam controller.
    OFFICE = "OFFICE"


class BuiltinRole(str, enum.Enum):
    """The roles every install starts with, by key. They may be edited, but
    not deleted, and Super admin's permissions are fixed at all of them."""

    SUPER_ADMIN = "SUPER_ADMIN"
    HOD = "HOD"
    ASSOCIATE_HEAD = "ASSOCIATE_HEAD"
    COORDINATION_OFFICER = "COORDINATION_OFFICER"
    COMMITTEE = "COMMITTEE"
    STAFF = "STAFF"
    TEACHER = "TEACHER"


ALL_PERMISSIONS = frozenset(Permission)

_COORDINATION = frozenset(
    {
        Permission.CHECK_CLASSES,
        Permission.CORRECT_CHECKS,
        Permission.VIEW_DASHBOARD,
        Permission.CANCEL_CLASSES,
        Permission.MANAGE_ROUTINE,
        Permission.MANAGE_CALENDAR,
        Permission.MANAGE_RULES,
        Permission.MANAGE_STAFF,
        Permission.MANAGE_TEACHERS,
        Permission.VIEW_AUDIT,
    }
)

#: Name, kind, description and starting permissions of each built-in role --
#: exactly the access each had before roles became editable.
BUILTIN_ROLES: dict[BuiltinRole, tuple[str, RoleKind, str, frozenset[Permission]]] = {
    BuiltinRole.SUPER_ADMIN: (
        "Super admin",
        RoleKind.OFFICE,
        "Everything, always. Kept as a fallback sign-in.",
        ALL_PERMISSIONS,
    ),
    BuiltinRole.HOD: (
        "Head of Department",
        RoleKind.OFFICE,
        "Runs the department: reports, approvals, accounts and semesters.",
        ALL_PERMISSIONS,
    ),
    BuiltinRole.ASSOCIATE_HEAD: (
        "Associate Head",
        RoleKind.OFFICE,
        "Deputy to the Head, with the same access.",
        ALL_PERMISSIONS,
    ),
    BuiltinRole.COORDINATION_OFFICER: (
        "Coordination Officer",
        RoleKind.OFFICE,
        "Day-to-day monitoring, the routine, the calendar and staff coverage.",
        _COORDINATION,
    ),
    BuiltinRole.COMMITTEE: (
        "Committee member",
        RoleKind.OFFICE,
        "Reports classes and corrects past checks.",
        frozenset({Permission.CHECK_CLASSES, Permission.CORRECT_CHECKS}),
    ),
    BuiltinRole.STAFF: (
        "Office staff",
        RoleKind.STAFF,
        "Checks the classes on their floors.",
        frozenset({Permission.CHECK_CLASSES}),
    ),
    BuiltinRole.TEACHER: (
        "Teacher",
        RoleKind.TEACHER,
        "Their own classes, reports, reschedules and extra classes.",
        TEACHER_PERMISSIONS,
    ),
}

user_role = Table(
    "user_role",
    Base.metadata,
    Column("user_id", ForeignKey("user.id", ondelete="CASCADE"), primary_key=True),
    # A role still held cannot be deleted; the service says so first.
    Column("role_id", ForeignKey("role.id", ondelete="RESTRICT"), primary_key=True),
)


class Role(Base, TimestampMixin):
    __tablename__ = "role"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    #: A built-in role's ``BuiltinRole`` value, or ``CUSTOM_<n>`` for one an
    #: admin made. Never shown; the name is.
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    kind: Mapped[RoleKind] = mapped_column(Enum(RoleKind, native_enum=False), nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    #: Permission values. Read through ``granted``, which drops any this
    #: version does not know rather than failing on it.
    permission_values: Mapped[list[str]] = mapped_column(
        "permissions", JSON, default=list, nullable=False
    )

    @property
    def granted(self) -> frozenset[Permission]:
        if self.key == BuiltinRole.SUPER_ADMIN.value:
            return ALL_PERMISSIONS
        known = {p.value for p in Permission}
        return frozenset(Permission(v) for v in self.permission_values if v in known)

    @property
    def is_locked(self) -> bool:
        """Super admin always holds everything, so nobody is locked out."""
        return self.key == BuiltinRole.SUPER_ADMIN.value

    def __repr__(self) -> str:
        return f"<Role {self.key} {self.kind.value}>"

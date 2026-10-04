"""Model package. Importing it registers every table on ``Base.metadata``."""

from classtrack.models.academic import (
    BLOCKING_KINDS,
    TERM_LABELS,
    DayKind,
    Holiday,
    Semester,
    Term,
)
from classtrack.models.access import (
    ALL_PERMISSIONS,
    BUILTIN_ROLES,
    PERMISSION_INFO,
    TEACHER_PERMISSIONS,
    BuiltinRole,
    Permission,
    PermissionInfo,
    Role,
    RoleKind,
    user_role,
)
from classtrack.models.assignment import StaffZone
from classtrack.models.audit import AuditLog
from classtrack.models.check import CheckOutcome, CheckRecord
from classtrack.models.instance import (
    MAKEUP_ELIGIBLE,
    ClassInstance,
    ClassStatus,
    DerivedStatus,
    TeacherResponse,
)
from classtrack.models.makeup import MakeupClass, MakeupMode, MakeupStatus
from classtrack.models.notification import Notification, NotificationKind
from classtrack.models.routine import ClassSession, Routine
from classtrack.models.setting import SETTING_DEFAULTS, Setting
from classtrack.models.teacher import Teacher
from classtrack.models.user import User

__all__ = [
    "ALL_PERMISSIONS",
    "BLOCKING_KINDS",
    "BUILTIN_ROLES",
    "MAKEUP_ELIGIBLE",
    "PERMISSION_INFO",
    "SETTING_DEFAULTS",
    "TEACHER_PERMISSIONS",
    "TERM_LABELS",
    "AuditLog",
    "BuiltinRole",
    "CheckOutcome",
    "CheckRecord",
    "ClassInstance",
    "ClassSession",
    "ClassStatus",
    "DayKind",
    "DerivedStatus",
    "Holiday",
    "MakeupClass",
    "MakeupMode",
    "MakeupStatus",
    "Notification",
    "NotificationKind",
    "Permission",
    "PermissionInfo",
    "Role",
    "RoleKind",
    "Routine",
    "Semester",
    "Setting",
    "StaffZone",
    "Teacher",
    "TeacherResponse",
    "Term",
    "User",
    "user_role",
]

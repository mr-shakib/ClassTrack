"""Model package. Importing it registers every table on ``Base.metadata``."""

from classtrack.models.academic import BLOCKING_KINDS, DayKind, Holiday, Semester
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
from classtrack.models.user import (
    ADMIN_ROLES,
    CHECKING_ROLES,
    MANAGEMENT_ROLES,
    OVERRIDE_ROLES,
    Role,
    User,
)

__all__ = [
    "ADMIN_ROLES",
    "BLOCKING_KINDS",
    "CHECKING_ROLES",
    "MAKEUP_ELIGIBLE",
    "MANAGEMENT_ROLES",
    "OVERRIDE_ROLES",
    "SETTING_DEFAULTS",
    "AuditLog",
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
    "Role",
    "Routine",
    "Semester",
    "Setting",
    "StaffZone",
    "Teacher",
    "TeacherResponse",
    "User",
]

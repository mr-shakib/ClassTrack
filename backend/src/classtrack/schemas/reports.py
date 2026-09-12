"""Report response models."""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime

from pydantic import BaseModel


class DateRange(BaseModel):
    from_: Date
    to: Date

    model_config = {"populate_by_name": True, "serialization_alias": None}


class DailyReport(BaseModel):
    date: Date
    total_scheduled: int
    total_checked: int
    running: int
    late: int
    missed: int
    not_checked: int
    makeup: int
    online_approved: int
    unresolved: int


class TeacherReport(BaseModel):
    teacher_initial: str
    teacher_name: str | None = None
    range: dict[str, Date]
    total_scheduled: int
    conducted: int
    late: int
    missed: int
    not_checked: int
    makeup_scheduled: int
    makeup_completed: int
    makeup_pending: int
    online_approved: int
    unresolved: int


class StaffRow(BaseModel):
    user_id: int
    name: str
    assigned: int
    checked: int
    completion_rate: float


class StaffReport(BaseModel):
    range: dict[str, Date]
    assigned: int
    checked: int
    not_checked: int
    completion_rate: float
    rows: list[StaffRow]


# --- accountability: who failed to report what ------------------------------


class UnreportedClass(BaseModel):
    instance_id: int
    date: Date
    time_slot: str
    room: str
    zone: str
    course_code: str
    section: str
    teacher_initial: str
    hours_since: float


class StaffMisses(BaseModel):
    user_id: int
    name: str
    email: str
    zones: list[str]
    total: int
    today: int
    this_week: int
    urgency: str
    classes: list[UnreportedClass]


class UnreportedSummary(BaseModel):
    total: int
    today: int
    this_week: int
    staff_with_misses: int
    unassigned: int


class UnreportedReport(BaseModel):
    as_of: datetime
    range: dict[str, Date]
    summary: UnreportedSummary
    by_staff: list[StaffMisses]
    #: Classes on floors nobody covers -- an admin gap, not a staff failure.
    unassigned: list[UnreportedClass]

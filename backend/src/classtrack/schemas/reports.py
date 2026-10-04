"""Report response models."""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime

from pydantic import BaseModel, Field

from classtrack.models import Term
from classtrack.schemas.monitoring import SlotRef, StatusOut


class DateRange(BaseModel):
    from_: Date
    to: Date

    model_config = {"populate_by_name": True, "serialization_alias": None}


class Tally(BaseModel):
    """Counts per outcome. Every class falls in exactly one bucket."""

    total: int = 0
    #: Routine classes, excluding makeups.
    scheduled: int = 0
    #: Conducted on time plus late: the class happened.
    held: int = 0
    conducted: int = 0
    late: int = 0
    missed: int = 0
    not_checked: int = 0
    rescheduled: int = 0
    cancelled: int = 0
    pending: int = 0
    makeup_held: int = 0
    #: Extra classes held, on top of the routine; counted in ``held`` too.
    extra_held: int = 0
    #: Held / (held + missed), as a percentage. Not-checked classes are left out:
    #: a staff gap says nothing about the teacher.
    conduct_rate: float = 0.0
    avg_late_minutes: float = 0.0


class FloorTally(Tally):
    key: str
    label: str
    short_label: str


class SlotTally(Tally):
    time_slot: str


class TrendPoint(Tally):
    date: Date


class TeacherTally(Tally):
    teacher_initial: str
    teacher_name: str | None = None
    courses: int = 0
    courses_below_minimum: int = 0
    min_course_held: int = 0
    #: At least one of the teacher's courses is below the minimum so far.
    flagged: bool = False


class CourseTally(Tally):
    teacher_initial: str
    teacher_name: str | None = None
    course_code: str
    course_title: str | None = None
    section: str
    below_minimum: bool = False


class ClassRow(BaseModel):
    instance_id: int
    date: Date
    day: str
    time_slot: str
    room: str
    zone: str
    course_code: str
    course_title: str | None = None
    section: str
    teacher_initial: str
    teacher_name: str | None = None
    status: StatusOut | None = None
    outcome: str
    late_minutes: int | None = None
    remark: str | None = None
    is_makeup: bool = False
    is_extra: bool = False
    #: Set on a makeup: the missed class it recovers.
    rescheduled_from: SlotRef | None = None
    #: Set on a missed class: where it was moved.
    rescheduled_to: SlotRef | None = None


class Overview(BaseModel):
    range: dict[str, Date]
    #: "Fall 2026 · Till mid-term" for a term of a semester; null for plain dates.
    label: str | None = None
    term: Term | None = None
    filters: dict[str, str | None]
    min_conducted: int
    totals: Tally
    #: "day", "week" or "month" -- how ``trend`` is bucketed.
    granularity: str
    trend: list[TrendPoint]
    by_floor: list[FloorTally]
    by_slot: list[SlotTally]
    by_teacher: list[TeacherTally]
    by_course: list[CourseTally]


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
    totals: Tally
    by_floor: list[FloorTally] = Field(default_factory=list)
    by_slot: list[SlotTally] = Field(default_factory=list)
    rescheduled_in: list[ClassRow] = Field(default_factory=list)


class TeacherReport(BaseModel):
    teacher_initial: str
    teacher_name: str | None = None
    range: dict[str, Date]
    label: str | None = None
    term: Term | None = None
    min_conducted: int
    total_scheduled: int
    conducted: int
    on_time: int
    late: int
    missed: int
    not_checked: int
    rescheduled: int
    cancelled: int
    makeup_scheduled: int
    makeup_completed: int
    makeup_pending: int
    online_approved: int
    unresolved: int
    conduct_rate: float
    avg_late_minutes: float
    flagged: bool
    courses: list[CourseTally]
    classes: list[ClassRow]


class StaffRow(BaseModel):
    user_id: int
    name: str
    assigned: int
    checked: int
    completion_rate: float


class StaffReport(BaseModel):
    range: dict[str, Date]
    label: str | None = None
    assigned: int
    checked: int
    not_checked: int
    completion_rate: float
    rows: list[StaffRow]


class TermOut(BaseModel):
    term: Term
    label: str
    #: Null while the exam dates the term needs are unset.
    from_: Date | None = Field(default=None, alias="from")
    to: Date | None = None
    #: False until the dates are set and the term has begun.
    available: bool

    model_config = {"populate_by_name": True}


class ReportSemester(BaseModel):
    """A semester as the report period picker needs it -- for teachers too."""

    id: int
    name: str
    is_active: bool
    start_date: Date
    end_date: Date
    terms: list[TermOut]


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

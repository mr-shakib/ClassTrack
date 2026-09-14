"""Monitoring request/response models. Mirrors docs/API.md."""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime, time

from pydantic import BaseModel, Field

from classtrack.models import (
    CheckOutcome,
    ClassStatus,
    DerivedStatus,
    TeacherResponse,
)
from classtrack.schemas.common import ORMModel

StatusOut = ClassStatus | DerivedStatus


class CheckOut(ORMModel):
    outcome: CheckOutcome
    arrival_time: time | None = None
    late_minutes: int | None = None
    remark: str | None = None
    checked_at: datetime
    checked_by: str | None = None


class RoomRow(BaseModel):
    """One room card on the staff checking screen."""

    instance_id: int
    room: str
    room_type: str
    course_code: str
    course_title: str | None = None
    section: str
    teacher_initial: str
    teacher_name: str | None = None
    scheduled_start: str
    scheduled_end: str
    is_makeup: bool
    #: "KT-3", "G1-0", "Other" -- shown so staff can see the card is theirs.
    zone: str | None = None
    #: "KT-3", "UNZONED" -- matches ``FloorSummary.key``.
    zone_key: str | None = None
    status: StatusOut | None = None
    check: CheckOut | None = None


class FloorSummary(BaseModel):
    """One floor card on the staff checking screen."""

    key: str
    #: "KT · Floor 3", "G1 · Ground floor", "Other rooms".
    label: str
    short_label: str
    total: int
    checked: int
    #: One of the caller's assigned floors. Listed first; never a restriction.
    is_mine: bool = False


class CheckingScreen(BaseModel):
    date: Date
    time_slot: str
    slot_state: str
    window_closes_at: datetime
    #: The caller's assigned floors (staff only). They order the list, not filter it.
    zones: list[str] = Field(default_factory=list)
    floors: list[FloorSummary] = Field(default_factory=list)
    rooms: list[RoomRow]


class CheckRequest(BaseModel):
    outcome: CheckOutcome
    #: Required when outcome is LATE.
    arrival_time: time | None = None
    remark: str | None = Field(default=None, max_length=2000)
    #: Required when an admin changes a record after the window has closed.
    #: Staff cannot submit outside the window at all, so this is ignored for them.
    reason: str | None = Field(default=None, max_length=2000)


class CheckResponse(BaseModel):
    instance_id: int
    status: StatusOut | None
    late_minutes: int | None = None
    checked_by: str
    checked_at: datetime
    #: True when this was an admin correction made after the window closed.
    outside_window: bool = False


class InstanceOut(ORMModel):
    id: int
    date: Date
    day: str
    time_slot: str
    room: str
    #: "Theory" or "Lab" -- a reschedule is offered rooms of the same kind.
    room_type: str = "Theory"
    course_code: str
    course_title: str | None = None
    section: str
    batch: str
    teacher_initial: str
    is_makeup: bool
    status: StatusOut | None = None
    teacher_response: TeacherResponse | None = None
    response_note: str | None = None
    check: CheckOut | None = None


class RespondRequest(BaseModel):
    response: TeacherResponse
    note: str | None = Field(default=None, max_length=2000)


class CancelRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


class DashboardSummary(BaseModel):
    scheduled_now: int = 0
    running: int = 0
    late: int = 0
    missed: int = 0
    not_checked: int = 0
    makeup_physical: int = 0
    online_approved: int = 0


class AttentionCounts(BaseModel):
    missed_today: int = 0
    not_checked_today: int = 0
    pending_online: int = 0
    pending_makeup: int = 0
    disputes: int = 0


class DashboardRow(BaseModel):
    instance_id: int
    room: str
    teacher_initial: str
    teacher_name: str | None = None
    course_code: str
    section: str
    time_slot: str
    status: StatusOut | None
    late_minutes: int | None = None
    checked_by: str | None = None
    checked_at: str | None = None
    is_makeup: bool = False


class DashboardOut(BaseModel):
    as_of: datetime
    current_slot: str | None
    summary: DashboardSummary
    rows: list[DashboardRow]
    attention: AttentionCounts

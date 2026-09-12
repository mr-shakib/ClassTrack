"""Report response models."""

from __future__ import annotations

from datetime import date as Date

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

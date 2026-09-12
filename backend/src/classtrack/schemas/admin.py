"""Admin request/response models."""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from classtrack.models import DayKind, NotificationKind, Role
from classtrack.schemas.common import ORMModel


class NotificationOut(ORMModel):
    id: int
    kind: NotificationKind
    title: str
    body: str
    link: str | None = None
    read_at: datetime | None = None
    created_at: datetime


class SemesterIn(BaseModel):
    name: str
    start_date: Date
    end_date: Date
    routine_id: int | None = None
    department: str = "cse"


class SemesterOut(ORMModel):
    id: int
    name: str
    department: str
    routine_id: int | None
    start_date: Date
    end_date: Date
    is_active: bool


class HolidayIn(BaseModel):
    date: Date
    title: str
    kind: DayKind = DayKind.HOLIDAY
    semester_id: int | None = None


class HolidayOut(ORMModel):
    id: int
    semester_id: int
    date: Date
    title: str
    kind: DayKind


class UserIn(BaseModel):
    email: EmailStr
    full_name: str
    role: Role
    password: str = Field(min_length=6)
    teacher_initial: str | None = None


class UserOut(ORMModel):
    id: int
    email: str
    full_name: str
    role: Role
    teacher_initial: str | None
    is_active: bool


class SettingsIn(BaseModel):
    missed_threshold_minutes: int | None = Field(default=None, ge=1, le=180)
    check_window_minutes: int | None = Field(default=None, ge=1, le=180)


class AuditOut(ORMModel):
    id: int
    actor_id: int | None
    actor_name: str | None = None
    entity_type: str
    entity_id: int
    action: str
    before: dict | None
    after: dict | None
    reason: str | None
    created_at: datetime


class RoutineOut(ORMModel):
    id: int
    department: str
    version: str
    semester: str | None
    source_filename: str | None
    is_active: bool
    session_count: int
    published_at: datetime | None


class ActivateRequest(BaseModel):
    semester_id: int | None = None


class SessionRow(BaseModel):
    day: str
    time_slot: str
    room: str
    course_code: str
    section: str
    teacher: str
    is_lab: bool


class RoutineReview(BaseModel):
    routine: RoutineOut
    conflicts: list[dict]
    sessions: list[SessionRow]
    total_sessions: int

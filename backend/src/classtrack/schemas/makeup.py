"""Makeup and approval models."""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime

from pydantic import BaseModel, Field

from classtrack.models import MakeupMode, MakeupStatus
from classtrack.schemas.common import ORMModel


class ConflictItem(BaseModel):
    type: str
    message: str
    instance_id: int | None = None


class ConflictReportOut(BaseModel):
    ok: bool
    overridable: bool
    conflicts: list[ConflictItem]


class ConflictCheckRequest(BaseModel):
    date: Date
    time_slot: str
    teacher_initial: str | None = None
    room: str | None = None
    section: str | None = None


class MakeupCreateRequest(BaseModel):
    original_instance_id: int
    mode: MakeupMode
    date: Date
    time_slot: str
    #: Required for PHYSICAL, ignored for ONLINE.
    room: str | None = None
    reason: str | None = Field(default=None, max_length=2000)


class MakeupOut(ORMModel):
    id: int
    original_instance_id: int
    teacher_initial: str
    mode: MakeupMode
    date: Date
    time_slot: str
    room: str | None = None
    reason: str | None = None
    status: MakeupStatus
    decision_note: str | None = None
    decided_at: datetime | None = None
    created_instance_id: int | None = None
    #: Filled in by the route for the approval queue and teacher views.
    original_course_code: str | None = None
    original_section: str | None = None
    original_date: Date | None = None
    original_time_slot: str | None = None
    original_room: str | None = None
    teacher_name: str | None = None


class FreeRoomOut(BaseModel):
    room: str
    room_type: str
    #: Short floor label, e.g. "KT-3".
    zone: str


class DecisionRequest(BaseModel):
    decision: str = Field(pattern="^(APPROVE|REJECT)$")
    note: str | None = Field(default=None, max_length=2000)

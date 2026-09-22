"""Makeup and approval models."""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

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
    #: One of the two, as for `MakeupCreateRequest`.
    time_slot: str | None = None
    start_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    teacher_initial: str | None = None
    room: str | None = None
    section: str | None = None


class MakeupCreateRequest(BaseModel):
    original_instance_id: int
    mode: MakeupMode
    date: Date
    #: A routine slot. Required for PHYSICAL; for ONLINE, send this or `start_time`.
    time_slot: str | None = None
    #: ONLINE only: a 24-hour `HH:MM` the teacher picked off the clock. The class
    #: runs the standard class length from there, on any day at any hour.
    start_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    #: Required for PHYSICAL, ignored for ONLINE.
    room: str | None = None

    @model_validator(mode="after")
    def _one_time(self) -> MakeupCreateRequest:
        if bool(self.time_slot) == bool(self.start_time):
            raise ValueError("Send either time_slot or start_time, not both.")
        if self.start_time and self.mode is not MakeupMode.ONLINE:
            raise ValueError("Only an online class can be held at a time off the routine.")
        return self
    reason: str | None = Field(default=None, max_length=2000)
    #: ONLINE only, optional: a Drive link for the approver to open. Ignored for PHYSICAL.
    drive_link: str | None = Field(default=None, max_length=1024)


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
    drive_link: str | None = None
    completed_at: datetime | None = None
    #: When the rescheduled class ends; it can be marked done from then on.
    ends_at: datetime | None = None
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


class CompleteRequest(BaseModel):
    #: Required when the makeup is ONLINE, ignored when PHYSICAL.
    drive_link: str | None = Field(default=None, max_length=1024)


class DecisionRequest(BaseModel):
    decision: str = Field(pattern="^(APPROVE|REJECT)$")
    note: str | None = Field(default=None, max_length=2000)

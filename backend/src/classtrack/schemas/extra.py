"""Extra-class booking."""

from __future__ import annotations

from datetime import date as Date

from pydantic import BaseModel, Field


class ExtraSectionOut(BaseModel):
    course_code: str
    course_title: str
    section: str
    #: The kind of room the section usually meets in, to offer those first.
    room_type: str


class ExtraClassRequest(BaseModel):
    course_code: str = Field(min_length=1, max_length=64)
    section: str = Field(min_length=1, max_length=32)
    date: Date
    #: A routine slot: a class in a room runs where staff walk.
    time_slot: str = Field(min_length=1, max_length=32)
    room: str = Field(min_length=1, max_length=64)

"""What students read, and what is written to them. Mirrors docs/API.md."""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime

from pydantic import BaseModel, Field


class LabGroupOut(BaseModel):
    token: str
    section: str


class RetakeGroupOut(BaseModel):
    #: "CSE447:RE_A": a retake group is only a group within its course.
    token: str
    section: str
    lab_groups: list[LabGroupOut]


class RetakeCourseOut(BaseModel):
    course_code: str
    course_title: str | None = None
    groups: list[RetakeGroupOut]


class SectionOut(BaseModel):
    #: "63_A". Its token is itself.
    section: str
    #: "63".
    intake: str
    #: "63_A1", "63_A2": its lab groups, when it has any.
    lab_groups: list[str]


class DirectoryOut(BaseModel):
    department: str
    semester: str | None = None
    sections: list[SectionOut]
    retakes: list[RetakeCourseOut]


class TopicsOut(BaseModel):
    #: Followed for every notice to the student's groups.
    alerts: list[str]
    #: Followed for a push shortly before each of their classes.
    reminders: list[str]
    #: How long before a class it is reminded; 0 means no reminders. The app
    #: sets its own alarm this far ahead when the phone allows it.
    reminder_minutes: int = 10


class TeacherCardOut(BaseModel):
    initial: str
    name: str | None = None
    designation: str | None = None
    office_room: str | None = None
    photo_url: str | None = None


class MovedToOut(BaseModel):
    date: Date
    time_slot: str
    room: str | None = None
    online: bool = False


class MakeupForOut(BaseModel):
    date: Date
    time_slot: str


class ClassNoteOut(BaseModel):
    body: str
    author: str
    created_at: datetime


class StudentClassOut(BaseModel):
    """A class as students see it: where and when, and whether it is on."""

    id: int
    date: Date
    day: str
    time_slot: str
    #: Minutes past midnight, for "on now" and the 24-hour clock.
    start_min: int
    end_min: int
    #: Null when it is held online.
    room: str | None = None
    room_type: str
    online: bool = False
    #: The course alone, "CSE311"; the section is beside it.
    course_code: str
    course_title: str | None = None
    section: str
    #: CLASS from the routine, a MAKEUP for one that was moved, or an EXTRA class.
    kind: str
    #: SCHEDULED, CANCELLED, or MOVED to the time in ``moved_to``.
    state: str
    moved_to: MovedToOut | None = None
    #: On a makeup: the class it makes up.
    makeup_for: MakeupForOut | None = None
    #: On an online makeup: where to join it.
    join_link: str | None = None
    teacher: TeacherCardOut
    #: The latest note the teacher wrote about this class.
    note: ClassNoteOut | None = None


class StudentNoticeOut(BaseModel):
    id: int
    #: ANNOUNCEMENT from the department, TEACHER, or CHANGE to a class.
    kind: str
    title: str
    body: str
    author: str
    created_at: datetime
    #: The groups it was written to.
    targets: list[str]
    #: The class it is about, if one.
    about: StudentClassOut | None = None


class FreeRoomOut(BaseModel):
    room: str
    room_type: str
    zone: str


class FreeSlotOut(BaseModel):
    time_slot: str
    rooms: list[FreeRoomOut]


class ExamOut(BaseModel):
    name: str
    start: Date
    end: Date


class DayOffOut(BaseModel):
    date: Date
    title: str
    #: HOLIDAY, EXAM, CLOSED, or SPECIAL (an extra teaching day).
    kind: str


class CalendarOut(BaseModel):
    name: str
    start_date: Date
    end_date: Date
    exams: list[ExamOut]
    holidays: list[DayOffOut]


class TeacherGroupOut(BaseModel):
    token: str
    course_code: str
    course_title: str
    section: str


class TeacherNoticeIn(BaseModel):
    """A teacher's note: about one class (``instance_id``), or to chosen sections."""

    model_config = {"str_strip_whitespace": True}

    body: str = Field(min_length=1, max_length=500)
    targets: list[str] = Field(default_factory=list, max_length=16)
    instance_id: int | None = None


class AdminNoticeIn(BaseModel):
    model_config = {"str_strip_whitespace": True}

    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=1000)
    #: "*" everyone, "63" an intake, "63_A" a section, "CSE447:RE_A" a retake group.
    targets: list[str] = Field(min_length=1, max_length=64)

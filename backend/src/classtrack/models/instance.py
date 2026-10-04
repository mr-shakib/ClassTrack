"""The class instance: one scheduled class on one date.

``ClassSession`` is the *template* -- "CSE311 is in KT-305 every Sunday at
10:00-11:30". ``ClassInstance`` is the *occurrence* -- "on 2026-09-13 that class
had status X, checked by Y at Z". Everything monitored hangs off the instance.

Room, teacher, course and slot are denormalised onto each row on purpose: the
staff screen and the live dashboard then read a single table through one index,
with no join on the hot path, and history survives a later routine revision.
"""

from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from classtrack.db.base import Base, TimestampMixin


class ClassStatus(str, enum.Enum):
    """Stored, terminal statuses only.

    ``UPCOMING`` and ``ONGOING`` are *derived from the clock* and never stored --
    see ``services/status_engine.py``. A null status means "not yet resolved",
    which is what makes the sweep naturally idempotent: it selects exactly the
    rows where ``status IS NULL``.
    """

    RUNNING = "RUNNING"
    LATE = "LATE"
    MISSED = "MISSED"
    NOT_CHECKED = "NOT_CHECKED"
    #: No longer set: an in-room reschedule once waited for the HoD, and goes
    #: straight to MAKEUP_SCHEDULED now. Rows from then still carry it, and a
    #: rejection still returns them to MISSED.
    MAKEUP_REQUESTED = "MAKEUP_REQUESTED"
    MAKEUP_SCHEDULED = "MAKEUP_SCHEDULED"
    MAKEUP_COMPLETED = "MAKEUP_COMPLETED"
    ONLINE_PENDING = "ONLINE_PENDING"
    ONLINE_APPROVED = "ONLINE_APPROVED"
    ONLINE_REJECTED = "ONLINE_REJECTED"
    CANCELLED = "CANCELLED"


class DerivedStatus(str, enum.Enum):
    """Clock-derived statuses. Returned by the API, never persisted."""

    UPCOMING = "UPCOMING"
    ONGOING = "ONGOING"


class TeacherResponse(str, enum.Enum):
    CONFIRMED = "CONFIRMED"
    DISPUTED = "DISPUTED"


#: Statuses the sweep must never overwrite -- it only touches ``status IS NULL``,
#: but this spells out the intent for readers and for the makeup guard.
TERMINAL_STATUSES = frozenset(ClassStatus)

#: A missed class the teacher has acknowledged can proceed to makeup (BR-09).
MAKEUP_ELIGIBLE = (ClassStatus.MISSED,)


class ClassInstance(Base, TimestampMixin):
    __tablename__ = "class_instance"
    __table_args__ = (
        # Makes generation idempotent: re-running it is an upsert, not a duplicate.
        UniqueConstraint("session_id", "date", name="uq_class_instance_session_date"),
        # Conflict detection and the staff screen.
        Index("ix_instance_date_slot", "date", "time_slot"),
        Index("ix_instance_date_room", "date", "time_slot", "room"),
        Index("ix_instance_teacher_date", "teacher_initial", "date"),
        # Sweep and dashboard.
        Index("ix_instance_status_date", "status", "date"),
        Index("ix_instance_section_date", "section", "date", "time_slot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    #: Null for a makeup instance, which has no routine template behind it.
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("class_session.id", ondelete="CASCADE")
    )
    semester_id: Mapped[int] = mapped_column(
        ForeignKey("semester.id", ondelete="CASCADE"), nullable=False
    )

    date: Mapped[date] = mapped_column(Date, nullable=False)
    day: Mapped[str] = mapped_column(String(16), nullable=False)

    #: Lattice coordinate, compared with ``==``. Never interval arithmetic.
    time_slot: Mapped[str] = mapped_column(String(32), nullable=False)
    #: Derived from the slot, for display and sorting only.
    start_min: Mapped[int] = mapped_column(Integer, nullable=False)
    end_min: Mapped[int] = mapped_column(Integer, nullable=False)

    room: Mapped[str] = mapped_column(String(64), nullable=False)
    room_type: Mapped[str] = mapped_column(String(32), default="Theory", nullable=False)
    course_code: Mapped[str] = mapped_column(String(64), nullable=False)
    course_title: Mapped[str | None] = mapped_column(String(255))
    section: Mapped[str] = mapped_column(String(32), nullable=False)
    batch: Mapped[str] = mapped_column(String(32), nullable=False)
    teacher_initial: Mapped[str] = mapped_column(String(16), nullable=False)

    #: Null means unresolved -- the API derives UPCOMING/ONGOING from the clock.
    status: Mapped[ClassStatus | None] = mapped_column(
        Enum(ClassStatus, native_enum=False), default=None
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    is_makeup: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    #: A class the teacher booked in an empty room on top of the routine. Checked
    #: and counted like any other, but never owed: missing one asks for no
    #: reschedule. Like a makeup it has no ``session_id``.
    is_extra: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    makeup_id: Mapped[int | None] = mapped_column(
        ForeignKey("makeup_class.id", ondelete="SET NULL")
    )

    #: Teacher's answer to a missed-class record (BR-08). Recording a dispute
    #: does not change ``status``: the original monitoring record must survive.
    teacher_response: Mapped[TeacherResponse | None] = mapped_column(
        Enum(TeacherResponse, native_enum=False)
    )
    response_note: Mapped[str | None] = mapped_column(Text)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    check: Mapped[CheckRecord | None] = relationship(
        back_populates="instance",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
        lazy="selectin",
    )

    @property
    def is_resolved(self) -> bool:
        return self.status is not None

    def __repr__(self) -> str:
        return (
            f"<ClassInstance {self.date} {self.time_slot} {self.room} "
            f"{self.course_code} {self.status.value if self.status else 'unresolved'}>"
        )


# Imported at the bottom to keep the relationship annotation resolvable without
# a circular import at module load.
from classtrack.models.check import CheckRecord  # noqa: E402

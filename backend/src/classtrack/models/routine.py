"""The routine data model.

One table holds every class. It is indexed three ways so all four queries are
index hits.

This is the deliberate departure from the app we studied: it wrote every record
*twice* -- once under a batch key, once under a teacher key -- because IndexedDB
cannot index arbitrary fields. We have a real database, so each class is stored
once and the indexes do the work. Half the storage, and room search drops from
O(n) to an index seek.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from classtrack.db.base import Base, TimestampMixin


class Routine(Base, TimestampMixin):
    """One published revision of a department's routine.

    DIU republishes mid-semester and numbers each revision. A new revision is
    ingested into a new row and only becomes ``is_active`` once the whole import
    succeeds, so clients never observe a half-imported routine.
    """

    __tablename__ = "routine"
    __table_args__ = (
        UniqueConstraint("department", "version", name="uq_routine_department_version"),
        Index("ix_routine_department_active", "department", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    department: Mapped[str] = mapped_column(String(16), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    semester: Mapped[str | None] = mapped_column(String(64))
    source_filename: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    session_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    sessions: Mapped[list[ClassSession]] = relationship(
        back_populates="routine", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<Routine {self.department} v{self.version}{' active' if self.is_active else ''}>"


class ClassSession(Base):
    """A single class: one cell of the routine grid."""

    __tablename__ = "class_session"
    __table_args__ = (
        Index("ix_session_batch", "routine_id", "batch"),
        Index("ix_session_teacher", "routine_id", "teacher"),
        Index("ix_session_room_day_slot", "routine_id", "room", "day", "time_slot"),
        Index("ix_session_day_slot", "routine_id", "day", "time_slot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    routine_id: Mapped[int] = mapped_column(
        ForeignKey("routine.id", ondelete="CASCADE"), nullable=False
    )

    # --- lattice coordinates -------------------------------------------------
    #: Weekday name, e.g. "Sunday". From the grid's row axis.
    day: Mapped[str] = mapped_column(String(16), nullable=False)
    #: Slot label exactly as published, e.g. "08:30-10:00". From the column axis.
    #:
    #: This is the occupancy key and is compared with ``==``. It is a lattice
    #: coordinate, not a time. Never replace this test with interval arithmetic.
    time_slot: Mapped[str] = mapped_column(String(32), nullable=False)

    # --- what and where ------------------------------------------------------
    room: Mapped[str] = mapped_column(String(64), nullable=False)
    room_type: Mapped[str] = mapped_column(String(32), default="Theory", nullable=False)

    #: The source token, kept fused: "CSE414(62_E1)". Never split destructively.
    course_code: Mapped[str] = mapped_column(String(64), nullable=False)
    course_title: Mapped[str | None] = mapped_column(String(255))
    #: Teacher initial, or "TBA" when unassigned.
    teacher: Mapped[str] = mapped_column(String(16), nullable=False)

    #: Derived from course_code: "62_E" from "CSE414(62_E1)".
    batch: Mapped[str] = mapped_column(String(32), nullable=False)
    #: Full section including any lab subsection: "62_E1".
    section: Mapped[str] = mapped_column(String(32), nullable=False)
    #: True when the section carries a subsection suffix (a split lab group).
    is_lab: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    #: True for elective courses (code prefixed "TCSE").
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # --- derived, for display and sorting ONLY -------------------------------
    #: Minutes past midnight. Exists so the client can sort, render, and answer
    #: "what is on right now". It must never become the occupancy test.
    start_min: Mapped[int] = mapped_column(Integer, nullable=False)
    end_min: Mapped[int] = mapped_column(Integer, nullable=False)

    routine: Mapped[Routine] = relationship(back_populates="sessions")

    def __repr__(self) -> str:
        return f"<ClassSession {self.day} {self.time_slot} {self.room} {self.course_code}>"

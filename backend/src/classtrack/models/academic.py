"""Semester and academic calendar.

Instance generation walks a semester's date range and skips anything the
calendar blocks, so a holiday never produces a monitoring record.
"""

from __future__ import annotations

import enum
from datetime import date

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from classtrack.db.base import Base, TimestampMixin


class DayKind(str, enum.Enum):
    HOLIDAY = "HOLIDAY"
    EXAM = "EXAM"
    CLOSED = "CLOSED"
    #: An extra teaching day. Does not block generation.
    SPECIAL = "SPECIAL"


#: Kinds that stop a class instance being generated.
BLOCKING_KINDS = (DayKind.HOLIDAY, DayKind.EXAM, DayKind.CLOSED)


class Semester(Base, TimestampMixin):
    __tablename__ = "semester"
    __table_args__ = (Index("ix_semester_department_active", "department", "is_active"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    department: Mapped[str] = mapped_column(String(16), default="cse", nullable=False)
    routine_id: Mapped[int | None] = mapped_column(
        ForeignKey("routine.id", ondelete="SET NULL")
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    holidays: Mapped[list[Holiday]] = relationship(
        back_populates="semester", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<Semester {self.name}{' active' if self.is_active else ''}>"


class Holiday(Base, TimestampMixin):
    __tablename__ = "holiday"
    __table_args__ = (
        UniqueConstraint("semester_id", "date", name="uq_holiday_semester_date"),
        Index("ix_holiday_date", "date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    semester_id: Mapped[int] = mapped_column(
        ForeignKey("semester.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[DayKind] = mapped_column(
        Enum(DayKind, native_enum=False), default=DayKind.HOLIDAY, nullable=False
    )

    semester: Mapped[Semester] = relationship(back_populates="holidays")

    @property
    def blocks_classes(self) -> bool:
        return self.kind in BLOCKING_KINDS

    def __repr__(self) -> str:
        return f"<Holiday {self.date} {self.title!r}>"

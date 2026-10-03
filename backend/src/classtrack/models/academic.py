"""Semester and academic calendar.

Instance generation walks a semester's date range and skips anything the
calendar blocks, so a holiday never produces a monitoring record.

A semester runs like the university's: classes begin, the mid-term exams
interrupt them, classes resume, and teaching ends when the final exams begin.
No routine class is held in either exam period, and the two exams split the
semester into the two terms it is reported on separately (see ``Term``).
"""

from __future__ import annotations

import enum
from datetime import date, timedelta

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


class Term(str, enum.Enum):
    """A stretch of a semester that is reported on by itself."""

    #: From the first class to the mid-term exams.
    MID = "MID"
    #: From the end of the mid-term exams to the final exams.
    FINAL = "FINAL"
    #: The whole semester.
    FULL = "FULL"


TERM_LABELS = {
    Term.MID: "Till mid-term",
    Term.FINAL: "Mid-term to final",
    Term.FULL: "Full semester",
}


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
    #: The semester the department is running now. Exactly one per department;
    #: a routine, a calendar day or a makeup with no semester named joins it.
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    #: The mid-term exam period, inclusive. Null until the dates are announced.
    mid_exam_start: Mapped[date | None] = mapped_column(Date)
    mid_exam_end: Mapped[date | None] = mapped_column(Date)
    #: First day of the final exams. Teaching ends the day before, and the exams
    #: run to ``end_date``.
    final_exam_start: Mapped[date | None] = mapped_column(Date)

    holidays: Mapped[list[Holiday]] = relationship(
        back_populates="semester", cascade="all, delete-orphan", passive_deletes=True
    )

    @property
    def teaching_end(self) -> date:
        """The last day a class can be held: the eve of the final exams."""
        if self.final_exam_start is not None:
            return self.final_exam_start - timedelta(days=1)
        return self.end_date

    def in_exams(self, on: date) -> bool:
        """Whether ``on`` falls in the mid-term or the final exams."""
        if (
            self.mid_exam_start is not None
            and self.mid_exam_end is not None
            and self.mid_exam_start <= on <= self.mid_exam_end
        ):
            return True
        return self.final_exam_start is not None and self.final_exam_start <= on <= self.end_date

    def term_range(self, term: Term) -> tuple[date, date] | None:
        """The dates a term covers, or None while the exam dates it needs are unset."""
        if term is Term.MID:
            if self.mid_exam_start is None:
                return None
            return self.start_date, self.mid_exam_start - timedelta(days=1)
        if term is Term.FINAL:
            if self.mid_exam_end is None:
                return None
            return self.mid_exam_end + timedelta(days=1), self.teaching_end
        return self.start_date, self.end_date

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

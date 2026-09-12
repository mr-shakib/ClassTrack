"""Faculty directory.

Sourced separately from the routine. Joined on the initial purely for display:
the routine itself already carries the initial, so no lookup is needed to answer
a teacher query.
"""

from __future__ import annotations

from sqlalchemy import Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from classtrack.db.base import Base, TimestampMixin


class Teacher(Base, TimestampMixin):
    __tablename__ = "teacher"
    __table_args__ = (Index("ix_teacher_department", "department"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    #: Uppercase initial as it appears in the routine, e.g. "SRH". Unique key.
    initial: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    designation: Mapped[str | None] = mapped_column(String(255))
    department: Mapped[str | None] = mapped_column(String(64))
    office_room: Mapped[str | None] = mapped_column(String(64))
    image_url: Mapped[str | None] = mapped_column(String(512))

    def __repr__(self) -> str:
        return f"<Teacher {self.initial} {self.name!r}>"

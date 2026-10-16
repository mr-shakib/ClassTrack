"""What students are told: notices to their sections.

Students have no accounts. A student names the groups they sit in -- a section,
its lab group, any retake groups -- and reads what was written to those groups,
and their phone follows the matching push topics. A group is written as a
*token* (``services/student_service.py``):

* ``*``            -- every student of the department.
* ``63``           -- an intake: every section of batch 63.
* ``63_A``         -- a section; ``63_A1`` one of its lab groups.
* ``CSE447:RE_A``  -- a retake group, which is only a group within its course.

A notice is written by an admin, by a teacher to their own sections, or by the
system when one of a section's classes changes: a makeup is booked, an extra
class added, a class cancelled.
"""

from __future__ import annotations

import enum

from sqlalchemy import Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from classtrack.db.base import Base, TimestampMixin


class NoticeKind(str, enum.Enum):
    #: Written by an admin.
    ANNOUNCEMENT = "ANNOUNCEMENT"
    #: Written by a teacher to their own sections, perhaps about one class.
    TEACHER = "TEACHER"
    #: Written by the system: one of the section's classes changed.
    CHANGE = "CHANGE"


class StudentNotice(Base, TimestampMixin):
    __tablename__ = "student_notice"
    __table_args__ = (Index("ix_student_notice_instance", "instance_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[NoticeKind] = mapped_column(Enum(NoticeKind, native_enum=False), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    #: Who wrote it, as students see it: "Department of CSE", or the teacher.
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"))
    #: The class it is about, if one: a teacher's note on it, or its change.
    instance_id: Mapped[int | None] = mapped_column(
        ForeignKey("class_instance.id", ondelete="SET NULL")
    )

    targets: Mapped[list[StudentNoticeTarget]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, lazy="selectin"
    )

    @property
    def tokens(self) -> list[str]:
        return [t.token for t in self.targets]

    def __repr__(self) -> str:
        return f"<StudentNotice {self.kind.value} {self.title!r}>"


class StudentNoticeTarget(Base):
    """One group a notice is for. A student reads every notice to any of theirs."""

    __tablename__ = "student_notice_target"
    __table_args__ = (Index("ix_student_notice_target_token", "token", "notice_id"),)

    notice_id: Mapped[int] = mapped_column(
        ForeignKey("student_notice.id", ondelete="CASCADE"), primary_key=True
    )
    token: Mapped[str] = mapped_column(String(48), primary_key=True)

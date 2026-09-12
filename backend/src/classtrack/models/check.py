"""A staff member's monitoring submission for one class instance.

One check per instance, enforced by a unique constraint. That is what makes
submission safe to retry over a flaky mobile connection: the service upserts on
``instance_id``, so a double tap or a retry can never create two records.
"""

from __future__ import annotations

import enum
from datetime import datetime, time

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from classtrack.db.base import Base, TimestampMixin


class CheckOutcome(str, enum.Enum):
    """What the staff member physically observed.

    Note the deliberate gap: ``TEACHER_NOT_FOUND`` is an *observation*, not a
    status. It becomes ``MISSED`` only once the threshold elapses (BR-05). No
    outcome ever produces ``NOT_CHECKED`` -- that status means this record does
    not exist (BR-06).
    """

    RUNNING = "RUNNING"
    LATE = "LATE"
    TEACHER_NOT_FOUND = "TEACHER_NOT_FOUND"


class CheckRecord(Base, TimestampMixin):
    __tablename__ = "check_record"
    __table_args__ = (
        UniqueConstraint("instance_id", name="uq_check_record_instance_id"),
        Index("ix_check_user_date", "checked_by_id", "checked_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instance_id: Mapped[int] = mapped_column(
        ForeignKey("class_instance.id", ondelete="CASCADE"), nullable=False
    )
    checked_by_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="RESTRICT"), nullable=False
    )

    outcome: Mapped[CheckOutcome] = mapped_column(
        Enum(CheckOutcome, native_enum=False), nullable=False
    )
    #: Required when ``outcome`` is LATE.
    arrival_time: Mapped[time | None] = mapped_column(Time)
    #: Computed server-side from arrival minus scheduled start (BR-04). A
    #: client-supplied value is ignored.
    late_minutes: Mapped[int | None] = mapped_column(Integer)
    remark: Mapped[str | None] = mapped_column(Text)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    instance: Mapped[ClassInstance] = relationship(back_populates="check")

    def __repr__(self) -> str:
        return f"<CheckRecord instance={self.instance_id} {self.outcome.value}>"


from classtrack.models.instance import ClassInstance  # noqa: E402

"""Makeup classes, and the online-approval workflow.

Every makeup permanently references the missed class it recovers (BR-13), so the
final record can show the sequence Missed -> Makeup Scheduled -> Makeup Completed.
"""

from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from classtrack.db.base import Base, TimestampMixin


class MakeupMode(str, enum.Enum):
    PHYSICAL = "PHYSICAL"
    ONLINE = "ONLINE"


class MakeupStatus(str, enum.Enum):
    #: Physical makeup, approved and already in the checking schedule.
    SCHEDULED = "SCHEDULED"
    #: Awaiting an HoD decision. Both modes start here (BR-11).
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"


class MakeupClass(Base, TimestampMixin):
    __tablename__ = "makeup_class"
    __table_args__ = (
        Index("ix_makeup_status", "status"),
        Index("ix_makeup_teacher", "teacher_initial"),
        Index("ix_makeup_original", "original_instance_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    #: BR-13: non-null, so a makeup can never be orphaned from its missed class.
    original_instance_id: Mapped[int] = mapped_column(
        ForeignKey("class_instance.id", ondelete="CASCADE"), nullable=False
    )
    teacher_initial: Mapped[str] = mapped_column(String(16), nullable=False)

    mode: Mapped[MakeupMode] = mapped_column(Enum(MakeupMode, native_enum=False), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    #: Must be a canonical lattice slot label.
    time_slot: Mapped[str] = mapped_column(String(32), nullable=False)
    #: Null when the mode is ONLINE.
    room: Mapped[str | None] = mapped_column(String(64))
    reason: Mapped[str | None] = mapped_column(Text)

    status: Mapped[MakeupStatus] = mapped_column(
        Enum(MakeupStatus, native_enum=False), nullable=False
    )

    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"))
    decision_note: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    #: The monitoring instance this makeup produced. For PHYSICAL it is created
    #: immediately; for ONLINE only once approved.
    created_instance_id: Mapped[int | None] = mapped_column(
        ForeignKey("class_instance.id", ondelete="SET NULL")
    )

    def __repr__(self) -> str:
        return f"<MakeupClass {self.mode.value} {self.date} {self.time_slot} {self.status.value}>"

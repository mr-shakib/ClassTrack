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
from classtrack.routine.lattice import slot_bounds


class MakeupMode(str, enum.Enum):
    PHYSICAL = "PHYSICAL"
    ONLINE = "ONLINE"


class MakeupStatus(str, enum.Enum):
    #: In-room makeup, holding its room and already in the checking schedule.
    #: An in-room reschedule starts here: an empty room needs no approval.
    SCHEDULED = "SCHEDULED"
    #: Awaiting an HoD decision. Only an online makeup starts here (BR-11).
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
    #: A canonical lattice slot label, or -- for an online class held at a time
    #: the teacher chose -- a plain 24-hour ``"HH:MM-HH:MM"`` label.
    time_slot: Mapped[str] = mapped_column(String(32), nullable=False)
    #: Set only for an online class off the lattice, where ``time_slot`` is a
    #: label rather than a grid coordinate and cannot be read back through
    #: ``slot_bounds``. Null means: this is a lattice slot, ask the lattice.
    #: Always read both through ``makeup_service.bounds()``, never directly.
    start_min: Mapped[int | None] = mapped_column(Integer)
    end_min: Mapped[int | None] = mapped_column(Integer)
    #: Null when the mode is ONLINE.
    room: Mapped[str | None] = mapped_column(String(64))
    reason: Mapped[str | None] = mapped_column(Text)

    status: Mapped[MakeupStatus] = mapped_column(
        Enum(MakeupStatus, native_enum=False), nullable=False
    )

    def bounds(self) -> tuple[int, int]:
        """When this makeup runs, in minutes past midnight.

        An online class the teacher timed themselves carries its own bounds,
        because its ``time_slot`` is a label the lattice knows nothing about.
        Every other makeup sits in a cell, and the lattice owns those. Read the
        two fields through here and never separately.
        """
        if self.start_min is not None and self.end_min is not None:
            return self.start_min, self.end_min
        return slot_bounds(self.time_slot)

    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"))
    decision_note: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    #: The monitoring instance this makeup produced. For PHYSICAL it is created
    #: immediately; for ONLINE only once approved.
    created_instance_id: Mapped[int | None] = mapped_column(
        ForeignKey("class_instance.id", ondelete="SET NULL")
    )

    #: ONLINE only: the Drive link the teacher submits after holding the class.
    #: Nothing else shows an online class took place, so completion requires it.
    drive_link: Mapped[str | None] = mapped_column(String(1024))
    completed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: Set when the sweep reminds the teacher to mark a held class done, so the
    #: reminder goes out once rather than on every pass.
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<MakeupClass {self.mode.value} {self.date} {self.time_slot} {self.status.value}>"

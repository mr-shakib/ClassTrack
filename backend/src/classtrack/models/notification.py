"""In-app notifications.

Delivery is abstracted behind ``NotificationChannel`` in the service layer so an
email or SMS channel is an addition, not a rewrite (SRS 2.2).
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from classtrack.db.base import Base, TimestampMixin


class NotificationKind(str, enum.Enum):
    #: Staff recorded the teacher as absent or late, before the sweep decides.
    CLASS_REPORTED = "CLASS_REPORTED"
    MISSED_CLASS = "MISSED_CLASS"
    #: An in-room reschedule, which books itself and needs no decision.
    MAKEUP_SCHEDULED = "MAKEUP_SCHEDULED"
    #: An HoD's answer to a reschedule request.
    MAKEUP_DECISION = "MAKEUP_DECISION"
    #: No longer written: an in-room reschedule once needed an HoD's approval,
    #: and rows from then still read back through this kind.
    MAKEUP_REQUEST = "MAKEUP_REQUEST"
    MAKEUP_REMINDER = "MAKEUP_REMINDER"
    ONLINE_REQUEST = "ONLINE_REQUEST"
    ONLINE_DECISION = "ONLINE_DECISION"
    DISPUTE_RAISED = "DISPUTE_RAISED"


class Notification(Base, TimestampMixin):
    __tablename__ = "notification"
    __table_args__ = (Index("ix_notification_user_unread", "user_id", "read_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[NotificationKind] = mapped_column(
        Enum(NotificationKind, native_enum=False), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    #: Where the UI should send the user, e.g. "/teacher".
    link: Mapped[str | None] = mapped_column(String(255))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<Notification {self.kind.value} user={self.user_id}>"

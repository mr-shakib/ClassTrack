"""Phones that receive push notifications.

The mobile app registers its Firebase token when someone signs in, and drops it
when they sign out. A token belongs to one phone, so it names one account: when
someone else signs in on that phone, the token moves to them.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from classtrack.db.base import Base, TimestampMixin


class PushDevice(Base, TimestampMixin):
    __tablename__ = "push_device"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: The Firebase Cloud Messaging registration token.
    token: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    #: "android" or "ios", for the logs.
    platform: Mapped[str] = mapped_column(String(16), nullable=False)

    def __repr__(self) -> str:
        return f"<PushDevice {self.platform} user={self.user_id}>"

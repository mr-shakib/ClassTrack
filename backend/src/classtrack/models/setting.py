"""Runtime-configurable monitoring rules.

Values live in the database so an HoD can change the missed threshold without a
redeploy (BR-05). ``core.config`` supplies the fallback default.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from classtrack.db.base import Base, utcnow

#: Keys the admin UI exposes, with their defaults.
SETTING_DEFAULTS: dict[str, str] = {
    "missed_threshold_minutes": "30",
    "check_window_minutes": "30",
    "timezone": "Asia/Dhaka",
    "department": "cse",
}


class Setting(Base):
    __tablename__ = "setting"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<Setting {self.key}={self.value!r}>"

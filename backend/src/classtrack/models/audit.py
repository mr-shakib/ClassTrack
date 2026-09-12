"""Append-only audit trail (BR-15).

No update path, no delete path. ``audit_service.record()`` is the only writer and
exposes no mutation, because the source SRS requires the original monitoring
record to survive even when an admin later changes the final status -- the
``before``/``after`` pair carries that history.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from classtrack.db.base import Base, utcnow


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_entity", "entity_type", "entity_id"),
        Index("ix_audit_actor", "actor_id"),
        Index("ix_audit_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    #: Null means the system acted -- the sweep job has no user behind it.
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"))
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    before: Mapped[dict | None] = mapped_column(JSON)
    after: Mapped[dict | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} {self.entity_type}:{self.entity_id}>"

"""Which staff member covers which part of the building.

Office staff walk a floor, not a department. Assigning them zones means the
checking screen shows only the rooms they can actually reach, which is the
difference between a usable list and a scroll through sixty-five rooms.

A staff member with *no* assignment sees everything. That is deliberate: an
unassigned account should be able to work rather than be locked out, and the
admin screen says plainly when someone is unrestricted.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from classtrack.db.base import Base, TimestampMixin


class StaffZone(Base, TimestampMixin):
    __tablename__ = "staff_zone"
    __table_args__ = (
        UniqueConstraint("user_id", "zone_key", name="uq_staff_zone_user_id"),
        Index("ix_staff_zone_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    #: A key from ``services.zones`` -- "KT-3", "G1-0", or "UNZONED".
    #: Stored rather than a room list so a routine revision that adds a room on
    #: an already-assigned floor needs no re-assignment.
    zone_key: Mapped[str] = mapped_column(String(32), nullable=False)

    def __repr__(self) -> str:
        return f"<StaffZone user={self.user_id} {self.zone_key}>"

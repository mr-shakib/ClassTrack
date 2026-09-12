"""Reporting and analytics.

Every figure here is a count over ``class_instance`` for a date range, so the
same aggregation serves daily, monthly, semester and yearly reports -- the
deferred report types in SRS 2.2 are a different range, not different code.

The reports keep the six questions from the SRS separate. In particular
``missed`` counts teacher absence and ``not_checked`` counts staff failure, and
neither is ever folded into the other.
"""

from __future__ import annotations

from datetime import date as Date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from classtrack.models import (
    CheckRecord,
    ClassInstance,
    ClassStatus,
    MakeupClass,
    MakeupStatus,
    Teacher,
    User,
)
from classtrack.models.user import Role


async def _status_counts(
    session: AsyncSession,
    *,
    start: Date,
    end: Date,
    teacher_initial: str | None = None,
) -> dict[str | None, int]:
    """Count instances by status over a range."""
    query = (
        select(ClassInstance.status, func.count(ClassInstance.id))
        .where(ClassInstance.date >= start, ClassInstance.date <= end)
        .group_by(ClassInstance.status)
    )
    if teacher_initial is not None:
        query = query.where(ClassInstance.teacher_initial == teacher_initial)
    rows = (await session.execute(query)).all()
    return {(status.value if status else None): count for status, count in rows}


async def daily(session: AsyncSession, *, on: Date) -> dict[str, object]:
    """The day's monitoring summary (SRS 12.2)."""
    counts = await _status_counts(session, start=on, end=on)
    total = sum(counts.values())
    checked = await session.scalar(
        select(func.count(CheckRecord.id))
        .join(ClassInstance, CheckRecord.instance_id == ClassInstance.id)
        .where(ClassInstance.date == on)
    )
    makeup = await session.scalar(
        select(func.count(ClassInstance.id)).where(
            ClassInstance.date == on, ClassInstance.is_makeup.is_(True)
        )
    )
    return {
        "date": on,
        "total_scheduled": total,
        "total_checked": checked or 0,
        "running": counts.get(ClassStatus.RUNNING.value, 0),
        "late": counts.get(ClassStatus.LATE.value, 0),
        "missed": counts.get(ClassStatus.MISSED.value, 0),
        "not_checked": counts.get(ClassStatus.NOT_CHECKED.value, 0),
        "makeup": makeup or 0,
        "online_approved": counts.get(ClassStatus.ONLINE_APPROVED.value, 0),
        "unresolved": counts.get(None, 0),
    }


async def teacher_report(
    session: AsyncSession, *, teacher_initial: str, start: Date, end: Date
) -> dict[str, object]:
    """Teacher-wise indicators (SRS 12.1)."""
    counts = await _status_counts(
        session, start=start, end=end, teacher_initial=teacher_initial
    )
    total = sum(counts.values())

    late = counts.get(ClassStatus.LATE.value, 0)
    running = counts.get(ClassStatus.RUNNING.value, 0)
    makeup_completed = counts.get(ClassStatus.MAKEUP_COMPLETED.value, 0)

    makeup_rows = dict(
        (
            await session.execute(
                select(MakeupClass.status, func.count(MakeupClass.id))
                .where(
                    MakeupClass.teacher_initial == teacher_initial,
                    MakeupClass.date >= start,
                    MakeupClass.date <= end,
                )
                .group_by(MakeupClass.status)
            )
        ).all()
    )
    scheduled = makeup_rows.get(MakeupStatus.SCHEDULED, 0)
    approved = makeup_rows.get(MakeupStatus.APPROVED, 0)
    pending = makeup_rows.get(MakeupStatus.PENDING, 0)
    completed = makeup_rows.get(MakeupStatus.COMPLETED, 0)

    name = await session.scalar(
        select(Teacher.name).where(Teacher.initial == teacher_initial)
    )

    return {
        "teacher_initial": teacher_initial,
        "teacher_name": name,
        "range": {"from": start, "to": end},
        "total_scheduled": total,
        # "Conducted" means the class actually happened: running, late, or
        # recovered by a completed makeup.
        "conducted": running + late + makeup_completed,
        "late": late,
        "missed": counts.get(ClassStatus.MISSED.value, 0),
        # Staff failure -- reported separately, never as the teacher's absence.
        "not_checked": counts.get(ClassStatus.NOT_CHECKED.value, 0),
        "makeup_scheduled": scheduled + approved,
        "makeup_completed": completed,
        "makeup_pending": pending,
        "online_approved": approved,
        "unresolved": counts.get(None, 0),
    }


async def staff_report(
    session: AsyncSession, *, start: Date, end: Date
) -> dict[str, object]:
    """Monitoring completion per staff member (SRS 12.4).

    ``assigned`` is every instance in the range, because v1 has no room
    assignment -- all staff see all rooms. When ``User.assigned_rooms`` lands,
    this becomes a per-user filter and nothing else changes.
    """
    assigned = await session.scalar(
        select(func.count(ClassInstance.id)).where(
            ClassInstance.date >= start, ClassInstance.date <= end
        )
    ) or 0

    checked_rows = dict(
        (
            await session.execute(
                select(CheckRecord.checked_by_id, func.count(CheckRecord.id))
                .join(ClassInstance, CheckRecord.instance_id == ClassInstance.id)
                .where(ClassInstance.date >= start, ClassInstance.date <= end)
                .group_by(CheckRecord.checked_by_id)
            )
        ).all()
    )

    # Office staff only. Admins may also check, but listing them here at 0%
    # is noise -- this is the staff monitoring report (SRS 12.4).
    staff = (
        await session.scalars(select(User).where(User.role == Role.STAFF))
    ).all()

    rows = []
    for member in staff:
        checked = checked_rows.get(member.id, 0)
        rows.append(
            {
                "user_id": member.id,
                "name": member.full_name,
                "assigned": assigned,
                "checked": checked,
                # Monitoring Completion Rate = checked / assigned x 100
                "completion_rate": round(checked / assigned * 100, 1) if assigned else 0.0,
            }
        )
    rows.sort(key=lambda r: r["checked"], reverse=True)

    total_checked = sum(checked_rows.values())
    return {
        "range": {"from": start, "to": end},
        "assigned": assigned,
        "checked": total_checked,
        "not_checked": max(0, assigned - total_checked),
        "completion_rate": round(total_checked / assigned * 100, 1) if assigned else 0.0,
        "rows": rows,
    }

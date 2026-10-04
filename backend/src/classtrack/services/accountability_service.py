"""Who failed to report which class.

``NOT_CHECKED`` says a class went unmonitored. On its own that is only half the
story: the point of the floor assignments is that somebody was responsible, and
an accountability screen that cannot name them is just a list of regrets.

Responsibility is derived the same way the checking screen is filtered -- the
room's zone, matched against staff assignments -- so the two can never drift.
Two cases are kept apart on purpose:

* **unreported** -- somebody was assigned that floor and did not submit.
  A person problem.
* **unassigned** -- nobody covers that floor at all. An admin configuration
  problem, and no amount of chasing staff will fix it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from classtrack.models import (
    ClassInstance,
    ClassStatus,
    RoleKind,
    StaffZone,
    User,
)
from classtrack.services import status_engine, zones

#: How bad is one person's backlog. Thresholds are deliberately blunt: an
#: office manager needs "chase this person today", not a score.
URGENCY_CRITICAL = "CRITICAL"
URGENCY_HIGH = "HIGH"
URGENCY_MEDIUM = "MEDIUM"
URGENCY_LOW = "LOW"


@dataclass(slots=True)
class _Miss:
    instance: ClassInstance
    hours_since: float


def _urgency(today_count: int, week_count: int) -> str:
    """Rank a person's backlog.

    Today's misses dominate: a class missed this morning can still be chased
    with the teacher, one from last week cannot.
    """
    if today_count >= 5:
        return URGENCY_CRITICAL
    if today_count > 0:
        return URGENCY_HIGH
    if week_count >= 5:
        return URGENCY_MEDIUM
    return URGENCY_LOW


async def _staff_by_zone(session: AsyncSession) -> dict[str, list[User]]:
    """Which staff cover which zone."""
    rows = (await session.scalars(select(StaffZone))).all()
    if not rows:
        return {}
    users = {
        u.id: u
        for u in (
            await session.scalars(
                select(User).where(User.id.in_({r.user_id for r in rows}))
            )
        ).all()
    }
    out: dict[str, list[User]] = {}
    for row in rows:
        user = users.get(row.user_id)
        if user is not None and user.is_active:
            out.setdefault(row.zone_key, []).append(user)
    return out


def _describe(miss: _Miss) -> dict[str, object]:
    inst = miss.instance
    return {
        "instance_id": inst.id,
        "date": inst.date,
        "time_slot": inst.time_slot,
        "room": inst.room,
        "zone": zones.room_zone(inst.room).short_label,
        "course_code": inst.course_code,
        "section": inst.section,
        "teacher_initial": inst.teacher_initial,
        "hours_since": round(miss.hours_since, 1),
    }


async def unreported(
    session: AsyncSession, *, start: Date | None = None, end: Date | None = None
) -> dict[str, object]:
    """Every class nobody reported, grouped by who should have."""
    now = status_engine.now_local()
    today = now.date()
    end = end or today
    start = start or (end - timedelta(days=7))
    week_ago = today - timedelta(days=7)

    misses = (
        await session.scalars(
            select(ClassInstance)
            .where(
                ClassInstance.status == ClassStatus.NOT_CHECKED,
                ClassInstance.date >= start,
                ClassInstance.date <= end,
            )
            .order_by(ClassInstance.date.desc(), ClassInstance.start_min.desc())
        )
    ).all()

    by_zone = await _staff_by_zone(session)

    # Everyone who could be responsible, so a clean record still shows a row.
    all_staff = (
        await session.scalars(
            select(User).where(User.of_kind(RoleKind.STAFF), User.is_active.is_(True))
        )
    ).all()
    buckets: dict[int, list[_Miss]] = {u.id: [] for u in all_staff}
    people = {u.id: u for u in all_staff}
    orphans: list[_Miss] = []

    for inst in misses:
        closed = status_engine.slot_start_at(inst.date, inst.start_min)
        hours = max(0.0, (now - closed).total_seconds() / 3600)
        miss = _Miss(instance=inst, hours_since=hours)

        owners = by_zone.get(zones.zone_key(inst.room), [])
        if not owners:
            # Nobody covers this floor. Not a staff failure.
            orphans.append(miss)
            continue
        for owner in owners:
            buckets.setdefault(owner.id, []).append(miss)
            people.setdefault(owner.id, owner)

    rows = []
    for user_id, items in buckets.items():
        user = people[user_id]
        today_items = [m for m in items if m.instance.date == today]
        week_items = [m for m in items if m.instance.date >= week_ago]
        assigned = sorted(
            key for key, owners in by_zone.items() if any(o.id == user_id for o in owners)
        )
        rows.append(
            {
                "user_id": user_id,
                "name": user.full_name,
                "email": user.email,
                "zones": assigned,
                "total": len(items),
                "today": len(today_items),
                "this_week": len(week_items),
                "urgency": _urgency(len(today_items), len(week_items)),
                # Bounded: a screen is for triage, not for paging through months.
                "classes": [_describe(m) for m in items[:50]],
            }
        )

    # Worst first: today's backlog, then the week's, then the total.
    rows.sort(key=lambda r: (-int(r["today"]), -int(r["this_week"]), -int(r["total"])))

    return {
        "as_of": now,
        "range": {"from": start, "to": end},
        "summary": {
            "total": len(misses),
            "today": sum(1 for m in misses if m.date == today),
            "this_week": sum(1 for m in misses if m.date >= week_ago),
            "staff_with_misses": sum(1 for r in rows if int(r["total"]) > 0),
            "unassigned": len(orphans),
        },
        "by_staff": rows,
        # Kept separate: this is a configuration gap, not a person's failure.
        "unassigned": [_describe(m) for m in orphans[:50]],
    }

"""Reporting and analytics.

Every figure here is a count over ``class_instance`` for a date range, so one
aggregation serves the daily, monthly, semester and teacher-wise reports: they
differ in range and filter, not in code.

Each class is put in exactly one *outcome* bucket (see ``classify``). The buckets
keep the six questions from the SRS separate -- in particular ``MISSED`` counts
teacher absence and ``NOT_CHECKED`` counts staff failure, and neither is ever
folded into the other.

A rescheduled class is counted once, on the day it was held: the missed
original becomes ``RESCHEDULED`` and the makeup instance carries the conducted
class. Counting the completed status on both would credit the teacher twice.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date as Date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
from classtrack.routine.lattice import SLOT_INDEX
from classtrack.services import (
    reschedule_links,
    settings_service,
    status_engine,
    zones,
)

# --- outcome buckets ---------------------------------------------------------

#: Held, on time.
CONDUCTED = "CONDUCTED"
#: Held, late.
LATE = "LATE"
#: Teacher absent, confirmed by a check -- or an online request was refused and
#: the class is still owed.
MISSED = "MISSED"
#: Nobody submitted a check. A staff gap, never the teacher's absence.
NOT_CHECKED = "NOT_CHECKED"
#: Missed, and moved to another slot; the makeup is counted on its own day.
RESCHEDULED = "RESCHEDULED"
CANCELLED = "CANCELLED"
#: Not settled yet: upcoming, in progress, or an online makeup not yet marked done.
PENDING = "PENDING"

OUTCOMES = (CONDUCTED, LATE, MISSED, NOT_CHECKED, RESCHEDULED, CANCELLED, PENDING)

#: What an outcome is called in a report, a PDF or a CSV.
OUTCOME_LABELS = {
    CONDUCTED: "Conducted",
    LATE: "Late",
    MISSED: "Missed",
    NOT_CHECKED: "Not checked",
    RESCHEDULED: "Rescheduled",
    CANCELLED: "Cancelled",
    PENDING: "Pending",
}

_ORIGINAL_MOVED = frozenset(
    {
        ClassStatus.MAKEUP_REQUESTED,
        ClassStatus.MAKEUP_SCHEDULED,
        ClassStatus.MAKEUP_COMPLETED,
        ClassStatus.ONLINE_PENDING,
        ClassStatus.ONLINE_APPROVED,
    }
)


def classify(inst: ClassInstance, *, makeup_done: bool = False) -> str:
    """The one outcome bucket a class instance falls in.

    ``makeup_done`` says whether the makeup behind a makeup instance has been
    marked done; it only matters for an online class, whose instance keeps
    ONLINE_APPROVED after it is held.
    """
    status = inst.status
    if status is ClassStatus.RUNNING:
        return CONDUCTED
    if status is ClassStatus.LATE:
        return LATE
    if status is ClassStatus.MISSED or status is ClassStatus.ONLINE_REJECTED:
        return MISSED
    if status is ClassStatus.NOT_CHECKED:
        return NOT_CHECKED
    if status is ClassStatus.CANCELLED:
        return CANCELLED
    if inst.is_makeup:
        if status is ClassStatus.MAKEUP_COMPLETED:
            return CONDUCTED
        if status is ClassStatus.ONLINE_APPROVED and makeup_done:
            return CONDUCTED
        return PENDING
    if status in _ORIGINAL_MOVED:
        return RESCHEDULED
    return PENDING


def is_held(outcome: str) -> bool:
    return outcome in (CONDUCTED, LATE)


async def min_conducted(session: AsyncSession) -> int:
    """Classes a course-section must have held so far before it stops showing red."""
    return await settings_service.get_int(session, "min_conducted_classes")


# --- tallies -------------------------------------------------------------------


@dataclass
class Tally:
    """Counts per outcome, plus the few derived figures every table shows."""

    counts: dict[str, int] = field(default_factory=lambda: dict.fromkeys(OUTCOMES, 0))
    #: Routine classes, excluding makeups.
    scheduled: int = 0
    makeup_held: int = 0
    late_minutes: int = 0

    def add(self, inst: ClassInstance, outcome: str, late_minutes: int | None) -> None:
        self.counts[outcome] += 1
        if not inst.is_makeup:
            self.scheduled += 1
        elif is_held(outcome):
            self.makeup_held += 1
        if outcome == LATE and late_minutes:
            self.late_minutes += late_minutes

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    @property
    def held(self) -> int:
        return self.counts[CONDUCTED] + self.counts[LATE]

    def as_dict(self) -> dict[str, object]:
        c = self.counts
        # Only classes with evidence either way: held, or confirmed missed. A
        # not-checked class is a staff gap and says nothing about the teacher, and
        # a rescheduled one is counted through its makeup, not twice.
        decided = self.held + c[MISSED]
        return {
            "total": self.total,
            "scheduled": self.scheduled,
            "held": self.held,
            "conducted": c[CONDUCTED],
            "late": c[LATE],
            "missed": c[MISSED],
            "not_checked": c[NOT_CHECKED],
            "rescheduled": c[RESCHEDULED],
            "cancelled": c[CANCELLED],
            "pending": c[PENDING],
            "makeup_held": self.makeup_held,
            "conduct_rate": round(self.held / decided * 100, 1) if decided else 0.0,
            "avg_late_minutes": round(self.late_minutes / c[LATE], 1) if c[LATE] else 0.0,
        }


@dataclass
class Row:
    """One class instance with the context every report needs, loaded once."""

    inst: ClassInstance
    outcome: str
    late_minutes: int | None
    zone_key: str
    rescheduled_from: dict | None
    rescheduled_to: dict | None


@dataclass
class Filters:
    teacher: str | None = None
    floor: str | None = None
    course: str | None = None
    section: str | None = None
    slot: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "teacher": self.teacher,
            "floor": self.floor,
            "course": self.course,
            "section": self.section,
            "slot": self.slot,
        }


async def load_rows(
    session: AsyncSession,
    *,
    start: Date,
    end: Date,
    filters: Filters | None = None,
) -> list[Row]:
    """Every instance in the range that passes the filters, classified."""
    filters = filters or Filters()
    query = (
        select(ClassInstance)
        .where(ClassInstance.date >= start, ClassInstance.date <= end)
        .options(selectinload(ClassInstance.check))
        .order_by(ClassInstance.date, ClassInstance.start_min, ClassInstance.room)
    )
    if filters.teacher:
        query = query.where(ClassInstance.teacher_initial == filters.teacher.upper())
    if filters.course:
        query = query.where(ClassInstance.course_code.ilike(f"%{filters.course.strip()}%"))
    if filters.section:
        query = query.where(ClassInstance.section.ilike(f"%{filters.section.strip()}%"))
    if filters.slot:
        query = query.where(ClassInstance.time_slot == filters.slot)

    instances = list((await session.scalars(query)).all())
    # The floor is a function of the room name, so it is filtered here rather
    # than in SQL.
    if filters.floor:
        instances = [i for i in instances if zones.zone_key(i.room) == filters.floor]

    done = await reschedule_links.completed_makeup_ids(
        session, {i.makeup_id for i in instances if i.is_makeup and i.makeup_id}
    )
    moved_from, moved_to = await reschedule_links.links_for(session, instances)

    return [
        Row(
            inst=i,
            outcome=classify(i, makeup_done=i.makeup_id in done),
            late_minutes=i.check.late_minutes if i.check else None,
            zone_key=zones.zone_key(i.room),
            rescheduled_from=moved_from.get(i.id),
            rescheduled_to=moved_to.get(i.id),
        )
        for i in instances
    ]


async def teacher_names(session: AsyncSession, initials: set[str]) -> dict[str, str]:
    if not initials:
        return {}
    rows = (await session.scalars(select(Teacher).where(Teacher.initial.in_(initials)))).all()
    return {t.initial: t.name for t in rows}


def _tally(rows: list[Row]) -> Tally:
    tally = Tally()
    for r in rows:
        tally.add(r.inst, r.outcome, r.late_minutes)
    return tally


def _group(rows: list[Row], key) -> dict[object, list[Row]]:
    groups: dict[object, list[Row]] = defaultdict(list)
    for r in rows:
        groups[key(r)].append(r)
    return groups


def _floor_rows(rows: list[Row]) -> list[dict[str, object]]:
    groups = _group(rows, lambda r: r.zone_key)
    out = []
    # zones_for_rooms orders floors like a building directory.
    for zone in zones.zones_for_rooms([r.inst.room for r in rows]):
        on_floor = groups.get(zone["key"], [])
        out.append(
            {
                "key": zone["key"],
                "label": zone["label"],
                "short_label": zone["short_label"],
                **_tally(on_floor).as_dict(),
            }
        )
    return out


def _slot_rows(rows: list[Row]) -> list[dict[str, object]]:
    groups = _group(rows, lambda r: r.inst.time_slot)
    return [
        {"time_slot": slot, **_tally(groups[slot]).as_dict()}
        for slot in sorted(groups, key=lambda s: SLOT_INDEX.get(s, 99))
    ]


def _course_rows(
    rows: list[Row], names: dict[str, str], minimum: int
) -> list[dict[str, object]]:
    """Per teacher, course and section -- the unit the minimum-classes rule applies to."""
    groups = _group(rows, lambda r: (r.inst.teacher_initial, r.inst.course_code, r.inst.section))
    out = []
    for (initial, course, section), members in groups.items():
        tally = _tally(members).as_dict()
        out.append(
            {
                "teacher_initial": initial,
                "teacher_name": names.get(initial),
                "course_code": course,
                "course_title": members[0].inst.course_title,
                "section": section,
                **tally,
                "below_minimum": tally["held"] < minimum,
            }
        )
    out.sort(key=lambda r: (r["held"], r["teacher_initial"], r["course_code"]))
    return out


def _teacher_rows(
    rows: list[Row], courses: list[dict[str, object]], names: dict[str, str]
) -> list[dict[str, object]]:
    by_teacher = _group(rows, lambda r: r.inst.teacher_initial)
    courses_by_teacher: dict[str, list[dict]] = defaultdict(list)
    for c in courses:
        courses_by_teacher[str(c["teacher_initial"])].append(c)

    out = []
    for initial, members in by_teacher.items():
        mine = courses_by_teacher.get(initial, [])
        below = [c for c in mine if c["below_minimum"]]
        out.append(
            {
                "teacher_initial": initial,
                "teacher_name": names.get(initial),
                **_tally(members).as_dict(),
                "courses": len(mine),
                "courses_below_minimum": len(below),
                "min_course_held": min((int(c["held"]) for c in mine), default=0),
                "flagged": bool(below),
            }
        )
    # Worst first: most courses short, then fewest held.
    out.sort(key=lambda r: (-r["courses_below_minimum"], r["held"], r["teacher_initial"]))
    return out


def _bucket(on: Date, granularity: str) -> Date:
    if granularity == "month":
        return on.replace(day=1)
    if granularity == "week":
        # DIU's week starts on Saturday (Friday is the weekend).
        return Date.fromordinal(on.toordinal() - (on.weekday() - 5) % 7)
    return on


def _trend(rows: list[Row], start: Date, end: Date) -> tuple[str, list[dict[str, object]]]:
    """Outcome counts over time, bucketed so a long range stays readable."""
    span = (end - start).days + 1
    granularity = "day" if span <= 45 else "week" if span <= 200 else "month"
    groups = _group(rows, lambda r: _bucket(r.inst.date, granularity))
    points = []
    for bucket in sorted(groups):
        tally = _tally(groups[bucket]).as_dict()
        points.append({"date": bucket, **tally})
    return granularity, points


def _class_row(r: Row, names: dict[str, str]) -> dict[str, object]:
    inst = r.inst
    return {
        "instance_id": inst.id,
        "date": inst.date,
        "day": inst.day,
        "time_slot": inst.time_slot,
        "room": inst.room,
        "zone": zones.room_zone(inst.room).short_label,
        "course_code": inst.course_code,
        "course_title": inst.course_title,
        "section": inst.section,
        "teacher_initial": inst.teacher_initial,
        "teacher_name": names.get(inst.teacher_initial),
        "status": status_engine.derive(inst),
        "outcome": r.outcome,
        "late_minutes": r.late_minutes,
        "remark": inst.check.remark if inst.check else None,
        "is_makeup": inst.is_makeup,
        "rescheduled_from": r.rescheduled_from,
        "rescheduled_to": r.rescheduled_to,
    }


# --- reports -------------------------------------------------------------------


async def overview(
    session: AsyncSession,
    *,
    start: Date,
    end: Date,
    filters: Filters | None = None,
) -> dict[str, object]:
    """One period, every breakdown: the monthly and semester reports (SRS 12)."""
    filters = filters or Filters()
    rows = await load_rows(session, start=start, end=end, filters=filters)
    names = await teacher_names(session, {r.inst.teacher_initial for r in rows})
    minimum = await min_conducted(session)

    courses = _course_rows(rows, names, minimum)
    granularity, trend = _trend(rows, start, end)
    return {
        "range": {"from": start, "to": end},
        "filters": filters.as_dict(),
        "min_conducted": minimum,
        "totals": _tally(rows).as_dict(),
        "granularity": granularity,
        "trend": trend,
        "by_floor": _floor_rows(rows),
        "by_slot": _slot_rows(rows),
        "by_teacher": _teacher_rows(rows, courses, names),
        "by_course": courses,
    }


async def daily(session: AsyncSession, *, on: Date) -> dict[str, object]:
    """The day's monitoring summary (SRS 12.2), floor by floor."""
    rows = await load_rows(session, start=on, end=on)
    names = await teacher_names(session, {r.inst.teacher_initial for r in rows})
    tally = _tally(rows)
    checked = sum(1 for r in rows if r.inst.check is not None)
    status_of = [r.inst.status for r in rows]

    return {
        "date": on,
        # Every class on the day, including makeups moved onto it.
        "total_scheduled": len(rows),
        "total_checked": checked,
        "running": status_of.count(ClassStatus.RUNNING),
        "late": status_of.count(ClassStatus.LATE),
        "missed": status_of.count(ClassStatus.MISSED),
        "not_checked": status_of.count(ClassStatus.NOT_CHECKED),
        "makeup": sum(1 for r in rows if r.inst.is_makeup),
        "online_approved": status_of.count(ClassStatus.ONLINE_APPROVED),
        "unresolved": status_of.count(None),
        "totals": tally.as_dict(),
        "by_floor": _floor_rows(rows),
        "by_slot": _slot_rows(rows),
        # Makeups held today for a class missed on another day.
        "rescheduled_in": [_class_row(r, names) for r in rows if r.inst.is_makeup],
    }


async def teacher_report(
    session: AsyncSession, *, teacher_initial: str, start: Date, end: Date
) -> dict[str, object]:
    """Teacher-wise indicators (SRS 12.1), with every class in the range."""
    rows = await load_rows(
        session, start=start, end=end, filters=Filters(teacher=teacher_initial)
    )
    names = await teacher_names(session, {teacher_initial})
    minimum = await min_conducted(session)
    tally = _tally(rows)
    t = tally.as_dict()

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
    courses = _course_rows(rows, names, minimum)

    return {
        "teacher_initial": teacher_initial,
        "teacher_name": names.get(teacher_initial),
        "range": {"from": start, "to": end},
        "min_conducted": minimum,
        "total_scheduled": tally.scheduled,
        # "Conducted" means the class actually happened: on time, late, or as a
        # makeup held on another day.
        "conducted": tally.held,
        "on_time": t["conducted"],
        "late": t["late"],
        "missed": t["missed"],
        # Staff failure -- reported separately, never as the teacher's absence.
        "not_checked": t["not_checked"],
        "rescheduled": t["rescheduled"],
        "cancelled": t["cancelled"],
        "makeup_scheduled": makeup_rows.get(MakeupStatus.SCHEDULED, 0)
        + makeup_rows.get(MakeupStatus.APPROVED, 0),
        "makeup_completed": makeup_rows.get(MakeupStatus.COMPLETED, 0),
        "makeup_pending": makeup_rows.get(MakeupStatus.PENDING, 0),
        "online_approved": makeup_rows.get(MakeupStatus.APPROVED, 0),
        "unresolved": t["pending"],
        "conduct_rate": t["conduct_rate"],
        "avg_late_minutes": t["avg_late_minutes"],
        "flagged": any(c["below_minimum"] for c in courses),
        "courses": courses,
        "classes": [_class_row(r, names) for r in rows],
    }


async def staff_report(
    session: AsyncSession, *, start: Date, end: Date
) -> dict[str, object]:
    """Monitoring completion per staff member (SRS 12.4).

    ``assigned`` is every instance in the range, because every staff member may
    check every room. Assigned floors only decide who answers for a class
    nobody reported -- see ``accountability_service``.
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

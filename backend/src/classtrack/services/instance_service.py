"""Materialise routine templates into dated monitoring instances (BR-01).

A ``ClassSession`` says "CSE311 is in KT-305 every Sunday at 10:00-11:30".
This turns that into one ``ClassInstance`` per applicable date, which is what
everything monitored hangs off.

Generation is idempotent: the unique key ``(session_id, date)`` makes a re-run an
upsert, so re-running after a routine revision preserves existing statuses and
check records rather than duplicating or losing them.
"""

from __future__ import annotations

import logging
from datetime import date as Date
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from classtrack.core.errors import NotFoundError, ValidationError
from classtrack.models import (
    BLOCKING_KINDS,
    ClassInstance,
    ClassSession,
    Holiday,
    Semester,
)
from classtrack.services import status_engine

logger = logging.getLogger(__name__)

#: Friday is the weekend in Bangladesh; the lattice has no Friday column.
_PY_WEEKDAY_TO_DAY = {
    5: "Saturday",
    6: "Sunday",
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: None,  # Friday
}


def day_name(day: Date) -> str | None:
    return _PY_WEEKDAY_TO_DAY[day.weekday()]


def date_range(start: Date, end: Date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


async def retire_superseded(
    session: AsyncSession, *, semester_id: int, keep_routine_id: int
) -> int:
    """Drop future classes left behind by a replaced routine.

    When a revised routine is activated, the classes it supersedes are no longer
    scheduled and must stop appearing on the checking screen -- otherwise staff
    see every remaining class twice, once per revision.

    Two things are deliberately preserved:

    * **Anything already monitored** (``status IS NOT NULL``). A checked class is
      a historical fact; a routine revision does not un-happen it.
    * **Anything in the past.** Today's partly-checked slots included, so the
      cut-off is tomorrow rather than now.

    Makeup instances have no ``session_id`` and so are never matched here --
    correctly, since a makeup is not part of any routine.
    """
    from_tomorrow = status_engine.now_local().date() + timedelta(days=1)

    stale = select(ClassInstance.id).join(
        ClassSession, ClassSession.id == ClassInstance.session_id
    ).where(
        ClassInstance.semester_id == semester_id,
        ClassInstance.status.is_(None),
        ClassInstance.date >= from_tomorrow,
        ClassSession.routine_id != keep_routine_id,
    )

    ids = list((await session.scalars(stale)).all())
    if ids:
        await session.execute(delete(ClassInstance).where(ClassInstance.id.in_(ids)))
        logger.info(
            "Retired %d future instances from superseded routines (kept %d)",
            len(ids),
            keep_routine_id,
        )
    return len(ids)


async def retire_days_off(
    session: AsyncSession, *, semester: Semester, days_off: set[Date]
) -> int:
    """Drop future classes on days that no longer hold any.

    A holiday or an exam period declared after generation, or a semester whose
    dates were moved, leaves routine classes on days that hold none. Left alone
    they would sit on the checking screen and sweep to NOT_CHECKED -- a staff
    gap that never happened. The same things are preserved as in
    ``retire_superseded``: anything monitored, anything up to today, and every
    makeup, which no calendar change undoes.
    """
    from_tomorrow = status_engine.now_local().date() + timedelta(days=1)
    rows = (
        await session.execute(
            select(ClassInstance.id, ClassInstance.date).where(
                ClassInstance.semester_id == semester.id,
                ClassInstance.session_id.is_not(None),
                ClassInstance.status.is_(None),
                ClassInstance.date >= from_tomorrow,
            )
        )
    ).all()
    ids = [
        iid
        for iid, on in rows
        if on in days_off or not semester.start_date <= on <= semester.end_date
    ]
    if ids:
        await session.execute(delete(ClassInstance).where(ClassInstance.id.in_(ids)))
        logger.info("Retired %d future instances on days that hold no class", len(ids))
    return len(ids)


async def generate(
    session: AsyncSession, *, semester_id: int | None = None
) -> dict[str, object]:
    """Generate instances for a semester's active routine.

    Returns counts rather than rows: the caller is an operator or a CLI, and the
    interesting question is "how many, and how many were skipped and why".
    """
    if semester_id is None:
        semester = await session.scalar(select(Semester).where(Semester.is_active))
        if semester is None:
            raise NotFoundError("No active semester. Create one first.")
    else:
        semester = await session.get(Semester, semester_id)
        if semester is None:
            raise NotFoundError(f"No semester with id {semester_id}")

    if semester.routine_id is None:
        raise ValidationError(
            f"Semester {semester.name!r} has no routine attached. "
            "Ingest and activate a routine first."
        )
    if semester.end_date < semester.start_date:
        raise ValidationError("Semester end date precedes its start date.")

    sessions = (
        await session.scalars(
            select(ClassSession).where(ClassSession.routine_id == semester.routine_id)
        )
    ).all()
    if not sessions:
        raise ValidationError(
            f"Routine {semester.routine_id} holds no classes. Ingest it again."
        )

    retired = await retire_superseded(
        session, semester_id=semester.id, keep_routine_id=semester.routine_id
    )

    by_day: dict[str, list[ClassSession]] = {}
    for sess in sessions:
        by_day.setdefault(sess.day, []).append(sess)

    blocked = {
        h.date
        for h in (
            await session.scalars(
                select(Holiday).where(
                    Holiday.semester_id == semester.id, Holiday.kind.in_(BLOCKING_KINDS)
                )
            )
        ).all()
    }
    exam_days = {
        d for d in date_range(semester.start_date, semester.end_date) if semester.in_exams(d)
    }
    retired_days_off = await retire_days_off(
        session, semester=semester, days_off=blocked | exam_days
    )

    # One query for what already exists, so a re-run is cheap and truly an upsert.
    existing = {
        (sid, d)
        for sid, d in (
            await session.execute(
                select(ClassInstance.session_id, ClassInstance.date).where(
                    ClassInstance.semester_id == semester.id,
                    ClassInstance.session_id.is_not(None),
                )
            )
        ).all()
    }

    rows: list[dict[str, object]] = []
    skipped_holidays = 0
    skipped_exam_days = 0
    skipped_fridays = 0

    for current in date_range(semester.start_date, semester.end_date):
        day = day_name(current)
        if day is None:
            skipped_fridays += 1
            continue
        if current in blocked:
            skipped_holidays += 1
            continue
        if current in exam_days:
            skipped_exam_days += 1
            continue
        for sess in by_day.get(day, ()):
            if (sess.id, current) in existing:
                continue
            rows.append(
                {
                    "session_id": sess.id,
                    "semester_id": semester.id,
                    "date": current,
                    "day": day,
                    "time_slot": sess.time_slot,
                    "start_min": sess.start_min,
                    "end_min": sess.end_min,
                    "room": sess.room,
                    "room_type": sess.room_type,
                    "course_code": sess.course_code,
                    "course_title": sess.course_title,
                    "section": sess.section,
                    "batch": sess.batch,
                    "teacher_initial": sess.teacher,
                    "status": None,
                    "is_makeup": False,
                }
            )

    if rows:
        # Bulk insert: ~8k rows per semester, one transaction.
        await session.run_sync(
            lambda sync_session: sync_session.bulk_insert_mappings(ClassInstance, rows)
        )

    logger.info(
        "Generated %d instances for semester %s (%d already present)",
        len(rows),
        semester.name,
        len(existing),
    )
    return {
        "semester_id": semester.id,
        "semester": semester.name,
        "routine_id": semester.routine_id,
        "instances_created": len(rows),
        "instances_existing": len(existing),
        "instances_retired": retired,
        "instances_retired_days_off": retired_days_off,
        "skipped_holidays": skipped_holidays,
        "skipped_exam_days": skipped_exam_days,
        "skipped_fridays": skipped_fridays,
    }

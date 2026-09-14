"""Derived status, and the clock arithmetic the monitoring rules depend on.

Status has two sources, kept deliberately apart:

* **Stored** -- a terminal ``ClassStatus``, written once by a check, the sweep,
  or a workflow action, and never recomputed.
* **Derived** -- while ``status IS NULL``, UPCOMING/ONGOING come from the clock.
  Nothing is persisted, so nothing can go stale.

All comparisons happen in the configured local zone (Asia/Dhaka). Stored
timestamps are UTC; this module is the only place the two meet.
"""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime, time, timedelta

from classtrack.core.config import get_settings
from classtrack.models import ClassInstance, ClassStatus, DerivedStatus

#: What the API reports for an instance: a stored status, or a derived one.
StatusValue = ClassStatus | DerivedStatus


def now_local() -> datetime:
    """Current time in the configured zone."""
    return datetime.now(get_settings().tz)


def to_local(moment: datetime) -> datetime:
    """Move a stored (UTC) timestamp into the configured zone."""
    tz = get_settings().tz
    if moment.tzinfo is None:
        # Naive values coming back from SQLite are UTC by construction.
        from datetime import UTC

        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(tz)


def minutes_to_time(minutes: int) -> time:
    """Convert minutes-past-midnight into a wall-clock time."""
    return time(hour=(minutes // 60) % 24, minute=minutes % 60)


def slot_start_at(day: Date, start_min: int) -> datetime:
    """The scheduled start of a slot, as a zone-aware local datetime."""
    return datetime.combine(day, minutes_to_time(start_min), tzinfo=get_settings().tz)


def slot_end_at(day: Date, end_min: int) -> datetime:
    return datetime.combine(day, minutes_to_time(end_min), tzinfo=get_settings().tz)


def late_minutes(start_min: int, arrival: time) -> int:
    """Minutes a teacher arrived after the scheduled start (BR-04).

    Never negative: arriving early is simply on time, not "minus five late".
    """
    arrival_min = arrival.hour * 60 + arrival.minute
    return max(0, arrival_min - start_min)


def day_ends_at(day: Date) -> datetime:
    """Midnight after ``day``: staff may report that day's classes until then (BR-06)."""
    return datetime.combine(day + timedelta(days=1), time(0, 0), tzinfo=get_settings().tz)


def derive(instance: ClassInstance, *, now: datetime | None = None) -> StatusValue:
    """The status to report for an instance.

    A stored status always wins -- it is terminal and was written deliberately.
    Only unresolved instances consult the clock.
    """
    if instance.status is not None:
        return instance.status

    now = now or now_local()
    if now < slot_start_at(instance.date, instance.start_min):
        return DerivedStatus.UPCOMING
    # Started and still unresolved. Report ONGOING rather than inventing a
    # status here -- only the sweep may decide between MISSED and NOT_CHECKED,
    # and it needs the check record to do it.
    return DerivedStatus.ONGOING


def slot_state(day: Date, start_min: int) -> str:
    """UPCOMING before the slot starts, ONGOING until the day ends, then CLOSED."""
    now = now_local()
    if now < slot_start_at(day, start_min):
        return "UPCOMING"
    if now < day_ends_at(day):
        return "ONGOING"
    return "CLOSED"


def is_checkable(instance: ClassInstance, *, now: datetime | None = None) -> bool:
    """Whether staff may still report: from the class's start until the end of its day.

    The service layer decides whether reporting outside those hours is an error
    or an override.
    """
    now = now or now_local()
    return slot_start_at(instance.date, instance.start_min) <= now < day_ends_at(instance.date)

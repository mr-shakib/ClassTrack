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


def window_closes_at(instance: ClassInstance, window_minutes: int) -> datetime:
    """When staff lose the chance to submit a check for this instance (BR-06)."""
    return slot_start_at(instance.date, instance.start_min) + timedelta(minutes=window_minutes)


def derive(
    instance: ClassInstance, *, now: datetime | None = None, window_minutes: int | None = None
) -> StatusValue:
    """The status to report for an instance.

    A stored status always wins -- it is terminal and was written deliberately.
    Only unresolved instances consult the clock.
    """
    if instance.status is not None:
        return instance.status

    now = now or now_local()
    settings = get_settings()
    window = window_minutes if window_minutes is not None else settings.check_window_minutes

    start = slot_start_at(instance.date, instance.start_min)
    if now < start:
        return DerivedStatus.UPCOMING
    if now <= start + timedelta(minutes=window):
        return DerivedStatus.ONGOING
    # Past the window but still unresolved: the sweep has not run yet. Report
    # ONGOING rather than inventing a status here -- only the sweep may decide
    # between MISSED and NOT_CHECKED, and it needs the check record to do it.
    return DerivedStatus.ONGOING


def slot_state(day: Date, start_min: int, window_minutes: int) -> str:
    """Whether a slot is UPCOMING, ONGOING, or CLOSED for checking."""
    now = now_local()
    start = slot_start_at(day, start_min)
    if now < start:
        return "UPCOMING"
    if now <= start + timedelta(minutes=window_minutes):
        return "ONGOING"
    return "CLOSED"


def is_checkable(
    instance: ClassInstance, window_minutes: int, *, now: datetime | None = None
) -> bool:
    """Whether staff may still submit a check.

    Amending an existing check stays allowed while the window is open; the
    route layer decides whether a closed window is a hard error.
    """
    now = now or now_local()
    start = slot_start_at(instance.date, instance.start_min)
    return start <= now <= start + timedelta(minutes=window_minutes)

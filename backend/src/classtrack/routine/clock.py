"""Times that are *not* on the lattice.

Every routine class sits in a lattice cell, and occupancy there is string
equality on the slot label -- see ``lattice.py``, and do not change it.

An online makeup is the one class that escapes the grid. It occupies no room,
and no staff member ever walks past it, so the two things the lattice buys us
-- an indexed room lookup and atomic, non-overlapping cells -- buy us nothing.
A teacher may therefore hold one at any time of any day, and that freedom is
what makes interval arithmetic necessary *here* and nowhere else: two free-clock
periods really can overlap partially, so :func:`overlaps` is the only honest
test of whether a teacher is already busy.

Nothing in this module may be used to decide who is in a room. That remains the
lattice's job.
"""

from __future__ import annotations

import re

from classtrack.core.errors import ValidationError

#: How long a class runs. The lattice slots are 90 minutes, and an online class
#: is still a class, so a report counts both the same way.
CLASS_MINUTES = 90

_DAY_MINUTES = 24 * 60

#: A 24-hour wall-clock time, exactly as an ``<input type="time">`` submits it.
_HHMM = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def parse_hhmm(raw: str | None) -> int:
    """Minutes past midnight for a 24-hour ``HH:MM``.

    Strict on purpose: this is the one place a time enters the system without a
    lattice label to validate it against, so a typo has to stop here.
    """
    match = _HHMM.match((raw or "").strip())
    if match is None:
        raise ValidationError(
            "Enter the start time as a 24-hour clock time, for example 19:30.",
            detail={"start_time": raw},
        )
    return int(match.group(1)) * 60 + int(match.group(2))


def hhmm(minutes: int) -> str:
    """``1170`` -> ``"19:30"``."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def period_from_start(raw: str | None) -> tuple[str, int, int]:
    """``"19:30"`` -> ``("19:30-21:00", 1170, 1260)``.

    The class must finish on the day it starts: a period running past midnight
    would belong to two dates at once, and every screen keys a class by one.
    """
    start_min = parse_hhmm(raw)
    end_min = start_min + CLASS_MINUTES
    if end_min > _DAY_MINUTES:
        raise ValidationError(
            f"A class starting at {hhmm(start_min)} would run past midnight. "
            f"Start it at {hhmm(_DAY_MINUTES - CLASS_MINUTES)} or earlier.",
            detail={"start_time": raw},
        )
    return f"{hhmm(start_min)}-{hhmm(end_min)}", start_min, end_min


def overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    """Do two periods on the same date share any minute?

    Half-open: a class ending at 21:00 does not clash with one starting then.
    """
    return a_start < b_end and b_start < a_end

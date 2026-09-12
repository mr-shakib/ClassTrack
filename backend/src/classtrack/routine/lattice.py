"""The routine lattice: the fixed grid every class snaps to.

The DIU routine is not a free-form calendar. It is a 6 x 6 lattice -- six working
days by six fixed 90-minute slots -- and every class occupies exactly one cell.

Two consequences drive the whole system:

1. Ingestion is a *grid walk*, not layout inference.
2. Occupancy is decided by string equality on the slot label. Because slots are
   atomic, two classes can never partially overlap, so no interval arithmetic is
   needed anywhere. Keep it that way.
"""

from __future__ import annotations

from classtrack.core.errors import IngestionError

#: Working days, in display order. Friday is the weekend in Bangladesh.
DAYS: tuple[str, ...] = (
    "Saturday",
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
)

#: Canonical slot labels, in grid-column order, exactly as published.
SLOTS: tuple[str, ...] = (
    "08:30-10:00",
    "10:00-11:30",
    "11:30-01:00",
    "01:00-02:30",
    "02:30-04:00",
    "04:00-05:30",
)

DAY_INDEX = {day: i for i, day in enumerate(DAYS)}
SLOT_INDEX = {slot: i for i, slot in enumerate(SLOTS)}

#: Recognised abbreviations and casings seen in published sheets.
_DAY_ALIASES = {
    **{d.lower(): d for d in DAYS},
    **{d[:3].lower(): d for d in DAYS},
    "sat": "Saturday",
    "sun": "Sunday",
    "mon": "Monday",
    "tue": "Tuesday",
    "tues": "Tuesday",
    "wed": "Wednesday",
    "thu": "Thursday",
    "thur": "Thursday",
    "thurs": "Thursday",
}


def normalise_day(raw: str) -> str | None:
    """Map a spreadsheet day label onto a canonical day, or ``None``."""
    if not raw:
        return None
    key = raw.strip().lower().rstrip(".:")
    return _DAY_ALIASES.get(key)


def normalise_slot(raw: str) -> str | None:
    """Map a spreadsheet column header onto a canonical slot label, or ``None``.

    Tolerates the whitespace variants that survive copy-paste between revisions
    ("08:30 - 10:00", "08:30-10:00" with an en dash) but never invents a slot:
    the result is always one of :data:`SLOTS`.
    """
    if not raw:
        return None
    cleaned = raw.strip().replace("–", "-").replace("—", "-")  # noqa: RUF001
    cleaned = " ".join(cleaned.split())
    compact = cleaned.replace(" ", "")
    if compact in SLOT_INDEX:
        return compact
    # Pad single-digit hours: "8:30-10:00" -> "08:30-10:00"
    parts = compact.split("-")
    if len(parts) == 2:
        padded = "-".join(p.zfill(5) if len(p) == 4 else p for p in parts)
        if padded in SLOT_INDEX:
            return padded
    return None


def slot_bounds(slot: str) -> tuple[int, int]:
    """Return ``(start_min, end_min)`` as minutes past midnight.

    Published slots carry no AM/PM marker -- ``11:30-01:00`` crosses midday. The
    campus convention resolves it: an hour of 8 or more is morning, anything less
    is afternoon.

    These values are for display, sorting and "what is on now". They are *not*
    the occupancy test; that remains equality on the slot label.
    """
    if slot not in SLOT_INDEX:
        raise IngestionError(f"Unknown time slot {slot!r}", detail={"known": list(SLOTS)})

    def to_minutes(hhmm: str) -> int:
        hours, minutes = (int(p) for p in hhmm.split(":"))
        if hours < 8:  # 01:00 means 13:00 on this campus
            hours += 12
        return hours * 60 + minutes

    start_s, end_s = slot.split("-")
    return to_minutes(start_s), to_minutes(end_s)


def validate_lattice(days: list[str], slots: list[str]) -> None:
    """Fail the import unless the sheet's axes match the expected lattice.

    Deliberately strict. A routine that imports with a shifted or missing column
    is worse than one that refuses to import, because nothing downstream can
    detect the damage.
    """
    missing_slots = [s for s in SLOTS if s not in slots]
    unknown_slots = [s for s in slots if s not in SLOT_INDEX]
    if missing_slots or unknown_slots:
        raise IngestionError(
            "Spreadsheet time-slot columns do not match the expected lattice",
            detail={
                "expected": list(SLOTS),
                "found": slots,
                "missing": missing_slots,
                "unrecognised": unknown_slots,
            },
        )

    unknown_days = [d for d in days if d not in DAY_INDEX]
    if unknown_days:
        raise IngestionError(
            "Spreadsheet contains unrecognised day labels",
            detail={"expected": list(DAYS), "unrecognised": unknown_days},
        )
    if not days:
        raise IngestionError("Spreadsheet contains no recognisable day rows")

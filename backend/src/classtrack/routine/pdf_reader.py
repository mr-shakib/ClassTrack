"""Read the published routine PDF and yield one raw record per populated cell.

The department publishes the routine as a PDF with a real text layer and real
ruling lines -- not a scan -- so no OCR is involved. ``pdfplumber`` recovers the
table from those rules directly.

Layout of the published document::

                 08:30-10:00       10:00-11:30       ...  (6 time slots)
                 Room Course Teach Room Course Teach ...  (3 columns each)
    SATURDAY                                              <- a day header row
                 KT-201  CSE315(66_E)  AS   ...
                 KT-503  CSE322(66_B1) AAM  ...
                 (COM LAB)
    SUNDAY                                                <- next day starts
                 ...

Three properties of the real document drive the design:

* **It is one continuous table.** A day begins partway down a page and flows
  across page breaks, so days cannot be inferred from page boundaries. The
  current day is carried forward until a day-header row changes it.
* **The room repeats in all six slot columns**, so a row is six independent
  ``(room, course, teacher)`` triples rather than one room with six classes.
* **The room cell carries its type on a second line** -- ``"KT-503\\n(COM LAB)"``
  -- which is exactly the artifact left unstripped in the app we studied.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pdfplumber

from classtrack.core.errors import IngestionError
from classtrack.routine.lattice import DAYS, normalise_slot, validate_lattice
from classtrack.routine.normalizer import normalise_room, normalise_whitespace

#: Slot columns per row, each spanning Room / Course / Teacher.
SLOTS_PER_ROW = 6
COLUMNS_PER_SLOT = 3

_DAY_LOOKUP = {day.upper(): day for day in DAYS}

#: The sub-header under each slot, repeated on every continuation page.
_SUBHEADER = {"room", "course", "teacher"}

#: "Version V5" in the document header.
VERSION_RE = re.compile(r"Version\s+V?([\w.]+)", re.IGNORECASE)

#: "Effective From: Saturday 11 July, 2026"
EFFECTIVE_RE = re.compile(r"Effective\s+From:\s*(.+?)(?:\s{2,}|\s+Prepared|$)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class RawCell:
    """One populated cell, before its text is parsed."""

    day: str
    time_slot: str
    room: str
    room_type: str
    course_text: str
    teacher_text: str
    page: int


@dataclass(frozen=True, slots=True)
class DocumentInfo:
    """What the document says about itself."""

    version: str | None
    effective_from: str | None
    title: str | None


def read_pdf(path: str | Path) -> tuple[list[RawCell], DocumentInfo]:
    """Read a routine PDF and return every populated cell plus its header info."""
    with pdfplumber.open(str(path)) as pdf:
        if not pdf.pages:
            raise IngestionError("The PDF has no pages.")
        info = _read_header(pdf.pages[0].extract_text() or "")
        pages = [(n, page.extract_tables()) for n, page in enumerate(pdf.pages, start=1)]

    return parse_tables(pages), info


def parse_tables(pages: Iterable[tuple[int, list[list[list[Any]]]]]) -> list[RawCell]:
    """Turn extracted tables into raw cells.

    Kept separate from the PDF machinery so the interesting part -- carrying the
    day across page breaks, locating the slot columns, splitting a row into six
    triples -- is testable without a PDF to hand.
    """
    cells: list[RawCell] = []
    slot_columns: dict[int, str] = {}
    current_day: str | None = None
    days_seen: list[str] = []

    for page_number, tables in pages:
        for table in tables:
            for row in table:
                values = [normalise_whitespace(c or "") for c in row]

                day = _day_header(row)
                if day:
                    current_day = day
                    if day not in days_seen:
                        days_seen.append(day)
                    continue

                if _is_subheader(values):
                    continue

                found = _slot_header(values)
                if found:
                    # The header repeats on continuation pages; the columns are
                    # identical, so a later read simply confirms them.
                    slot_columns = found
                    continue

                if current_day is None or not slot_columns:
                    continue

                cells.extend(_row_cells(row, current_day, slot_columns, page_number))

    if not slot_columns:
        raise IngestionError(
            "Could not find the time-slot header row, so the document does not "
            "match the expected routine lattice.",
            detail={"expected_slots": _expected_slots()},
        )

    validate_lattice(days_seen, sorted(slot_columns.values(), key=_expected_slots().index))
    return cells


def _expected_slots() -> list[str]:
    from classtrack.routine.lattice import SLOTS

    return list(SLOTS)


def _read_header(text: str) -> DocumentInfo:
    """Pull the version and effective date out of the document's own header.

    The published PDF states both, so an operator does not have to retype them
    and cannot mistype them.
    """
    version = None
    effective = None
    title = None

    for line in text.split("\n")[:6]:
        flat = normalise_whitespace(line)
        if title is None and "routine" in flat.lower():
            title = flat
        if version is None and (m := VERSION_RE.search(flat)):
            version = m.group(1).strip()
        if effective is None and (m := EFFECTIVE_RE.search(flat)):
            effective = m.group(1).strip().rstrip(".")

    return DocumentInfo(version=version, effective_from=effective, title=title)


def _day_header(row: list[Any]) -> str | None:
    """Return the day this row announces, if it is a day-header row.

    The label can land in any column, and the match is case-sensitive on
    purpose: the header line "Effective From: Saturday 11 July" contains a
    capitalised day name that must not be mistaken for a header row.
    """
    for cell in row:
        text = normalise_whitespace(cell or "")
        if text.isupper() and text in _DAY_LOOKUP:
            return _DAY_LOOKUP[text]
    return None


def _is_subheader(values: list[str]) -> bool:
    """Whether this row is the repeated ``Room | Course | Teacher`` sub-header."""
    labels = {v.strip().lower() for v in values if v.strip()}
    return bool(labels) and labels <= _SUBHEADER


def _slot_header(values: list[str]) -> dict[int, str] | None:
    """Map slot index -> canonical slot label, if this row is the slot header."""
    columns: dict[int, str] = {}
    for index, value in enumerate(values):
        slot = normalise_slot(value)
        if slot and index % COLUMNS_PER_SLOT == 0:
            columns[index // COLUMNS_PER_SLOT] = slot
    return columns if len(columns) == SLOTS_PER_ROW else None


def _row_cells(row: list[Any], day: str, slot_columns: dict[int, str], page: int) -> list[RawCell]:
    """Split one table row into its six ``(room, course, teacher)`` triples."""
    out: list[RawCell] = []
    for slot_index, slot in slot_columns.items():
        base = slot_index * COLUMNS_PER_SLOT
        if base + 2 >= len(row):
            continue

        room_raw = row[base] or ""
        course_text = normalise_whitespace(row[base + 1] or "")
        teacher_text = normalise_whitespace(row[base + 2] or "")

        if not course_text:
            continue

        room, room_type = normalise_room(room_raw)
        if not room:
            continue

        out.append(
            RawCell(
                day=day,
                time_slot=slot,
                room=room,
                room_type=room_type,
                course_text=course_text,
                teacher_text=teacher_text,
                page=page,
            )
        )
    return out

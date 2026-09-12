"""Turn the published routine PDF into rows, and swap it in atomically.

    .pdf -> read tables -> validate lattice -> parse cells -> normalise -> swap

The swap is the important part. A new revision is written to a *new* routine row
and only becomes active once the entire import has succeeded, so a client never
observes a half-imported routine.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from classtrack.core.errors import IngestionError
from classtrack.models import ClassSession, Routine
from classtrack.routine.cell_parser import is_non_class, parse_cell
from classtrack.routine.lattice import slot_bounds
from classtrack.routine.pdf_reader import RawCell, read_pdf

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class IngestionReport:
    """What an import did, and what it could not make sense of."""

    department: str
    version: str
    cells_read: int = 0
    sessions_created: int = 0
    reserved_cells: int = 0
    skipped_cells: list[dict[str, object]] = field(default_factory=list)
    routine_id: int | None = None
    effective_from: str | None = None
    days_covered: dict[str, int] = field(default_factory=dict)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped_cells)

    def as_dict(self) -> dict[str, object]:
        return {
            "department": self.department,
            "version": self.version,
            "effective_from": self.effective_from,
            "routine_id": self.routine_id,
            "cells_read": self.cells_read,
            "sessions_created": self.sessions_created,
            "days_covered": self.days_covered,
            "reserved": self.reserved_cells,
            "skipped": self.skipped_count,
            # Bounded: a broken document must not produce an unbounded response.
            "skipped_sample": self.skipped_cells[:20],
        }


def build_sessions(cells: list[RawCell], report: IngestionReport) -> list[dict[str, object]]:
    """Parse raw cells into session dicts, recording anything unparseable.

    A cell that cannot be parsed is *reported*, not silently dropped: silent
    drops are how a routine ends up quietly missing classes.
    """
    rows: list[dict[str, object]] = []
    for cell in cells:
        # A room held as "Reserved" is deliberate, not a broken cell. Counting
        # it separately keeps the skipped list meaning "needs a human look".
        if is_non_class(cell.course_text):
            report.reserved_cells += 1
            continue

        parsed = parse_cell(cell.course_text, cell.teacher_text)
        if parsed is None:
            report.skipped_cells.append(
                {
                    "page": cell.page,
                    "day": cell.day,
                    "time_slot": cell.time_slot,
                    "room": cell.room,
                    "text": cell.course_text[:120],
                }
            )
            continue

        start_min, end_min = slot_bounds(cell.time_slot)
        rows.append(
            {
                "day": cell.day,
                "time_slot": cell.time_slot,
                "room": cell.room,
                "room_type": cell.room_type,
                "course_code": parsed.course_code,
                "course_title": None,
                "teacher": parsed.teacher,
                "batch": parsed.batch,
                "section": parsed.section,
                "is_lab": parsed.is_lab,
                "is_optional": parsed.is_optional,
                "start_min": start_min,
                "end_min": end_min,
            }
        )
    return rows


async def ingest_pdf(
    session: AsyncSession,
    path: str | Path,
    *,
    department: str = "cse",
    version: str | None = None,
    semester: str | None = None,
    activate: bool = True,
) -> IngestionReport:
    """Ingest one published routine PDF and make it the active revision.

    ``version`` is read from the document's own header ("Version V5") unless
    given explicitly, so an operator neither retypes it nor mistypes it.
    """
    department = department.strip().lower()
    if not department:
        raise IngestionError("A department is required")

    cells, info = read_pdf(path)

    resolved_version = (version or info.version or "").strip()
    if not resolved_version:
        raise IngestionError(
            "No routine version given, and none found in the document header. Pass one explicitly.",
            detail={"title": info.title},
        )

    report = IngestionReport(department=department, version=resolved_version)
    report.effective_from = info.effective_from
    report.cells_read = len(cells)
    if not cells:
        raise IngestionError(
            "No populated cells found. The document appears to hold no classes.",
            detail={"path": str(path)},
        )
    version = resolved_version

    rows = build_sessions(cells, report)
    if not rows:
        raise IngestionError(
            "No cell could be parsed into a class. The cell format is probably "
            "not what the parser expects.",
            detail={"cells_read": report.cells_read, "sample": report.skipped_cells[:5]},
        )

    counts: dict[str, int] = {}
    for row in rows:
        day = str(row["day"])
        counts[day] = counts.get(day, 0) + 1
    report.days_covered = counts

    routine = await _replace_routine(
        session,
        department=department,
        version=version,
        semester=semester,
        source_filename=Path(path).name,
        rows=rows,
    )

    if activate:
        await _activate(session, routine)

    await session.commit()

    report.routine_id = routine.id
    report.sessions_created = len(rows)
    logger.info(
        "Ingested %s v%s: %d sessions from %d cells (%d skipped)",
        department,
        version,
        report.sessions_created,
        report.cells_read,
        report.skipped_count,
    )
    return report


async def _replace_routine(
    session: AsyncSession,
    *,
    department: str,
    version: str,
    semester: str | None,
    source_filename: str,
    rows: list[dict[str, object]],
) -> Routine:
    """Create the routine row, replacing any earlier import of the same version."""
    existing = await session.scalar(
        select(Routine).where(Routine.department == department, Routine.version == version)
    )
    if existing is not None:
        # Re-ingesting a version is a correction, so the old rows must go.
        # Deleting them explicitly rather than relying on ON DELETE CASCADE keeps
        # this correct on any backend, including SQLite with foreign keys off.
        await session.execute(delete(ClassSession).where(ClassSession.routine_id == existing.id))
        await session.delete(existing)
        await session.flush()

    routine = Routine(
        department=department,
        version=version,
        semester=semester,
        source_filename=source_filename,
        is_active=False,
        published_at=datetime.now(UTC),
        session_count=len(rows),
    )
    session.add(routine)
    await session.flush()

    session.add_all([ClassSession(routine_id=routine.id, **row) for row in rows])
    await session.flush()
    return routine


async def _activate(session: AsyncSession, routine: Routine) -> None:
    """Make ``routine`` the single active revision for its department."""
    await session.execute(
        update(Routine)
        .where(Routine.department == routine.department, Routine.id != routine.id)
        .values(is_active=False)
    )
    routine.is_active = True
    await session.flush()

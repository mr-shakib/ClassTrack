"""The semester cycle.

The department runs one semester after another, as the university does. Each
has its own dates, exam periods, calendar and routine. Exactly one is *current*,
and anything created without naming a semester -- a routine activation, a
calendar day, a makeup -- joins it. A new semester can be set up ahead of time
and made current when it begins.

Semesters of a department never overlap. Every report is a range of dates, and
that is what lets a semester, or a term of one, be reported as a range.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from classtrack.core.errors import NotFoundError, ValidationError
from classtrack.models import TERM_LABELS, Routine, Semester, Term


async def current(session: AsyncSession) -> Semester | None:
    return await session.scalar(select(Semester).where(Semester.is_active))


async def get(session: AsyncSession, semester_id: int) -> Semester:
    semester = await session.get(Semester, semester_id)
    if semester is None:
        raise NotFoundError(f"No semester with id {semester_id}")
    return semester


async def validate(session: AsyncSession, semester: Semester) -> None:
    """Refuse dates out of order, or a semester overlapping another.

    Call it before adding a new semester to the session: once flushed, the
    overlap query would find the semester itself.
    """
    s = semester
    if s.end_date < s.start_date:
        raise ValidationError("The semester ends before it starts.")

    if (s.mid_exam_start is None) != (s.mid_exam_end is None):
        raise ValidationError("Give the mid-term exams both a first and a last day.")
    if s.mid_exam_start is not None and s.mid_exam_end is not None:
        if s.mid_exam_end < s.mid_exam_start:
            raise ValidationError("The mid-term exams end before they begin.")
        if not s.start_date < s.mid_exam_start or s.mid_exam_end > s.end_date:
            raise ValidationError(
                "The mid-term exams must fall inside the semester, after its first day."
            )
    if s.final_exam_start is not None:
        after = s.mid_exam_end or s.start_date
        if not after < s.final_exam_start <= s.end_date:
            raise ValidationError(
                "The final exams must begin after the mid-term exams, "
                "and no later than the semester's last day."
            )

    overlap = select(Semester).where(
        Semester.department == s.department,
        Semester.start_date <= s.end_date,
        Semester.end_date >= s.start_date,
    )
    if s.id is not None:
        overlap = overlap.where(Semester.id != s.id)
    other = await session.scalar(overlap)
    if other is not None:
        raise ValidationError(
            f"{s.name} overlaps {other.name} ({other.start_date} to {other.end_date}). "
            "Semesters must not overlap."
        )


async def make_current(session: AsyncSession, semester: Semester) -> None:
    """Switch the department to this semester, and to its routine with it.

    The routine matters beyond generation: the staff floors and the free-room
    search both read the active routine's rooms.
    """
    await session.execute(
        update(Semester)
        .where(Semester.department == semester.department, Semester.id != semester.id)
        .values(is_active=False)
    )
    semester.is_active = True
    if semester.routine_id is not None:
        await session.execute(
            update(Routine)
            .where(Routine.department == semester.department)
            .values(is_active=Routine.id == semester.routine_id)
        )


# --- terms ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Period:
    """The dates a report covers, and what to call them."""

    start: Date
    end: Date
    #: "Fall 2026 · Till mid-term". None for a plain range of dates.
    label: str | None = None
    term: Term | None = None


def terms(semester: Semester, today: Date) -> list[dict[str, object]]:
    """Each term's dates, and whether it can be reported yet."""
    out = []
    for term in Term:
        span = semester.term_range(term)
        out.append(
            {
                "term": term,
                "label": TERM_LABELS[term],
                "from": span[0] if span else None,
                "to": span[1] if span else None,
                # Unset exam dates, or a term that has not begun.
                "available": span is not None and span[0] <= today,
            }
        )
    return out


async def term_period(
    session: AsyncSession, *, semester_id: int | None, term: Term, today: Date
) -> Period:
    """A term of a semester -- the current one if none is named -- as dates.

    Like the monthly report, a term reports what has happened so far, so it
    stops at today.
    """
    if semester_id is not None:
        semester = await get(session, semester_id)
    else:
        semester = await current(session)
    if semester is None:
        raise ValidationError("No current semester. Create one first.")

    label = f"{semester.name} · {TERM_LABELS[term]}"
    span = semester.term_range(term)
    if span is None:
        raise ValidationError(
            f"{label} needs the mid-term exam dates of {semester.name}. "
            "Set them on the Semesters page."
        )
    start, end = span
    if start > today:
        raise ValidationError(f"{label} has not begun. It starts on {start:%d %B %Y}.")
    return Period(start=start, end=min(end, today), label=label, term=term)

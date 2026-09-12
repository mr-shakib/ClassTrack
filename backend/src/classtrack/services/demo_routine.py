"""Build a synthetic routine directly as rows, bypassing the PDF.

The published DIU routine is university material and is not redistributed, so
there is no PDF in this repo to ingest. This produces a routine of the same
*shape* -- real faculty initials, real room names, canonical lattice slots -- so
every downstream feature is demonstrable without one.

The PDF path itself is the vendored ``routine.pipeline`` and is unchanged from
open-routine; point ``classtrack ingest`` at a real document to use it.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from classtrack.models import ClassSession, Routine, Teacher
from classtrack.routine.lattice import DAYS, SLOTS, slot_bounds

#: Rooms in the shape the real routine uses: building-floor-number.
_THEORY_ROOMS = [f"KT-{floor}{n:02d}" for floor in (3, 4, 5) for n in range(1, 7)]
_LAB_ROOMS = ["KT-503", "KT-504", "AB4-701", "AB4-702"]

_COURSES = [
    ("CSE311", "Computer Networks"),
    ("CSE313", "Computer Networks Lab"),
    ("CSE333", "Software Engineering"),
    ("CSE341", "Microprocessors"),
    ("CSE411", "Artificial Intelligence"),
    ("CSE414", "Compiler Design"),
    ("CSE123", "Data Structures"),
    ("CSE231", "Algorithms"),
    ("CSE221", "Database Management"),
    ("CSE223", "Database Lab"),
    ("TCSE451", "Machine Learning"),
    ("CSE131", "Discrete Mathematics"),
]

_BATCHES = ["68_A", "68_B", "69_A", "69_B", "70_A", "70_B", "70_C", "71_A", "71_B", "62_E"]


async def build(
    session: AsyncSession, *, department: str = "cse", version: str = "DEMO-V1", seed: int = 7
) -> dict[str, object]:
    """Create a routine covering the full 6x6 lattice, and activate it.

    Deterministic for a given ``seed`` so a demo is reproducible.
    """
    rng = random.Random(seed)

    initials = list((await session.scalars(select(Teacher.initial).limit(40))).all())
    if not initials:
        initials = ["SRH", "SAH", "MOH", "NUR", "TCA"]

    existing = await session.scalar(
        select(Routine).where(Routine.department == department, Routine.version == version)
    )
    if existing is not None:
        await session.execute(
            delete(ClassSession).where(ClassSession.routine_id == existing.id)
        )
        await session.delete(existing)
        await session.flush()

    routine = Routine(
        department=department,
        version=version,
        semester="Fall 2026",
        source_filename="synthetic-demo",
        is_active=False,
        published_at=datetime.now(UTC),
        session_count=0,
    )
    session.add(routine)
    await session.flush()

    rows: list[ClassSession] = []
    # Walk the lattice. Each (day, slot) fills a subset of rooms, so the grid is
    # realistically sparse rather than uniformly full.
    for day in DAYS:
        for slot in SLOTS:
            start_min, end_min = slot_bounds(slot)
            occupancy = rng.sample(_THEORY_ROOMS, k=rng.randint(4, 7))
            if rng.random() < 0.4:
                occupancy.append(rng.choice(_LAB_ROOMS))

            # A teacher and a section may each appear only once per cell -- the
            # same invariant the real routine holds, and what conflict detection
            # relies on downstream.
            used_teachers: set[str] = set()
            used_sections: set[str] = set()

            for room in occupancy:
                code, title = rng.choice(_COURSES)
                batch = rng.choice(_BATCHES)
                is_lab = room in _LAB_ROOMS
                section = f"{batch}{rng.randint(1, 2)}" if is_lab else batch
                teacher = rng.choice(initials)
                if teacher in used_teachers or section in used_sections:
                    continue
                used_teachers.add(teacher)
                used_sections.add(section)

                rows.append(
                    ClassSession(
                        routine_id=routine.id,
                        day=day,
                        time_slot=slot,
                        room=room,
                        room_type="Computer Lab" if is_lab else "Theory",
                        course_code=f"{code}({section})",
                        course_title=title,
                        teacher=teacher,
                        batch=batch,
                        section=section,
                        is_lab=is_lab,
                        is_optional=code.startswith("TCSE"),
                        start_min=start_min,
                        end_min=end_min,
                    )
                )

    session.add_all(rows)
    routine.session_count = len(rows)
    await session.flush()

    await session.execute(
        update(Routine)
        .where(Routine.department == department, Routine.id != routine.id)
        .values(is_active=False)
    )
    routine.is_active = True
    await session.flush()

    per_day = dict(
        (
            await session.execute(
                select(ClassSession.day, func.count(ClassSession.id))
                .where(ClassSession.routine_id == routine.id)
                .group_by(ClassSession.day)
            )
        ).all()
    )
    return {
        "routine_id": routine.id,
        "version": version,
        "sessions_created": len(rows),
        "days_covered": per_day,
        "teachers_used": len({r.teacher for r in rows}),
        "rooms_used": len({r.room for r in rows}),
    }

"""Operational commands: seed, load faculty, ingest a routine, generate instances."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import func, select

from classtrack.core.security import hash_password
from classtrack.db.session import dispose_engine, get_sessionmaker
from classtrack.models import (
    SETTING_DEFAULTS,
    Routine,
    Semester,
    Setting,
    Teacher,
    User,
)
from classtrack.models.user import Role
from classtrack.routine.normalizer import split_name_initial

DEFAULT_PASSWORD = "classtrack"

#: Where the faculty directory might live. The installed package sits outside
#: the source tree, so a path relative to ``__file__`` only works in a checkout.
_TEACHER_FILE_CANDIDATES = (
    Path("seed/teachers.json"),                                   # cwd (/app in the image)
    Path(__file__).resolve().parents[2] / "seed" / "teachers.json",  # source checkout
    Path("/app/seed/teachers.json"),                              # image, explicit
)


def _find_teachers_file() -> Path | None:
    for candidate in _TEACHER_FILE_CANDIDATES:
        if candidate.exists():
            return candidate
    return None

#: Demo accounts. The teacher account is bound to a real initial at seed time.
_ACCOUNTS = [
    ("admin@diu.edu", "Department Admin", Role.SUPER_ADMIN, None),
    ("hod@diu.edu", "Head of Department", Role.HOD, None),
    ("staff1@diu.edu", "Office Staff One", Role.STAFF, None),
    ("staff2@diu.edu", "Office Staff Two", Role.STAFF, None),
]


async def _load_teachers(session, path: Path) -> int:
    """Load the faculty directory, keyed on the initial the routine uses."""
    records = json.loads(path.read_text())
    existing = set((await session.scalars(select(Teacher.initial))).all())
    added = 0
    for row in records:
        name, initial = split_name_initial(row.get("Name_Initial", ""))
        if not initial or initial in existing:
            continue
        session.add(
            Teacher(
                initial=initial,
                name=name,
                designation=row.get("Designation") or None,
                department="cse",
                office_room=row.get("Assigned Room Number") or None,
                image_url=row.get("Image") or None,
            )
        )
        existing.add(initial)
        added += 1
    await session.flush()
    return added


async def seed(teachers_path: Path | None = None) -> None:
    """Create settings, faculty, demo accounts and an active semester."""
    async with get_sessionmaker()() as session:
        for key, value in SETTING_DEFAULTS.items():
            if await session.get(Setting, key) is None:
                session.add(Setting(key=key, value=value))
        await session.flush()

        path = teachers_path or _find_teachers_file()
        if path is not None and path.exists():
            added = await _load_teachers(session, path)
            total = await session.scalar(select(func.count(Teacher.id)))
            print(f"  faculty:   +{added} (total {total})")
        else:
            print("  faculty:   skipped, no teachers.json found")

        # A teacher account needs a real initial or it sees an empty schedule.
        head = await session.scalar(select(Teacher).where(Teacher.initial == "SRH"))
        accounts = list(_ACCOUNTS)
        if head is not None:
            accounts.append(("teacher@diu.edu", head.name, Role.TEACHER, head.initial))

        created = 0
        for email, name, role, initial in accounts:
            if await session.scalar(select(User).where(User.email == email)):
                continue
            session.add(
                User(
                    email=email,
                    password_hash=hash_password(DEFAULT_PASSWORD),
                    full_name=name,
                    role=role,
                    teacher_initial=initial,
                )
            )
            created += 1
        await session.flush()
        print(f"  users:     +{created} (password: {DEFAULT_PASSWORD!r})")

        if not await session.scalar(select(Semester).where(Semester.is_active)):
            routine = await session.scalar(
                select(Routine).where(Routine.is_active).order_by(Routine.id.desc())
            )
            session.add(
                Semester(
                    name="Fall 2026",
                    department="cse",
                    routine_id=routine.id if routine else None,
                    start_date=date(2026, 9, 1),
                    end_date=date(2026, 12, 31),
                    is_active=True,
                )
            )
            print("  semester:  Fall 2026 (2026-09-01 .. 2026-12-31)")

        await session.commit()
    print("✅ seed complete")


async def ingest(path: str, department: str, semester: str | None, activate: bool) -> None:
    from classtrack.routine.pipeline import ingest_pdf

    async with get_sessionmaker()() as session:
        report = await ingest_pdf(
            session, path, department=department, semester=semester, activate=activate
        )
        print(json.dumps(report.as_dict(), indent=2))


async def demo_routine(version: str, seed: int) -> None:
    """Build a synthetic routine and attach it to the active semester."""
    from classtrack.services import demo_routine as builder

    async with get_sessionmaker()() as session:
        result = await builder.build(session, version=version, seed=seed)
        semester = await session.scalar(select(Semester).where(Semester.is_active))
        if semester is not None:
            semester.routine_id = int(result["routine_id"])
            result["attached_to_semester"] = semester.name
        await session.commit()
        print(json.dumps(result, indent=2))


async def demo(days: int) -> None:
    """Full demo setup: routine, instances, and a back-dated history."""
    from classtrack.services import demo_routine as builder
    from classtrack.services import demo_seed, instance_service

    async with get_sessionmaker()() as session:
        routine = await builder.build(session)
        semester = await session.scalar(select(Semester).where(Semester.is_active))
        if semester is not None:
            semester.routine_id = int(routine["routine_id"])
        await session.commit()
        print(f"  routine:   {routine['sessions_created']} sessions")

        sid = semester.id if semester else None
        gen = await instance_service.generate(session, semester_id=sid)
        await session.commit()
        print(f"  instances: {gen['instances_created']} created")

        # Cover every elapsed teaching day, otherwise dates before the window
        # sweep to NOT_CHECKED and the report looks far worse than intended.
        if days <= 0 and semester is not None:
            today = date.today()
            days = max(1, (today - semester.start_date).days + 1)
        history = await demo_seed.build(session, days=days)
        print(f"  teacher:   demo account bound to {history['demo_teacher_initial']}")
        for name, keys in (history.get("staff_floors") or {}).items():
            print(f"  floors:    {name} → {', '.join(keys) or '(none)'}")
        print(f"  checks:    {history['checks']}")
        print(f"  sweep:     {history['sweep']}")
        print(f"  makeups:   {history['makeups']}")
    print("✅ demo data ready")


async def generate(semester_id: int | None) -> None:
    from classtrack.services import instance_service

    async with get_sessionmaker()() as session:
        result = await instance_service.generate(session, semester_id=semester_id)
        await session.commit()
        print(json.dumps(result, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="classtrack")
    sub = parser.add_subparsers(dest="command", required=True)

    p_seed = sub.add_parser("seed", help="Create settings, faculty, accounts, semester")
    p_seed.add_argument("--teachers", type=Path, default=None)

    p_ing = sub.add_parser("ingest", help="Ingest a routine PDF")
    p_ing.add_argument("path")
    p_ing.add_argument("--department", default="cse")
    p_ing.add_argument("--semester", default=None)
    p_ing.add_argument("--activate", action="store_true")

    p_demo = sub.add_parser(
        "demo-routine", help="Build a synthetic routine (no PDF needed) and activate it"
    )
    p_demo.add_argument("--version", default="DEMO-V1")
    p_demo.add_argument("--seed", type=int, default=7)

    p_dem = sub.add_parser("demo", help="Full demo: routine + instances + history")
    p_dem.add_argument(
        "--days", type=int, default=0, help="0 = every elapsed day of the semester"
    )

    p_gen = sub.add_parser("generate", help="Generate class instances for a semester")
    p_gen.add_argument("--semester-id", type=int, default=None)

    args = parser.parse_args()

    async def run() -> None:
        try:
            if args.command == "seed":
                await seed(args.teachers)
            elif args.command == "ingest":
                await ingest(args.path, args.department, args.semester, args.activate)
            elif args.command == "demo-routine":
                await demo_routine(args.version, args.seed)
            elif args.command == "demo":
                await demo(args.days)
            elif args.command == "generate":
                await generate(args.semester_id)
        finally:
            await dispose_engine()

    try:
        asyncio.run(run())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

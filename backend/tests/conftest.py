"""Test fixtures: an in-memory database, seeded with the minimum to monitor."""

from __future__ import annotations

import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

os.environ.setdefault("CLASSTRACK_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("CLASSTRACK_SWEEP_INTERVAL_SECONDS", "0")

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from classtrack.core.security import hash_password
from classtrack.db.base import Base
from classtrack.models import (
    ClassInstance,
    ClassSession,
    Role,
    Routine,
    Semester,
    Teacher,
    User,
)

DHAKA = ZoneInfo("Asia/Dhaka")

#: The 10:00-11:30 lattice slot, in minutes past midnight.
SLOT = "10:00-11:30"
START_MIN = 600
END_MIN = 690


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture
async def staff(session: AsyncSession) -> User:
    user = User(
        email="staff@test.edu",
        password_hash=hash_password("x"),
        full_name="Staff",
        role=Role.STAFF,
    )
    session.add(user)
    await session.flush()
    return user


@pytest_asyncio.fixture
async def teacher_user(session: AsyncSession) -> User:
    session.add(Teacher(initial="TCA", name="Teacher A", department="cse"))
    await session.flush()
    user = User(
        email="tca@test.edu",
        password_hash=hash_password("x"),
        full_name="Teacher A",
        role=Role.TEACHER,
        teacher_initial="TCA",
    )
    session.add(user)
    await session.flush()
    return user


@pytest_asyncio.fixture
async def instance(session: AsyncSession, teacher_user: User) -> ClassInstance:
    """One unresolved CSE311 instance on 2026-09-13 at 10:00-11:30."""
    routine = Routine(department="cse", version="T1", is_active=True, session_count=1)
    session.add(routine)
    await session.flush()

    sess = ClassSession(
        routine_id=routine.id,
        day="Sunday",
        time_slot=SLOT,
        room="KT-305",
        course_code="CSE311(70_A)",
        teacher="TCA",
        batch="70_A",
        section="70_A",
        start_min=START_MIN,
        end_min=END_MIN,
    )
    semester = Semester(
        name="Fall 2026",
        routine_id=routine.id,
        start_date=date(2026, 9, 1),
        end_date=date(2026, 12, 31),
        is_active=True,
    )
    session.add_all([sess, semester])
    await session.flush()

    inst = ClassInstance(
        session_id=sess.id,
        semester_id=semester.id,
        date=date(2026, 9, 13),
        day="Sunday",
        time_slot=SLOT,
        start_min=START_MIN,
        end_min=END_MIN,
        room="KT-305",
        course_code="CSE311(70_A)",
        section="70_A",
        batch="70_A",
        teacher_initial="TCA",
        status=None,
    )
    session.add(inst)
    await session.flush()
    return inst


def at(hour: int, minute: int = 0, *, day: date = date(2026, 9, 13)) -> datetime:
    """A zone-aware local datetime on the instance's date."""
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=DHAKA)

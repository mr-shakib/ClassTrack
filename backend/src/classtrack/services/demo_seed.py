"""Back-date a realistic monitoring history, so a fresh install can be shown.

Without this the dashboard and every report are empty on day one: instances
exist but none are resolved, because nothing has been checked yet. This walks
recent dates and applies a plausible mix of outcomes through the *real* services,
so the resulting data obeys every rule the system enforces -- including the
MISSED / NOT_CHECKED split -- rather than being written straight to the tables.
"""

from __future__ import annotations

import random
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from classtrack.models import (
    CheckOutcome,
    ClassInstance,
    MakeupMode,
    Role,
    Teacher,
    User,
)
from classtrack.services import check_service, makeup_service, status_engine, sweep


async def rebind_demo_teacher(session: AsyncSession) -> str | None:
    """Point the demo teacher account at a teacher with an interesting history.

    The faculty directory has 219 names but a routine only uses a few dozen, so
    a randomly chosen account usually has an empty schedule -- which makes the
    teacher dashboard look broken when it is merely accurate. Preferring a
    teacher who has a missed class also gives the makeup flow something to act
    on, so every screen has content.
    """
    from classtrack.models import ClassStatus

    # First choice: the teacher with the most missed classes.
    pick = (
        await session.execute(
            select(ClassInstance.teacher_initial, func.count(ClassInstance.id))
            .where(ClassInstance.status == ClassStatus.MISSED)
            .group_by(ClassInstance.teacher_initial)
            .order_by(func.count(ClassInstance.id).desc())
            .limit(1)
        )
    ).first()
    if pick is None:
        # Nothing missed yet -- fall back to whoever teaches the most.
        pick = (
            await session.execute(
                select(ClassInstance.teacher_initial, func.count(ClassInstance.id))
                .group_by(ClassInstance.teacher_initial)
                .order_by(func.count(ClassInstance.id).desc())
                .limit(1)
            )
        ).first()
    if pick is None:
        return None

    initial = pick[0]
    teacher = await session.scalar(select(Teacher).where(Teacher.initial == initial))
    await session.execute(
        update(User)
        .where(User.email == "teacher@diu.edu")
        .values(teacher_initial=initial, full_name=teacher.name if teacher else initial)
    )
    return initial


async def build(session: AsyncSession, *, days: int = 10, seed: int = 11) -> dict[str, object]:
    """Apply a plausible monitoring history over the last ``days`` teaching days."""
    rng = random.Random(seed)
    today = status_engine.now_local().date()

    staff = list(
        (await session.scalars(select(User).where(User.role == Role.STAFF))).all()
    )
    admin = await session.scalar(select(User).where(User.role == Role.HOD))
    if not staff:
        return {"error": "No staff accounts. Run `classtrack seed` first."}

    counts = {"running": 0, "late": 0, "not_found": 0, "unchecked": 0}

    for offset in range(1, days + 1):
        day = today - timedelta(days=offset)
        instances = list(
            (
                await session.scalars(
                    select(ClassInstance).where(
                        ClassInstance.date == day, ClassInstance.status.is_(None)
                    )
                )
            ).all()
        )
        for inst in instances:
            roll = rng.random()
            # A realistic mix: mostly fine, a few late, a couple absent, and
            # some genuinely never checked -- which is the distinction the whole
            # system exists to make visible.
            if roll < 0.08:
                counts["unchecked"] += 1
                continue  # left for the sweep to mark NOT_CHECKED

            member = rng.choice(staff)
            start = status_engine.slot_start_at(inst.date, inst.start_min)

            if roll < 0.15:
                arrival_min = inst.start_min + rng.randint(4, 25)
                await check_service.submit(
                    session,
                    instance_id=inst.id,
                    user=member,
                    outcome=CheckOutcome.LATE,
                    arrival_time=status_engine.minutes_to_time(arrival_min),
                    now=start + timedelta(minutes=arrival_min - inst.start_min),
                )
                counts["late"] += 1
            elif roll < 0.20:
                await check_service.submit(
                    session,
                    instance_id=inst.id,
                    user=member,
                    outcome=CheckOutcome.TEACHER_NOT_FOUND,
                    now=start + timedelta(minutes=rng.randint(5, 15)),
                )
                counts["not_found"] += 1
            else:
                await check_service.submit(
                    session,
                    instance_id=inst.id,
                    user=member,
                    outcome=CheckOutcome.RUNNING,
                    now=start + timedelta(minutes=rng.randint(1, 10)),
                )
                counts["running"] += 1

        await session.commit()

    # Let the real sweep resolve everything. This is what turns the
    # TEACHER_NOT_FOUND observations into MISSED and the gaps into NOT_CHECKED.
    result = await sweep.sweep_once(session)
    await session.commit()

    initial = await rebind_demo_teacher(session)
    await session.commit()

    # One of each makeup kind, so the approval queue and the linkage are visible.
    makeups = {"physical": 0, "online": 0}
    if admin is not None and initial is not None:
        from classtrack.models import ClassStatus

        # Capture plain ids, not ORM objects. A rollback below expires any
        # instance still attached to this session, and touching an expired
        # attribute afterwards triggers sync IO inside the async context.
        missed_ids = list(
            (
                await session.scalars(
                    select(ClassInstance.id)
                    .where(
                        ClassInstance.status == ClassStatus.MISSED,
                        ClassInstance.teacher_initial == initial,
                    )
                    .limit(2)
                )
            ).all()
        )
        teacher_account = await session.scalar(
            select(User).where(User.teacher_initial == initial, User.role == Role.TEACHER)
        )
        if teacher_account is not None:
            teacher_id = teacher_account.id
            for idx, original_id in enumerate(missed_ids):
                mode = MakeupMode.PHYSICAL if idx == 0 else MakeupMode.ONLINE
                # Find a free cell rather than guessing: a conflict would raise.
                for ahead in range(3, 30):
                    target = today + timedelta(days=ahead)
                    if status_engine.now_local().date() >= target:
                        continue
                    try:
                        # Re-fetch after any rollback so the object is live.
                        account = await session.get(User, teacher_id)
                        await makeup_service.create(
                            session,
                            original_instance_id=original_id,
                            user=account,
                            mode=mode,
                            on=target,
                            time_slot="04:00-05:30",
                            room="KT-508" if mode is MakeupMode.PHYSICAL else None,
                            reason="Was on official university duty",
                        )
                    except Exception:  # a conflict just means: try the next day
                        await session.rollback()
                        continue
                    await session.commit()
                    makeups["physical" if mode is MakeupMode.PHYSICAL else "online"] += 1
                    break

    return {
        "demo_teacher_initial": initial,
        "checks": counts,
        "sweep": result,
        "makeups": makeups,
    }

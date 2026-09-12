"""The staff checking screen, and the live dashboard behind it.

Both read ``class_instance`` through a single index with no join on the hot
path, which is why room and teacher are denormalised onto every row.
"""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from classtrack.models import (
    ClassInstance,
    ClassStatus,
    MakeupClass,
    MakeupStatus,
    Teacher,
    TeacherResponse,
    User,
)
from classtrack.routine.lattice import SLOTS, slot_bounds
from classtrack.services import settings_service, status_engine, zones

#: Statuses excluded from physical room checking.
#: BR-12: an approved online makeup must not appear on the staff screen.
#: A cancelled class is not there to be checked either.
EXCLUDED_FROM_CHECKING = (
    ClassStatus.ONLINE_APPROVED,
    ClassStatus.ONLINE_PENDING,
    ClassStatus.ONLINE_REJECTED,
    ClassStatus.CANCELLED,
)


def current_slot(now: datetime | None = None) -> str:
    """The lattice slot covering this moment, or the nearest upcoming one.

    Falls back to the last slot of the day once teaching is over, so the screen
    always has something to show.
    """
    now = now or status_engine.now_local()
    minutes = now.hour * 60 + now.minute
    for slot in SLOTS:
        _start, end = slot_bounds(slot)
        if minutes <= end:
            return slot
    return SLOTS[-1]


async def _teacher_names(session: AsyncSession, initials: set[str]) -> dict[str, str]:
    if not initials:
        return {}
    rows = (
        await session.scalars(select(Teacher).where(Teacher.initial.in_(initials)))
    ).all()
    return {t.initial: t.name for t in rows}


async def checking_screen(
    session: AsyncSession,
    *,
    on: Date | None = None,
    slot: str | None = None,
    only_zones: list[str] | None = None,
) -> dict:
    """Room-wise list for one date and slot (BR-02).

    ``only_zones`` narrows the list to the floors a staff member covers.
    ``None`` means no restriction (an admin); an empty list means the caller
    covers no floors and therefore has no classes -- the two are different, and
    conflating them is how an unassigned account silently gets the whole
    department.

    Filtering happens in Python rather than SQL because one slot is at most a
    few dozen rooms, and the zone rule is a string function the database cannot
    index on.
    """
    now = status_engine.now_local()
    on = on or now.date()
    slot = slot or current_slot(now)
    start_min, end_min = slot_bounds(slot)
    window = await settings_service.check_window(session)

    instances = (
        await session.scalars(
            select(ClassInstance)
            .where(
                ClassInstance.date == on,
                ClassInstance.time_slot == slot,
                # BR-12 -- approved online makeups are not physically checked.
                ClassInstance.status.not_in(EXCLUDED_FROM_CHECKING)
                | ClassInstance.status.is_(None),
            )
            .options(selectinload(ClassInstance.check))
            .order_by(ClassInstance.room)
        )
    ).all()

    if only_zones is not None:
        allowed = set(only_zones)
        instances = [i for i in instances if zones.zone_key(i.room) in allowed]

    names = await _teacher_names(session, {i.teacher_initial for i in instances})
    checker_ids = {i.check.checked_by_id for i in instances if i.check}
    checkers: dict[int, str] = {}
    if checker_ids:
        checkers = {
            u.id: u.full_name
            for u in (await session.scalars(select(User).where(User.id.in_(checker_ids)))).all()
        }

    rooms = []
    for inst in instances:
        check = None
        if inst.check:
            check = {
                "outcome": inst.check.outcome,
                "arrival_time": inst.check.arrival_time,
                "late_minutes": inst.check.late_minutes,
                "remark": inst.check.remark,
                "checked_at": inst.check.checked_at,
                "checked_by": checkers.get(inst.check.checked_by_id),
            }
        rooms.append(
            {
                "instance_id": inst.id,
                "room": inst.room,
                "room_type": inst.room_type,
                "course_code": inst.course_code,
                "course_title": inst.course_title,
                "section": inst.section,
                "teacher_initial": inst.teacher_initial,
                "teacher_name": names.get(inst.teacher_initial),
                "scheduled_start": f"{start_min // 60:02d}:{start_min % 60:02d}",
                "scheduled_end": f"{end_min // 60:02d}:{end_min % 60:02d}",
                "is_makeup": inst.is_makeup,
                "zone": zones.room_zone(inst.room).short_label,
                "status": status_engine.derive(inst, now=now, window_minutes=window),
                "check": check,
            }
        )

    return {
        "date": on,
        "time_slot": slot,
        "slot_state": status_engine.slot_state(on, start_min, window),
        "window_closes_at": status_engine.slot_start_at(on, start_min)
        + timedelta(minutes=window),
        "zones": sorted(only_zones) if only_zones is not None else [],
        "rooms": rooms,
    }


async def dashboard(session: AsyncSession) -> dict:
    """Live departmental overview for the HoD."""
    now = status_engine.now_local()
    today = now.date()
    slot = current_slot(now)
    window = await settings_service.check_window(session)

    todays = (
        await session.scalars(
            select(ClassInstance)
            .where(ClassInstance.date == today)
            .options(selectinload(ClassInstance.check))
            .order_by(ClassInstance.start_min, ClassInstance.room)
        )
    ).all()

    in_slot = [i for i in todays if i.time_slot == slot]
    names = await _teacher_names(session, {i.teacher_initial for i in in_slot})
    checker_ids = {i.check.checked_by_id for i in in_slot if i.check}
    checkers: dict[int, str] = {}
    if checker_ids:
        checkers = {
            u.id: u.full_name
            for u in (await session.scalars(select(User).where(User.id.in_(checker_ids)))).all()
        }

    summary = {
        "scheduled_now": len(in_slot),
        "running": sum(1 for i in in_slot if i.status is ClassStatus.RUNNING),
        "late": sum(1 for i in in_slot if i.status is ClassStatus.LATE),
        "missed": sum(1 for i in in_slot if i.status is ClassStatus.MISSED),
        "not_checked": sum(1 for i in in_slot if i.status is ClassStatus.NOT_CHECKED),
        "makeup_physical": sum(1 for i in in_slot if i.is_makeup),
        "online_approved": sum(
            1 for i in in_slot if i.status is ClassStatus.ONLINE_APPROVED
        ),
    }

    rows = []
    for inst in in_slot:
        rows.append(
            {
                "instance_id": inst.id,
                "room": inst.room,
                "teacher_initial": inst.teacher_initial,
                "teacher_name": names.get(inst.teacher_initial),
                "course_code": inst.course_code,
                "section": inst.section,
                "time_slot": inst.time_slot,
                "status": status_engine.derive(inst, now=now, window_minutes=window),
                "late_minutes": inst.check.late_minutes if inst.check else None,
                "checked_by": checkers.get(inst.check.checked_by_id) if inst.check else None,
                "checked_at": (
                    status_engine.to_local(inst.check.checked_at).strftime("%H:%M")
                    if inst.check
                    else None
                ),
                "is_makeup": inst.is_makeup,
            }
        )

    pending_online = await session.scalar(
        select(func.count(MakeupClass.id)).where(MakeupClass.status == MakeupStatus.PENDING)
    )
    pending_makeup = await session.scalar(
        select(func.count(MakeupClass.id)).where(
            MakeupClass.status.in_((MakeupStatus.SCHEDULED, MakeupStatus.APPROVED))
        )
    )

    attention = {
        "missed_today": sum(1 for i in todays if i.status is ClassStatus.MISSED),
        "not_checked_today": sum(1 for i in todays if i.status is ClassStatus.NOT_CHECKED),
        "pending_online": pending_online or 0,
        "pending_makeup": pending_makeup or 0,
        "disputes": sum(
            1 for i in todays if i.teacher_response is TeacherResponse.DISPUTED
        ),
    }

    return {
        "as_of": now,
        "current_slot": slot,
        "summary": summary,
        "rows": rows,
        "attention": attention,
    }

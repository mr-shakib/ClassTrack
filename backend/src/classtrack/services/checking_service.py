"""The staff checking screen, and the live dashboard behind it.

Both read ``class_instance`` through a single index with no join on the hot
path, which is why room and teacher are denormalised onto every row.
"""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime

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
from classtrack.services import report_service, reschedule_links, status_engine, zones

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


async def _checker_names(session: AsyncSession, instances) -> dict[int, str]:
    ids = {i.check.checked_by_id for i in instances if i.check}
    if not ids:
        return {}
    return {
        u.id: u.full_name
        for u in (await session.scalars(select(User).where(User.id.in_(ids)))).all()
    }


def _hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _room_row(
    inst: ClassInstance,
    *,
    names: dict[str, str],
    checkers: dict[int, str],
    moved_from: dict[int, dict],
    now: datetime,
) -> dict:
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
    return {
        "instance_id": inst.id,
        "date": inst.date,
        "time_slot": inst.time_slot,
        "slot_state": status_engine.slot_state(inst.date, inst.start_min),
        "room": inst.room,
        "room_type": inst.room_type,
        "course_code": inst.course_code,
        "course_title": inst.course_title,
        "section": inst.section,
        "teacher_initial": inst.teacher_initial,
        "teacher_name": names.get(inst.teacher_initial),
        "scheduled_start": _hhmm(inst.start_min),
        "scheduled_end": _hhmm(inst.end_min),
        "is_makeup": inst.is_makeup,
        "is_extra": inst.is_extra,
        "rescheduled_from": moved_from.get(inst.id),
        "zone": zones.room_zone(inst.room).short_label,
        "zone_key": zones.zone_key(inst.room),
        "status": status_engine.derive(inst, now=now),
        "check": check,
    }


async def _room_rows(session: AsyncSession, instances, now: datetime) -> list[dict]:
    names = await _teacher_names(session, {i.teacher_initial for i in instances})
    checkers = await _checker_names(session, instances)
    moved_from, _moved_to = await reschedule_links.links_for(session, instances)
    return [
        _room_row(i, names=names, checkers=checkers, moved_from=moved_from, now=now)
        for i in instances
    ]


async def search_by_teacher(
    session: AsyncSession, *, teacher_initial: str, start: Date, end: Date
) -> list[dict]:
    """A teacher's checkable classes over a range, newest first.

    For correcting a past record: finding it by teacher is quicker than walking
    back through each day, slot and floor.
    """
    now = status_engine.now_local()
    instances = (
        await session.scalars(
            select(ClassInstance)
            .where(
                ClassInstance.teacher_initial == teacher_initial.upper(),
                ClassInstance.date >= start,
                ClassInstance.date <= end,
                ClassInstance.status.not_in(EXCLUDED_FROM_CHECKING)
                | ClassInstance.status.is_(None),
            )
            .options(selectinload(ClassInstance.check))
            .order_by(ClassInstance.date.desc(), ClassInstance.start_min.desc())
            .limit(300)
        )
    ).all()
    return await _room_rows(session, instances, now)


async def checking_screen(
    session: AsyncSession,
    *,
    on: Date | None = None,
    slot: str | None = None,
    my_zones: list[str] | None = None,
) -> dict:
    """Room-wise list for one date and slot (BR-02), with a summary per floor.

    Every room is returned whoever asks. ``my_zones`` -- the floors a staff
    member covers -- only orders the floor summary and marks those floors as
    theirs; it hides nothing.

    Floors are grouped in Python rather than SQL because one slot is at most a
    few dozen rooms, and the zone rule is a string function the database cannot
    index on.
    """
    now = status_engine.now_local()
    on = on or now.date()
    slot = slot or current_slot(now)
    start_min, _end_min = slot_bounds(slot)

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

    rooms = await _room_rows(session, instances, now)

    mine = set(my_zones or [])
    floors = []
    # zones_for_rooms orders the floors like a building directory.
    for zone in zones.zones_for_rooms([r["room"] for r in rooms]):
        on_floor = [r for r in rooms if r["zone_key"] == zone["key"]]
        floors.append(
            {
                "key": zone["key"],
                "label": zone["label"],
                "short_label": zone["short_label"],
                "total": len(on_floor),
                "checked": sum(1 for r in on_floor if r["check"] is not None),
                "is_mine": zone["key"] in mine,
            }
        )
    # A staff member's own floors first; the sort is stable, so each group keeps
    # directory order.
    floors.sort(key=lambda f: not f["is_mine"])

    return {
        "date": on,
        "time_slot": slot,
        "slot_state": status_engine.slot_state(on, start_min),
        # Reports stay open all day; the field keeps its name for API clients.
        "window_closes_at": status_engine.day_ends_at(on),
        "zones": sorted(mine),
        "floors": floors,
        "rooms": rooms,
    }


async def dashboard(session: AsyncSession) -> dict:
    """Live departmental overview for the HoD."""
    now = status_engine.now_local()
    today = now.date()
    slot = current_slot(now)

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
    checkers = await _checker_names(session, in_slot)
    moved_from, _moved_to = await reschedule_links.links_for(session, in_slot)

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
                "status": status_engine.derive(inst, now=now),
                "late_minutes": inst.check.late_minutes if inst.check else None,
                "checked_by": checkers.get(inst.check.checked_by_id) if inst.check else None,
                "checked_at": (
                    status_engine.to_local(inst.check.checked_at).strftime("%H:%M")
                    if inst.check
                    else None
                ),
                "is_makeup": inst.is_makeup,
                "is_extra": inst.is_extra,
                "rescheduled_from": moved_from.get(inst.id),
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


async def day_status(session: AsyncSession, *, on: Date | None = None) -> dict:
    """Every class on one day, with its status and the report bucket it falls in.

    One day is a few hundred rows at most, so the screen filters them itself --
    by teacher, floor, slot or status -- without a round trip per keystroke.
    """
    now = status_engine.now_local()
    on = on or now.date()
    instances = (
        await session.scalars(
            select(ClassInstance)
            .where(ClassInstance.date == on)
            .options(selectinload(ClassInstance.check))
            .order_by(ClassInstance.start_min, ClassInstance.room)
        )
    ).all()

    names = await _teacher_names(session, {i.teacher_initial for i in instances})
    checkers = await _checker_names(session, instances)
    moved_from, moved_to = await reschedule_links.links_for(session, instances)
    done = await reschedule_links.completed_makeup_ids(
        session, {i.makeup_id for i in instances if i.is_makeup and i.makeup_id}
    )

    rows = []
    for inst in instances:
        zone = zones.room_zone(inst.room)
        rows.append(
            {
                "instance_id": inst.id,
                "date": inst.date,
                "room": inst.room,
                "zone": zone.short_label,
                "zone_key": zone.key,
                "teacher_initial": inst.teacher_initial,
                "teacher_name": names.get(inst.teacher_initial),
                "course_code": inst.course_code,
                "course_title": inst.course_title,
                "section": inst.section,
                "time_slot": inst.time_slot,
                "start": _hhmm(inst.start_min),
                "end": _hhmm(inst.end_min),
                "status": status_engine.derive(inst, now=now),
                "outcome": report_service.classify(inst, makeup_done=inst.makeup_id in done),
                "late_minutes": inst.check.late_minutes if inst.check else None,
                "remark": inst.check.remark if inst.check else None,
                "checked_by": checkers.get(inst.check.checked_by_id) if inst.check else None,
                "checked_at": (
                    status_engine.to_local(inst.check.checked_at).strftime("%H:%M")
                    if inst.check
                    else None
                ),
                "is_makeup": inst.is_makeup,
                "is_extra": inst.is_extra,
                "rescheduled_from": moved_from.get(inst.id),
                "rescheduled_to": moved_to.get(inst.id),
            }
        )

    return {
        "date": on,
        "as_of": now,
        "current_slot": current_slot(now) if on == now.date() else None,
        "rows": rows,
    }

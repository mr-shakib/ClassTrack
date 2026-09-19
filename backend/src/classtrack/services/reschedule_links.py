"""Where a rescheduled class came from, and where a missed class went.

A physical makeup is a class instance of its own, dated the day it is held, so
it already appears in that day's lists and reports. What those lists cannot see
on their own is *why* the class is there. These lookups attach that: a makeup
instance learns the class it recovers, and a missed class learns its new slot,
so every screen can mark the two apart from the routine's own classes.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date as Date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from classtrack.models import ClassInstance, MakeupClass, MakeupStatus


def _slot_ref(on: Date, time_slot: str, room: str | None, **extra: object) -> dict:
    return {"date": on, "time_slot": time_slot, "room": room, **extra}


async def links_for(
    session: AsyncSession, instances: Iterable[ClassInstance]
) -> tuple[dict[int, dict], dict[int, dict]]:
    """Return ``(rescheduled_from, rescheduled_to)``, keyed on instance id.

    ``rescheduled_from`` covers makeup instances: the missed class each one
    recovers. ``rescheduled_to`` covers the missed classes: the latest request
    for each that was not rejected, with its mode and progress.
    """
    instances = list(instances)
    makeup_ids = {i.makeup_id for i in instances if i.is_makeup and i.makeup_id}
    original_ids = {i.id for i in instances if not i.is_makeup}

    rescheduled_from: dict[int, dict] = {}
    if makeup_ids:
        rows = (
            await session.execute(
                select(MakeupClass, ClassInstance)
                .join(ClassInstance, ClassInstance.id == MakeupClass.original_instance_id)
                .where(MakeupClass.id.in_(makeup_ids))
            )
        ).all()
        by_makeup = {
            makeup.id: _slot_ref(
                original.date,
                original.time_slot,
                original.room,
                instance_id=original.id,
                mode=makeup.mode.value,
            )
            for makeup, original in rows
        }
        for inst in instances:
            if inst.is_makeup and inst.makeup_id in by_makeup:
                rescheduled_from[inst.id] = by_makeup[inst.makeup_id]

    rescheduled_to: dict[int, dict] = {}
    if original_ids:
        makeups = (
            await session.scalars(
                select(MakeupClass)
                .where(
                    MakeupClass.original_instance_id.in_(original_ids),
                    MakeupClass.status != MakeupStatus.REJECTED,
                )
                .order_by(MakeupClass.id)
            )
        ).all()
        # Ordered by id, so a later request for the same class wins.
        for makeup in makeups:
            rescheduled_to[makeup.original_instance_id] = _slot_ref(
                makeup.date,
                makeup.time_slot,
                makeup.room,
                instance_id=makeup.created_instance_id,
                mode=makeup.mode.value,
                status=makeup.status.value,
            )

    return rescheduled_from, rescheduled_to


async def completed_makeup_ids(session: AsyncSession, makeup_ids: set[int]) -> set[int]:
    """The makeups a teacher has marked done.

    An approved online class keeps ONLINE_APPROVED on its instance after it is
    held, so whether it counts as conducted is read from the makeup itself.
    """
    if not makeup_ids:
        return set()
    return set(
        (
            await session.scalars(
                select(MakeupClass.id).where(
                    MakeupClass.id.in_(makeup_ids),
                    MakeupClass.status == MakeupStatus.COMPLETED,
                )
            )
        ).all()
    )

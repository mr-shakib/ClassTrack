"""Monitoring rules read from the database, falling back to static config.

The HoD can change the missed threshold without a redeploy (BR-05), so the
sweep and the checking service must read it here rather than from ``Settings``.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from classtrack.core.config import get_settings
from classtrack.models import SETTING_DEFAULTS, Setting


async def get_all(session: AsyncSession) -> dict[str, str]:
    rows = (await session.scalars(select(Setting))).all()
    values = dict(SETTING_DEFAULTS)
    values.update({r.key: r.value for r in rows})
    return values


async def get_int(session: AsyncSession, key: str) -> int:
    """Read an integer rule, falling back to config then to the static default."""
    row = await session.get(Setting, key)
    if row is not None:
        try:
            return int(row.value)
        except ValueError:
            pass
    fallback = getattr(get_settings(), key, None)
    if isinstance(fallback, int):
        return fallback
    return int(SETTING_DEFAULTS[key])


async def missed_threshold(session: AsyncSession) -> int:
    return await get_int(session, "missed_threshold_minutes")


async def check_window(session: AsyncSession) -> int:
    return await get_int(session, "check_window_minutes")


async def set_value(
    session: AsyncSession, key: str, value: str, *, updated_by_id: int | None = None
) -> Setting:
    row = await session.get(Setting, key)
    if row is None:
        row = Setting(key=key, value=value, updated_by_id=updated_by_id)
        session.add(row)
    else:
        row.value = value
        row.updated_by_id = updated_by_id
    return row

"""Append-only audit writer (BR-15).

This module deliberately exposes *no* update or delete path. Every critical
status change routes through ``record()``, and the ``before``/``after`` pair is
what lets an admin override be reviewed later without destroying the original
monitoring record.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from classtrack.models import AuditLog


def record(
    session: AsyncSession,
    *,
    actor_id: int | None,
    entity_type: str,
    entity_id: int,
    action: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str | None = None,
) -> AuditLog:
    """Stage an audit row. The caller owns the commit.

    ``actor_id`` is None when the system acted -- the sweep job has no user
    behind it, and recording that honestly matters for accountability.
    """
    entry = AuditLog(
        actor_id=actor_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        before=before,
        after=after,
        reason=reason,
    )
    session.add(entry)
    return entry

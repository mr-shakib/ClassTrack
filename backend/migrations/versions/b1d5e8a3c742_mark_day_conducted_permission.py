"""mark a day conducted permission

A new permission, ``checking.mark_day``: when monitoring was off for a day,
record every class nobody reported as held. The full admins hold every
permission, so they get it, and so does the Coordination Officer, who runs
monitoring day to day. Any other role is given it from the Roles tab.

Revision ID: b1d5e8a3c742
Revises: e2b8f4c6a913
Create Date: 2026-10-12 10:00:00.000000

"""
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1d5e8a3c742'
down_revision: Union[str, Sequence[str], None] = 'e2b8f4c6a913'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PERMISSION = 'checking.mark_day'
_GRANTED_TO = ('SUPER_ADMIN', 'HOD', 'ASSOCIATE_HEAD', 'COORDINATION_OFFICER')

_role = sa.table(
    'role',
    sa.column('id', sa.Integer),
    sa.column('key', sa.String),
    sa.column('permissions', sa.JSON),
    sa.column('updated_at', sa.DateTime(timezone=True)),
)


def _rewrite(change) -> None:
    bind = op.get_bind()
    now = datetime.now(timezone.utc)
    for role_id, key, permissions in bind.execute(
        sa.select(_role.c.id, _role.c.key, _role.c.permissions)
    ).all():
        held = list(permissions or [])
        updated = change(key, held)
        if updated != held:
            bind.execute(
                _role.update()
                .where(_role.c.id == role_id)
                .values(permissions=updated, updated_at=now)
            )


def upgrade() -> None:
    """Upgrade schema."""
    _rewrite(
        lambda key, held: sorted({*held, _PERMISSION}) if key in _GRANTED_TO else held
    )


def downgrade() -> None:
    """Downgrade schema."""
    _rewrite(lambda _key, held: [p for p in held if p != _PERMISSION])

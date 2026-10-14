"""send notifications permission

A new permission, ``notifications.send``: write a notification of one's own to
teachers and staff, from the Notifications tab. The full admins hold every
permission, so they get it, and so does the Coordination Officer, who runs the
department day to day. Any other role is given it from the Roles tab.

Revision ID: c7d2e5a8f134
Revises: f3a9c1e7b254
Create Date: 2026-10-14 20:00:00.000000

"""
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d2e5a8f134'
down_revision: Union[str, Sequence[str], None] = 'f3a9c1e7b254'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PERMISSION = 'notifications.send'
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

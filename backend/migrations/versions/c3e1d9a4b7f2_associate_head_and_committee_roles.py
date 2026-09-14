"""associate head and committee roles

The role is stored as a plain string sized to the longest value, so the new
ASSOCIATE_HEAD value needs a wider column. No existing row changes.

Revision ID: c3e1d9a4b7f2
Revises: 780b0745eefd
Create Date: 2026-09-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3e1d9a4b7f2'
down_revision: Union[str, Sequence[str], None] = '780b0745eefd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD = sa.Enum('SUPER_ADMIN', 'HOD', 'STAFF', 'TEACHER', name='role', native_enum=False)
_NEW = sa.Enum(
    'SUPER_ADMIN', 'HOD', 'ASSOCIATE_HEAD', 'COMMITTEE', 'STAFF', 'TEACHER',
    name='role', native_enum=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('role', existing_type=_OLD, type_=_NEW, existing_nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Remapping these accounts would silently change what someone may do, so
    # refuse instead and let an administrator decide what they should become.
    remaining = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM \"user\" WHERE role IN ('ASSOCIATE_HEAD', 'COMMITTEE')")
    )
    if remaining:
        raise RuntimeError(
            f"{remaining} account(s) still hold the ASSOCIATE_HEAD or COMMITTEE role. "
            "Reassign or remove them before downgrading."
        )
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('role', existing_type=_NEW, type_=_OLD, existing_nullable=False)

"""online makeup free clock time

Revision ID: b6d4e9f10275
Revises: f4b8c2d6e913
Create Date: 2026-09-23 01:10:00.000000

An online makeup may be held at any time of any day, so its ``time_slot`` can be
a plain "HH:MM-HH:MM" label instead of a lattice coordinate. These columns carry
the bounds such a label cannot be read back through ``slot_bounds``; they stay
null for every class that is on the lattice.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b6d4e9f10275'
down_revision: Union[str, Sequence[str], None] = 'f4b8c2d6e913'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('makeup_class', schema=None) as batch_op:
        batch_op.add_column(sa.Column('start_min', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('end_min', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('makeup_class', schema=None) as batch_op:
        batch_op.drop_column('end_min')
        batch_op.drop_column('start_min')

"""extra classes

A teacher may book an empty room for an extra class of one of their sections.
It is an ordinary class instance with no routine row behind it, marked so that
missing it asks for no reschedule. Every existing row is a routine class or a
makeup, so they all start false.

Revision ID: c9e4b7a1d368
Revises: a8f3e6c2d417
Create Date: 2026-10-04 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9e4b7a1d368'
down_revision: Union[str, Sequence[str], None] = 'a8f3e6c2d417'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('class_instance', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('is_extra', sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('class_instance', schema=None) as batch_op:
        batch_op.drop_column('is_extra')

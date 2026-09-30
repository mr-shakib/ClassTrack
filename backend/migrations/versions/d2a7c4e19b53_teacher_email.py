"""teacher email

The faculty directory gains the address absence reports are mailed to. Existing
rows stay null until the directory is reloaded with ``classtrack faculty``.

Revision ID: d2a7c4e19b53
Revises: b6d4e9f10275
Create Date: 2026-09-30 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2a7c4e19b53'
down_revision: Union[str, Sequence[str], None] = 'b6d4e9f10275'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('teacher', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email', sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('teacher', schema=None) as batch_op:
        batch_op.drop_column('email')

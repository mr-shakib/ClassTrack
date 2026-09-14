"""makeup completion and drive link

Revision ID: e7a2f5c81d34
Revises: c3e1d9a4b7f2
Create Date: 2026-09-14 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7a2f5c81d34'
down_revision: Union[str, Sequence[str], None] = 'c3e1d9a4b7f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('makeup_class', schema=None) as batch_op:
        batch_op.add_column(sa.Column('drive_link', sa.String(length=1024), nullable=True))
        batch_op.add_column(sa.Column('completed_by_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column('reminder_sent_at', sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_foreign_key(
            batch_op.f('fk_makeup_class_completed_by_id_user'),
            'user',
            ['completed_by_id'],
            ['id'],
            ondelete='SET NULL',
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('makeup_class', schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f('fk_makeup_class_completed_by_id_user'), type_='foreignkey'
        )
        batch_op.drop_column('reminder_sent_at')
        batch_op.drop_column('completed_at')
        batch_op.drop_column('completed_by_id')
        batch_op.drop_column('drive_link')

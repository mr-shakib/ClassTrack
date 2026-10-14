"""push notifications

The mobile app registers each phone's Firebase token, so notifications reach it
as pushes, and the sweep reminds a teacher shortly before each class. A class
remembers when it was reminded, so it is reminded once; every existing class
starts unreminded, and those already past are never selected.

Revision ID: f3a9c1e7b254
Revises: b1d5e8a3c742
Create Date: 2026-10-14 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a9c1e7b254'
down_revision: Union[str, Sequence[str], None] = 'b1d5e8a3c742'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'push_device',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=512), nullable=False),
        sa.Column('platform', sa.String(length=16), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['user_id'], ['user.id'],
            name=op.f('fk_push_device_user_id_user'), ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_push_device')),
        sa.UniqueConstraint('token', name=op.f('uq_push_device_token')),
    )
    op.create_index(op.f('ix_push_device_user_id'), 'push_device', ['user_id'], unique=False)

    with op.batch_alter_table('class_instance', schema=None) as batch_op:
        batch_op.add_column(sa.Column('reminded_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('class_instance', schema=None) as batch_op:
        batch_op.drop_column('reminded_at')

    op.drop_index(op.f('ix_push_device_user_id'), table_name='push_device')
    op.drop_table('push_device')

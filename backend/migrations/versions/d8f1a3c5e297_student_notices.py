"""student notices

Students read their routine without an account, by section, and are told what
changes in it. Two tables hold what they are told: a notice, and the groups it
is for (a section, a lab group, a retake group, an intake, or everyone). An
online makeup gains the link students join it by.

A new permission, ``students.message``, lets a teacher write to the students of
their own sections. The Teacher role gets it, and so do the roles that hold
every permission.

Revision ID: d8f1a3c5e297
Revises: c7d2e5a8f134
Create Date: 2026-10-16 12:00:00.000000

"""
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8f1a3c5e297'
down_revision: Union[str, Sequence[str], None] = 'c7d2e5a8f134'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PERMISSION = 'students.message'
_GRANTED_TO = ('SUPER_ADMIN', 'HOD', 'ASSOCIATE_HEAD', 'TEACHER')

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
    op.create_table(
        'student_notice',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.Enum('ANNOUNCEMENT', 'TEACHER', 'CHANGE', name='noticekind', native_enum=False), nullable=False),
        sa.Column('title', sa.String(length=160), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('author', sa.String(length=255), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=True),
        sa.Column('instance_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['author_id'], ['user.id'],
            name=op.f('fk_student_notice_author_id_user'), ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['instance_id'], ['class_instance.id'],
            name=op.f('fk_student_notice_instance_id_class_instance'), ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_student_notice')),
    )
    op.create_index('ix_student_notice_instance', 'student_notice', ['instance_id'], unique=False)
    op.create_table(
        'student_notice_target',
        sa.Column('notice_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=48), nullable=False),
        sa.ForeignKeyConstraint(
            ['notice_id'], ['student_notice.id'],
            name=op.f('fk_student_notice_target_notice_id_student_notice'), ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('notice_id', 'token', name=op.f('pk_student_notice_target')),
    )
    op.create_index(
        'ix_student_notice_target_token', 'student_notice_target', ['token', 'notice_id'], unique=False
    )

    with op.batch_alter_table('makeup_class', schema=None) as batch_op:
        batch_op.add_column(sa.Column('meeting_link', sa.String(length=1024), nullable=True))

    _rewrite(
        lambda key, held: sorted({*held, _PERMISSION}) if key in _GRANTED_TO else held
    )


def downgrade() -> None:
    """Downgrade schema."""
    _rewrite(lambda _key, held: [p for p in held if p != _PERMISSION])

    with op.batch_alter_table('makeup_class', schema=None) as batch_op:
        batch_op.drop_column('meeting_link')

    op.drop_index('ix_student_notice_target_token', table_name='student_notice_target')
    op.drop_table('student_notice_target')
    op.drop_index('ix_student_notice_instance', table_name='student_notice')
    op.drop_table('student_notice')

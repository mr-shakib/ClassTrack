"""roles and permissions

A role becomes a row an admin can create and edit -- a name, a kind and a set
of permissions -- and an account may hold several. The seven roles that were a
fixed list become built-in rows with exactly the access each had, and every
account keeps the role it held. The single role column on the account goes.

The starting permissions are written out here rather than read from the code,
so what this upgrade did never changes after the fact.

Revision ID: e2b8f4c6a913
Revises: c9e4b7a1d368
Create Date: 2026-10-05 10:00:00.000000

"""
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2b8f4c6a913'
down_revision: Union[str, Sequence[str], None] = 'c9e4b7a1d368'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ALL = [
    'alerts.receive', 'audit.view', 'calendar.manage', 'checking.correct', 'checking.submit',
    'classes.cancel', 'dashboard.view', 'extra_classes.book', 'reports.department',
    'reschedules.any_teacher', 'reschedules.decide', 'reschedules.request', 'roles.manage',
    'routine.manage', 'semesters.manage', 'settings.manage', 'staff.manage',
    'teachers.manage', 'accounts.manage',
]
_COORDINATION = [
    'audit.view', 'calendar.manage', 'checking.correct', 'checking.submit', 'classes.cancel',
    'dashboard.view', 'routine.manage', 'settings.manage', 'staff.manage', 'teachers.manage',
]

# key, name, kind, description, permissions -- in this order, so ids are stable.
_BUILTIN = [
    ('SUPER_ADMIN', 'Super admin', 'OFFICE',
     'Everything, always. Kept as a fallback sign-in.', _ALL),
    ('HOD', 'Head of Department', 'OFFICE',
     'Runs the department: reports, approvals, accounts and semesters.', _ALL),
    ('ASSOCIATE_HEAD', 'Associate Head', 'OFFICE',
     'Deputy to the Head, with the same access.', _ALL),
    ('COORDINATION_OFFICER', 'Coordination Officer', 'OFFICE',
     'Day-to-day monitoring, the routine, the calendar and staff coverage.', _COORDINATION),
    ('COMMITTEE', 'Committee member', 'OFFICE',
     'Reports classes and corrects past checks.', ['checking.correct', 'checking.submit']),
    ('STAFF', 'Office staff', 'STAFF',
     'Checks the classes on their floors.', ['checking.submit']),
    ('TEACHER', 'Teacher', 'TEACHER',
     'Their own classes, reports, reschedules and extra classes.',
     ['extra_classes.book', 'reschedules.request']),
]

#: On the way back an account keeps the most powerful built-in role it holds.
_PRECEDENCE = [key for key, *_ in _BUILTIN]


def upgrade() -> None:
    """Upgrade schema."""
    role = op.create_table(
        'role',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('kind', sa.Enum('TEACHER', 'STAFF', 'OFFICE', name='rolekind', native_enum=False), nullable=False),
        sa.Column('is_builtin', sa.Boolean(), nullable=False),
        sa.Column('permissions', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_role')),
        sa.UniqueConstraint('key', name=op.f('uq_role_key')),
        sa.UniqueConstraint('name', name=op.f('uq_role_name')),
    )
    op.create_table(
        'user_role',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_user_role_user_id_user'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['role.id'], name=op.f('fk_user_role_role_id_role'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('user_id', 'role_id', name=op.f('pk_user_role')),
    )

    now = datetime.now(timezone.utc)
    op.bulk_insert(
        role,
        [
            {
                'id': i, 'key': key, 'name': name, 'kind': kind, 'description': description,
                'is_builtin': True, 'permissions': sorted(granted),
                'created_at': now, 'updated_at': now,
            }
            for i, (key, name, kind, description, granted) in enumerate(_BUILTIN, start=1)
        ],
    )
    # Everyone keeps the role they held.
    op.execute(
        'INSERT INTO user_role (user_id, role_id) '
        'SELECT u.id, r.id FROM "user" u JOIN role r ON r.key = u.role'
    )

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_index('ix_user_role')
        batch_op.drop_column('role')


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    orphans = conn.execute(sa.text(
        'SELECT count(*) FROM "user" u WHERE NOT EXISTS ('
        ' SELECT 1 FROM user_role ur JOIN role r ON r.id = ur.role_id'
        ' WHERE ur.user_id = u.id AND r.is_builtin)'
    )).scalar()
    if orphans:
        raise RuntimeError(
            f"{orphans} account(s) hold only roles made in the app. Give each a built-in "
            "role before downgrading: the older schema holds one fixed role per account."
        )

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('role', sa.String(length=20), nullable=True))
    # The most powerful built-in role each account holds.
    for key in reversed(_PRECEDENCE):
        conn.execute(sa.text(
            'UPDATE "user" SET role = :key WHERE id IN ('
            ' SELECT ur.user_id FROM user_role ur JOIN role r ON r.id = ur.role_id'
            ' WHERE r.key = :key)'
        ), {'key': key})
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column(
            'role',
            existing_type=sa.String(length=20),
            type_=sa.Enum('SUPER_ADMIN', 'HOD', 'ASSOCIATE_HEAD', 'COORDINATION_OFFICER', 'COMMITTEE', 'STAFF', 'TEACHER', name='role', native_enum=False),
            nullable=False,
        )
        batch_op.create_index('ix_user_role', ['role'], unique=False)

    op.drop_table('user_role')
    op.drop_table('role')

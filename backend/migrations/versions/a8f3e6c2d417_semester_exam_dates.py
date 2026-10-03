"""semester exam dates

A semester gains its mid-term exam period and the first day of its final exams.
No routine class is held in either, and they split the semester into the two
terms reported on separately. Existing semesters stay null until an admin sets
the dates; until then only the full-semester report is offered for them.

Revision ID: a8f3e6c2d417
Revises: d2a7c4e19b53
Create Date: 2026-10-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8f3e6c2d417'
down_revision: Union[str, Sequence[str], None] = 'd2a7c4e19b53'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('semester', schema=None) as batch_op:
        batch_op.add_column(sa.Column('mid_exam_start', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('mid_exam_end', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('final_exam_start', sa.Date(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('semester', schema=None) as batch_op:
        batch_op.drop_column('final_exam_start')
        batch_op.drop_column('mid_exam_end')
        batch_op.drop_column('mid_exam_start')

"""add_familiarity_and_goal_to_study_plans

Revision ID: 92ab31455568
Revises: 9f72f028f9ff
Create Date: 2025-05-10 16:17:40.719686

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '92ab31455568'
down_revision: Union[str, None] = '9f72f028f9ff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add familiarity and goal columns to study_plans table
    op.add_column('study_plans', sa.Column('familiarity', sa.String(length=255), nullable=True))
    op.add_column('study_plans', sa.Column('goal', sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove the columns in reverse order
    op.drop_column('study_plans', 'goal')
    op.drop_column('study_plans', 'familiarity')

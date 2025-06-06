"""Add pinecone_namespace to Document

Revision ID: 9f72f028f9ff
Revises: 15f1b6fb075c
Create Date: 2025-05-03 21:54:27.248164

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f72f028f9ff'
down_revision: Union[str, None] = '15f1b6fb075c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('documents', sa.Column('pinecone_namespace', sa.String(length=255), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('documents', 'pinecone_namespace')
    # ### end Alembic commands ###

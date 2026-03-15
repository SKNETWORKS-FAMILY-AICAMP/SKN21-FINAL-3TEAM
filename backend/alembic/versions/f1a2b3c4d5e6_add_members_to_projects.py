"""add members column to projects

Revision ID: f1a2b3c4d5e6
Revises: d1f2e3a4b5c6
Create Date: 2026-03-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'd1f2e3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('members', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('projects', 'members')

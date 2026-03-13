"""add project_name column to schedules

Revision ID: g2h3i4j5k6l7
Revises: f1a2b3c4d5e6
Create Date: 2026-03-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'g2h3i4j5k6l7'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('schedules', sa.Column('project_name', sa.String(300), nullable=True))


def downgrade() -> None:
    op.drop_column('schedules', 'project_name')

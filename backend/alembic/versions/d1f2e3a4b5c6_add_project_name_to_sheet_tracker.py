"""add project_name to google_sheet_trackers

Revision ID: d1f2e3a4b5c6
Revises: ccceaaad855b
Create Date: 2026-03-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd1f2e3a4b5c6'
down_revision: Union[str, None] = 'ccceaaad855b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('google_sheet_trackers', sa.Column('project_name', sa.String(300), nullable=True))


def downgrade() -> None:
    op.drop_column('google_sheet_trackers', 'project_name')

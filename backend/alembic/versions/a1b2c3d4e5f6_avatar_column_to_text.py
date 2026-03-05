"""avatar column to text

Revision ID: a1b2c3d4e5f6
Revises: 8c278366604b
Create Date: 2026-03-05 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '8c278366604b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('users', 'avatar',
                    existing_type=sa.String(length=255),
                    type_=sa.Text(),
                    existing_nullable=True)


def downgrade() -> None:
    op.alter_column('users', 'avatar',
                    existing_type=sa.Text(),
                    type_=sa.String(length=255),
                    existing_nullable=True)

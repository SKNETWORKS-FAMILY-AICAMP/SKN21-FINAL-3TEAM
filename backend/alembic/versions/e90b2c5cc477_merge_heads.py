"""merge heads

Revision ID: e90b2c5cc477
Revises: 7939e09c25f2, c3d4e5f6g7h8
Create Date: 2026-03-05 09:47:54.712076

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e90b2c5cc477'
down_revision: Union[str, None] = ('7939e09c25f2', 'c3d4e5f6g7h8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

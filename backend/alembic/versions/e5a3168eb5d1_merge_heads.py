"""merge heads

Revision ID: e5a3168eb5d1
Revises: 8c278366604b, a1b2c3d4e5f6
Create Date: 2026-03-05 12:26:11.411117

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5a3168eb5d1'
down_revision: Union[str, None] = ('8c278366604b', 'a1b2c3d4e5f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

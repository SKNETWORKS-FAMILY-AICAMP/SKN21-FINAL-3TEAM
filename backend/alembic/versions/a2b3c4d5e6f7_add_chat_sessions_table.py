"""Add chat_sessions table

Revision ID: a2b3c4d5e6f7
Revises: ff4b6e2ab2e5
Create Date: 2026-02-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, None] = 'ff4b6e2ab2e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.String(length=50), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False, server_default='새 대화'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_chat_sessions_session_id', 'chat_sessions', ['session_id'], unique=True)
    op.create_index('ix_chat_sessions_user_id', 'chat_sessions', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_chat_sessions_user_id', table_name='chat_sessions')
    op.drop_index('ix_chat_sessions_session_id', table_name='chat_sessions')
    op.drop_table('chat_sessions')

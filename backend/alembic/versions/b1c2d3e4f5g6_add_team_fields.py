"""Add team fields to documents and schedules

Revision ID: b1c2d3e4f5g6
Revises: a2b3c4d5e6f7
Create Date: 2026-03-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b1c2d3e4f5g6'
down_revision: Union[str, None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # documents: scope 컬럼 확장 + team_name 추가
    op.alter_column('documents', 'scope',
                    existing_type=sa.String(10),
                    type_=sa.String(20),
                    existing_nullable=False)
    op.add_column('documents', sa.Column('team_name', sa.String(50), nullable=True))

    # schedules: team_name + is_team_visible 추가
    op.add_column('schedules', sa.Column('team_name', sa.String(50), nullable=True))
    op.add_column('schedules', sa.Column('is_team_visible', sa.Boolean(), server_default='false', nullable=False))

    # 인덱스 추가 (팀별 조회 성능)
    op.create_index('ix_documents_team_name', 'documents', ['team_name'])
    op.create_index('ix_schedules_team_name', 'schedules', ['team_name'])


def downgrade() -> None:
    op.drop_index('ix_schedules_team_name', table_name='schedules')
    op.drop_index('ix_documents_team_name', table_name='documents')
    op.drop_column('schedules', 'is_team_visible')
    op.drop_column('schedules', 'team_name')
    op.drop_column('documents', 'team_name')
    op.alter_column('documents', 'scope',
                    existing_type=sa.String(20),
                    type_=sa.String(10),
                    existing_nullable=False)

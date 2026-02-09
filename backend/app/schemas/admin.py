"""
관리자 스키마 (팀원 D 정의)
"""
from pydantic import BaseModel


class SystemStatsResponse(BaseModel):
    total_users: int
    total_documents: int
    total_queries: int
    total_judgments: int


class UserAdminResponse(BaseModel):
    id: int
    email: str
    name: str
    is_admin: bool
    is_active: bool

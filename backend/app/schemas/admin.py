"""
관리자 스키마 (팀원 D 정의)
"""
from pydantic import BaseModel
from datetime import datetime


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


# ── 질의 로그 ──


class QueryLogResponse(BaseModel):
    """질의 로그 항목"""
    id: int
    user_id: int
    user_name: str
    message: str
    intent: str
    agent_type: str
    response_summary: str
    created_at: datetime


class QueryLogListResponse(BaseModel):
    """질의 로그 목록 (페이지네이션)"""
    total: int
    page: int
    per_page: int
    items: list[QueryLogResponse]


# ── Top 질의 통계 ──


class TopQueryItem(BaseModel):
    """인기 질의 항목"""
    query: str
    count: int
    intent: str


class TopQueryResponse(BaseModel):
    """Top 질의 응답"""
    period: str                 # daily | weekly | monthly
    items: list[TopQueryItem]

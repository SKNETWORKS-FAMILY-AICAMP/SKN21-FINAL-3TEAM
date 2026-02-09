"""
문서 스키마 (팀원 A 정의, 팀원 C/D 확장)
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class DocumentResponse(BaseModel):
    id: int
    title: str
    file_type: str
    scope: str  # company / personal
    status: str
    uploaded_by: int
    created_at: datetime


class DocumentDetailResponse(DocumentResponse):
    content: Optional[str] = None
    file_path: str

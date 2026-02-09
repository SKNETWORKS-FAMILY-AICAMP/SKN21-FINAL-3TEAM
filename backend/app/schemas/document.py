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
    version: Optional[int] = 1


# ── UI_UX.pdf 추가 스키마 ──


class DocumentGenerateRequest(BaseModel):
    """문서 생성 요청 (FR-DOC-008)"""
    template_type: str  # meeting_minutes | report | jd | proposal
    user_input: str     # 사용자 입력 (회의 요약 등)


class DocumentGenerateResponse(BaseModel):
    """문서 생성 응답 → GenerateCard에서 표시"""
    document_id: int
    template_type: str
    template_name: str  # "회의록", "보고서" 등
    preview: str        # 마크다운 미리보기
    created_at: datetime


class DocumentSearchResult(BaseModel):
    """검색 결과 + 키워드 하이라이트 (FR-DOC-006)"""
    id: int
    title: str
    snippet: str                    # 매칭된 부분 발췌
    highlights: list                # [{"start": 10, "end": 15, "keyword": "보안"}]
    relevance_score: float          # 관련도 점수
    scope: str


class ParsingStatusResponse(BaseModel):
    """파싱 상태 응답 (NF-PRF-002)"""
    document_id: int
    status: str             # uploading | parsing | completed | failed
    progress: Optional[int] = None
    detected_template: Optional[str] = None  # meeting_minutes | None

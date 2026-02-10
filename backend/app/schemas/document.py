"""
문서 스키마 (팀원 A 정의, 팀원 C/D 확장)
"""
from pydantic import BaseModel
from typing import Optional, List
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


# ── 문서 생성 ──


class DocumentGenerateRequest(BaseModel):
    """문서 생성 요청 (FR-DOC-008) — 템플릿 ID 기반"""
    template_id: Optional[int] = None       # DB 템플릿 ID (커스텀/시스템)
    template_type: Optional[str] = None     # 시스템 템플릿 직접 지정 (meeting_minutes | report | jd | proposal)
    user_input: str                         # 사용자 입력 (내용/지시사항)


class DocumentGenerateResponse(BaseModel):
    """문서 생성 응답 → GenerateCard / DocumentPreview에서 표시"""
    document_id: int
    template_id: Optional[int] = None
    template_type: str
    template_name: str  # "회의록", "보고서" 등
    preview: str        # 마크다운 미리보기
    download_url: str   # 다운로드 URL
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


# ── 템플릿 관리 ──


class TemplateResponse(BaseModel):
    """템플릿 목록/상세 응답"""
    id: int
    name: str
    description: Optional[str] = None
    category: str           # meeting_minutes | report | jd | proposal | custom
    is_system: bool
    scope: str              # company | personal
    file_type: Optional[str] = None
    status: str             # processing | ready | error
    created_at: datetime


class TemplateDetailResponse(TemplateResponse):
    """템플릿 상세 (parsed_structure 포함)"""
    parsed_structure: Optional[str] = None
    file_path: Optional[str] = None
    uploaded_by: Optional[int] = None


class TemplateUploadRequest(BaseModel):
    """템플릿 업로드 메타데이터"""
    name: str
    description: Optional[str] = None
    category: str = "custom"
    scope: str = "company"

"""
문서 스키마 (팀원 A 정의, 팀원 C/D 확장)
"""
from pydantic import BaseModel, model_validator
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
    highlights: list[dict] = []     # [{"start": 10, "end": 15, "keyword": "보안"}]
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


# ── 문서 요약 ──


class DocumentSummarizeRequest(BaseModel):
    """문서 요약 요청 — 파일 업로드 또는 기존 문서 선택

    template_type과 custom_fields 중 하나만 지정 가능:
      - template_type만 지정 → 해당 템플릿의 기본 필드로 요약
      - custom_fields만 지정 → 커스텀 필드로 요약
      - 둘 다 None → 기본 필드(title, summary, key_points, conclusion)로 요약
    """
    document_id: Optional[int] = None       # 문서관리에서 기존 문서 선택 시
    # 파일 업로드는 multipart/form-data로 별도 처리 (file 파라미터)
    template_type: Optional[str] = None     # 요약 형식 선택 (report | proposal | 등)
    custom_fields: Optional[list[str]] = None  # 커스텀 필드 직접 지정

    @model_validator(mode="after")
    def check_fields_exclusive(self):
        if self.template_type and self.custom_fields:
            raise ValueError("template_type과 custom_fields는 동시에 지정할 수 없습니다")
        return self


class DocumentSummarizeResponse(BaseModel):
    """문서 요약 응답 — 필드별 요약 결과"""
    document_id: int
    original_title: Optional[str] = None
    fields_used: list[str]                  # 어떤 필드로 요약했는지
    result: dict                            # 필드별 요약 결과 (예: {"title": "...", "summary": "...", ...})
    preview: str                            # 마크다운 미리보기
    download_url: Optional[str] = None

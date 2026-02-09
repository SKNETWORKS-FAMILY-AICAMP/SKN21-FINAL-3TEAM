"""
문서 서비스 (팀원 C/D 공동 담당)
"""


class DocumentService:
    """문서 업로드, 파싱, 검색 비즈니스 로직"""

    async def upload_and_parse(self, file_path: str, scope: str, user_id: int):
        """파일 업로드 → 파싱 → 벡터 DB 저장"""
        # TODO: 팀원 C - Docling/PaddleOCR 파싱 연동
        # TODO: 팀원 D - DB 저장
        raise NotImplementedError

    async def search_documents(self, query: str, user_id: int):
        """문서 검색 (scope 필터 포함)"""
        # TODO: 팀원 B/C - RAG 검색 + scope 필터
        raise NotImplementedError

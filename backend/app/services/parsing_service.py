"""
문서 파싱 상태 관리 서비스 (팀원 D 담당)

UI_UX.pdf: "[추가] 파싱 진행 상태 표시 ('파싱 중...' → '파싱 완료')"
요구사항: NF-PRF-002

파싱 상태 플로우:
  uploading → parsing → completed (또는 failed)
"""


class ParsingService:
    """문서 파싱 상태 관리"""

    # 파싱 상태 종류
    STATUS_UPLOADING = "uploading"
    STATUS_PARSING = "parsing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    async def start_parsing(self, document_id: int) -> dict:
        """
        문서 파싱 시작 (비동기)

        Args:
            document_id: 업로드된 문서 ID

        Returns:
            {"document_id": 123, "status": "parsing", "detected_template": "meeting_minutes"}
        """
        # TODO: 팀원 D 구현
        # 1. 상태를 'parsing'으로 변경
        # 2. Celery 태스크로 파싱 비동기 실행
        # 3. 회의록 자동 감지 (FR-DOC-002)
        # 4. 파싱 완료 시 상태를 'completed'로 변경
        raise NotImplementedError

    async def get_parsing_status(self, document_id: int) -> dict:
        """
        파싱 상태 조회 (프론트에서 폴링)

        Returns:
            {
                "document_id": 123,
                "status": "completed",
                "detected_template": "meeting_minutes",
                "progress": 100
            }
        """
        # TODO: 팀원 D 구현
        raise NotImplementedError

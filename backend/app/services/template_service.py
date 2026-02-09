"""
문서 템플릿 서비스 (팀원 D 담당 - API, 팀원 C 담당 - 생성 로직)

UI_UX.pdf + 기획서: 문서 생성 + 다운로드 + 미리보기
요구사항: FR-DOC-008

플로우:
  1. 챗봇에서 문서 생성 요청 (doc_generate intent)
  2. 문서 Agent가 sLLM + 템플릿으로 문서 생성
  3. 미리보기(마크다운) 반환 → 프론트에서 GenerateCard로 표시
  4. 사용자가 다운로드 클릭 → DOCX/PDF 변환 후 반환
"""


class TemplateService:
    """문서 템플릿 서비스"""

    # 지원 템플릿 목록
    TEMPLATE_TYPES = {
        "meeting_minutes": "회의록",
        "report": "보고서",
        "jd": "채용 공고",
        "proposal": "제안서",
    }

    async def generate_document(
        self, template_type: str, user_input: str, user_id: int
    ) -> dict:
        """
        사용자 입력으로 문서 생성

        Args:
            template_type: 템플릿 종류
            user_input: 사용자가 입력한 요약/핵심 내용
            user_id: 사용자 ID

        Returns:
            {
                "preview": "렌더링된 마크다운 텍스트",
                "template_type": "meeting_minutes",
                "document_id": 123
            }
        """
        # TODO: 팀원 D (API) + 팀원 C (생성 로직) 협업
        # 1. template_type에 맞는 템플릿 로드 (ai/templates/)
        # 2. sLLM으로 user_input 기반 데이터 생성
        # 3. 템플릿 렌더링
        # 4. DB에 생성된 문서 저장
        # 5. 미리보기 텍스트 반환
        raise NotImplementedError

    async def download_document(
        self, document_id: int, format: str = "docx"
    ) -> bytes:
        """
        생성된 문서를 DOCX/PDF로 다운로드

        Args:
            document_id: 문서 ID
            format: 'docx' 또는 'pdf'

        Returns:
            파일 바이너리 데이터
        """
        # TODO: 팀원 D 구현
        # 1. DB에서 문서 조회
        # 2. 템플릿의 to_docx() 또는 to_pdf() 호출
        # 3. 바이너리 반환
        raise NotImplementedError

    async def detect_template(self, text: str) -> str:
        """
        업로드된 문서에서 템플릿 종류 자동 감지

        요구사항: FR-DOC-002 (회의록 자동 인식)

        Args:
            text: 업로드된 문서 텍스트

        Returns:
            감지된 템플릿 종류 ('meeting_minutes' | 'report' | 'unknown')
        """
        # TODO: 팀원 C 구현
        # 키워드 기반 감지: "회의", "참석자", "안건" → meeting_minutes
        raise NotImplementedError

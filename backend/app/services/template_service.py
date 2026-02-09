"""
문서 템플릿 서비스 (팀원 D 담당 - API, 팀원 C 담당 - 생성 로직)

플로우:
  1. 챗봇 또는 전용 페이지에서 문서 생성 요청
  2. template_id로 DB에서 템플릿 로드 (시스템 or 커스텀)
  3. 시스템 템플릿 → ai/templates/ 클래스 사용
     커스텀 템플릿 → parsed_structure 기반 동적 생성
  4. sLLM으로 user_input 기반 데이터 생성
  5. 템플릿 렌더링 → 미리보기(마크다운) 반환
  6. 다운로드 시 DOCX/PDF 변환

요구사항: FR-DOC-008
"""


class TemplateService:
    """문서 템플릿 서비스"""

    # 시스템 기본 제공 템플릿 종류
    SYSTEM_TEMPLATE_TYPES = {
        "meeting_minutes": "회의록",
        "report": "보고서",
        "jd": "채용 공고",
        "proposal": "제안서",
    }

    async def generate_document(
        self,
        user_input: str,
        user_id: int,
        template_id: int = None,
        template_type: str = None,
    ) -> dict:
        """
        사용자 입력으로 문서 생성

        Args:
            user_input: 사용자가 입력한 내용/지시사항
            user_id: 사용자 ID
            template_id: DB 템플릿 ID (커스텀 또는 시스템)
            template_type: 시스템 템플릿 직접 지정 (template_id 없을 때)

        Returns:
            {
                "preview": "렌더링된 마크다운 텍스트",
                "template_type": "meeting_minutes",
                "template_name": "회의록",
                "document_id": 123,
                "download_url": "/api/v1/documents/123/download"
            }
        """
        # TODO: 팀원 D (API) + 팀원 C (생성 로직) 협업
        # 1. template_id → document_templates 테이블에서 로드
        #    OR template_type → SYSTEM_TEMPLATES에서 클래스 로드
        # 2. 시스템 템플릿: ai/templates/ 클래스의 render() 사용
        #    커스텀 템플릿: parsed_structure + render_from_structure() 사용
        # 3. sLLM으로 user_input 기반 데이터 생성
        # 4. 템플릿 렌더링
        # 5. DB에 생성된 문서 저장
        # 6. 미리보기 텍스트 반환
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

    async def upload_template(
        self,
        file_path: str,
        file_type: str,
        name: str,
        description: str,
        category: str,
        scope: str,
        user_id: int,
    ) -> dict:
        """
        커스텀 템플릿 업로드 및 구조 추출

        Args:
            file_path: 저장된 파일 경로
            file_type: 파일 타입 (docx, pdf)
            name: 템플릿 이름
            description: 설명
            category: 카테고리
            scope: company | personal
            user_id: 업로드한 사용자 ID

        Returns:
            {
                "template_id": 42,
                "status": "processing",
                "name": "커스텀 보고서"
            }
        """
        # TODO: 팀원 D (저장) + 팀원 C (구조 추출)
        # 1. document_templates 테이블에 레코드 생성 (status: processing)
        # 2. 비동기로 AI 구조 추출 시작
        # 3. parsed_structure 저장 → status: ready
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

"""
기본 템플릿 클래스 (팀원 C 담당)

모든 문서 템플릿의 부모 클래스.
각 템플릿은 이 클래스를 상속받아 render() 메서드를 구현합니다.
커스텀 템플릿은 from_parsed_structure()로 동적 생성 가능합니다.
"""


class BaseTemplate:
    """문서 템플릿 베이스 클래스"""

    template_type: str = ""
    template_name: str = ""

    def render(self, data: dict) -> str:
        """
        템플릿에 데이터를 넣어 문서 텍스트(마크다운) 생성

        Args:
            data: 템플릿에 채울 데이터 (사용자 입력 + sLLM 생성)

        Returns:
            렌더링된 문서 텍스트 (마크다운 형식)
        """
        # TODO: 팀원 C - 각 하위 클래스에서 구현
        raise NotImplementedError

    def validate(self, data: dict) -> bool:
        """
        데이터 유효성 검증 (필수 필드 확인)

        Args:
            data: 검증할 데이터

        Returns:
            유효 여부
        """
        # TODO: 팀원 C 구현
        raise NotImplementedError

    def to_docx(self, rendered_text: str) -> bytes:
        """
        렌더링된 텍스트를 DOCX 바이너리로 변환

        Args:
            rendered_text: render()의 결과

        Returns:
            DOCX 바이트 데이터
        """
        # TODO: 팀원 C - python-docx 활용
        raise NotImplementedError

    def to_pdf(self, rendered_text: str) -> bytes:
        """
        렌더링된 텍스트를 PDF 바이너리로 변환

        Args:
            rendered_text: render()의 결과

        Returns:
            PDF 바이트 데이터
        """
        # TODO: 팀원 C - weasyprint 또는 reportlab 활용
        raise NotImplementedError

    @classmethod
    def from_parsed_structure(cls, parsed_structure: dict) -> "BaseTemplate":
        """
        DB에 저장된 parsed_structure(JSON)로부터 동적 템플릿 인스턴스 생성

        사용자가 업로드한 커스텀 템플릿을 AI가 분석하여 parsed_structure를 추출하고,
        이를 기반으로 런타임에 템플릿을 생성합니다.

        Args:
            parsed_structure: AI가 추출한 양식 구조
                {
                    "sections": ["제목", "개요", "본문", ...],
                    "fields": {"title": "str", "date": "date", ...},
                    "layout": "report"
                }

        Returns:
            동적 생성된 BaseTemplate 인스턴스
        """
        # TODO: 팀원 C 구현
        raise NotImplementedError

    def render_from_structure(self, parsed_structure: dict, data: dict) -> str:
        """
        parsed_structure 기반으로 데이터를 채워 마크다운 문서 생성

        커스텀 템플릿(사용자 업로드)에서 사용.
        시스템 템플릿은 render()를 직접 사용.

        Args:
            parsed_structure: AI가 추출한 양식 구조 (JSON)
            data: sLLM이 생성한 내용 데이터

        Returns:
            렌더링된 마크다운 텍스트
        """
        # TODO: 팀원 C 구현
        raise NotImplementedError

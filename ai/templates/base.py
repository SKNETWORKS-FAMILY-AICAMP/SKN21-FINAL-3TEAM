"""
기본 템플릿 클래스 (팀원 C 담당)

모든 문서 템플릿의 부모 클래스.
각 템플릿은 이 클래스를 상속받아 render() 메서드를 구현합니다.
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

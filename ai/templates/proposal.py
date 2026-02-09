"""
제안서 템플릿 (팀원 C 담당)

요구사항: FR-DOC-008
"""
from ai.templates.base import BaseTemplate


class ProposalTemplate(BaseTemplate):
    """제안서 템플릿"""

    template_type = "proposal"
    template_name = "제안서"

    TEMPLATE = """# {title}

## 제안 배경
{background}

## 제안 내용
{content}

## 기대 효과
{expected_results}

## 일정 계획
{timeline}

## 필요 자원
{resources}

## 리스크 및 대응 방안
{risks}
"""

    def render(self, data: dict) -> str:
        # TODO: 팀원 C 구현
        raise NotImplementedError("팀원 C: 제안서 템플릿 렌더링 구현 필요")

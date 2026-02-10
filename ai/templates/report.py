"""
보고서 템플릿 (팀원 C 담당)

요구사항: FR-DOC-008
"""
from ai.templates.base import BaseTemplate


class ReportTemplate(BaseTemplate):
    """보고서 템플릿"""

    template_type = "report"
    template_name = "보고서"

    TEMPLATE = """# {title}

## 개요
- **작성일**: {date}
- **작성자**: {author}
- **대상**: {audience}

## 요약
{summary}

## 상세 내용
{content}

## 결론 및 제안
{conclusion}

## 첨부
{attachments}
"""

    def render(self, data: dict) -> str:
        # TODO: 팀원 C 구현
        raise NotImplementedError("팀원 C: 보고서 템플릿 렌더링 구현 필요")

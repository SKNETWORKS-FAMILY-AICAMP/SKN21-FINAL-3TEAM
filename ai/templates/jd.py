"""
채용 공고(JD) 템플릿 (팀원 C 담당)

요구사항: FR-DOC-008
"""
from ai.templates.base import BaseTemplate


class JDTemplate(BaseTemplate):
    """채용 공고 템플릿"""

    template_type = "jd"
    template_name = "채용 공고"

    TEMPLATE = """# {position} 채용

## 포지션 정보
- **직무**: {position}
- **고용형태**: {employment_type}
- **경력**: {experience}
- **근무지**: {location}

## 주요 업무
{responsibilities}

## 자격 요건
{requirements}

## 우대 사항
{preferred}

## 복리후생
{benefits}

## 지원 방법
{how_to_apply}
"""

    def render(self, data: dict) -> str:
        # TODO: 팀원 C 구현
        raise NotImplementedError("팀원 C: JD 템플릿 렌더링 구현 필요")

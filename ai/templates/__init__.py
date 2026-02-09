"""
문서 템플릿 시스템 (팀원 C 담당)

사용자가 챗봇/전용 페이지에서 문서 생성 요청 시 템플릿 기반으로 문서 생성
요구사항: FR-DOC-008

시스템 기본 제공 템플릿 (4종):
  - meeting_minutes: 회의록
  - report: 보고서
  - jd: 채용 공고 (Job Description)
  - proposal: 제안서

사용자 커스텀 템플릿:
  - 사용자가 파일 업로드 → AI가 양식 구조 추출 → parsed_structure 저장
  - 이후 해당 구조 기반으로 문서 생성 가능
"""
from ai.templates.base import BaseTemplate
from ai.templates.meeting_minutes import MeetingMinutesTemplate
from ai.templates.report import ReportTemplate
from ai.templates.jd import JDTemplate
from ai.templates.proposal import ProposalTemplate

# 시스템 기본 제공 템플릿 레지스트리
SYSTEM_TEMPLATES = {
    "meeting_minutes": MeetingMinutesTemplate,
    "report": ReportTemplate,
    "jd": JDTemplate,
    "proposal": ProposalTemplate,
}


def get_system_template(template_type: str) -> BaseTemplate:
    """시스템 템플릿 인스턴스 반환"""
    template_cls = SYSTEM_TEMPLATES.get(template_type)
    if template_cls is None:
        raise ValueError(f"알 수 없는 시스템 템플릿: {template_type}")
    return template_cls()

"""
문서 템플릿 시스템 (팀원 C 담당)

UI_UX.pdf + 기획서: "템플릿 기반 문서 생성 (JD, 보고서, 제안서, 회의록)"
요구사항: FR-DOC-008

사용자가 챗봇에서 "회의록 만들어줘" → 요약 입력 → 템플릿 기반 문서 생성 → 미리보기 + 다운로드

템플릿 종류:
  - meeting_minutes: 회의록
  - report: 보고서
  - jd: 채용 공고 (Job Description)
  - proposal: 제안서
"""
from ai.templates.base import BaseTemplate

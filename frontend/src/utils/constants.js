/**
 * 상수 정의 (팀원 E 담당)
 */

// Intent 타입
export const INTENT_TYPES = {
  JUDGMENT: 'judgment',
  DOC_SEARCH: 'doc_search',
  DOC_SUMMARY: 'doc_summary',
  DOC_GENERATE: 'doc_generate',
  MEETING_ANALYSIS: 'meeting_analysis',
  SCHEDULE_ADD: 'schedule_add',
  SCHEDULE_VIEW: 'schedule_view',
}

// Intent 한글 라벨
export const INTENT_LABELS = {
  judgment: '규정 판단',
  doc_search: '문서 검색',
  doc_summary: '문서 요약',
  doc_generate: '문서 생성',
  meeting_analysis: '회의록 분석',
  schedule_add: '일정 추가',
  schedule_view: '일정 조회',
}

// 판단 결과 타입
export const JUDGMENT_RESULTS = {
  YES: 'yes',
  NO: 'no',
  CONDITIONAL: 'conditional',
  NO_REGULATION: 'no_regulation',
}

// 문서 scope
export const DOCUMENT_SCOPES = {
  COMPANY: 'company',
  PERSONAL: 'personal',
}

// 일정 타입 색상
export const SCHEDULE_COLORS = {
  meeting: '#3B82F6',
  task: '#8B5CF6',
  deadline: '#EF4444',
}

// 리스크 레벨 색상
export const RISK_COLORS = {
  high: '#EF4444',
  medium: '#F59E0B',
  low: '#10B981',
}

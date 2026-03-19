/**
 * 상수 정의 (팀원 E 담당)
 */

// Intent 타입 (6개)
export const INTENT_TYPES = {
  JUDGMENT: 'judgment',
  DOC_RETRIEVE: 'doc_retrieve',
  DOC_GENERATE: 'doc_generate',
  SCHEDULE_ADD: 'schedule_add',
  SCHEDULE_VIEW: 'schedule_view',
  GENERAL: 'general',
}

// Intent 한글 라벨
export const INTENT_LABELS = {
  judgment: '규정 판단',
  doc_retrieve: '문서 검색/조회',
  doc_generate: '문서 생성',
  schedule_add: '일정 추가',
  schedule_view: '일정 조회',
  general: '일반 질문',
}

// Intent별 아이콘 이름 (Lucide 매핑용)
export const INTENT_ICONS = {
  judgment: 'Scale',
  doc_retrieve: 'Search',
  doc_generate: 'FileText',
  schedule_add: 'CalendarPlus',
  schedule_view: 'CalendarDays',
  general: 'MessageCircle',
}

// 판단 결과 타입
export const JUDGMENT_RESULTS = {
  YES: 'yes',
  NO: 'no',
  CONDITIONAL: 'conditional',
  NO_REGULATION: 'no_regulation',
}

// 팀(부서) 목록
export const TEAMS = ['개발', 'QA기획', 'UI/UX', '영업', '마케팅', 'CS', '경영', 'HR'];

// 문서 scope
export const DOCUMENT_SCOPES = {
  COMPANY: 'company',
  TEAM: 'team',
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

// ── 템플릿 관련 ──

// 문서 템플릿 종류 (시스템 기본)
export const TEMPLATE_TYPES = {
  MEETING_MINUTES: 'meeting_minutes',
  REPORT: 'report',
  JD: 'jd',
  PROPOSAL: 'proposal',
}

// 템플릿 한글 라벨
export const TEMPLATE_LABELS = {
  meeting_minutes: '회의록',
  report: '보고서',
  jd: '채용 공고',
  proposal: '제안서',
  custom: '사용자 정의',
}

// 템플릿 카테고리
export const TEMPLATE_CATEGORIES = [
  { value: 'meeting_minutes', label: '회의록' },
  { value: 'report', label: '보고서' },
  { value: 'proposal', label: '제안서' },
]

// ── 파싱/상태 관련 ──

// 파싱 상태
export const PARSING_STATUS = {
  UPLOADING: 'uploading',
  PARSING: 'parsing',
  COMPLETED: 'completed',
  FAILED: 'failed',
}

// 파싱 상태 한글 라벨
export const PARSING_STATUS_LABELS = {
  uploading: '업로드 중...',
  parsing: '파싱 중...',
  completed: '파싱 완료',
  failed: '파싱 실패',
}

// 회의 상태 뱃지
export const MEETING_STATUS = {
  SCHEDULED: 'scheduled',
  IN_PROGRESS: 'in_progress',
  COMPLETED: 'completed',
  ANALYZING: 'analyzing',
  ANALYZED: 'analyzed',
}

// 회의 상태 한글 라벨
export const MEETING_STATUS_LABELS = {
  scheduled: '예정',
  in_progress: '진행중',
  completed: '완료',
  analyzing: '분석중',
  analyzed: '분석완료',
}

// 규정 상태 뱃지
export const REGULATION_STATUS = {
  ACTIVE: 'active',
  REVISING: 'revising',
  DEPRECATED: 'deprecated',
}

// 규정 상태 색상
export const REGULATION_STATUS_COLORS = {
  active: '#10B981',
  revising: '#F59E0B',
  deprecated: '#6B7280',
}

// 추천 질문 카테고리
export const SUGGESTED_QUESTION_CATEGORIES = [
  { key: 'all', label: '전체', icon: 'Sparkles' },
  { key: 'regulation', label: '규정', icon: 'Scale' },
  { key: 'document', label: '문서', icon: 'FileText' },
  { key: 'schedule', label: '일정', icon: 'CalendarDays' },
  { key: 'general', label: '일반', icon: 'MessageCircle' },
]

// 추천 질문 (카테고리 포함)
export const SUGGESTED_QUESTIONS = [
  { text: '재택근무 규정 알려줘', intent: 'judgment', category: 'regulation' },
  { text: '연차 사용 기준이 어떻게 돼?', intent: 'judgment', category: 'regulation' },
  { text: '인턴도 법인카드 쓸 수 있어?', intent: 'judgment', category: 'regulation' },
  { text: '회의록 만들어줘', intent: 'doc_generate', category: 'document' },
  { text: '보고서 만들어줘', intent: 'doc_generate', category: 'document' },
  { text: '이 문서 요약해줘', intent: 'doc_retrieve', category: 'document' },
  { text: '지난 회의 결정사항이 뭐야?', intent: 'doc_retrieve', category: 'document' },
  { text: '신입 온보딩 가이드 있어?', intent: 'doc_retrieve', category: 'document' },
  { text: '오늘 일정 알려줘', intent: 'schedule_view', category: 'schedule' },
  { text: '내일 오후 2시에 회의 잡아줘', intent: 'schedule_add', category: 'schedule' },
  { text: '이번 주 미팅 일정 보여줘', intent: 'schedule_view', category: 'schedule' },
  { text: '우리 회사 복지 제도 알려줘', intent: 'general', category: 'general' },
  { text: '부서 연락처 알려줘', intent: 'general', category: 'general' },
]

// 알림 설정 (Phase 2)
export const REMINDER_OPTIONS = [
  { value: 'none', label: '없음' },
  { value: '1d', label: '1일 전' },
  { value: '3d', label: '3일 전' },
  { value: '7d', label: '7일 전' },
]

// ── Google 서비스 ──

// Google OAuth scope 키
export const GOOGLE_SCOPES = {
  CALENDAR: 'calendar',
  TASKS: 'tasks',
  GMAIL_SEND: 'gmail_send',
  SHEETS: 'sheets',
}

// Google scope 한글 라벨
export const GOOGLE_SCOPE_LABELS = {
  calendar: 'Google Calendar',
  tasks: 'Google Tasks',
  gmail_send: 'Gmail',
  sheets: 'Google Sheets',
}

// Google Task 상태
export const TASK_STATUS = {
  NEEDS_ACTION: 'needsAction',
  COMPLETED: 'completed',
}

// Task 상태 한글 라벨
export const TASK_STATUS_LABELS = {
  needsAction: '미완료',
  completed: '완료',
}

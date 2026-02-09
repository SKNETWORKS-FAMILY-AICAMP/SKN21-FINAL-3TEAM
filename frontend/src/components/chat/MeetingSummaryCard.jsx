/**
 * MeetingSummaryCard - 회의 요약 응답 카드 (팀원 E 담당)
 *
 * UI_UX.pdf: "회의 요약 응답 UI (핵심 내용 + 결정사항 + Action Items)"
 *
 * Props:
 *   - summary: 핵심 내용 요약 텍스트
 *   - decisions: 결정사항 배열
 *   - actionItems: Action Item 배열 [{content, assignee, dueDate}]
 *   - riskLevel: 리스크 레벨 ('high' | 'medium' | 'low')
 *   - risks: 규정 위반 리스크 배열
 *
 * 기능:
 *   - 핵심 내용 요약 표시
 *   - 결정사항 목록
 *   - Action Items 체크리스트 (담당자, 기한 포함)
 *   - 리스크 알림 (규정 위반 경고)
 *   - "일정에 추가" 버튼 (Action Item → 일정 Agent 연동)
 */
export default function MeetingSummaryCard() {
  return (
    <div>
      {/* TODO: 팀원 E 구현
        1. 핵심 내용 요약 섹션
        2. 결정사항 리스트 (넘버링)
        3. Action Items 테이블 (담당자, 내용, 기한, 체크박스)
        4. 리스크 알림 뱃지 (높음:빨강, 중간:주황, 낮음:초록)
        5. "일정에 추가" 버튼 → schedule_add 요청
      */}
    </div>
  )
}

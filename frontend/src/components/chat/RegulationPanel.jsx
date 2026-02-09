/**
 * RegulationPanel - 관련 규정 패널 (팀원 E 담당)
 *
 * UI_UX.pdf: "관련 규정 패널 (우측)"
 *
 * Props:
 *   - regulations: RAG 검색 결과 규정 목록
 *     [{title, section, content, relevanceScore}]
 *   - isOpen: 패널 열림 상태
 *   - onClose: 닫기 콜백
 *
 * 기능:
 *   - 챗봇 우측에 관련 규정 원문 패널
 *   - 판단/문서 응답 시 참조한 규정 조항 표시
 *   - 관련도 점수 표시
 *   - 조항 클릭 시 전문 보기
 */
export default function RegulationPanel() {
  return (
    <div>
      {/* TODO: 팀원 E 구현
        1. 슬라이드 패널 (우측에서 열림)
        2. 규정 목록 (제목 + 조항 번호 + 관련도 점수)
        3. 조항 펼치기/접기 (전문 보기)
        4. "문서 관리에서 보기" 링크
      */}
    </div>
  )
}

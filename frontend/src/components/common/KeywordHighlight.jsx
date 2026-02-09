/**
 * KeywordHighlight - 검색 키워드 하이라이트 유틸 컴포넌트 (팀원 E 담당)
 *
 * UI_UX.pdf: "[추가] 검색 결과 키워드 하이라이트 (매칭 키워드 노란색 배경 강조)"
 * 요구사항: FR-DOC-006
 *
 * Props:
 *   - text: 원문 텍스트
 *   - keywords: 하이라이트할 키워드 배열
 *   - highlightColor: 하이라이트 색상 (기본: '#FEF08A' 노란색)
 *
 * 기능:
 *   - 텍스트 내 키워드 매칭 부분을 노란색 배경으로 강조
 *   - 문서 검색 결과, 규정 상세 페이지에서 사용
 */
export default function KeywordHighlight() {
  return (
    <span>
      {/* TODO: 팀원 E 구현
        1. text에서 keywords에 해당하는 부분을 찾아서 <mark> 태그로 감싸기
        2. 대소문자 무시, 한글 초성 검색 고려
        3. highlightColor로 배경색 지정
      */}
    </span>
  )
}

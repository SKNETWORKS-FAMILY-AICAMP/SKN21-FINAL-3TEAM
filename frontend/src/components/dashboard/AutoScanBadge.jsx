/**
 * AutoScanBadge - 자동 스캔 뱃지 (팀원 E 담당)
 *
 * UI_UX.pdf: "[추가] 자동 스캔 뱃지 ('자동 스캔됨' 표시)"
 * 요구사항: FR-DOC-010
 *
 * Props:
 *   - isScanned: 자동 스캔 완료 여부
 *   - riskLevel: 리스크 레벨 ('high' | 'medium' | 'low' | null)
 *   - riskCount: 감지된 리스크 건수
 *
 * 기능:
 *   - 문서 처리 완료 후 규정 이슈 자동 스캔 결과 뱃지
 *   - 리스크 레벨별 색상 (높음:빨강, 중간:주황, 낮음:초록)
 */
export default function AutoScanBadge() {
  return (
    <span>
      {/* TODO: 팀원 E 구현
        1. "자동 스캔됨" 뱃지 (riskLevel에 따라 색상 변경)
        2. 리스크 건수 표시
        3. 클릭 시 상세 리스크 목록 팝오버
      */}
    </span>
  )
}

/**
 * ParsingStatus - 파싱 진행 상태 표시 (팀원 E 담당)
 *
 * UI_UX.pdf: "[추가] 업로드 시 파싱 상태 표시 ('파싱 중...' → '파싱 완료 ✓')"
 * 요구사항: NF-PRF-002
 *
 * Props:
 *   - status: 파싱 상태 ('uploading' | 'parsing' | 'completed' | 'failed')
 *   - progress: 진행률 (0~100, 선택적)
 *   - documentName: 문서 이름
 *
 * 기능:
 *   - 문서 업로드 후 파싱 진행 상태 실시간 표시
 *   - "업로드 중..." → "파싱 중..." → "파싱 완료 ✓"
 *   - 회의록 자동 감지 시 "회의록 자동 감지됨 ✓" 뱃지 추가
 */
export default function ParsingStatus() {
  return (
    <div>
      {/* TODO: 팀원 E 구현
        1. 상태별 아이콘 + 텍스트 (업로드/파싱중/완료/실패)
        2. 프로그레스 바 (선택적)
        3. 회의록 자동 감지 뱃지 (FR-DOC-002)
        4. 실패 시 "재시도" 버튼
      */}
    </div>
  )
}

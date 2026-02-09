/**
 * GenerateCard - 문서 생성 응답 카드 (팀원 E 담당)
 *
 * UI_UX.pdf: "문서 생성 응답 UI (미리보기 + 다운로드 버튼)"
 * 요구사항: FR-DOC-008
 *
 * Props:
 *   - title: 생성된 문서 제목
 *   - templateType: 템플릿 종류 ('meeting_minutes' | 'report' | 'jd' | 'proposal')
 *   - preview: 미리보기 텍스트 (마크다운)
 *   - downloadUrl: 다운로드 링크 (DOCX/PDF)
 *   - createdAt: 생성 시각
 *
 * 기능:
 *   - 생성된 문서 미리보기 (마크다운 렌더링)
 *   - DOCX / PDF 다운로드 버튼
 *   - 템플릿 종류 뱃지 표시
 */
export default function GenerateCard() {
  return (
    <div>
      {/* TODO: 팀원 E 구현
        1. 문서 미리보기 영역 (마크다운 렌더링)
        2. 템플릿 종류 뱃지 (회의록 / 보고서 / JD / 제안서)
        3. 다운로드 버튼 (DOCX, PDF)
        4. "수정하기" 버튼 → 재생성 요청
      */}
    </div>
  )
}

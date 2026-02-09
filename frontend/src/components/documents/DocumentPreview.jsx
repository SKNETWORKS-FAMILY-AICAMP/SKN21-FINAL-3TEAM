/**
 * 생성된 문서 미리보기 + 다운로드 컴포넌트 (팀원 E 담당)
 *
 * 표시 항목:
 *   - 템플릿 정보 (이름, 타입)
 *   - 마크다운 미리보기
 *   - DOCX/PDF 다운로드 버튼
 */

export default function DocumentPreview({ result, onReset }) {
  const handleDownload = (format) => {
    const url = `${result.download_url}?format=${format}`
    window.open(url, '_blank')
  }

  return (
    <div className="space-y-6">
      {/* 템플릿 정보 */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center gap-3 mb-2">
          <span className="px-2.5 py-1 text-xs font-medium bg-primary-100 text-primary-700 rounded-full">
            {result.template_name}
          </span>
          {result.template_type && (
            <span className="text-xs text-gray-400">
              {result.template_type}
            </span>
          )}
        </div>
        <p className="text-sm text-gray-500">
          문서가 성공적으로 생성되었습니다.
        </p>
      </div>

      {/* 마크다운 미리보기 */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-3">문서 미리보기</h2>
        <div className="prose prose-sm max-w-none bg-gray-50 rounded-lg p-4 border border-gray-100">
          <pre className="whitespace-pre-wrap text-sm text-gray-700 font-sans">
            {result.preview}
          </pre>
        </div>
      </div>

      {/* 액션 버튼 */}
      <div className="flex items-center justify-between">
        <button
          onClick={onReset}
          className="px-4 py-2 text-sm font-medium text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
        >
          새 문서 생성
        </button>
        <div className="flex gap-3">
          <button
            onClick={() => handleDownload('docx')}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
          >
            DOCX 다운로드
          </button>
          <button
            onClick={() => handleDownload('pdf')}
            className="px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 transition-colors"
          >
            PDF 다운로드
          </button>
        </div>
      </div>
    </div>
  )
}

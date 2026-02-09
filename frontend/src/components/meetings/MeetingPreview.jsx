/**
 * 회의록 미리보기 + 다운로드 컴포넌트 (팀원 E 담당)
 *
 * 표시 항목:
 *   - AI 요약
 *   - 결정사항 목록
 *   - Action Items 테이블
 *   - 리스크 경고 (있을 경우)
 *   - 마크다운 미리보기
 *   - DOCX/PDF 다운로드 버튼
 */
import { downloadMeetingDocument } from '../../api/meetings'

export default function MeetingPreview({ result, onReset }) {
  const handleDownload = async (format) => {
    try {
      const response = await downloadMeetingDocument(result.meeting_id, format)
      const blob = new Blob([response.data])
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `회의록_${result.meeting_id}.${format}`
      a.click()
      window.URL.revokeObjectURL(url)
    } catch {
      alert('다운로드에 실패했습니다.')
    }
  }

  return (
    <div className="space-y-6">
      {/* 요약 */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-3">AI 요약</h2>
        <p className="text-gray-700 leading-relaxed">{result.summary}</p>
      </div>

      {/* 결정사항 */}
      {result.decisions?.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-3">결정사항</h2>
          <ul className="list-disc list-inside space-y-1">
            {result.decisions.map((decision, i) => (
              <li key={i} className="text-gray-700">{decision}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Action Items */}
      {result.action_items?.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-3">Action Items</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-2 px-3 font-medium text-gray-600">담당자</th>
                  <th className="text-left py-2 px-3 font-medium text-gray-600">내용</th>
                  <th className="text-left py-2 px-3 font-medium text-gray-600">기한</th>
                </tr>
              </thead>
              <tbody>
                {result.action_items.map((item, i) => (
                  <tr key={i} className="border-b border-gray-100">
                    <td className="py-2 px-3 text-gray-700">{item.assignee || '-'}</td>
                    <td className="py-2 px-3 text-gray-700">{item.content}</td>
                    <td className="py-2 px-3 text-gray-500">{item.due_date || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 리스크 경고 */}
      {result.risks?.length > 0 && (
        <div className="bg-amber-50 rounded-lg border border-amber-200 p-6">
          <h2 className="text-lg font-semibold text-amber-800 mb-3">
            규정 리스크 ({result.risk_level})
          </h2>
          <ul className="space-y-2">
            {result.risks.map((risk, i) => (
              <li key={i} className="text-sm text-amber-700">
                <span className="font-medium">[{risk.level}]</span> {risk.description}
                {risk.regulation && (
                  <span className="text-amber-600"> — {risk.regulation}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

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
          새 회의록 작성
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

/**
 * 회의 내용 텍스트 입력 컴포넌트 (팀원 E 담당)
 *
 * 입력 필드:
 *   - 회의 내용 (필수): 회의 텍스트 전문
 *   - 제목 (선택): 회의 제목
 *   - 날짜 (선택): 회의 일시
 *   - 참석자 (선택): 콤마 구분
 */
import { useState } from 'react'

export default function MeetingInput({ onSubmit, loading, error }) {
  const [formData, setFormData] = useState({
    title: '',
    meeting_date: '',
    attendees: '',
    raw_content: '',
  })

  const handleChange = (field) => (e) => {
    setFormData((prev) => ({ ...prev, [field]: e.target.value }))
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!formData.raw_content.trim()) return
    onSubmit(formData)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* 메타 정보 (선택) */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">
          회의 정보 <span className="text-sm font-normal text-gray-400">(선택)</span>
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              회의 제목
            </label>
            <input
              type="text"
              value={formData.title}
              onChange={handleChange('title')}
              placeholder="예: 2026 Q1 스프린트 회의"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              회의 일시
            </label>
            <input
              type="datetime-local"
              value={formData.meeting_date}
              onChange={handleChange('meeting_date')}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              참석자
            </label>
            <input
              type="text"
              value={formData.attendees}
              onChange={handleChange('attendees')}
              placeholder="예: 김철수, 이영희, 박민수"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>
        </div>
      </div>

      {/* 회의 내용 (필수) */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">
          회의 내용 <span className="text-sm font-normal text-red-500">*</span>
        </h2>
        <textarea
          value={formData.raw_content}
          onChange={handleChange('raw_content')}
          placeholder="회의 내용을 입력하세요. 회의 중 기록한 내용이나 메모를 그대로 붙여넣어도 됩니다."
          className="w-full h-64 px-4 py-3 border border-gray-300 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          required
        />
      </div>

      {/* 에러 메시지 */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {/* 생성 버튼 */}
      <div className="flex justify-end">
        <button
          type="submit"
          disabled={loading || !formData.raw_content.trim()}
          className="px-6 py-3 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? '생성 중...' : '회의록 생성'}
        </button>
      </div>
    </form>
  )
}

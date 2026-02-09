/**
 * 템플릿 파일 업로드 다이얼로그 (팀원 E 담당)
 *
 * 사용자가 자신의 템플릿 파일(docx/pdf)을 업로드하면
 * AI가 양식 구조를 추출하여 커스텀 템플릿으로 등록
 */
import { useState } from 'react'
import { uploadTemplate } from '../../api/documents'

export default function TemplateUploadDialog({ onClose, onUploaded }) {
  const [file, setFile] = useState(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState('custom')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleFileChange = (e) => {
    const selected = e.target.files[0]
    if (selected) {
      setFile(selected)
      if (!name) {
        setName(selected.name.replace(/\.(docx|pdf)$/i, ''))
      }
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!file || !name.trim()) return

    setLoading(true)
    setError(null)
    try {
      const response = await uploadTemplate(file, {
        name: name.trim(),
        description: description.trim(),
        category,
      })
      onUploaded(response.data)
    } catch (err) {
      setError(err.response?.data?.detail || '업로드에 실패했습니다.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-800">
            새 템플릿 업로드
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            &times;
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* 파일 선택 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              파일 선택 <span className="text-red-500">*</span>
            </label>
            <input
              type="file"
              accept=".docx,.pdf"
              onChange={handleFileChange}
              className="w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100"
            />
            <p className="text-xs text-gray-400 mt-1">DOCX 또는 PDF 파일</p>
          </div>

          {/* 템플릿 이름 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              템플릿 이름 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="예: 주간 업무 보고서"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              required
            />
          </div>

          {/* 설명 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              설명
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="템플릿에 대한 간단한 설명"
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>

          {/* 카테고리 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              카테고리
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            >
              <option value="custom">사용자 정의</option>
              <option value="meeting_minutes">회의록</option>
              <option value="report">보고서</option>
              <option value="jd">채용 공고</option>
              <option value="proposal">제안서</option>
            </select>
          </div>

          {/* 에러 */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          {/* 버튼 */}
          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
            >
              취소
            </button>
            <button
              type="submit"
              disabled={loading || !file || !name.trim()}
              className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? '업로드 중...' : '업로드'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

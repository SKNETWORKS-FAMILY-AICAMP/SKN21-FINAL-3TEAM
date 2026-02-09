/**
 * 문서 요약 및 생성 페이지 (팀원 E 담당)
 *
 * 플로우:
 *   1. 사용자가 템플릿 선택 (기존 업로드 양식 or 새 파일 업로드)
 *   2. 내용/지시사항 입력
 *   3. "생성" 버튼 클릭 → POST /api/v1/documents/generate
 *   4. AI가 양식에 맞게 내용 채워서 생성
 *   5. 미리보기 표시 → DOCX/PDF 다운로드
 */
import { useState } from 'react'
import TemplateSelector from '../components/documents/TemplateSelector'
import TemplateUploadDialog from '../components/documents/TemplateUploadDialog'
import DocumentPreview from '../components/documents/DocumentPreview'
import { generateDocument } from '../api/documents'

export default function DocumentGeneratePage() {
  const [selectedTemplate, setSelectedTemplate] = useState(null)
  const [userInput, setUserInput] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [showUploadDialog, setShowUploadDialog] = useState(false)

  const handleGenerate = async () => {
    if (!selectedTemplate && !userInput.trim()) return

    setLoading(true)
    setError(null)
    try {
      const payload = {
        user_input: userInput,
        ...(selectedTemplate?.id
          ? { template_id: selectedTemplate.id }
          : { template_type: selectedTemplate?.type }),
      }
      const response = await generateDocument(payload)
      setResult(response.data)
    } catch (err) {
      setError(err.response?.data?.detail || '문서 생성에 실패했습니다.')
    } finally {
      setLoading(false)
    }
  }

  const handleReset = () => {
    setResult(null)
    setSelectedTemplate(null)
    setUserInput('')
    setError(null)
  }

  const handleTemplateUploaded = (template) => {
    setSelectedTemplate(template)
    setShowUploadDialog(false)
  }

  if (result) {
    return (
      <div className="max-w-5xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">문서 생성</h1>
        </div>
        <DocumentPreview result={result} onReset={handleReset} />
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">문서 생성</h1>
        <p className="text-sm text-gray-500 mt-1">
          템플릿을 선택하거나 업로드한 후, AI가 양식에 맞게 문서를 생성합니다.
        </p>
      </div>

      {/* 템플릿 선택 */}
      <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-800">템플릿 선택</h2>
          <button
            onClick={() => setShowUploadDialog(true)}
            className="px-4 py-2 text-sm font-medium text-primary-700 bg-primary-50 rounded-lg hover:bg-primary-100 transition-colors"
          >
            새 템플릿 업로드
          </button>
        </div>
        <TemplateSelector
          selected={selectedTemplate}
          onSelect={setSelectedTemplate}
        />
      </div>

      {/* 내용 입력 */}
      <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">내용 입력</h2>
        <textarea
          value={userInput}
          onChange={(e) => setUserInput(e.target.value)}
          placeholder="생성할 문서의 내용이나 지시사항을 입력하세요..."
          className="w-full h-40 px-4 py-3 border border-gray-300 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        />
      </div>

      {/* 에러 메시지 */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {/* 생성 버튼 */}
      <div className="flex justify-end">
        <button
          onClick={handleGenerate}
          disabled={loading || (!selectedTemplate && !userInput.trim())}
          className="px-6 py-3 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? '생성 중...' : '문서 생성'}
        </button>
      </div>

      {/* 템플릿 업로드 다이얼로그 */}
      {showUploadDialog && (
        <TemplateUploadDialog
          onClose={() => setShowUploadDialog(false)}
          onUploaded={handleTemplateUploaded}
        />
      )}
    </div>
  )
}

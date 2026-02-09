/**
 * 회의록 요약 및 생성 페이지 (팀원 E 담당)
 *
 * 플로우:
 *   1. 사용자가 회의 내용 텍스트 입력 + (선택) 제목/날짜/참석자
 *   2. "생성" 버튼 클릭 → POST /api/v1/meetings/generate
 *   3. AI가 요약 + 결정사항 + Action Items 추출 + 회의록 양식 채움
 *   4. 미리보기 표시 → DOCX/PDF 다운로드
 */
import { useState } from 'react'
import MeetingInput from '../components/meetings/MeetingInput'
import MeetingPreview from '../components/meetings/MeetingPreview'
import { generateMeetingMinutes } from '../api/meetings'

export default function MeetingMinutesPage() {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleGenerate = async (formData) => {
    setLoading(true)
    setError(null)
    try {
      const response = await generateMeetingMinutes(formData)
      setResult(response.data)
    } catch (err) {
      setError(err.response?.data?.detail || '회의록 생성에 실패했습니다.')
    } finally {
      setLoading(false)
    }
  }

  const handleReset = () => {
    setResult(null)
    setError(null)
  }

  return (
    <div className="max-w-5xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">회의록 생성</h1>
        <p className="text-sm text-gray-500 mt-1">
          회의 내용을 입력하면 AI가 요약하고 회의록 양식에 맞게 생성합니다.
        </p>
      </div>

      {!result ? (
        <MeetingInput onSubmit={handleGenerate} loading={loading} error={error} />
      ) : (
        <MeetingPreview result={result} onReset={handleReset} />
      )}
    </div>
  )
}

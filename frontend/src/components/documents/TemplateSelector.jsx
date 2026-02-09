/**
 * 템플릿 선택 그리드 컴포넌트 (팀원 E 담당)
 *
 * 시스템 기본 템플릿(4종) + 사용자 커스텀 템플릿을 그리드로 표시
 * 선택된 템플릿은 하이라이트 표시
 */
import { useState, useEffect } from 'react'
import { listTemplates } from '../../api/documents'
import { TEMPLATE_LABELS } from '../../utils/constants'

const SYSTEM_TEMPLATE_ICONS = {
  meeting_minutes: '📋',
  report: '📊',
  jd: '💼',
  proposal: '📝',
}

export default function TemplateSelector({ selected, onSelect }) {
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadTemplates()
  }, [])

  const loadTemplates = async () => {
    try {
      const response = await listTemplates()
      setTemplates(response.data)
    } catch {
      // 기본 시스템 템플릿 폴백
      setTemplates([
        { id: null, type: 'meeting_minutes', name: '회의록', category: 'meeting_minutes', is_system: true },
        { id: null, type: 'report', name: '보고서', category: 'report', is_system: true },
        { id: null, type: 'jd', name: '채용 공고', category: 'jd', is_system: true },
        { id: null, type: 'proposal', name: '제안서', category: 'proposal', is_system: true },
      ])
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return <div className="text-sm text-gray-500">템플릿 로딩 중...</div>
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {templates.map((template, index) => {
        const isSelected =
          selected?.id === template.id && selected?.type === template.type
        const icon =
          SYSTEM_TEMPLATE_ICONS[template.category] || '📄'
        const label =
          template.name ||
          TEMPLATE_LABELS[template.category] ||
          template.category

        return (
          <button
            key={template.id || `system-${index}`}
            onClick={() =>
              onSelect({
                id: template.id,
                type: template.category,
                name: label,
              })
            }
            className={`p-4 rounded-lg border-2 text-left transition-all hover:shadow-md ${
              isSelected
                ? 'border-primary-500 bg-primary-50'
                : 'border-gray-200 bg-white hover:border-gray-300'
            }`}
          >
            <div className="text-2xl mb-2">{icon}</div>
            <div className="text-sm font-medium text-gray-800">{label}</div>
            {template.is_system && (
              <div className="text-xs text-gray-400 mt-1">기본 제공</div>
            )}
            {!template.is_system && (
              <div className="text-xs text-primary-500 mt-1">커스텀</div>
            )}
          </button>
        )
      })}
    </div>
  )
}

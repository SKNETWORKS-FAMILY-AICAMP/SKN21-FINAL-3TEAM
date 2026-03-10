import { TEMPLATE_CATEGORIES } from '../../utils/constants';
import { ClipboardList, BarChart3, UserCircle, FileText, FolderOpen, Trash2 } from 'lucide-react';

const templateIcons = {
  meeting_minutes: ClipboardList,
  report: BarChart3,
  jd: UserCircle,
  proposal: FileText,
  custom: FolderOpen,
};

const categoryLabels = {
  meeting_minutes: '회의록',
  report: '보고서',
  proposal: '제안서',
};

export default function TemplateSelector({ selected, selectedCustomId, onSelect, onUploadClick, customTemplates = [], onDeleteTemplate }) {
  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">템플릿 선택</div>
        <button onClick={onUploadClick} className="btn-outline text-xs">
          + 템플릿 업로드
        </button>
      </div>
      <div className="card-body space-y-4">
        {/* 시스템 기본 템플릿 */}
        <div>
          <div className="text-xs font-semibold text-neutral-muted mb-2">기본 템플릿</div>
          <div className="grid grid-cols-3 gap-3">
            {TEMPLATE_CATEGORIES.map((tpl) => {
              const Icon = templateIcons[tpl.value] || FileText;
              const isSelected = selected === tpl.value && !selectedCustomId;
              return (
                <button
                  key={tpl.value}
                  onClick={() => onSelect?.(tpl.value, null)}
                  className={`flex items-center gap-3 p-4 rounded-sm border-2 text-left transition ${
                    isSelected
                      ? 'border-primary-500 bg-primary-50'
                      : 'border-neutral-border hover:border-primary-300 hover:bg-surface-hover'
                  }`}
                >
                  <div className={`w-10 h-10 rounded-sm flex items-center justify-center ${isSelected ? 'bg-primary-100 text-primary-700' : 'bg-surface-hover text-neutral-sub'}`}>
                    <Icon size={20} />
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-neutral-main">{tpl.label}</div>
                    <div className="text-xs text-neutral-muted mt-0.5">시스템 기본 템플릿</div>
                  </div>
                  {isSelected && (
                    <span className="ml-auto text-primary-700 font-bold">✓</span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* 커스텀 템플릿 */}
        {customTemplates.length > 0 && (
          <div>
            <div className="text-xs font-semibold text-neutral-muted mb-2">업로드된 템플릿</div>
            <div className="grid grid-cols-3 gap-3">
              {customTemplates.map((tpl) => {
                const Icon = templateIcons[tpl.category] || FolderOpen;
                const isSelected = selectedCustomId === tpl.id;
                return (
                  <button
                    key={`custom-${tpl.id}`}
                    onClick={() => onSelect?.(tpl.category, tpl)}
                    className={`flex items-center gap-3 p-4 rounded-sm border-2 text-left transition relative group ${
                      isSelected
                        ? 'border-primary-500 bg-primary-50'
                        : 'border-neutral-border hover:border-primary-300 hover:bg-surface-hover'
                    }`}
                  >
                    <div className={`w-10 h-10 rounded-sm flex items-center justify-center ${isSelected ? 'bg-primary-100 text-primary-700' : 'bg-surface-hover text-neutral-sub'}`}>
                      <Icon size={20} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-semibold text-neutral-main truncate">{tpl.name}</div>
                      <div className="text-xs text-neutral-muted mt-0.5">
                        {categoryLabels[tpl.category] || '커스텀'} · {tpl.field_count || '?'}개 필드
                      </div>
                    </div>
                    {isSelected && (
                      <span className="text-primary-700 font-bold">✓</span>
                    )}
                    {onDeleteTemplate && (
                      <button
                        onClick={(e) => { e.stopPropagation(); onDeleteTemplate(tpl.id); }}
                        className="absolute top-1 right-1 p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-red-50 text-neutral-muted hover:text-red-500 transition"
                        title="삭제"
                      >
                        <Trash2 size={14} />
                      </button>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

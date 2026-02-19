import { TEMPLATE_CATEGORIES } from '../../utils/constants';
import { ClipboardList, BarChart3, UserCircle, FileText, FolderOpen } from 'lucide-react';

const templateIcons = {
  meeting_minutes: ClipboardList,
  report: BarChart3,
  jd: UserCircle,
  proposal: FileText,
  custom: FolderOpen,
};

export default function TemplateSelector({ selected, onSelect, onUploadClick }) {
  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">템플릿 선택</div>
        <button onClick={onUploadClick} className="btn-outline text-xs">
          + 템플릿 업로드
        </button>
      </div>
      <div className="card-body">
        <div className="grid grid-cols-2 gap-3">
          {TEMPLATE_CATEGORIES.map((tpl) => {
            const Icon = templateIcons[tpl.value] || FileText;
            return (
              <button
                key={tpl.value}
                onClick={() => onSelect?.(tpl.value)}
                className={`flex items-center gap-3 p-4 rounded-sm border-2 text-left transition ${
                  selected === tpl.value
                    ? 'border-primary-500 bg-primary-50'
                    : 'border-neutral-border hover:border-primary-300 hover:bg-surface-hover'
                }`}
              >
                <div className={`w-10 h-10 rounded-sm flex items-center justify-center ${selected === tpl.value ? 'bg-primary-100 text-primary-700' : 'bg-surface-hover text-neutral-sub'}`}>
                  <Icon size={20} />
                </div>
                <div>
                  <div className="text-sm font-semibold text-neutral-main">{tpl.label}</div>
                  <div className="text-xs text-neutral-muted mt-0.5">
                    {tpl.value === 'custom' ? '직접 업로드한 템플릿' : '시스템 기본 템플릿'}
                  </div>
                </div>
                {selected === tpl.value && (
                  <span className="ml-auto text-primary-700 font-bold">✓</span>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

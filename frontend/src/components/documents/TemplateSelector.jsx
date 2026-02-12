import { TEMPLATE_CATEGORIES } from '../../utils/constants';

const templateIcons = {
  meeting_minutes: '📋',
  report: '📊',
  jd: '👤',
  proposal: '📑',
  custom: '📁',
};

export default function TemplateSelector({ selected, onSelect, onUploadClick }) {
  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><span>📂</span>템플릿 선택</div>
        <button onClick={onUploadClick} className="btn-outline text-xs">
          + 템플릿 업로드
        </button>
      </div>
      <div className="card-body">
        <div className="grid grid-cols-2 gap-3">
          {TEMPLATE_CATEGORIES.map((tpl) => (
            <button
              key={tpl.value}
              onClick={() => onSelect?.(tpl.value)}
              className={`flex items-center gap-3 p-4 rounded-sm border-2 text-left transition ${
                selected === tpl.value
                  ? 'border-primary-500 bg-primary-50'
                  : 'border-neutral-border hover:border-primary-300 hover:bg-surface-hover'
              }`}
            >
              <span className="text-2xl">{templateIcons[tpl.value] || '📄'}</span>
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
          ))}
        </div>
      </div>
    </div>
  );
}
